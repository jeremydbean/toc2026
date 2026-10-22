"""The dashboard's live log feeds and its config endpoint (review, 2026-10-22).

Two findings, each reproduced before the fix:

* /api/config resolved MUD_PUBLIC_HOST with a blocking gethostbyname() on
  the event loop, so on a cold cache a 200 ms resolver held up every other
  coroutine -- a 20 ms heartbeat came back at about 205 ms.
* The /ws/logs and /ws/events followers kept only a byte offset and called
  a file rotated when it shrank below it. A replacement of the same size
  sent nothing; a larger one had its first part skipped. The event
  follower also parsed each read as whole lines, so a record caught half
  written was split in two, and a UTF-8 character split between reads was
  mangled.

FollowedFile is the cursor both followers share now; most of these tests
drive it against temporary files. The follower tests run the real
follow_log and follow_events coroutines against a fake websocket. No real
DNS is touched: the resolver is patched.
"""
from __future__ import annotations

import ast
import asyncio
import importlib
import os
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

try:
    from fastapi.testclient import TestClient

    SKIP_REASON = None
except Exception as exc:  # pragma: no cover - C-only environments skip
    TestClient = None
    SKIP_REASON = (
        f"web test client unavailable ({type(exc).__name__}: {exc}). "
        "Install both webadmin/requirements.txt and scripts/requirements.txt."
    )


@contextmanager
def server_module():
    """Import webadmin.server against a throwaway directory."""
    with tempfile.TemporaryDirectory(prefix="toc-followers-") as temp:
        temp_root = Path(temp)
        (temp_root / "backups").mkdir()
        (temp_root / "player").mkdir()
        env = {
            "QUEUE_PATH": str(temp_root / "webadmin.queue"),
            "WEB_ADMIN_TOKEN": "secret",
            "AREA_PATH": str(ROOT / "area"),
            "BACKUP_PATH": str(temp_root / "backups"),
            "PLAYER_PATH": str(temp_root / "player"),
            "LOG_FILE": str(temp_root / "toc.log"),
            "EVENT_LOG_FILE": str(temp_root / "events.tsv"),
            "MUD_HOST": "127.0.0.1",
            "MUD_PORT": "65534",
            "WEB_ADMIN_BIND": "127.0.0.1",
            "WEB_ADMIN_LOCAL_UNLOCK": "0",
            "WEB_ADMIN_HOST_STATUS": "0",
            "TOC_UPDATE_REQUEST_PATH": "",
        }
        with patch.dict(os.environ, env, clear=False):
            sys.modules.pop("webadmin.server", None)
            server = importlib.import_module("webadmin.server")
            try:
                yield server, temp_root
            finally:
                sys.modules.pop("webadmin.server", None)


def replace_file(path: Path, data: bytes) -> None:
    """Swap in a new file (new inode) the way a log rotation does."""
    staged = path.with_name(path.name + ".new")
    staged.write_bytes(data)
    os.replace(staged, path)


@unittest.skipIf(TestClient is None, SKIP_REASON or "")
class PublicHostTests(unittest.TestCase):
    """Behaviour tests: get_config and public_game_host with a fake resolver."""

    def setUp(self) -> None:
        self._module = server_module()
        self.server, _ = self._module.__enter__()
        self.server.MUD_PUBLIC_HOST = "synthetic.invalid"
        self.server.MUD_PUBLIC_PORT = 4000
        self.server._PUBLIC_IP_CACHE = (0.0, "")
        self.calls = 0
        self.calls_lock = threading.Lock()

    def tearDown(self) -> None:
        self._module.__exit__(None, None, None)

    def slow_resolver(self, delay: float, answer: str = "192.0.2.1"):
        def resolve(name: str) -> str:
            with self.calls_lock:
                self.calls += 1
            time.sleep(delay)
            return answer
        return resolve

    def run_config_beside_heartbeat(self, concurrent: int = 1):
        """Run get_config while a 20 ms heartbeat waits; return both results."""
        async def scenario():
            started = time.monotonic()

            async def heartbeat() -> float:
                await asyncio.sleep(0.02)
                return time.monotonic() - started

            pulse = asyncio.create_task(heartbeat())
            await asyncio.sleep(0)
            configs = await asyncio.gather(
                *(self.server.get_config(None) for _ in range(concurrent)))
            return configs, await pulse

        with patch.object(self.server, "local_admin_request_allowed", lambda _: False):
            return asyncio.run(scenario())

    def test_a_slow_resolver_does_not_stall_the_event_loop(self) -> None:
        with patch.object(self.server.socket, "gethostbyname", self.slow_resolver(0.3)):
            configs, heartbeat = self.run_config_beside_heartbeat()
        self.assertEqual(configs[0]["mud_endpoint"], "192.0.2.1:4000")
        # Due at 20 ms; on the loop it came back after the whole lookup.
        self.assertLess(heartbeat, 0.15, f"heartbeat delayed to {heartbeat:.3f}s")

    def test_concurrent_cold_requests_share_one_lookup(self) -> None:
        with patch.object(self.server.socket, "gethostbyname", self.slow_resolver(0.2)):
            configs, heartbeat = self.run_config_beside_heartbeat(concurrent=4)
        self.assertEqual({config["mud_endpoint"] for config in configs}, {"192.0.2.1:4000"})
        self.assertEqual(self.calls, 1)
        self.assertLess(heartbeat, 0.15)

    def test_a_failed_lookup_falls_back_to_the_name(self) -> None:
        def fail(name: str) -> str:
            self.calls += 1
            raise OSError("synthetic resolver failure")

        with patch.object(self.server.socket, "gethostbyname", fail):
            configs, _ = self.run_config_beside_heartbeat()
            self.assertEqual(configs[0]["mud_endpoint"], "synthetic.invalid:4000")
            # The fallback is cached like an answer, as it always was.
            configs, _ = self.run_config_beside_heartbeat()
        self.assertEqual(configs[0]["mud_endpoint"], "synthetic.invalid:4000")
        self.assertEqual(self.calls, 1)

    def test_a_warm_cache_never_calls_the_resolver(self) -> None:
        self.server._PUBLIC_IP_CACHE = (time.monotonic(), "198.51.100.7")

        def forbidden(name: str) -> str:
            raise AssertionError("resolver called on a warm cache")

        with patch.object(self.server.socket, "gethostbyname", forbidden):
            configs, _ = self.run_config_beside_heartbeat()
        self.assertEqual(configs[0]["mud_endpoint"], "198.51.100.7:4000")

    def test_an_expired_cache_resolves_again(self) -> None:
        stale = time.monotonic() - self.server._PUBLIC_IP_TTL - 1
        self.server._PUBLIC_IP_CACHE = (stale, "198.51.100.7")
        with patch.object(self.server.socket, "gethostbyname", self.slow_resolver(0.0, "192.0.2.9")):
            configs, _ = self.run_config_beside_heartbeat()
        self.assertEqual(configs[0]["mud_endpoint"], "192.0.2.9:4000")
        self.assertEqual(self.calls, 1)

    def test_the_endpoint_keeps_its_fields(self) -> None:
        with patch.object(self.server.socket, "gethostbyname", self.slow_resolver(0.0)):
            with TestClient(self.server.app) as client:
                config = client.get("/api/config").json()
        self.assertEqual(config["mud_endpoint"], "192.0.2.1:4000")
        self.assertEqual(config["mud_endpoint_host"], "synthetic.invalid")
        self.assertIs(config["admin_token_configured"], True)
        # A test client is not a loopback peer, so no local unlock.
        self.assertIs(config["local_admin_unlock"], False)
        self.assertEqual(set(config), {
            "version", "admin_token_configured", "local_admin_unlock",
            "mud_endpoint", "mud_endpoint_host", "client_path",
            "game_websocket_auth", "player_data_protected",
            "log_websocket_auth", "event_websocket_auth",
            "update_available", "host_status_available",
        })


@unittest.skipIf(TestClient is None, SKIP_REASON or "")
class FollowedFileTests(unittest.TestCase):
    """Behaviour tests: the shared cursor against real temporary files."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._module = server_module()
        cls.server, _ = cls._module.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._module.__exit__(None, None, None)

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory(prefix="toc-cursor-")
        self.path = Path(self._temp.name) / "followed.log"

    def tearDown(self) -> None:
        self._temp.cleanup()

    def cursor(self, **kwargs):
        return self.server.FollowedFile(self.path, **kwargs)

    def test_appended_text_is_returned_once(self) -> None:
        self.path.write_bytes(b"one\n")
        cursor = self.cursor()
        self.assertEqual(cursor.snapshot(200), "one\n")
        self.assertEqual(cursor.poll(), "")
        with self.path.open("ab") as handle:
            handle.write(b"two\n")
        self.assertEqual(cursor.poll(), "two\n")
        self.assertEqual(cursor.poll(), "")

    def test_a_same_size_replacement_is_noticed(self) -> None:
        self.path.write_bytes(b"old\n")
        cursor = self.cursor()
        cursor.snapshot(200)
        replace_file(self.path, b"new\n")
        self.assertIsNone(cursor.poll())
        self.assertEqual(cursor.snapshot(200), "new\n")
        self.assertEqual(cursor.poll(), "")

    def test_a_larger_replacement_is_not_read_from_the_old_offset(self) -> None:
        self.path.write_bytes(b"old\n")
        cursor = self.cursor()
        cursor.snapshot(200)
        replace_file(self.path, b"fresh start\nmore\n")
        self.assertIsNone(cursor.poll())
        self.assertEqual(cursor.snapshot(200), "fresh start\nmore\n")

    def test_a_truncated_file_is_noticed(self) -> None:
        self.path.write_bytes(b"a long first line\n")
        cursor = self.cursor()
        cursor.snapshot(200)
        with self.path.open("r+b") as handle:
            handle.truncate(0)
            handle.write(b"short\n")
        self.assertIsNone(cursor.poll())
        self.assertEqual(cursor.snapshot(200), "short\n")

    def test_a_vanished_file_is_nothing_new_until_it_returns(self) -> None:
        self.path.write_bytes(b"before\n")
        cursor = self.cursor()
        cursor.snapshot(200)
        self.path.unlink()
        self.assertEqual(cursor.poll(), "")
        self.assertEqual(cursor.poll(), "")
        self.path.write_bytes(b"after\n")
        self.assertIsNone(cursor.poll())
        self.assertEqual(cursor.snapshot(200), "after\n")
        with self.path.open("ab") as handle:
            handle.write(b"later\n")
        self.assertEqual(cursor.poll(), "later\n")

    def test_a_file_missing_at_the_start_is_picked_up(self) -> None:
        cursor = self.cursor()
        self.assertEqual(cursor.snapshot(200), "")
        self.assertEqual(cursor.poll(), "")
        self.path.write_bytes(b"born\n")
        self.assertIsNone(cursor.poll())
        self.assertEqual(cursor.snapshot(200), "born\n")

    def test_a_record_split_across_reads_is_held_until_complete(self) -> None:
        self.path.write_bytes(b"")
        cursor = self.cursor(whole_lines=True)
        cursor.snapshot(300)
        with self.path.open("ab") as handle:
            handle.write(b"1787680002\twizinfo\t70\tLive ev")
        self.assertEqual(cursor.poll(), "")
        with self.path.open("ab") as handle:
            handle.write(b"ent.\n1787680003\tinfo\t0\tNext")
        text = cursor.poll()
        self.assertEqual(text, "1787680002\twizinfo\t70\tLive event.\n")
        self.assertEqual(self.server.parse_server_events(text, 10)[0]["message"], "Live event.")
        with self.path.open("ab") as handle:
            handle.write(b".\n")
        self.assertEqual(cursor.poll(), "1787680003\tinfo\t0\tNext.\n")

    def test_a_snapshot_holds_back_a_half_written_record(self) -> None:
        self.path.write_bytes(b"1787680001\tinfo\t0\tWhole.\n1787680002\tinfo\t0\tHal")
        cursor = self.cursor(whole_lines=True)
        self.assertEqual(cursor.snapshot(300), "1787680001\tinfo\t0\tWhole.\n")
        with self.path.open("ab") as handle:
            handle.write(b"f.\n")
        self.assertEqual(cursor.poll(), "1787680002\tinfo\t0\tHalf.\n")

    def test_a_multibyte_character_split_across_reads_survives(self) -> None:
        word = "café — done\n".encode("utf-8")
        split = word.index(b"\xe2") + 1  # inside the three-byte em dash
        for whole_lines in (False, True):
            with self.subTest(whole_lines=whole_lines):
                self.path.write_bytes(b"")
                cursor = self.cursor(whole_lines=whole_lines)
                cursor.snapshot(200)
                with self.path.open("ab") as handle:
                    handle.write(word[:split])
                first = cursor.poll()
                with self.path.open("ab") as handle:
                    handle.write(word[split:])
                second = cursor.poll()
                self.assertEqual(first + second, "café — done\n")
                self.assertNotIn("�", first + second)


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list = []
        self.arrived = asyncio.Event()

    async def send_text(self, text: str) -> None:
        self.sent.append(text)
        self.arrived.set()

    async def send_json(self, payload) -> None:
        self.sent.append(payload)
        self.arrived.set()

    async def next(self, count: int, timeout: float = 5.0):
        """Wait until `count` messages have been sent; return the last."""
        async def wait() -> None:
            while len(self.sent) < count:
                self.arrived.clear()
                await self.arrived.wait()
        await asyncio.wait_for(wait(), timeout)
        return self.sent[count - 1]


@unittest.skipIf(TestClient is None, SKIP_REASON or "")
class FollowerTests(unittest.TestCase):
    """Behaviour tests: the real follow_log/follow_events coroutines."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._module = server_module()
        cls.server, _ = cls._module.__enter__()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._module.__exit__(None, None, None)

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory(prefix="toc-follow-")
        self.path = Path(self._temp.name) / "followed"

    def tearDown(self) -> None:
        self._temp.cleanup()

    def follow(self, follower, script) -> None:
        async def scenario() -> None:
            websocket = FakeWebSocket()
            task = asyncio.create_task(follower(websocket, self.path, interval=0.01))
            try:
                await script(websocket)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        asyncio.run(scenario())

    def test_the_log_follower_sends_a_same_size_replacement(self) -> None:
        self.path.write_bytes(b"old\n")

        async def script(websocket: FakeWebSocket) -> None:
            self.assertEqual(await websocket.next(1), "old\n")
            await asyncio.sleep(0.05)
            replace_file(self.path, b"new\n")
            self.assertEqual(await websocket.next(2), "new\n")
            with self.path.open("ab") as handle:
                handle.write(b"appended\n")
            self.assertEqual(await websocket.next(3), "appended\n")

        self.follow(self.server.follow_log, script)

    def test_the_log_follower_sends_all_of_a_larger_replacement(self) -> None:
        self.path.write_bytes(b"old\n")

        async def script(websocket: FakeWebSocket) -> None:
            await websocket.next(1)
            await asyncio.sleep(0.05)
            replace_file(self.path, b"first of new\nsecond of new\n")
            self.assertEqual(await websocket.next(2), "first of new\nsecond of new\n")

        self.follow(self.server.follow_log, script)

    def test_the_event_follower_resnapshots_a_replacement_and_waits_for_whole_records(self) -> None:
        self.path.write_bytes(b"1787680000\tinfo\t0\tOld.\n")

        async def script(websocket: FakeWebSocket) -> None:
            first = await websocket.next(1)
            self.assertEqual(first["type"], "snapshot")
            self.assertEqual([e["message"] for e in first["events"]], ["Old."])
            await asyncio.sleep(0.05)
            replace_file(self.path, b"1787680001\tinfo\t0\tNew.\n")
            second = await websocket.next(2)
            self.assertEqual(second["type"], "snapshot")
            self.assertEqual([e["message"] for e in second["events"]], ["New."])
            with self.path.open("ab") as handle:
                handle.write(b"1787680002\twizinfo\t70\tSpl")
            await asyncio.sleep(0.1)
            self.assertEqual(len(websocket.sent), 2, websocket.sent)
            with self.path.open("ab") as handle:
                handle.write("it — whole.\n".encode("utf-8"))
            third = await websocket.next(3)
            self.assertEqual(third["type"], "events")
            self.assertEqual([e["message"] for e in third["events"]], ["Split — whole."])

        self.follow(self.server.follow_events, script)


class FollowerSourceTests(unittest.TestCase):
    """Source assertions: both endpoints run the shared followers."""

    def test_both_websockets_follow_through_followed_file(self) -> None:
        tree = ast.parse((ROOT / "webadmin" / "server.py").read_text(encoding="utf-8"))
        functions = {node.name: node for node in tree.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}

        def calls(node) -> set[str]:
            return {sub.func.id for sub in ast.walk(node)
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)}

        self.assertIn("follow_log", calls(functions["websocket_logs"]))
        self.assertIn("follow_events", calls(functions["websocket_events"]))
        for follower in ("follow_log", "follow_events"):
            body = functions[follower]
            self.assertIn("FollowedFile", calls(body), follower)
            # No size-only rotation test left behind in either.
            self.assertNotIn("st_size", ast.unparse(body), follower)


if __name__ == "__main__":
    unittest.main()

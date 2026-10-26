"""Connection and login bugs from the 2026-10-22 audit, played live.

Each test here failed on the code before its fix:

* One client that stopped reading froze the whole game: the write loop
  retried EAGAIN on a non-blocking socket for ever (finding 1).
* A login begun at the name prompt entered with the copy read there, so a
  file changed meanwhile -- the character quit after giving something away,
  or was PRESTOREd -- came back as it was (finding 3). Hanging up at that
  password prompt wrote the old copy over the file the same way.
* Two connections could create the same new name at once (finding 10).
* ``purge self`` from the dashboard queue extracted the stand-in twice
  (finding 19).
* A PROXY header was accepted on any name-prompt line, and the web bridge
  sent none for an IPv6 player, who then stayed "loopback" (finding 20).

Every character is a throwaway Z-name in a throwaway world.
"""
from __future__ import annotations

import importlib
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from live_mud import (  # noqa: E402
    LiveMud,
    MudClient,
    _enter_game,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

try:
    from fastapi.testclient import TestClient  # noqa: E402

    WEBADMIN_UNAVAILABLE_REASON = None
except Exception as exc:  # pragma: no cover - C-only environments skip this
    TestClient = None
    WEBADMIN_UNAVAILABLE_REASON = (
        f"webadmin dependencies unavailable ({type(exc).__name__}: {exc}). "
        "Install webadmin/requirements.txt."
    )

SKIP = skip_reason()
REPO_ROOT = Path(__file__).resolve().parents[1]
PW = "Zpass12345"
SWORD = "Vnum 3702"          # the sub issue sword a warrior starts with


def run(client: MudClient, command: str, seconds: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(seconds)
    return client.transcript[mark:]


def journal_rows(mud: LiveMud) -> list[list[str]]:
    path = mud.root / "log" / "logins.tsv"
    if not path.is_file():
        return []
    return [line.split("\t")
            for line in path.read_text(encoding="latin-1").splitlines()
            if line.strip()]


def hosts_for(mud: LiveMud, name: str) -> list[str]:
    return [row[2] for row in journal_rows(mud) if len(row) > 2 and row[1] == name]


def file_text(mud: LiveMud, name: str) -> str:
    return (mud.player_dir / name).read_text(encoding="latin-1")


def greeting_arrives(port: int, timeout: float = 5.0) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as s:
            s.settimeout(timeout)
            return len(s.recv(4096)) > 0
    except OSError:
        return False


def stuck_server_report(mud: LiveMud) -> str:
    """Where a live server that stopped answering is: its state, the
    syscall it sits in, a backtrace if gdb is about, and then the game's
    own crash ring (last commands, update phase), written on SIGABRT.
    CI's artifacts cannot be fetched from everywhere a failure is read,
    so the failure line has to carry this itself."""
    pid = mud.proc.pid
    parts = []
    for name in ("stat", "wchan", "syscall"):
        try:
            text = Path(f"/proc/{pid}/{name}").read_text().strip()
        except OSError as exc:
            text = f"? ({exc.strerror})"
        if name == "stat":
            text = "state " + text.rsplit(")", 1)[-1].split()[0]
        parts.append(f"{name}: {text}")
    if shutil.which("gdb"):
        try:
            bt = subprocess.run(["gdb", "-p", str(pid), "-batch", "-ex", "bt 12"],
                                capture_output=True, text=True, timeout=60).stdout
            frames = [" ".join(line.split()[3:6]) if " in " in line else line
                      for line in bt.splitlines() if line.startswith("#")]
            parts.append("bt: " + " < ".join(frames))
        except (OSError, subprocess.TimeoutExpired) as exc:
            parts.append(f"bt: ? ({exc})")
    try:
        os.kill(pid, signal.SIGABRT)
        mud.proc.wait(timeout=10)
        crash = (mud.root / "log" / "crash.log").read_text(errors="replace")
        parts.append("crash ring: " + " / ".join(crash.strip().splitlines()[-12:]))
    except (OSError, subprocess.TimeoutExpired) as exc:
        parts.append(f"crash ring: ? ({exc})")
    return " | ".join(parts)


def wait_at_password(mud: LiveMud, name: str) -> MudClient:
    """A second connection that has typed the name and stopped there."""
    client = mud.connect(timeout=120)
    client.expect("by what name", "name:")
    client.send(name)
    client.expect("password")
    return client


@unittest.skipIf(SKIP is not None, SKIP or "")
class SlowReaderTests(unittest.TestCase):
    def test_a_client_that_stops_reading_does_not_freeze_the_game(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zslowpoke", PW)
                client.command("scroll 0", settle=0.5)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            # A tiny receive window, and then never read again.
            slow = socket.socket()
            slow.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
            slow.connect(("127.0.0.1", mud.port))
            slow.settimeout(1.0)

            def soak(seconds: float) -> None:
                end = time.monotonic() + seconds
                while time.monotonic() < end:
                    try:
                        if not slow.recv(65536):
                            return
                    except socket.timeout:
                        return

            soak(1.0)
            for line in (b"Zslowpoke\r\n", PW.encode() + b"\r\n", b"\r\n", b"\r\n", b"\r\n"):
                slow.sendall(line)
                soak(0.8)

            self.assertTrue(greeting_arrives(mud.port), "no greeting before the flood")

            # Each of these runs past the 32,000-byte output buffer. They
            # rotate because the game stops a word repeated 25 times.
            commands = (b"changes all\r\n", b"change all\r\n", b"chang all\r\n")
            slow.setblocking(False)
            dropped = False
            sent = 0
            checked = 0
            deadline = time.monotonic() + 150
            try:
                while time.monotonic() < deadline:
                    try:
                        slow.send(commands[sent % 3])
                        sent += 1
                    except BlockingIOError:
                        pass
                    except OSError:
                        dropped = True          # the game let go of us
                        break
                    time.sleep(0.3)
                    if sent % 10 or sent == checked:
                        continue
                    checked = sent
                    # The game's own saves fsync on the main loop, and a
                    # shared CI runner's disk can hold one for seconds; the
                    # bug this guards against froze the game for good.
                    began = time.monotonic()
                    if not greeting_arrives(mud.port, timeout=20.0):
                        # CI reprints only this first line: say whether
                        # the server is alive and what it said last.
                        tail = [line.split(" :: ", 1)[-1] for line in
                                mud.server_output().splitlines() if line.strip()][-4:]
                        waited = time.monotonic() - began
                        self.fail(f"the game stopped answering new connections "
                                  f"after {sent} floods from one client that never "
                                  f"reads ({waited:.1f}s); "
                                  f"server exit={mud.proc.poll()}; last: "
                                  + " | ".join(tail) + " || "
                                  + stuck_server_report(mud))
            finally:
                slow.close()

            self.assertTrue(dropped, "the client that never reads was never let go")
            self.assertTrue(greeting_arrives(mud.port, timeout=20.0))
            self.assertIn("stopped reading", mud.server_output())


@unittest.skipIf(SKIP is not None, SKIP or "")
class StaleLoginCopyTests(unittest.TestCase):
    def test_a_give_and_quit_during_the_password_prompt_is_not_undone(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as fence:
                create_character(fence, "Zfencee", PW)
                with mud.connect(timeout=120) as owner:
                    create_character(owner, "Zduperr", PW)
                    run(owner, "remove sword")
                    run(owner, "save", 3.0)
                    late = wait_at_password(mud, "Zduperr")
                    run(owner, "give sword zfencee", 4.0)
                    owner.send("quit")
                    self.assertTrue(owner.wait_closed())

                self.assertNotIn(SWORD, file_text(mud, "Zduperr"),
                                 "the give was not saved")
                with late:
                    late.send(PW)
                    late.drain(1.0)
                    if "y or n" in late.buffer.lower():
                        late.send("Y")
                    _enter_game(late)
                    carried = run(late, "inventory") + run(late, "equipment")
                    self.assertIn("sword", run(fence, "inventory").lower())
                    self.assertNotIn("sword", carried.lower(),
                                     "the late login came in holding the sword "
                                     "it had already given away")
                    late.send("quit")
                    self.assertTrue(late.wait_closed())

            self.assertNotIn(SWORD, file_text(mud, "Zduperr"),
                             "the file got the given-away sword back")

    def test_hanging_up_at_the_password_prompt_writes_nothing(self) -> None:
        """The copy read at the name prompt was saved on a dropped link."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as fence:
                create_character(fence, "Zfencetwo", PW)
                with mud.connect(timeout=120) as owner:
                    create_character(owner, "Zhangup", PW)
                    run(owner, "remove sword")
                    run(owner, "save", 3.0)
                    late = wait_at_password(mud, "Zhangup")
                    run(owner, "give sword zfencetwo", 4.0)
                    owner.send("quit")
                    self.assertTrue(owner.wait_closed())
                self.assertNotIn(SWORD, file_text(mud, "Zhangup"))

                late.close()                  # hang up at the password prompt
                fence.drain(3.0)              # let the game notice the EOF

            self.assertNotIn(SWORD, file_text(mud, "Zhangup"),
                             "hanging up wrote the name-prompt copy over the file")

    def test_a_prestore_during_the_password_prompt_survives_the_login(self) -> None:
        with LiveMud() as mud:
            for name in ("Zpregod", "Zprevict"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zpregod", Levl=70, Room=4207)
            patch_player_file(mud, "Zprevict", Room=4207)

            with mud.connect(timeout=120) as god:
                login(god, "Zpregod", PW)
                victim = mud.connect(timeout=120)
                login(victim, "Zprevict", PW)
                run(god, "goto 4207")
                run(victim, "remove sword")
                run(victim, "give sword zpregod")
                run(victim, "save", 6.0)
                self.assertNotIn(SWORD, file_text(mud, "Zprevict"))
                victim.close()                # link-dead
                god.drain(2.0)

                listing = run(god, "prestore zprevict", 2.0)
                stamps = re.findall(r"stamp (\S+)", listing)
                self.assertTrue(stamps, listing)

                late = wait_at_password(mud, "Zprevict")
                restored = run(god, "prestore zprevict %s" % stamps[-1], 3.0)
                self.assertIn(SWORD, file_text(mud, "Zprevict"),
                              "the oldest snapshot should hold the sword: " + restored)

                with late:
                    late.send(PW)
                    late.drain(1.0)
                    if "y or n" in late.buffer.lower():
                        late.send("Y")
                    _enter_game(late)
                    late.send("quit")
                    self.assertTrue(late.wait_closed())

            self.assertIn(SWORD, file_text(mud, "Zprevict"),
                          "the login undid the PRESTORE")


@unittest.skipIf(SKIP is not None, SKIP or "")
class DuplicateCreationTests(unittest.TestCase):
    def test_a_name_being_created_is_refused_to_a_second_connection(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as first, mud.connect(timeout=120) as second:
                first.expect("by what name", "name:")
                second.expect("by what name", "name:")
                first.send("Zsamename")
                first.expect("right")

                mark = len(second.transcript)
                second.send("Zsamename")
                second.expect("choose another", "right")
                second.drain(0.5)
                answer = second.transcript[mark:]
                self.assertIn("being taken by someone else", answer)
                self.assertNotIn("did i get that right", answer.lower())

                # The first creation goes on undisturbed, and the second
                # connection is still at a name prompt it can use.
                first.buffer = "did i get that right"
                _enter_game(first, PW)
                create_character_after_refusal(second, "Zothername")
                who = run(first, "who", 2.0)
                self.assertEqual(who.count("Zsamename"), 1, who)
                for client in (first, second):
                    client.send("quit")
                    self.assertTrue(client.wait_closed())


def create_character_after_refusal(client: MudClient, name: str) -> None:
    client.buffer = ""
    client.send(name)
    _enter_game(client, PW)


@unittest.skipIf(SKIP is not None, SKIP or "")
class WebQueuePurgeTests(unittest.TestCase):
    def test_purge_self_from_the_queue_extracts_nothing_twice(self) -> None:
        with LiveMud() as mud:
            queue = mud.root / "area" / "webadmin.queue"
            for line in ("command|purge self", "command|at 3001 purge self"):
                queue.write_text(line + "\n", encoding="latin-1")
                deadline = time.monotonic() + 10
                while queue.exists() and queue.stat().st_size and time.monotonic() < deadline:
                    time.sleep(0.25)
                time.sleep(1.0)
                self.assertIsNone(mud.proc.poll(), "the game died on " + line)

            output = mud.server_output()
            self.assertNotIn("Extract_char", output,
                             "the stand-in was extracted twice")
            with mud.connect(timeout=30) as client:
                client.expect("by what name", "name:")


@unittest.skipIf(SKIP is not None, SKIP or "")
class ProxyHeaderTests(unittest.TestCase):
    def test_a_proxy_line_after_the_first_is_only_a_name(self) -> None:
        claimed = "203.0.113.55"
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                client.expect("by what name", "name:")
                client.send("Zx9")                 # an ordinary first line
                client.expect("illegal name")
                client.send(f"PROXY TCP4 {claimed} 127.0.0.1 51000 {mud.port}")
                client.drain(1.0)
                client.buffer = ""
                client.send("Zproxylate")
                _enter_game(client, PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            hosts = hosts_for(mud, "Zproxylate")
            self.assertTrue(hosts, "no journal row")
            self.assertNotIn(claimed, hosts,
                             "a PROXY line typed at a later prompt renamed the address")

    def test_an_ipv6_header_names_the_player(self) -> None:
        with LiveMud() as mud:
            for name, header, expected in (
                ("Zproxysix", "PROXY TCP6 2001:db8::7 ::1 51000 {port}", "2001:db8::7"),
                ("Zproxymap", "PROXY TCP6 ::ffff:203.0.113.8 ::1 51001 {port}", "203.0.113.8"),
                ("Zproxynone", "PROXY UNKNOWN", None),
            ):
                with mud.connect(timeout=120) as client:
                    client.send(header.format(port=mud.port))
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                hosts = hosts_for(mud, name)
                self.assertTrue(hosts, f"no journal row for {name}: the header became a name?")
                if expected is not None:
                    self.assertEqual(hosts[0], expected)

    def test_ipv6_failures_are_throttled_together(self) -> None:
        """Two addresses in one /64 share a throttle bucket; loopback has none."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zsixthrot", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            blocked = False
            for attempt in range(8):
                with mud.connect(timeout=30) as client:
                    # A different address each time, all in one /64.
                    client.send(f"PROXY TCP6 2001:db8:5::{attempt + 1} ::1 {51000 + attempt} {mud.port}")
                    client.drain(1.0)
                    if "too many failed" in client.buffer.lower():
                        blocked = True
                        break
                    client.buffer = ""
                    client.send("Zsixthrot")
                    client.expect("password")
                    client.send("wrongpassword")
                    client.expect("wrong password")
                    client.wait_closed(10)
            self.assertTrue(blocked, "an IPv6 player could guess passwords without limit")


@unittest.skipIf(SKIP is not None, SKIP or "")
@unittest.skipIf(WEBADMIN_UNAVAILABLE_REASON is not None, WEBADMIN_UNAVAILABLE_REASON or "")
class BridgeHeaderTests(unittest.TestCase):
    def test_the_bridge_names_an_ipv6_player(self) -> None:
        peer = ("2001:db8::9", 50123)
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zbridgesix", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            with tempfile.TemporaryDirectory() as tmp:
                env = {
                    "WEB_ADMIN_TOKEN": "secret",
                    "AREA_PATH": str(REPO_ROOT / "area"),
                    "PLAYER_PATH": str(Path(tmp)),
                    "BACKUP_PATH": str(Path(tmp)),
                    "QUEUE_PATH": str(Path(tmp) / "webadmin.queue"),
                    "MUD_HOST": "127.0.0.1",
                    "MUD_PORT": str(mud.port),
                    "TOC_UPDATE_REQUEST_PATH": "",
                }
                with patch.dict(os.environ, env, clear=False):
                    sys.modules.pop("webadmin.server", None)
                    server = importlib.import_module("webadmin.server")
                    try:
                        with TestClient(server.app, client=peer) as http:
                            with http.websocket_connect("/ws") as ws:
                                self.assertEqual(ws.receive_text(), "\0TOC_CONNECTED")
                                time.sleep(1.0)
                                ws.send_text("Zbridgesix\r\n")
                                time.sleep(1.0)
                                ws.send_text(PW + "\r\n")
                                deadline = time.monotonic() + 15
                                while not hosts_for(mud, "Zbridgesix") and time.monotonic() < deadline:
                                    time.sleep(0.25)
                                ws.send_text("\r\n")
                                time.sleep(0.5)
                                ws.send_text("quit\r\n")
                                time.sleep(1.0)
                    finally:
                        sys.modules.pop("webadmin.server", None)

            hosts = hosts_for(mud, "Zbridgesix")
            self.assertTrue(hosts, "the bridged login never reached the journal")
            self.assertEqual(hosts[-1], "2001:db8::9",
                             "a bridged IPv6 player was recorded as " + hosts[-1])


if __name__ == "__main__":
    unittest.main()

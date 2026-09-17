from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

try:
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    TESTCLIENT_UNAVAILABLE_REASON = None
except Exception as exc:  # pragma: no cover - local C-only environments can skip this
    TestClient = None
    WebSocketDisconnect = Exception
    # Report why the client is missing. starlette's TestClient raises a
    # RuntimeError (not ImportError) when httpx2 is absent, so a blanket
    # "fastapi is not installed" message sends readers after the wrong
    # package. Both webadmin/requirements.txt and scripts/requirements.txt
    # are needed for these tests; CI installs both.
    TESTCLIENT_UNAVAILABLE_REASON = (
        f"web test client unavailable ({type(exc).__name__}: {exc}). "
        "Install both webadmin/requirements.txt and scripts/requirements.txt."
    )


PLAYER_FIXTURE = """#PLAYER
Name MiXeD~
Race elf~
Sex 2
Cla 3
Gui 3
Levl 12
LogO 1700050000
Plyd 7200
Room 3001
SesLogin 1700046400
SesDur   1800
HMV 100 200 150 250 75 100
Attr 14 15 16 17 18
AMod 1 2 3 4 5
ACs -10 -20 -30 -40
Hit 7
Dam 8
Exp 12345
Prac 4
Trai 2
QuestPnts 9
Alig 250
NewGold 500
NewPlat 12
NumRemorts 1
Titl the Test Hero~
Desc
A deliberately mixed-case player.
~
Sk 75 'sword'
#O
Vnum 1
Wear 6
Lev 10
End
#END
"""


class WebAdminApiTests(unittest.TestCase):
    @contextmanager
    def webadmin_client(
        self,
        local_unlock: bool = False,
        web_bind: str = "127.0.0.1",
        host_status: bool = False,
        peer: tuple[str, int] = ("127.0.0.1", 40000),
    ):
        if TestClient is None:
            self.skipTest(TESTCLIENT_UNAVAILABLE_REASON)

        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            player_path = temp_root / "players"
            backup_path = temp_root / "backups"
            log_path = temp_root / "toc.log"
            event_path = temp_root / "webadmin-events.tsv"
            queue_path = temp_root / "webadmin.queue"
            player_path.mkdir()
            backup_path.mkdir()
            (player_path / "MiXeD").write_text(PLAYER_FIXTURE, encoding="latin-1")
            (player_path / "notes").mkdir()
            (player_path / "invalid-name").write_text("ignored", encoding="ascii")
            log_path.write_text("first line\nsecond line\nthird line\n", encoding="utf-8")
            event_path.write_text(
                "1787680000\tinfo\t0\tA player reached level 20.\n"
                "1787680001\twizinfo\t62\tAutomated backup complete.\n",
                encoding="utf-8",
            )

            env = {
                "QUEUE_PATH": str(queue_path),
                "WEB_ADMIN_TOKEN": "secret",
                "AREA_PATH": str(repo_root / "area"),
                "BACKUP_PATH": str(backup_path),
                "PLAYER_PATH": str(player_path),
                "LOG_FILE": str(log_path),
                "EVENT_LOG_FILE": str(event_path),
                "MUD_HOST": "127.0.0.1",
                "MUD_PORT": "65534",
                "WEB_ADMIN_BIND": web_bind,
                "WEB_ADMIN_LOCAL_UNLOCK": "1" if local_unlock else "0",
                "WEB_ADMIN_HOST_STATUS": "1" if host_status else "0",
                "TOC_UPDATE_REQUEST_PATH": "",
            }
            with patch.dict(os.environ, env, clear=False):
                sys.modules.pop("webadmin.server", None)
                server = importlib.import_module("webadmin.server")
                try:
                    base_url = "http://127.0.0.1:9001" if local_unlock else "http://testserver"
                    server.set_bind_address(web_bind)
                    with TestClient(server.app, base_url=base_url, client=peer) as client:
                        yield server, client, temp_root
                finally:
                    sys.modules.pop("webadmin.server", None)

    def test_self_contained_interface_and_paginated_catalogs(self) -> None:
        with self.webadmin_client() as (server, client, _):
            page = client.get("/")
            self.assertEqual(page.status_code, 200)
            self.assertIn("Times of Chaos Admin", page.text)
            self.assertIn('/static/app.js', page.text)
            self.assertIn('/static/command-sequence.js', page.text)
            self.assertIn('/static/console-output.js', page.text)
            self.assertIn('href="/client"', page.text)
            self.assertNotIn("cdn.", page.text)
            self.assertNotIn("tailwind", page.text.lower())
            self.assertIn("default-src 'self'", page.headers["Content-Security-Policy"])
            self.assertEqual(page.headers["X-Frame-Options"], "DENY")
            self.assertEqual(client.get("/docs").status_code, 404)

            stylesheet = client.get("/static/app.css")
            script = client.get("/static/app.js")
            command_sequence = client.get("/static/command-sequence.js")
            console_output = client.get("/static/console-output.js")
            self.assertEqual(stylesheet.status_code, 200)
            self.assertEqual(script.status_code, 200)
            self.assertEqual(command_sequence.status_code, 200)
            self.assertEqual(console_output.status_code, 200)
            self.assertIn("TocConsoleOutput.create", script.text)
            self.assertIn("consoleOutput.write(message)", script.text)
            self.assertIn("#game-terminal .ansi-fg-red", stylesheet.text)
            self.assertNotIn("innerHTML", console_output.text)
            self.assertIn('type: "auth", token: state.token', script.text)
            self.assertIn('/api/auth/local', script.text)
            self.assertIn('data-operation="update"', page.text)
            self.assertIn('data-view="host"', page.text)
            self.assertIn("Read-only appliance telemetry", page.text)
            self.assertIn("Resource monitor", page.text)
            self.assertIn('/api/host/resources', script.text)
            self.assertIn("TocCommandSequence.parse(command)", script.text)
            self.assertIn("const MAX_COMMANDS = 50", command_sequence.text)
            self.assertIn('next === ";"', command_sequence.text)
            self.assertIn("quoteCanOpen", command_sequence.text)
            self.assertIn("commands, overflow", command_sequence.text)

            game_client = client.get("/client")
            self.assertEqual(game_client.status_code, 200)
            self.assertIn("Times of Chaos Client", game_client.text)
            self.assertIn('/static/client.css', game_client.text)
            self.assertIn('/static/client.js', game_client.text)
            self.assertIn('/static/command-sequence.js', game_client.text)
            self.assertNotIn("cdn.", game_client.text)
            self.assertNotIn("http://", game_client.text)
            self.assertNotIn("https://", game_client.text)
            self.assertIn("default-src 'self'", game_client.headers["Content-Security-Policy"])

            client_stylesheet = client.get("/static/client.css")
            client_script = client.get("/static/client.js")
            self.assertEqual(client_stylesheet.status_code, 200)
            self.assertEqual(client_script.status_code, 200)
            self.assertIn('new WebSocket(`${protocol}//${location.host}/ws`)', client_script.text)
            self.assertIn('type: "auth", token: state.token', client_script.text)
            self.assertIn('/ws/events', client_script.text)
            self.assertIn('Server activity', game_client.text)
            self.assertIn('/api/auth/local', client_script.text)
            self.assertIn(r"/\r\n|\n\r/g", client_script.text)
            self.assertIn('if (typeof command !== "string") return false;', client_script.text)
            self.assertIn("sendCommandSequence(input.value)", client_script.text)
            self.assertIn('state.secretInput || !command.includes(";")', client_script.text)
            self.assertIn("TocCommandSequence.parse(command)", client_script.text)
            self.assertNotIn("if (!command) return false;", client_script.text)
            self.assertNotIn("if (!command || !state.terminal.socket", script.text)
            self.assertIn('addEventListener("click", focusCommandFromTerminal)', client_script.text)
            self.assertIn('addEventListener("click", focusConsoleFromTerminal)', script.text)
            self.assertIn("selection && !selection.isCollapsed", client_script.text)
            self.assertIn("selection && !selection.isCollapsed", script.text)
            self.assertNotIn("innerHTML", client_script.text)
            self.assertIn('maxlength="8191"', game_client.text)

            config = client.get("/api/config")
            self.assertEqual(config.status_code, 200)
            self.assertTrue(config.json()["admin_token_configured"])
            self.assertFalse(config.json()["local_admin_unlock"])
            self.assertEqual(config.json()["client_path"], "/client")
            self.assertEqual(config.json()["game_websocket_auth"], "same-origin")
            self.assertEqual(config.json()["log_websocket_auth"], "cookie-or-first-message")
            self.assertEqual(config.json()["event_websocket_auth"], "cookie-or-first-message")
            self.assertFalse(config.json()["update_available"])
            self.assertFalse(config.json()["host_status_available"])

            health = client.get("/api/health")
            self.assertEqual(health.status_code, 200)
            self.assertTrue(health.json()["webadmin"])

            summary = client.get("/api/area_health?include_issues=false")
            self.assertEqual(summary.status_code, 200)
            self.assertNotIn("issues", summary.json())
            self.assertEqual(summary.json()["summary"]["by_severity"]["critical"], 0)

            mobs = client.get("/api/mobs", params={"limit": 2, "offset": 1})
            self.assertEqual(mobs.status_code, 200)
            self.assertEqual(len(mobs.json()), 2)
            self.assertGreater(int(mobs.headers["X-Total-Count"]), 2)

            first_mob = mobs.json()[0]
            search = client.get("/api/mobs", params={"q": first_mob["vnum"], "limit": 25})
            self.assertTrue(any(item["vnum"] == first_mob["vnum"] for item in search.json()))

            objects = client.get("/api/objects", params={"limit": 1, "offset": 1})
            rooms = client.get("/api/rooms", params={"limit": 1, "offset": 1})
            self.assertEqual(len(objects.json()), 1)
            self.assertEqual(len(rooms.json()), 1)
            self.assertGreater(int(objects.headers["X-Total-Count"]), 1)
            self.assertGreater(int(rooms.headers["X-Total-Count"]), 1)

            bad_gear_level = client.get(
                "/api/best_gear",
                params={"class_name": "warrior", "race_name": "human", "level": 71},
            )
            self.assertEqual(bad_gear_level.status_code, 400)

            self.assertEqual(
                server.telnet_negotiation_responses(bytes([255, 251, 1, 255, 253, 31])),
                bytes([255, 253, 1, 255, 252, 31]),
            )

            with patch.object(server.asyncio, "open_connection", side_effect=ConnectionRefusedError):
                with client.websocket_connect("/ws") as websocket:
                    self.assertEqual(
                        websocket.receive_text(),
                        "\0TOC_ERROR:Game server is unavailable.",
                    )

            with self.assertRaises(WebSocketDisconnect) as rejected_origin:
                with client.websocket_connect(
                    "/ws",
                    headers={"origin": "https://untrusted.example"},
                ) as websocket:
                    websocket.receive_text()
            self.assertEqual(rejected_origin.exception.code, 1008)

            with self.assertRaises(WebSocketDisconnect) as rejected_log_origin:
                with client.websocket_connect(
                    "/ws/logs",
                    headers={"origin": "https://untrusted.example"},
                ) as websocket:
                    websocket.receive_text()
            self.assertEqual(rejected_log_origin.exception.code, 1008)

            with self.assertRaises(WebSocketDisconnect) as rejected_event_origin:
                with client.websocket_connect(
                    "/ws/events",
                    headers={"origin": "https://untrusted.example"},
                ) as websocket:
                    websocket.receive_json()
            self.assertEqual(rejected_event_origin.exception.code, 1008)

            comm_source = (Path(__file__).resolve().parents[1] / "src" / "comm.c").read_text(encoding="latin-1")
            stubs_source = (Path(__file__).resolve().parents[1] / "src" / "stubs.c").read_text(encoding="latin-1")
            self.assertIn('write_web_admin_event( "wizinfo", info, level )', comm_source)
            self.assertIn('write_web_admin_event( "info", argument, 0 )', stubs_source)

            self.assertEqual(server.MAX_GAME_FRAME_BYTES, 8192)

            self.assertGreater(len(server.parser.rooms), 7000)

    def test_player_privacy_case_preservation_and_log_auth(self) -> None:
        with self.webadmin_client() as (server, client, temp_root):
            event_path = temp_root / "webadmin-events.tsv"
            self.assertEqual(client.get("/api/players").status_code, 403)
            self.assertEqual(client.get("/api/player/MiXeD").status_code, 403)
            self.assertEqual(client.get("/api/auth/check").status_code, 403)
            self.assertEqual(client.get("/api/events").status_code, 403)
            self.assertEqual(client.get("/api/admin/status").status_code, 403)
            self.assertEqual(client.get("/api/host/status").status_code, 403)
            self.assertEqual(client.get("/api/host/resources").status_code, 403)

            headers = {"X-Admin-Token": "secret"}
            auth = client.get("/api/auth/check", headers=headers)
            self.assertEqual(auth.status_code, 200)
            self.assertTrue(auth.json()["authenticated"])

            players = client.get("/api/players", headers=headers)
            self.assertEqual(players.json(), ["MiXeD"])

            # Case-insensitive lookup must preserve the actual save filename and
            # must not use str.capitalize(), which broke mixed-case filenames.
            player = client.get("/api/player/mixed", headers=headers)
            self.assertEqual(player.status_code, 200)
            self.assertEqual(player.json()["name"], "MiXeD")
            self.assertEqual(player.json()["equipment"][0]["wear_slot"], "Head")
            self.assertEqual(client.get("/api/player/bad.name", headers=headers).status_code, 400)

            logs = client.get("/api/logs", params={"lines": 2}, headers=headers)
            self.assertEqual(logs.status_code, 200)
            self.assertEqual(logs.text.splitlines(), ["second line", "third line"])

            events = client.get("/api/events", params={"limit": 10}, headers=headers)
            self.assertEqual(events.status_code, 200)
            self.assertEqual([event["channel"] for event in events.json()], ["info", "wizinfo"])
            self.assertIsNone(events.json()[0]["level"])
            self.assertEqual(events.json()[1]["level"], 62)
            self.assertEqual(client.get("/api/events", params={"limit": 0}, headers=headers).status_code, 422)

            self.assertIsNone(server.parse_server_event_line("not-an-event"))
            self.assertIsNone(server.parse_server_event_line("1787680002\tprivate\t70\tHidden"))
            self.assertIsNone(server.parse_server_event_line("1787680002\twizinfo\t71\tToo high"))

            with client.websocket_connect("/ws/events") as websocket:
                websocket.send_json({"type": "auth", "token": "secret"})
                snapshot = websocket.receive_json()
                self.assertEqual(snapshot["type"], "snapshot")
                self.assertEqual(len(snapshot["events"]), 2)
                with event_path.open("a", encoding="utf-8") as event_file:
                    event_file.write("1787680002\twizinfo\t70\tLive event.\n")
                live_update = websocket.receive_json()
                self.assertEqual(live_update["type"], "events")
                self.assertEqual(live_update["events"][0]["message"], "Live event.")
                websocket.send_json({"type": "close"})
                with self.assertRaises(WebSocketDisconnect):
                    websocket.receive_json()

            with client.websocket_connect("/ws/logs") as websocket:
                websocket.send_json({"type": "auth", "token": "secret"})
                self.assertIn("third line", websocket.receive_text())
                websocket.send_json({"type": "close"})
                with self.assertRaises(WebSocketDisconnect) as closed:
                    websocket.receive_text()
            self.assertEqual(closed.exception.code, 1000)

            with self.assertRaises(WebSocketDisconnect) as rejected:
                with client.websocket_connect("/ws/logs") as websocket:
                    websocket.send_json({"type": "auth", "token": "wrong"})
                    websocket.receive_text()
            self.assertEqual(rejected.exception.code, 4003)

    def test_admin_status_reports_operations_without_exposing_queue_payloads(self) -> None:
        with self.webadmin_client() as (_, client, temp_root):
            headers = {"X-Admin-Token": "secret"}
            queue_path = temp_root / "webadmin.queue"
            queue_path.write_text("backup\n\ncommand|look\n", encoding="utf-8")
            backup_path = temp_root / "backups" / "toc-test.tar.gz"
            backup_path.write_bytes(b"backup data")

            response = client.get("/api/admin/status", headers=headers)
            self.assertEqual(response.status_code, 200)
            status = response.json()

            self.assertTrue(status["runtime"]["webadmin"])
            self.assertEqual(status["queue"]["pending_actions"], 2)
            self.assertFalse(status["queue"]["truncated"])
            self.assertTrue(status["queue"]["readable"])
            self.assertNotIn("command|look", response.text)
            self.assertEqual(status["backups"]["count"], 1)
            self.assertEqual(status["backups"]["latest"]["name"], "toc-test.tar.gz")
            self.assertEqual(status["players"]["count"], 1)
            self.assertEqual(status["players"]["recent"][0]["name"], "MiXeD")
            self.assertTrue(status["activity"]["log"]["exists"])
            self.assertTrue(status["activity"]["events"]["exists"])

    def test_host_status_is_opt_in_authenticated_and_read_only(self) -> None:
        headers = {"X-Admin-Token": "secret"}
        with self.webadmin_client() as (_, client, _):
            self.assertEqual(client.get("/api/host/status", headers=headers).status_code, 503)
            self.assertEqual(client.get("/api/host/resources", headers=headers).status_code, 503)

        payload = {
            "generated": 1788000000,
            "read_only": True,
            "host": {
                "hostname": "toc",
                "boot_id": "123456789abc",
                "uptime_seconds": 3600,
                "cpu_count": 4,
                "load_average": [0.1, 0.2, 0.3],
                "temperature_c": 40.5,
                "cpu_percent": 12.5,
                "memory": {"total_bytes": 1024, "available_bytes": 512, "used_bytes": 512},
                "swap": {"total_bytes": 1024, "free_bytes": 768, "used_bytes": 256},
                "root_filesystem": {"total_bytes": 4096, "used_bytes": 1024, "free_bytes": 3072},
                "network": {"receive_bytes_per_second": 200, "transmit_bytes_per_second": 100},
            },
            "repository": {
                "head": "abc123",
                "known_origin_main": "abc123",
                "deployed": "abc123",
                "tracked_changes": 0,
                "ahead": 0,
                "behind": 0,
                "matches_known_origin": True,
            },
            "services": [{
                "unit": "toc2026-game.service", "description": "Times of Chaos",
                "load_state": "loaded", "active_state": "active", "sub_state": "running",
                "result": "success", "pid": 123, "restarts": 1,
                "since": "Tue 2026-09-15 12:00:00 EDT", "exit_status": "0",
            }],
            "timers": [],
            "boots": [{"index": "0", "boot_id": "123456789abc", "range": "Tue 2026-09-15 - Tue 2026-09-15"}],
            "journal": [{
                "timestamp": 1788000000, "source": "toc2026-update.service",
                "priority": "6", "message": "ToC update complete.", "boot_id": "123456789abc",
            }],
            "errors": [],
        }
        with self.webadmin_client(host_status=True) as (server, client, _):
            self.assertTrue(client.get("/api/config").json()["host_status_available"])
            self.assertEqual(client.get("/api/host/status").status_code, 403)
            self.assertEqual(client.get("/api/host/resources").status_code, 403)
            self.assertIn("toc2026-healthcheck.service", server.HOST_SERVICE_UNITS)
            self.assertIn("toc2026-maintenance.service", server.HOST_SERVICE_UNITS)
            self.assertIn("toc2026-healthcheck.timer", server.HOST_TIMER_UNITS)
            self.assertIn("toc2026-maintenance.timer", server.HOST_TIMER_UNITS)
            self.assertIsNone(server.run_host_command(("sh", "-c", "id")))
            self.assertEqual(
                server.parse_cpu_counters("cpu 10 2 3 80 5 0 0 0\ncpu0 1 1 1 1"),
                (100, 85),
            )
            self.assertEqual(
                server.parse_network_counters(
                    "lo: 100 0 0 0 0 0 0 0 100 0 0 0 0 0 0 0\n"
                    "eth0: 200 0 0 0 0 0 0 0 300 0 0 0 0 0 0 0\n"
                ),
                (200, 300),
            )
            shutdown_entries = server.parse_journal_output(
                '{"_SYSTEMD_UNIT":"init.scope","SYSLOG_IDENTIFIER":"systemd-shutdown",'
                '"MESSAGE":"Syncing filesystems.","__REALTIME_TIMESTAMP":"1788000000000000"}',
                "systemd-shutdown",
            )
            self.assertEqual(shutdown_entries[0]["source"], "systemd-shutdown")
            with patch.object(server, "host_status_snapshot", return_value=payload):
                response = client.get("/api/host/status", headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["read_only"])
            self.assertEqual(response.json()["services"][0]["unit"], "toc2026-game.service")
            self.assertNotIn("command", response.json())
            resource_payload = {
                "generated": payload["generated"],
                "read_only": True,
                "host": payload["host"],
            }
            with patch.object(server, "host_resource_snapshot", return_value=resource_payload):
                resources = client.get("/api/host/resources", headers=headers)
            self.assertEqual(resources.status_code, 200)
            self.assertEqual(resources.json()["host"]["cpu_percent"], 12.5)
            self.assertNotIn("journal", resources.json())

    def test_loopback_client_can_open_and_close_a_local_admin_session(self) -> None:
        with self.webadmin_client(local_unlock=True) as (_, client, _):
            config = client.get("/api/config")
            self.assertTrue(config.json()["local_admin_unlock"])
            self.assertEqual(client.get("/api/auth/check").status_code, 403)

            unlocked = client.post("/api/auth/local")
            self.assertEqual(unlocked.status_code, 200)
            self.assertEqual(unlocked.json()["mode"], "local")
            cookie = unlocked.headers["set-cookie"].lower()
            self.assertIn("httponly", cookie)
            self.assertIn("samesite=strict", cookie)

            self.assertEqual(client.get("/api/auth/check").status_code, 200)
            self.assertEqual(client.get("/api/players").json(), ["MiXeD"])

            session_cookie = client.cookies.get("toc_admin_session")
            with client.websocket_connect(
                "ws://127.0.0.1:9001/ws/logs",
                headers={"cookie": f"toc_admin_session={session_cookie}"},
            ) as websocket:
                self.assertIn("third line", websocket.receive_text())
                websocket.send_json({"type": "close"})
                with self.assertRaises(WebSocketDisconnect):
                    websocket.receive_text()

            with client.websocket_connect(
                "ws://127.0.0.1:9001/ws/events",
                headers={"cookie": f"toc_admin_session={session_cookie}"},
            ) as websocket:
                self.assertEqual(websocket.receive_json()["type"], "snapshot")
                websocket.send_json({"type": "close"})
                with self.assertRaises(WebSocketDisconnect):
                    websocket.receive_json()

            self.assertEqual(client.post("/api/auth/logout").status_code, 200)
            self.assertEqual(client.get("/api/auth/check").status_code, 403)

        with self.webadmin_client(local_unlock=True, web_bind="0.0.0.0") as (_, client, _):
            self.assertFalse(client.get("/api/config").json()["local_admin_unlock"])
            self.assertEqual(client.post("/api/auth/local").status_code, 403)

    def test_login_history_pairs_sessions_and_reports_playtime(self) -> None:
        """The journal is two half-records per session; the API joins them.

        The game writes a row when a session starts and another when it ends,
        so a duration only exists once both have been seen. The awkward cases
        are the ones that actually happen: a session still open, and an end
        whose start has already been trimmed off the front of the file.
        """
        with self.webadmin_client() as (server, client, temp_root):
            journal = temp_root / "logins.tsv"
            journal.write_text(
                "\n".join([
                    # a complete session, ended by quit
                    "1700000000\tMixed\t10.0.0.5\tconnect",
                    "1700003600\tMixed\t10.0.0.5\tquit\t3600",
                    # a complete session, ended by a dropped link
                    "1700010000\tOther\t10.0.0.9\tnew",
                    "1700010090\tOther\t10.0.0.9\tlinkdead\t90",
                    # still connected: no end row yet
                    "1700020000\tThird\t10.0.0.7\treconnect",
                    # an end with no start, as after a journal trim
                    "1700030000\tOrphan\t10.0.0.3\tquit\t120",
                    # junk the game could leave behind on a crash mid-write
                    "not-a-timestamp\tBad\thost\tconnect",
                    "1700040000\ttruncated",
                ]) + "\n",
                encoding="latin-1",
            )

            with patch.object(server, "LOGIN_JOURNAL", journal):
                denied = client.get("/api/logins")
                self.assertEqual(denied.status_code, 403, "IPs must stay behind the token")

                payload = client.get(
                    "/api/logins", headers={"X-Admin-Token": "secret"}
                ).json()

            self.assertTrue(payload["journal_present"])
            sessions = {s["name"]: s for s in payload["sessions"]}

            self.assertEqual(sessions["Mixed"]["duration"], 3600)
            self.assertEqual(sessions["Mixed"]["ended"], "quit")
            self.assertEqual(sessions["Mixed"]["host"], "10.0.0.5")

            self.assertEqual(sessions["Other"]["duration"], 90)
            self.assertEqual(sessions["Other"]["ended"], "linkdead")

            # Open session: reported, but with no invented duration.
            self.assertIsNone(sessions["Third"]["duration"])
            self.assertIsNone(sessions["Third"]["ended"])
            self.assertEqual(sessions["Third"]["login"], 1700020000)

            # Orphaned end: the playtime is kept even though the start is gone.
            self.assertEqual(sessions["Orphan"]["duration"], 120)
            self.assertIsNone(sessions["Orphan"]["login"])

            # Malformed rows are skipped, not fatal.
            self.assertNotIn("Bad", sessions)
            self.assertEqual(len(payload["sessions"]), 4)

            # Newest first.
            stamps = [s["logout"] or s["login"] for s in payload["sessions"]]
            self.assertEqual(stamps, sorted(stamps, reverse=True))

            # Lifetime totals come from the save file, not the journal.
            saved = payload["players"]["MiXeD"]
            self.assertEqual(saved["played"], 7200)
            self.assertEqual(saved["last_session"], 1800)
            self.assertEqual(saved["last_login"], 1700046400)
            # The character's level, not the level of an object it carries.
            self.assertEqual(saved["level"], 12)

    def test_login_history_is_empty_not_broken_before_any_login(self) -> None:
        """A server that has not been logged into yet still renders."""
        with self.webadmin_client() as (server, client, temp_root):
            missing = temp_root / "no-such-logins.tsv"
            with patch.object(server, "LOGIN_JOURNAL", missing):
                payload = client.get(
                    "/api/logins", headers={"X-Admin-Token": "secret"}
                ).json()
            self.assertFalse(payload["journal_present"])
            self.assertEqual(payload["sessions"], [])

    def test_admin_only_interface_is_marked_and_hidden_until_unlocked(self) -> None:
        """The dashboard is on a public port, so the locked view has to be tidy.

        Every section whose data comes only from a token-protected route is
        marked `data-admin`, the stylesheet hides those until the body carries
        `admin-unlocked`, and the script sets that class from the auth state
        alone. A view added later without the marker shows up as a panel of
        "Locked" rows to anyone who opens the page.
        """
        static = Path(__file__).resolve().parents[1] / "webadmin" / "static"
        markup = (static / "index.html").read_text(encoding="utf-8")
        styles = (static / "app.css").read_text(encoding="utf-8")
        script = (static / "app.js").read_text(encoding="utf-8")

        for view in ("players", "console", "logs", "host", "operations"):
            self.assertIn(
                f'<button class="nav-item" type="button" data-admin data-view="{view}">',
                markup,
                f"{view} nav item is not marked admin-only",
            )
            self.assertIn(
                f'<section class="view" data-admin id="{view}-view"',
                markup,
                f"{view} view is not marked admin-only",
            )

        self.assertIn("body:not(.admin-unlocked) [data-admin]", styles)
        self.assertIn('classList.toggle("admin-unlocked", state.authenticated)', script)

        # And the locked page must not be reachable into an admin view by hash.
        self.assertIn(
            'if (ADMIN_VIEWS.has(view) && !state.authenticated) view = "overview";',
            script,
        )

    def test_local_unlock_ignores_a_spoofed_loopback_host_header(self) -> None:
        """The unlock must read the connection, not the request.

        It used to gate on the Host header, which the caller writes: a request
        from anywhere carrying `Host: 127.0.0.1` was handed an admin session
        cookie, and that cookie opens every protected endpoint. The peer
        address is the one part of a request a remote caller cannot choose.
        """
        remote = ("203.0.113.9", 51000)
        with self.webadmin_client(local_unlock=True, peer=remote) as (server, client, _):
            self.assertFalse(
                client.get("/api/config", headers={"host": "127.0.0.1"}).json()[
                    "local_admin_unlock"
                ]
            )
            denied = client.post("/api/auth/local", headers={"host": "127.0.0.1"})
            self.assertEqual(denied.status_code, 403)
            self.assertIsNone(denied.cookies.get(server.LOCAL_ADMIN_COOKIE))

            # Nor by presenting the cookie the loopback path would have set.
            client.cookies.set(
                server.LOCAL_ADMIN_COOKIE, server.local_admin_session_value()
            )
            self.assertEqual(
                client.get("/api/auth/check", headers={"host": "127.0.0.1"}).status_code,
                403,
            )

    def test_local_unlock_is_off_whenever_the_bound_address_is_not_loopback(self) -> None:
        """The gate reads the address that was actually bound.

        It used to read WEB_ADMIN_BIND while uvicorn bound whatever --host
        said, and the production unit passes --host 0.0.0.0 with no such
        variable set, so the gate believed it was loopback-bound.
        """
        with self.webadmin_client(local_unlock=True) as (server, client, _):
            self.assertTrue(server.local_admin_unlock_enabled())
            self.assertEqual(client.post("/api/auth/local").status_code, 200)

            server.set_bind_address("0.0.0.0")
            self.assertFalse(server.local_admin_unlock_enabled())
            self.assertEqual(client.post("/api/auth/local").status_code, 403)
            self.assertEqual(client.get("/api/auth/check").status_code, 403)

    def test_commands_reload_and_queue_validation(self) -> None:
        with self.webadmin_client() as (server, client, temp_root):
            queue_path = temp_root / "webadmin.queue"
            headers = {"X-Admin-Token": "secret"}

            accepted = client.post(
                "/api/command",
                json={"command": "look"},
                headers=headers,
            )
            self.assertEqual(accepted.status_code, 200)
            self.assertIn("command|look", queue_path.read_text(encoding="utf-8"))

            original_queue = queue_path.read_text(encoding="utf-8")
            for invalid_command in ("look\nshutdown", "look|shutdown", "x" * 256):
                rejected = client.post(
                    "/api/command",
                    json={"command": invalid_command},
                    headers=headers,
                )
                self.assertEqual(rejected.status_code, 400)
            self.assertEqual(queue_path.read_text(encoding="utf-8"), original_queue)

            bad_level = client.post(
                "/api/wizinfo",
                json={"message": "Test", "level": 71},
                headers=headers,
            )
            self.assertEqual(bad_level.status_code, 400)

            backups = client.get("/api/backups", headers=headers)
            self.assertEqual(backups.status_code, 200)
            self.assertEqual(backups.json(), [])

            with patch.object(server, "_WEB_ADMIN_TOKEN", ""):
                disabled = client.post("/api/backup", headers=headers)
            self.assertEqual(disabled.status_code, 503)

            self.assertEqual(client.post("/api/update", headers=headers).status_code, 503)
            update_request = temp_root / "update.request"
            with patch.object(server, "UPDATE_REQUEST_PATH", update_request):
                self.assertEqual(client.post("/api/update").status_code, 403)
                accepted_update = client.post("/api/update", headers=headers)
            self.assertEqual(accepted_update.status_code, 200)
            self.assertEqual(accepted_update.json(), {"status": "queued"})
            self.assertTrue(update_request.is_file())

            original_parser = server.parser
            original_health = server.AREA_HEALTH_CACHE
            broken_parser = SimpleNamespace(
                areas={}, mobiles={}, objects={}, rooms={}, resets={},
                errors=[{"file": "broken.are", "error": "bad data"}],
                parse_all=Mock(),
            )
            critical_health = {
                "summary": {
                    "areas": 0, "mobiles": 0, "objects": 0, "rooms": 0,
                    "listed_area_files": 1, "parse_errors": 1, "issues": 1,
                    "by_severity": {"critical": 1, "warning": 0, "info": 0},
                },
                "issues": [{
                    "severity": "critical", "code": "area-parse-error",
                    "message": "broken.are failed to parse",
                }],
            }
            with (
                patch.object(server, "AreaParser", return_value=broken_parser),
                patch.object(server, "build_area_health", return_value=critical_health),
            ):
                rejected_reload = client.post("/api/reload", headers=headers)
            self.assertEqual(rejected_reload.status_code, 422)
            self.assertIs(server.parser, original_parser)

            healthy_parser = SimpleNamespace(
                areas={"test.are": object()}, mobiles={1: object()},
                objects={2: object()}, rooms={3: object()}, resets={"test.are": []},
                errors=[], parse_all=Mock(),
            )
            healthy_health = {
                "summary": {
                    "areas": 1, "mobiles": 1, "objects": 1, "rooms": 1,
                    "listed_area_files": 1, "parse_errors": 0, "issues": 0,
                    "by_severity": {"critical": 0, "warning": 0, "info": 0},
                },
                "issues": [],
            }
            try:
                with (
                    patch.object(server, "AreaParser", return_value=healthy_parser),
                    patch.object(server, "build_area_health", return_value=healthy_health),
                ):
                    accepted_reload = client.post("/api/reload", headers=headers)
                self.assertEqual(accepted_reload.status_code, 200)
                self.assertIs(server.parser, healthy_parser)
                self.assertIs(server.AREA_HEALTH_CACHE, healthy_health)
                self.assertEqual(accepted_reload.json()["rooms"], 1)
            finally:
                server.parser = original_parser
                server.AREA_HEALTH_CACHE = original_health

            nested_queue = temp_root / "nested" / "admin.queue"
            writer = server.QueueWriter(nested_queue)
            writer.append("backup")
            self.assertEqual(nested_queue.read_text(encoding="utf-8"), "backup\n")
            with self.assertRaises(ValueError):
                writer.append("backup\nshutdown")


if __name__ == "__main__":
    unittest.main()

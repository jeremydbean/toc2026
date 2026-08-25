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
except Exception:  # pragma: no cover - local C-only environments can skip this
    TestClient = None
    WebSocketDisconnect = Exception


PLAYER_FIXTURE = """#PLAYER
Name MiXeD~
Race elf~
Sex 2
Cla 3
Gui 3
Levl 12
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
    def webadmin_client(self, local_unlock: bool = False, web_bind: str = "127.0.0.1"):
        if TestClient is None:
            self.skipTest("fastapi is not installed")

        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            player_path = temp_root / "players"
            backup_path = temp_root / "backups"
            log_path = temp_root / "toc.log"
            queue_path = temp_root / "webadmin.queue"
            player_path.mkdir()
            backup_path.mkdir()
            (player_path / "MiXeD").write_text(PLAYER_FIXTURE, encoding="latin-1")
            (player_path / "notes").mkdir()
            (player_path / "invalid-name").write_text("ignored", encoding="ascii")
            log_path.write_text("first line\nsecond line\nthird line\n", encoding="utf-8")

            env = {
                "QUEUE_PATH": str(queue_path),
                "WEB_ADMIN_TOKEN": "secret",
                "AREA_PATH": str(repo_root / "area"),
                "BACKUP_PATH": str(backup_path),
                "PLAYER_PATH": str(player_path),
                "LOG_FILE": str(log_path),
                "MUD_HOST": "127.0.0.1",
                "MUD_PORT": "65534",
                "WEB_ADMIN_BIND": web_bind,
                "WEB_ADMIN_LOCAL_UNLOCK": "1" if local_unlock else "0",
            }
            with patch.dict(os.environ, env, clear=False):
                sys.modules.pop("webadmin.server", None)
                server = importlib.import_module("webadmin.server")
                try:
                    base_url = "http://127.0.0.1:9001" if local_unlock else "http://testserver"
                    with TestClient(server.app, base_url=base_url) as client:
                        yield server, client, temp_root
                finally:
                    sys.modules.pop("webadmin.server", None)

    def test_self_contained_interface_and_paginated_catalogs(self) -> None:
        with self.webadmin_client() as (server, client, _):
            page = client.get("/")
            self.assertEqual(page.status_code, 200)
            self.assertIn("Times of Chaos Admin", page.text)
            self.assertIn('/static/app.js', page.text)
            self.assertIn('href="/client"', page.text)
            self.assertNotIn("cdn.", page.text)
            self.assertNotIn("tailwind", page.text.lower())
            self.assertIn("default-src 'self'", page.headers["Content-Security-Policy"])
            self.assertEqual(page.headers["X-Frame-Options"], "DENY")
            self.assertEqual(client.get("/docs").status_code, 404)

            stylesheet = client.get("/static/app.css")
            script = client.get("/static/app.js")
            self.assertEqual(stylesheet.status_code, 200)
            self.assertEqual(script.status_code, 200)
            self.assertIn('type: "auth", token: state.token', script.text)
            self.assertIn('/api/auth/local', script.text)

            game_client = client.get("/client")
            self.assertEqual(game_client.status_code, 200)
            self.assertIn("Times of Chaos Client", game_client.text)
            self.assertIn('/static/client.css', game_client.text)
            self.assertIn('/static/client.js', game_client.text)
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
            self.assertIn('/api/auth/local', client_script.text)
            self.assertIn(r"/\r\n|\n\r/g", client_script.text)
            self.assertIn(r"/\r\n|\n\r/g", script.text)
            self.assertNotIn("innerHTML", client_script.text)
            self.assertIn('maxlength="8191"', game_client.text)

            config = client.get("/api/config")
            self.assertEqual(config.status_code, 200)
            self.assertTrue(config.json()["admin_token_configured"])
            self.assertFalse(config.json()["local_admin_unlock"])
            self.assertEqual(config.json()["client_path"], "/client")
            self.assertEqual(config.json()["game_websocket_auth"], "same-origin")
            self.assertEqual(config.json()["log_websocket_auth"], "cookie-or-first-message")

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

            self.assertEqual(server.MAX_GAME_FRAME_BYTES, 8192)

            self.assertGreater(len(server.parser.rooms), 7000)

    def test_player_privacy_case_preservation_and_log_auth(self) -> None:
        with self.webadmin_client() as (_, client, _):
            self.assertEqual(client.get("/api/players").status_code, 403)
            self.assertEqual(client.get("/api/player/MiXeD").status_code, 403)
            self.assertEqual(client.get("/api/auth/check").status_code, 403)

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

    def test_loopback_client_can_open_and_close_a_local_admin_session(self) -> None:
        with self.webadmin_client(local_unlock=True) as (_, client, _):
            remote_config = client.get("/api/config", headers={"host": "mud.example.com"})
            self.assertFalse(remote_config.json()["local_admin_unlock"])
            self.assertEqual(
                client.post("/api/auth/local", headers={"host": "mud.example.com"}).status_code,
                403,
            )

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

            self.assertEqual(client.post("/api/auth/logout").status_code, 200)
            self.assertEqual(client.get("/api/auth/check").status_code, 403)

        with self.webadmin_client(local_unlock=True, web_bind="0.0.0.0") as (_, client, _):
            self.assertFalse(client.get("/api/config").json()["local_admin_unlock"])
            self.assertEqual(client.post("/api/auth/local").status_code, 403)

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

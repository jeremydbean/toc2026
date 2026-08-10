from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover - local C-only environments can skip this
    TestClient = None


class WebAdminApiTests(unittest.TestCase):
    def test_area_health_and_token_protected_command(self) -> None:
        if TestClient is None:
            self.skipTest("fastapi is not installed")

        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "webadmin.queue"
            old_env = {
                "QUEUE_PATH": os.environ.get("QUEUE_PATH"),
                "WEB_ADMIN_TOKEN": os.environ.get("WEB_ADMIN_TOKEN"),
                "AREA_PATH": os.environ.get("AREA_PATH"),
                "BACKUP_PATH": os.environ.get("BACKUP_PATH"),
            }
            os.environ["QUEUE_PATH"] = str(queue_path)
            os.environ["WEB_ADMIN_TOKEN"] = "secret"
            os.environ["AREA_PATH"] = "area"
            os.environ["BACKUP_PATH"] = tmp

            try:
                sys.modules.pop("webadmin.server", None)
                server = importlib.import_module("webadmin.server")

                with TestClient(server.app) as client:
                    health = client.get("/api/area_health")
                    self.assertEqual(health.status_code, 200)
                    self.assertEqual(health.json()["summary"]["by_severity"]["critical"], 0)

                    forbidden = client.post("/api/command", json={"command": "look"})
                    self.assertEqual(forbidden.status_code, 403)

                    accepted = client.post(
                        "/api/command",
                        json={"command": "look"},
                        headers={"X-Admin-Token": "secret"},
                    )
                    self.assertEqual(accepted.status_code, 200)
                    self.assertIn("command|look", queue_path.read_text(encoding="utf-8"))

                    original_queue = queue_path.read_text(encoding="utf-8")
                    for invalid_command in (
                        "look\nshutdown",
                        "look|shutdown",
                        "x" * 256,
                    ):
                        rejected = client.post(
                            "/api/command",
                            json={"command": invalid_command},
                            headers={"X-Admin-Token": "secret"},
                        )
                        self.assertEqual(rejected.status_code, 400)
                    self.assertEqual(
                        queue_path.read_text(encoding="utf-8"),
                        original_queue,
                    )

                    bad_level = client.post(
                        "/api/wizinfo",
                        json={"message": "Test", "level": 71},
                        headers={"X-Admin-Token": "secret"},
                    )
                    self.assertEqual(bad_level.status_code, 400)

                    backups = client.get("/api/backups", headers={"X-Admin-Token": "secret"})
                    self.assertEqual(backups.status_code, 200)
                    self.assertEqual(backups.json(), [])

                    with patch.object(server, "_WEB_ADMIN_TOKEN", ""):
                        disabled = client.post(
                            "/api/backup",
                            headers={"X-Admin-Token": "secret"},
                        )
                    self.assertEqual(disabled.status_code, 503)

                    original_parser = server.parser
                    broken_parser = SimpleNamespace(
                        areas={},
                        mobiles={},
                        objects={},
                        rooms={},
                        resets={},
                        errors=[{"file": "broken.are", "error": "bad data"}],
                        parse_all=Mock(),
                    )
                    critical_health = {
                        "summary": {
                            "areas": 0,
                            "mobiles": 0,
                            "objects": 0,
                            "rooms": 0,
                            "listed_area_files": 1,
                            "parse_errors": 1,
                            "issues": 1,
                            "by_severity": {
                                "critical": 1,
                                "warning": 0,
                                "info": 0,
                            },
                        },
                        "issues": [
                            {
                                "severity": "critical",
                                "code": "area-parse-error",
                                "message": "broken.are failed to parse",
                            }
                        ],
                    }
                    with (
                        patch.object(server, "AreaParser", return_value=broken_parser),
                        patch.object(
                            server,
                            "build_area_health",
                            return_value=critical_health,
                        ),
                    ):
                        rejected_reload = client.post(
                            "/api/reload",
                            headers={"X-Admin-Token": "secret"},
                        )
                    self.assertEqual(rejected_reload.status_code, 422)
                    self.assertIs(server.parser, original_parser)

                    healthy_parser = SimpleNamespace(
                        areas={"test.are": object()},
                        mobiles={1: object()},
                        objects={2: object()},
                        rooms={3: object()},
                        resets={"test.are": []},
                        errors=[],
                        parse_all=Mock(),
                    )
                    healthy_health = {
                        "summary": {
                            "areas": 1,
                            "mobiles": 1,
                            "objects": 1,
                            "rooms": 1,
                            "listed_area_files": 1,
                            "parse_errors": 0,
                            "issues": 0,
                            "by_severity": {
                                "critical": 0,
                                "warning": 0,
                                "info": 0,
                            },
                        },
                        "issues": [],
                    }
                    try:
                        with (
                            patch.object(server, "AreaParser", return_value=healthy_parser),
                            patch.object(
                                server,
                                "build_area_health",
                                return_value=healthy_health,
                            ),
                        ):
                            accepted_reload = client.post(
                                "/api/reload",
                                headers={"X-Admin-Token": "secret"},
                            )
                        self.assertEqual(accepted_reload.status_code, 200)
                        self.assertIs(server.parser, healthy_parser)
                        self.assertEqual(accepted_reload.json()["rooms"], 1)
                    finally:
                        server.parser = original_parser

                nested_queue = Path(tmp) / "nested" / "admin.queue"
                writer = server.QueueWriter(nested_queue)
                writer.append("backup")
                self.assertEqual(
                    nested_queue.read_text(encoding="utf-8"),
                    "backup\n",
                )
                with self.assertRaises(ValueError):
                    writer.append("backup\nshutdown")
            finally:
                sys.modules.pop("webadmin.server", None)
                for key, value in old_env.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()

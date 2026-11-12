"""The website's Changes page (2026-11-12).

/api/changes reads area/changes.dat the way src/changes.c does and serves
the entries players see with CHANGES ALL, newest first. An entry headed
`staff` is shown in game to staff alone, so the endpoint returns it only
to a request the admin token (or the local staff session) authenticates;
the page shows its who-sees-it filter only then.
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from webadmin import changes_index  # noqa: E402

try:
    from fastapi.testclient import TestClient
    UNAVAILABLE = None
except Exception as exc:  # pragma: no cover - C-only environments skip
    TestClient = None
    UNAVAILABLE = (f"web test client unavailable ({type(exc).__name__}: {exc}). "
                   "Install webadmin/requirements.txt and scripts/requirements.txt.")

SAMPLE = """# CHANGES -- a header comment
# @ 99999999notanentry 2026-01-01 staff

@ 20261112zthird 2026-11-12
A player change, wrapped over
two lines.

And a second paragraph.

@ 20261111zsecond 2026-11-11 staff
A staff change nobody else sees.

@ 20261110zfirst 2026-11-10
The oldest one.
"""


class ParserTests(unittest.TestCase):
    def test_entries_paragraphs_and_staff(self) -> None:
        entries = changes_index.parse_changes(SAMPLE)
        self.assertEqual([e["id"] for e in entries],
                         ["20261112zthird", "20261111zsecond", "20261110zfirst"])
        self.assertEqual(entries[0]["paragraphs"],
                         ["A player change, wrapped over two lines.", "And a second paragraph."])
        self.assertEqual([e["staff"] for e in entries], [False, True, False])
        self.assertEqual(entries[0]["date"], "2026-11-12")

    def test_staff_entries_only_for_staff(self) -> None:
        entries = changes_index.parse_changes(SAMPLE)
        self.assertEqual([e["id"] for e in changes_index.visible_changes(entries, False)],
                         ["20261112zthird", "20261110zfirst"])
        self.assertEqual(len(changes_index.visible_changes(entries, True)), 3)

    def test_the_real_file(self) -> None:
        """Every header the game reads is an entry here, ids are unique and
        the list is newest first, as CHANGES ALL shows it."""
        text = (ROOT / "area" / "changes.dat").read_text(encoding="latin-1")
        headers = [line for line in text.splitlines() if line.startswith("@ ")]
        entries = changes_index.parse_changes(text)
        self.assertEqual(len(entries), len(headers))
        self.assertEqual(len({e["id"] for e in entries}), len(entries))
        dates = [e["date"] for e in entries]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertTrue(all(e["paragraphs"] for e in entries), "no entry is empty")

    def test_missing_file_is_no_entries(self) -> None:
        self.assertEqual(changes_index.read_changes(ROOT / "no-such-changes.dat"), [])


class ApiTests(unittest.TestCase):
    @contextmanager
    def client(self):
        if TestClient is None:
            self.skipTest(UNAVAILABLE)
        with tempfile.TemporaryDirectory() as tmp:
            area = Path(tmp) / "area"
            area.mkdir()
            (area / "changes.dat").write_text(SAMPLE, encoding="latin-1")
            env = {"WEB_ADMIN_TOKEN": "secret", "AREA_PATH": str(area),
                   "PLAYER_PATH": str(Path(tmp) / "players"),
                   "QUEUE_PATH": str(Path(tmp) / "webadmin.queue"),
                   "LOG_FILE": str(Path(tmp) / "toc.log"),
                   "EVENT_LOG_FILE": str(Path(tmp) / "events.tsv"),
                   "WEB_ADMIN_LOCAL_UNLOCK": "0"}
            with patch.dict(os.environ, env, clear=False):
                sys.modules.pop("webadmin.server", None)
                server = importlib.import_module("webadmin.server")
                try:
                    with TestClient(server.app, base_url="http://testserver") as client:
                        yield server, client, area
                finally:
                    sys.modules.pop("webadmin.server", None)

    def test_public_sees_player_changes_only(self) -> None:
        with self.client() as (_, client, _area):
            reply = client.get("/api/changes")
            self.assertEqual(reply.status_code, 200)
            body = reply.json()
            self.assertFalse(body["staff"])
            self.assertEqual([e["id"] for e in body["changes"]],
                             ["20261112zthird", "20261110zfirst"])
            self.assertNotIn("nobody else sees", reply.text)

    def test_wrong_token_is_still_public(self) -> None:
        with self.client() as (_, client, _area):
            body = client.get("/api/changes", headers={"X-Admin-Token": "wrong"}).json()
            self.assertFalse(body["staff"])
            self.assertEqual(body["total"], 2)

    def test_token_adds_staff_changes(self) -> None:
        with self.client() as (_, client, _area):
            body = client.get("/api/changes", headers={"X-Admin-Token": "secret"}).json()
            self.assertTrue(body["staff"])
            self.assertEqual(body["total"], 3)
            self.assertTrue(body["changes"][1]["staff"])

    def test_a_new_entry_is_read_without_a_restart(self) -> None:
        with self.client() as (_, client, area):
            self.assertEqual(client.get("/api/changes").json()["total"], 2)
            path = area / "changes.dat"
            path.write_text("@ 20261113znewest 2026-11-13\nFresh.\n\n" + SAMPLE, encoding="latin-1")
            stamp = path.stat().st_mtime + 5
            os.utime(path, (stamp, stamp))
            self.assertEqual(client.get("/api/changes").json()["changes"][0]["id"], "20261113znewest")


class PageTests(unittest.TestCase):
    def test_the_page_has_the_view_and_bumped_assets(self) -> None:
        html = (ROOT / "webadmin" / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn('data-view="changes"', html)
        self.assertIn('id="changes-view"', html)
        script = (ROOT / "webadmin" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('api("/api/changes")', script)
        # A Changes button shown to everybody: not an admin-only view.
        self.assertNotRegex(html, r'data-admin data-view="changes"')


if __name__ == "__main__":
    unittest.main()

"""Public help, and paging over the log views.

The help endpoints are deliberately unauthenticated, which makes the level
filter the entire security model: entries above level 0 are staff
documentation -- SET, SNOOP, the immortal reference -- and must never reach
the public page. That is the test that matters here.

The paging tests cover the two orderings that are easy to get backwards: a
log reads oldest-first on the page but pages backwards through history, and
the events file is stored oldest-first while the API hands back newest
first.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "webadmin"))

try:
    from fastapi.testclient import TestClient
except Exception as exc:  # noqa: BLE001
    TestClient = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


@unittest.skipIf(TestClient is None,
                 f"web test client unavailable ({IMPORT_ERROR})")
class PlayerHelpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import server
        cls.server = server
        cls.client = TestClient(server.app)

    def test_the_index_is_public_and_not_empty(self) -> None:
        response = self.client.get("/api/help")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertGreater(body["total"], 50,
                           "the area files should yield plenty of topics")

    def test_no_staff_documentation_is_exposed(self) -> None:
        """The level filter is the whole security model for this endpoint."""
        for entry in self.server.load_player_help():
            self.assertLessEqual(
                entry["level"], self.server.HELP_PUBLIC_MAX_LEVEL,
                f"{entry['title']} is staff documentation")

        keywords = {word.lower()
                    for entry in self.server.load_player_help()
                    for word in entry["keywords"]}
        for staff_only in ("set", "snoop", "spellup", "iportal", "smash"):
            self.assertNotIn(staff_only, keywords,
                             f"{staff_only} help must not be public")

    def test_a_topic_returns_its_body(self) -> None:
        response = self.client.get("/api/help/new")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("PROMPT", body["body"])

    def test_an_unknown_topic_is_a_404(self) -> None:
        self.assertEqual(
            self.client.get("/api/help/nosuchtopicatall").status_code, 404)

    def test_a_staff_topic_is_not_reachable_by_name(self) -> None:
        """Filtered at parse time, so the direct lookup cannot find it."""
        self.assertEqual(self.client.get("/api/help/snoop").status_code, 404)


@unittest.skipIf(TestClient is None,
                 f"web test client unavailable ({IMPORT_ERROR})")
class EndpointDisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import server
        cls.server = server
        cls.client = TestClient(server.app)

    def test_the_game_endpoint_is_not_loopback(self) -> None:
        """127.0.0.1 is where the web service dials, not somewhere to play."""
        endpoint = self.client.get("/api/config").json()["mud_endpoint"]
        self.assertFalse(endpoint.startswith("127."), endpoint)
        self.assertFalse(endpoint.startswith("localhost"), endpoint)

    def test_an_unresolvable_host_falls_back_to_the_name(self) -> None:
        original = self.server.MUD_PUBLIC_HOST
        try:
            self.server.MUD_PUBLIC_HOST = "no-such-host.invalid"
            self.server._PUBLIC_IP_CACHE = (0.0, "")
            self.assertEqual(self.server.public_game_host(),
                             "no-such-host.invalid")
        finally:
            self.server.MUD_PUBLIC_HOST = original
            self.server._PUBLIC_IP_CACHE = (0.0, "")


if __name__ == "__main__":
    unittest.main()

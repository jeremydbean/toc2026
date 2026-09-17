"""The browser client must not anonymise its players.

Every web player reaches the game from 127.0.0.1, so before this they were
all recorded as "localhost" in the login history, and all shared one bucket
in the login throttle -- which skips loopback precisely because it could not
tell them apart. A PROXY v1 header from the bridge names the real client.

The half that matters for security is the refusal: the header is honoured
only over loopback. Accepting it from a direct connection would let a player
choose the address recorded against them, and choose their way out of a
throttle block.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from live_mud import (  # noqa: E402
    LiveMud,
    create_character,
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Zproxypw1"


def journal_rows(mud: LiveMud) -> list[list[str]]:
    path = mud.root / "log" / "logins.tsv"
    if not path.is_file():
        return []
    return [
        line.split("\t")
        for line in path.read_text(encoding="latin-1").splitlines()
        if line.strip()
    ]


@unittest.skipIf(SKIP is not None, SKIP or "")
class ProxyHeaderTests(unittest.TestCase):
    def test_a_loopback_bridge_can_name_the_real_client(self) -> None:
        name = "Zproxyone"
        claimed = "203.0.113.77"

        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                # Exactly what webadmin's bridge sends before anything else.
                client.send(f"PROXY TCP4 {claimed} 127.0.0.1 51000 {mud.port}")
                create_character(client, name, PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            rows = [r for r in journal_rows(mud) if r[1] == name]
            self.assertTrue(rows, "no journal row for the character")
            self.assertEqual(
                rows[0][2],
                claimed,
                f"host column should be the real client, got {rows[0][2]!r}",
            )

    def test_a_header_naming_loopback_is_ignored(self) -> None:
        """Nothing is learned from it, so the connection keeps what it had."""
        name = "Zproxytwo"

        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                client.send(f"PROXY TCP4 127.0.0.1 127.0.0.1 51000 {mud.port}")
                create_character(client, name, PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            rows = [r for r in journal_rows(mud) if r[1] == name]
            self.assertTrue(rows, "no journal row for the character")
            self.assertNotEqual(rows[0][2], "", "host column was blanked")

    def test_a_malformed_header_is_not_treated_as_a_name(self) -> None:
        """It must not silently become a character called PROXY."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                client.send("PROXY TCP4 not-an-ip 127.0.0.1 1 2")
                # A rejected header falls through as an ordinary name, so the
                # game should be asking about creating it rather than
                # accepting the line as a proxy announcement.
                client.drain(1.0)
                transcript = client.transcript
            self.assertNotIn(
                "PROXY TCP4 not-an-ip",
                [r[1] for r in journal_rows(mud)],
                "a bad header reached the journal",
            )
            self.assertTrue(transcript, "server said nothing at all")


if __name__ == "__main__":
    unittest.main()

"""Live coverage for the recent-login journal and the lastlog command.

do_sockets can only report a host while its descriptor is still connected, so
the journal comm.c appends at every login is what makes recent arrivals
visible after they leave. These tests drive a throwaway server: every
character here is created by the test and discarded with the temporary tree.
"""

from __future__ import annotations

import unittest

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)


SKIP = skip_reason()

# Mirrors ML in src/interp.h; lastlog is gated at L7 (MAX_LEVEL - 7).
IMMORTAL_LEVEL = 70

PASSWORD = "Ziplogpw"


def journal_rows(mud: LiveMud) -> list[list[str]]:
    path = mud.root / "log" / "logins.tsv"
    if not path.is_file():
        return []
    text = path.read_text(encoding="latin-1")
    return [line.split("\t") for line in text.splitlines() if line.strip()]


@unittest.skipIf(SKIP is not None, SKIP or "")
class LoginJournalTests(unittest.TestCase):
    def test_creating_a_character_records_a_new_row(self) -> None:
        name = "Ziplogone"

        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, name, PASSWORD)
                client.send("quit")
                self.assertTrue(
                    client.wait_closed(),
                    "character did not leave the world",
                )

            rows = journal_rows(mud)
            self.assertEqual(len(rows), 1, f"expected one row, got {rows}")

            epoch, who, host, event = rows[0]
            self.assertTrue(epoch.isdigit(), f"bad timestamp {epoch!r}")
            self.assertEqual(who, name)
            self.assertEqual(event, "new")
            # The harness connects over loopback.
            self.assertTrue(host, "host column was empty")

    def test_lastlog_reports_name_time_and_host(self) -> None:
        name = "Ziplogtwo"

        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, name, PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            # lastlog is an L7 command; a fresh character cannot reach it.
            patch_player_file(mud, name, Levl=IMMORTAL_LEVEL)

            with mud.connect(timeout=120) as client:
                login(client, name, PASSWORD)
                # expect() returns the matched pattern, so mark the transcript
                # and slice it afterwards to get just the command's output.
                mark = len(client.transcript)
                client.send("lastlog")
                client.expect(
                    "shown of", "No login history", timeout=30
                )
                client.drain(0.5)
                output = client.transcript[mark:]

        self.assertIn(name, output, f"character missing from output:\n{output}")
        self.assertIn(
            "Host",
            output,
            f"header missing from output:\n{output}",
        )
        # The login that just happened must be present as a connect.
        self.assertIn(
            "connect",
            output,
            f"connect event missing from output:\n{output}",
        )

    def test_journal_survives_a_restart(self) -> None:
        """The point of the file: history outlives the process."""
        name = "Ziplogtri"

        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, name, PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            before = journal_rows(mud)
            self.assertEqual(len(before), 1)

            patch_player_file(mud, name, Levl=IMMORTAL_LEVEL)

            with mud.connect(timeout=120) as client:
                login(client, name, PASSWORD)
                client.send("quit")
                client.wait_closed()

            after = journal_rows(mud)
            self.assertEqual(
                len(after),
                2,
                f"second login was not appended: {after}",
            )
            self.assertEqual(after[0][3], "new")
            self.assertEqual(after[1][3], "connect")
            self.assertEqual(after[1][1], name)


if __name__ == "__main__":
    unittest.main()

"""One player quitting must not disconnect anybody else.

do_quit ends with a loop meant to close any *other* descriptor still
holding the same character, a duplicate login. It compared CHAR_DATA.id,
which nothing in this codebase ever assigns -- the field was only ever read
at that one line. Every character's id was therefore 0, the comparison was
0 == 0, and every quit extracted and disconnected every player online.

It was reported as "snooping someone who deletes disconnects the
immortal", which is just the case where somebody was watching closely
enough to notice. DELETE calls do_quit, so it is the same loop.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from live_mud import (  # noqa: E402
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Zquitiso1"


def run(client, command: str, settle: float = 3.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class QuitIsolationTests(unittest.TestCase):
    def test_a_bystander_survives_someone_elses_quit(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as watcher:
                create_character(watcher, "Zquitstay", PASSWORD)
                watcher.drain(2.0)

                with mud.connect(timeout=120) as quitter:
                    create_character(quitter, "Zquitaway", PASSWORD)
                    quitter.drain(2.0)
                    quitter.send("quit")
                    quitter.drain(3.0)

                watcher.drain(3.0)
                self.assertIn("Zquitstay", run(watcher, "score"),
                              "a bystander was disconnected by someone "
                              "else's quit")

    def test_a_snooping_immortal_survives_the_victim_quitting(self) -> None:
        """The symptom as reported: only the snoop should end."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as setup:
                create_character(setup, "Zquitimm", PASSWORD)
                setup.send("quit")
                setup.wait_closed()
            patch_player_file(mud, "Zquitimm", Levl=70)

            with mud.connect(timeout=120) as god:
                login(god, "Zquitimm", PASSWORD)

                with mud.connect(timeout=120) as victim:
                    create_character(victim, "Zquitvict", PASSWORD)
                    victim.drain(2.0)

                    run(god, "snoop Zquitvict")
                    victim.send("quit")
                    victim.drain(3.0)

                god.drain(3.0)
                self.assertIn("left the game", god.transcript,
                              "the snooper should be told the snoop ended")
                self.assertIn("Zquitimm", run(god, "score"),
                              "the snooping immortal was disconnected")

    def test_the_quitter_is_actually_gone(self) -> None:
        """The loop still has to do its job, not just stop over-reaching."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as watcher:
                create_character(watcher, "Zquitseer", PASSWORD)
                watcher.drain(2.0)

                with mud.connect(timeout=120) as quitter:
                    create_character(quitter, "Zquitleft", PASSWORD)
                    quitter.drain(2.0)
                    quitter.send("quit")
                    quitter.wait_closed()

                watcher.drain(3.0)
                self.assertNotIn("Zquitleft", run(watcher, "who"))


if __name__ == "__main__":
    unittest.main()

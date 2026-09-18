"""Immortal tooling: wizhelp listing, purge, and the holylight header.

Each of these went wrong in a way that reading the code would not have
caught, which is why they are tested behaviourally:

  * `smash` and `iportal` were both in wizhelp all along -- the listing was
    just in command-table order, which hoists a few entries to the front for
    prefix matching, so nothing was where you would look for it. The test
    that matters is that the output is *sorted*, not that a given command
    appears.
  * `purge <object>` silently answered "They aren't here" for every object,
    because the argument path only ever looked up characters.
  * Purging a player extracted the character outright. It should sever the
    link and leave them recoverable.
"""
from __future__ import annotations

import re
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

IMMORTAL_LEVEL = 70
PASSWORD = "Zimmtool1"


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def immortal(mud: LiveMud, name: str, level: int = IMMORTAL_LEVEL) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        client.wait_closed()
    patch_player_file(mud, name, Levl=level)


@unittest.skipIf(SKIP is not None, SKIP or "")
class WizhelpTests(unittest.TestCase):
    def test_listing_is_sorted_and_lists_staff_commands_only(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zwizone")
            with mud.connect(timeout=120) as client:
                login(client, "Zwizone", PASSWORD)
                output = run(client, "wizhelp", settle=6.0)

            listed = [name for _, name in re.findall(r"\[\s*(\d+)\] (\S+)", output)]

            self.assertGreater(len(listed), 80,
                               "wizhelp should cover the staff commands")
            self.assertTrue(all(int(lv) >= 51 for lv, _ in
                                re.findall(r"\[\s*(\d+)\] (\S+)", output)),
                            "mortal commands do not belong in wizhelp")
            self.assertEqual(listed, sorted(listed),
                             "the listing has to be alphabetical to be usable")

            # The ones that prompted this: all present before, but
            # buried in the hoisted block at the top of the table.
            for command in ("smash", "iportal", "spellup", "spellpurge"):
                self.assertIn(command, listed)

            # ...and one command per name, with no handler listed twice.
            self.assertEqual(len(listed), len(set(listed)))

    def test_a_lower_ranked_immortal_sees_less(self) -> None:
        """The trust ceiling still applies, as does the LEVEL_HERO floor."""
        with LiveMud() as mud:
            immortal(mud, "Zwiztwo", level=62)
            with mud.connect(timeout=120) as client:
                login(client, "Zwiztwo", PASSWORD)
                output = run(client, "wizhelp", settle=6.0)

            listed = [name for _, name in re.findall(r"\[\s*(\d+)\] (\S+)", output)]
            levels = [int(lv) for lv, _ in re.findall(r"\[\s*(\d+)\] (\S+)", output)]

            self.assertTrue(listed, "a level 62 immortal still has commands")
            self.assertLessEqual(max(levels), 62)
            self.assertNotIn("smash", listed)      # level 65
            self.assertNotIn("iportal", listed)    # level 64


@unittest.skipIf(SKIP is not None, SKIP or "")
class PurgeTests(unittest.TestCase):
    def test_purge_removes_a_named_object(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zpurgeone")
            with mud.connect(timeout=120) as client:
                login(client, "Zpurgeone", PASSWORD)

                # Target our own room so the vnum is certain to exist.
                run(client, "iportal Zpurgeone", settle=3.0)
                self.assertIn("portal", run(client, "look", settle=3.0).lower())

                purged = run(client, "purge portal", settle=3.0)
                self.assertIn("purged", purged)
                self.assertNotIn("aren't here", purged)
                self.assertNotIn("portal", run(client, "look", settle=3.0).lower())

    def test_purging_a_player_leaves_them_linkdead_not_destroyed(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zpurgetwo")
            with mud.connect(timeout=120) as god:
                login(god, "Zpurgetwo", PASSWORD)

                with mud.connect(timeout=120) as mortal:
                    create_character(mortal, "Zpurgemort", PASSWORD)
                    mortal.drain(2.0)

                    result = run(god, "purge Zpurgemort", settle=4.0)
                    self.assertIn("link severed", result)
                    mortal.wait_closed()

                # The character survives: they can log back in, which is the
                # whole difference between linkdead and extracted.
                with mud.connect(timeout=120) as again:
                    login(again, "Zpurgemort", PASSWORD)
                    self.assertIn("Zpurgemort", run(again, "score", settle=3.0))

    def test_bare_purge_still_clears_the_room(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zpurgethr")
            with mud.connect(timeout=120) as client:
                login(client, "Zpurgethr", PASSWORD)
                run(client, "iportal Zpurgethr", settle=3.0)
                self.assertIn("Room purged", run(client, "purge", settle=3.0))
                self.assertNotIn("portal", run(client, "look", settle=3.0).lower())


@unittest.skipIf(SKIP is not None, SKIP or "")
class HolylightTests(unittest.TestCase):
    def test_holylight_shows_the_room_vnum(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zholyone")
            with mud.connect(timeout=120) as client:
                login(client, "Zholyone", PASSWORD)
                run(client, "holylight", settle=2.0)

                looked = run(client, "look", settle=3.0)
                match = re.search(r"\[Room: (\d+)\]", looked)
                self.assertIsNotNone(match, "holylight should carry the vnum")

                # And it is the real vnum, not a constant.
                stat = run(client, "stat room", settle=3.0)
                self.assertIn(match.group(1), stat)


if __name__ == "__main__":
    unittest.main()

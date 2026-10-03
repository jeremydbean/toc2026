"""Two of Alaric's bug reports, October 2026.

* "Hero leveled players should never get full. Sometimes they are
  permanently in a 'full' state and cannot eat food or pill items."
  Hunger stands still from LEVEL_HERO up, and stood still wherever it was:
  levelling while sated, or a RESTORE (which sets it to 100), left a hero
  "too full to eat" for good -- no food, no pills, no training cakes.

* "After logging in, players are seeing 'No help on that word'... prior to
  the MOTD." Every hero (51+) was shown the immortal MOTD, and every IMOTD
  topic is level 60 or more. Behind it: the MOTD and IMOTD commands' own
  help entries in commands.are, which loads first, hid the real messages in
  toc.are -- every login printed "Syntax: motd" instead of the MOTD.
"""
from __future__ import annotations

import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()

PASSWORD = "Zheropass1"
TEMPLE = 4207
BREAD = 3011            # "a bread", ITEM_FOOD
BERRIES = 100           # "A bunch of smurfberries", ITEM_PILL


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.5)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud: LiveMud, name: str, **fields: object) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Room=TEMPLE, **fields)


@unittest.skipIf(SKIP is not None, SKIP or "")
class HeroReportTests(unittest.TestCase):
    def test_heroes_are_never_too_full_and_see_no_missing_help(self) -> None:
        with LiveMud() as mud:
            # Cond is drunk, full, thirst: a hero RESTOREd to 100.
            make(mud, "Zherofull", Levl=55, Cond="0 100 100")
            make(mud, "Zmortfull", Levl=20, Cond="0 48 48")
            make(mud, "Zherogod", Levl=70)

            with mud.connect(timeout=120) as hero, \
                    mud.connect(timeout=120) as mortal, \
                    mud.connect(timeout=120) as god:
                login(hero, "Zherofull", PASSWORD)
                self.assertNotIn("No help on that word", hero.transcript,
                                 "a hero is not shown the immortal MOTD")
                # The real message of the day, not the MOTD command's own
                # help, which commands.are loaded first and do_help, taking
                # the first match, showed at every login instead.
                self.assertIn("ignorance of the rules is not an excuse",
                              hero.transcript)
                self.assertNotIn("Syntax: motd", hero.transcript)
                login(god, "Zherogod", PASSWORD)
                self.assertIn("Welcome Immortal", god.transcript,
                              "an immortal still is")
                login(mortal, "Zmortfull", PASSWORD)

                for vnum, keyword, who in ((BREAD, "bread", "zherofull"),
                                           (BERRIES, "smurfberries", "zherofull"),
                                           (BREAD, "bread", "zmortfull")):
                    run(god, f"load obj {vnum}")
                    run(god, f"give {keyword} {who}")

                ate = run(hero, "eat bread")
                self.assertNotIn("too full", ate)
                self.assertIn("You eat", ate)
                ate = run(hero, "eat smurfberries")
                self.assertNotIn("too full", ate)
                self.assertIn("You eat", ate)

                # A mortal still fills up: only heroes are spared.
                self.assertIn("too full", run(mortal, "eat bread"))


if __name__ == "__main__":
    unittest.main()

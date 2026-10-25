"""Alaric's bug reports of 2026-10-07 (area/bugs.txt).

- "walk quest" said there was no destination called quest. WALKTO QUEST
  now walks staff to the room the quest master named, and since
  2026-10-25 walks a mortal to the area's entrance and no further
  (owner, 2026-10-20: finding the quarry is the quest). It refused
  mortals outright before, which Trentlin read as staff-only.
- A quest sent him to a Storage Room in the Valley of the Elves that no
  way he could walk reached. The quest master now chooses only targets
  this character could walk to by WALKTO's own rules
  (walkto_mark_reachable), so WALKTO QUEST always finds the way.
- The web client's Affects button sent "affects", which the game did not
  know. The button sends "affect", and AFFECTS is a command too.
- The Gear Finder offered thieves no second weapon: that is in
  tests/test_gear_finder.py.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PASSWORD = "Zreportpw1"
QUEST_ROOM = 2497


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class SourceTests(unittest.TestCase):
    def test_the_quest_master_asks_whether_a_target_can_be_walked_to(self) -> None:
        source = (ROOT / "src" / "quest.c").read_text(encoding="latin-1")
        body = source[source.index("void generate_quest("):]
        body = body[:body.index("room = victim->in_room;")]
        self.assertIn("walkto_mark_reachable( ch );", body)
        self.assertRegex(body, r"if \( !walkto_reached\( candidate->in_room \) \)\s*continue;")

    def test_the_affects_button_sends_a_command_the_game_knows(self) -> None:
        html = (ROOT / "webadmin" / "static" / "client.html").read_text(encoding="utf-8")
        self.assertIn('data-command="affect">Affects', html)
        interp = (ROOT / "src" / "interp.c").read_text(encoding="latin-1")
        self.assertRegex(interp, r'\{ "affects",\s+do_affect,')


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_walk_quest_and_affects(self) -> None:
        with LiveMud() as mud:
            for name in ("Zreporter", "Zwalker"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zreporter", Levl=20, Room=QUEST_ROOM)
            patch_player_file(mud, "Zwalker", Levl=20, Tru=70, Room=QUEST_ROOM)

            with mud.connect(timeout=120) as player:
                login(player, "Zreporter", PASSWORD)
                run(player, "scroll 0")

                out = run(player, "affects")
                self.assertNotIn("Huh?", out, out)
                self.assertRegex(out, r"(?i)affected", out)

                self.assertIn("not on a quest", run(player, "walk quest"))
                # A level 20's pool is every live mobile from level 3 to 20
                # it could walk to -- hundreds in a fresh world -- so "no
                # suitable quests" is a failure here, not bad luck. It was
                # a silent pass-through before, and a skip below.
                asked = run(player, "aquest request", 2.5)
                self.assertNotIn("no suitable quests", asked)
                walked = run(player, "walk quest", 2.0)
                self.assertNotIn("is for immortals", walked, walked)
                self.assertTrue(re.search(r"area's entrance|already in the area|"
                                          r"no road into", walked), walked)
                run(player, "walkto stop")
                run(player, "aquest abort", 1.5)

                # Mud School's kit: what a new player types for it works,
                # and HELP finds it by those words (watched log, 2026-10-06).
                self.assertIn("OUTFIT", run(player, "help subissue").upper())
                self.assertNotIn("Huh?", run(player, "issue"))

                player.send("quit")
                player.wait_closed()

            # An immortal, by trust, still walks to the quest.
            with mud.connect(timeout=120) as player:
                login(player, "Zwalker", PASSWORD)
                run(player, "scroll 0")
                self.assertIn("not on a quest", run(player, "walk quest"))
                asked = run(player, "aquest request", 2.5)
                self.assertRegex(asked, r"(?i)quest", asked)
                self.assertNotIn("no suitable quests", asked)

                walked = run(player, "walk quest", 2.0)
                self.assertTrue(re.search(r"You set off for|You are already at", walked),
                                "WALKTO QUEST found no way to the quest: " + walked)
                run(player, "walkto stop")


if __name__ == "__main__":
    unittest.main()

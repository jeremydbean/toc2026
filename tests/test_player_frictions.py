"""Four commands players repeated because the answer did not tell them enough.

From the October 2026 watch logs (2026-10-20):

- TRACK pointed a random way on a missed roll and said "You find a trail"
  exactly as a good roll does, so trackers typed it four to seven times
  running to take a vote. A miss now says the trail was lost, and a hit
  says how far off the quarry is, as HELP TRACK always promised.
- HIDE said "You attempt to hide." whether it worked or not; a thief at
  1% hid thirteen times running, hidden in none of them.
- The pit healer's REFRESH is a slice of its level in moves for 10 gold,
  and players bought it five times in a row. One REFRESH buys every
  slice the pool needs now, at the same price a slice.
- PRACTICE spent one session a command; a trailing count or MAX spends
  that many.

And from the same day's refusals and channels:

- A command nobody knows said only "Huh?" -- to "comapre", "heall",
  "logout", "logoff", and a new player trying "talk salir", "learn" and
  "speak" at a trainer. It suggests the command within a typo now, and
  names the right one for the words players reach for.
- USE did not exist ("use bomb" in a Hyrule dungeon); it finds the item
  and hands the line to the verb for it.
- Alignment went past -1000: the branch for victims within 500 of the
  slayer was the one group_gain left unclamped ("my alignment just
  alternates between -1000 and -1005").
"""
from __future__ import annotations

import pathlib
import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zfriction1"
TEMPLE = 4207
ALTAR = 4208          # the Adept of Devota, the pit healer, resets here


def body(path: str, start: str) -> str:
    source = (ROOT / path).read_text(encoding="latin-1")
    text = source[source.index(start):]
    return text[:text.index("\n}\n")]


class FrictionSourceTests(unittest.TestCase):
    def test_track_never_points_a_random_way(self) -> None:
        source = (ROOT / "src" / "hunt.c").read_text(encoding="latin-1")
        track = source[source.index("void do_track("):source.index("End do_track")]
        self.assertNotIn("number_door()", track)
        self.assertIn("check_improve( ch, gsn_tracking, false", track)
        self.assertIn("check_improve( ch, gsn_tracking, true", track)

    def test_alignment_is_clamped_however_it_moves(self) -> None:

        # Every move goes through alignment_shift (src/alignment.c) since
        # the rebuild of 2026-10-21; the kill is one caller of it.
        source = (ROOT / "src" / "alignment.c").read_text(encoding="latin-1")
        block = source[source.index("void alignment_shift("):source.index("void alignment_kill(")]
        self.assertIn("now = URANGE( -1000, was + delta, 1000 );", block)
        self.assertIn('"risen"', block, "a rise is not reported as lowered")
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        self.assertNotIn("gch->alignment -= change", fight)

    def test_hide_says_which(self) -> None:
        hide = body("src/act_move.c", "void do_hide(")
        self.assertNotIn('send_to_char( "You attempt to hide.', hide)
        self.assertIn("You slip into the shadows", hide)


@unittest.skipIf(SKIP is not None, SKIP or "")
class FrictionLiveTests(unittest.TestCase):
    def run_cmd(self, client, command: str, settle: float = 1.8) -> str:
        mark = len(client.transcript)
        client.send(command)
        client.drain(settle)
        return client.transcript[mark:]

    def test_track_hide_refresh_and_practice(self) -> None:
        with LiveMud() as mud:
            for name in ("Zfriction", "Zquarry"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zfriction", Levl=30, Tru=70, Room=TEMPLE)
            patch_player_file(mud, "Zquarry", Levl=30, Room=2401)

            with mud.connect(timeout=120) as quarry, mud.connect(timeout=120) as client:
                login(quarry, "Zquarry", PASSWORD)
                login(client, "Zfriction", PASSWORD)
                self.run_cmd(client, "scroll 0", 1.0)

                # TRACK at 1%: a missed roll loses the trail and names no
                # direction. 1% is the lowest the skill goes and still finds
                # the trail one time in a hundred (CI, 2026-10-26), so look
                # at the first miss of up to five tries.
                self.run_cmd(client, "set skill zfriction track 1", 1.2)
                miss = re.compile(r"lose|nothing you trust|cannot pick out")
                for _ in range(5):
                    reply = self.run_cmd(client, "track zquarry", 2.0)
                    if miss.search(reply):
                        break
                self.assertTrue(miss.search(reply), reply)
                self.assertNotIn("You find a trail", reply)
                # ...and at 100% the way, and how far.
                self.run_cmd(client, "set skill zfriction track 100", 1.2)
                reply = self.run_cmd(client, "track zquarry", 2.0)
                self.assertRegex(reply, r"You find a trail \w+ from here for Zquarry, "
                                        r"(just beyond|not far off|some way off|a long way off)\.")

                # HIDE says whether it worked.
                self.run_cmd(client, "set skill zfriction hide 1", 1.2)
                self.assertIn("find nowhere that would cover you", self.run_cmd(client, "hide", 1.6))
                # At 100% HIDE still misses one roll in a hundred
                # (number_percent() < 100), so look for the first success.
                self.run_cmd(client, "set skill zfriction hide 100", 1.2)
                for _ in range(5):
                    reply = self.run_cmd(client, "hide", 1.6)
                    if "You slip into the shadows" in reply:
                        break
                self.assertIn("You slip into the shadows", reply)
                self.run_cmd(client, "visible", 1.2)

                # The healer's REFRESH fills the pool in one go, priced by the slice.
                self.run_cmd(client, "goto %d" % ALTAR, 1.6)
                self.run_cmd(client, "set char zfriction move 1", 1.2)
                self.run_cmd(client, "set char zfriction gold 1000", 1.2)
                reply = self.run_cmd(client, "heal refresh", 4.0)
                self.assertIn("You feel fully refreshed!", reply)
                self.assertRegex(reply, r"\((\d+) castings, (\d+) gold\.\)")
                casts, gold = map(int, re.search(r"\((\d+) castings, (\d+) gold", reply).groups())
                self.assertEqual(gold, casts * 10)
                self.assertIn("as fresh as I can make them", self.run_cmd(client, "heal refresh", 4.0))

                # PRACTICE <skill> <count> before the Weaponsmaster (mob 10,
                # any class, any guild), brought to the Temple.
                self.run_cmd(client, "goto %d" % TEMPLE, 1.6)
                self.run_cmd(client, "load mob 10", 1.6)
                self.run_cmd(client, "set skill zfriction sword 1", 1.2)
                self.run_cmd(client, "set char zfriction prac 40", 1.2)
                reply = self.run_cmd(client, "practice sword 3", 2.0)
                self.assertRegex(reply, r"You practice sword 3 times, to \d+%\.")
                self.assertIn("Practice how many times?", self.run_cmd(client, "practice sword 0", 1.6))
                reply = self.run_cmd(client, "practice sword max", 2.0)
                self.assertIn("You are now learned at sword.", reply)


    def test_huh_suggests_and_use_finds_the_verb(self) -> None:
        with LiveMud() as mud:
            for name in ("Zhinter", "Zhkeeper"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zhinter", Levl=20, Room=TEMPLE)
            patch_player_file(mud, "Zhkeeper", Levl=70, Room=TEMPLE)

            with mud.connect(timeout=120) as keeper, mud.connect(timeout=120) as client:
                login(keeper, "Zhkeeper", PASSWORD)
                login(client, "Zhinter", PASSWORD)
                self.run_cmd(client, "scroll 0", 1.0)

                self.assertIn("Huh? Did you mean COMPARE", self.run_cmd(client, "comapre sword", 1.4))
                self.assertIn("To leave the game, type QUIT.", self.run_cmd(client, "logout", 1.4))
                self.assertIn("PRACTICE", self.run_cmd(client, "learn", 1.4))
                self.assertIn("SAY", self.run_cmd(client, "talk salir", 1.4))
                reply = self.run_cmd(client, "xqzv", 1.4)
                self.assertIn("Huh?", reply)
                self.assertNotIn("Did you mean", reply)

                self.assertIn("Use what?", self.run_cmd(client, "use", 1.4))
                self.assertIn("Bomb what?", self.run_cmd(client, "use bomb", 1.4))
                self.assertIn("You don't have that.", self.run_cmd(client, "use zzzwidget", 1.4))
                self.run_cmd(keeper, "load obj 3083", 1.4)       # cure light wounds
                self.run_cmd(keeper, "give potion zhinter", 1.6)
                client.drain(1.0)
                self.assertIn("You quaff", self.run_cmd(client, "use potion", 2.0))


if __name__ == "__main__":
    unittest.main()

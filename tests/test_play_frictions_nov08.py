"""What the play journal of 2026-11-07/08 showed, fixed.

- HEAL HEAL and HEAL MANA were typed five and six times running, a dozen
  times in one session: like HEAL REFRESH, each now buys as many castings
  as the pool needs, at the price of one each, as far as the purse goes,
  and sells nothing to a full pool.
- STOP and STOP WALK were answered "Huh?" while a walk went on: STOP ends
  a WALKTO, and the Mudlet package stops its own walk on either.
- A Hyrule small key taken from a kill crumbled within the hour (the
  corpse's key timer), though small keys are kept at quit as on the NES.
- A recover quest's item handed in read as a lost item in the journal.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (LiveMud, SPARRING_FLOOR, SPARRING_GUARD, create_character, login,
                      patch_player_file, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
ALTAR = 4208            # the pit healer resets here


def quit_out(client) -> None:
    client.sync("save")
    client.send("quit")
    assert client.wait_closed(30)


class FrictionSourceTests(unittest.TestCase):
    def test_a_quest_hand_in_is_not_a_loss(self) -> None:
        code = (ROOT / "src" / "playlog.c").read_text(encoding="latin-1")
        body = code[code.index("void playlog_obj_gone("):]
        body = body[:body.index("journal_write")]
        self.assertIn('!str_cmp( current_cmd, "aquest" )', body)

    def test_the_mudlet_package_stops_its_walk_on_stop(self) -> None:
        xml = (ROOT / "mudlet" / "package" / "TimesOfChaos.xml").read_text(encoding="utf-8")
        self.assertIn(r"<regex>^stop(?:\s+walk(?:ing)?)?$</regex>", xml)
        self.assertIn("function tocMudlet.stopCommand(line)", xml)
        body = xml[xml.index("function tocMudlet.stopCommand(line)"):]
        body = body[:body.index("\nend\n")]
        self.assertIn('walkStop("stopped.")', body)
        self.assertIn("send(line)", body)


@unittest.skipIf(SKIP is not None, SKIP or "")
class FrictionLiveTests(unittest.TestCase):

    def test_healer_fills_stop_ends_a_walk_and_small_keys_keep(self) -> None:
        with LiveMud(fixtures=True) as mud:
            with mud.connect() as c:
                create_character(c, "Zfhstaff", "Zstaffpass1")
                quit_out(c)
            patch_player_file(mud, "Zfhstaff", Levl=70)
            with mud.connect() as c:
                create_character(c, "Zfhealee", "Zhealpass12")
                quit_out(c)
            patch_player_file(mud, "Zfhealee", Levl=20, Room=ALTAR)

            with mud.connect() as staff, mud.connect() as player:
                login(staff, "Zfhstaff", "Zstaffpass1")
                login(player, "Zfhealee", "Zhealpass12")

                # HEAL HEAL: every casting the hit points need, in one go.
                staff.must("set char zfhealee hp 3000", "")
                staff.must("set char zfhealee gold 100000", "")
                reply = player.must("heal heal", "you are whole")
                casts, gold = map(int, re.search(r"\((\d+) castings?, (\d+) gold\.\)", reply).groups())
                self.assertGreater(casts, 5, reply)
                self.assertEqual(gold, casts * 500)
                self.assertIn("<3000hp", player.sync("look"))
                self.assertIn("as whole as I can make you", player.sync("heal heal"))
                # As far as the purse goes, and says so.
                staff.must("set char zfhealee hp 9000", "")
                for pile in ("platinum", "silver", "copper"):
                    staff.must("set char zfhealee %s 0" % pile, "")
                staff.must("set char zfhealee gold 1000", "")
                reply = player.must("heal heal", "that is all you can pay for")
                self.assertIn("(2 castings, 1000 gold.)", reply)
                self.assertIn("do not have enough gold", player.sync("heal heal"))

                # HEAL MANA the same.
                staff.must("set char zfhealee mana 2000", "")
                staff.must("set char zfhealee gold 100000", "")
                reply = player.must("heal mana", "your mind is full")
                casts, gold = map(int, re.search(r"\((\d+) castings?, (\d+) gold\.\)", reply).groups())
                self.assertGreater(casts, 1, reply)
                self.assertEqual(gold, casts * 100)
                self.assertIn("as full as I can make it", player.sync("heal mana"))

                # STOP when nothing walks; then STOP ends a WALKTO, once.
                self.assertIn("You are not walking anywhere", player.sync("stop"))
                mark = len(player.transcript)
                player.send("walkto azeroth")
                player.send("stop walk")
                player.expect("You stop walking", timeout=20)
                player.sync("look")
                said = player.transcript[mark:]
                self.assertNotIn("Huh?", said)
                self.assertEqual(said.count("You stop walking"), 1, said)

                # A Hyrule small key from a kill keeps; an ordinary key crumbles.
                def key_timer_from_kill(vnum: int) -> int:
                    staff.must("goto %d" % SPARRING_FLOOR, "")
                    staff.must("purge", "")
                    staff.must("load mob %d" % SPARRING_GUARD, "")
                    staff.must("load obj %d" % vnum, "")
                    staff.must("give key guard", "You give")
                    staff.must("slay guard", "")
                    staff.must("get all corpse", "key")
                    stat = staff.must("ostat key", "Timer")
                    staff.must("drop key", "")
                    staff.must("purge", "")
                    return int(re.search(r"Timer: (\d+)", stat).group(1))

                self.assertEqual(key_timer_from_kill(30227), 0)
                self.assertTrue(40 <= key_timer_from_kill(29002) <= 80)

                quit_out(player)
                quit_out(staff)


if __name__ == "__main__":
    unittest.main()

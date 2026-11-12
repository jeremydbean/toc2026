"""Player skill and gameplay bugs from the review of 2026-11-12.

- BLINDING FISTS paid its lag only after a blow landed, so a flurry that
  missed every time cost no lag and could be fired a pulse until one
  connected. FISTS OF FURY had the same hole: a first blow that missed sent
  the victim running, lag-free. Both pay before the first roll now.
- STUNNING BLOW's miss rolled half the level to three times it against a
  landed blow's level to twice it: a miss averaged more than a hit. The
  ranges are stunning_blow_range() in combat_rules.c (tests/test_combat_rules.c
  holds the arithmetic), and a miss says it glanced off.
- CALM stopped at the first undead, magic-immune, berserk, frenzied or
  already-calm character in the room -- a `return` where stock ROM has
  `continue` -- and calmed nobody after it.
- LISTEN rolled only when somebody was behind the door, and a miss said the
  words of an empty room; DANGER SENSE's miss said "You sense no danger".
  Each miss now says it was one.
- SEARCH at 1% or less took its lag and said nothing at all.
- Mud School: can_see_room closed ROOM_NEWBIES_ONLY rooms above level 5 and
  everything else above level 10, so a level 6 to 10 was routed there and
  refused at the door; newbie_room_refuses() is the one test now, at 10.
- SEAL never took ne, nw, se or sw.
- The automatic guild join at level 6 took 50 gold, or emptied a purse
  short of it; the player never asked for it, so it is free now.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (LiveMud, SPARRING_GUARD, carried_copper, create_character,
                      login, patch_player_file, place_sparring_guard, room_of,
                      skip_reason)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PASSWORD = "Zskillrev1"
TEMPLE = 4207
LOCK_ROOM = 32709        # fixture: a closed, locked door south
BEYOND_LOCK = 32710
SPARRING_FLOOR = 32700
GAS_HALL_EXIT = 32703
SCHOOL_DOORSTEP = 3757   # "A Room in Mud School", not flagged; north is flagged
SCHOOL_FIRST = 3701
SKILL_SET = "skill set to"   # SET SKILL: "<name> <skill> skill set to <n>."


def function_body(path: str, signature: str) -> str:
    text = (ROOT / path).read_text(encoding="latin-1")
    start = text.index(signature)
    brace = text.index("{", start)
    depth = 0
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise AssertionError("no end to " + signature)


def without_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


class SkillReviewSourceTests(unittest.TestCase):
    def test_flurries_pay_their_lag_before_the_first_roll(self) -> None:
        for name, gsn in (("do_blinding_fists", "gsn_blinding_fists"),
                          ("do_fists_of_fury", "gsn_fists_of_fury")):
            body = without_comments(function_body("src/fight.c", "void %s(" % name))
            loop = body.index("for(hit")
            lag = body.find("WAIT_STATE( ch, skill_table[%s].beats);" % gsn)
            self.assertNotEqual(lag, -1, name)
            self.assertLess(lag, loop, name + " pays its lag only after a blow lands")

    def test_stunning_blow_uses_the_shared_ranges(self) -> None:
        body = without_comments(function_body("src/fight.c", "void do_stunning_blow("))
        self.assertEqual(body.count("stunning_blow_range("), 2)
        self.assertNotIn("ch->level*3", body)
        self.assertNotIn("ch->level/2", body)
        self.assertIn("glances off", body)

    def test_calm_passes_over_rather_than_stopping(self) -> None:
        body = without_comments(function_body("src/magic.c", "void spell_calm("))
        wave = body[body.index("for (vch = ch->in_room->people", body.index("number_range")):]
        self.assertNotIn("return;", wave)
        self.assertGreaterEqual(wave.count("continue;"), 2)

    def test_one_newbie_room_test(self) -> None:
        offenders = []
        for path in sorted((ROOT / "src").glob("*.c")):
            text = without_comments(path.read_text(encoding="latin-1"))
            for match in re.finditer(r"ROOM_NEWBIES_ONLY", text):
                window = text[max(0, match.start() - 160):match.end() + 40]
                if re.search(r"level\s*>\s*(5|10)\b", window):
                    offenders.append(path.name)
        self.assertEqual(offenders, [], "a newbie room test outside newbie_room_refuses")
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        self.assertRegex(merc, r"#define LEVEL_NEWBIE\s+10\b")
        server = (ROOT / "webadmin" / "server.py").read_text(encoding="utf-8")
        self.assertIn("LEVEL_NEWBIE = 10", server)

    def test_seal_reads_directions_as_movement_does(self) -> None:
        body = function_body("src/act_wiz.c", "void do_seal(")
        self.assertIn("door_direction_word( arg )", body)
        self.assertNotIn('str_prefix( arg, "north"', body)

    def test_the_automatic_guild_join_is_free(self) -> None:
        body = function_body("src/update.c", "static void advance_level_body(")
        join = body[body.index("ch->level == 6 && ch->pcdata->guild == GUILD_NONE"):]
        join = without_comments(join[:join.index("if (guild < 0")])
        self.assertNotIn("add_money", join)
        self.assertNotIn("new_gold", join)
        self.assertNotIn("spend_copper", join)


@unittest.skipIf(SKIP is not None, SKIP or "")
class SkillReviewLiveTests(unittest.TestCase):
    def make(self, mud: LiveMud, **levels: dict) -> None:
        """Create each named character and patch its file. Mortals, because
        staff never miss a skill's roll (owner, 2026-11-10)."""
        for name, fields in levels.items():
            with mud.connect(timeout=120) as client:
                create_character(client, name, PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, name, Room=TEMPLE, **fields)

    def test_misses_say_they_missed(self) -> None:
        with LiveMud(fixtures=True) as mud:
            self.make(mud, Zskstaff={"Levl": 70}, Zskmortal={"Levl": 30})
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as me:
                login(staff, "Zskstaff", PASSWORD)
                login(me, "Zskmortal", PASSWORD)
                me.sync("scroll 0")

                # LISTEN: a miss says so, an empty room says nobody, and
                # somebody there is heard. At 1% the roll never lands
                # (number_percent() < 1), at 100% it lands 99 times in 100.
                staff.must("transfer zskmortal %d" % LOCK_ROOM, "Ok.")
                self.assertEqual(room_of(staff, "zskmortal"), LOCK_ROOM)
                staff.must("set skill zskmortal 'listen at door' 1", SKILL_SET)
                reply = me.sync("listen south")
                self.assertIn("cannot make out anything", reply)
                self.assertNotIn("out of the ordinary", reply)
                staff.must("set skill zskmortal 'listen at door' 100", SKILL_SET)
                for _ in range(5):
                    reply = me.sync("listen south")
                    if "hear nothing on the other side" in reply:
                        break
                self.assertIn("hear nothing on the other side", reply)
                staff.sync("goto %d" % BEYOND_LOCK)
                for _ in range(5):
                    reply = me.sync("listen south")
                    if "You hear someone" in reply:
                        break
                self.assertIn("You hear someone, or something", reply)

                # SEARCH below the skill says why, and costs no lag.
                staff.must("set skill zskmortal search 1", SKILL_SET)
                self.assertIn("know too little of searching", me.sync("search south"))
                staff.must("set skill zskmortal search 0", SKILL_SET)
                self.assertIn("don't know how to search", me.sync("search south"))

                # DANGER SENSE: a miss is not "no danger".
                staff.must("set skill zskmortal 'danger sense' 1", SKILL_SET)
                reply = me.sync("danger")
                self.assertIn("cannot tell what lies about you", reply)
                self.assertNotIn("You sense no danger", reply)
                staff.must("set skill zskmortal 'danger sense' 0", SKILL_SET)
                self.assertIn("no idea how to sense danger", me.sync("danger"))

    def test_calm_reaches_the_whole_room_and_seal_takes_diagonals(self) -> None:
        with LiveMud(fixtures=True) as mud:
            self.make(mud, Zskstaff={"Levl": 70}, Zskmortal={"Levl": 30})
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as me:
                login(staff, "Zskstaff", PASSWORD)
                login(me, "Zskmortal", PASSWORD)
                me.sync("scroll 0")

                # CALM: a character already calm ahead of the others in the
                # room used to end the wave. The caster calms itself alone,
                # then arrives in front of the sparring guard.
                staff.must("set skill zskmortal calm 100", SKILL_SET)
                staff.must("set char zskmortal mana 5000", "set to")
                staff.must("restore zskmortal", "restored")
                staff.must("transfer zskmortal %d" % GAS_HALL_EXIT, "Ok.")
                for _ in range(5):
                    reply = me.sync("cast calm")
                    if "A wave of calm passes over you" in reply:
                        break
                self.assertIn("A wave of calm passes over you", reply)
                place_sparring_guard(staff, "Zskstaff", SPARRING_FLOOR)
                staff.must("transfer zskmortal %d" % SPARRING_FLOOR, "Ok.")
                stat = staff.must("stat mob sparring", "Vnum: %d" % SPARRING_GUARD)
                # STAT MOB lists affect bits as "Affect 1: ...".
                self.assertNotRegex(stat, r"Affect 1:.*\bcalm\b")
                for _ in range(5):
                    reply = me.sync("cast calm")
                    if "A wave of calm passes over the room" in reply:
                        break
                stat = staff.must("stat mob sparring", "Vnum: %d" % SPARRING_GUARD)
                self.assertRegex(stat, r"Affect 1:.*\bcalm\b",
                                 "the caster's own calm stopped the wave")
                # The caster, already calm, is passed over and told so.
                self.assertIn("A wave of calm passes over the room", reply)

                # SEAL takes the short diagonals.
                self.assertIn("There is no exit in that direction",
                              staff.sync("seal ne"))
                self.assertNotIn("Invalid direction", staff.sync("seal sw"))
                self.assertIn("Exit sealed.", staff.sync("seal n"))
                self.assertIn("Exit unsealed.", staff.sync("seal n"))

    def test_mud_school_and_the_free_guild(self) -> None:
        with LiveMud(fixtures=True) as mud:
            self.make(mud, Zskstaff={"Levl": 70}, Zsknewb={"Levl": 8},
                      Zskbig={"Levl": 11},
                      Zskguild={"Levl": 5, "NewPlat": 0, "NewGold": 100,
                                "NewSilv": 0, "NewCopp": 0})

            # Mud School: a level 8 walks in, a level 11 is told why not.
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as newb, \
                    mud.connect(timeout=120) as big:
                login(staff, "Zskstaff", PASSWORD)
                login(newb, "Zsknewb", PASSWORD)
                login(big, "Zskbig", PASSWORD)
                for who in ("zsknewb", "zskbig"):
                    staff.must("transfer %s %d" % (who, SCHOOL_DOORSTEP), "Ok.")
                    self.assertEqual(room_of(staff, who), SCHOOL_DOORSTEP)
                newb.sync("north")
                self.assertEqual(room_of(staff, "zsknewb"), SCHOOL_FIRST)
                reply = big.sync("north")
                self.assertIn("Mud School is for newbies only", reply)
                self.assertEqual(room_of(staff, "zskbig"), SCHOOL_DOORSTEP)

            # The automatic guild join at level 6 is free.
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as joiner:
                login(staff, "Zskstaff", PASSWORD)
                login(joiner, "Zskguild", PASSWORD)
                before = carried_copper(joiner)
                self.assertEqual(before, 100 * 10000)
                # ADVANCE wants its target in the room.
                staff.sync("goto %d" % TEMPLE)
                self.assertEqual(room_of(staff, "zskguild"), TEMPLE)
                staff.sync("advance zskguild 6")
                joiner.drain(2.0)
                self.assertIn("ask nothing for it", joiner.transcript)
                self.assertNotIn("take some gold", joiner.transcript)
                self.assertEqual(carried_copper(joiner), before)
                joiner.sync("save")
                text = (mud.player_dir / "Zskguild").read_text(encoding="latin-1")
                cla = re.search(r"^Cla\s+(\d+)", text, re.M)
                gui = re.search(r"^Gui\s+(-?\d+)", text, re.M)
                self.assertIsNotNone(cla)
                self.assertIsNotNone(gui)
                self.assertEqual(gui.group(1), cla.group(1))


if __name__ == "__main__":
    unittest.main()

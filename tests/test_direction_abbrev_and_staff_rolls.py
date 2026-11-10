"""Directions shorten, and staff never miss a skill's roll (owner, 2026-11-10).

1. "i don't like that directions don't allow shortening. op wes doesn't
   work for open west, etc. directions like that should be prioritized."
   door_direction_word() in act_move.c now takes ne/nw/se/sw or any start
   of a direction's name, the way the movement commands resolve one: the
   plain directions come first in dir_name, so "no" is north and "so"
   south. find_door() and every other command that reads a typed
   direction (LOOK, RUN, SHOVE, LISTEN, PROJECT, GKICK, a TAR_EXIT cast)
   ask it, and OPEN, CLOSE, LOCK, UNLOCK, PICK and SEARCH take a
   direction that has a visible door as that door before any object whose
   name it also begins.

2. "immortals should never fail picking a lock or stealing or any skills
   that are chance (except things like fatality)." skill_roll_sure() in
   handler.c -- staff by level, never by trust (owner, 2026-11-10: a
   trusted character below an immortal's level rolls like anyone), a
   mobile only while staff are switched into it -- and its two wrappers, skill_roll_landed() and
   skill_roll_missed(), carry each skill command's own roll; refusals,
   fatality and other instant kills, victims' saving throws and combat's
   hit/parry/dodge rolls never go through them.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (LiveMud, create_character, login, patch_player_file,
                      place_sparring_guard, skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zdirpass1"

# tests/fixtures/area/ztestfix.are (LiveMud(fixtures=True)).
LOCK_ROOM = 32709      # a south door to BEYOND_LOCK, closed and locked by a
BEYOND_LOCK = 32710    # reset; it picks, and FIXTURE_KEY locks it again
FIXTURE_KEY = 32709
FIXTURE_SACK = 32710   # a closed container whose name begins with "s"

PICK_FUMBLES = ("tumblers drop back", "skitters out", "the lock holds",
                "lose them again", "Not this time")
STEAL_FUMBLES = ("close on nothing", "comes away empty", "fumble the lift",
                 "closes on your wrist")


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


def function_body(text: str, start: str) -> str:
    """From `start` to the brace that closes it, at the start of a line
    (do_track's carries a comment after it)."""
    body = text[text.index(start):]
    end = re.search(r"\n}", body)
    return body[:end.start()] if end else body


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


class DirectionSourceTests(unittest.TestCase):
    def test_one_resolver_reads_any_start_of_a_name(self) -> None:
        move = source("act_move.c")
        resolver = function_body(move, "int door_direction_word(")
        self.assertIn("str_prefix( arg, dir_name[door] )", resolver)
        self.assertIn('"ne", "nw", "se", "sw"', resolver)
        self.assertIn("arg[0] == '\\0'", resolver, "an empty word names no direction")
        # The plain directions come first, so a shared start is the plain one.
        self.assertIn('"north", "east", "south", "west", "up", "down",\n'
                      '    "northeast", "northwest", "southeast", "southwest"', move)

    def test_no_command_keeps_its_own_whole_word_table(self) -> None:
        chain = re.compile(r'str_cmp\(\s*\w+,\s*"(north|south|east|west)"\s*\)')
        for name in ("act_move.c", "act_info.c", "act_wiz.c", "magic.c", "magic2.c"):
            with self.subTest(file=name):
                self.assertIsNone(chain.search(source(name)))
        for name, start in (("act_move.c", "void do_look("),
                            ("act_move.c", "void do_run("),
                            ("act_move.c", "do_shove( CHAR_DATA *ch"),
                            ("act_move.c", "int find_door("),
                            ("act_info.c", "void do_listen("),
                            ("magic2.c", "void do_project("),
                            ("act_wiz.c", "void do_gkick("),
                            ("magic.c", "void do_cast(")):
            with self.subTest(command=start):
                self.assertIn("door_direction_word(", function_body(source(name), start))

    def test_a_direction_with_a_door_comes_before_an_object(self) -> None:
        move = source("act_move.c")
        for start in ("void do_open(", "void do_close(", "void do_lock(",
                      "void do_unlock(", "void do_pick(", "void do_search("):
            with self.subTest(command=start):
                body = function_body(move, start)
                self.assertLess(body.index("!door_word_names_door( ch, arg )"),
                                body.index("get_obj_here( ch, arg )"))
        names = function_body(move, "static bool door_word_names_door(")
        self.assertIn("EX_ISDOOR", names)
        self.assertIn("!IS_SET(pexit->exit_info, EX_SECRET)", names,
                      "a secret door is never found by its direction")


class StaffRollSourceTests(unittest.TestCase):
    def test_the_helper_asks_level_and_lets_no_mobile_through(self) -> None:
        sure = function_body(source("handler.c"), "bool skill_roll_sure(")
        self.assertIn("who->level >= LEVEL_IMMORTAL", sure)
        self.assertNotIn("IS_TRUSTED", sure)
        self.assertIn("ch->desc->original == NULL", sure)

    def test_every_skill_roll_goes_through_it(self) -> None:
        covered = {
            "act_move.c": ("static bool pick_lock_roll_fails(", "void do_doorbash(",
                           "void do_sneak(", "void recheck_sneak(", "void do_shadowmeld(",
                           "void do_hide(", "static void recall_travel(",
                           "do_shove( CHAR_DATA *ch", "void do_search(", "void do_ride(",
                           "void do_stealth(", "void do_sleep("),
            "act_info.c": ("void show_char_to_char_1(", "void do_listen("),
            "act_obj.c": ("void get_obj(", "void do_put(", "void do_recite(",
                          "void do_brandish(", "void do_zap(", "void do_steal("),
            "hunt.c": ("void do_danger_sense(", "void do_track("),
            "fight.c": ("void do_berserk(", "void do_bash(", "void do_dirt(", "void do_trip(",
                        "void do_smite(", "void do_backstab(", "void do_flee(",
                        "void do_rescue(", "void do_kick(", "void do_disarm(",
                        "void do_shoot(", "void do_steel_fist(", "void do_crane_dance(",
                        "void do_nerve_damage(", "void do_blinding_fists(",
                        "void do_fists_of_fury(", "void do_stunning_blow(",
                        "void do_iron_skin("),
            "magic.c": ("void do_cast(",),
            "magic2.c": ("void do_lore(", "void do_project(", "void do_mindleech(",
                         "void do_enervate(", "void do_mindblast(", "void do_nightmare(",
                         "void do_astral_walk(", "void do_telekinesis(", "void do_confuse(",
                         "void do_clairvoyance(", "void do_pyrotechnics", "void do_ego_whip(",
                         "void do_psionic_armor(", "void do_psychic_shield(",
                         "void do_mindbar(", "void do_torment(", "void do_transfusion(",
                         "void do_shift(", "void do_brew(", "void do_concoct(",
                         "void do_scribe("),
        }
        for name, starts in covered.items():
            text = source(name)
            for start in starts:
                with self.subTest(function=start):
                    self.assertRegex(function_body(text, start), r"skill_roll_(landed|missed|sure)\(")

    def test_fatality_and_saves_are_left_to_the_dice(self) -> None:
        backstab = function_body(source("fight.c"), "void do_backstab(")
        fatal = backstab.index("fatality(ch,victim);")
        self.assertIn("if ((chance >= number_percent()) && chance !=0)", backstab)
        self.assertNotIn("skill_roll_", backstab[:fatal])
        magic = source("magic.c")
        for start in ("bool saves_spell(", "bool saves_dispel("):
            with self.subTest(function=start):
                self.assertNotIn("skill_roll_", function_body(magic, start))
        fight = source("fight.c")
        for start in ("bool check_parry(", "bool check_dodge(", "bool check_shield_block(",
                      "void one_hit(", "bool check_aggrostab("):
            with self.subTest(function=start):
                self.assertNotIn("skill_roll_", function_body(fight, start))

    def test_a_pickproof_lock_still_refuses_before_the_roll(self) -> None:
        body = function_body(source("act_move.c"), "void do_pick(")
        for flag in ("CONT_PICKPROOF", "EX_PICKPROOF", "EX_WIZLOCKED"):
            with self.subTest(flag=flag):
                at = body.index(flag)
                self.assertLess(at, body.index("pick_lock_roll_fails( ch )", at))
        roll = function_body(source("act_move.c"), "static bool pick_lock_roll_fails(")
        self.assertIn("skill_roll_missed( ch, number_percent( ) > "
                      "ch->pcdata->learned[gsn_pick_lock] )", roll)


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_shortened_directions_and_rolls_staff_never_miss(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zdirstaff", Levl=70, Room=LOCK_ROOM)
            # A builder trusted to staff rank at a mortal level rolls like
            # anyone (owner, 2026-11-10): level, not trust, never misses.
            make(mud, "Zdirbuild", Levl=30, Tru=65, Room=LOCK_ROOM)
            make(mud, "Zdirthief", Levl=30, Cla=2, Room=LOCK_ROOM)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as build, \
                    mud.connect(timeout=120) as thief:
                for client, name in ((staff, "Zdirstaff"), (build, "Zdirbuild"),
                                     (thief, "Zdirthief")):
                    login(client, name, PW)
                    client.sync("scroll 0")
                for name in ("zdirstaff", "zdirbuild", "zdirthief"):
                    for skill in ("'pick lock'", "steal"):
                        staff.must(f"set skill {name} {skill} 0", "set to", "is now")

                # LOOK by any start of the name, and the door is the reset's.
                for word in ("so", "sou", "s", "south"):
                    looked = thief.sync(f"look {word}")
                    self.assertIn("A plain wooden door.", looked, (word, looked))
                    self.assertIn("The door is closed.", looked, (word, looked))
                self.assertIn("Nothing special there.", thief.sync("look wes"))
                self.assertIn("You do not see that here.", thief.sync("look sideways"))

                # OP WES's shape: the door answers, not "I see no sou here".
                for line in ("op so", "open sou", "op s"):
                    said = thief.sync(line)
                    self.assertIn("It's locked.", said, (line, said))
                    self.assertNotIn("I see no", said, (line, said))
                self.assertIn("You lack the key.", thief.sync("unlock so"))
                self.assertIn("I see no door", thief.sync("open wes"),
                              "a direction with no exit says so")

                # A mortal at 0% misses, said as a fumble, and nothing opens.
                picked = thief.sync("pick sou", timeout=60)
                self.assertTrue(any(f in picked for f in PICK_FUMBLES), picked)
                self.assertNotIn("*Click*", picked)

                # Staff at 0% never miss: ten picks, ten clicks.
                staff.must(f"load obj {FIXTURE_KEY}", "You create")
                for attempt in range(10):
                    picked = staff.sync("pick so")
                    self.assertIn("*Click*", picked, (attempt, picked))
                    self.assertFalse(any(f in picked for f in PICK_FUMBLES), picked)
                    staff.must("lock s", "*Click*", "already locked")
                # ...but a trusted builder at level 30 fumbles like a mortal.
                picked = build.sync("pick sout", timeout=60)
                self.assertTrue(any(f in picked for f in PICK_FUMBLES), picked)
                self.assertNotIn("*Click*", picked)

                # A direction with a door is the door, before the sack in the
                # pack whose name it also begins.
                staff.must(f"load obj {FIXTURE_SACK}", "You create")
                staff.must("give sack zdirthief", "You give")
                staff.must("unlock s", "*Click*", "already unlocked")
                said = thief.sync("op s")
                # A reset may have locked it again between the two; either
                # way it is the door that answered.
                self.assertTrue("Ok." in said or "It's locked." in said, said)
                self.assertNotIn("sack", said, said)
                self.assertIn("Ok.", thief.sync("open sack"), "the sack was still closed")
                thief.sync("close s")

                # STEAL: staff at 0% lift the key every time.
                place_sparring_guard(staff, "Zdirstaff", LOCK_ROOM)
                staff.must("give key sparring", "You give")
                for attempt in range(10):
                    stolen = staff.sync("steal key sparring")
                    self.assertIn("You steal", stolen, (attempt, stolen))
                    staff.must("give key sparring", "You give")
                # A mortal at 0% fumbles.
                stolen = thief.sync("steal key sparring", timeout=60)
                self.assertTrue(any(f in stolen for f in STEAL_FUMBLES), stolen)
                self.assertNotIn("You steal", stolen)
                staff.sync("peace")


if __name__ == "__main__":
    unittest.main()

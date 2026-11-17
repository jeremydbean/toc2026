"""The creator's dice (owner, 2026-11-17).

FATE <player> MISRECALL [room] | EMERGENCY | RUSH | MAP | CLEAR, DISASTER
<kind> AREA <area> and DISASTER <kind> <player> (a sure strike), and
GRANTPSI, are the creator's alone: an implementor is answered "Huh?" (or,
for DISASTER, told aiming is the creator's). A fated misrecall throws the
next prayer into the named room; a fated rush is the next quest's
contract; a sure earthquake lands with no saving throw and never kills; a
sandstorm in a room with no desert is refused with the kinds that would
reach; a fated map comes out of the next kill's corpse. A clover's luck is
read by the rolls it is meant to bend (source).

Synthetic characters in a throwaway world: the creator is a synthetic
Killuminati, as test_creator_rank's is.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    place_sparring_guard,
    room_of,
    skip_reason,
)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zluckpass1"
QUIET_ROOM = 32703          # fixture: not safe, nothing walks in
HALL_OF_HEROES = 4649
QUESTMASTER = 2497
MAP_ROOM = 5905             # a grassy clearing in an area a map can come from


def make(mud, name, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CreatorLuckTests(unittest.TestCase):
    def test_fate_and_aimed_disasters(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Killuminati", Levl=70, Room=4207)
            make(mud, "Zluckimpl", Levl=70, Room=4207)
            make(mud, "Zlucky", Levl=50, Room=QUIET_ROOM)
            with mud.connect(timeout=120) as god, mud.connect(timeout=120) as impl, \
                    mud.connect(timeout=120) as hero:
                login(god, "Killuminati", PW)
                login(impl, "Zluckimpl", PW)
                login(hero, "Zlucky", PW)

                # An implementor has none of it.
                self.assertIn("Huh?", impl.sync("fate zlucky"))
                self.assertIn("Huh?", impl.sync("grantpsi zlucky level"))
                self.assertIn("creator's alone", impl.sync("disaster earthquake zlucky"))
                self.assertIn("creator's alone", impl.sync("disaster flood area ztestfix"))

                self.assertIn("Nothing: their dice", god.sync("fate zlucky"))
                self.assertIn("next time they gain a level", god.sync("grantpsi zlucky level"))

                # A fated misrecall, into the named room.
                self.assertIn("No room has that vnum", god.sync("fate zlucky misrecall 999999"))
                god.must("fate zlucky misrecall %d" % HALL_OF_HEROES, "will misfire")
                self.assertIn("room %d" % HALL_OF_HEROES, god.sync("fate zlucky"))
                said = hero.sync("recall")
                self.assertIn("Something is very wrong", said, said)
                self.assertEqual(room_of(god, "zlucky"), HALL_OF_HEROES)
                self.assertIn("Nothing: their dice", god.sync("fate zlucky"))
                log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")
                self.assertIn("Fate: Killuminati fated Zlucky a misfired recall into room 4649.", log)
                self.assertIn("Fate: Zlucky's recall misfired as fated.", log)

                # A sure strike, and a kind the room rules out.
                god.must("transfer zlucky %d" % QUIET_ROOM, "")
                hero.sync("look")
                said = god.sync("disaster sandstorm zlucky")
                self.assertIn("cannot reach them", said, said)
                self.assertIn("earthquake", said.split("Kinds that would:", 1)[1], said)
                mark = len(hero.transcript)
                god.must("disaster earthquake zlucky", "struck Zlucky")
                hero.sync("look")
                felt = hero.transcript[mark:]
                self.assertIn("The earth heaves under your feet", felt, felt)
                self.assertNotIn("keep your footing", felt, felt)
                self.assertNotIn("DEAD", felt)

                # An area struck from afar.
                said = god.sync("disaster flood area ztestfix")
                self.assertIn("strikes", said, said)
                self.assertIn("next cycle", said, said)
                god.sync("goto %d" % QUIET_ROOM)
                god.sync("disaster stop")
                god.sync("goto 4207")

                # A fated rush is the next quest's contract.
                god.must("fate zlucky rush", "rush contract")
                god.must("transfer zlucky %d" % QUESTMASTER, "")
                said = hero.sync("aquest request", timeout=60)
                self.assertIn("RUSH CONTRACT", said, said)
                self.assertNotIn("rush contract", god.sync("fate zlucky"))
                hero.sync("aquest abort")

                # A fated map, out of the next kill's corpse.
                god.must("fate zlucky map", "drops its area's map")
                god.must("transfer zlucky %d" % MAP_ROOM, "")
                place_sparring_guard(god, "Killuminati", MAP_ROOM)
                # A guard of one hit point: the kill is what is being tested.
                god.must("set char sparring hp 1", "now set to 1")
                god.sync("restore sparring")
                self.assertIn("1/1", god.sync("stat mob sparring"))
                god.sync("goto 4207")
                hero.sync("stand")                 # the earthquake knocked them down
                hero.send("kill sparring")
                hero.expect("is DEAD", timeout=180)
                # The fixture may sacrifice the corpse on its own (AUTOSAC):
                # the log line is written only once the map is in it.
                hero.sync("look")
                self.assertIn("Nothing: their dice", god.sync("fate zlucky"))
                log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")
                self.assertIn("Fate: Zlucky's kill dropped its area's map, as fated.", log)

                self.assertIn("Nobody playing", god.sync("fate znobody rush"))
                god.must("fate zlucky emergency", "emergency contract")
                god.must("fate zlucky clear", "Nothing is fated")


class CreatorLuckSourceTests(unittest.TestCase):
    def test_commands_are_the_creators(self) -> None:
        interp = (ROOT / "src" / "interp.c").read_text(encoding="utf-8")
        for name in ("fate", "grantpsi"):
            row = re.search(r'\{\s*"%s",[^}]*\}' % name, interp).group(0)
            self.assertRegex(row, r",\s*CR,", name)
        disaster = (ROOT / "src" / "disaster.c").read_text(encoding="latin-1")
        self.assertIn("get_trust( ch ) < LEVEL_CREATOR", disaster)
        # A fated misrecall may name a death trap (owner, 2026-11-17): the
        # creator is warned, never refused.
        fate = (ROOT / "src" / "fate.c").read_text(encoding="latin-1")
        self.assertIn("the misfire will kill them", fate)
        self.assertNotIn("a misfire is not a death", fate)

    def test_clover_luck_bends_the_rolls(self) -> None:
        reads = {
            "quest.c": "CLOVER_RUSH_STEP * luck",
            "goblin.c": "CLOVER_RARE_STEP * clover_luck( ch )",
            "disaster.c": "CLOVER_RARE_STEP * clover_luck( ch )",
            "special.c": "CLOVER_HERBIE_STEP * clover_luck( most_hurt )",
            "fight.c": "map_corpse_drop_lucky( corpse, victim, kill_luck )",
            "magic2.c": "CLOVER_FARSLAY_STEP * ( clover_luck( ch ) - clover_luck( victim ) )",
            "act_move.c": "5 - CLOVER_RECALL_STEP * clover_luck( ch )",
        }
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        self.assertIn("CLOVER_FATALITY_STEP", fight)
        disaster = (ROOT / "src" / "disaster.c").read_text(encoding="latin-1")
        self.assertEqual(disaster.count("CLOVER_DISASTER_STEP * clover_luck( vch )"), 2)
        # A fated misrecall misfires whatever luck the player holds.
        act_move = (ROOT / "src" / "act_move.c").read_text(encoding="latin-1")
        self.assertEqual(act_move.count("(fated || chance < recall_misfire_odds(ch)) && !sure"), 2)
        for name, needle in reads.items():
            self.assertIn(needle, (ROOT / "src" / name).read_text(encoding="latin-1"), name)
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        # Read before the pot of gold spends a point of it.
        self.assertLess(fight.index("kill_luck = clover_luck( ch );"),
                        fight.index("holiday_kill( ch, victim );"))

    def test_no_public_change_entry(self) -> None:
        changes = (ROOT / "area" / "changes.dat").read_text(encoding="latin-1")
        self.assertNotRegex(changes, r"(?im)^.*\bFATE\b")


if __name__ == "__main__":
    unittest.main()

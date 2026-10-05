"""Portal and astral walk may leave a no-recall room but never enter one.

The owner's rule, 2026-10-03: ROOM_NO_RECALL keeps people *out* of a place
through these two, and does not trap them *in* it; ROOM_JAIL stops both
directions. Portal already behaved that way -- its caster side asked only
about jail -- and astral walk refused its own origin as well, so the two
psionic and arcane ways of travelling disagreed. Gate, summon, teleport,
shift, earth travel and word of recall are untouched and keep no-recall on
both sides.
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
    skip_reason,
)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()


def function_body(source: str, signature: str) -> str:
    start = source.index(signature)
    return source[start:source.index("\n}\n", start)]


class TravelSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.magic = (ROOT / "src" / "magic.c").read_text(encoding="latin-1")
        cls.magic2 = (ROOT / "src" / "magic2.c").read_text(encoding="latin-1")

    def travel_target(self) -> str:
        # Gate, earth travel, portal and astral walk all choose their
        # target through travel_target() since 2026-10-04; the room rules
        # live there, told apart by mode.
        return function_body(self.magic, "CHAR_DATA *travel_target(")

    def test_portal_leaves_a_no_recall_room_but_never_enters_one(self) -> None:
        portal = self.magic[self.magic.index("void spell_portal("):]
        portal = portal[:portal.index("spell_iportal")]
        self.assertIn("travel_target( ch, target_name, level, TRAVEL_PORTAL )", portal)
        check = self.travel_target()
        # The caster's room: jail for every mode, no-recall for gate only.
        self.assertIn(
            "if ( ch->in_room == NULL || IS_SET(ch->in_room->room_flags, ROOM_JAIL) )", check)
        self.assertIn(
            "if ( mode == TRAVEL_GATE && IS_SET(ch->in_room->room_flags, ROOM_NO_RECALL) )",
            check)
        self.assertEqual(1, check.count("ch->in_room->room_flags, ROOM_NO_RECALL"))
        # The target's room: both, for every mode.
        self.assertIn("IS_SET(room->room_flags, ROOM_NO_RECALL)", check)
        self.assertIn("IS_SET(room->room_flags, ROOM_JAIL)", check)

    def test_astral_walk_leaves_a_no_recall_room_but_never_enters_one(self) -> None:
        body = function_body(self.magic2, "void do_astral_walk(")
        self.assertIn("travel_target( ch, arg, ch->level, TRAVEL_ASTRAL )", body)
        check = self.travel_target()
        origin = re.search(
            r"mode == TRAVEL_ASTRAL\s*&&\s*psionic_remote_room_blocked\(\s*ch,\s*ch->in_room,"
            r"\s*(\w+),\s*(\w+)\s*\)", check)
        target = re.search(
            r"mode == TRAVEL_ASTRAL\s*&&\s*psionic_remote_room_blocked\(\s*ch,\s*room,"
            r"\s*(\w+),\s*(\w+)\s*\)", check)
        self.assertIsNotNone(origin)
        self.assertIsNotNone(target)
        self.assertEqual("false", origin.group(2), "origin must not block no-recall")
        self.assertEqual("true", target.group(2), "destination must block no-recall")

    def test_jail_still_stops_the_helper_both_ways(self) -> None:
        helper = function_body(self.magic2, "bool psionic_remote_room_blocked(")
        unconditional = helper[:helper.index("if ( block_safe")]
        self.assertIn("ROOM_JAIL", unconditional)

    def test_the_others_keep_no_recall_on_the_caster_side(self) -> None:
        self.assertIn("travel_target( ch, target_name, level, TRAVEL_GATE )",
                      function_body(self.magic, "void spell_gate("))
        self.assertIn("travel_target( ch, target_name, level, TRAVEL_GATE )",
                      function_body(self.magic2, "void spell_earth_travel("))
        self.assertIn(
            "mode == TRAVEL_GATE && IS_SET(ch->in_room->room_flags, ROOM_NO_RECALL)",
            self.travel_target())
        self.assertIn("IS_SET(ch->in_room->room_flags, ROOM_NO_RECALL)",
                      function_body(self.magic, "void spell_summon("))
        shift = function_body(self.magic2, "void do_shift(")
        self.assertRegex(
            shift, r"psionic_remote_room_blocked\(ch, ch->in_room, false, true\)")


PASSWORD = "Zastralpw12"
NO_RECALL_ORIGIN = 5905     # A grassy clearing, mid_ruin.are: flags N only
NO_RECALL_TARGET = 5900     # Along the Midgaard river: flags N only
ORDINARY_TARGET = 2401      # Center of Oak Tree Square: no flags


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def give_skill(mud: LiveMud, name: str, skill: str, percent: int) -> None:
    path = mud.player_dir / name
    lines = path.read_text(encoding="latin-1").split("\n")
    at = next(i for i, line in enumerate(lines) if line.startswith("Sk "))
    lines.insert(at, "Sk %d '%s'" % (percent, skill))
    path.write_text("\n".join(lines), encoding="latin-1", newline="")


@unittest.skipIf(SKIP is not None, SKIP or "")
class AstralWalkLiveTests(unittest.TestCase):
    def test_out_of_a_no_recall_room_yes_into_one_no(self) -> None:
        with LiveMud() as mud:
            for name, room in (("Zastralwk", NO_RECALL_ORIGIN),
                               ("Zastralin", NO_RECALL_TARGET),
                               ("Zastralto", ORDINARY_TARGET)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=30, Room=room,
                                  HpManaMove="300 300 900 900 300 300")
            give_skill(mud, "Zastralwk", "astral walk", 100)

            with mud.connect(timeout=120) as walker, \
                 mud.connect(timeout=120) as kept_out, \
                 mud.connect(timeout=120) as open_target:
                login(walker, "Zastralwk", PASSWORD)
                login(kept_out, "Zastralin", PASSWORD)
                login(open_target, "Zastralto", PASSWORD)
                # New characters refuse summoning; both targets must allow
                # it, so a refusal can only be the room's doing.
                for target in (kept_out, open_target):
                    self.assertIn("no longer immune", run(target, "nosummon"))

                # The command is ASTRAL <target>: "astral walk x" takes
                # "walk" for the target and is refused for that instead.
                refused = run(walker, "astral zastralin", 2.5)
                self.assertIn("cannot find a safe astral path", refused, refused)

                went = run(walker, "astral zastralto", 3.0)
                self.assertNotIn("cannot find a safe astral path", went, went)
                self.assertIn("Oak Tree Square", went, went)


if __name__ == "__main__":
    unittest.main()

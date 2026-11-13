"""A dungeon's gate counts what lies in the player's own corpse.

Bug report, 2026-11-12: Trentlin died in Level 5 carrying his Triforce
pieces, and every dungeon entrance then asked for a piece that lay in his
own corpse inside -- the only way back to it. hyrule_gate_check now asks
hyrule_holds_for_gate: carried, or in the character's own corpse
(ITEM_CORPSE_PC, owner by name), anywhere it lies. Nobody else's corpse
counts. Synthetic Z characters in a disposable world.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, room_of, skip_reason

SKIP = skip_reason()
PW = "Zgatepass1"
MOON_GATE = 30276        # overworld; DOWN leads into Level 2's entrance
MOON_ENTRANCE = 30418    # Level 2's seal asks for the first piece
FIRST_PIECE = 30400
SIGHT = 512              # infravision: Hyrule's rooms may be dark
SEAL = "seal shaped like the Triforce"


def make(mud: LiveMud, name: str, objects: str = "", **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)
    if objects:
        path = mud.player_dir / name
        text = path.read_text(encoding="latin-1")
        path.write_text(text.replace("#END", objects + "#END", 1), encoding="latin-1")


def carried(vnum: int) -> str:
    return "#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 100\nEnd\n\n" % vnum


@unittest.skipIf(SKIP is not None, SKIP or "")
class OwnCorpseGateTests(unittest.TestCase):
    def test_a_piece_in_your_own_corpse_opens_the_seal(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zgatestaff", Levl=70, Room=4207)
            make(mud, "Zgatedead", Levl=30, Room=4207, AfBy=SIGHT,
                 objects=carried(FIRST_PIECE))
            make(mud, "Zgatenone", Levl=30, Room=4207, AfBy=SIGHT)
            with mud.connect(timeout=120) as staff, \
                    mud.connect(timeout=120) as dead, \
                    mud.connect(timeout=120) as none:
                login(staff, "Zgatestaff", PW)
                login(dead, "Zgatedead", PW)
                login(none, "Zgatenone", PW)
                staff.must(f"transfer zgatedead {MOON_GATE}", "")
                staff.must(f"goto {MOON_GATE}", "")
                staff.must("slay zgatedead", "")
                dead.drain(2.0)
                # Their corpse, holding the piece, lies at the gate; they
                # stand in the death room with nothing.
                inventory = dead.sync("inventory", timeout=60)
                staff.must(f"transfer zgatedead {MOON_GATE}", "")
                staff.must(f"transfer zgatenone {MOON_GATE}", "")
                staff.must("goto 4207", "")
                dead.sync("stand", timeout=60)          # a death leaves one resting
                none.sync("stand", timeout=60)
                went = dead.sync("down", timeout=60)
                dead_room = room_of(staff, "zgatedead")
                refused = none.sync("down", timeout=60)
                none_room = room_of(staff, "zgatenone")
                for client in (dead, none, staff):
                    client.send("quit")
                    client.wait_closed()
        self.assertNotIn("Triforce", inventory, inventory)
        self.assertNotIn(SEAL, went, went)
        self.assertEqual(MOON_ENTRANCE, dead_room, went)
        # Somebody else's corpse is no key: the one who never held a piece
        # is still refused, with the corpse lying beside them.
        self.assertIn(SEAL, refused, refused)
        self.assertEqual(MOON_GATE, none_room, refused)


class NoDropNamesTheItemTests(unittest.TestCase):
    """The same evening's other report: DROP GEAR answered "You can't let
    go of it." about a Hyrule piece (every one carries the keyword gear),
    not the remort pack the player meant. A refusal names what it found."""

    def test_every_nodrop_refusal_names_the_object(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for name in ("act_obj.c", "special.c"):
            text = (root / "src" / name).read_text(encoding="latin-1")
            self.assertNotIn("You can't let go of it.", text, name)
            self.assertIn('act( "You can\'t let go of $p.", ch, obj, NULL, TO_CHAR );', text, name)


if __name__ == "__main__":
    unittest.main()

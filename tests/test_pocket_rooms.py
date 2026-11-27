"""HAVEN and ROPE TRICK's pocket rooms, made and ended (review, 2026-11-27).

* Both spells allocated the room before looking for a free vnum (a failed
  search leaked it), and HAVEN hung the way back on the caster's room --
  the room the group left, when the caster was not pulled in.
* extract_room cleared the pocket's down exit without freeing it.
* When the pocket ended, everything on its floor was destroyed: a player's
  dropped gear, a tracked player corpse with all it held. Now it goes out
  with the people, to the room they came from.

TOC_TICK_PULSES and TOC_POCKET_TICKS (test-only) play the ticks through in
seconds. Synthetic characters only; test_pocket_rooms runs under the
sanitizers in CI too.
"""
from __future__ import annotations

import pathlib
import re
import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PW = "Zpocketpw1"
TEMPLE = 4207
SQUARE = 2401           # outdoors, not safe: pockets may be made here


def make(mud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def wait_for(client, text: str, seconds: float) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        client.drain(1.0)
        if text in client.transcript:
            return True
    return False


@unittest.skipIf(SKIP is not None, SKIP or "")
class PocketRoomTests(unittest.TestCase):
    def test_occupants_an_idle_player_and_the_floor_all_come_out(self) -> None:
        """A group in a HAVEN: one stays at the keyboard, one loses the link
        and sits idle in the pocket (linkdead, as a player whose connection
        dropped), and a sword lies on the floor. When it ends all of them
        are in the square they came from, and the idle one logs back in
        there. (A player idle at the keyboard is moved to the void and then
        quit by the limbo sweep within a few ticks -- room_aff_update points
        a void return at the way out, which test_edge_cases_oct4 holds.)"""
        env = {"TOC_TICK_PULSES": "8", "TOC_POCKET_TICKS": "12"}
        with LiveMud(extra_env=env) as mud:
            make(mud, "Zkeeper", Levl=70, Room=TEMPLE)
            for name in ("Zcaster", "Zmember", "Zlinker"):
                # Mages: ROPE TRICK at 31, HAVEN at 44 (src/const.c).
                make(mud, name, Levl=45, Cla=0, Room=SQUARE, HMV="3000 3000 30000 30000 1000 1000",
                     HMVP="3000 30000 1000")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as caster, \
                    mud.connect(timeout=120) as member:
                linker = mud.connect(timeout=120)
                login(staff, "Zkeeper", PW)
                for client, name in ((caster, "Zcaster"), (member, "Zmember"), (linker, "Zlinker")):
                    login(client, name, PW)
                    client.sync("scroll 0")
                staff.sync("holylight")
                staff.must("set skill zcaster haven 100", "")
                staff.sync(f"goto {SQUARE}")
                staff.must("load obj 3022", "You create")         # a long sword
                staff.must("give sword zcaster", "You give")
                staff.sync(f"goto {TEMPLE}")
                member.sync("follow zcaster")
                linker.sync("follow zcaster")
                caster.sync("group zmember")
                caster.sync("group zlinker")

                cast = caster.sync("cast haven", timeout=30)
                self.assertIn("pocket dimension", cast, cast)
                here = caster.sync("look")
                self.assertIn("Zmember", here)
                self.assertIn("Zlinker", here)
                # The way back is the pocket's own exit, DOWN (it was hung on
                # the caster's room before -- the square, had the caster
                # stayed behind).
                self.assertIn("[Exits: down]", here)
                caster.sync("drop sword")
                linker.close()                    # linkdead, idle, in the pocket

                self.assertTrue(wait_for(caster, "expelled from the room", 60),
                                caster.transcript[-600:])
                square = staff.sync(f"at {SQUARE} look")
                for who in ("Zcaster", "Zmember", "Zlinker"):
                    self.assertIn(who, square, f"{who} came out to the square")
                self.assertIn("long sword", square, "what lay on the floor came out too")
                self.assertIn("Oak Tree", member.sync("look"))
                # The idle one logs back in where the pocket put them.
                with mud.connect(timeout=120) as back:
                    login(back, "Zlinker", PW)
                    self.assertIn("Oak Tree", back.sync("look"))
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertNotIn("Room_Aff", log)

    def test_many_pockets_made_and_ended(self) -> None:
        """Repeated ROPE TRICK casts, each ending on the next tick: under the
        sanitizers this is the leak and use-after-free check (CI)."""
        env = {"TOC_TICK_PULSES": "8", "TOC_POCKET_TICKS": "1"}
        with LiveMud(extra_env=env) as mud:
            make(mud, "Zkeeper", Levl=70, Room=TEMPLE)
            make(mud, "Zroper", Levl=45, Cla=0, Room=SQUARE, HMV="3000 3000 30000 30000 1000 1000",
                 HMVP="3000 30000 1000")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as roper:
                login(staff, "Zkeeper", PW)
                login(roper, "Zroper", PW)
                staff.must("set skill zroper 'rope trick' 100", "")
                made = 0
                for _ in range(6):
                    staff.sync("restore zroper")
                    said = roper.sync("cast 'rope trick'", timeout=30)
                    if "climb up it" not in said:
                        continue
                    made += 1
                    self.assertTrue(wait_for(roper, "expelled from the room", 20),
                                    roper.transcript[-600:])
                    roper.transcript = ""
                self.assertGreaterEqual(made, 4, "most casts made a pocket")
                self.assertIn("Oak Tree", roper.sync("look"))


class PocketRoomSourceTests(unittest.TestCase):
    def test_the_vnum_first_the_exit_owned_and_nothing_destroyed(self) -> None:
        magic = (ROOT / "src" / "magic2.c").read_text(encoding="latin-1")
        new = magic[magic.index("static ROOM_INDEX_DATA *pocket_room_new("):]
        new = new[:new.index("\n}\n")]
        self.assertLess(new.index("get_room_index( vnum )"), new.index("alloc_mem( sizeof(*pRoomIndex) )"))
        self.assertIn("pRoomIndex->exit[DIR_DOWN] = pexit;", new)
        for spell in ("void spell_rope_trick(", "void spell_haven("):
            body = magic[magic.index(spell):]
            body = body[:body.index("\n}\n")]
            self.assertNotIn("ch->in_room->exit[5]", body, spell)
            self.assertIn("pocket_room_new(", body, spell)
        handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        extract = handler[handler.index("void extract_room( ROOM_INDEX_DATA *pRoom )"):]
        self.assertIn("free_mem( pRoom->exit[door], sizeof(*pRoom->exit[door]) );",
                      extract[:extract.index("\n}\n")])
        update = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        expiry = update[update.index("void room_aff_update( void )"):]
        expiry = expiry[:expiry.index("\n}\n")]
        self.assertNotIn("extract_obj(obj)", expiry)
        self.assertIn("obj_to_room( obj, way_out );", expiry)


if __name__ == "__main__":
    unittest.main()

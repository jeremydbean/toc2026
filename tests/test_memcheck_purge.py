"""MEMCHECK, PURGE and the resurrection offer (review, 2026-11-11).

1. MEMCHECK named a wizinvis staff member to staff below their level: the
   self-test's event read "stale reply on Zmemhigh" to a level 60 who could
   not see Zmemhigh on WHO. Every event now keeps the trust that may read
   it -- the higher of the holder's and the dead target's notice levels --
   and MEMCHECK shows a viewer only what they may read.

2. PURGE asked get_char_world before the room's objects, so `purge corpse'
   with a player's corpse at the staff member's feet took a mobile called
   "zombie corpse" somewhere else in the world. It now looks in the room
   first (somebody, then something), then the world, and says what it
   removed and where.

3. A resurrection offer kept a pointer to its corpse after the corpse was
   purged, and the memory sweep read it there: under ASan with no
   quarantine, a heap-use-after-free in obj_is_live, from memguard.c's
   check of resurrect_corpse, whenever the sweep ran a pass after the
   purge. Extracting a corpse now forgets any offer naming it (and
   extracting a character clears a descriptor's gmcp_last_character), so
   the sweep never meets either.
"""

from __future__ import annotations

import re
import time
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason
import test_resurrection_transfer as rt

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zmempass11"
TEMPLE = 4207
SQUARE = 2401
ZOMBIE = 24209                 # "zombie corpse", crypt.are


def make(mud: LiveMud, name: str, **fields: object) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed()
    patch_player_file(mud, name, **fields)


class SourceTests(unittest.TestCase):
    def test_events_keep_the_level_that_may_read_them(self) -> None:
        guard = (ROOT / "src" / "memguard.c").read_text(encoding="latin-1")
        # staff_trust: an immortal's trust, a trusted mortal's level --
        # a mortal whose trust lets them type MEMCHECK reads no names.
        self.assertIn("staff_trust( ch ) < mg_event_level[slot]", guard)
        self.assertIn("level = UMAX( level, target_level );", guard)
        recycle = (ROOT / "src" / "recycle.c").read_text(encoding="latin-1")
        self.assertIn("pending_label_level = staff_notice_level( ch, LEVEL_IMMORTAL );", recycle)

    def test_purge_looks_here_before_the_world(self) -> None:
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        body = wiz.split("void do_purge( CHAR_DATA *ch, char *argument )", 1)[1].split("\n}\n", 1)[0]
        room = body.index("get_char_room( ch, arg )")
        obj = body.index("get_obj_here( ch, arg )")
        world = body.index("get_char_world( ch, arg )")
        self.assertLess(room, obj)
        self.assertLess(obj, world)

    def test_no_pointer_outlives_a_corpse_or_a_character(self) -> None:
        handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        self.assertEqual(handler.count("resurrect_forget_corpse( obj );"), 2)
        self.assertIn("d->gmcp_last_character = NULL;", handler)


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_memcheck_hides_a_wizinvis_name_from_lower_staff(self) -> None:
        env = {"TOC_MEMCHECK_SELFTEST": "1", "TOC_MEM_QUARANTINE_SECS": "30"}
        with LiveMud(extra_env=env) as mud:
            make(mud, "Zmemhigh", Levl=70, Room=TEMPLE)
            make(mud, "Zmemlow", Levl=60, Room=TEMPLE)
            with mud.connect(timeout=120) as high, mud.connect(timeout=120) as low:
                login(high, "Zmemhigh", PW)
                login(low, "Zmemlow", PW)
                for client in (high, low):
                    client.sync("scroll 0")
                high.sync("wizinvis 70")
                seen_before = len(low.transcript)       # logins name both
                self.assertNotIn("Zmemhigh", low.sync("who"), "hidden on WHO")

                high.must("memcheck selftest", "Self-test")
                deadline = time.monotonic() + 30
                mine = ""
                while time.monotonic() < deadline:
                    mine = high.sync("memcheck")
                    if "stale reply on Zmemhigh" in mine:
                        break
                    time.sleep(1)
                self.assertIn("stale reply on Zmemhigh", mine, "the event is kept for its own level")
                theirs = low.sync("memcheck")
                self.assertIn("Stale pointers caught since boot: 1", theirs, "counts are not names")
                self.assertNotIn("Zmemhigh", theirs)
                self.assertNotIn("Zmemhigh", low.transcript[seen_before:], "nor by WIZINFO")
                for client in (low, high):
                    client.send("quit")
                    client.wait_closed()

    def test_purge_takes_the_corpse_here_not_a_mobile_elsewhere(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zpurgestaff", Levl=70, Room=TEMPLE)
            make(mud, "Zpurgefall", Levl=20, Room=TEMPLE)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as fallen:
                login(staff, "Zpurgestaff", PW)
                login(fallen, "Zpurgefall", PW)
                staff.sync("scroll 0")
                staff.must(f"at {SQUARE} load mob {ZOMBIE}", "zombie")
                staff.must("slay zpurgefall", "")
                self.assertIn("corpse of Zpurgefall", staff.sync("look"))

                def mobiles_named_corpse() -> int:
                    # One line a mobile: "[vnum] name [room] room name".
                    return len(re.findall(r"\[\s*\d+\] .*?\[\s*\d+\]",
                                          staff.sync("mwhere corpse", timeout=60)))

                before = mobiles_named_corpse()
                self.assertGreaterEqual(before, 1, "the loaded zombie corpse is somewhere")
                reply = staff.sync("purge corpse")
                self.assertRegex(reply, r"corpse of Zpurgefall \(object \d+\) purged from this room")
                self.assertNotIn("corpse of Zpurgefall", staff.sync("look"))
                self.assertEqual(mobiles_named_corpse(), before, "no mobile elsewhere was taken")

                # With nothing here by that name, the world: said, with where.
                reply = staff.sync("purge corpse")
                self.assertRegex(reply, r"\(mobile \d+\) purged from elsewhere: room \d+")
                self.assertEqual(mobiles_named_corpse(), before - 1)
                reply = staff.sync("purge zqxnothing")
                self.assertIn("Nothing here or in the world answers to that.", reply)
                for client in (fallen, staff):
                    client.send("quit")
                    client.wait_closed()

    def test_a_purged_corpse_leaves_no_offer_behind(self) -> None:
        """The reviewer's ASan scenario: an offer, then the corpse purged.
        Under ASan with no quarantine (TOC_SERVER_BINARY, the default
        window there is 0) the old code read freed memory; in any build the
        sweep counted a stale resurrect_corpse. Now nothing is stale and
        ACCEPT finds no corpse."""
        with LiveMud(extra_env={"TOC_MEM_QUARANTINE_SECS": "0"}) as mud:
            rt.setup(mud)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as cleric, \
                    mud.connect(timeout=120) as fallen:
                for client, name in ((staff, "Zrtstaff"), (cleric, "Zrtcleric"),
                                     (fallen, "Zrtfallen")):
                    login(client, name, rt.PW)
                    client.sync("scroll 0")
                rt.kill_loot_and_call(staff, cleric, fallen)
                self.assertIn("purged", staff.sync('purge "zrtfallen corpse"'))
                time.sleep(4)                # several sweeps, a second apart
                check = staff.sync("memcheck", timeout=60)
                self.assertNotIn("resurrect_corpse", check)
                self.assertIn("Stale pointers caught since boot: 0", check)
                reply = fallen.sync("accept", timeout=60)
                self.assertNotIn("edge of life", reply, "no corpse to rise into")
                for client in (fallen, cleric, staff):
                    client.send("quit")
                    client.wait_closed()
            self.assertIsNone(mud.proc.poll(), "the game is still running")


if __name__ == "__main__":
    unittest.main()

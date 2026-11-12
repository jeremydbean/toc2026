"""A player file names one pet and a bottle one captive (review,
2026-11-12), and the genie lever opens the bottle it names.

1. Two #PET sections: fread_pet made a mobile for each and overwrote
   ch->pet, so the first stayed registered with its master pointing at
   the character. Freeing a name prompt's copy left it pointing at freed
   memory; under ASan with no quarantine the memory sweep read it
   (heap-use-after-free in char_is_live <- mg_check_char).
2. Two Trap fields in one object: char_to_obj made a second captive and
   overwrote obj->trapped, leaving the first pointing at the bottle after
   it was freed (heap-use-after-free in obj_is_live <- mg_check_char).

Both records are refused now before anything is made: the character is
refused at the name, its file is left byte for byte, and nothing is left
registered. A record that is malformed part way (a #PET, or an object
after a valid Trap) is refused too and leaves no mobile behind. One pet
and one captive load as they always did.

3. The genie lever (a manipulation, value[4] 2) read the lever's own
   captive instead of the bottle's, so pulling it beside the bottle let
   nothing out.

Run under the sanitizers with TOC_MEM_QUARANTINE_SECS=0 as well as the
default window; in an ordinary build the default window turns any stale
pointer into a MEMORY line, which this test also refuses.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (LiveMud, SPARRING_FLOOR, SPARRING_GALLERY, SPARRING_GUARD,
                      create_character, login, patch_player_file, place_sparring_guard,
                      skip_reason)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zownpass11"
TEMPLE = 4207
BOTTLE = 32711
LEVER = 32712

PET = ("#PET\nVnum %d\nName sparring guard fixture~\nSex  0\n"
       "HMV  100 100 100 100 100 100\nEnd\n\n" % SPARRING_GUARD)
PET_MALFORMED = ("#PET\nVnum %d\nName sparring guard fixture~\nSex  0\n"
                 "HMV  100 notanumber 100 100 100 100\nEnd\n\n" % SPARRING_GUARD)


def bottle(*traps: str, tail: str = "") -> str:
    return ("#O\nVnum %d\nNest 0\nWear -1\nLev 1\n%s%sCond 100\nEnd\n\n"
            % (BOTTLE, "".join("Trap %s\n" % t for t in traps), tail))


def add(mud: LiveMud, name: str, records: str) -> bytes:
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    path.write_text(text.replace("#END", records + "#END", 1), encoding="latin-1")
    return path.read_bytes()


def guard_count(staff) -> int:
    """How many sparring guards the world holds, placed or not: STAT of
    the one placed in the floor reads the prototype's count."""
    reply = staff.must("stat mob sparring", "Count:")
    found = re.search(r"Count: (\d+)", reply)
    assert found, reply
    return int(found.group(1))


def try_name(mud: LiveMud, name: str) -> str:
    """Type the name. A refused file closes the connection at once; one
    that loads reaches the password prompt and is hung up on there."""
    with mud.connect(timeout=60) as client:
        client.expect("by what name", "name:")
        client.send(name)
        said = client.expect("could not be read", "assword")
        if said != "could not be read":
            return "loaded"
        client.wait_closed()
        return "refused"


class OwnershipSourceTests(unittest.TestCase):
    def test_refused_before_anything_is_made(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        pet = save.split("void fread_pet( CHAR_DATA *ch, FILE *fp )\n{", 1)[1]
        self.assertLess(pet.index("if ( ch->pet != NULL )"), pet.index("create_mobile( index )"))
        trap = save.split('if(!str_cmp(word,"Trap") )', 1)[1][:1200]
        self.assertLess(trap.index("if (obj->trapped != NULL)"), trap.index("create_mobile(trap_mob)"))
        self.assertIn('fread_obj_refuse( "has an object record with two traps" )', trap)

    def test_the_lever_reads_the_bottle(self) -> None:
        obj = (ROOT / "src" / "act_obj.c").read_text(encoding="latin-1")
        genie = obj.split("let the genie out of the bottle", 1)[1][:1500]
        self.assertIn("bottled = find_obj->trapped;", genie)
        self.assertNotIn("bottled = obj->trapped;", genie)


@unittest.skipIf(SKIP is not None, SKIP or "")
class OwnershipLiveTests(unittest.TestCase):
    maxDiff = None

    def world(self, names: tuple[str, ...]) -> LiveMud:
        mud = LiveMud(fixtures=True)
        mud.__enter__()
        self.addCleanup(mud.__exit__, None, None, None)
        for name in ("Zownstaff",) + names:
            with mud.connect(timeout=120) as client:
                create_character(client, name, PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
        patch_player_file(mud, "Zownstaff", Levl=70, Room=TEMPLE)
        for name in names:
            patch_player_file(mud, name, Levl=20, Room=SPARRING_GALLERY)
        return mud

    @staticmethod
    def stale_lines(mud: LiveMud) -> list[str]:
        log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")
        return [line for line in log.splitlines() if "MEMORY: stale" in line]

    def test_one_pet_and_one_captive_a_record(self) -> None:
        mud = self.world(("Zpetdup", "Zpetbad", "Zpetone", "Ztrapdup", "Ztrapbad"))
        refused = {
            "Zpetdup": add(mud, "Zpetdup", PET + PET),
            "Zpetbad": add(mud, "Zpetbad", PET_MALFORMED),
            "Ztrapdup": add(mud, "Ztrapdup", bottle(str(SPARRING_GUARD), str(SPARRING_GUARD))),
            "Ztrapbad": add(mud, "Ztrapbad", bottle(str(SPARRING_GUARD), tail="Timer zz\n")),
        }
        add(mud, "Zpetone", PET)

        with mud.connect(timeout=120) as staff:
            login(staff, "Zownstaff", PW)
            staff.sync("scroll 0")
            place_sparring_guard(staff, "Zownstaff", SPARRING_FLOOR)
            self.assertEqual(guard_count(staff), 1)

            outcomes = {name: [try_name(mud, name) for _ in range(3)] for name in refused}
            staff.drain(3.0)            # the memory sweep runs every second
            seen = {
                "outcomes": outcomes,
                "guards in the world": guard_count(staff),
                "files changed": sorted(name for name, data in refused.items()
                                        if (mud.player_dir / name).read_bytes() != data),
                "stale pointers": self.stale_lines(mud),
            }
            self.assertEqual({"outcomes": {name: ["refused"] * 3 for name in refused},
                              "guards in the world": 1, "files changed": [],
                              "stale pointers": []}, seen)

            # One pet still comes with its owner, and goes with them.
            with mud.connect(timeout=120) as owner:
                login(owner, "Zpetone", PW)
                owner.sync("scroll 0")
                self.assertEqual(guard_count(staff), 2, "the pet came in")
                owner.send("quit")
                self.assertTrue(owner.wait_closed())
            staff.drain(2.0)
            self.assertEqual(guard_count(staff), 1, "the pet went with its owner")
            self.assertIn("Vnum %d" % SPARRING_GUARD,
                          (mud.player_dir / "Zpetone").read_text(encoding="latin-1"))
            memory = staff.must("memcheck", "Memory safeguards")
            self.assertIn("Stale pointers caught since boot: 0.", memory)
            staff.send("quit")
            staff.wait_closed()
        self.assertEqual([], self.stale_lines(mud))

    def test_the_genie_lever_opens_the_bottle_it_names(self) -> None:
        mud = self.world(("Zgenie",))
        add(mud, "Zgenie", bottle(str(SPARRING_GUARD)))
        with mud.connect(timeout=120) as staff:
            login(staff, "Zownstaff", PW)
            staff.sync("scroll 0")
            place_sparring_guard(staff, "Zownstaff", SPARRING_FLOOR)
            staff.sync(f"goto {SPARRING_GALLERY}")
            staff.must(f"load obj {LEVER}", "genie lever", "Ok.")
            with mud.connect(timeout=120) as genie:
                login(genie, "Zgenie", PW)
                genie.sync("scroll 0")
                self.assertEqual(guard_count(staff), 2, "the captive is in the bottle")
                genie.must("drop amulet", "You drop")
                pulled = genie.sync("pull lever", timeout=60)
                here = staff.sync("mwhere sparring", timeout=60)
                self.assertIn("bursts out of", pulled, pulled)
                self.assertRegex(here, r"\[\s*%d\].*\[\s*%d\]" % (SPARRING_GUARD, SPARRING_GALLERY))
                genie.send("quit")
                self.assertTrue(genie.wait_closed())
            staff.drain(2.0)
            self.assertEqual(guard_count(staff), 2, "the placed guard and the genie")
            staff.send("quit")
            staff.wait_closed()
        self.assertEqual([], self.stale_lines(mud))


if __name__ == "__main__":
    unittest.main()

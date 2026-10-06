"""In-game building, phase 2: MCREATE, OCREATE and the whole-area save.

An ANEW area knows which mobiles and objects are its own -- the ones in its
vnum range -- so ASAVE writes all of it: #AREADATA, #MOBILES, #OBJECTS,
#ROOMS, #RESETS, #SHOPS, #SPECIALS. The writer has to be the exact inverse
of the loader, and the test of that is a round trip: copy real prototypes
that use every awkward corner of the format (an M-style mobile with an
action, a shopkeeper with a special, an object with wear actions, one with
affects and two extra descriptions, one with an affect-bit F record, a
potion whose spells are stored by slot), save, reboot, and save again. The
two files must be byte for byte the same, and the copies must read back
exactly as the originals do.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Zbuildpw2"
LO, HI = 21000, 21019
ROOM = 21001
AREA_FILE = "zed_copy_works.are"

# new vnum -> the shipped prototype it copies
MOB_COPIES = {
    21002: 4444,   # elite guard: M-style, with a { A ... } action
    21003: 739,    # Stirrup: a shopkeeper with a special
}
OBJ_COPIES = {
    21005: 4503,   # the Recall Ring: a T wear action
    21006: 7206,   # a strange white skull: affects and two extra descs
    21007: 30200,  # the Master Sword: an F affect-bit record
    21008: 24,     # a jug o' moonshine: a potion, spells stored by slot
}
BLANK_MOB = 21004
BLANK_OBJ = 21009


def run(client, command: str, settle: float = 1.2) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


# The lines OSTAT writes, less its Vnum line. Anything else in the window --
# a prompt, the weather, a rooster -- is the world talking, not the object.
OSTAT_LINE = re.compile(
    r"^(Name\(s\)|Short description|Long description|Wear bits|Extra bits"
    r"|Number:|Level|In room:|Values:|Has \d|Weapon|Damage is"
    r"|Extra description|Affects)")


def ostat_body(text: str) -> list[str]:
    """OSTAT's own lines, with the vnum line taken out."""
    keep = []
    for line in text.replace("\r", "").split("\n"):
        line = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
        if OSTAT_LINE.match(line):
            keep.append(line)
    return keep


@unittest.skipIf(SKIP is not None, SKIP or "")
class MobObjBuildingTests(unittest.TestCase):
    def test_copies_round_trip_through_a_whole_area_save(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zbuildtwo", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zbuildtwo", Levl=70, Room=4207)

            area_path = mud.root / "area" / AREA_FILE

            with mud.connect(timeout=120) as imm:
                login(imm, "Zbuildtwo", PASSWORD)
                run(imm, "scroll 0")

                self.assertIn("Created area", run(imm, f"anew {LO} {HI} Zed Copy Works"))
                run(imm, f"goto {ROOM}", 1.5)
                run(imm, f"set room {ROOM} name The Copying Room", 1.5)
                # An exit, because boot makes a room with none NO_MOB
                # (fix_exits), and the second save would then differ for a
                # reason that has nothing to do with the writer.
                run(imm, "rlink north 21010", 1.5)

                # Refusals: outside any built area, and a vnum in use.
                self.assertIn("in no area", run(imm, "mcreate 4207"))
                self.assertIn("in no area", run(imm, "ocreate 4207 24"))

                for new, old in MOB_COPIES.items():
                    out = run(imm, f"mcreate {new} {old}")
                    self.assertIn(f"a copy of {old}", out, out)
                self.assertIn("already exists", run(imm, "mcreate 21002"))
                self.assertIn("no mobile", run(imm, "mcreate 21010 99999").lower())
                self.assertIn("blank level 1", run(imm, f"mcreate {BLANK_MOB}"))

                for new, old in OBJ_COPIES.items():
                    out = run(imm, f"ocreate {new} {old}")
                    self.assertIn(f"a copy of {old}", out, out)
                self.assertIn("blank piece", run(imm, f"ocreate {BLANK_OBJ}"))

                before = {new: ostat_body(run(imm, f"ostat {old}", 1.5))
                          for new, old in OBJ_COPIES.items()}
                for new in OBJ_COPIES:
                    self.assertEqual(ostat_body(run(imm, f"ostat {new}", 1.5)),
                                     before[new], f"copy {new} differs at once")

                saved = run(imm, "asave", 2.0)
                self.assertIn("Saved Zed Copy Works", saved, saved)
                self.assertIn("3 mobiles, 5 objects", saved, saved)

                # RSAVE on an ANEW area saves it whole too.
                self.assertIn("saves whole", run(imm, "rsave"))

                imm.send("quit")
                self.assertTrue(imm.wait_closed())

            first = area_path.read_bytes()
            text = first.decode("latin-1")
            for section in ("#AREADATA", "#MOBILES", "#OBJECTS", "#ROOMS",
                            "#RESETS", "#SHOPS", "#SPECIALS", "#$"):
                self.assertIn(section, text)
            self.assertNotIn("\r", text, "carriage returns written to the area file")
            self.assertRegex(text, r"\n21003 ", "the copied shop was not saved")
            self.assertRegex(text, r"\nM 21003 spec_", "the copied special was not saved")
            self.assertIn("{\nA 54\n", text, "the M-style action was not saved")

            mud.restart()

            with mud.connect(timeout=120) as imm:
                login(imm, "Zbuildtwo", PASSWORD)
                run(imm, "scroll 0")

                for new, old in OBJ_COPIES.items():
                    self.assertEqual(ostat_body(run(imm, f"ostat {new}", 1.5)),
                                     before[new],
                                     f"object {new} (copy of {old}) changed across a reboot")

                run(imm, f"goto {ROOM}", 1.5)
                run(imm, f"load mob 21002", 1.5)
                here = run(imm, "look", 1.5)
                self.assertIn("elite guard of Dresden", here, here)

                # Save again: a faithful writer reproduces its own file.
                self.assertIn("Saved Zed Copy Works", run(imm, "asave", 2.0))
                imm.send("quit")
                self.assertTrue(imm.wait_closed())

            second = area_path.read_bytes()
            self.assertEqual(first, second,
                             "the area file changed when saved again after a reboot")
            backups = list(area_path.parent.glob(AREA_FILE + ".*.bak"))
            self.assertTrue(backups, "no backup kept of the previous file")


if __name__ == "__main__":
    unittest.main()

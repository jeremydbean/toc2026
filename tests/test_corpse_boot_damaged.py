"""A damaged corpse file is set aside at boot, never the end of the boot
(review, 2026-11-12).

A player's corpse is made again at boot from corpse/live/<id>.corpse
(src/corpses.c). A dry run (scan_gear_section) checks every number before
the real read, but fread_string wrote into the string space with no bound
of its own: a string longer than the space left -- six megabytes in a
corpse file -- ran off the end of string_space and the game died before
it answered anybody. Now fread_string stops at the end of the space as a
malformed value, and the objects of a corpse or a snapshot are read under
a trap of their own (fread_aside_trap, read_objects_aside): the file is
renamed .unreadable with a log line, nothing is laid, and the boot goes
on -- a good corpse beside it is made again as always. A player file with
such a string refuses that character at the name prompt, as any
malformed value does.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zcorpsebad1"
GOOD_ROOM, BAD_ROOM = 4202, 4203
HUGE = 6_000_000            # past the five-megabyte string space

CORPSE = """#CORPSE
Id {id}
Owner {owner}
Uid -
Owned 1
Room {room}
Level 20
Timer 10080
Died 1794447689
Saved 1794447689
Snapshot -
State live
Why -
Objects 1
Vers 4
End

#O
Vnum 3702
Nest 0
{extra}Wear -1
Cost 0
Cond 100
Repd 0
End

#END
"""


def boot_finished(mud: LiveMud) -> None:
    """The port opens before boot reads the corpses; the name prompt is
    sent only by the running game loop, after it has."""
    with mud.connect(timeout=180) as client:
        client.expect("by what name", "name:", "what is your name")


class DamagedCorpseSourceTests(unittest.TestCase):
    def test_the_string_reader_is_bounded_and_aside_reads_are_trapped(self) -> None:
        db = (ROOT / "src" / "db.c").read_text(encoding="latin-1")
        for name in ("char *fread_string( FILE *fp )", "char *fread_string_eol( FILE *fp )"):
            body = db.split(name, 1)[1].split("\n}\n", 1)[0]
            self.assertRegex(body, r"plast > &string_space\[MAX_STRING - [23]\]", name)
        malformed = db.split("static void fread_malformed( const char *what )", 1)[1]
        self.assertIn("longjmp( *fread_aside_trap, 1 );", malformed.split("\n}\n", 1)[0])
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        aside = save.split("static int read_objects_aside(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("fread_aside_trap = &trap;", aside)
        self.assertIn("fread_obj_release_unfinished();", aside)


@unittest.skipIf(SKIP is not None, SKIP or "")
class DamagedCorpseLiveTests(unittest.TestCase):
    def test_a_corpse_too_big_to_read_is_set_aside_and_the_boot_goes_on(self) -> None:
        with LiveMud() as mud:
            for name in ("Zcorpstaff", "Zcorphuge"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zcorpstaff", Levl=70, Room=4207)
            mud._stop()

            live = mud.root / "corpse" / "live"
            live.mkdir(parents=True, exist_ok=True)
            bad = live / "cdamagedhuge01.corpse"
            bad.write_text(CORPSE.format(id="cdamagedhuge01", owner="Zcorpbad", room=BAD_ROOM,
                                         extra="ShD " + "x" * HUGE + "~\n"), encoding="latin-1")
            (live / "cwholecorpse01.corpse").write_text(
                CORPSE.format(id="cwholecorpse01", owner="Zcorpgood", room=GOOD_ROOM, extra=""),
                encoding="latin-1")
            # A player file with the same: that character is refused.
            path = mud.player_dir / "Zcorphuge"
            text = path.read_text(encoding="latin-1")
            path.write_text(text.replace("\nEnd\n", "\nDesc " + "y" * HUGE + "~\nEnd\n", 1),
                            encoding="latin-1")

            mud._launch()
            boot_finished(mud)
            self.assertIsNone(mud.proc.poll(), "the game is running")
            with mud.connect(timeout=120) as refused:
                refused.expect("by what name", "name:")
                refused.send("Zcorphuge")
                said = refused.expect("could not be read", "assword", timeout=60)
            self.assertIn("could not be read", said, "the character is refused, not asked in")
            with mud.connect(timeout=120) as staff:
                login(staff, "Zcorpstaff", PW)
                staff.sync("scroll 0")
                staff.must("holylight", "Holy light")
                there = staff.sync(f"at {BAD_ROOM} look")
                good = staff.sync(f"at {GOOD_ROOM} look")
                staff.send("quit")
                staff.wait_closed()
            self.assertIsNone(mud.proc.poll(), "still running after the refusal")
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            files = sorted(p.name for p in live.iterdir())

        self.assertNotIn("Zcorpbad", there)
        self.assertIn("corpse of Zcorpgood", good)
        self.assertIn("cdamagedhuge01.corpse.unreadable", files)
        self.assertNotIn("cdamagedhuge01.corpse", files)
        self.assertIn("cwholecorpse01.corpse", files)
        self.assertIn("a string longer than the string space", log)
        self.assertRegex(log, r"Corpse keeper: \S*cdamagedhuge01\.corpse could not be made again "
                              r"\(a value in its objects could not be read\); kept as")
        self.assertIn("Corpse keeper: Zcorpgood's corpse cwholecorpse01 made again", log)


if __name__ == "__main__":
    unittest.main()

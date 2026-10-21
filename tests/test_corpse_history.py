"""NEWCORPSE reads a corpse history (corpse/<name>.cps) safely.

Audit 2026-10-21: a record holding exactly 99 items begins "99 99", which
was also the end marker, so the reader stopped there and lost it and
every older record; the reader also took any count into fixed arrays and
trusted any slot from 1 to 5 past the records it had found. New files
end "-1 -1"; "99 99" ends an old file only when nothing follows it.

corpse_back, which writes these, is not called at present (fight.c), so
the files here are written by hand in both shapes.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zcorpse1"
TEMPLE = 4207
SWORD = 3702


def run(client, command: str, settle: float = 1.2) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def record(count: int) -> str:
    items = " ".join("%d 5" % SWORD for _ in range(count))
    return "%d %d %s %d %d " % (count, count, items, SWORD * count, 5 * count)


class CorpseHistorySourceTests(unittest.TestCase):
    def test_both_readers_share_the_bounded_one(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        self.assertIn('fprintf( fp, "-1 -1" );', save)
        newcorpse = wiz[wiz.index("void do_newcorpse("):]
        newcorpse = newcorpse[:newcorpse.index("\n}\n")]
        self.assertIn("corpse_history_read(", newcorpse)
        self.assertNotIn("fread_number", newcorpse)
        self.assertIn("number >= held", newcorpse)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CorpseHistoryLiveTests(unittest.TestCase):
    def test_ninety_nine_items_is_a_record_not_the_end(self) -> None:
        with LiveMud() as mud:
            for name in ("Zcoroner", "Zdeceased"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zcoroner", Levl=70, Room=TEMPLE)
            patch_player_file(mud, "Zdeceased", Levl=10, Room=TEMPLE, Corpses=3)
            cps = mud.root / "corpse" / "Zdeceased.cps"

            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as dead:
                login(staff, "Zcoroner", PASSWORD)
                login(dead, "Zdeceased", PASSWORD)
                run(staff, "scroll 0")

                def listing() -> list[tuple[int, str]]:
                    text = run(staff, "newcorpse zdeceased", 1.5)
                    return [(int(n), flag) for n, flag in
                            re.findall(r"^\s+\d+\s+(\d+)\s+(Valid|Invalid)", text, re.M)]

                # An old file: a 99-item record, then a 1-item one, then the
                # old end marker.
                cps.write_text(record(99) + record(1) + "99 99", encoding="latin-1")
                self.assertEqual(listing(), [(99, "Valid"), (1, "Valid")])
                self.assertIn("They don't have that many corpses",
                              run(staff, "newcorpse zdeceased 3", 1.2))

                # An old file in its common shape.
                cps.write_text(record(2) + "99 99", encoding="latin-1")
                self.assertEqual(listing(), [(2, "Valid")])

                # A new file, and restoring the 99-item corpse from it.
                cps.write_text(record(99) + "-1 -1", encoding="latin-1")
                self.assertEqual(listing(), [(99, "Valid")])
                self.assertIn("create", run(staff, "newcorpse zdeceased 1", 1.5))

                # A file cut short: refused, and the game is still up.
                cps.write_text("5 5 %d 5 " % SWORD, encoding="latin-1")
                self.assertIn("damaged", run(staff, "newcorpse zdeceased", 1.5))
                cps.write_text("5000 5000 1 1", encoding="latin-1")
                self.assertIn("damaged", run(staff, "newcorpse zdeceased", 1.5))
                self.assertIn("Zdeceased", run(staff, "who", 1.2))


if __name__ == "__main__":
    unittest.main()

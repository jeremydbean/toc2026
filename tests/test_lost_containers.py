"""What was inside a container whose vnum is gone survives the login.

fread_obj makes a placeholder for an object whose vnum no longer exists
and frees it at End -- but the Nest key had already pointed its slot in
the nesting table at that placeholder, so every object saved inside the
vanished container was linked into freed memory and never reached the
player (found 2026-10-14 reviewing the stash restore). The loader clears
the slot and keeps such contents loose, in the inventory or the stash,
with a log line naming them.
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zorphan1"
GONE = 99999            # no object has this vnum
BAG = 3032
BOMBS = 30695


def record(vnum: int, nest: int) -> str:
    return ("#O\nVnum %d\nNest %d\nWear -1\nLev  1\nCost 0\nCond 100\nRepd 0\nEnd\n\n"
            % (vnum, nest))


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class LoaderSourceTests(unittest.TestCase):
    def test_a_freed_placeholder_leaves_the_nesting_table(self) -> None:
        source = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        body = source[source.index("void fread_obj( CHAR_DATA *ch, FILE *fp )"):]
        body = body[:body.index("\n}\n")]
        incomplete = body[body.index('bug( "Fread_obj: incomplete object."'):]
        incomplete = incomplete[:incomplete.index("return;")]
        self.assertIn("rgObjNest[iSlot] = NULL", incomplete)
        self.assertIn("rgObjNest[iNest-1] == NULL", body)


@unittest.skipIf(SKIP is not None, SKIP or "")
class LostContainerLiveTests(unittest.TestCase):
    def test_contents_of_a_vanished_container_are_kept(self) -> None:
        """A gone container (nest 0) holding a bag (nest 1) holding bombs
        (nest 2), in the inventory and again in the stash."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zorphan", PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zorphan", Room=4207)

            path = mud.player_dir / "Zorphan"
            text = path.read_text(encoding="latin-1")
            chain = record(GONE, 0) + record(BAG, 1) + record(BOMBS, 2)
            text = text.replace("#END", chain + "#STASH\n\n" + chain + "#END", 1)
            path.write_text(text, encoding="latin-1")

            with mud.connect(timeout=120) as client:
                login(client, "Zorphan", PASSWORD)
                client.drain(0.5)
                inventory = run(client, "inventory", 1.8)
                self.assertIn("bag", inventory, inventory)
                self.assertIn("four bombs", run(client, "look in bag", 1.8))
                stash = run(client, "stash", 1.8)
                self.assertIn("bag", stash, stash)
                self.assertIn("holds 1 of", stash)

            written = (mud.root / "log" / "toc.log").read_text(encoding="latin-1",
                                                               errors="replace")
            self.assertIn("bad vnum %d" % GONE, written)
            self.assertIn("the container holding %d on Zorphan is gone; kept loose" % BAG,
                          written)


if __name__ == "__main__":
    unittest.main()

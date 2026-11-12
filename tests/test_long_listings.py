"""A long listing ends where the list ends.

Growable output buffers, 2026-11-12. STASH, HISTORY, NOTE LIST, WHO,
REPORTS, GAINLIST, CHANGES, DIARY LIST and the Hall of Heroes' rolls were
built in fixed arrays -- STASH's was 4,096 bytes -- and stopped part way:
a stash of 500 listed about the first ninety and said "... and more than
will fit on one screen", while STASH GET <number> takes the numbers it
shows. They are built in a bounded DString now (src/dstring.h), and the
pager takes text of any size (page_to_char sends past its block unpaged).

Played here with STASH: three hundred pieces, read with paging off and
again a page at a time; every number from 1 to the last is there, in
order, and nothing says the list was cut.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Zstash1pass"
ALTAR = 4208
SILVER_PLATE = 631          # body armour, ofcol.are: takes no timer
PIECES = 300

CUT = "more than will fit"


def clone_stash_record(path, pieces: int) -> None:
    """Make the one object in a saved stash `pieces` of it."""
    text = path.read_text(encoding="latin-1")
    stash = text.index("#STASH\n")
    start = text.index("#O\n", stash)
    end = text.index("End\n", start) + len("End\n")
    record = text[start:end]
    assert "Vnum %d" % SILVER_PLATE in record, record
    assert text.count("#O\n", stash) == 1, "the stash should hold one piece"
    path.write_text(text[:end] + ("\n" + record) * (pieces - 1) + text[end:],
                    encoding="latin-1")


def numbers_listed(text: str) -> list[int]:
    return [int(n) for n in re.findall(r"^\s*(\d+)\) ", text.replace("\r", ""), re.M)]


@unittest.skipIf(SKIP is not None, SKIP or "")
class LongListingTests(unittest.TestCase):
    def test_a_full_stash_lists_every_piece(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zstasher", PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zstasher", Levl=70, Room=ALTAR)

            # One piece stashed by the game, then its record copied in
            # the file: three hundred LOAD and STASH commands cost a pulse
            # each, and the copy is what the game itself wrote.
            with mud.connect(timeout=120) as client:
                login(client, "Zstasher", PASSWORD)
                client.must("set player zstasher stash 500", "stash now holds 500")
                client.must("load obj %d" % SILVER_PLATE, "You create")
                client.must("stash put plate", "You put")
                client.send("quit")
                self.assertTrue(client.wait_closed())
            clone_stash_record(mud.player_dir / "Zstasher", PIECES)

            with mud.connect(timeout=120) as client:
                login(client, "Zstasher", PASSWORD)
                # Paging off: one reply, the whole list.
                client.must("scroll 0", "Paging disabled")
                listing = client.sync("stash", timeout=60)
                held = re.search(r"Your stash holds (\d+) of 500", listing)
                self.assertIsNotNone(held, listing[-600:])
                total = int(held.group(1))
                self.assertGreaterEqual(total, PIECES)
                self.assertNotIn(CUT, listing)
                shown = numbers_listed(listing)
                self.assertEqual(shown, list(range(1, total + 1)),
                                 "the stash list stopped at %s of %d" % (shown[-1:], total))

                # Paging on: a page at a time. Never sync here -- the
                # barrier would be read as the pager's return.
                client.must("scroll 20", "Scroll set to 20")
                mark = len(client.transcript)
                client.buffer = ""
                client.send("stash")
                last = "%3d) " % total
                pages = 0
                while client.expect("[hit return to continue]", last,
                                    timeout=60) != last:
                    pages += 1
                    self.assertLess(pages, 200, "the pager never ended")
                    client.send("")
                client.drain(0.5)
                paged = client.transcript[mark:]
                self.assertGreater(pages, 5, "300 lines should page at 20 a page")
                self.assertNotIn(CUT, paged)
                self.assertEqual(numbers_listed(paged), list(range(1, total + 1)))

if __name__ == "__main__":
    unittest.main()

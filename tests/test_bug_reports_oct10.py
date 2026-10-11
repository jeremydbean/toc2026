"""Alaric's bug reports of 2026-10-10 (area/bugs.txt).

- Dying emptied the stash. A player's death extracts them with fPull
  false and they go on playing, but extract_char freed the stash in
  memory either way, so the next save wrote it empty. Only a character
  who is leaving (fPull) has their stash copies freed now.
- HISTORY with nothing to show said "Nothing has been said on every
  channel."; it says "any channel".
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SourceTests(unittest.TestCase):
    def test_a_death_does_not_free_the_stash(self) -> None:
        source = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        body = source[source.index("void extract_char( CHAR_DATA *ch, bool fPull )"):]
        body = body[:body.index("char_from_room( ch );")]
        calls = re.findall(r"if \(([^)]*\)?[^)]*)\)\s*\n\s*stash_extract\( ch \);", body)
        self.assertEqual(len(calls), 1, "extract_char should free the stash once")
        self.assertIn("fPull", calls[0],
                      "a death (fPull false) must not free the stash")

    def test_empty_history_says_any_channel(self) -> None:
        source = (ROOT / "src" / "act_comm.c").read_text(encoding="latin-1")
        self.assertIn("Nothing has been said on any channel.", source)


if __name__ == "__main__":
    unittest.main()

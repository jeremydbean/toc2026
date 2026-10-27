"""AFFECTS names an immunity instead of filing a bug.

Iron skin, the monster wards and dshield carry their immunity on the
affect through APPLY_IMMUNITY, which affect_loc_name() never learned: a
monk at level 20 or more who typed AFFECTS with iron skin up was told it
"modifies (unknown) by 16", and every look wrote a BUG line
(Alaric, 2026-10-27). AFFECTS now says what it turns, and every APPLY_
location has a name.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zimmunepw1"
TEMPLE = 4207
IMM_BASH = 16  # (E)
APPLY_IMMUNITY = 25


class ApplyNamesTests(unittest.TestCase):
    def test_every_apply_location_has_a_name(self) -> None:
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        body = handler[handler.index("char *affect_loc_name("):]
        body = body[: body.index("bug( \"Affect_location_name")]
        applies = set(re.findall(r"#define\s+(APPLY_[A-Z_]+)\s+\d+", merc))
        named = set(re.findall(r"case\s+(APPLY_[A-Z_]+)\s*:", body))
        self.assertEqual(applies - named, set())


@unittest.skipIf(SKIP is not None, SKIP or "")
class ImmunityAffectLiveTests(unittest.TestCase):
    def test_affects_names_the_immunity(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zimmune", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            # The iron skin affect as do_iron_skin saves it: level 30,
            # ten hours, modifier IMM_BASH, location APPLY_IMMUNITY.
            patch_player_file(mud, "Zimmune", Levl=30, Room=TEMPLE,
                              AffD=f"'iron skin' 30 10 {IMM_BASH} {APPLY_IMMUNITY} 0 0")
            with mud.connect(timeout=120) as client:
                login(client, "Zimmune", PW)
                said = client.sync("affects")
                self.assertIn("grants immunity to blunt", said)
                self.assertNotIn("unknown", said.lower())
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1",
                                                           errors="replace")
            self.assertNotIn("Affect_location_name", log)


if __name__ == "__main__":
    unittest.main()

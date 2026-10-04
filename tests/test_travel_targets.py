"""Gate, earth travel, portal and astral walk reach what they should.

Owner's rules (2026-10-04): gate, earth travel and portal reach anyone not
in a no-recall or jail room, not of immortal level and not more than four
levels above the caster; astral walk has no level limit and may leave a
no-recall room but never enter one. The first reachable match is taken,
so "kitten" no longer stops at a level 45 kitten nobody could reach, and a
mobile's summon immunity no longer blocks travelling to it.
"""
from __future__ import annotations

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

try:
    from live_mud import LiveMud, create_character, patch_player_file, login, skip_reason
    LIVE_SKIP = skip_reason()
except ImportError as exc:  # pragma: no cover
    LIVE_SKIP = str(exc)

PW = "Zearthpw1"


def first_line_after(out: str) -> str:
    lines = [line for line in out.splitlines() if line.strip()]
    if lines and "sink into the earth" in lines[0] and len(lines) > 1:
        return lines[1]
    return lines[0] if lines else ""


class SourceTests(unittest.TestCase):
    def test_one_finder_for_every_travel_spell(self) -> None:
        magic = (ROOT / "src" / "magic.c").read_text(encoding="latin-1")
        magic2 = (ROOT / "src" / "magic2.c").read_text(encoding="latin-1")
        self.assertIn("travel_target( ch, target_name, level, TRAVEL_GATE )", magic)
        self.assertIn("travel_target( ch, target_name, level, TRAVEL_PORTAL )", magic)
        self.assertIn("travel_target( ch, target_name, level, TRAVEL_GATE )", magic2)
        self.assertIn("travel_target( ch, arg, ch->level, TRAVEL_ASTRAL )", magic2)
        finder = magic[magic.index("CHAR_DATA *travel_target("):]
        finder = finder[:finder.index("\n}\n")]
        self.assertIn("wch->level > level + 4", finder)
        self.assertNotIn("IMM_SUMMON", finder)


@unittest.skipIf(LIVE_SKIP is not None, LIVE_SKIP or "")
class LiveTests(unittest.TestCase):
    def test_earth_travel_finds_a_reachable_target(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as c:
                create_character(c, "Zearther", PW)
                c.send("quit")
                self.assertTrue(c.wait_closed())
            patch_player_file(mud, "Zearther", Levl=28, Room=4207, Cla=5, Gui=5,
                              HMV="500 500 5000 5000 500 500", HMVP="500 5000 500",
                              Sk="100 'earth travel'")
            results = {}
            with mud.connect(timeout=120) as c:
                login(c, "Zearther", PW)
                for target in ("kitten", "cepheus", "sammy"):
                    c.send("recall")
                    c.drain(4)
                    mark = len(c.transcript)
                    c.send(f"cast 'earth travel' {target}")
                    c.drain(4)
                    results[target] = first_line_after(c.transcript[mark:])
                c.send("quit")
                self.assertTrue(c.wait_closed())
            # The High Tower's level 1 kitten, not Sammy the level 45 one.
            self.assertIn("hallway", results["kitten"].lower(), results)
            # Cepheus is level 26 and summon-immune: reachable now.
            self.assertIn("Cepheus", results["cepheus"], results)
            # Sammy is level 45, more than four above a level 28.
            self.assertNotIn("Study", results["sammy"], results)


if __name__ == "__main__":
    unittest.main()

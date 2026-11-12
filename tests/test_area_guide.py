"""The area building guide (wiki/, the authoritative area format reference)
is held to the code it documents.

The guide is the authoritative area format reference, and it had drifted:
flag letters that named the wrong bit (AFF2_STEALTH as F, VULN_WOOD as T,
the elf and halfling race bits swapped), identifiers that no longer exist
(ACT_NOPUSH, AFF_INFRAVISION, VULN2_IRON), shop trade numbers that were not
object types, and a complete area template that neither the Python reader
nor the game could load (two-letter vnums, an ITEM_FLAGS2 token with no Z,
a #SPECIALS section with no S).

These tests read the guide's tables and compare them with src/merc.h,
attack_table and liq_table in src/const.c and spec_table in
src/special.c; then they take the "Complete Area Template" code block out
of the guide and load it through webadmin/area_reader.py and, where a
built server binary exists, through the game's own --check-area in a
disposable copy of the world.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from webadmin.area_reader import parse_area_text  # noqa: E402

# The name is put together rather than written whole: scripts/ci/classify.py
# picks a document's contract tests by a substring search for its file name,
# so naming this guide here would also select this module for the separate
# in-game building guide, whose name ends the same way (test_ci_classify
# pins that it selects nothing). The nightly and every full run still run
# this module.
GUIDE = ROOT / "wiki" / ("area-building-guide" + ".md")
MERC_H = ROOT / "src" / "merc.h"
CONST_C = ROOT / "src" / "const.c"
SPECIAL_C = ROOT / "src" / "special.c"

# Every flag family the guide documents letter by letter.
FLAG_PREFIXES = ("ACT_", "ACT2_", "AFF_", "AFF2_", "OFF_", "OFF2_", "ASSIST_",
                 "IMM_", "RES_", "VULN_", "FORM_", "PART_", "ITEM_", "ITEM2_",
                 "ROOM_", "ROOM2_", "WEAPON_")
FLAG_NAMES = ("NEEDS_MASTER",)

DAM_WORDS = {
    "DAM_BASH": "bash", "DAM_PIERCE": "pierce", "DAM_SLASH": "slash",
    "DAM_FIRE": "fire", "DAM_COLD": "cold", "DAM_LIGHTNING": "lightning",
    "DAM_ACID": "acid", "DAM_POISON": "poison", "DAM_NEGATIVE": "negative",
    "DAM_HOLY": "holy", "DAM_ENERGY": "energy", "DAM_MENTAL": "mental",
    "DAM_DISEASE": "disease", "DAM_DROWNING": "drowning", "DAM_LIGHT": "light",
    # attack_table's "hit" has no type of its own (-1); one_hit reads it as
    # bash.
    "-1": "bash",
}


def read(path: Path) -> str:
    return path.read_text(encoding="latin-1")


def letter_defines() -> dict:
    """#define NAME (X) or (xx) in merc.h -> 'X' or 'xx'."""
    out = {}
    for m in re.finditer(r"^#define\s+(\w+)\s+\(([A-Za-z]{1,2})\)", read(MERC_H), re.M):
        out[m.group(1)] = m.group(2)
    return out


def number_defines() -> dict:
    out = {}
    for m in re.finditer(r"^#define\s+(\w+)\s+(-?\d+)\b", read(MERC_H), re.M):
        out.setdefault(m.group(1), int(m.group(2)))
    return out


def table_rows(text: str):
    """Every markdown table row as a list of stripped cells (header and
    separator rows included; callers filter)."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("|") and line.endswith("|"):
            yield [c.strip() for c in line[1:-1].split("|")]


def section(text: str, heading: str) -> str:
    """The text under a heading, up to the next heading of any level."""
    start = text.index(heading)
    rest = text[start + len(heading):]
    m = re.search(r"^#{2,3} ", rest, re.M)
    return rest[: m.start()] if m else rest


def guide_letter_rows(text: str):
    """(name, letter-as-merc.h-writes-it) for every NAME | L row."""
    for cells in table_rows(text):
        if len(cells) < 2:
            continue
        name = cells[0].strip("`")
        letter = cells[1].strip("`")
        if re.fullmatch(r"[A-Z][A-Z0-9]*_[A-Z0-9_]+", name) and re.fullmatch(r"[A-Za-z]", letter):
            # The guide writes a bit past Z as the lower-case letter the
            # file takes; merc.h names it doubled (aa, bb, ...).
            yield name, letter if letter.isupper() else letter * 2


def template_block(text: str) -> str:
    body = section(text, "## Complete Area Template")
    m = re.search(r"^```\n(.*?)^```", body, re.M | re.S)
    assert m, "no code block under Complete Area Template"
    return m.group(1)


class GuideFlagTests(unittest.TestCase):
    """Every NAME | letter row is a real merc.h flag with that letter, and
    every flag of a documented family has a row."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = read(GUIDE)
        cls.letters = letter_defines()
        cls.numbers = number_defines()

    def test_every_letter_row_names_a_real_flag_with_its_letter(self) -> None:
        wrong = []
        for name, letter in guide_letter_rows(self.text):
            if name not in self.letters:
                wrong.append(f"{name}: no such letter flag in merc.h")
            elif self.letters[name] != letter:
                wrong.append(f"{name}: guide says {letter}, merc.h says {self.letters[name]}")
        self.assertEqual(wrong, [])

    def test_every_documented_family_is_complete(self) -> None:
        documented = {name for name, _ in guide_letter_rows(self.text)}
        missing = sorted(name for name in self.letters
                         if (name.startswith(FLAG_PREFIXES) or name in FLAG_NAMES)
                         and name not in documented)
        self.assertEqual(missing, [])

    def test_every_numbered_row_matches_its_define(self) -> None:
        wrong = []
        for cells in table_rows(self.text):
            if len(cells) < 2 or not re.fullmatch(r"-?\d+", cells[0]):
                continue
            name = cells[1].strip("`")
            if not re.fullmatch(r"[A-Z][A-Z0-9]*_[A-Z0-9_]+", name):
                continue
            if name not in self.numbers:
                wrong.append(f"{name}: no such numeric define in merc.h")
            elif self.numbers[name] != int(cells[0]):
                wrong.append(f"{name}: guide says {cells[0]}, merc.h says {self.numbers[name]}")
        self.assertEqual(wrong, [])

    def test_stale_identifiers_are_gone(self) -> None:
        for stale in ("ACT_NOPUSH", "AFF_INFRAVISION", "VULN2_IRON", "POS_MOUNTED",
                      "ROOM_DEATHTRAP", "ROOM_AFF_BY", "AFF2_FLAMING |"):
            self.assertNotIn(stale, self.text, stale)

    def test_lycanthropy_is_described_as_disabled(self) -> None:
        self.assertIn("#define LYCANTHROPY_ENABLED     0", read(MERC_H))
        self.assertIn("LYCANTHROPY_ENABLED", self.text)

    def test_shop_trade_types_are_object_types(self) -> None:
        body = section(self.text, "### Item Types for Shops (trade values)")
        self.assertIn("get_cost", body)
        rows = [c for c in table_rows(body) if re.fullmatch(r"\d+", c[0])]
        self.assertGreater(len(rows), 10)
        for cells in rows:
            self.assertTrue(cells[1].startswith("ITEM_"), cells)
            self.assertEqual(self.numbers[cells[1]], int(cells[0]), cells)


class GuideTableTests(unittest.TestCase):
    """The attack, liquid and spec-function tables against const.c and
    special.c."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = read(GUIDE)

    def test_attack_types_match_attack_table(self) -> None:
        src = read(CONST_C)
        block = src[src.index("attack_table    []"):]
        block = block[: block.index("};")]
        table = re.findall(r'\{\s*"([^"]+)",\s*(-?\w+)\s*\}', block)
        self.assertGreater(len(table), 30)
        rows = [c for c in table_rows(section(self.text, "### Damage / Attack Types"))
                if re.fullmatch(r"\d+", c[0])]
        self.assertEqual(len(rows), len(table))
        for cells, (name, dam) in zip(rows, table):
            index = int(cells[0])
            self.assertEqual(table[index][0], name)
            guide_name = re.sub(r"\s*\(.*\)", "", cells[1]).lower()
            self.assertEqual(guide_name, name, cells)
            self.assertEqual(cells[2].split()[0].lower(), DAM_WORDS[dam], cells)

    def test_liquids_match_liq_table(self) -> None:
        src = read(CONST_C)
        block = src[src.index("liq_table       [LIQ_MAX]"):]
        block = block[: block.index("};")]
        table = re.findall(r'\{\s*"([^"]+)",\s*"[^"]*",\s*\{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\s*\}', block)
        self.assertEqual(len(table), 16)
        rows = [c for c in table_rows(section(self.text, "### Liquid Values"))
                if re.fullmatch(r"\d+", c[0])]
        self.assertEqual(len(rows), len(table))
        for cells, (name, drunk, _full, thirst) in zip(rows, table):
            self.assertEqual(cells[1], name, cells)
            self.assertEqual(int(cells[2]), int(drunk), cells)
            self.assertEqual(int(cells[3]), int(thirst), cells)

    def test_named_spec_functions_exist(self) -> None:
        known = set(re.findall(r'\{\s*"(spec_\w+)"', read(SPECIAL_C)))
        named = set(re.findall(r"^\| `(spec_\w+)` \|", section(self.text, "### Available Spec-Functions"), re.M))
        named |= set(re.findall(r"^M \d+ (spec_\w+)", self.text, re.M))
        self.assertTrue(named)
        self.assertEqual(sorted(named - known), [])

    def test_resist_and_vuln_arithmetic_is_combat_rules(self) -> None:
        rules = read(ROOT / "src" / "combat_rules.c")
        self.assertIn("case BLOW_RESISTANT:  return dam - dam / 3;", rules)
        self.assertIn("case BLOW_VULNERABLE: return dam + dam / 2;", rules)
        self.assertIn("`dam - dam/3`", self.text)
        self.assertIn("`dam + dam/2`", self.text)
        self.assertNotIn("approximately **half damage**", self.text)
        self.assertNotIn("approximately **double damage**", self.text)


class TemplateTests(unittest.TestCase):
    """The complete template loads, through the Python reader and the
    game."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.block = template_block(read(GUIDE))

    def test_python_reader_loads_the_template(self) -> None:
        area = parse_area_text(self.block, "guide_template.are")
        self.assertEqual(len(area.rooms), 3)
        self.assertEqual(len(area.mobiles), 2)
        self.assertEqual(len(area.objects), 2)
        self.assertEqual(len(area.shops), 1)
        self.assertEqual(len(area.specials), 1)
        self.assertEqual(area.section("$") is not None, True)
        # Every vnum is a number in the stand-in block.
        for record in area.rooms + area.mobiles + area.objects:
            self.assertTrue(41000 <= record.vnum <= 41099, record.vnum)
        # The gate's keyword is the keyword, not part of the description.
        market = next(r for r in area.rooms if r.vnum == 41000)
        north = next(e for e in market.exits if e.door == 0)
        self.assertEqual(north.keyword.strip(), "gate gates")
        self.assertNotIn("gate gates", north.description)
        self.assertEqual(north.to_room, 41001)
        # No object writes an ITEM_FLAGS2 token without a Z.
        for obj in area.objects:
            self.assertIsNone(obj.extra2)

    @unittest.skipIf(sys.platform.startswith("win"), "the game is POSIX-only")
    def test_game_loads_the_template(self) -> None:
        sys.path.insert(0, str(ROOT / "tests"))
        from live_mud import find_binary  # noqa: E402

        binary = find_binary()
        if binary is None:
            self.skipTest("no built server binary (run `make` or the CMake build first)")
        env = dict(os.environ, TOC_SEASON="none")

        def check(area_dir: Path) -> tuple:
            run = subprocess.run([str(binary), "--check-area"], cwd=area_dir,
                                 capture_output=True, text=True, timeout=600,
                                 errors="replace", env=env)
            out = run.stdout + run.stderr
            self.assertEqual(run.returncode, 0, out[-2000:])
            m = re.search(r"Validation OK: areas=(\d+) mobs=(\d+) objects=(\d+) rooms=(\d+)", out)
            self.assertIsNotNone(m, out[-2000:])
            return tuple(map(int, m.groups()))

        with tempfile.TemporaryDirectory(prefix="toc-guide-") as tmp:
            root = Path(tmp)
            shutil.copytree(ROOT / "area", root / "area")
            for name in ("player", "gods", "heroes", "corpse", "backups", "log"):
                (root / name).mkdir(exist_ok=True)
            area = root / "area"
            base = check(area)

            (area / "zguidetemplate.are").write_bytes(self.block.encode("latin-1"))
            listing = area / "area.lst"
            words = listing.read_text(encoding="latin-1").split()
            cut = next(i for i, w in enumerate(words) if w.startswith("$"))
            words.insert(cut, "zguidetemplate.are")
            listing.write_text("\n".join(words) + "\n", encoding="latin-1")

            after = check(area)
            self.assertEqual(after, (base[0] + 1, base[1] + 2, base[2] + 2, base[3] + 3))


if __name__ == "__main__":
    unittest.main()

"""The holiday copies of dresden, limbo and midennir are generated, and
each is a superset of its base.

src/season.c loads <base>_halloween.are from Oct 18 to Nov 1 and
<base>_xmas.are from Dec 16 to Jan 6 in place of the base file. Until
2026-10-19 the copies were hand-kept snapshots of an older world: the
Halloween dresden had no room 4216 (where every dead player is moved, so
a boot in season would have crashed on the first death), limbo had no
Oracle, no Hermie and no sanctum, the Quest Master was gone from dresden
and duplicated in limbo, and every object still carried its pre-copper
gold price. Nobody noticed, because the files only load in season.

scripts/build_seasonal_areas.py builds each copy from the base plus an
overlay of flavour text and seasonal-only records (data/seasonal/); these
tests hold the committed copies to that build and to their bases.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / "area"
SCRIPT = ROOT / "scripts" / "build_seasonal_areas.py"
sys.path.insert(0, str(ROOT / "scripts"))
import build_seasonal_areas as gen  # noqa: E402

VARIANTS = gen.VARIANTS

# Rooms, mobiles and objects the game cannot do without, by base file.
CRITICAL = {
    "dresden": {"ROOMS": {4207, 4208, 4216, 2401, 4649}, "MOBILES": {7551}, "OBJECTS": set()},
    "limbo": {"ROOMS": {1, 2, 8, 9}, "MOBILES": {97, 98}, "OBJECTS": set()},
    "midennir": {"ROOMS": set(), "MOBILES": set(), "OBJECTS": set()},
}


def section_records(path: Path, name: str) -> dict[int, list[str]]:
    for sname, body in gen.sections(gen.read(path)):
        if sname == name:
            return gen.records(body)[1]
    return {}


def world_vnums(name: str, skip: set[str]) -> set[int]:
    out: set[int] = set()
    for entry in (AREA / "area.lst").read_text(encoding="latin-1").split("\n"):
        entry = entry.strip()
        if not entry or entry.startswith(("#", "$")) or entry in skip or not (AREA / entry).is_file():
            continue
        out |= set(section_records(AREA / entry, name))
    return out


class SeasonalAreaTests(unittest.TestCase):
    def test_the_generator_reproduces_every_committed_copy(self) -> None:
        result = subprocess.run([sys.executable, str(SCRIPT), "--check"],
                                capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_each_copy_holds_everything_its_base_holds(self) -> None:
        """Every room, mobile and object of the base, and every object
        identical to the base's: a season decorates, it never removes, and
        prices and stats are the base's."""
        for base, tag in VARIANTS:
            for name in ("ROOMS", "MOBILES", "OBJECTS"):
                with self.subTest(variant=f"{base}_{tag}", section=name):
                    b = section_records(AREA / f"{base}.are", name)
                    s = section_records(AREA / f"{base}_{tag}.are", name)
                    missing = set(b) - set(s)
                    self.assertEqual(missing, set(), f"missing from {base}_{tag}: {sorted(missing)[:10]}")
                    if name == "OBJECTS":
                        differing = [v for v in b if s[v] != b[v]]
                        self.assertEqual(differing, [], f"objects differing from base in {base}_{tag}: {differing[:10]}")

    def test_the_rooms_and_mobiles_differ_from_the_base_only_in_text(self) -> None:
        """...and, for a room, in the extra descriptions the overlay adds."""
        for base, tag in VARIANTS:
            overlay = json.loads((gen.DATA / f"{base}_{tag}.json").read_text(encoding="utf-8"))
            for name in ("ROOMS", "MOBILES"):
                b = section_records(AREA / f"{base}.are", name)
                s = section_records(AREA / f"{base}_{tag}.are", name)
                extras = overlay.get("extras", {}).get(name, {})
                for vnum in b:
                    with self.subTest(variant=f"{base}_{tag}", section=name, vnum=vnum):
                        n = gen.TEXT_FIELDS[name]
                        srec = gen.without_extras(s[vnum], extras.get(str(vnum), []))
                        self.assertEqual(b[vnum][gen.text_fields(b[vnum], n):],
                                         srec[gen.text_fields(srec, n):],
                                         "numbers, exits or stats differ from the base")

    def test_the_critical_records_are_present(self) -> None:
        for base, tag in VARIANTS:
            for name, vnums in CRITICAL[base].items():
                present = set(section_records(AREA / f"{base}_{tag}.are", name))
                with self.subTest(variant=f"{base}_{tag}", section=name):
                    self.assertEqual(vnums - present, set())

    def test_a_seasonal_only_record_collides_with_nothing(self) -> None:
        """The old Halloween limbo carried the Quest Master, who lives in
        dresden: loading him twice is a fatal duplicate at boot."""
        for base, tag in VARIANTS:
            overlay = json.loads((gen.DATA / f"{base}_{tag}.json").read_text(encoding="utf-8"))
            for name, recs in overlay.get("records", {}).items():
                elsewhere = world_vnums(name, skip={f"{base}.are"})
                clash = {int(v) for v in recs} & elsewhere
                with self.subTest(variant=f"{base}_{tag}", section=name):
                    self.assertEqual(clash, set())

    def test_the_overlay_resets_name_only_seasonal_records(self) -> None:
        for base, tag in VARIANTS:
            overlay = json.loads((gen.DATA / f"{base}_{tag}.json").read_text(encoding="utf-8"))
            seasonal = {int(v) for recs in overlay.get("records", {}).values() for v in recs}
            for line in overlay.get("resets", []):
                with self.subTest(variant=f"{base}_{tag}", reset=line):
                    self.assertTrue(gen.vnums_in(line) & seasonal, "a base reset does not belong in the overlay")

    def test_season_c_names_exactly_these_files(self) -> None:
        source = (ROOT / "src" / "season.c").read_text(encoding="latin-1")
        named = set(re.findall(r'return "([a-z]+_(?:halloween|xmas)\.are)"', source))
        self.assertEqual(named, {f"{b}_{t}.are" for b, t in VARIANTS})


try:
    from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason
    SKIP = skip_reason()
except ImportError as exc:  # pragma: no cover - the module runs from tests/
    SKIP = str(exc)


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class SeasonBootTests(unittest.TestCase):
    """TOC_SEASON forces a season on; the fixture forces it off."""

    def test_hallows_end_boots_whole_and_a_death_has_somewhere_to_go(self) -> None:
        with LiveMud(extra_env={"TOC_SEASON": "halloween", "TOC_NO_BOOT_HERMIE": None}) as mud:
            for name, level in (("Zghoul", 20), ("Zreaper", 70)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, "Zseason1")
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=4207)
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as keeper:
                login(hero, "Zghoul", "Zseason1")
                login(keeper, "Zreaper", "Zseason1")
                run(keeper, "scroll 0", 1.0)           # MSHOW pages; a page eats the next command
                # The Oak Tree Square wears its pumpkins; Hermie and the Oracle exist.
                self.assertIn("pumpkins", run(keeper, "goto 2401", 2.0))
                # The decorations answer LOOK (players tried "look pump").
                self.assertIn("carved", run(keeper, "look pumpkins", 1.6))
                self.assertIn("knocking", run(keeper, "goto 4209", 2.0))
                self.assertIn("undertaker", run(keeper, "look coffins", 1.6))
                self.assertIn("Hermie", run(keeper, "mshow 98", 1.6))
                self.assertIn("Oracle", run(keeper, "mshow 97", 1.6))
                self.assertIn("Quest Master", run(keeper, "mshow 7551", 1.6))
                # The death room is there, and a death lands in it.
                run(keeper, "goto 4207", 2.0)
                mark = len(hero.transcript)
                keeper.send("slay zghoul")
                hero.drain(2.5)
                self.assertIn("first true death", hero.transcript[mark:])
                self.assertIn("Death room", run(hero, "look", 2.0))
            booted = mud.server_output()
            self.assertIn("Hermie placed", booted)
            self.assertNotIn("BUG", booted)

    def test_winter_veil_boots_whole(self) -> None:
        with LiveMud(extra_env={"TOC_SEASON": "xmas"}) as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zelf", "Zseason1")
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zelf", Levl=70, Room=4207)
            with mud.connect(timeout=120) as imm:
                login(imm, "Zelf", "Zseason1")
                run(imm, "scroll 0", 1.0)
                self.assertIn("Christmas Tree Square", run(imm, "goto 2401", 2.0))
                self.assertIn("Quest Master", run(imm, "mshow 7551", 1.6))
                self.assertIn("Death room", run(imm, "goto 4216", 2.0))
            self.assertNotIn("BUG", mud.server_output())


if __name__ == "__main__":
    unittest.main()

"""Area names credit the builder after the zone, so lists sort by zone.

`#AREA { 5 15} Alfa    Moria~` carries the level range, the builder's
handle and the name in one line, handle first. Anything that sorted on
that string sorted by whoever built the place: Alfa's Moria filed under
A, which is not how a player looks for a zone.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "webadmin"))

from area_parser import format_area_name, split_area_name  # noqa: E402


class SplitAreaNameTests(unittest.TestCase):
    def test_a_wide_gap_is_the_builders_own_separator(self) -> None:
        """105 of the 124 areas write it this way, and it is unambiguous."""
        self.assertEqual(("Alfa", "Moria"), split_area_name("Alfa    Moria"))
        self.assertEqual(("Drakk", "City of Dresden"),
                         split_area_name("Drakk   City of Dresden"))

    def test_a_single_space_leaves_the_first_word_as_the_handle(self) -> None:
        """The other 19. "Generic" and "Unknown" are handles too."""
        for raw, expected in (
            ("Hatchet Mud School", ("Hatchet", "Mud School")),
            ("Generic Old Marsh", ("Generic", "Old Marsh")),
            ("Unknown The Tombs of Tarin", ("Unknown", "The Tombs of Tarin")),
            ("Killum Hyrule", ("Killum", "Hyrule")),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(expected, split_area_name(raw))

    def test_a_lone_word_is_all_name_and_no_handle(self) -> None:
        """Rather than crediting a builder the line never named."""
        self.assertEqual(("", "Limbo"), split_area_name("Limbo"))
        self.assertEqual(("", ""), split_area_name(""))
        self.assertEqual(("", ""), split_area_name("   "))

    def test_the_zone_comes_first_when_formatted(self) -> None:
        self.assertEqual("Moria (Alfa)", format_area_name("Alfa    Moria"))
        self.assertEqual("Mud School (Hatchet)",
                         format_area_name("Hatchet Mud School"))
        # Nothing to credit, nothing in brackets.
        self.assertEqual("Limbo", format_area_name("Limbo"))

    def test_every_listed_area_splits_into_both_halves(self) -> None:
        """A silent regression here would recredit the whole world."""
        listed = {line.strip() for line
                  in (ROOT / "area" / "area.lst").read_text("latin-1").splitlines()}
        seen = 0
        uncredited = []
        for path in sorted((ROOT / "area").glob("*.are")):
            if path.name not in listed:
                continue
            found = re.search(r"#AREA\s+([^\n]+?)~", path.read_text("latin-1"))
            if not found:
                continue
            rest = re.match(r"\{(.*?)\}\s*(.*)", found.group(1).strip())
            raw = rest.group(2).strip() if rest else found.group(1).strip()
            builder, zone = split_area_name(raw)
            seen += 1
            if not builder or not zone:
                uncredited.append((path.name, raw))

        self.assertGreater(seen, 80, "found almost no areas; the glob is wrong")
        self.assertEqual([], uncredited)


class PublishedDirectionsTests(unittest.TestCase):
    """The generated file the dashboard and the client both read."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(
            (ROOT / "webadmin" / "directions.json").read_text("utf-8"))

    def test_a_route_is_named_for_its_zone_not_its_builder(self) -> None:
        for route in self.data["routes"]:
            with self.subTest(area=route["area"]):
                self.assertEqual(format_area_name(route["area"]), route["name"])

    def test_the_raw_area_is_kept_beside_the_display_name(self) -> None:
        """match_area() and the parity test both compare against it, so
        it must stay exactly as the area file writes it."""
        for route in self.data["routes"]:
            with self.subTest(area=route["area"]):
                self.assertIn("area_display", route)
                self.assertNotEqual("", route["area"])

    def test_commands_stay_single_semicolon_in_the_data(self) -> None:
        """Mudlet's doubled separator is a display choice made in the
        browser. Baking it into the feed would break the in-client send
        button and every existing consumer."""
        for group in ("routes", "legacy"):
            for route in self.data.get(group, []):
                for field in ("commands", "fixed_commands"):
                    text = route.get(field) or ""
                    with self.subTest(route=route["name"], field=field):
                        self.assertNotIn(";;", text)


if __name__ == "__main__":
    unittest.main()

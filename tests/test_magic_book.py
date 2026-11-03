"""The Magic Book holds every recipe (owner, 2026-11-03).

READ or OPEN Hyrule's Magic Book (object 30415) and it shows every
recipe BREW, CONCOCT and SCRIBE know -- written from the recipe table
itself (craft_recipe_book in magic2.c), so it cannot list one the game
does not make or miss one it does. This reads the table from the source,
opens the book live, and checks every recipe is there with its
ingredients, that no line runs past the screen, and that the book pages.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zbookpass1"
TEMPLE = 4207
BOOK = 30415
NOUNS = {"CRAFT_BREW": "tea", "CRAFT_CONCOCT": "potion", "CRAFT_SCRIBE": "scroll"}


def recipes() -> list[tuple[str, str, list[int]]]:
    source = (ROOT / "src" / "magic2.c").read_text(encoding="latin-1")
    table = source[source.index("static const CRAFT_RECIPE craft_recipes[] ="):]
    table = table[:table.index("\n};")]
    found = []
    for m in re.finditer(r'\{ (CRAFT_\w+), \{ (\d+), (\d+), (\d+) \}, \{[^}]*\}, "([^"]+)"', table):
        parts = [int(v) for v in m.group(2, 3, 4) if int(v)]
        found.append((m.group(5), NOUNS[m.group(1)], parts))
    return found


def object_names() -> dict[int, str]:
    text = (ROOT / "area" / "limbo.are").read_text(encoding="latin-1").replace("\r\n", "\n")
    objects = text[text.index("#OBJECTS"):text.index("#ROOMS")]
    return {int(v): short for v, short in
            re.findall(r"\n#(\d+)\n[^~]*~\n([^~]*)~", objects)}


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def plain(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text).replace("\r", "")


class MagicBookSourceTests(unittest.TestCase):
    def test_the_table_reads_as_fifty_two_recipes(self) -> None:
        self.assertEqual(len(recipes()), 52)


@unittest.skipIf(SKIP is not None, SKIP or "")
class MagicBookLiveTests(unittest.TestCase):
    def test_read_and_open_show_every_recipe(self) -> None:
        names = object_names()
        with LiveMud() as mud:
            make(mud, "Zbookstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zbookworm", Levl=50, Room=TEMPLE)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as reader:
                login(staff, "Zbookstaff", PW)
                login(reader, "Zbookworm", PW)
                staff.sync("scroll 0")
                reader.sync("scroll 0")
                staff.must(f"load obj {BOOK}", "You create")
                staff.must("give book zbookworm", "You give")

                page = plain(reader.sync("read book"))
                self.assertIn("T H E   M A G I C   B O O K", page)
                for header in ("BREW", "CONCOCT", "SCRIBE"):
                    self.assertRegex(page, rf"\n{header} +\S")
                flat = re.sub(r"\s+", " ", page)
                missing = []
                for colour, noun, parts in recipes():
                    shown = " + ".join(names[v] for v in parts)
                    if f"{colour} {noun}" not in flat or f"from {shown}" not in flat:
                        missing.append(f"{colour} {noun}: {shown}")
                self.assertEqual(missing, [])
                self.assertIn("(one in four goes bad)", flat)
                self.assertIn("(cast at half your level)", flat)
                wide = [line for line in page.split("\n")
                        if len(re.sub(r"^<[^>]*> ", "", line)) > 79]
                self.assertEqual(wide, [])

                # OPEN shows the same pages; colour off draws the same text.
                self.assertIn("feathered gold potion", re.sub(r"\s+", " ",
                              plain(reader.sync("open book"))))
                reader.sync("color")
                self.assertNotIn("\x1b[", reader.sync("read book"))

                # With paging on, the book pages instead of flooding.
                reader.sync("scroll 30")
                reader.send("read book")
                reader.expect("Hit Return to continue", timeout=30)

                # No line ends in a space where a long list wrapped.
                self.assertEqual([l for l in page.split("\n") if l.endswith(" ")
                                  and not l.startswith("<")], [])


if __name__ == "__main__":
    unittest.main()

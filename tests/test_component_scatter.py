"""Herbs and spell components, and the room lottery that stopped them landing.

`component_update()` picked where to put things by guessing a vnum between
0 and 65535 and asking whether a room lived there. With 7,781 rooms in
play that finds *a* room about one try in eight, and a room inside an
area already chosen about one try in eight hundred. The inner loop gave up
after a hundred tries, which it did roughly nine times in ten, so most of
what the function meant to scatter was never placed. The COMPONENT command
said "New Components Scattered!" either way, so there was nothing to go on.

Now it walks the room hash once and samples, which always answers; the
command counts before and after and prints both numbers; and the rate is
much lower than it would otherwise have become, with nothing scattered at
all while nobody is logged in.
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

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]

PASSWORD = "Zcomp1"
MUD_SCHOOL = 3700

HERB_CEILING = 40
COMPONENT_CEILING = 25


def run(client, command: str, settle: float = 3.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def holdings(text: str) -> tuple[int, int]:
    found = re.search(r"holds (\d+) of \d+ herbs and (\d+) of \d+ components",
                      text)
    assert found is not None, text
    return int(found.group(1)), int(found.group(2))


@unittest.skipIf(SKIP is not None, SKIP or "")
class ComponentScatterTests(unittest.TestCase):
    def test_the_command_scatters_and_says_how_much(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zcomp", PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zcomp", Levl=70, Room=MUD_SCHOOL)

            with mud.connect(timeout=120) as client:
                login(client, "Zcomp", PASSWORD)

                first = run(client, "component")
                self.assertRegex(first, r"Scattered \d+ herbs?")
                herbs, comps = holdings(first)
                self.assertGreater(herbs, 0, "nothing landed:\n" + first)

                # It accumulates towards the ceiling rather than flatlining.
                for _ in range(4):
                    later = run(client, "component")
                grew_h, grew_c = holdings(later)
                self.assertGreater(grew_h, herbs)
                self.assertLessEqual(grew_h, HERB_CEILING)
                self.assertLessEqual(grew_c, COMPONENT_CEILING)

    def test_a_scattered_herb_is_somewhere_real(self) -> None:
        """The lottery could leave the room pointer at a vnum in another
        area entirely, so this checks one actually exists to be found."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zfinder", PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zfinder", Levl=70, Room=MUD_SCHOOL)

            with mud.connect(timeout=120) as client:
                login(client, "Zfinder", PASSWORD)
                for _ in range(4):
                    run(client, "component")

                found = ""
                for keyword in ("mandrake", "root", "leaf", "herb", "bloom"):
                    found = run(client, "owhere " + keyword, 2.5)
                    if "Room [" in found:
                        break
                self.assertIn("Room [", found, found[-500:])


class ComponentSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.update = (ROOT / "src" / "update.c").read_text(encoding="utf-8")
        cls.db = (ROOT / "src" / "db.c").read_text(encoding="utf-8")
        cls.wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="utf-8")

    def scatterer(self) -> str:
        body = self.update.split("void component_update( void )", 1)[1]
        return body.split("\nvoid ", 1)[0]

    def test_the_vnum_lottery_is_gone(self) -> None:
        body = self.scatterer()
        self.assertNotIn("number_range( 0, 65535 )", body)
        self.assertNotIn("attempts", body)
        self.assertEqual(body.count("random_scatter_room"), 4)
        self.assertIn("ROOM_INDEX_DATA *random_scatter_room", self.db)

    def test_the_picker_skips_rooms_nothing_should_lie_in(self) -> None:
        picker = self.db.split("ROOM_INDEX_DATA *random_scatter_room", 1)[1]
        picker = picker.split("\n}", 1)[0]
        for flag in ("ROOM_DT", "ROOM_JAIL", "ROOM_PRIVATE", "ROOM_SOLITARY",
                     "ROOM_IMP_ONLY", "ROOM_GODS_ONLY"):
            with self.subTest(flag=flag):
                self.assertIn(flag, picker)

    def test_nothing_is_scattered_into_an_empty_world(self) -> None:
        self.assertIn("telnet_count_players() < 1", self.scatterer())

    def test_the_ceilings_are_named_and_low(self) -> None:
        body = self.scatterer()
        self.assertIn("HERB_CEILING", body)
        self.assertIn("COMPONENT_CEILING", body)
        self.assertNotIn("250", body)
        self.assertNotIn("200", body)

        merc = (ROOT / "src" / "merc.h").read_text(encoding="utf-8")
        self.assertIn("#define HERB_CEILING            %d" % HERB_CEILING,
                      merc)
        self.assertIn(
            "#define COMPONENT_CEILING       %d" % COMPONENT_CEILING, merc)

    def test_the_command_reports_what_it_did(self) -> None:
        body = self.wiz.split("void do_component_update", 1)[1]
        body = body.split("\nvoid ", 1)[0]
        self.assertIn("count_components", body)
        self.assertNotIn("New Components Scattered!", body)


if __name__ == "__main__":
    unittest.main()

"""In-game building, phase 3: SET MOB <vnum> edits a prototype in words.

A blank mobile is made into a dwarf smith field by field, every value
given by name -- race, sex, size, attack, flags, positions, special -- and
checked through MSHOW, which prints the same words SET takes. The edits
apply load_mobiles' own level clamps at once and refuse to take away a
race's natural flags, so what MSHOW shows before a save is what the game
loads after one: the test saves, reboots, and compares.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Zbuildpw3"
LO, HI = 21100, 21119
ROOM = 21101
MOB = 21103


def run(client, command: str, settle: float = 1.0) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def sheet(text: str) -> str:
    """MSHOW's own output: from its first line to its closing note."""
    text = re.sub(r"\x1b\[[0-9;]*m", "", text.replace("\r", ""))
    start = text.find(f"Mobile {MOB}, in")
    end = text.find("(Mobiles already loaded", start)
    assert start >= 0 and end > start, "no MSHOW sheet in: " + text
    return text[start:end]


def field(sheet_text: str, name: str) -> str:
    match = re.search(rf"^{name}:\s*(.*)$", sheet_text, re.M)
    return match.group(1).strip() if match else ""


@unittest.skipIf(SKIP is not None, SKIP or "")
class MobEditTests(unittest.TestCase):
    def test_a_mobile_built_in_words_survives_a_reboot(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zbuildthree", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zbuildthree", Levl=70, Room=4207)

            with mud.connect(timeout=120) as imm:
                login(imm, "Zbuildthree", PASSWORD)
                run(imm, "scroll 0")
                self.assertIn("Created area", run(imm, f"anew {LO} {HI} Zed Edit Works"))
                run(imm, f"goto {ROOM}", 1.5)
                run(imm, "rlink north 21102", 1.5)
                self.assertIn("blank level 1", run(imm, f"mcreate {MOB}"))

                # A shipped prototype cannot be edited: it could never be saved.
                self.assertIn("came with the game", run(imm, "set mob 4444 level 3"))

                for command in (
                    "keywords dwarf smith",
                    "short a burly dwarf smith",
                    "long a burly dwarf smith hammers at an anvil here.",
                    "desc Soot covers his arms to the elbow, and his beard is "
                    "singed short.",
                    "desc + He does not look up.",
                    "race dwarf",
                    "sex male",
                    "size small",
                    "hp 4d10+80",
                    "damage 2d6",
                    "attack flaming_bite",
                    "act +aggressive +sentinel",
                    "act -sentinel",
                    "offense +parry +dodge",
                    "immune +fire",
                    "alignment evil",
                    "wealth 500",
                    "position sleeping",
                    "default resting",
                    "special cast_mage",
                    "material iron",
                ):
                    out = run(imm, f"set mob {MOB} {command}")
                    self.assertIn("is set", out, f"{command!r}: {out}")

                # Level applies load_mobiles' clamps at once and says so.
                out = run(imm, f"set mob {MOB} level 20")
                self.assertIn("Hitroll raised to 10", out, out)
                self.assertIn("Damage bonus raised to 15", out, out)
                self.assertIn("Armour brought down to -20", out, out)

                # Refusals name what went wrong.
                self.assertIn("no act flag called 'flibble'",
                              run(imm, f"set mob {MOB} act +flibble"))
                self.assertIn("part of being a dwarf",
                              run(imm, f"set mob {MOB} affect -infrared"))
                self.assertIn("dice", run(imm, f"set mob {MOB} hp lots"))
                self.assertIn("Sex is", run(imm, f"set mob {MOB} sex maybe"))

                before = sheet(run(imm, f"mshow {MOB}", 1.5))
                self.assertEqual(field(before, "race"), "dwarf   sex: male   size: small"
                                 "   material: iron")
                self.assertIn("damage: 2d6+15   attack: flaming bite", before)
                self.assertIn("hp: 4d10+80", before)
                self.assertIn("alignment: -1000", before)
                self.assertIn("position: sleeping   default: resting   wealth: 500", before)
                self.assertEqual(field(before, "act"), "aggressive")
                self.assertIn("parry", field(before, "offense"))
                self.assertIn("infrared", field(before, "affect"))
                self.assertIn("fire", field(before, "immune"))
                self.assertIn("special: spec_cast_mage", before)
                self.assertIn("Soot covers his arms", before)
                self.assertIn("He does not look up.", before)

                self.assertIn("Saved Zed Edit Works", run(imm, "asave", 2.0))
                imm.send("quit")
                self.assertTrue(imm.wait_closed())

            mud.restart()

            with mud.connect(timeout=120) as imm:
                login(imm, "Zbuildthree", PASSWORD)
                run(imm, "scroll 0")
                after = sheet(run(imm, f"mshow {MOB}", 1.5))
                self.assertEqual(after, before, "the prototype changed across a reboot")

                run(imm, f"goto {ROOM}", 1.5)
                run(imm, f"load mob {MOB}", 1.5)
                self.assertIn("A burly dwarf smith hammers at an anvil here.",
                              run(imm, "look", 1.5))


if __name__ == "__main__":
    unittest.main()

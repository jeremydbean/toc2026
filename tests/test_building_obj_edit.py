"""In-game building, phase 4: SET OBJ <vnum> edits a prototype in words.

Four blank objects become a runed sword, a potion, a chest and a jug of
beer, every value given by name: the type, the wear slots and flags, and
the values that type gives meaning to (a weapon's class, dice and attack;
a potion's spells; a container's lid and key; a drink's liquid). Affects
and worn powers are refused while a copy is being worn, because equip and
unequip read them from the prototype. OSHOW prints the same words SET
takes; the test saves, reboots and compares every sheet.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Zbuildpw4"
LO, HI = 21200, 21219
ROOM = 21201
SWORD, POTION, CHEST, JUG = 21203, 21204, 21205, 21206


def run(client, command: str, settle: float = 1.0) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def sheet(text: str, vnum: int) -> str:
    text = re.sub(r"\x1b\[[0-9;]*m", "", text.replace("\r", ""))
    start = text.find(f"Object {vnum}, in")
    end = text.find("(Objects already made", start)
    assert start >= 0 and end > start, "no OSHOW sheet in: " + text
    return text[start:end]


BUILD = {
    SWORD: (
        "keywords sword runed",
        "short a runed sword",
        "long A runed sword lies here.",
        "type weapon",
        "class sword",
        "dice 3d6",
        "attack slash",
        "weapon +sharp +flaming",
        "wear +take +wield",
        "flags +glow +magic",
        "level 15",
        "weight 8",
        "cost 5g 20s",
        "condition good",
        "material steel",
        "affect +hitroll 2",
        "affect +damroll 3",
        "affect -damroll",
        "grants +haste",
        "detail runes They spell out a name nobody remembers.",
        "desc The blade is etched from hilt to point.",
    ),
    POTION: (
        "keywords potion red",
        "short a red potion",
        "long A red potion sits here.",
        "type potion",
        "spell level 20",
        "spells 'cure light' armor",
    ),
    CHEST: (
        "keywords chest iron",
        "short an iron chest",
        "long An iron chest squats in the corner.",
        "type container",
        "capacity 100",
        "container +closeable +closed",
        f"key {SWORD}",
    ),
    JUG: (
        "keywords jug",
        "short a clay jug",
        "long A clay jug stands here.",
        "type drink",
        "capacity 10",
        "amount full",
        "liquid beer",
    ),
}


@unittest.skipIf(SKIP is not None, SKIP or "")
class ObjEditTests(unittest.TestCase):
    def test_objects_built_in_words_survive_a_reboot(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zbuildfour", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zbuildfour", Levl=70, Room=4207)

            with mud.connect(timeout=120) as imm:
                login(imm, "Zbuildfour", PASSWORD)
                run(imm, "scroll 0")
                self.assertIn("Created area", run(imm, f"anew {LO} {HI} Zed Forge Works"))
                run(imm, f"goto {ROOM}", 1.5)
                run(imm, "rlink north 21202", 1.5)

                for vnum, commands in BUILD.items():
                    self.assertIn("blank piece", run(imm, f"ocreate {vnum}"))
                    for command in commands:
                        out = run(imm, f"set obj {vnum} {command}")
                        self.assertIn("is set", out, f"{vnum} {command!r}: {out}")

                # Refusals.
                self.assertIn("came with the game", run(imm, "set obj 3021 level 2"))
                self.assertIn("weapon has no field 'hours'",
                              run(imm, f"set obj {SWORD} hours 5"))
                self.assertIn("Give a price", run(imm, f"set obj {SWORD} cost lots"))
                self.assertIn("not a spell an item can hold",
                              run(imm, f"set obj {POTION} spells flibble"))

                # A worn copy pins the prototype's affects.
                run(imm, f"load obj {SWORD}", 1.5)
                run(imm, "wield sword", 1.5)
                self.assertIn("Somebody is wearing",
                              run(imm, f"set obj {SWORD} affect +hitroll 1"))
                run(imm, "remove sword", 1.5)
                run(imm, "drop sword", 1.5)
                run(imm, "purge", 1.5)

                sheets = {v: sheet(run(imm, f"oshow {v}", 1.5), v) for v in BUILD}
                sword = sheets[SWORD]
                self.assertIn("type: weapon   level: 15   weight: 8   cost: 5g 20s", sword)
                self.assertIn("condition: good   material: steel", sword)
                self.assertIn("wear:  take wield", sword)
                self.assertIn("flags: glow magic", sword)
                self.assertIn("class: sword   dice: 3d6 (average 10)   attack: slash", sword)
                self.assertIn("weapon: flaming sharp", sword)
                self.assertIn("affects: +2 hitroll", sword)
                self.assertNotIn("damroll", sword)
                self.assertIn("grants:  haste", sword)
                self.assertIn("details: runes, sword runed", sword)
                self.assertIn("spells: 'cure light' 'armor' 'none'", sheets[POTION])
                self.assertIn("spell level: 20", sheets[POTION])
                self.assertIn(f"capacity: 100   container: closeable closed   key: {SWORD}",
                              sheets[CHEST])
                self.assertIn("capacity: 10   amount: 10   liquid: beer", sheets[JUG])

                self.assertIn("Saved Zed Forge Works", run(imm, "asave", 2.0))
                imm.send("quit")
                self.assertTrue(imm.wait_closed())

            mud.restart()

            with mud.connect(timeout=120) as imm:
                login(imm, "Zbuildfour", PASSWORD)
                run(imm, "scroll 0")
                for vnum, before in sheets.items():
                    self.assertEqual(sheet(run(imm, f"oshow {vnum}", 1.5), vnum), before,
                                     f"object {vnum} changed across a reboot")

                run(imm, f"load obj {SWORD}", 1.5)
                self.assertIn("nobody remembers", run(imm, "look runes", 1.5))
                self.assertIn("etched from hilt to point", run(imm, "look sword", 1.5))


if __name__ == "__main__":
    unittest.main()

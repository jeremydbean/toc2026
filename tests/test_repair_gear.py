"""Repairing gear, including the gear you are wearing.

The help for REPAIR says it "requests repairs from an NPC repair vendor on
worn equipment", but do_repair looked the item up with get_obj_carry, which
skips anything whose wear_loc is set. Damaged armour is normally still on
your body -- damage_eq only strips a piece once its condition drops below
zero -- so the common case answered "You aren't carrying that!" about a
sword the character was holding.

These run against a real server in a throwaway tree.
"""
from __future__ import annotations

import re
import unittest

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Zrepair1"
IMMORTAL_LEVEL = 70

# The dwarven blacksmith, mob 51, carries ACT2_REPAIR and is reset into
# the Smithy in limbo.are. He is one of five repairers in the world.
SMITHY_ROOM = 2490


def staff(mud: LiveMud, name: str, room: int, gold: int = 500) -> None:
    """A staff character, standing where the test needs it, able to pay.

    Staff level is only so `load obj` and `set obj` are available; the
    repair itself is an ordinary player action and is charged for.
    """
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError("character did not leave the world")
    patch_player_file(mud, name, Levl=IMMORTAL_LEVEL, Room=room,
                      NewGold=gold)


def run(client, command: str, settle: float = 1.2) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class RepairTests(unittest.TestCase):
    def test_a_worn_item_can_be_repaired_without_removing_it(self) -> None:
        with LiveMud() as mud:
            staff(mud, "Zrepairone", SMITHY_ROOM)
            with mud.connect(timeout=120) as client:
                login(client, "Zrepairone", PASSWORD)

                # Something wearable, damaged, and still on the body.
                run(client, "load obj 3355")          # a vest
                run(client, "wear vest")
                worn = run(client, "equipment")
                self.assertIn("vest", worn.lower(),
                              "the vest should be worn for this test")

                run(client, "set obj vest condition 40")
                said = run(client, "repair vest", settle=2.0)

        self.assertNotIn("aren't carrying", said.lower(),
                         "a worn item should be repairable where it is")
        self.assertIn("repairs your", said.lower())

    def test_an_item_in_the_pack_still_repairs(self) -> None:
        with LiveMud() as mud:
            staff(mud, "Zrepairtwo", SMITHY_ROOM)
            with mud.connect(timeout=120) as client:
                login(client, "Zrepairtwo", PASSWORD)
                run(client, "load obj 3355")
                run(client, "set obj vest condition 40")
                said = run(client, "repair vest", settle=2.0)

        self.assertIn("repairs your", said.lower())

    def test_the_quote_is_written_in_coins(self) -> None:
        """Prices are counted in copper now, so a bare number is a lie."""
        with LiveMud() as mud:
            staff(mud, "Zrepairfee", SMITHY_ROOM)
            with mud.connect(timeout=120) as client:
                login(client, "Zrepairfee", PASSWORD)
                run(client, "load obj 3355")
                run(client, "set obj vest condition 40")
                said = run(client, "repair vest", settle=2.0)

        cost_line = [l for l in said.splitlines() if "cost you" in l.lower()]
        self.assertTrue(cost_line, "the repair should say what it cost:\n" + said)
        self.assertRegex(
            cost_line[0], r"\d+\s*[pgsc]\b",
            "the price should name denominations, not a bare number")

    def test_repair_restores_armour_filed_down_by_damage(self) -> None:
        """A dented shield loses a point of AC and two thirds of its worth.

        check_shield_block does that permanently; nothing used to put it
        back, so a shield that had been repaired ten times was ten points
        worse than the one on the shelf. Repair now restores both, up to
        -- never past -- the prototype it was made from.
        """
        with LiveMud() as mud:
            # A level 25 helmet at condition 20 quotes 10,000 gold.
            staff(mud, "Zrepairac", SMITHY_ROOM, gold=50000)
            with mud.connect(timeout=120) as client:
                login(client, "Zrepairac", PASSWORD)
                # A helmet with real armour values and a real price; the
                # Mud School vest is worth nothing, so nothing to restore.
                run(client, "load obj 4619")
                before = run(client, "stat obj helmet", settle=1.5)

                # Stand in for a beating: file the armour down and cut
                # the price the way a damaged shield gets cut.
                run(client, "set obj helmet v0 0")
                run(client, "set obj helmet cost 1")
                run(client, "set obj helmet condition 20")

                run(client, "repair helmet", settle=2.0)
                after = run(client, "stat obj helmet", settle=1.5)

        def cost_of(text: str) -> int:
            m = re.search(r"Cost:\s*(-?\d+)", text)
            if not m:
                raise AssertionError("no Cost in stat output:\n" + text)
            return int(m.group(1))

        def first_value(text: str) -> int:
            m = re.search(r"Values:\s*(-?\d+)", text)
            if not m:
                raise AssertionError("no Values in stat output:\n" + text)
            return int(m.group(1))

        self.assertEqual(
            cost_of(before), cost_of(after),
            "repair should restore the worth the damage took off")
        self.assertEqual(
            first_value(before), first_value(after),
            "repair should restore the armour value the damage filed down")

    def test_an_undamaged_item_is_refused(self) -> None:
        with LiveMud() as mud:
            staff(mud, "Zrepairok", SMITHY_ROOM)
            with mud.connect(timeout=120) as client:
                login(client, "Zrepairok", PASSWORD)
                run(client, "load obj 3355")
                said = run(client, "repair vest", settle=2.0)

        self.assertIn("perfect condition", said.lower())

    def test_nothing_to_repair_with_reports_honestly(self) -> None:
        with LiveMud() as mud:
            staff(mud, "Zrepairnil", SMITHY_ROOM)
            with mud.connect(timeout=120) as client:
                login(client, "Zrepairnil", PASSWORD)
                said = run(client, "repair nosuchthing", settle=1.5)

        self.assertIn("carrying or wearing", said.lower())

    def test_away_from_a_smith_it_says_so(self) -> None:
        with LiveMud() as mud:
            # Oak Tree Square has no repairer.
            staff(mud, "Zrepairfar", 2401)
            with mud.connect(timeout=120) as client:
                login(client, "Zrepairfar", PASSWORD)
                run(client, "load obj 3355")
                run(client, "set obj vest condition 40")
                said = run(client, "repair vest", settle=2.0)

        self.assertIn("nobody here to repair", said.lower())


if __name__ == "__main__":
    unittest.main()

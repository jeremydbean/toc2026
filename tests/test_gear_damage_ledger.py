"""REPAIR puts back what damage took, and no more (review, 2026-10-22, G2).

A level -1 prototype's armour is rolled at creation, and the roll was
never recorded, so REPAIR could only restore a piece to the least the
roll can make: a vest made 6/6/6/1 and etched to 5/5/5/0 came back
5/5/5/1, and every cycle wore it further towards the floor. Damage now
records the points it files off in a per-piece ledger (gear_file_armor,
saved as ArmorLost) and REPAIR adds exactly those back. The floor stays
as the backstop for pieces damaged before the ledger existed, so old kit
repairs as it always did and nothing gets a free upgrade.

Played live: acid breath on a randomized vest and a fixed-level helmet,
a quit and a fresh login in between (the ledger must survive the save),
then REPAIR ALL at the smith. Values are read from the saved file, and
the wearer's armour class from STAT, before the damage and after the
repair.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PASSWORD = "Zledger1"
SMITHY = 2490           # the dwarven blacksmith, an ACT2_REPAIR mobile
VEST = 616              # a leather vest, level -1: values rolled at creation
HELMET = 4619           # a great war helmet, level 25: prototype values 8 7 8 0
HELMET_VALUES = [8, 7, 8, 0]


def run(client, command: str, settle: float = 1.2) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud: LiveMud, name: str, level: int, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Levl=level, Room=SMITHY, **fields)


def armour_on_file(mud: LiveMud, name: str, prototypes: dict) -> list:
    """[(vnum, values[4], lost[4])] for each carried armour piece, in file
    order. A value the file omits is the prototype's (save.c writes Val
    only when it differs); a missing ArmorLost is no damage."""
    pieces = []
    vnum = values = lost = None
    for line in (mud.player_dir / name).read_text(encoding="latin-1").splitlines():
        if line.startswith("#O"):
            vnum, values, lost = None, None, [0, 0, 0, 0]
        elif line.startswith("Vnum "):
            vnum = int(line.split()[1])
        elif line.startswith("Val "):
            values = [int(v) for v in line.split()[1:5]]
        elif line.startswith("ArmorLost "):
            lost = [int(v) for v in line.split()[1:5]]
        elif line == "End" and vnum in prototypes:
            pieces.append((vnum, values or list(prototypes[vnum]), lost))
            vnum = None
    return pieces


def armour_class(text: str) -> tuple:
    m = re.search(r"Armor:\s*pierce:\s*(-?\d+)\s+bash:\s*(-?\d+)\s+slash:\s*(-?\d+)\s+magic:\s*(-?\d+)", text)
    if not m:
        raise AssertionError("no Armor line in stat output:\n" + text)
    return tuple(int(g) for g in m.groups())


@unittest.skipIf(SKIP is not None, SKIP or "")
class DamageLedgerTests(unittest.TestCase):
    def test_repair_restores_exactly_what_damage_took(self) -> None:
        prototypes = {VEST: [0, 0, 0, 0], HELMET: HELMET_VALUES}
        with LiveMud() as mud:
            # Mana for every cast: a new character has about a hundred, so
            # only five landed, and five one-in-four chances at the helmet
            # missed it about a time in four (CI, 2026-10-23).
            make(mud, "Zledgersmith", 70, Sk="100 'acid breath'",
                 HMV="9000 9000 30000 30000 500 500", HMVP="9000 30000 500")
            make(mud, "Zledgerworn", 50, NewGold=500000,
                 HMV="9000 9000 500 500 500 500", HMVP="9000 500 500")

            # The kit: eight randomized vests and the helmet, worn.
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zledgersmith", PASSWORD)
                login(hero, "Zledgerworn", PASSWORD)
                for _ in range(8):
                    run(staff, f"load obj {VEST} 40", 0.4)
                    run(staff, "give vest zledgerworn", 0.4)
                run(staff, f"load obj {HELMET}", 0.4)
                run(staff, "give helmet zledgerworn", 1.0)
                run(hero, "wear helmet", 1.0)
                before_ac = armour_class(run(staff, "stat zledgerworn", 1.5))
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
                staff.send("quit")
                self.assertTrue(staff.wait_closed())
            original = armour_on_file(mud, "Zledgerworn", prototypes)
            self.assertEqual(len(original), 9, original)
            rolled = {tuple(values) for vnum, values, _ in original if vnum == VEST}
            self.assertNotIn((0, 0, 0, 0), rolled, "the vests were not rolled at creation")

            # Acid until the helmet itself is etched and a few vests are.
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zledgersmith", PASSWORD)
                login(hero, "Zledgerworn", PASSWORD)
                for _ in range(40):
                    run(staff, "cast 'acid breath' zledgerworn", 1.0)
                    run(staff, "peace", 0.5)
                    run(staff, "restore zledgerworn", 0.5)
                    hero.drain(0.3)
                    if "great war helmet is pitted" in hero.transcript \
                            and "leather vest is pitted" in hero.transcript:
                        break
                self.assertIn("great war helmet is pitted", hero.transcript,
                              "forty casts never etched the helmet")
                self.assertIn("leather vest is pitted", hero.transcript,
                              "forty casts never etched a vest")
                damaged_ac = armour_class(run(staff, "stat zledgerworn", 1.5))
                run(staff, "peace", 0.5)
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
                staff.send("quit")
                self.assertTrue(staff.wait_closed())
            etched = armour_on_file(mud, "Zledgerworn", prototypes)

            # Back in -- the ledger has been through a save and a load --
            # and repaired.
            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as staff:
                login(hero, "Zledgerworn", PASSWORD)
                login(staff, "Zledgersmith", PASSWORD)
                repaired_text = run(hero, "repair all", 4.0)
                after_ac = armour_class(run(staff, "stat zledgerworn", 1.5))
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
                staff.send("quit")
                self.assertTrue(staff.wait_closed())
            repaired = armour_on_file(mud, "Zledgerworn", prototypes)

        # The damage was recorded: every piece's value plus its ledger is
        # what it was made with, and some pieces carry one.
        self.assertEqual(len(etched), 9)
        for (vnum, made, _), (_, now, lost) in zip(original, etched):
            self.assertEqual([v + l for v, l in zip(now, lost)], made, (vnum, made, now, lost))
        # A randomized vest and the fixed helmet both carry a ledger.
        self.assertTrue(any(any(lost) for vnum, _, lost in etched if vnum == VEST), etched)
        self.assertTrue(any(any(lost) for vnum, _, lost in etched if vnum == HELMET), etched)
        self.assertNotEqual(damaged_ac, before_ac, "the worn helmet was etched but AC did not move")

        # Repaired: each piece exactly as made -- not the floor below a
        # good roll, not the prototype above it -- and no ledger left.
        self.assertIn("repaired", repaired_text)
        self.assertEqual([(v, made) for v, made, _ in original],
                         [(v, now) for v, now, _ in repaired])
        self.assertTrue(all(not any(lost) for _, _, lost in repaired), repaired)
        self.assertEqual(after_ac, before_ac, "the worn helmet's armour did not come back")

    def test_a_piece_damaged_before_the_ledger_repairs_as_it_always_did(self) -> None:
        """A file from before 2026-10-22 has no ArmorLost. Its damage is
        unknown, so REPAIR keeps the old rule: a randomized piece filed
        below the least its roll can make comes back to that floor, and a
        good roll with nothing recorded is not touched -- no free upgrade
        towards the prototype or the best roll."""
        floor = 40 // 5 + 3 - 1         # repair_armor_floor at level 40

        def vest(values: str, condition: int) -> str:
            return ("#O\nVnum %d\nNest 0\nWear -1\nLev 40\nCond %d\nVal  %s 0\nEnd\n\n"
                    % (VEST, condition, values))

        with LiveMud() as mud:
            make(mud, "Zledgerold", 50, NewGold=500000)
            path = mud.player_dir / "Zledgerold"
            text = path.read_text(encoding="latin-1")
            planted = vest("2 2 2 -1", 40) + vest("12 11 12 0", 100)
            path.write_text(text.replace("#END", planted + "#END", 1), encoding="latin-1")
            with mud.connect(timeout=120) as hero:
                login(hero, "Zledgerold", PASSWORD)
                answer = run(hero, "repair all", 3.0)
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
            pieces = armour_on_file(mud, "Zledgerold", {VEST: [0, 0, 0, 0]})

        self.assertIn("1 item repaired", answer, answer)
        self.assertEqual(sorted(values for _, values, _ in pieces),
                         sorted([[floor, floor, floor, 0], [12, 11, 12, 0]]))


if __name__ == "__main__":
    unittest.main()

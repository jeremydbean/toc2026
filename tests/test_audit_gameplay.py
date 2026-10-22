"""Gameplay faults from the correctness audit of 2026-10-22, played live.

Each test plays the audit's reproduction against a real server in a
throwaway tree and fails on the code before the fix:

 8. A haggled part-used wand was bought for nothing, with a negative cost.
 9. REPAIR "repaired" brand-new level -1 armour, charging and raising it.
11. REMORT put back gear WEAR, WIELD or SECONDARY would refuse.
12. SECONDARY took a weapon carrying its own +8/+8.
14. Heat overwrote an item's own timer.
15. LOOK IN a portal moved the looker there and back, firing arrivals.
16. CLIMB walked into a full private room; CRAWL escaped a fight.
17. Meteor swarm struck each target once instead of up to four times.
18. Divine protection's counter carried the attacker's backstab.

Staff fixtures are only there for LOAD, SET and FORCE; what is tested is
the ordinary command. Names are Z-prefixed and alphabetic.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zaudit22"
TEMPLE = 4207
SQUARE = 2401          # the Oak Tree Square, where nothing is safe
SMITHY = 2490          # the dwarven blacksmith repairs here
GAMES_ROOM = 15068     # the Hyrule arcade cabinet stands here
GELIDIA_SQUARE = 18215  # a ladder climbs to the private tower top
TOWER_TOP = 18220
STAFF = 70
BEGGAR = 2432          # a level 1 sentinel: he stays put for the test


def run(client, command: str, settle: float = 1.4) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.drain(1.0)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError("character did not leave the world")
    if fields:
        patch_player_file(mud, name, **fields)


def add_lines(mud: LiveMud, name: str, objects=(), player_lines=()) -> None:
    """Objects appended to the file; lines added to the player block."""
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    if player_lines:
        at = text.index("\nEnd\n")
        text = text[:at] + "\n" + "\n".join(player_lines) + text[at:]
    text = text.replace("#END", "".join(objects) + "#END", 1)
    path.write_text(text, encoding="latin-1")


def purse(text: str) -> int:
    """The last WORTH line, in copper (100 to each step up)."""
    found = re.findall(r"You have (\d+) platinum, (\d+) gold, (\d+) silver and (\d+) copper", text)
    if not found:
        raise AssertionError("no WORTH line in:\n" + text)
    p, g, s, c = (int(x) for x in found[-1])
    return ((p * 100 + g) * 100 + s) * 100 + c


def stat_field(text: str, field: str) -> int:
    m = re.search(field + r":\s*(-?\d+)", text)
    if not m:
        raise AssertionError("no %s in stat output:\n%s" % (field, text))
    return int(m.group(1))


def armour_values(text: str) -> list[int]:
    m = re.search(r"Values:\s*(-?\d+) (-?\d+) (-?\d+) (-?\d+)", text)
    if not m:
        raise AssertionError("no Values in stat output:\n" + text)
    return [int(x) for x in m.groups()]


def quit_(testcase: unittest.TestCase, client) -> None:
    client.send("quit")
    testcase.assertTrue(client.wait_closed())


@unittest.skipIf(SKIP is not None, SKIP or "")
class ShopAndSmithTests(unittest.TestCase):
    def test_a_haggled_part_used_wand_is_never_free(self) -> None:
        """Finding 8: a wand at 1 of 100 charges, haggled at 100%.

        The price is the worth scaled by charges; the haggle took up to
        half the *full* worth off it. The price went negative, the purse
        refused to pay, the wand was handed over anyway and its cost set
        negative. Now the haggle comes off the asking price."""
        with LiveMud() as mud:
            make(mud, "Zhaggler", Levl=STAFF, Room=SMITHY, NewGold=500)
            with mud.connect(timeout=120) as client:
                login(client, "Zhaggler", PW)
                run(client, "scroll 0")
                run(client, "set skill self haggle 100")
                run(client, "load mob 20117")      # Thomas the weaponmaster keeps a shop
                run(client, "load obj 3044")       # a wand of magic missiles
                run(client, "set obj wand v1 100")
                run(client, "set obj wand v2 1")
                run(client, "give wand weaponmaster")
                before = purse(run(client, "worth"))
                bought = run(client, "buy wand", 2.0)
                after = purse(run(client, "worth"))
                stat = run(client, "stat obj wand", 1.5)
                quit_(self, client)

        self.assertIn("You buy a wand", bought, bought)
        self.assertNotIn("down to free", bought, bought)
        self.assertLess(after, before, "the wand must cost something: " + bought)
        self.assertIn("Carried by: Zhaggler", stat, stat)
        self.assertGreater(stat_field(stat, "Cost"), 0, stat)

    def test_new_level_minus_one_armour_needs_no_repair(self) -> None:
        """Finding 9: a new kraken shell (10226, a level -1 prototype).

        create_object rolls its armour from its level, well below the
        prototype's 10 20 15, and REPAIR took every value below the
        prototype for damage: it charged for brand-new kit and raised it to
        10 20 15. A real dent is still mended, never past what was made."""
        with LiveMud() as mud:
            make(mud, "Zsmithy", Levl=STAFF, Room=SMITHY, NewGold=500)
            with mud.connect(timeout=120) as client:
                login(client, "Zsmithy", PW)
                run(client, "scroll 0")
                run(client, "load obj 10226 5")   # level 5: a cheap repair
                made = run(client, "stat obj kraken", 1.5)
                before = purse(run(client, "worth"))
                said = run(client, "repair kraken", 2.0)
                after = purse(run(client, "worth"))
                kept = run(client, "stat obj kraken", 1.5)
                # Now a real dent: a value filed to nothing and wear taken.
                run(client, "set obj kraken v0 0")
                run(client, "set obj kraken condition 50")
                mended_said = run(client, "repair kraken", 2.0)
                mended = run(client, "stat obj kraken", 1.5)
                quit_(self, client)

        self.assertIn("perfect condition", said, said)
        self.assertEqual(before, after, "nothing is charged for new kit")
        self.assertEqual(armour_values(made), armour_values(kept))
        self.assertNotIn("perfect condition", mended_said, mended_said)
        self.assertGreater(armour_values(mended)[0], 0, mended)
        self.assertLessEqual(armour_values(mended)[0], armour_values(made)[0],
                             "a repair never lifts a piece past what was made")
        self.assertEqual(stat_field(mended, "Condition"), 100, mended)


@unittest.skipIf(SKIP is not None, SKIP or "")
class EquipmentTests(unittest.TestCase):
    def test_remort_leaves_an_axe_too_heavy_to_wield_in_the_pack(self) -> None:
        """Finding 11: strength 25 wields a small axe; the remort's
        strength-13 mage cannot, and WIELD says so -- the remort put it
        back in the hand anyway."""
        with LiveMud() as mud:
            make(mud, "Zremheavy", Levl=54, Room=TEMPLE, Attr="25 25 25 25 25")
            add_lines(mud, "Zremheavy",
                      ["#O\nVnum 103\nNest 0\nWear -1\nLev 2\nCond 100\nEnd\n\n"])
            with mud.connect(timeout=120) as client:
                login(client, "Zremheavy", PW)
                run(client, "scroll 0")
                self.assertIn("You wield a small axe", run(client, "wield axe"))
                run(client, "remort %s mage none human" % PW, 4.0)
                worn = run(client, "equipment")
                carried = run(client, "inventory")
                again = run(client, "wield axe")
                quit_(self, client)

        self.assertNotIn("small axe", worn, worn)
        self.assertIn("small axe", carried, "kept, carried: " + carried)
        self.assertIn("too heavy", again, again)

    def test_remort_takes_the_off_hand_weapon_from_a_life_without_dual_wield(self) -> None:
        """Finding 11: a thief's second dagger stayed in the off hand of
        the warrior it remorted into, who has no dual wield."""
        with LiveMud() as mud:
            make(mud, "Zremdual", Levl=54, Room=TEMPLE, Cla=2, Attr="25 25 25 25 25")
            add_lines(mud, "Zremdual", [
                "#O\nVnum 3701\nNest 0\nName dagger zplain~\nWear -1\nLev 1\nCond 100\nEnd\n\n",
                "#O\nVnum 3701\nNest 0\nName dagger zoff~\nWear -1\nLev 1\nCond 100\nEnd\n\n",
            ], ["Sk 75 'dual wield'"])
            with mud.connect(timeout=120) as client:
                login(client, "Zremdual", PW)
                run(client, "scroll 0")
                run(client, "wield zplain")
                self.assertIn("as your second weapon", run(client, "secondary zoff"))
                run(client, "remort %s warrior none human" % PW, 4.0)
                worn = run(client, "equipment")
                carried = run(client, "inventory")
                again = run(client, "secondary zoff")
                quit_(self, client)

        self.assertNotIn("secondary weapon", worn, worn)
        self.assertIn("dagger", carried, "the off-hand dagger is kept: " + carried)
        self.assertIn("only wield one weapon", again, again)

    def test_secondary_refuses_a_weapon_with_its_own_bonuses(self) -> None:
        """Finding 12: the limit read only the prototype's affects, and the
        `enchanted` refusal tested a flag no spell sets. A dagger carrying
        +8/+8 of its own was taken; one ENCHANT WEAPON
        worked on (the flag it now sets) is an enchanted weapon; a +2 the
        weapon rolled when it was made is not. A plain one still goes."""
        with LiveMud() as mud:
            make(mud, "Zdualer", Levl=30, Room=TEMPLE, Cla=2, Attr="25 25 25 25 25")
            add_lines(mud, "Zdualer", [
                "#O\nVnum 3701\nNest 0\nName dagger zplain~\nWear -1\nLev 1\nCond 100\nEnd\n\n",
                "#O\nVnum 3701\nNest 0\nName dagger zblade~\nWear -1\nLev 1\nCond 100\n"
                "Affect -1 30 -1 8 19 0 0\nAffect -1 30 -1 8 18 0 0\nEnd\n\n",
                # What ENCHANT WEAPON leaves: the flag (saved as Enchanted)
                # and a bonus.
                "#O\nVnum 3701\nNest 0\nName dagger zmild~\nEnchanted\nWear -1\nLev 1\n"
                "Cond 100\nAffect -1 30 -1 2 18 0 0\nEnd\n\n",
                # A small bonus the weapon rolled when it was made: not an
                # enchantment, and it may be dual wielded.
                "#O\nVnum 3701\nNest 0\nName dagger zlucky~\nWear -1\nLev 1\nCond 100\n"
                "Affect -1 30 -1 2 18 0 0\nEnd\n\n",
                "#O\nVnum 3701\nNest 0\nName dagger zoff~\nWear -1\nLev 1\nCond 100\nEnd\n\n",
            ], ["Sk 75 'dual wield'"])
            with mud.connect(timeout=120) as client:
                login(client, "Zdualer", PW)
                run(client, "scroll 0")
                run(client, "wield zplain")
                strong = run(client, "secondary zblade")
                mild = run(client, "secondary zmild")
                lucky = run(client, "secondary zlucky")
                run(client, "remove zlucky")
                plain = run(client, "secondary zoff")
                quit_(self, client)

        self.assertIn("too powerful to dual wield", strong, strong)
        self.assertIn("enchanted weapon", mild, mild)
        self.assertIn("as your second weapon", lucky, lucky)
        self.assertIn("as your second weapon", plain, plain)

    def test_heat_leaves_a_piece_with_its_own_timer_alone(self) -> None:
        """Finding 14: try_heat_gear stored the cooling time in obj->timer
        over whatever was there, and obj_update zeroes it on cooling, so a
        decaying item's countdown was lost.

        Heat is a 15% roll per fire breath, so this breathes up to sixty
        times at a beggar wearing two pieces -- a helmet with a timer of
        its own and a vest without -- and stops once the vest has been
        heated (the rolls are landing) and a dozen more have been spent
        with only the helmet left to pick. Before the fix the helmet is
        the only candidate after the vest, and is heated."""
        with LiveMud() as mud:
            make(mud, "Zheater", Levl=STAFF, Room=SQUARE)
            with mud.connect(timeout=120) as client:
                login(client, "Zheater", PW)
                run(client, "scroll 0")
                # Fire breath hits for an eighth of the breather's hit
                # points: enough to stand the beggar's blows, not so many
                # that sixty breaths kill him.
                run(client, "set char self hp 300", 0.6)
                run(client, "set char self mana 30000", 0.6)
                run(client, "set skill self 'fire breath' 100", 0.6)
                run(client, "load mob %d" % BEGGAR, 0.6)
                run(client, "set char beggar level 30", 0.6)
                run(client, "set char beggar hp 30000", 0.6)
                run(client, "restore room", 0.6)
                run(client, "load obj 4619", 0.6)      # a great war helmet
                run(client, "load obj 3703", 0.6)      # a sub issue vest
                run(client, "set obj helmet timer 60", 0.6)
                run(client, "give helmet beggar", 0.6)
                run(client, "give vest beggar", 0.6)
                dressed = run(client, "force beggar wear all", 1.0) + run(client, "look beggar")
                self.assertIn("great war helmet", dressed, dressed)
                self.assertIn("vest", dressed, dressed)

                breaths = ""
                after_vest = None
                for _ in range(60):
                    breaths += run(client, "cast 'fire breath' beggar", 0.5)
                    if after_vest is None and re.search(r"superheats .*vest", breaths):
                        after_vest = 0
                    elif after_vest is not None:
                        after_vest += 1
                        if after_vest >= 12:
                            break
                run(client, "peace", 0.6)
                helmet = run(client, "stat obj helmet", 1.5)
                quit_(self, client)

        self.assertIsNotNone(after_vest, "no breath heated anything:\n" + breaths[-2000:])
        self.assertNotRegex(breaths, r"superheats .*helmet")
        self.assertGreaterEqual(stat_field(helmet, "Timer"), 50, helmet)
        self.assertNotIn("Wear_loc: -1", helmet, "the helmet stays on: " + helmet)


@unittest.skipIf(SKIP is not None, SKIP or "")
class MovementTests(unittest.TestCase):
    def test_looking_into_a_portal_moves_nobody(self) -> None:
        """Finding 15: LOOK IN the arcade cabinet moved the looker into
        Hyrule and back, and the arrival earned A Hero Awakens."""
        with LiveMud() as mud:
            make(mud, "Zpeeker", Room=GAMES_ROOM)
            with mud.connect(timeout=120) as client:
                login(client, "Zpeeker", PW)
                run(client, "scroll 0")
                peek = run(client, "look in cabinet", 2.5)
                here = run(client, "look")
                earned = run(client, "achievements exploration", 1.5)
                run(client, "")
                quit_(self, client)

        self.assertIn("Looking into", peek, peek)
        self.assertIn("The First Quest Begins", peek, peek)
        self.assertNotIn("ACHIEVEMENT EARNED", peek, peek)
        self.assertIn("Games Room", here, here)
        self.assertNotRegex(earned, r"Earned[^\n]*A Hero Awakens")

    def test_a_ladder_respects_a_full_private_room(self) -> None:
        """Finding 16: two people in the private tower top, and a third
        climbed the ladder in."""
        with LiveMud() as mud:
            for name, room in (("Zalpha", TOWER_TOP), ("Zbravo", TOWER_TOP),
                               ("Zclimber", GELIDIA_SQUARE)):
                make(mud, name, Room=room, Levl=20)
            first = mud.connect(timeout=120)
            second = mud.connect(timeout=120)
            try:
                login(first, "Zalpha", PW)
                login(second, "Zbravo", PW)
                with mud.connect(timeout=120) as client:
                    login(client, "Zclimber", PW)
                    run(client, "scroll 0")
                    said = run(client, "climb ladder", 2.0)
                    here = run(client, "look")
                    quit_(self, client)
            finally:
                first.close()
                second.close()

        self.assertIn("private", said, said)
        self.assertNotIn("Top of the tower", said + here, said + here)
        self.assertIn("Center of Town Square", here, here)

    def test_a_crawl_does_not_escape_a_fight(self) -> None:
        """Finding 16: NORTH answered "You are still fighting!" and CRAWL
        HOLE, registered at POS_RESTING, carried the fighter away. Out of
        the fight the hole still works."""
        with LiveMud() as mud:
            make(mud, "Zgodly", Room=SQUARE, Levl=STAFF)
            make(mud, "Zrunner", Room=SQUARE, Levl=30)
            staff = mud.connect(timeout=120)
            try:
                login(staff, "Zgodly", PW)
                run(staff, "load mob %d" % BEGGAR, 0.6)
                run(staff, "set char beggar hp 30000", 0.6)
                run(staff, "restore room", 0.6)
                with mud.connect(timeout=120) as client:
                    login(client, "Zrunner", PW)
                    run(client, "scroll 0")
                    run(client, "kill beggar", 1.0)
                    fighting = run(client, "crawl hole", 3.5)
                    run(staff, "peace", 1.0)
                    client.drain(1.0)
                    free = run(client, "crawl hole", 3.5)
                    quit_(self, client)
            finally:
                staff.close()

        self.assertIn("still fighting", fighting, fighting)
        self.assertNotIn("House of Pancakes", fighting, fighting)
        self.assertIn("House of Pancakes", free, "an ordinary crawl still works: " + free)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CombatTests(unittest.TestCase):
    def _staff_with_beggar(self, mud: LiveMud, name: str, *skills: str):
        make(mud, name, Room=SQUARE, Levl=STAFF)
        client = mud.connect(timeout=120)
        login(client, name, PW)
        run(client, "scroll 0")
        run(client, "set char self hp 30000", 0.6)
        for skill in skills:
            run(client, "set skill self '%s' 100" % skill, 0.6)
        run(client, "load mob %d" % BEGGAR, 0.6)
        run(client, "set char beggar hp 30000", 0.6)
        run(client, "restore room", 0.6)
        return client

    def test_meteor_swarm_strikes_a_target_more_than_once(self) -> None:
        """Finding 17: each target's meteors stopped at damage()'s result,
        which is true of every landed blow -- one meteor a target. A target
        that survives takes up to four."""
        with LiveMud() as mud:
            client = self._staff_with_beggar(mud, "Zmeteor", "meteor swarm")
            try:
                counts = []
                for _ in range(3):
                    run(client, "set char self mana 30000", 0.6)
                    out = run(client, "cast 'meteor swarm'", 2.0)
                    counts.append(len(re.findall(r"Your meteor[^\n]*beggar", out)))
                    run(client, "peace", 0.8)
                    run(client, "restore room", 0.8)
                quit_(self, client)
            finally:
                client.close()

        self.assertGreaterEqual(max(counts), 2, "meteors on the beggar per cast: %r" % counts)

    def test_divine_protection_counters_with_its_own_blow(self) -> None:
        """Finding 18: the counter was one_hit(victim, ch, dt), so the
        counter to a backstab was the victim's own backstab, with the
        backstab's multiplier. It is the victim's ordinary blow now.

        The counter fires 95% of the time; three backstabs make missing it
        on the old code vanishingly unlikely."""
        with LiveMud() as mud:
            client = self._staff_with_beggar(mud, "Zstabber", "backstab", "divine protection")
            try:
                warded = run(client, "cast 'divine protection' beggar", 1.0)
                self.assertIn("divine protection", warded, warded)
                stabs = ""
                for _ in range(3):
                    stabs += run(client, "backstab beggar", 2.0)
                    run(client, "peace", 0.8)
                    run(client, "restore room", 0.8)
                quit_(self, client)
            finally:
                client.close()

        self.assertIn("backstab", stabs.lower(), stabs)
        self.assertNotRegex(stabs, r"[Bb]eggar's backstab", stabs)


if __name__ == "__main__":
    unittest.main()

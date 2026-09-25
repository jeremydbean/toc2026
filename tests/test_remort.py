"""Remorting back to level 3 without quietly shaving the character down.

do_remort rewrites armour, maxima and affect flags for a bare level-3 body,
but the character keeps everything it owns and goes on wearing it. Worn gear
had already added itself to all three when it went on, so writing over the
top of that discarded the contribution -- and the player's next REMOVE then
subtracted a bonus that was no longer there. A character who remorted in
full plate came out five armour classes worse than one who had never worn
anything, and repeated it on every remort.

The other half of the same pass: exp_per_level reads class, race and guild,
and the starting experience was being computed before any of the three had
been replaced, so a new life was priced against the old one's table.

These run against a real server in a throwaway tree.
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

PASSWORD = "Zremort1"

# LEVEL_HERO3 in merc.h. The first remort is gated on exactly this level.
FIRST_REMORT_LEVEL = 54

# A character with no gear on has 100 in each of the four armour classes.
BARE_ARMOUR = [100, 100, 100, 100]


def armour(sheet: str) -> list[int]:
    """The four armour classes from a SCORE sheet, in printed order."""
    return [
        int(value)
        for value in re.findall(
            r"(?:Piercing|Bashing|Slashing|Magical) AC:\s+(\d+)", sheet
        )
    ]


def run(client, command: str, settle: float = 1.3) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class RemortTests(unittest.TestCase):
    def test_a_remort_keeps_what_it_is_wearing_and_what_it_is_worth(self):
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Remorty", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            patch_player_file(mud, "Remorty", Levl=FIRST_REMORT_LEVEL)

            with mud.connect(timeout=120) as client:
                login(client, "Remorty", PASSWORD)
                run(client, "wear all", 1.6)

                before = run(client, "score", 1.6)
                worn_before = run(client, "equipment", 1.3)
                self.assertIn("worn on body", worn_before)
                self.assertNotEqual(
                    armour(before), BARE_ARMOUR,
                    "the fixture needs gear that actually changes armour; "
                    "got " + worn_before,
                )

                said = run(client, "remort %s mage cleric elf" % PASSWORD, 3.0)
                self.assertIn("remorted to level 3", said)

                after = run(client, "score", 1.6)
                worn_after = run(client, "equipment", 1.3)

                self.assertEqual(
                    worn_before.count("worn"), worn_after.count("worn"),
                    "gear should still be worn after the remort:\n" + worn_after,
                )
                self.assertEqual(
                    armour(after), armour(before),
                    "worn gear stopped counting towards armour across the "
                    "remort",
                )

                run(client, "remove all", 1.6)
                self.assertEqual(
                    armour(run(client, "score", 1.6)), BARE_ARMOUR,
                    "taking the gear off drifted away from the bare baseline, "
                    "which means the remort discarded what equip_char added",
                )

    def test_starting_experience_is_priced_for_the_new_life(self):
        """A remort starts three levels' worth of experience in.

        exp_per_level reads ch->class, ch->race and ch->pcdata->guild, so
        the sum only comes out right if it is asked after all three have
        been replaced. SCORE prints both halves, and the check is that they
        agree: experience held is exactly three times the cost of a level.
        """
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Reborny", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            patch_player_file(mud, "Reborny", Levl=FIRST_REMORT_LEVEL)

            with mud.connect(timeout=120) as client:
                login(client, "Reborny", PASSWORD)
                self.assertIn(
                    "remorted to level 3",
                    run(client, "remort %s mage cleric elf" % PASSWORD, 3.0),
                )
                sheet = run(client, "score", 1.6)

                held = re.search(r"Exp:\s+(\d+)", sheet)
                per_level = re.search(r"To Level:\s+(\d+)", sheet)
                self.assertIsNotNone(held, sheet)
                self.assertIsNotNone(per_level, sheet)
                self.assertEqual(
                    int(held.group(1)), 3 * int(per_level.group(1)),
                    "starting experience was computed against the old "
                    "class/race/guild:\n" + sheet,
                )


class RemortSourceTests(unittest.TestCase):
    """Two hazards that a live run cannot reach without corrupt input."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "src" / "act_info.c").read_text(encoding="utf-8")

    def test_the_remort_history_walk_cannot_run_off_the_array(self) -> None:
        """had_classes is a fixed stack array read from the player file.

        ListRemorts is two numbers per remort and five remorts is the cap,
        so a sound file never fills it -- but a hand-edited or damaged one
        can, and the loop had no bound at all.
        """
        self.assertIn(
            "while (to_strip[0] != '\\0' && ind_class < 2*MAX_CLASS)",
            self.source,
        )

    def test_remorting_off_a_mount_releases_the_mount(self) -> None:
        """Clearing only the rider's half leaves the steed flagged ridden,
        and act_info.c hides a ridden mob from the room for good."""
        body = self.source.split("void do_remort(")[1]
        self.assertIn("ch->pet->ridden = false;", body)
        self.assertLess(
            body.index("ch->pet->ridden = false;"),
            body.index("ch->pcdata->mounted = false;"),
        )

    def test_the_password_argument_keeps_its_case(self) -> None:
        """one_argument lowercases what it copies and crypt(3) does not, so
        a character created with a capital in their password could never
        hand it to REMORT. do_password and do_pkill had each stolen a
        private copy of one_argument to dodge this; there is one now."""
        interp = (ROOT / "src" / "interp.c").read_text(encoding="utf-8")

        self.assertIn("char *one_argument_case( char *argument", interp)
        self.assertIn("one_argument_case(arg,arg1);", self.source)
        self.assertIn("one_argument_case( argument, arg1 );", self.source)
        self.assertNotIn("we just steal all its code", self.source)


if __name__ == "__main__":
    unittest.main()

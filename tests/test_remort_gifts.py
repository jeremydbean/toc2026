"""The gifts a remort carries, and the history that decides the next life.

Three things are proved here.

The third remort's gifts: twice the carrying room and a deeper psionic
grant, alongside the longer idle rope that ``test_shadowmeld`` covers.

Psionics stack. A remort wipes the whole skill table, so the powers it
awarded were being redealt rather than added to -- a player could lose a
discipline they had spent a life with. They are remembered by name now, in
``PsiKnown``, which survives the wipe and is put back from on the next
grant. The final remort hands over all seventeen.

And the class history. It used to be read as one flat pool of numbers, but
a guild is stored as the matching class index, so the pool conflated the
two: having been in the mage guild barred you from ever being a mage. Each
non-monk life burned two of only six values, and a player who spent them
badly reached their fourth remort with nothing left to choose -- shown an
empty list, stuck at level 57, with level 59 out of reach for good.

These run against a real server in a throwaway tree.
"""
from __future__ import annotations

import itertools
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

PASSWORD = "Zgiftly1"

# LEVEL_HERO3 in merc.h; a remort is gated on exactly LEVEL_HERO3 + count.
FIRST_REMORT_LEVEL = 54

# CLASS_/GUILD_ in merc.h.
MAGE, CLERIC, THIEF, WARRIOR, MONK, NECRO = range(6)

# The whole psionic pool, from psionic_skill_names[] in src/stubs.c.
PSIONIC_COUNT = 17


def run(client, command: str, settle: float = 1.3) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def saved_field(mud: "LiveMud", name: str, key: str) -> str:
    """One ``~``-terminated string field out of a saved player file."""
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    match = re.search(r"^%s ?(.*?)~" % key, text, re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError("no %s line in %s's file" % (key, name))
    return match.group(1).strip()


def psionics(mud: "LiveMud", name: str) -> set:
    known = saved_field(mud, name, "PsiKnown")
    return {part.strip() for part in known.split(",") if part.strip()}


def carry_limits(sheet: str) -> tuple:
    """The two ceilings SCORE prints: items, then weight."""
    found = re.findall(r"(?:Items carried|Encumbrance):\s+\d+\s+\(\s*(\d+)\)",
                       sheet)
    if len(found) != 2:
        raise AssertionError("could not read the carry ceilings:\n" + sheet)
    return int(found[0]), int(found[1])


@unittest.skipIf(SKIP is not None, SKIP or "")
class ThirdRemortCarriesMore(unittest.TestCase):
    def test_the_third_remort_doubles_what_you_can_haul(self) -> None:
        """Same character, same stats, one more remort behind them."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Hauler", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            patch_player_file(mud, "Hauler", NumRemorts=2)
            with mud.connect(timeout=120) as client:
                login(client, "Hauler", PASSWORD)
                before = carry_limits(run(client, "score", 1.6))
                client.send("quit")
                self.assertTrue(client.wait_closed())

            patch_player_file(mud, "Hauler", NumRemorts=3)
            with mud.connect(timeout=120) as client:
                login(client, "Hauler", PASSWORD)
                after = carry_limits(run(client, "score", 1.6))

            self.assertEqual(
                after, (before[0] * 2, before[1] * 2),
                "the third remort should double both carry ceilings; "
                "went from %r to %r" % (before, after),
            )


@unittest.skipIf(SKIP is not None, SKIP or "")
class PsionicsStack(unittest.TestCase):
    def test_a_later_remort_adds_powers_instead_of_redealing_them(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Mindly", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            # A mage of the mage guild, one remort in, ready for a second.
            patch_player_file(
                mud, "Mindly",
                Levl=FIRST_REMORT_LEVEL + 1, NumRemorts=1,
                Cla=MAGE, Gui=MAGE, ListRemorts="~", PsiKnown="~",
            )

            with mud.connect(timeout=120) as client:
                login(client, "Mindly", PASSWORD)
                self.assertIn(
                    "remorted to level 3",
                    run(client, "remort %s warrior cleric human" % PASSWORD, 3.0),
                )
                client.send("quit")
                self.assertTrue(client.wait_closed())

            second = psionics(mud, "Mindly")
            self.assertEqual(
                len(second), 4,
                "the second remort awards one power from each of the four "
                "disciplines; got %r" % sorted(second),
            )

            patch_player_file(mud, "Mindly", Levl=FIRST_REMORT_LEVEL + 2)
            with mud.connect(timeout=120) as client:
                login(client, "Mindly", PASSWORD)
                self.assertIn(
                    "remorted to level 3",
                    run(client, "remort %s thief thief human" % PASSWORD, 3.0),
                )
                client.send("quit")
                self.assertTrue(client.wait_closed())

            third = psionics(mud, "Mindly")
            self.assertEqual(
                len(third), 8,
                "the third remort should add a second power from each "
                "discipline; got %r" % sorted(third),
            )
            self.assertTrue(
                second <= third,
                "the powers of the earlier life were redealt rather than "
                "kept: %r became %r" % (sorted(second), sorted(third)),
            )

    def test_the_final_remort_hands_over_every_power(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Lastly", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            patch_player_file(
                mud, "Lastly",
                Levl=FIRST_REMORT_LEVEL + 4, NumRemorts=4,
                Cla=MAGE, Gui=MAGE, ListRemorts="~", PsiKnown="~",
            )

            with mud.connect(timeout=120) as client:
                login(client, "Lastly", PASSWORD)
                self.assertIn(
                    "remorted to level 3",
                    run(client, "remort %s mage mage human" % PASSWORD, 3.0),
                )
                client.send("quit")
                self.assertTrue(client.wait_closed())

            self.assertEqual(
                len(psionics(mud, "Lastly")), PSIONIC_COUNT,
                "the last life is meant to hold the whole discipline",
            )


@unittest.skipIf(SKIP is not None, SKIP or "")
class ClassHistory(unittest.TestCase):
    def test_a_class_you_have_lived_is_refused_and_a_guild_you_held_is_not(
        self,
    ) -> None:
        """One live run covers both halves of the split.

        The fixture has been a mage of the cleric guild and is now a
        warrior of the warrior guild. Mage is refused because it was a
        class. Cleric is offered because it was only ever a guild -- under
        the old shared pool it was barred.
        """
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Pastly", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            patch_player_file(
                mud, "Pastly",
                Levl=FIRST_REMORT_LEVEL + 1, NumRemorts=1,
                Cla=WARRIOR, Gui=WARRIOR,
                ListRemorts="%d %d ~" % (MAGE, CLERIC),
            )

            with mud.connect(timeout=120) as client:
                login(client, "Pastly", PASSWORD)

                refused = run(client, "remort %s mage mage human" % PASSWORD, 2.0)
                self.assertIn("already lived as a mage", refused)
                self.assertIn("Classes still open to you", refused)
                self.assertIn("Guilds still open to you", refused)
                self.assertNotIn("remorted to level 3", refused)

                # The guild half still bites on a guild actually held.
                refused = run(
                    client, "remort %s cleric warrior human" % PASSWORD, 2.0)
                self.assertIn("already belonged to the warrior guild", refused)
                self.assertNotIn("remorted to level 3", refused)

                # Cleric was a guild, never a class: it is a life available.
                self.assertIn(
                    "remorted to level 3",
                    run(client, "remort %s cleric mage human" % PASSWORD, 3.0),
                )


class RemortHistorySourceTests(unittest.TestCase):
    """Reachability, and the guards the live tests cannot see."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "src" / "act_info.c").read_text(encoding="utf-8")
        cls.header = (ROOT / "src" / "merc.h").read_text(encoding="utf-8")

    def test_classes_and_guilds_are_two_histories_not_one_pool(self) -> None:
        body = self.source.split("void do_remort(")[1]
        self.assertIn("had_class[requested_class]", body)
        self.assertIn("had_guild[requested_guild]", body)
        self.assertNotIn("had_classes", body)

    def test_the_last_remort_is_free_of_the_history(self) -> None:
        body = self.source.split("void do_remort(")[1]
        self.assertIn(
            "if (ch->pcdata->num_remorts < REMORTS_FOR_FREE_CHOICE)", body)
        self.assertIn("#define REMORTS_FOR_FREE_CHOICE 4", self.header)

    def test_no_history_can_leave_a_player_unable_to_remort(self) -> None:
        """The rule the source now implements, walked exhaustively.

        Under the old shared pool this fails: a mage of the cleric guild who
        goes thief/warrior, then monk, then necro arrives at their fourth
        remort with no legal choice at all.
        """
        classes = range(6)
        guilds = [MAGE, CLERIC, THIEF, WARRIOR, -1]   # -1 is "none"

        def legal(cls: int, guild: int) -> bool:
            if cls in (MONK, NECRO):
                return guild == -1
            return True

        def reachable(had_c: frozenset, had_g: frozenset, taken: int) -> bool:
            if taken >= 5:
                return True
            free = taken >= 4          # the fifth remort ignores the history
            for cls, guild in itertools.product(classes, guilds):
                if not legal(cls, guild):
                    continue
                if not free:
                    if cls in had_c:
                        continue
                    if guild >= 0 and guild in had_g:
                        continue
                if reachable(had_c | {cls},
                             had_g | ({guild} if guild >= 0 else set()),
                             taken + 1):
                    return True
            return False

        stuck = [
            (cls, guild)
            for cls, guild in itertools.product(classes, guilds)
            if legal(cls, guild)
            and not reachable(frozenset({cls}),
                              frozenset({guild} if guild >= 0 else set()), 0)
        ]
        self.assertEqual(
            stuck, [],
            "these starting class/guild pairs can never reach the fifth "
            "remort: %r" % stuck,
        )


if __name__ == "__main__":
    unittest.main()

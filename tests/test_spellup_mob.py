"""Hermie, the standing spellup desk.

`spellup` plants Herbie's girlfriend in the room and she buffs whoever talks
to her, picking from a menu she reads out. Three things here are worth a
test rather than a read-through:

  * the flat 30-tick duration, because the spell functions each compute
    their own from the caster's level and ours is rewritten afterwards;
  * that she answers *mortals*, since the command that places her is
    immortal-only and it would be easy to gate the conversation by accident;
  * that `spellpurge` reaches copies of her in rooms nobody is standing in,
    because there is no global character list in this codebase and the sweep
    walks the room hash by hand;
  * that she keeps quiet during conversations aimed at somebody else, which
    is the difference between a fixture you can park on a recall square and
    one nobody will tolerate there.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from live_mud import (  # noqa: E402
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()

IMMORTAL_LEVEL = 70
PASSWORD = "Zspellup1"

# What the C table pins every affect to.
DURATION = 30


def run(client, command: str, settle: float = 1.5) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def immortal(mud: LiveMud, name: str) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        client.wait_closed()
    patch_player_file(mud, name, Levl=IMMORTAL_LEVEL)


@unittest.skipIf(SKIP is not None, SKIP or "")
class SpellupMobTests(unittest.TestCase):
    def test_she_appears_reads_her_menu_and_casts(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zspellone")
            with mud.connect(timeout=120) as client:
                login(client, "Zspellone", PASSWORD)

                placed = run(client, "spellup", settle=3.0)
                self.assertIn("taking requests", placed)
                self.assertNotIn("missing from the area files", placed)

                # Anything she does not recognise opens the menu.
                menu = run(client, "say hello", settle=3.0)
                self.assertIn("sanctuary", menu)
                self.assertIn("empower (bundle)", menu)
                self.assertIn("titanic (bundle)", menu)
                self.assertIn(f"lasts {DURATION} ticks", menu)

                # By name.
                run(client, "say sanctuary", settle=3.0)
                # By menu number -- haste is row 6.
                run(client, "say 6", settle=3.0)

                affects = run(client, "affect", settle=3.0)
                self.assertIn("sanctuary", affects)
                self.assertIn("haste", affects)
                # Every duration she grants is the flat one, not a
                # level-scaled one. At level 70 haste would otherwise run
                # far longer than 30.
                self.assertNotIn(f"for {DURATION * 2} hours", affects)
                for spell in ("sanctuary", "haste"):
                    line = next(row for row in affects.splitlines()
                                if f"'{spell}'" in row)
                    self.assertIn(f"for {DURATION} hours", line,
                                  f"{spell} did not get the flat duration")

    def test_looking_at_her_explains_how_to_use_her(self) -> None:
        """A player's first move is to look at her, so the syntax lives there."""
        with LiveMud() as mud:
            immortal(mud, "Zspellsev")
            with mud.connect(timeout=120) as client:
                login(client, "Zspellsev", PASSWORD)
                run(client, "spellup", settle=3.0)

                described = run(client, "look hermie", settle=3.0)
                self.assertIn("say hermie", described)
                self.assertIn("say all", described)
                self.assertIn("thirty", described)

                # And the room line points at her rather than just naming her.
                room = run(client, "look", settle=2.0)
                self.assertIn("taking requests", room)

    def test_she_stays_out_of_conversations_she_is_not_in(self) -> None:
        """Otherwise she is unusable anywhere players actually gather."""
        with LiveMud() as mud:
            immortal(mud, "Zspellsix")
            with mud.connect(timeout=120) as client:
                login(client, "Zspellsix", PASSWORD)
                run(client, "spellup", settle=3.0)

                chatter = run(client, "say did you see that fight last night",
                              settle=3.0)
                self.assertNotIn("Hermie's list", chatter)
                self.assertNotIn("stone skin", chatter)

                # But her name still opens it.
                asked = run(client, "say hermie are you there", settle=3.0)
                self.assertIn("stone skin", asked)

    def test_mortals_can_use_her(self) -> None:
        """The command is immortal-only; the conversation must not be."""
        with LiveMud() as mud:
            immortal(mud, "Zspelltwo")
            with mud.connect(timeout=120) as god:
                login(god, "Zspelltwo", PASSWORD)
                run(god, "spellup", settle=3.0)

                with mud.connect(timeout=120) as mortal:
                    create_character(mortal, "Zspellmort", PASSWORD)
                    mortal.drain(2.0)

                    menu = run(mortal, "say menu", settle=3.0)
                    self.assertIn("stone skin", menu)

                    run(mortal, "say armor", settle=3.0)
                    affects = run(mortal, "affect", settle=3.0)
                    self.assertIn("armor", affects)

    def test_all_hands_over_the_whole_list_and_is_logged(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zspellthr")
            with mud.connect(timeout=120) as client:
                login(client, "Zspellthr", PASSWORD)
                run(client, "spellup", settle=3.0)

                run(client, "say all", settle=6.0)
                affects = run(client, "affect", settle=3.0)

                # A representative spread: a plain buff, one of the two
                # bundles' components, and a detect.
                for spell in ("armor", "sanctuary", "giant strength",
                              "detect invis"):
                    self.assertIn(spell, affects, f"{spell} was not granted")

            log = (mud.root / "log" / "toc.log").read_text(
                encoding="utf-8", errors="replace")
            self.assertIn("Spellup:", log)
            self.assertIn("Zspellthr", log)
            self.assertIn("the full list", log)

    def test_spellpurge_reaches_an_empty_room(self) -> None:
        """She persists after the immortal leaves, and the sweep finds her."""
        with LiveMud() as mud:
            immortal(mud, "Zspellfou")
            with mud.connect(timeout=120) as client:
                login(client, "Zspellfou", PASSWORD)
                run(client, "spellup", settle=3.0)

                # Walk away so nobody is in her room when the sweep runs.
                run(client, "goto 3001", settle=2.0)
                run(client, "goto 3014", settle=2.0)

                purged = run(client, "spellpurge", settle=3.0)
                self.assertRegex(purged, r"Removed 1 spellup mob\b")

                again = run(client, "spellpurge", settle=2.0)
                self.assertIn("none of her anywhere", again)

    def test_she_is_not_placed_twice_in_one_room(self) -> None:
        with LiveMud() as mud:
            immortal(mud, "Zspellfiv")
            with mud.connect(timeout=120) as client:
                login(client, "Zspellfiv", PASSWORD)
                run(client, "spellup", settle=3.0)
                second = run(client, "spellup", settle=2.0)
                self.assertIn("already standing right here", second)

                # And an ordinary purge clears her, which is why she carries
                # no ACT_NOPURGE.
                run(client, "purge", settle=2.0)
                after = run(client, "spellpurge", settle=2.0)
                self.assertIn("none of her anywhere", after)


if __name__ == "__main__":
    unittest.main()

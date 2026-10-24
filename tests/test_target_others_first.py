"""A word that starts your own name still finds the monster first.

Trentlin's "kill tr" among trolls answered "You must MURDER a player."
three times on 2026-10-24, and "consider tr" beside a tree told him he
was no pkiller: get_char_room walked the room in arrival order with the
looker in it, so the looker could match before the troll. The looker is
now the last match. And CONSIDER, which attacks nobody, no longer asks
is_safe -- in the Temple it answered "Not in the temple my dear." and
then "Don't even think about it."
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Ztarget1pass"
TEMPLE = 4207
ZOMBIE_ROOM = 3766  # school.are: mob 3724, "zombie"


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class TargetSourceTests(unittest.TestCase):
    def test_the_looker_is_matched_last(self) -> None:
        handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        fn = handler[handler.index("CHAR_DATA *get_char_room( CHAR_DATA *ch, char *argument )"):]
        fn = fn[:fn.index("\n}\n")]
        loop = fn.index("rch == ch ||")
        self_match = fn.index("is_name( arg, ch->name )")
        self.assertLess(loop, self_match)

    def test_consider_hit_points_have_no_gap(self) -> None:
        """A 2,000-3,000 point difference fell through the old scale."""
        info = (ROOT / "src" / "act_info.c").read_text(encoding="latin-1")
        fn = info[info.index("static void consider_fight("):]
        fn = fn[:fn.index("\n}\n")]
        self.assertIn("ratio < 5.0", fn)
        self.assertIn("else                     msg = \"$N has many times", fn)

    def test_consider_does_not_ask_is_safe_of_a_mobile(self) -> None:
        info = (ROOT / "src" / "act_info.c").read_text(encoding="latin-1")
        fn = info[info.index("void do_consider("):]
        fn = fn[:fn.index("\n}\n")]
        self.assertIn("is_protected_npc( victim )", fn)


@unittest.skipIf(SKIP is not None, SKIP or "")
class TargetLiveTests(unittest.TestCase):
    def test_a_prefix_of_your_name_finds_the_monster(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zorbo", PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            # Immortal, so the school's monsters leave it be.
            patch_player_file(mud, "Zorbo", Levl=70, Room=TEMPLE)

            with mud.connect(timeout=120) as client:
                login(client, "Zorbo", PASSWORD)
                run(client, "scroll 0", 1.0)

                temple = run(client, "consider watcher", 1.6)
                self.assertNotIn("Not in the temple", temple, temple)

                run(client, "goto %d" % ZOMBIE_ROOM, 1.6)
                self.assertIn("zombie", run(client, "look", 1.4).lower())
                said = run(client, "consider zo", 1.6)
                self.assertIn("zombie", said.lower(), said)
                # One verdict from one model (CONSIDER rework, 2026-10-24).
                self.assertIn("blow for blow", said.lower(), said)
                verdicts = ("You should win easily.", "You should win.",
                            "You should win, but not by much.",
                            "It could go either way.", "You would probably lose.",
                            "You would almost certainly die.")
                lines = [line.strip() for line in said.splitlines()]
                self.assertEqual(1, sum(v in lines for v in verdicts), said)
                self.assertNotIn("naked and weaponless", said)
                self.assertNotIn("your own level", said.lower(), said)
                # "self" is still you.
                self.assertIn("your own level", run(client, "consider self", 1.6).lower())


if __name__ == "__main__":
    unittest.main()

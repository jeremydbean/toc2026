"""A trap that kills a player on the way out ends the move.

Audit 2026-10-21: after room_affect, move_char asked whether in_room was
NULL -- but a slain player is not extracted, they are moved to the death
room, so the move went on: char_from_room took them out of the death room
and char_to_room put them through the exit, alive on 1 hit point at the
far end. Every trap check in movement now asks gone_after_blow() against
the room the character stood in.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Ztrap1pass"
HALLS = 4202            # Halls of Healing: not safe, west to the Temple
TEMPLE = 4207
DEATH_ROOM = 4216


def run(client, command: str, settle: float = 1.2) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class TrapMovementSourceTests(unittest.TestCase):
    def test_no_trap_check_in_movement_asks_for_null(self) -> None:
        move = (ROOT / "src" / "act_move.c").read_text(encoding="latin-1")
        calls = [m.start() for m in re.finditer(r"room_affect\(", move)]
        self.assertEqual(len(calls), 5)
        for at in calls:
            after = move[at:at + 400]
            self.assertIn("gone_after_blow(", after, after)


@unittest.skipIf(SKIP is not None, SKIP or "")
class TrapMovementLiveTests(unittest.TestCase):
    def test_a_lethal_departure_trap_ends_the_move(self) -> None:
        with LiveMud() as mud:
            for name in ("Zwalker", "Ztrapper"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zwalker", Levl=10, Room=TEMPLE)
            patch_player_file(mud, "Ztrapper", Levl=70, Room=HALLS)

            with mud.connect(timeout=120) as walker, mud.connect(timeout=120) as trapper:
                login(walker, "Zwalker", PASSWORD)
                login(trapper, "Ztrapper", PASSWORD)
                run(walker, "scroll 0")
                run(trapper, "set skill ztrapper 'stinking cloud' 100")
                run(trapper, "set char ztrapper mana 30000")
                run(trapper, "set char zwalker hp 1")

                # The cloud's 2d8 kills a player on 1 hit point about one
                # time in four (dead is -11); a survivor simply arrives,
                # which is correct, so walk out until one does not.
                #
                # A survivor is also poisoned, and a poison tick can kill
                # them in the Temple between tries -- CI, 2026-10-21: that
                # death's "KILLED" was read with the next try's WEST, the
                # dead walker was still resting in the Halls, and the test
                # took it for the trap's. So each try stands the walker up,
                # reads off anything already said, and counts only a death
                # that came with this departure's gas.
                for _ in range(40):
                    run(trapper, "restore ztrapper", 0.3)
                    run(trapper, "cast 'stinking cloud'", 0.8)
                    run(trapper, "restore zwalker", 0.4)
                    run(trapper, "force zwalker stand", 0.4)
                    run(trapper, "transfer zwalker %d" % HALLS, 0.6)
                    walker.drain(0.5)
                    said = run(walker, "west", 2.0)
                    if "KILLED" in said and "Poison gas!" in said:
                        break
                    if "KILLED" in said:
                        continue   # the poison's tick, not the departure
                    # The control: a trap that does not kill lets the move
                    # finish.
                    self.assertRegex(run(trapper, "stat char zwalker", 1.4),
                                     r"Room: %d\b" % TEMPLE)
                else:
                    self.fail("the cloud never killed the walker")

                stat = run(trapper, "stat char zwalker", 1.4)
                self.assertRegex(stat, r"Room: %d\b" % DEATH_ROOM, stat)


if __name__ == "__main__":
    unittest.main()

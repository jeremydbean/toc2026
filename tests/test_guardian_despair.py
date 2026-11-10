"""A Hyrule guardian is never driven from its chamber by DESPAIR.

Play journal, 2026-11-10: a monk at 13% of his health typed FLEE in
Digdogger's den, and his despair answered it the stock way -- the
opponent fled instead. Digdogger walked east out of its den and stood in
the next room, out from behind the gate that asks for the recorder and
with its shutters reading the chamber as clear. A guardian holds its
room; the fleer's own flight runs instead, and the player is told why
despair did not take.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

from live_mud import (EAST_PADDOCK, WEST_PADDOCK, LiveMud, create_character,
                      login, patch_player_file, room_of, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_hyrule_area import BOSS_MOBS  # noqa: E402

SKIP = skip_reason()
PW = "Zdesppass1"
HELD = r"will not be driven from (its|his|her) ground"


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


class GuardianDespairSourceTests(unittest.TestCase):
    def test_despair_asks_whether_the_opponent_is_a_guardian(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        flee = fight.split("void do_flee(", 1)[1].split("\nvoid ", 1)[0]
        guard = flee.index("hyrule_native( victim )")
        self.assertLess(guard, flee.index("do_flee(victim"),
                        "the guardian test comes before the opponent's flight")
        special = (ROOT / "src" / "special.c").read_text(encoding="latin-1")
        helper = special.split("bool is_hyrule_guardian(", 1)[1].split("\n}", 1)[0]
        self.assertIn("spec_hyrule_guardian", helper)
        self.assertIn("spec_ganon", helper)


@unittest.skipIf(SKIP is not None, SKIP or "")
class GuardianDespairLiveTests(unittest.TestCase):
    def test_a_guardian_holds_its_room_and_the_fleer_flees(self) -> None:
        guardian = BOSS_MOBS[5]          # Digdogger: no blade hurts it whole
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zdespstaff", Levl=70, Room=WEST_PADDOCK)
            make(mud, "Zdespmonk", Levl=30, Room=WEST_PADDOCK,
                 HMV="30000 30000 1000 1000 1000 1000",
                 HMVP="30000 1000 1000", Sk="100 'despair'",
                 AfBy=512)      # infravision: the paddock is dark at night

            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as monk:
                login(staff, "Zdespstaff", PW)
                login(monk, "Zdespmonk", PW)
                for client in (staff, monk):
                    client.sync("scroll 0")
                staff.must(f"goto {WEST_PADDOCK}", "")
                staff.must(f"load mob {guardian}", "You create")
                stat = staff.must("stat mob digdogger", "Vnum: %d" % guardian)
                self.assertRegex(stat, r"Room: %d\b" % WEST_PADDOCK)
                # Out of the fight's way; STAT still finds it from the Temple.
                staff.must("goto 4207", "")

                replies = [monk.sync("kill digdogger", timeout=60)]
                # Ten directions are drawn and only east leads out, so a
                # FLEE panics about two times in five; try until one goes.
                for _ in range(20):
                    said = monk.sync("flee", timeout=60)
                    replies.append(said)
                    if "You flee from combat" in said:
                        break
                    if "aren't fighting" in said:
                        # Out of the fight with nobody fleeing: a guardian
                        # despair drove off has left the paddock (the old
                        # bug), and one still standing there is fought
                        # again (CI, 2026-11-10: the first FLEE found the
                        # monk already out of the fight).
                        stat = staff.must("stat mob digdogger", "Room:")
                        if not re.search(r"Room: %d\b" % WEST_PADDOCK, stat):
                            break
                        replies.append(monk.sync("kill digdogger", timeout=60))
                        continue
                    if "PANIC" not in said:
                        replies.append(monk.sync("kill digdogger", timeout=60))
                transcript = "\n".join(replies)

                where = re.search(r"Room: (-?\d+)",
                                  staff.must("stat mob digdogger", "Room:"))
                monk_room = room_of(staff, "zdespmonk")
                for client in (staff, monk):
                    client.send("quit")
                    client.wait_closed()

        self.assertNotIn("overcome with a feeling of despair", transcript)
        self.assertRegex(transcript, HELD)
        self.assertIn("You flee from combat", transcript, transcript)
        self.assertEqual(int(where.group(1)), WEST_PADDOCK,
                         "the guardian stayed in its room")
        self.assertEqual(monk_room, EAST_PADDOCK, "the fleer fled")


if __name__ == "__main__":
    unittest.main()

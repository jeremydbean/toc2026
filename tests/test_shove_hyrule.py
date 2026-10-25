"""SHOVE does not clear a Hyrule room (logs, 2026-10-25).

SHOVE refused aggressive monsters, and until October every Hyrule enemy
was one. Once Hyrule was calmed, a shove out of a shuttered dungeon room
opened its shutter with nothing fought: Trentlin, level 50 in Level 7,
pushed goriyas out of three rooms that way. SHOVE had no lag either, so
a miss was simply typed again. Now a Hyrule foe stands its ground,
refused before any roll, and a real attempt pays the skill's beats.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zshovepass1"
BOOMERANG_HALL = 30536   # Level 7: goriyas by reset, a shutter east


def run(client, command: str, settle: float = 1.4) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class ShoveSourceTests(unittest.TestCase):
    def test_hyrule_foes_are_refused_and_attempts_pay_lag(self) -> None:
        src = (ROOT / "src" / "act_move.c").read_text(encoding="latin-1")
        body = src[src.index("do_shove( CHAR_DATA *ch"):src.index("void do_enter(")]
        self.assertIn("if ( hyrule_foe( victim ) )", body)
        self.assertLess(body.index("hyrule_foe( victim )"), body.index("number_percent"))
        self.assertIn("WAIT_STATE( ch, skill_table[gsn_shove].beats );", body)
        self.assertLess(body.index("WAIT_STATE( ch, skill_table[gsn_shove].beats );"),
                        body.index("if(number_percent () < chance)"))
        # The shutters and SHOVE ask the same question.
        guard = src[src.index("static bool hyrule_room_has_guardian"):]
        guard = guard[:guard.index("\n}\n")]
        self.assertIn("hyrule_foe( victim )", guard)


@unittest.skipIf(SKIP is not None, SKIP or "")
class ShoveLiveTests(unittest.TestCase):
    def test_a_goriya_cannot_be_shoved_out_to_open_the_shutter(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zshover", PW)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zshover", Levl=50, Cla=3, Room=BOOMERANG_HALL,
                              AfBy=512, HMV="5000 5000 500 500 500 500",
                              HMVP="5000 500 500")
            path = mud.player_dir / "Zshover"
            text = path.read_text(encoding="latin-1")
            at = text.index("\nEnd\n")
            path.write_text(text[:at] + "\nSk 100 'shove'" + text[at:], encoding="latin-1")

            with mud.connect(timeout=120) as client:
                login(client, "Zshover", PW)
                run(client, "scroll 0")
                self.assertIn("goriya", run(client, "look", 1.4))
                refused = run(client, "shove goriya south", 1.4)
                self.assertIn("stands its ground", refused, refused)
                self.assertNotIn("out of the room", refused, refused)
                # A refusal costs no lag: the next command answers at once.
                self.assertIn("shutter is sealed", run(client, "east", 1.4))


if __name__ == "__main__":
    unittest.main()

"""FISTS OF FURY opens a fight as well as joining one (2026-10-25).

The blow loop asked "is ch still fighting this victim?" before its first
blow, to stop once a victim fled. Out of a fight nothing had started one
yet, so `fists <victim>` said "You attack in an all consuming fury!",
took 30 mana and 15 moves, and struck nothing. Alaric typed it 48 times
on 2026-10-25 before finding that plain FISTS worked once a fight had
begun some other way.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zfistpass1"
ROOM = 4202          # outside the Temple, which refuses a fight
GUARD = 29012


def run(client, command: str, settle: float = 1.4) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class FistsSourceTests(unittest.TestCase):
    def test_the_fight_check_waits_for_the_first_blow(self) -> None:
        src = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        body = src[src.index("void do_fists_of_fury("):src.index("void do_stunning_blow(")]
        self.assertIn("if ( struck && ch->fighting != victim )", body)
        self.assertLess(body.index("gsn_fists_of_fury, hit );"),
                        body.index("struck = true;"))


@unittest.skipIf(SKIP is not None, SKIP or "")
class FistsLiveTests(unittest.TestCase):
    def test_fists_at_a_named_victim_strikes(self) -> None:
        with LiveMud() as mud:
            for name in ("Zfiststaff", "Zfistmonk"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zfiststaff", Levl=70, Room=ROOM)
            patch_player_file(mud, "Zfistmonk", Levl=30, Cla=4, Room=ROOM,
                              HMV="3000 3000 500 500 500 500", HMVP="3000 500 500")
            path = mud.player_dir / "Zfistmonk"
            text = path.read_text(encoding="latin-1")
            at = text.index("\nEnd\n")
            path.write_text(text[:at] + "\nSk 100 'fists of fury'" + text[at:],
                            encoding="latin-1")

            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as monk:
                login(staff, "Zfiststaff", PW)
                login(monk, "Zfistmonk", PW)
                run(staff, "scroll 0")
                run(monk, "scroll 0")
                run(monk, "remove all", 1.2)
                run(staff, "set mob %d act +sentinel" % GUARD)   # it wanders off otherwise
                run(staff, "load mob %d" % GUARD, 1.2)
                run(staff, "set char guard hp 30000", 1.0)
                run(staff, "restore guard", 1.0)

                out = run(monk, "fists guard", 2.5)
                self.assertIn("all consuming fury", out, out)
                self.assertIn("Your fists of fury", out, out)

                run(staff, "slay guard", 1.2)
                monk.send("quit")
                self.assertTrue(monk.wait_closed())


if __name__ == "__main__":
    unittest.main()

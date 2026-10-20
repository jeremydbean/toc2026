"""A wizinvis immortal leaves no trace with players below the level.

"An Immortal appears in the room" was shown to every mortal when a
wizinvis immortal recalled (owner, 2026-10-20). PERS() named an unseen
immortal "An Immortal" rather than "someone", and act() delivered every
room message of theirs with that in place of the name -- arrivals,
departures, recalls, says and socials -- although HELP WIZINVIS had
always promised "your actions produce no messages to them".

wizinvis_hides() in handler.c is the one test; can_see asks it, and
act() drops a wizinvis actor's TO_ROOM and TO_NOTVICT messages for
anybody it hides them from. A message aimed at a victim still lands,
as "someone".
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zwizi1pass"
TEMPLE = 4207
SQUARE = 2401


def body(path: str, start: str) -> str:
    source = (ROOT / path).read_text(encoding="latin-1")
    text = source[source.index(start):]
    return text[:text.index("\n}\n")]


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class WizinvisSourceTests(unittest.TestCase):
    def test_nobody_unseen_is_ever_called_an_immortal(self) -> None:
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        pers = [l for l in merc.splitlines() if l.startswith("#define PERS(")][0]
        self.assertNotIn("An Immortal", pers)
        self.assertIn('"someone"', pers)

    def test_act_drops_a_wizinvis_actors_room_messages(self) -> None:
        act = body("src/comm.c", "void act_new(")
        self.assertIn("wizinvis_hides( ch, to )", act)
        self.assertIn("type == TO_ROOM || type == TO_NOTVICT", act)

    def test_can_see_asks_the_same_helper(self) -> None:
        see = body("src/handler.c", "bool can_see(")
        self.assertIn("wizinvis_hides( victim, ch )", see)
        helper = body("src/handler.c", "bool wizinvis_hides(")
        self.assertIn("PLR_WIZINVIS", helper)
        self.assertIn("sight_trust( looker ) < wch->invis_level", helper)


@unittest.skipIf(SKIP is not None, SKIP or "")
class WizinvisLiveTests(unittest.TestCase):
    def test_a_mortal_sees_nothing_of_a_wizinvis_immortal(self) -> None:
        with LiveMud() as mud:
            for name in ("Zwatcher", "Zhidden"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zwatcher", Levl=20, Room=TEMPLE)
            patch_player_file(mud, "Zhidden", Levl=70, Room=SQUARE)

            with mud.connect(timeout=120) as watcher, mud.connect(timeout=120) as imm:
                login(watcher, "Zwatcher", PASSWORD)
                login(imm, "Zhidden", PASSWORD)
                run(imm, "scroll 0", 1.0)
                run(watcher, "scroll 0", 1.0)
                self.assertIn("vanish into thin air", run(imm, "invis", 1.6))

                # Wizinvis: arriving, walking, speaking and recalling show the
                # mortal nothing. Recall is a skill roll, so whichever of its
                # room messages it produces, none may reach the watcher.
                mark = len(watcher.transcript)
                run(imm, "goto %d" % TEMPLE, 1.6)
                run(imm, "north", 1.6)
                run(imm, "south", 1.6)
                reply = run(imm, "say hello there", 1.6)
                self.assertIn("nobody below level 70 here heard that", reply)
                run(imm, "goto %d" % SQUARE, 1.6)
                run(imm, "recall", 1.6)
                watcher.drain(1.0)
                seen = watcher.transcript[mark:]
                for word in ("Zhidden", "Immortal", "someone", "appears", "arrive",
                             "leaves", "disappears", "prays", "hello there",
                             "raises into the sky"):
                    self.assertNotIn(word, seen, seen)
                run(imm, "goto %d" % TEMPLE, 1.6)
                self.assertNotIn("Zhidden", run(watcher, "look", 1.6))

                # Visible: the same steps are all seen, by name.
                self.assertIn("fade back into existence", run(imm, "invis 0", 1.6))
                mark = len(watcher.transcript)
                run(imm, "north", 1.6)
                run(imm, "south", 1.6)
                run(imm, "say hello again", 1.6)
                run(imm, "goto %d" % SQUARE, 1.6)
                run(imm, "goto %d" % TEMPLE, 1.6)
                watcher.drain(1.0)
                seen = watcher.transcript[mark:]
                self.assertIn("Zhidden leaves", seen)
                self.assertIn("Zhidden has arrived", seen)
                self.assertIn("Zhidden says 'hello again'", seen)
                self.assertIn("Zhidden appears before you.", seen)
                self.assertNotIn("someone", seen)

if __name__ == "__main__":
    unittest.main()

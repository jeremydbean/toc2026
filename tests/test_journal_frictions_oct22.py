"""Two frictions the play journal showed on 2026-10-22.

HEAL FRES at Hermie got no answer at all: the command goes through her
speech handler, which keeps quiet on a word it does not know so as not to
answer every SAY in the room. Asked by command, she answers now -- she
does not know that one, and here is her list.

OPEN WEST in the Oak Tree Square answered "You can't do that." four times
in a minute: the exit is open passage with no door, and the reply read
like a refusal. find_door, which OPEN, CLOSE, LOCK, UNLOCK and PICK all
ask, says so now.
"""
from __future__ import annotations

import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zfriction1"
ALTAR = 4208            # Hermie stands here for six hours after a boot
SQUARE = 2401           # the Oak Tree Square: west is open passage


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class JournalFrictionTests(unittest.TestCase):
    def test_hermie_answers_an_unknown_word_and_a_doorless_exit_says_so(self) -> None:
        with LiveMud(extra_env={"TOC_NO_BOOT_HERMIE": None}) as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zfriction", PW)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zfriction", Levl=20, Room=ALTAR)
            with mud.connect(timeout=120) as client:
                login(client, "Zfriction", PW)
                unknown = run(client, "heal fres")
                known = run(client, "heal refresh")
                client.send("quit")
                client.wait_closed()
            patch_player_file(mud, "Zfriction", Room=SQUARE)
            with mud.connect(timeout=120) as client:
                login(client, "Zfriction", PW)
                door = run(client, "open west")
                client.send("quit")
                client.wait_closed()

        self.assertIn("I don't know that one", unknown, unknown)
        self.assertIn("wink", known, known)
        self.assertIn("There is no door to the west", door, door)
        self.assertNotIn("You can't do that", door, door)


if __name__ == "__main__":
    unittest.main()

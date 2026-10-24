"""Nobody comes out of a file dead (Alaric's bug report, 2026-10-24).

A "before death" snapshot is written inside raw_kill, after the blow:
negative hit points, position DEAD, the room of the death. A full PRESTORE
to one logged the player in as a corpse -- every command answered "Lie
still; you are DEAD.", QUIT included, and no tick healed him. The loader
now stands such a character up at one hit point in the Temple.
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zrevive1pass"


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class ReviveSourceTests(unittest.TestCase):
    def test_the_loader_revives_after_reading(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        fn = save[save.index("static void revive_at_load("):]
        fn = fn[:fn.index("\n}\n")]
        self.assertIn("POS_STUNNED", fn)
        self.assertIn("ROOM_VNUM_TEMPLE", fn)
        self.assertIn("revive_at_load( ch );", save)


@unittest.skipIf(SKIP is not None, SKIP or "")
class ReviveLiveTests(unittest.TestCase):
    def test_a_file_saved_dying_logs_in_alive_in_the_temple(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zrevived", PASSWORD)
                client.drain(1.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            # As a death snapshot leaves it: dead, below zero, where it fell.
            patch_player_file(mud, "Zrevived", Levl=20, Pos=0, Room=3001,
                              HMV="-28 300 100 100 100 100")

            with mud.connect(timeout=120) as client:
                login(client, "Zrevived", PASSWORD)
                run(client, "scroll 0", 1.0)
                look = run(client, "look", 1.6)
                self.assertNotIn("you are DEAD", look, look)
                self.assertIn("Before the Altar", look, look)  # the Temple, 4207
                score = run(client, "score", 1.6)
                self.assertNotIn("you are DEAD", score, score)
                self.assertNotIn("-28", score, score)
                bye = run(client, "quit", 2.0)
                self.assertNotIn("not DEAD yet", bye, bye)

            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1") \
                if (mud.root / "log" / "toc.log").exists() else ""
            if log:
                self.assertEqual(log.count("Zrevived was saved dying"), 1, "logged once a login")


if __name__ == "__main__":
    unittest.main()

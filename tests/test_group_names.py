"""GROUP names your own group, unseen or not (Trentlin's log, 2026-10-24).

A stealthed Alaric was "Someone" in Trentlin's GROUP list: the listing
went through PERS(), which says "someone" for anybody the looker cannot
see. The Mudlet group panel, fed by name, showed him. Members are named
now; only wizinvis still hides.
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zgroup1pass"
TEMPLE = 4207


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class GroupNameSourceTests(unittest.TestCase):
    def test_the_list_does_not_ask_sight(self) -> None:
        comm = (ROOT / "src" / "act_comm.c").read_text(encoding="latin-1")
        group = comm[comm.index("void do_group( CHAR_DATA *ch, char *argument )"):]
        listing = group[:group.index("return;")]
        self.assertNotIn("PERS(", listing)
        self.assertIn("group_member_name(", listing)
        helper = comm[comm.index("static const char *group_member_name("):]
        self.assertIn("wizinvis_hides", helper[:helper.index("\n}\n")])


@unittest.skipIf(SKIP is not None, SKIP or "")
class GroupNameLiveTests(unittest.TestCase):
    def test_an_invisible_member_is_named(self) -> None:
        with LiveMud() as mud:
            for name in ("Zleader", "Zunseen"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            # A staff leader, so holylight can be turned off and on: the
            # leader must see the shade to take it into the group, and not
            # see it when the list is drawn.
            patch_player_file(mud, "Zleader", Levl=20, Tru=70, Room=TEMPLE)
            patch_player_file(mud, "Zunseen", Levl=20, Room=TEMPLE, AfBy=2)  # AFF_INVISIBLE (B)

            with mud.connect(timeout=120) as leader, mud.connect(timeout=120) as shade:
                login(leader, "Zleader", PASSWORD)
                login(shade, "Zunseen", PASSWORD)
                run(leader, "scroll 0", 0.8)
                run(shade, "scroll 0", 0.8)
                if "Zunseen" not in run(leader, "look", 1.4):
                    run(leader, "holylight", 1.0)
                self.assertIn("Zunseen", run(leader, "look", 1.4))
                run(shade, "follow zleader", 1.4)
                self.assertIn("joins your group", run(leader, "group zunseen", 1.6))

                run(leader, "holylight", 1.0)
                self.assertNotIn("Zunseen", run(leader, "look", 1.4),
                                 "the leader should no longer see the shade")
                listing = run(leader, "group", 1.6)
                self.assertIn("Zunseen", listing, listing)
                self.assertNotIn("Someone", listing, listing)

if __name__ == "__main__":
    unittest.main()

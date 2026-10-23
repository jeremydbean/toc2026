"""A player's corpse outlasts a restart (src/corpses.c, owner 2026-10-23).

Alaric died AFK; his corpse rotted in half an hour, the gear lay on the
floor, and the morning's deploy restarted the game and took it. A player's
corpse now lasts a week, and every one is written to ../corpse/registry.tsv
with the "before death" snapshot taken a moment earlier. At boot each corpse
still on the list is made again in its room from that snapshot. It comes off
the list for good once anything is taken out of it, it is picked up or it is
gone, so a rebuild never makes two of anything.
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PW = "Zkeeppass1"
ROOM = 4202
KIT = "sub issue sword"


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class CorpseKeeperSourceTests(unittest.TestCase):
    def test_a_player_corpse_lasts_a_week_and_is_written_down(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        corpse = fight[fight.index("void make_corpse( CHAR_DATA *ch )"):]
        corpse = corpse[:corpse.index("\n}\n")]
        self.assertIn("corpse->timer   = (sh_int) PC_CORPSE_TICKS;", corpse)
        self.assertIn("corpse_registry_died( ch, corpse );", corpse)
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        self.assertIn("#define PC_CORPSE_TICKS  10080", merc)
        handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1")
        for hook in ('corpse_registry_touched( obj, "it is gone" );',
                     'corpse_registry_touched( obj, "it was picked up" );',
                     'corpse_registry_touched( obj_from, "something was taken out" );',
                     "corpse_registry_moved( obj );"):
            self.assertIn(hook, handler)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CorpseKeeperLiveTests(unittest.TestCase):
    def test_a_corpse_is_made_again_after_a_restart_until_it_is_touched(self) -> None:
        with LiveMud() as mud:
            for name, level in (("Zkeepstaff", 70), ("Zkeepdead", 20)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=ROOM)

            registry = mud.root / "corpse" / "registry.tsv"
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as dead:
                login(staff, "Zkeepstaff", PW)
                login(dead, "Zkeepdead", PW)
                run(staff, "slay zkeepdead", 2.0)
                self.assertIn("corpse of Zkeepdead", run(staff, "look", 1.0))
                for client in (staff, dead):
                    client.send("quit")
                    client.wait_closed()
            self.assertIn("Zkeepdead\tZkeepdead.", registry.read_text(encoding="latin-1"))

            # A restart: the corpse is made again, in its room, with its gear.
            mud.restart()
            with mud.connect(timeout=120) as staff:
                login(staff, "Zkeepstaff", PW)
                self.assertIn("corpse of Zkeepdead", run(staff, "look", 1.0))
                self.assertIn(KIT, run(staff, "look in corpse", 1.5))
                # Taken from: off the list for good.
                run(staff, "get sword corpse", 1.5)
                staff.send("quit")
                staff.wait_closed()
            self.assertNotIn("Zkeepdead", registry.read_text(encoding="latin-1"))

            mud.restart()
            with mud.connect(timeout=120) as staff:
                login(staff, "Zkeepstaff", PW)
                self.assertNotIn("corpse of Zkeepdead", run(staff, "look", 1.0))
                staff.send("quit")
                staff.wait_closed()
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertIn("Corpse keeper: Zkeepdead's corpse made again in room 4202", log)
        self.assertIn("Corpse keeper: Zkeepdead's corpse off the list (something was taken out)", log)


if __name__ == "__main__":
    unittest.main()

"""Hermie after a restart (owner, 2026-11-10: "a play reward for players
who get kicked off due to a restart").

The game writes how many mortals are playing to log/online.txt; at boot,
if the restart put mortals off, Hermie keeps the Oak Tree Square (2401)
for four hours, standing there while any mortal plays and stepping away
while none does. A restart with only staff, or nobody, on brings none.
TOC_HERMIE_BOOT_SECONDS shortens the window for the test. HERMIE is the
staff command now; SPELLUP still works.
"""

from __future__ import annotations

import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zhermrest11"
SQUARE = 2401


def make(mud, name, level):
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed()
    patch_player_file(mud, name, Levl=level, Room=4207)


def online(mud) -> str:
    path = mud.root / "log" / "online.txt"
    return path.read_text().strip() if path.exists() else ""


def playing(mud) -> int:
    """The mortals playing now: the file's second field."""
    fields = online(mud).split()
    return int(fields[1]) if len(fields) > 1 else -1


def last_played(mud) -> int:
    """How many mortals were playing when one last was: the fourth field."""
    fields = online(mud).split()
    return int(fields[3]) if len(fields) > 3 else -1


def wait_for(check, timeout=40.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(1.0)
    return False


def hermie_at_square(staff) -> bool:
    return "Hermie" in staff.sync(f"at {SQUARE} look", timeout=60)


@unittest.skipIf(SKIP is not None, SKIP or "")
class HermieRestartTests(unittest.TestCase):
    def test_a_restart_that_put_players_off_brings_her_for_a_while(self) -> None:
        with LiveMud(extra_env={"TOC_HERMIE_BOOT_SECONDS": "60"}) as mud:
            make(mud, "Zhermstaff", 70)
            make(mud, "Zhermplay", 10)

            # A restart with only staff on: no Hermie.
            with mud.connect(timeout=120) as staff:
                login(staff, "Zhermstaff", PW)
                self.assertTrue(wait_for(lambda: playing(mud) == 0), online(mud))
                mud.restart()
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as player:
                login(staff, "Zhermstaff", PW)
                login(player, "Zhermplay", PW)
                time.sleep(9)               # two mobile pulses
                self.assertFalse(hermie_at_square(staff), "no mortal was put off")
                # The mortal is on when the next restart comes.
                self.assertTrue(wait_for(lambda: playing(mud) == 1), online(mud))
                mud.restart()

            with mud.connect(timeout=120) as staff:
                login(staff, "Zhermstaff", PW)
                time.sleep(9)
                self.assertFalse(hermie_at_square(staff), "staff alone: she waits")
                with mud.connect(timeout=120) as player:
                    login(player, "Zhermplay", PW)
                    self.assertTrue(wait_for(lambda: hermie_at_square(staff)), "she came")
                    said = player.sync("goto 2401", timeout=60)
                    player.send("quit")
                    player.wait_closed()
                self.assertTrue(wait_for(lambda: not hermie_at_square(staff)),
                                "no mortal playing: she steps away")
                with mud.connect(timeout=120) as player:
                    login(player, "Zhermplay", PW)
                    self.assertTrue(wait_for(lambda: hermie_at_square(staff)), "back again")
                    # The window ends: she goes for good.
                    self.assertTrue(wait_for(lambda: not hermie_at_square(staff), timeout=90),
                                    "the window ended")
                    time.sleep(9)
                    self.assertFalse(hermie_at_square(staff), "and stays away")
                    # HERMIE is the staff command; SPELLUP still works.
                    placed = staff.sync("hermie", timeout=60)
                    again = staff.sync("spellup", timeout=60)
                    player.send("quit")
                staff.send("quit")
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertIn("Hermie: the restart put no mortal off", log)
        self.assertIn("Hermie: the restart put 1 mortal off", log)
        self.assertIn("Hermie: at the Oak Tree Square", log)
        self.assertIn("she steps away from the Oak Tree Square", log)
        self.assertIn("four hours are over", log)
        self.assertIn("taking requests", placed, placed)
        self.assertIn("already standing right here", again, again)
        self.assertNotIn("Zhermplay", log.split("Hermie:", 1)[1].split("\n", 1)[0])
        del said

    def test_a_mortal_who_quit_at_the_warning_still_counts(self) -> None:
        """Owner, 2026-11-11: a deploy warns players a minute ahead, and a
        level 34 quit 34 seconds before the boot -- the file read 0 and she
        stayed away. A mortal who played within ten minutes counts."""
        with LiveMud(extra_env={"TOC_HERMIE_BOOT_SECONDS": "300"}) as mud:
            make(mud, "Zhermstaff", 70)
            make(mud, "Zhermquit", 10)
            with mud.connect(timeout=120) as player:
                login(player, "Zhermquit", PW)
                self.assertTrue(wait_for(lambda: playing(mud) == 1), online(mud))
                player.send("quit")
                player.wait_closed()
            self.assertTrue(wait_for(lambda: playing(mud) == 0 and last_played(mud) == 1),
                            online(mud))
            mud.restart()
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as player:
                login(staff, "Zhermstaff", PW)
                login(player, "Zhermquit", PW)
                self.assertTrue(wait_for(lambda: hermie_at_square(staff)), "she came")
                for client in (player, staff):
                    client.send("quit")
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertIn("put 1 mortal off (gone within ten minutes of the boot)", log)


if __name__ == "__main__":
    unittest.main()

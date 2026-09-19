"""Quitting reaches wizinfo, not just the room and the log file.

Connecting, entering the game, reconnecting and losing link all announced
themselves to staff. A clean QUIT did not, so an immortal anywhere but the
quitter's room watched people arrive and never leave.
"""
from __future__ import annotations

import unittest

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Zlogoutone1"


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class LogoutWizinfoTests(unittest.TestCase):
    def test_a_quit_is_announced_to_staff_elsewhere(self) -> None:
        with LiveMud() as mud:
            for name in ("Zwatcher", "Zleaver"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.send("quit")
                    client.wait_closed()
            patch_player_file(mud, "Zwatcher", Levl=70)

            with mud.connect(timeout=120) as watcher:
                login(watcher, "Zwatcher", PASSWORD)
                # Somewhere the quitter is not, so only wizinfo can carry it.
                run(watcher, "goto 3700", settle=3.0)

                with mud.connect(timeout=120) as leaver:
                    login(leaver, "Zleaver", PASSWORD)
                    watcher.drain(2.0)

                    mark = len(watcher.transcript)
                    leaver.send("quit")
                    leaver.wait_closed()

                watcher.drain(4.0)
                seen = watcher.transcript[mark:]

            self.assertIn("WIZINFO", seen,
                          f"the quit should reach wizinfo:\n{seen}")
            self.assertIn("Zleaver has left the game", seen,
                          f"the quit should name who left:\n{seen}")


if __name__ == "__main__":
    unittest.main()

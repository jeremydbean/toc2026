"""The creator and trust 71 (owner, 2026-10-22).

Killuminati, and only Killuminati, is the creator: get_trust() is 72
whatever his level, so he outranks every implementor and his WIZINVIS
defaults to 72, hidden from everyone. TRUST may now give 71, and only he
can, since nobody else's trust reaches it; 71 outranks every implementor
and sees him at WIZI 71. SHUTDOWN, REBOOT, LOG, SNOOP, BAN, ALLOW,
WIZLOCK, NEWLOCK, DENY and UNDENY are his alone, and the notices of his
arrival and departure go out at his WIZINVIS level.

The fixture is a synthetic Killuminati in a throwaway world -- the
creator is a name, so the test has to use it.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from live_mud import (  # noqa: E402
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()
PASSWORD = "Zcreator1"
TEMPLE = 4207


def run(client, command: str, settle: float = 1.5) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud: LiveMud, name: str) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Levl=70, Room=TEMPLE)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CreatorRankTests(unittest.TestCase):
    def test_the_creator_and_trust_seventy_one(self) -> None:
        with LiveMud() as mud:
            for name in ("Killuminati", "Zimpl", "Zmisery"):
                make(mud, name)
            with mud.connect(timeout=120) as creator, \
                    mud.connect(timeout=120) as impl, \
                    mud.connect(timeout=120) as trusted:
                login(creator, "Killuminati", PASSWORD)
                login(impl, "Zimpl", PASSWORD)
                login(trusted, "Zmisery", PASSWORD)

                # The creator's commands are his alone.
                for command in ("shutdown", "log zmisery", "snoop zmisery",
                                "ban zsomesite", "wizlock", "deny zmisery"):
                    self.assertIn("Huh?", run(impl, command), command)

                # Only the creator can give 71, and 71 then outranks 70.
                self.assertIn("Limited to your trust", run(impl, "trust zmisery 71"))
                self.assertIn("trusted at level 71", run(creator, "trust zmisery 71"))
                self.assertIn("outrank", run(impl, "trust zmisery 0"))
                trusted.drain(1.0)
                self.assertIn("trusted at level 71", trusted.transcript)
                self.assertIn("You failed", run(impl, "nochannels zmisery"))
                self.assertIn("Zmisery", run(creator, "stat zmisery"))

                # WIZINVIS at the creator's own trust hides him from all.
                self.assertIn("vanish", run(creator, "wizinvis"))
                run(impl, "holylight")
                run(trusted, "holylight")
                self.assertNotIn("Killuminati", run(impl, "who"))
                self.assertNotIn("Killuminati", run(trusted, "who"))
                self.assertNotIn("Killuminati", run(impl, "look"))
                # 71 outranks the creator in nothing: he is not even there.
                self.assertIn("aren't here", run(trusted, "nochannels killuminati"))

                # WIZI 71 lets trust 71 see him, and still not 70.
                run(creator, "wizinvis 71")
                self.assertIn("Killuminati", run(trusted, "who"))
                self.assertNotIn("Killuminati", run(impl, "who"))

                # His leaving and arriving reach nobody below his WIZI.
                run(creator, "wizinvis 72")
                mark_impl, mark_trusted = len(impl.transcript), len(trusted.transcript)
                creator.send("quit")
                self.assertTrue(creator.wait_closed())
                with mud.connect(timeout=120) as again:
                    login(again, "Killuminati", PASSWORD)
                    again.drain(1.5)
                    self.assertIn("Killuminati", run(again, "who"))
                    impl.drain(1.0)
                    trusted.drain(1.0)
                    self.assertNotIn("Killuminati", impl.transcript[mark_impl:])
                    self.assertNotIn("Killuminati", trusted.transcript[mark_trusted:])
                    again.send("quit")
                    again.wait_closed()
                for client in (impl, trusted):
                    client.send("quit")
                    client.wait_closed()

            # The log files keep the record.
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")
            self.assertIn("Killuminati@", log)
            self.assertIn("Killuminati set Zmisery's trust to 71.", log)


if __name__ == "__main__":
    unittest.main()

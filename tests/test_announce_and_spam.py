"""Announcements, the shared broadcast path, and the immortal spam exemption.

An announcement reaches every player, unlike wizinfo, which only reaches
immortals at or above a level and therefore looks broken to an operator who
sends one and sees nothing. The dashboard and the in-game command share one
implementation so the two cannot drift apart.

The spam guard forced a `quit` after 25 identical commands. Staff repeat
commands legitimately -- walking a vnum range, loading objects in bulk,
hammering repop while testing -- and being disconnected mid-task is never
the right answer.
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

IMMORTAL_LEVEL = 70
PASSWORD = "Zannounce1"


def run(client, command: str, settle: float = 1.5) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make_immortal(mud: LiveMud, name: str) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        client.wait_closed()
    patch_player_file(mud, name, Levl=IMMORTAL_LEVEL)


@unittest.skipIf(SKIP is not None, SKIP or "")
class AnnounceTests(unittest.TestCase):
    def test_an_announcement_reaches_an_ordinary_player(self) -> None:
        """The whole point: not just immortals."""
        with LiveMud() as mud:
            make_immortal(mud, "Zannimm")
            with mud.connect(timeout=120) as imm:
                login(imm, "Zannimm", PASSWORD)
                with mud.connect(timeout=120) as mortal:
                    create_character(mortal, "Zannmort", PASSWORD)
                    run(imm, "announce the realm is about to reboot", settle=2.5)
                    mortal.drain(2.5)
                    seen = mortal.transcript
                    self.assertIn("ANNOUNCEMENT", seen, seen[-600:])
                    self.assertIn(
                        "the realm is about to reboot",
                        seen,
                        seen[-600:],
                    )

    def test_an_empty_announcement_is_refused(self) -> None:
        with LiveMud() as mud:
            make_immortal(mud, "Zanntwo")
            with mud.connect(timeout=120) as imm:
                login(imm, "Zanntwo", PASSWORD)
                output = run(imm, "announce")
                self.assertIn("Announce what?", output, output)


@unittest.skipIf(SKIP is not None, SKIP or "")
class ImmortalSpamTests(unittest.TestCase):
    def test_an_immortal_is_not_booted_for_repeating_a_command(self) -> None:
        with LiveMud() as mud:
            make_immortal(mud, "Zspamimm")
            with mud.connect(timeout=120) as client:
                login(client, "Zspamimm", PASSWORD)
                # Well past the 25-repeat threshold, same burst and
                # settle time the mortal gets.
                client.send_raw(b"look" + bytes([10]))
                for _ in range(59):
                    client.send("look")
                client.drain(25.0)
                transcript = client.transcript
                self.assertNotIn("PUT A LID ON IT", transcript)

                # Still connected and responding.
                output = run(client, "score", settle=2.5)
                self.assertTrue(
                    output.strip(),
                    "the immortal stopped responding after repeating a command",
                )

    def test_a_mortal_is_still_stopped(self) -> None:
        """The guard still exists; it just does not apply to staff."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zspammort", PASSWORD)
                # The server consumes one queued line per pulse, so the 25th
                # repeat lands several seconds after the burst is sent.
                client.send_raw(b"look\n" * 60)
                client.drain(25.0)
                self.assertIn("PUT A LID ON IT", client.transcript)


if __name__ == "__main__":
    unittest.main()

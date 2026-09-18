"""WIZINFO has to close the colour it opens.

The line opened with a colour code and never closed it, so cyan ran on into
whatever printed next -- the room description, a tell, the prompt. Every
other coloured channel closes with {00; wizinfo was the only one that did
not, and on a staff channel that fires on every login it discolours most of
what an immortal sees.

This reads `client.raw` rather than `client.transcript`: the harness strips
ANSI out of the transcript, which is exactly the evidence the test needs.
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

PASSWORD = "Zwizcol11"
RESET = b"\x1b[0m"


@unittest.skipIf(SKIP is not None, SKIP or "")
class WizinfoColourTests(unittest.TestCase):
    def test_the_colour_is_closed_before_the_newline(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as setup:
                create_character(setup, "Zwizcolimm", PASSWORD)
                setup.send("quit")
                setup.wait_closed()
            patch_player_file(mud, "Zwizcolimm", Levl=70)

            with mud.connect(timeout=120) as god:
                login(god, "Zwizcolimm", PASSWORD)
                god.drain(2.0)

                mark = len(god.raw)
                # Another login is the easiest way to fire a wizinfo.
                with mud.connect(timeout=120) as other:
                    create_character(other, "Zwizcolmort", PASSWORD)
                    other.drain(2.0)
                god.drain(3.0)

                tail = god.raw[mark:]
                index = tail.find(b"[WIZINFO]")
                self.assertNotEqual(index, -1,
                                    "no wizinfo arrived to inspect")

                end = tail.find(b"\n", index)
                self.assertNotEqual(end, -1, "wizinfo line was not terminated")
                line = tail[index:end]

                self.assertIn(RESET, line,
                              f"colour left open: {line!r}")
                self.assertTrue(line.rstrip(b"\r").endswith(RESET),
                                f"reset is not the last thing on the line: {line!r}")


if __name__ == "__main__":
    unittest.main()

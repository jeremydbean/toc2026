"""Long messages: delivered, trimmed, never fatal.

Three things used to cut people off mid-sentence, and the worst of them
took the connection with it:

  * `say` truncated itself at 156 characters, silently, and no other
    channel did.
  * Nothing could exceed MAX_INPUT_LENGTH, which was 256.
  * Overrunning the read buffer returned FALSE from read_from_descriptor,
    and the caller closes the socket on FALSE -- so pasting a long line
    disconnected you and lost what you had typed.

A limit still exists, deliberately: nobody should be able to paste a
screenful into a channel. What changed is that hitting it costs you the
tail of one line, visibly, instead of your session.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from live_mud import (  # noqa: E402
    LiveMud,
    create_character,
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Zinputlen1"

# MAX_INPUT_LENGTH, and the usable width the reader leaves inside it.
MAX_INPUT = 512
USABLE = MAX_INPUT - 2


def run(client, command: str, settle: float = 2.5) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class InputLengthTests(unittest.TestCase):
    def test_a_long_say_arrives_whole(self) -> None:
        """Comfortably past the old 156-character self-truncation."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zinplena", PASSWORD)
                client.drain(2.0)

                # 300 characters: fine now, cut at 156 before.
                message = ("the quick brown fox jumps over the lazy dog. " * 7)[:300]
                output = run(client, f"say {message}", settle=3.0)

                self.assertIn(message[-40:], output,
                              "the tail of the message was dropped")
                self.assertNotIn("too long", output)

    def test_an_oversized_line_is_trimmed_and_still_delivered(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zinpover", PASSWORD)
                client.drain(2.0)

                message = "z" * (MAX_INPUT + 400)
                output = run(client, f"say {message}", settle=4.0)

                # Told what happened, rather than left guessing.
                self.assertIn("was not sent", output)
                # And what fit still went out as speech.
                self.assertIn("You say", output)

                # Still connected and still responsive.
                self.assertIn("Zinpover", run(client, "score", settle=3.0))

    def test_a_long_paste_does_not_drop_the_link(self) -> None:
        """The old code closed the socket on buffer overflow."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zinppast", PASSWORD)
                client.drain(2.0)

                # Bigger than inbuf (4 * MAX_INPUT_LENGTH) in one go, with
                # no line ending until the very end.
                client.send("say " + ("y" * (MAX_INPUT * 4 + 200)))
                client.drain(5.0)

                self.assertIn("Zinppast", run(client, "score", settle=4.0),
                              "the connection did not survive the paste")

    def test_tells_are_not_truncated_either(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as first:
                create_character(first, "Zinptela", PASSWORD)
                first.drain(2.0)

                with mud.connect(timeout=120) as second:
                    create_character(second, "Zinptelb", PASSWORD)
                    second.drain(2.0)

                    message = ("pack my box with five dozen liquor jugs. " * 8)[:320]
                    run(first, f"tell Zinptelb {message}", settle=3.0)

                    second.drain(2.0)
                    self.assertIn(message[-40:], second.transcript,
                                  "the tail of the tell was dropped")


if __name__ == "__main__":
    unittest.main()

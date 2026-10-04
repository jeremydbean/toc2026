"""Several commands on one typed line, separated by semicolons.

The browser client always split them itself; a telnet client such as
Mudlet sent "n;kill orc" whole and got "Huh?" (Alaric, 2026-10-04). The
server now splits on the browser's rules -- quotes and \\; keep a
semicolon in the command -- and never splits a line that defines an
alias or carries a password.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from live_mud import LiveMud, create_character, skip_reason  # noqa: E402

SKIP = skip_reason()
PASSWORD = "Zchainpw12"


def run(client, command: str, settle: float = 2.0) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class TypedChainTests(unittest.TestCase):
    def test_a_typed_line_splits_on_the_browsers_rules(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zchainer", PASSWORD)

                said = run(client, "say first;say second", 3.0)
                self.assertNotIn("Huh?", said, said)
                one, two = said.find("first"), said.find("second")
                self.assertTrue(0 <= one < two, said)

                said = run(client, r"say left\;right")
                self.assertIn("left;right", said, said)

                said = run(client, "say 'inside;quotes'")
                self.assertIn("inside;quotes", said, said)

                # A line that sets an alias keeps its semicolons for it.
                run(client, "alias zpair say alpha;say omega")
                said = run(client, "zpair", 3.0)
                self.assertIn("alpha", said, said)
                self.assertIn("omega", said, said)

                # Too many on one line runs none of them.
                said = run(client, ";".join(["say flood"] * 25), 3.0)
                self.assertIn("more commands than one line may hold", said, said)
                self.assertNotIn("You say 'flood'", said, said)

                client.send("quit")
                self.assertTrue(client.wait_closed())


if __name__ == "__main__":
    unittest.main()

"""ALIAS, which players have had saved in their files all along.

The storage, the save format and the substitution in interp.c all survived;
only the command to read and write them was a stub. So existing aliases still
fired when typed, but nobody could list, add or remove one -- and `alias`
answered "That command is not available."

The load-bearing case is the round trip: an alias set in one session has to
still be there, and still expand, after a quit and a fresh login.
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
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Zaliaspw12"


def run(client, command: str, settle: float = 1.5) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class AliasTests(unittest.TestCase):
    def test_set_list_expand_and_remove(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zaliasone", PASSWORD)

                self.assertIn("no aliases defined", run(client, "alias").lower())

                out = run(client, "alias gc get coins")
                self.assertIn("aliased to", out.lower(), out)

                listing = run(client, "alias")
                self.assertIn("gc", listing)
                self.assertIn("get coins", listing)

                single = run(client, "alias gc")
                self.assertIn("get coins", single, single)

                # It must actually expand: "gc" runs "get coins", and with
                # nothing to get the server says so rather than rejecting the
                # command as unknown.
                expanded = run(client, "gc")
                self.assertNotIn("Huh?", expanded, expanded)

                self.assertIn("removed", run(client, "unalias gc").lower())
                self.assertIn("no aliases defined", run(client, "alias").lower())

                # The form the help has always documented must work too.
                run(client, "alias gc get coins")
                self.assertIn("removed", run(client, "alias delete gc").lower())
                self.assertIn("no aliases defined", run(client, "alias").lower())

    def test_an_alias_survives_a_relog(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zaliastwo", PASSWORD)
                run(client, "alias gc get coins")
                client.send("quit")
                self.assertTrue(client.wait_closed())

            saved = (mud.root / "player" / "Zaliastwo").read_text(
                encoding="latin-1", errors="replace"
            )
            self.assertIn("Alias gc get coins", saved, "alias was not saved")

            with mud.connect(timeout=120) as client:
                login(client, "Zaliastwo", PASSWORD)
                listing = run(client, "alias")
                self.assertIn("get coins", listing, listing)

    def test_aliasing_alias_itself_is_refused(self) -> None:
        """Otherwise there is no way left to undo it."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zaliasthr", PASSWORD)
                out = run(client, "alias alias say hello")
                self.assertIn("no way to undo", out.lower(), out)
                out = run(client, "alias unalias say hello")
                self.assertIn("no way to undo", out.lower(), out)


if __name__ == "__main__":
    unittest.main()

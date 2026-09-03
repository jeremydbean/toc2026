"""End-to-end tests that play the real game over Telnet.

Every other test in this suite asserts on source text. These boot an actual
server, connect a socket, create a character, and play, which is the only
layer that catches a change that compiles and reads correctly but does not
work. Data is isolated in a temporary tree; see tests/live_mud.py.

Skipped automatically when there is no built binary or on Windows, where the
game is not natively runnable. Run them from WSL, Linux, macOS, or CI.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, skip_reason


SKIP = skip_reason()


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveGameplayTests(unittest.TestCase):
    def test_server_boots_and_greets(self) -> None:
        with LiveMud() as mud, mud.connect() as client:
            client.expect("by what name")
            self.assertIn("DikuMUD", client.transcript)

    def test_character_creation_reaches_the_game(self) -> None:
        with LiveMud() as mud, mud.connect() as client:
            create_character(client, "Ziptestone", "harnesspw")

            # A newly created character should be able to look around.
            output = client.command("look", settle=1.5)
            self.assertTrue(
                output.strip(),
                f"`look` produced nothing.\n{client.transcript[-2000:]}",
            )

            # And the character file should exist in the throwaway tree, not
            # anywhere near real player data.
            client.command("save", settle=1.5)
            self.assertTrue(
                (mud.player_dir / "Ziptestone").is_file(),
                f"no pfile written; player dir holds "
                f"{[p.name for p in mud.player_dir.iterdir()]}",
            )

    def test_core_commands_respond(self) -> None:
        with LiveMud() as mud, mud.connect() as client:
            create_character(client, "Ziptesttwo", "harnesspw")

            for command, expected in (
                ("score", "level"),
                ("inventory", "carrying"),
                ("commands", "commands"),
            ):
                with self.subTest(command=command):
                    output = client.command(command, settle=1.5).lower()
                    self.assertIn(
                        expected,
                        output,
                        f"`{command}` output lacked {expected!r}: {output[-600:]}",
                    )

    def test_character_persists_across_a_reconnect(self) -> None:
        with LiveMud() as mud:
            with mud.connect() as client:
                create_character(client, "Ziptestthree", "harnesspw")
                client.command("save", settle=2.0)
                client.command("quit", settle=2.0)

            # Reconnect with the same credentials.
            with mud.connect() as client:
                client.expect("by what name")
                client.send("Ziptestthree")
                client.expect("password")
                client.send("harnesspw")
                client.drain(2.5)
                self.assertNotIn("Wrong password", client.transcript)

                output = client.command("score", settle=2.0).lower()
                self.assertIn("level", output)

    def test_wrong_password_is_rejected(self) -> None:
        with LiveMud() as mud:
            with mud.connect() as client:
                create_character(client, "Ziptestfour", "harnesspw")
                client.command("save", settle=2.0)
                client.command("quit", settle=2.0)

            with mud.connect() as client:
                client.expect("by what name")
                client.send("Ziptestfour")
                client.expect("password")
                client.send("definitelywrong")
                client.drain(2.0)
                self.assertIn("Wrong password", client.transcript)


if __name__ == "__main__":
    unittest.main()

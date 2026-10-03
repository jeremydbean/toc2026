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
    patch_player_file,
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


ROOT = Path(__file__).resolve().parent.parent
TEMPLE = 4207


class MultiAliasSourceTests(unittest.TestCase):
    """The rules that are easiest to lose in a later edit."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.interp = (ROOT / "src" / "interp.c").read_text(encoding="latin-1")
        cls.comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")

    def test_alias_output_is_never_expanded_again(self) -> None:
        self.assertIn("!from_alias", self.interp)
        self.assertIn("from_alias = interp_from_alias;", self.interp)
        self.assertIn("interp_from_alias = FALSE;", self.interp)

    def test_the_rest_waits_in_the_input_buffer(self) -> None:
        """Queued like typed input, so lag still falls between them."""
        self.assertIn("queue_alias_input( ch->desc, parts + 1, count - 1 )",
                      self.interp)
        body = self.comm[self.comm.index("bool queue_alias_input("):]
        body = body[:body.index("\n}\n")]
        self.assertIn("memmove( d->inbuf + used, d->inbuf", body)
        self.assertIn("ALIAS_MAX_QUEUED", body)

    def test_each_command_is_bounded(self) -> None:
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        self.assertRegex(merc, r"#define ALIAS_MAX_COMMANDS\s+10\b")
        self.assertIn("ALIAS_MAX_COMMANDS", self.interp)


@unittest.skipIf(SKIP is not None, SKIP or "")
class MultiAliasLiveTests(unittest.TestCase):
    def test_commands_run_in_order_with_arguments_on_the_last(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zaliasmul", PASSWORD)

                out = run(client, "alias zz say first;say second")
                self.assertIn("aliased to", out.lower(), out)
                said = run(client, "zz", 3.0)
                self.assertNotIn("Huh?", said, said)
                one = said.find("first")
                two = said.find("second")
                self.assertTrue(0 <= one < two, said)

                # What is typed after the alias goes on its last command.
                run(client, "alias zl say alpha;say")
                said = run(client, "zl omega", 3.0)
                self.assertIn("alpha", said, said)
                self.assertIn("omega", said, said)
                self.assertLess(said.find("alpha"), said.find("omega"), said)

                # \; is a semicolon inside one command, not a break.
                run(client, r"alias zs say left\;right")
                said = run(client, "zs", 2.0)
                self.assertIn("left;right", said, said)

    def test_the_limits(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zaliaslim", PASSWORD)

                eleven = ";".join(["look"] * 11)
                out = run(client, "alias zb " + eleven)
                self.assertIn("at most 10", out, out)
                self.assertIn("not defined", run(client, "alias zb"))

                # An alias cannot reach another alias, or itself.
                run(client, "alias zinner say nested")
                run(client, "alias zouter zinner;zouter")
                said = run(client, "zouter", 3.0)
                self.assertNotIn("nested", said, said)
                self.assertIn("Huh?", said, said)

    def test_lag_falls_between_the_commands(self) -> None:
        """The second command waits out the first one's WAIT_STATE."""
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zaliaslag", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zaliaslag", Levl=10, Room=TEMPLE)

            with mud.connect(timeout=120) as client:
                login(client, "Zaliaslag", PASSWORD)
                # A wrong old password costs a fixed ten seconds of
                # WAIT_STATE, which no skill roll can skip. A spell is a
                # worse probe: at 1% it is refused before any lag is paid.
                run(client, "alias zc password Znotitatall Znewpasswd;"
                            "say afterwards")
                mark = len(client.transcript)
                client.send("zc")
                client.drain(4.0)
                early = client.transcript[mark:]
                self.assertIn("Wait 10 seconds", early, early)
                self.assertNotIn("afterwards", early, early)
                client.drain(9.0)
                late = client.transcript[mark:]
                self.assertIn("afterwards", late, late)

    def test_a_watched_alias_never_writes_a_password(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zaliaslog", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zaliaslog", Levl=45, Tru=70, Room=TEMPLE)

            with mud.connect(timeout=120) as client:
                login(client, "Zaliaslog", PASSWORD)
                # Defined before the log goes on: the definition is the
                # player's own text, the expansion is what is under test.
                run(client, "alias zp password Zsecretone Zsecrettwo;"
                            "password Zsecretthr Zsecretfou")
                run(client, "log Zaliaslog", 1.8)
                run(client, "zp", 4.0)
                client.drain(12.0)

            text = ""
            for path in (mud.root / "log").glob("*"):
                if path.is_file():
                    text += path.read_text(encoding="latin-1", errors="replace")
            if not text:
                self.skipTest("this harness does not capture the game log")

            self.assertIn("arguments withheld", text)
            for secret in ("Zsecretone", "Zsecrettwo", "Zsecretthr", "Zsecretfou"):
                self.assertNotIn(secret, text.split("log Zaliaslog", 1)[-1])


if __name__ == "__main__":
    unittest.main()

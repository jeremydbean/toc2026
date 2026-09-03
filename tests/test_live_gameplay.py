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

from live_mud import (
    DO,
    IAC,
    SB,
    SE,
    TELOPT_GMCP,
    TELOPT_MSSP,
    TELOPT_NAWS,
    WILL,
    LiveMud,
    create_character,
    login,
    naws,
    parse_mssp,
    skip_reason,
)


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
                login(client, "Ziptestthree", "harnesspw")
                client.send("score")
                client.expect("level")

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


@unittest.skipIf(SKIP is not None, SKIP or "")
class LoginThrottleTests(unittest.TestCase):
    """Brute-force throttling.

    Loopback is exempt by default because the browser client bridges through
    the dashboard, so every web player shares 127.0.0.1 and throttling it
    would let one fumbled web login lock out all of them.
    TOC_THROTTLE_LOOPBACK=1 opts loopback in so this can be tested at all.
    """

    THROTTLED_ENV = {"TOC_THROTTLE_LOOPBACK": "1"}

    def _make_character(self, mud, name: str, password: str) -> None:
        with mud.connect() as client:
            create_character(client, name, password)
            client.command("save", settle=2.0)
            client.command("quit", settle=2.0)

    def _attempt(self, mud, name: str, password: str) -> str:
        """One full login attempt. Returns the transcript."""
        with mud.connect() as client:
            first = client.expect("by what name", "too many failed login")
            if first == "too many failed login":
                return client.transcript
            client.send(name)
            client.expect("password")
            client.send(password)
            client.drain(1.0)
            return client.transcript

    def test_repeated_wrong_passwords_eventually_refuse_the_address(self) -> None:
        with LiveMud(extra_env=self.THROTTLED_ENV) as mud:
            self._make_character(mud, "Ziptestfive", "harnesspw")

            # Threshold is 5 failures; none of those should be refused outright.
            for attempt in range(5):
                transcript = self._attempt(mud, "Ziptestfive", "wrongpassword")
                with self.subTest(attempt=attempt):
                    self.assertIn("Wrong password", transcript)

            # The next connection is refused before the greeting.
            with mud.connect() as client:
                client.expect("too many failed login")
                self.assertNotIn("By what name", client.transcript)

    def test_a_successful_login_clears_the_failure_history(self) -> None:
        with LiveMud(extra_env=self.THROTTLED_ENV) as mud:
            self._make_character(mud, "Ziptestsix", "harnesspw")

            # Four failures: one short of the threshold.
            for _ in range(4):
                self.assertIn(
                    "Wrong password",
                    self._attempt(mud, "Ziptestsix", "wrongpassword"),
                )

            # A correct login must reset the counter.
            with mud.connect() as client:
                login(client, "Ziptestsix", "harnesspw")
                client.command("quit", settle=2.0)

            # So four more failures still must not trip the block.
            for _ in range(4):
                self.assertIn(
                    "Wrong password",
                    self._attempt(mud, "Ziptestsix", "wrongpassword"),
                )

            with mud.connect() as client:
                client.expect("by what name")

    def test_loopback_is_exempt_without_the_opt_in(self) -> None:
        """Default config must never throttle the shared web-bridge address."""
        with LiveMud() as mud:
            self._make_character(mud, "Ziptestseven", "harnesspw")

            for _ in range(8):
                self._attempt(mud, "Ziptestseven", "wrongpassword")

            with mud.connect() as client:
                client.expect("by what name")
                self.assertNotIn("Too many failed login", client.transcript)


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(SKIP is not None, SKIP or "")
class TelnetProtocolTests(unittest.TestCase):
    """MSSP, NAWS, and GMCP.

    The input path previously had no IAC handling at all, so negotiation
    bytes reached the command interpreter as garbage. These tests cover both
    halves: the options work, and a client that negotiates nothing is
    unaffected.
    """

    def test_server_offers_its_options(self) -> None:
        with LiveMud() as mud, mud.connect() as client:
            client.expect("by what name")
            self.assertTrue(
                client.negotiated(WILL, TELOPT_MSSP), "no WILL MSSP"
            )
            self.assertTrue(
                client.negotiated(WILL, TELOPT_GMCP), "no WILL GMCP"
            )
            self.assertTrue(
                client.negotiated(DO, TELOPT_NAWS), "no DO NAWS"
            )

    def test_mssp_reports_status_to_a_crawler(self) -> None:
        with LiveMud() as mud, mud.connect() as client:
            client.expect("by what name")
            client.send_raw(bytes([IAC, DO, TELOPT_MSSP]))
            client.drain(2.0)

            blocks = client.subnegotiations(TELOPT_MSSP)
            self.assertTrue(blocks, "server sent no MSSP subnegotiation")

            fields = parse_mssp(blocks[-1])
            self.assertEqual(fields.get("NAME"), "Times of Chaos")
            self.assertEqual(fields.get("CODEBASE"), "ROM 2.4")
            self.assertEqual(fields.get("FAMILY"), "DikuMUD")

            # Required numeric fields must actually be numbers.
            self.assertTrue(fields.get("PLAYERS", "").isdigit(), fields)
            self.assertTrue(fields.get("UPTIME", "").isdigit(), fields)
            # Uptime is a boot timestamp, so it must be a plausible epoch.
            self.assertGreater(int(fields["UPTIME"]), 1_000_000_000)

    def test_mssp_counts_a_logged_in_player(self) -> None:
        with LiveMud() as mud:
            with mud.connect() as player:
                create_character(player, "Zipeight", "harnesspw")
                # Confirm the character is actually in the game before
                # asserting on the player count.
                self.assertIn("level", player.command("score", settle=2.0).lower())

                with mud.connect() as crawler:
                    crawler.expect("by what name")
                    crawler.send_raw(bytes([IAC, DO, TELOPT_MSSP]))
                    crawler.drain(2.0)
                    fields = parse_mssp(crawler.subnegotiations(TELOPT_MSSP)[-1])
                    self.assertEqual(fields.get("PLAYERS"), "1")

    def test_naws_is_recorded_and_opt_in(self) -> None:
        with LiveMud() as mud, mud.connect() as client:
            # Sent before reading anything, so the greeting stays unconsumed
            # for create_character().
            client.send_raw(naws(100, 42))
            create_character(client, "Zipnine", "harnesspw")

            # The negotiation must not have leaked into the command stream.
            self.assertNotIn("Huh?", client.transcript)

            # The size is reported, but not applied behind the player's back:
            # in do_scroll(), lines == 0 means they turned paging off on
            # purpose, so NAWS must not silently override it.
            client.send("scroll")
            client.expect("100x42")

            # Opting in applies it.
            client.send("scroll auto")
            client.expect("42 lines")

            client.send("scroll")
            client.expect("42 lines per page")

    def test_gmcp_vitals_arrive_only_after_the_client_enables_gmcp(self) -> None:
        with LiveMud() as mud:
            # Without enabling GMCP, no GMCP subnegotiation should ever arrive.
            with mud.connect() as quiet:
                create_character(quiet, "Zipten", "harnesspw")
                quiet.command("look", settle=1.0)
                self.assertEqual(quiet.subnegotiations(TELOPT_GMCP), [])

            with mud.connect() as client:
                client.send_raw(bytes([IAC, DO, TELOPT_GMCP]))
                create_character(client, "Zipelev", "harnesspw")
                client.command("look", settle=1.5)

                blocks = client.subnegotiations(TELOPT_GMCP)
                self.assertTrue(blocks, "no GMCP data after enabling it")

                payload = blocks[-1].decode("latin-1")
                self.assertTrue(payload.startswith("Char.Vitals "), payload)

                import json

                vitals = json.loads(payload[len("Char.Vitals "):])
                for key in ("hp", "maxhp", "mana", "maxmana", "move", "maxmove", "level"):
                    self.assertIn(key, vitals)
                self.assertGreater(vitals["maxhp"], 0)

    def test_a_client_that_negotiates_nothing_is_unaffected(self) -> None:
        """Regression guard for the plain-Telnet majority."""
        with LiveMud() as mud, mud.connect() as client:
            create_character(client, "Ziptwelve", "harnesspw")
            output = client.command("score", settle=1.5).lower()
            self.assertIn("level", output)
            self.assertNotIn("huh?", output)

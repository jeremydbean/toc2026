"""The online count has to come from the game, not the login journal.

`players_online()` long claimed in its own docstring that the journal
names were "bounded by real connections", with "the socket count ... the
authority on how many". Nothing of the sort happened: it read
log/logins.tsv and returned however many names had an unclosed `connect`.
A session that dies without a recorded close leaves one of those behind
for good, so the number only ever drifts upward -- and the deploy gate,
which holds a game restart while players are on, was reading it.

The game already counts descriptors in CON_PLAYING and publishes the
total over MSSP. These tests pin that it is what gets reported, and that
the journal is used only to put names to it.
"""
from __future__ import annotations

import importlib
import os
import socket
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

IAC, SE, SB, DO = 255, 240, 250, 253
TELOPT_MSSP = 70
MSSP_VAR, MSSP_VAL = 1, 2

REPO_ROOT = Path(__file__).resolve().parents[1]

# Oldest first, the way parse_login_journal yields it. Ana and Bo were
# never recorded as leaving; Cy quit cleanly.
JOURNAL = (
    "1787680000\tAna\t10.0.0.1\tconnect\n"
    "1787680001\tBo\t10.0.0.2\tconnect\n"
    "1787680002\tCy\t10.0.0.3\tconnect\n"
    "1787680003\tCy\t10.0.0.3\tquit\n"
)


class FakeGame:
    """A listener that answers DO MSSP with a PLAYERS count."""

    def __init__(self, players: int | None):
        self.players = players
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(4)
        self.port = self.sock.getsockname()[1]
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.running = True
        self.thread.start()

    def _serve(self) -> None:
        while self.running:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                try:
                    conn.settimeout(2.0)
                    conn.recv(64)          # the DO MSSP
                    if self.players is not None:
                        body = (bytes([MSSP_VAR]) + b"PLAYERS"
                                + bytes([MSSP_VAL])
                                + str(self.players).encode())
                        conn.sendall(bytes([IAC, SB, TELOPT_MSSP]) + body
                                     + bytes([IAC, SE]))
                    else:
                        conn.sendall(b"Welcome, but no status for you.\r\n")
                except OSError:
                    pass

    def close(self) -> None:
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass


@contextmanager
def server_with(port: int):
    """Import webadmin.server pointed at `port` for the game."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        journal = root / "logins.tsv"
        journal.write_text(JOURNAL, encoding="utf-8")
        (root / "players").mkdir()
        (root / "backups").mkdir()

        env = {
            "WEB_ADMIN_TOKEN": "secret",
            "AREA_PATH": str(REPO_ROOT / "area"),
            "PLAYER_PATH": str(root / "players"),
            "BACKUP_PATH": str(root / "backups"),
            "LOGIN_JOURNAL": str(journal),
            "QUEUE_PATH": str(root / "webadmin.queue"),
            "MUD_HOST": "127.0.0.1",
            "MUD_PORT": str(port),
            "TOC_UPDATE_REQUEST_PATH": "",
        }
        with patch.dict(os.environ, env, clear=False):
            sys.modules.pop("webadmin.server", None)
            module = importlib.import_module("webadmin.server")
            try:
                yield module
            finally:
                sys.modules.pop("webadmin.server", None)


def fresh(module) -> None:
    """Drop the short probe cache so each assertion asks again."""
    module._GAME_PROBE_CACHE = None


class PlayersOnlineTests(unittest.TestCase):
    def test_mssp_body_decodes_to_fields(self) -> None:
        with server_with(1) as module:
            body = (bytes([MSSP_VAR]) + b"PLAYERS" + bytes([MSSP_VAL]) + b"3"
                    + bytes([MSSP_VAR]) + b"NAME" + bytes([MSSP_VAL]) + b"ToC")
            self.assertEqual(
                {"PLAYERS": "3", "NAME": "ToC"}, module._parse_mssp(body))

    def test_the_count_comes_from_the_game_not_the_journal(self) -> None:
        """The journal has two unclosed sessions; the game says one."""
        game = FakeGame(players=1)
        try:
            with server_with(game.port) as module:
                fresh(module)
                online = module.players_online()
        finally:
            game.close()

        self.assertEqual("game", online["source"])
        self.assertEqual(1, online["count"],
                         "the game's CON_PLAYING count is the authority")
        self.assertEqual(["Bo"], online["names"],
                         "the stale name is the older session, not the newer")

    def test_an_empty_game_reports_nobody_however_stale_the_journal(self) -> None:
        """This is the case the deploy gate turns on."""
        game = FakeGame(players=0)
        try:
            with server_with(game.port) as module:
                fresh(module)
                online = module.players_online()
        finally:
            game.close()

        self.assertEqual(0, online["count"])
        self.assertEqual([], online["names"])

    def test_more_players_than_names_keeps_the_game_count(self) -> None:
        game = FakeGame(players=5)
        try:
            with server_with(game.port) as module:
                fresh(module)
                online = module.players_online()
        finally:
            game.close()

        self.assertEqual(5, online["count"])
        self.assertEqual(["Ana", "Bo"], online["names"],
                         "names explain who they can; they do not cap the count")

    def test_an_unreachable_game_says_the_count_came_from_the_journal(self) -> None:
        """Silence must be visible, not passed off as a reading."""
        with socket.socket() as probe:      # a port with nothing behind it
            probe.bind(("127.0.0.1", 0))
            dead = probe.getsockname()[1]

        with server_with(dead) as module:
            fresh(module)
            online = module.players_online()

        self.assertEqual("journal", online["source"])
        self.assertEqual(2, online["count"])
        self.assertEqual(["Ana", "Bo"], online["names"])

    def test_health_still_reports_the_game_down_when_it_is(self) -> None:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            dead = probe.getsockname()[1]

        with server_with(dead) as module:
            fresh(module)
            self.assertFalse(module.read_process_health()["merc"])

    def test_health_reports_the_game_up_when_it_answers(self) -> None:
        game = FakeGame(players=2)
        try:
            with server_with(game.port) as module:
                fresh(module)
                self.assertTrue(module.read_process_health()["merc"])
        finally:
            game.close()


if __name__ == "__main__":
    unittest.main()

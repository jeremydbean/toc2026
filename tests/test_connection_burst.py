"""Many connections at once each get a greeting (review, 2026-11-12).

init_socket listened with a backlog of three and the game loop accepted one
connection a pass, four passes a second. Four or more clients connecting
before any of them logged in -- the live modules open every client first
and log them in after -- filled the queue: on macOS the kernel reset the
next connection, and a later client's greeting never came, while the
server ran on. Linux drops the SYN instead and the client retries a second
or three later, so the same burst there is slow rather than lost.

The game now listens with SOMAXCONN on a non-blocking socket and accepts
every connection waiting in one pass (at most ACCEPT_BURST_MAX). This test
opens a burst of raw connections at once, holds them all open, and needs a
greeting on every one -- and a player already in the game answered
throughout. Loopback is exempt from the connection guard, so the burst
meets no guard policy; nothing about the guard changed.
"""
from __future__ import annotations

import re
import socket
import threading
import time
import unittest

from live_mud import LiveMud, create_character, skip_reason

SKIP = skip_reason()
BURST = 24
GREETING = re.compile(rb"by what name|name:|what is your name", re.I)


def greet(port: int, out: dict, i: int, start: threading.Event) -> None:
    """Connect when told, then read until the greeting or 20 s."""
    start.wait()
    t0 = time.monotonic()
    got = b""
    try:
        sock = socket.create_connection(("127.0.0.1", port), timeout=20)
    except OSError as exc:
        out[i] = ("connect failed: %s" % exc, None, None)
        return
    out.setdefault("socks", []).append(sock)
    sock.settimeout(0.5)
    deadline = t0 + 20
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            continue
        except OSError as exc:
            out[i] = ("reset: %s" % exc, None, got)
            return
        if not chunk:
            out[i] = ("hung up", None, got)
            return
        got += chunk
        if GREETING.search(got):
            out[i] = ("ok", time.monotonic() - t0, None)
            return
    out[i] = ("no greeting", None, got)


@unittest.skipIf(SKIP is not None, SKIP or "")
class ConnectionBurstTests(unittest.TestCase):
    def test_a_burst_of_connections_is_greeted_and_play_goes_on(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as player:
                create_character(player, "Zburster", "Zburstpw1")
                player.sync("scroll 0")

                out: dict = {}
                start = threading.Event()
                threads = [threading.Thread(target=greet, args=(mud.port, out, i, start))
                           for i in range(BURST)]
                for t in threads:
                    t.start()
                start.set()
                # The player already in the game keeps being answered while
                # the burst is being taken in.
                during = player.sync("who", timeout=30)
                for t in threads:
                    t.join(timeout=40)
                after = player.sync("who", timeout=30)
                for sock in out.pop("socks", []):
                    sock.close()

        results = [out.get(i, ("thread did not finish", None, None)) for i in range(BURST)]
        failed = {i: r for i, r in enumerate(results) if r[0] != "ok"}
        self.assertEqual(failed, {}, "every connection in the burst gets a greeting")
        slowest = max(r[1] for r in results)
        # One a pass took a burst of 24 six seconds and more; all in one
        # pass is well under a second. Three is room for a busy runner.
        self.assertLess(slowest, 3.0, "the burst was taken in one pass, not one a pulse")
        self.assertIn("Zburster", during, "the player was answered during the burst")
        self.assertIn("Zburster", after, "and after it")


if __name__ == "__main__":
    unittest.main()

"""Closing a WebSocket the browser already dropped is not an error.

Every handler in webadmin/server.py closes its socket in a ``finally``.
When the browser has already gone -- a closed tab, a phone losing signal --
that close raises WebSocketDisconnect, or uvicorn's ClientDisconnected (an
OSError), and the handlers caught only RuntimeError. Each dropped tab put a
forty-line traceback in toc-web's journal: 44 of them in four days on the
live host, from the game client (/ws) and the live-log feed (2026-10-08).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WebSocketCloseTests(unittest.TestCase):
    def test_every_close_tolerates_a_vanished_client(self) -> None:
        source = (ROOT / "webadmin" / "server.py").read_text(encoding="utf-8")
        closes = [m.start() for m in re.finditer(r"await websocket\.close\(\)\n", source)]
        self.assertTrue(closes, "no websocket.close() found")
        for at in closes:
            guard = source[at:at + 200]
            handler = re.search(r"except \(([^)]*)\)|except (\w+)", guard)
            self.assertIsNotNone(handler, guard)
            caught = handler.group(1) or handler.group(2)
            for kind in ("RuntimeError", "WebSocketDisconnect", "OSError"):
                self.assertIn(kind, caught,
                              f"close() at offset {at} does not catch {kind}: {guard}")


if __name__ == "__main__":
    unittest.main()

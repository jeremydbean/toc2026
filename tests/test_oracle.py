"""The Oracle worker: dormant by default, capped, and safe.

It must cost nothing until a key is set and it is enabled, must honour a
daily USD ceiling and a per-player hourly cap, and must never raise into
the caller (the game would be speaking its return value).
"""
from __future__ import annotations

import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from webadmin import oracle  # noqa: E402  (import-safe without anthropic)


def _fake_anthropic(answer="Seek the guildmaster.", out_tokens=5):
    mod = types.ModuleType("anthropic")

    class Resp:
        content = [types.SimpleNamespace(type="text", text=answer)]
        usage = types.SimpleNamespace(
            input_tokens=10, output_tokens=out_tokens,
            cache_read_input_tokens=0, cache_creation_input_tokens=0)

    class Messages:
        def create(self, **kw):
            return Resp()

    class Client:
        def __init__(self, **kw):
            self.messages = Messages()

    mod.Anthropic = Client
    return mod


class OracleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.state = Path(self.tmp) / "oracle.state.json"
        self._saved_env = dict(
            (k, __import__("os").environ.get(k))
            for k in ("ORACLE_API_KEY", "ANTHROPIC_API_KEY", "ORACLE_ENABLED",
                      "ORACLE_MODEL", "ORACLE_DAILY_USD", "ORACLE_PER_PLAYER_HOUR",
                      "ORACLE_STATE"))
        import os
        os.environ["ORACLE_STATE"] = str(self.state)
        for k in ("ORACLE_API_KEY", "ANTHROPIC_API_KEY", "ORACLE_ENABLED"):
            os.environ.pop(k, None)
        sys.modules.pop("anthropic", None)

    def tearDown(self):
        import os
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        sys.modules.pop("anthropic", None)

    def _enable(self):
        import os
        os.environ["ORACLE_API_KEY"] = "sk-test"
        os.environ["ORACLE_ENABLED"] = "1"
        os.environ["ORACLE_MODEL"] = "claude-haiku-4-5"
        os.environ["ORACLE_DAILY_USD"] = "1.0"

    def test_dormant_without_key_or_flag(self):
        self.assertFalse(oracle.is_enabled())
        self.assertIn("nothing", oracle.consult("Alaric", "how do I remort?").lower())
        # A key but not enabled is still dormant.
        import os
        os.environ["ORACLE_API_KEY"] = "sk-test"
        self.assertFalse(oracle.is_enabled())

    def test_answers_when_enabled(self):
        self._enable()
        sys.modules["anthropic"] = _fake_anthropic("Remort at level 54 or beyond.")
        out = oracle.consult("Alaric", "how do I remort?")
        self.assertEqual(out, "Remort at level 54 or beyond.")
        # Spend was recorded.
        self.assertGreater(json.loads(self.state.read_text())["spent"], 0.0)

    def test_daily_cap_silences_it(self):
        self._enable()
        sys.modules["anthropic"] = _fake_anthropic()
        self.state.write_text(json.dumps(
            {"day": oracle._today(), "spent": 5.0, "players": {}}))
        self.assertIn("enough today", oracle.consult("Alaric", "hi?"))

    def test_per_player_hourly_cap(self):
        import os
        self._enable()
        os.environ["ORACLE_PER_PLAYER_HOUR"] = "2"
        sys.modules["anthropic"] = _fake_anthropic()
        self.assertNotIn("quickly", oracle.consult("Alaric", "q1?"))
        self.assertNotIn("quickly", oracle.consult("Alaric", "q2?"))
        self.assertIn("quickly", oracle.consult("Alaric", "q3?"))
        # A different player is unaffected.
        self.assertNotIn("quickly", oracle.consult("Milenko", "q1?"))

    def test_api_failure_degrades_quietly(self):
        self._enable()
        broken = types.ModuleType("anthropic")

        class Client:
            def __init__(self, **kw):
                raise RuntimeError("network down")
        broken.Anthropic = Client
        sys.modules["anthropic"] = broken
        self.assertIn("nothing", oracle.consult("Alaric", "q?").lower())

    def test_answers_are_one_line(self):
        self.assertEqual(oracle._one_line("a\n\r  b   c\n"), "a b c")


if __name__ == "__main__":
    unittest.main()

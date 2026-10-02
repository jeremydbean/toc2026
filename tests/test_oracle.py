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
                      "ORACLE_STATE", "ORACLE_USAGE", "ORACLE_CACHE",
                      "ORACLE_CACHE_DAYS"))
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

    def test_poll_once_drains_and_answers(self):
        self._enable()
        sys.modules["anthropic"] = _fake_anthropic("Go to the temple.")
        ask = Path(self.tmp) / "oracle.ask"
        answer = Path(self.tmp) / "oracle.answer"
        ask.write_text("1700000000\tAlaric\twhere is the temple?\n"
                       "1700000001\tMilenko\thow do I level?\n",
                       encoding="utf-8")
        self.assertEqual(oracle.poll_once(ask, answer), 2)
        out = answer.read_text(encoding="utf-8").splitlines()
        self.assertEqual(out[0], "Alaric\tGo to the temple.")
        self.assertEqual(out[1], "Milenko\tGo to the temple.")
        # Drained, so the spool can never back up.
        self.assertEqual(ask.read_text(encoding="utf-8"), "")

    def test_cache_hit_answers_without_the_api(self):
        import os
        self._enable()
        os.environ["ORACLE_USAGE"] = str(Path(self.tmp) / "usage.tsv")

        class Boom:
            def __init__(self, **kw):
                raise AssertionError("the API must not be called on a cache hit")
        broken = types.ModuleType("anthropic")
        broken.Anthropic = Boom
        sys.modules["anthropic"] = broken

        oracle._cache_put("how do i remort|warrior|human|54", "Remort at 54.")
        out = oracle.consult("Alaric", "How do I remort?",
                             cache_key="how do i remort|warrior|human|54")
        self.assertEqual(out, "Remort at 54.")
        row = (Path(self.tmp) / "usage.tsv").read_text().strip().split("\t")
        self.assertEqual(row[-1], "1")          # logged as cached
        self.assertEqual(float(row[7]), 0.0)    # at no cost

    def test_real_answers_are_cached_refusals_are_not(self):
        self._enable()
        sys.modules["anthropic"] = _fake_anthropic("Seek the smith.")
        oracle.consult("Alaric", "best sword?", cache_key="k-sword")
        self.assertEqual(oracle._cache_get("k-sword"), "Seek the smith.")

        sys.modules["anthropic"] = _fake_anthropic("__OFFTOPIC__")
        self.assertEqual(oracle.consult("Alaric", "capital of France?",
                                        cache_key="k-france"), "__OFFTOPIC__")
        self.assertIsNone(oracle._cache_get("k-france"))

    def test_poll_once_accepts_a_context_and_cache_key(self):
        self._enable()
        sys.modules["anthropic"] = _fake_anthropic("Go north.")
        ask = Path(self.tmp) / "oracle.ask"
        answer = Path(self.tmp) / "oracle.answer"
        ask.write_text("1700000000\tAlaric\twhere do I level?\n", encoding="utf-8")
        n = oracle.poll_once(ask, answer,
                             lambda p, q: ("Supplicant: Alaric.", "k-level"))
        self.assertEqual(n, 1)
        self.assertEqual(answer.read_text(encoding="utf-8").strip(), "Alaric\tGo north.")
        self.assertEqual(oracle._cache_get("k-level"), "Go north.")

    def test_poll_once_drains_even_when_dormant(self):
        ask = Path(self.tmp) / "oracle.ask"
        answer = Path(self.tmp) / "oracle.answer"
        ask.write_text("1700000000\tAlaric\thi?\n", encoding="utf-8")
        self.assertEqual(oracle.poll_once(ask, answer), 1)
        self.assertIn("Alaric\t", answer.read_text(encoding="utf-8"))
        self.assertEqual(ask.read_text(encoding="utf-8"), "")


class OracleWiringTests(unittest.TestCase):
    """The C side is wired so the dormant worker can actually be reached."""

    def read(self, *p):
        return ROOT.joinpath(*p).read_text(encoding="latin-1")

    def test_spec_and_commands_are_registered(self):
        special = self.read("src", "special.c")
        self.assertIn('{ "spec_oracle",', special)
        self.assertIn("spec_oracle", special)
        interp = self.read("src", "interp.c")
        self.assertIn('{ "ask",', interp)
        self.assertIn('{ "oracle",', interp)       # staff status/playback/dismiss
        self.assertIn('{ "pray",', interp)         # players summon her
        self.assertIn("src/oracle.c", self.read("CMakeLists.txt"))
        # A spoken question (or farewell) also reaches her, via the do_say hook.
        self.assertIn("oracle_hears", self.read("src", "act_comm.c"))

    def test_she_leaves_when_her_supplicant_does(self):
        # The departure hook retires her when the summoner leaves the room.
        self.assertIn("oracle_on_char_from_room", self.read("src", "handler.c"))

    def test_conversations_are_journalled_for_playback(self):
        self.assertIn("oracle.tsv", self.read("src", "oracle.c"))

    def test_oracle_mob_exists_in_limbo(self):
        self.assertIn("the Oracle sits here", self.read("area", "limbo.are"))

    def test_web_service_can_write_oracle_state(self):
        # ProtectSystem=strict makes /var/lib/toc read-only unless declared;
        # without this the $1/day cap silently never recorded spend.
        unit = self.read("deploy", "windows-vm", "toc-web.service")
        self.assertIn("StateDirectory=toc", unit)

    def test_a_question_mark_anywhere_reaches_her(self):
        # "where is X?  give me directions" must count, not just a trailing ?.
        self.assertIn("strchr( said, '?' )", self.read("src", "oracle.c"))

    def test_off_topic_protocol_is_wired(self):
        # The model emits a sentinel for off-topic; the game turns it into a
        # refusal and escalates.
        self.assertIn("__OFFTOPIC__", self.read("webadmin", "oracle.py"))
        self.assertIn("ORACLE_OFFTOPIC", self.read("src", "oracle.c"))

    def test_divine_wards_are_wired(self):
        fight = self.read("src", "fight.c")
        # Unattackable Oracle (melee + spells).
        self.assertIn("is_oracle_mob", fight)
        # Killuminati survives every instant death (raw_kill guard), and the
        # warded set is immune to fatality.
        self.assertIn("is_killuminati", fight)
        self.assertIn("is_divinely_warded", fight)
        # The god-level farslay command, warded only against Killuminati.
        magic2 = self.read("src", "magic2.c")
        self.assertIn("do_farslay", magic2)
        self.assertIn("is_divinely_warded", magic2)
        self.assertIn('{ "farslay",', self.read("src", "interp.c"))
        # The shared ward helpers live in oracle.c.
        oracle = self.read("src", "oracle.c")
        self.assertIn("divine_ward_backfire", oracle)
        self.assertIn("is_killuminati", oracle)


if __name__ == "__main__":
    unittest.main()

"""A cached Oracle answer is built only from what its key holds.

Review, 2026-11-12: _oracle_cache_key keyed an answer by the question,
class, race, level and guild, while the context the model answered from
carried the asker's name and worn gear (and the prompt named them) -- so
the next same-level player was handed an answer grounded in, and perhaps
naming, somebody else. And leveling advice, which quotes the live balance
feed, was cached for seven days whatever the feed did.

Now a question with a key is answered from the shared context (level,
class, race, guild; ABILITIES by digest in the key), the prompt does not
name the asker, the key carries the balance feed's version when the
answer quotes it (and the holidays on, for the gear finder), and the
context is built only on a cache miss. Characters are synthetic Z names.
"""

from __future__ import annotations

import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from webadmin import oracle  # noqa: E402

try:
    from webadmin import server  # needs fastapi
    SKIP = None
except Exception as exc:  # pragma: no cover - env dependent
    server = None
    SKIP = f"webadmin.server unavailable: {exc}"

GEAR = {100: "a zalpha-only glowing blade", 101: "a zbeta-only iron maul",
        102: "a zalpha-new silver helm"}


def profile(vnum):
    return {"class_name": "warrior", "race": "human", "level": 30, "guild_name": "knights",
            "equipment": [{"vnum": vnum, "wear": 16, "level": 28}]}


def fake_anthropic(calls):
    mod = types.ModuleType("anthropic")

    class Resp:
        content = [types.SimpleNamespace(type="text", text="Seek the guildmaster.")]
        usage = types.SimpleNamespace(input_tokens=10, output_tokens=5,
                                      cache_read_input_tokens=0, cache_creation_input_tokens=0)
        stop_reason = "end_turn"

    class Messages:
        def create(self, **kw):
            calls.append(kw)
            return Resp()

    class Client:
        def __init__(self, **kw):
            self.messages = Messages()

    mod.Anthropic = Client
    return mod


@unittest.skipIf(SKIP is not None, SKIP or "")
class SharedAnswerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.saved = {k: os.environ.get(k) for k in (
            "ORACLE_API_KEY", "ANTHROPIC_API_KEY", "ORACLE_ENABLED", "ORACLE_MODEL",
            "ORACLE_DAILY_USD", "ORACLE_PER_PLAYER_HOUR", "ORACLE_STATE", "ORACLE_USAGE",
            "ORACLE_CACHE", "ORACLE_CACHE_DAYS")}
        os.environ.update(ORACLE_API_KEY="sk-test", ORACLE_ENABLED="1",
                          ORACLE_MODEL="claude-haiku-4-5", ORACLE_DAILY_USD="5",
                          ORACLE_PER_PLAYER_HOUR="100",
                          ORACLE_STATE=str(tmp / "oracle.state.json"),
                          ORACLE_USAGE=str(tmp / "usage.tsv"),
                          ORACLE_CACHE=str(tmp / "oracle.cache.json"))
        os.environ.pop("ORACLE_CACHE_DAYS", None)
        self.calls: list = []
        self.saved_anthropic = sys.modules.get("anthropic")
        sys.modules["anthropic"] = fake_anthropic(self.calls)
        oracle._HISTORY.clear()
        oracle._LAST_CACHE_KEY.clear()

        self.profiles = {"Zalpha": profile(100), "Zbeta": profile(101), "Zgamma": profile(101)}
        self.progress = tmp / "progress.tsv"
        self.progress.write_text("", encoding="latin-1")
        (tmp / "player").mkdir()
        self.builds = []
        real_context = server._oracle_context

        def counted_context(*args, **kw):
            self.builds.append(kw.get("shared", False))
            return real_context(*args, **kw)

        async def fake_level(**kw):
            return {"mobs": [{"name": "a zfield troll", "level": 31, "area": "Zfields",
                              "xp_per_kill": 200, "xp_per_hour": 9000, "count": 4,
                              "aggressive": False, "directions": "s;s", "basis": "measured"}]}

        async def fake_best(**kw):
            return {"Wielded": [{"vnum": 7, "name": "a zfinder sword", "level": 29,
                                 "area": "Zfields"}]}

        def no_live(reqs, timeout=2.5, asker=""):
            raise AssertionError("a shared or generic question looked up the live game")

        objects = {v: types.SimpleNamespace(short_desc=n, carried_by=[]) for v, n in GEAR.items()}
        self.patches = [
            patch.object(server, "parse_player_file", lambda name: self.profiles.get(name)),
            patch.object(server, "parser", types.SimpleNamespace(objects=objects, mobiles={},
                                                                 rooms={})),
            patch.object(server, "PLAYER_PATH", tmp / "player"),
            patch.object(server, "PROGRESS_LOG", self.progress),
            patch.object(server, "load_player_help", lambda: []),
            patch.object(server, "load_directions", lambda: {"routes": []}),
            patch.object(server, "_oracle_live_lookup", no_live),
            patch.object(server, "get_leveling", fake_level),
            patch.object(server, "get_best_gear", fake_best),
            patch.object(server, "_oracle_context", counted_context),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self.patches):
            p.stop()
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if self.saved_anthropic is None:
            sys.modules.pop("anthropic", None)
        else:
            sys.modules["anthropic"] = self.saved_anthropic
        oracle._HISTORY.clear()
        oracle._LAST_CACHE_KEY.clear()
        self.tmp.cleanup()

    def ask(self, player: str, question: str, abilities: str = "") -> str:
        """One question through the poller, as the game spools it, at the
        start of a sitting (a follow-up is never cached)."""
        oracle.forget(player)
        tmp = Path(self.tmp.name)
        ask, answer = tmp / "oracle.ask", tmp / "oracle.answer"
        extra = ("\tABILITIES:" + abilities) if abilities else ""
        ask.write_text(f"1700000000\t{player}\t{question}{extra}\n", encoding="utf-8")
        answer.write_text("", encoding="utf-8")
        self.assertEqual(oracle.poll_once(ask, answer, server._oracle_provider), 1)
        return answer.read_text(encoding="utf-8")

    def sent(self, call) -> str:
        return repr(call.get("system")) + repr(call.get("messages"))

    def test_two_players_share_an_answer_built_from_neither(self) -> None:
        a = self.ask("Zalpha", "How do I remort?")
        b = self.ask("Zbeta", "How do I remort?")
        self.assertEqual(len(self.calls), 1, "the second is served from the cache")
        self.assertEqual(a.split("\t", 1)[1], b.split("\t", 1)[1])
        prompt = self.sent(self.calls[0])
        for private in ("Zalpha", "Zbeta", *GEAR.values(), "Currently worn"):
            self.assertNotIn(private, prompt)
        self.assertIn("A player asks: How do I remort?", prompt)
        self.assertIn("a level 30 human warrior", prompt, "what the key holds is still said")
        self.assertEqual(self.builds, [True], "built once, shared, and not on the hit")

    def test_a_personal_question_is_the_askers_own_and_never_shared(self) -> None:
        self.ask("Zalpha", "what is my gear worth?")
        self.ask("Zbeta", "what is my gear worth?")
        self.assertEqual(len(self.calls), 2)
        self.assertIn("Zalpha", self.sent(self.calls[0]))
        self.assertIn(GEAR[100], self.sent(self.calls[0]))
        self.assertIn(GEAR[101], self.sent(self.calls[1]))
        self.assertNotIn(GEAR[100], self.sent(self.calls[1]))
        self.assertEqual(self.builds, [False, False])

    def test_a_gear_change_reaches_the_personal_answer_not_the_shared(self) -> None:
        self.ask("Zalpha", "How do I remort?")
        self.profiles["Zalpha"] = profile(102)
        self.ask("Zalpha", "How do I remort?")
        self.assertEqual(len(self.calls), 1, "nothing the shared answer used changed")
        self.ask("Zalpha", "what is my gear worth?")
        self.assertIn(GEAR[102], self.sent(self.calls[-1]))
        self.assertNotIn(GEAR[100], self.sent(self.calls[-1]))

    def test_an_abilities_change_is_another_answer(self) -> None:
        self.ask("Zalpha", "How do I remort?", abilities="zfireball from Zmaster;")
        self.ask("Zbeta", "How do I remort?", abilities="zteleport from Zmaster;")
        self.assertEqual(len(self.calls), 2)
        self.assertIn("zteleport", self.sent(self.calls[1]), "built lazily, abilities included")
        self.ask("Zgamma", "How do I remort?", abilities="zfireball from Zmaster;")
        self.assertEqual(len(self.calls), 2, "the same abilities share the first answer")

    def test_new_balance_rows_retire_leveling_advice_only(self) -> None:
        q = "what mobs should I kill for exp?"
        self.ask("Zalpha", q)
        self.ask("Zbeta", q)
        self.assertEqual(len(self.calls), 1, "the same feed: one answer")
        self.assertIn("a zfield troll", self.sent(self.calls[0]))
        self.ask("Zalpha", "How do I remort?")
        self.assertEqual(len(self.calls), 2)
        with open(self.progress, "a", encoding="latin-1") as fh:
            fh.write("1700000100\tflee\t65536\t30\t3\t0\t50\t50\t3001\t31\tzone.are\t40\t500\t9\t-\n")
        self.ask("Zbeta", q)
        self.assertEqual(len(self.calls), 3, "a new row in the feed: asked again")
        self.ask("Zbeta", "How do I remort?")
        self.assertEqual(len(self.calls), 3, "a question that reads no balance keeps its answer")

    def test_the_key_names_what_the_shared_context_reads(self) -> None:
        remort = server._oracle_cache_key("Zalpha", "How do I remort?")
        self.assertEqual(remort, "how do i remort|warrior|human|30|knights")
        level = server._oracle_cache_key("Zalpha", "where should i level?")
        self.assertIn("|balance:", level)
        gear = server._oracle_cache_key("Zalpha", "what is the best sword at level 30?")
        self.assertIn("|balance:", gear)
        self.assertIn("|season:", gear)
        import datetime
        with patch.object(server, "_gear_today", lambda: datetime.date(2026, 10, 25)):
            halloween = server._oracle_cache_key("Zalpha", "what is the best sword at level 30?")
        self.assertNotEqual(gear.split("|season:")[1], halloween.split("|season:")[1])
        self.assertIsNone(server._oracle_cache_key("Zalpha", "where did I die?"),
                          "the asker's own corpse is theirs")

    def test_no_private_context_reaches_the_logs_or_the_cache(self) -> None:
        self.ask("Zalpha", "How do I remort?")
        self.ask("Zbeta", "How do I remort?")
        self.ask("Zalpha", "what is my gear worth?")
        tmp = Path(self.tmp.name)
        cache = (tmp / "oracle.cache.json").read_text(encoding="utf-8")
        usage = (tmp / "usage.tsv").read_text(encoding="utf-8")
        for private in (*GEAR.values(), "Currently worn", "Supplicant"):
            self.assertNotIn(private, cache)
            self.assertNotIn(private, usage)
        self.assertNotIn("Zalpha", cache)
        self.assertNotIn("Zbeta", cache)


if __name__ == "__main__":
    unittest.main()

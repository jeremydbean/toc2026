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


def _fake_anthropic(answer="Seek the guildmaster.", out_tokens=5,
                    stop_reason="end_turn", calls=None):
    mod = types.ModuleType("anthropic")

    class Resp:
        content = [types.SimpleNamespace(type="text", text=answer)]
        usage = types.SimpleNamespace(
            input_tokens=10, output_tokens=out_tokens,
            cache_read_input_tokens=0, cache_creation_input_tokens=0)

    Resp.stop_reason = stop_reason

    class Messages:
        def create(self, **kw):
            if calls is not None:
                calls.append(kw)
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
        # Conversation memory is per process; no test may inherit another's.
        oracle._HISTORY.clear()
        oracle._LAST_CACHE_KEY.clear()

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

    def test_poll_once_splits_off_the_abilities_field(self):
        ask = Path(self.tmp) / "oracle.ask"
        answer = Path(self.tmp) / "oracle.answer"
        ask.write_text("1700000000\tAlaric\twhat am I missing?\t"
                       "ABILITIES:level 28 necromancer; group life & undeath "
                       "(7 trains) from Soul Trapper, walkto soul trapper;\n",
                       encoding="utf-8")
        seen = {}

        def fake_consult(player, question, context="", cache_key=None):
            seen.update(player=player, question=question, context=context)
            return "Seek the Soul Trapper."

        real = oracle.consult
        oracle.consult = fake_consult
        try:
            self.assertEqual(oracle.poll_once(ask, answer, lambda p, q: ("Live.", None)), 1)
        finally:
            oracle.consult = real
        self.assertEqual(seen["question"], "what am I missing?")
        self.assertIn("Live.", seen["context"])
        self.assertIn("walkto soul trapper", seen["context"])

    def test_poll_once_drains_even_when_dormant(self):
        ask = Path(self.tmp) / "oracle.ask"
        answer = Path(self.tmp) / "oracle.answer"
        ask.write_text("1700000000\tAlaric\thi?\n", encoding="utf-8")
        self.assertEqual(oracle.poll_once(ask, answer), 1)
        self.assertIn("Alaric\t", answer.read_text(encoding="utf-8"))
        self.assertEqual(ask.read_text(encoding="utf-8"), "")

    def test_answers_reach_the_game_as_plain_ascii(self):
        # The game declares ISO-8859-1; a UTF-8 em dash arrived as mojibake.
        # Two of her first four live answers carried one.
        self._enable()
        sys.modules["anthropic"] = _fake_anthropic(
            "Psionics come at remort 2—one per discipline… "
            "“ask Salir”, it’s {7F}free.")
        out = oracle.consult("Alaric", "how do psionics work?")
        out.encode("ascii")   # raises if anything non-ASCII survived
        self.assertIn("remort 2 -- one per discipline...", out)
        self.assertIn('"ask Salir", it\'s', out)
        self.assertNotIn("{", out)   # the game's colour prefix

    def test_a_cut_off_answer_ends_on_a_whole_sentence(self):
        self._enable()
        sys.modules["anthropic"] = _fake_anthropic(
            "Remort at 54 with the remort command. Each life keeps your "
            "gear and grants a gift, the first being", stop_reason="max_tokens")
        self.assertEqual(oracle.consult("Alaric", "remort?"),
                         "Remort at 54 with the remort command.")
        self.assertEqual(oracle._trim_truncated("Seek the old smith in the"),
                         "Seek the old smith in...")

    def test_the_whole_manual_is_never_sent(self):
        # A cache write of ~19.7K tokens cost ~$0.04 for a sitting's first
        # question. Only the relevant sections go now, uncached.
        self._enable()
        calls = []
        sys.modules["anthropic"] = _fake_anthropic("Yes.", calls=calls)
        oracle.consult("Alaric", "how many times can I remort?")
        system = calls[0]["system"]
        self.assertTrue(all("cache_control" not in block for block in system))
        sent = sum(len(block["text"]) for block in system)
        self.assertLess(sent, 9000)
        self.assertIn("Remort", system[1]["text"])
        # Should a write ever happen, it is estimated at the 1-hour rate.
        usage = types.SimpleNamespace(input_tokens=0, output_tokens=0,
                                      cache_read_input_tokens=0,
                                      cache_creation_input_tokens=1_000_000)
        self.assertAlmostEqual(oracle._estimate_usd("claude-haiku-4-5", usage), 2.0)

    def test_a_docs_change_retires_cached_answers(self):
        oracle._cache_put("how do i remort|warrior|human|54", "Old answer.")
        self.assertEqual(oracle._cache_get("how do i remort|warrior|human|54"),
                         "Old answer.")
        saved = oracle._CONTEXT_CACHE
        try:
            oracle._CONTEXT_CACHE = (saved or "") + "\nA corrected paragraph."
            self.assertIsNone(oracle._cache_get("how do i remort|warrior|human|54"))
        finally:
            oracle._CONTEXT_CACHE = saved

    def test_follow_ups_carry_the_conversation_and_skip_the_cache(self):
        self._enable()
        calls = []
        sys.modules["anthropic"] = _fake_anthropic("Rangers want a longbow.",
                                                   calls=calls)
        oracle.consult("Alaric", "best weapon for a ranger?", cache_key="k-ranger")
        oracle.consult("Alaric", "and for a mage?", cache_key="k-mage")
        second = calls[1]["messages"]
        self.assertEqual([m["role"] for m in second],
                         ["user", "assistant", "user"])
        self.assertIn("best weapon for a ranger?", second[0]["content"])
        self.assertEqual(second[1]["content"], "Rangers want a longbow.")
        # The follow-up depended on the first answer, so it is not cached.
        self.assertIsNone(oracle._cache_get("k-mage"))
        # Another player's conversation is their own.
        oracle.consult("Milenko", "and for a mage?")
        self.assertEqual(len(calls[2]["messages"]), 1)

    def test_a_new_sitting_forgets_the_last_one(self):
        self._enable()
        calls = []
        sys.modules["anthropic"] = _fake_anthropic("Go north.", calls=calls)
        ask = Path(self.tmp) / "oracle.ask"
        answer = Path(self.tmp) / "oracle.answer"
        oracle.consult("Alaric", "where is the temple?")
        ask.write_text("1700000000\tAlaric\t\x01SITTING\n"
                       "1700000001\tAlaric\twhere now?\n", encoding="utf-8")
        self.assertEqual(oracle.poll_once(ask, answer), 1)   # control is not answered
        self.assertEqual(len(calls[-1]["messages"]), 1)
        self.assertEqual(answer.read_text(encoding="utf-8").strip(),
                         "Alaric\tGo north.")

    def test_wrong_drops_the_cached_answer(self):
        self._enable()
        sys.modules["anthropic"] = _fake_anthropic("Remort at 40.")
        oracle.consult("Alaric", "how do I remort?", cache_key="k-remort")
        self.assertEqual(oracle._cache_get("k-remort"), "Remort at 40.")
        ask = Path(self.tmp) / "oracle.ask"
        answer = Path(self.tmp) / "oracle.answer"
        ask.write_text("1700000000\tAlaric\t\x01WRONG\n", encoding="utf-8")
        self.assertEqual(oracle.poll_once(ask, answer), 0)
        self.assertIsNone(oracle._cache_get("k-remort"))
        self.assertNotIn("Alaric", oracle._HISTORY)
        self.assertFalse(answer.exists() and answer.read_text(encoding="utf-8"))

    def test_a_typed_wrong_is_just_a_question(self):
        # Only the game's control byte makes a record a control record.
        self._enable()
        sys.modules["anthropic"] = _fake_anthropic("Ask plainly.")
        ask = Path(self.tmp) / "oracle.ask"
        answer = Path(self.tmp) / "oracle.answer"
        ask.write_text("1700000000\tAlaric\tWRONG\n", encoding="utf-8")
        self.assertEqual(oracle.poll_once(ask, answer), 1)


try:
    from webadmin import server as _server   # needs fastapi
except Exception as exc:                     # pragma: no cover - env dependent
    _server = None
    _SERVER_SKIP = "webadmin.server unavailable: %s" % exc
else:
    _SERVER_SKIP = ""


@unittest.skipIf(_server is None, _SERVER_SKIP)
class OracleContextTests(unittest.TestCase):
    """What the poller looks up for a question, before the model sees it."""

    def test_a_creatures_gear_question_is_recognised(self):
        wq = _server._oracle_wear_question
        # The first question anybody asked her live, refused as off-topic.
        self.assertEqual(wq("is agustus wearing the sword of justice right now?"),
                         ("agustus", "sword justice"))
        self.assertEqual(wq("what is the cityguard wielding?"), ("cityguard", ""))
        self.assertEqual(wq("what does the hermit wear"), ("hermit", ""))
        # Advice about one's own gear is not a question about a creature.
        self.assertEqual(wq("what should I be wearing at level 20?"), ("", ""))
        self.assertEqual(wq("what are you wearing?"), ("", ""))

    def test_the_shipped_help_reaches_her_without_a_player_file(self):
        # She once said sanctuary takes off a quarter; the help says half.
        # The help must be in her context even when no player file is
        # readable, which is exactly when it is all she has.
        ctx = _server._oracle_context("Nobodyhere", "what does sanctuary do?")
        self.assertIn("SANCTUARY spell reduces the damage taken", ctx)
        self.assertIn("by one half", ctx)
        self.assertNotIn("Supplicant:", ctx)

    def test_a_gear_question_about_a_creature_is_never_cached(self):
        self.assertIsNone(_server._oracle_cache_key(
            "Nobodyhere", "is the cityguard wearing a helm?"))

    def test_help_entries_matching_the_question_are_quoted(self):
        entries = [
            {"title": "Sanctuary", "keywords": ["SANCTUARY"],
             "body": "{0BSanctuary{00 halves the damage you take."},
            {"title": "Level", "keywords": ["LEVEL"], "body": "Levels are..."},
            {"title": "Armor", "keywords": ["ARMOR"], "body": "Armor protects."},
        ]
        lines = _server._oracle_help_lines("what does sanctuary do at my level?",
                                           entries)
        # Named outright, it comes first, colour codes stripped.
        self.assertEqual(lines[0], "HELP SANCTUARY -- Sanctuary halves the damage "
                                   "you take.")
        self.assertEqual(_server._oracle_help_lines("zzqx wvvy", entries), [])

    def test_help_is_found_for_a_question_that_names_nothing(self):
        # Players ask in their own words; the shipped help must still answer.
        entries = _server.load_player_help()
        titles = lambda q: [l.split(" -- ")[0] for l in
                            _server._oracle_help_lines(q, entries)]
        self.assertIn("HELP STASH",
                      titles("where can I store items I don't want to carry around?"))
        self.assertIn("HELP HISTORY",
                      titles("how can I see what people said on gossip while I "
                             "was offline?"))
        self.assertIn("HELP BUFF", titles("how do I get free buffs?"))
        # Not AQUEST, which only mentions gambling in passing.
        self.assertIn("HELP CASINO", titles("is there anywhere to gamble?"))

    def test_the_strongest_weapon_in_the_game_is_answered_at_the_cap(self):
        # A question with no level is not best-in-slot; the eval found her
        # saying she could not see what weapons exist.
        from unittest.mock import patch
        seen = {}

        async def fake_best(**kw):
            seen.update(kw)
            return {"Wielded": [{"name": "the Power of the world", "level": 54,
                                 "area": "The Abandoned Cathedral", "vnum": 1}]}

        with patch.object(_server, "get_best_gear", fake_best), \
                patch.object(_server, "parser", types.SimpleNamespace(
                    objects={}, mobiles={}, rooms={})):
            ctx = _server._oracle_context(
                "Nobodyhere", "what is the most powerful weapon in the game?")
        self.assertEqual(seen.get("level"), _server._ORACLE_MORTAL_CAP)
        self.assertIn("the Power of the world (lvl 54)", ctx)

    def test_only_the_relevant_docs_are_sent(self):
        # Sending the whole manual cost ~$0.04 a sitting in cache writes.
        docs = oracle._relevant_docs("how many times can I remort?")
        self.assertIn("Remort", docs)
        self.assertLessEqual(len(docs), oracle._DOC_BUDGET_CHARS + oracle._DOC_SECTION_CHARS)
        self.assertLess(len(docs), len(oracle._game_context()) / 8)
        self.assertEqual(oracle._relevant_docs("what is the capital of france?"), "")

    def test_lookups_name_the_asker_and_every_kind_reaches_the_game(self):
        # mobeq and who were once dropped here before reaching the game.
        import os
        tmp = Path(tempfile.mkdtemp())
        saved = _server.QUEUE_PATH
        try:
            _server.QUEUE_PATH = tmp / "webadmin.queue"
            _server._oracle_live_lookup(
                [("obj", "sword"), ("mob", "dummy"), ("eq", "Bob"),
                 ("mobeq", "dummy"), ("who", "all"), ("shell", "rm")],
                timeout=0.2, asker="Alaric")
            sent = (tmp / "oracle.query").read_text(encoding="utf-8").splitlines()
        finally:
            _server.QUEUE_PATH = saved
        kinds = [line.split("\t")[1] for line in sent]
        self.assertEqual(kinds, ["obj", "mob", "eq", "mobeq", "who"])
        self.assertTrue(all(line.split("\t")[2] == "Alaric" for line in sent))

    def test_the_necro_guild_question_gets_the_masters_route(self):
        # Asked live and answered with an area route: an area route does
        # not say which room the master stands in, or that the door is
        # guarded. The Necro Guild Master is in Master's Chambers (4721).
        from unittest.mock import patch
        with patch.object(_server, "_oracle_live_lookup",
                          lambda reqs, timeout=2.5, asker="": ["" for _ in reqs]):
            ctx = _server._oracle_context("Nobodyhere", "where is the necro guild?")
        self.assertIn("Necro Guild Master, in Master's Chambers: from the Oak "
                      "Tree Square r s 6;r w 2;r n 5", ctx)
        self.assertIn("WALKTO NECRO GUILD MASTER", ctx)
        self.assertIn("only necromancers of the necro guild may enter", ctx)
        # Not the Assassins Guild, which is an area that happens to say
        # "guild" in its name.
        self.assertNotIn("Assassins Guild", ctx)

    def test_a_mage_asking_where_to_practise_gets_the_mage_masters(self):
        lines = _server._oracle_trainer_lines("where can a mage practice?")
        text = " ".join(lines)
        # Danko the mystic knight, the mage guild's guildmaster, in the
        # Center of the University.
        self.assertIn("Danko the mystic knight, in Center of the University: "
                      "from the Oak Tree Square r n 2;r w 2;r n 4", text)
        self.assertIn("University of Magic", text)
        # Asked without naming the class, the asker's own class decides.
        own = " ".join(_server._oracle_trainer_lines(
            "where can I practice?", asker_class="mage"))
        self.assertIn("Danko the mystic knight", own)

    def test_a_skill_named_finds_who_teaches_it(self):
        text = " ".join(_server._oracle_trainer_lines(
            "where can I learn fireball?"))
        self.assertIn("Who teaches fireball", text)
        self.assertIn("Flame the fire mage", text)

    def test_joining_a_guild_points_at_the_clerk(self):
        text = " ".join(_server._oracle_trainer_lines("how do I join a guild?"))
        self.assertIn("Melancholy", text)
        self.assertIn("WALKTO MELANCHOLY", text)

    def test_trainer_lines_stay_out_of_unrelated_questions_and_bounded(self):
        self.assertEqual([], _server._oracle_trainer_lines("what does sanctuary do?"))
        both = _server._oracle_trainer_lines(
            "where do mages and clerics practice and gain and learn sanctuary?")
        self.assertLessEqual(sum(len(l) for l in both),
                             _server._ORACLE_TRAINER_CHARS + 3)

    def test_drop_questions_are_answered_from_the_area_files(self):
        ns = types.SimpleNamespace
        objs = {
            100: ns(vnum=100, keywords="sword justice", short_desc="the Sword of Justice",
                    level=40, area_name="Castle", carried_by=[200], contained_by=[]),
            101: ns(vnum=101, keywords="sword rusty", short_desc="a rusty sword",
                    level=1, area_name="Town", carried_by=[], contained_by=[]),
        }
        mobs = {200: ns(short_desc="Crown Prince Augustus", level=45,
                        area_name="Castle")}
        rooms = {}
        lines = _server._oracle_drop_lines("where does the sword of justice drop?",
                                           objs, mobs, rooms)
        self.assertEqual(len(lines), 1)
        self.assertIn("carried by Crown Prince Augustus (lvl 45) in Castle", lines[0])
        # Directions are not a drop question, and nothing is guessed.
        self.assertEqual(_server._oracle_drop_lines(
            "how do i get to the castle?", objs, mobs, rooms), [])
        self.assertEqual(_server._oracle_drop_lines(
            "where does the axe of doom drop?", objs, mobs, rooms), [])


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
        # Every say in her sanctum reaches her, via the do_say hook.
        self.assertIn("oracle_here(ch) )\n        oracle_listen",
                      self.read("src", "act_comm.c").replace("\r\n", "\n"))

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

    def test_web_service_reads_a_log_it_can_open(self):
        # toc-game's append: capture in /var/log/toc is created root:root
        # 0600 by systemd, so the dashboard (User=toc) got Permission denied
        # and the live-log socket flapped. It reads the game's own log.
        unit = self.read("deploy", "windows-vm", "toc-web.service")
        self.assertIn("--log-file /srv/toc/current/log/toc.log", unit)
        self.assertNotIn("--log-file /var/log/toc/", unit)

    def test_the_sanctum_is_a_closed_room(self):
        # Solitary, no-recall, safe, no mobs, and its only exit leads down.
        limbo = self.read("area", "limbo.are").replace("\r\n", "\n")
        room = limbo[limbo.index("The Oracle's Sanctum~"):]
        room = room[:room.index("\nS\n")]
        self.assertIn("\n0 CDKLN 0\n", room)
        self.assertIn("\nD5\n", room)
        for d in ("D0", "D1", "D2", "D3", "D4"):
            self.assertNotIn("\n" + d + "\n", room)

    def test_pray_is_never_an_escape(self):
        oracle = self.read("src", "oracle.c")
        pray = oracle[oracle.index("void do_pray("):]
        for guard in ("ch->fighting", "battleticks", "oracle_is_hunted",
                      "ROOM_DT", "ROOM_JAIL", "ROOM_ARENA"):
            self.assertIn(guard, pray)

    def test_nobody_is_saved_inside_the_sanctum(self):
        self.assertIn("oracle_saved_room", self.read("src", "save.c"))
        self.assertIn("ORACLE_SESSION_SECONDS 300", self.read("src", "oracle.c"))

    def test_off_topic_protocol_is_wired(self):
        # The model emits a sentinel for off-topic; the game turns it into a
        # refusal and escalates.
        self.assertIn("__OFFTOPIC__", self.read("webadmin", "oracle.py"))
        self.assertIn("ORACLE_OFFTOPIC", self.read("src", "oracle.c"))

    def test_she_sees_only_what_the_asker_could(self):
        # Every live lookup goes through the asker-relative rule; none may
        # read a character or an object without it.
        src = self.read("src", "oracle.c").replace("\r\n", "\n")
        for fn, rule in (("oracle_lookup_obj", "oracle_can_locate_obj( asker"),
                         ("oracle_lookup_mob", "oracle_can_see_char( asker"),
                         ("oracle_lookup_eq", "oracle_can_see_char( asker"),
                         ("oracle_lookup_mobeq", "oracle_can_see_char( asker"),
                         ("oracle_lookup_who", "oracle_can_see_char( asker")):
            body = src[src.index("static void " + fn + "("):]
            body = body[:body.index("\n}\n")]
            self.assertIn(rule, body, fn)
        rule = src[src.index("static bool oracle_can_see_char("):]
        rule = rule[:rule.index("\n}\n")]
        # Staff never; stealth and shadowmeld always hide, with no dice roll
        # a repeated question could eventually win.
        self.assertIn("oracle_is_staff( vch )", rule)
        self.assertIn("AFF2_STEALTH", rule)
        self.assertIn("AFF2_SHADOWMELD", rule)
        self.assertIn("PLR_WIZINVIS", rule)
        self.assertNotIn("number_percent", rule)
        self.assertNotIn("can_see(", rule)
        # A player's pack is their own: only what they have on.
        locate = src[src.index("static bool oracle_can_locate_obj("):]
        self.assertIn("WEAR_NONE", locate[:locate.index("\n}\n")])
        # The dashboard's journal does not know who is invisible, and a saved
        # file describes an offline player nobody could look at.
        ctx = self.read("webadmin", "server.py")
        ctx = ctx[ctx.index("def _oracle_context("):]
        ctx = ctx[:ctx.index("\ndef ")]
        self.assertNotIn("players_online(", ctx)
        self.assertNotIn("parse_player_file(cap)", ctx)
        self.assertIn('("who", "all")', ctx)
        self.assertIn("asker=player", ctx)

    def test_wrong_files_a_report_and_tells_the_poller(self):
        src = self.read("src", "oracle.c")
        body = src[src.index("static void oracle_dispute("):]
        body = body[:body.index("\n}\n")]
        self.assertIn("append_file( ch, BUG_FILE", body)
        self.assertIn('oracle_spool_control( ch, "WRONG" )', body)
        pray = src[src.index("void do_pray("):]
        self.assertIn('oracle_spool_control( ch, "SITTING" )', pray)

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

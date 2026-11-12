"""The game's help agrees with the game (help audit, 2026-10-27).

Reads the help the way db.c and do_help read it (webadmin/help_index.py)
and holds it to the command table, the skill table and the groups through
tools/help_audit.py: every command and every skill a class can learn has a
page its user can read, no keyword is shared by accident, the KEYWORDS
topic is generated, and every class level table on a spell or skill page
is the skill table's.  The lookups below are the corrections the audit
made -- each would fail on the help as it stood.

Python only: no server.  tests/test_help_live.py plays the same lookups
against the real game.
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "webadmin"))

import help_audit  # noqa: E402
import help_index  # noqa: E402

AREA = ROOT / "area"
MORTAL = 1
# Topics with a line past 79 columns kept on purpose: tables, a generated
# page (routelist.are) and the old news.
WIDE_OK = {"mshow", "remort", "walkto", "wands", "news", "saurian"}


class HelpIndexReadsLikeTheGame(unittest.TestCase):
    def test_quoted_phrase_is_one_keyword(self) -> None:
        self.assertEqual(help_index.words_of("ARMOR 'STONE SKIN' SHIELD"),
                         ["armor", "stone skin", "shield"])
        self.assertTrue(help_index.keyword_exact("stone skin", "ARMOR 'STONE SKIN'"))
        self.assertFalse(help_index.keyword_exact("stone", "ARMOR 'STONE SKIN'"))

    def test_wrapped_header_and_latin1_and_list_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            area = Path(tmp)
            (area / "area.lst").write_text("b.are\na.are\n$\n", encoding="latin-1")
            # A header that wraps a line, Latin-1 text, and a file the list
            # does not name, which the game never reads.
            (area / "b.are").write_bytes(
                b"#HELPS\n0 FIRST\nSECOND~\nCaf\xe9 body.\n~\n0 $~\n#$\n")
            (area / "a.are").write_bytes(b"#HELPS\n0 FIRST~\nshadowed\n~\n0 $~\n#$\n")
            (area / "c.are").write_bytes(b"#HELPS\n0 UNLISTED~\nnever\n~\n0 $~\n#$\n")
            entries = help_index.load_helps(area)
        self.assertEqual([e.source for e in entries], ["b.are", "a.are"])
        self.assertEqual(entries[0].keyword, "FIRST SECOND")
        self.assertIn("Caf\xe9", entries[0].text)
        self.assertIs(help_index.lookup(entries, "first", MORTAL), entries[0])
        self.assertIs(help_index.lookup(entries, "second", MORTAL), entries[0])
        self.assertIsNone(help_index.lookup(entries, "unlisted", MORTAL))
        self.assertIsNone(help_index.reachable_by(entries, entries[1], MORTAL))

    def test_exact_keyword_beats_an_earlier_prefix(self) -> None:
        entries = help_index._parse_section(
            "0 DRAGON~\nprefix\n~\n0 DRAG~\nexact\n~\n0 $~\n", "x.are", 0)
        self.assertEqual(help_index.lookup(entries, "drag", MORTAL).text.strip(), "exact")
        self.assertEqual(help_index.lookup(entries, "dra", MORTAL).text.strip(), "prefix")

    def test_a_shortened_phrase_finds_its_page_last(self) -> None:
        # Owner, 2026-10-28: HELP DIVINE INTER found nothing although
        # 'DIVINE INTERVENTION' is a keyword; is_name wants each word to
        # begin a keyword whole, and "inter" begins none.
        entries = help_index._parse_section(
            "0 'DIVINE INTERVENTION'~\nphrase\n~\n0 DIVINE INTER~\nwords\n~\n"
            "0 'STONE SKIN'~\nstone\n~\n0 $~\n", "x.are", 0)
        self.assertEqual(help_index.lookup(entries, "divine inter", MORTAL).text.strip(), "words")
        self.assertEqual(help_index.lookup(entries[:1], "divine inter", MORTAL).text.strip(), "phrase")
        self.assertEqual(help_index.lookup(entries, "div int", MORTAL).text.strip(), "words")
        self.assertEqual(help_index.lookup(entries[:1], "div int", MORTAL).text.strip(), "phrase")
        self.assertEqual(help_index.lookup(entries, "stone sk", MORTAL).text.strip(), "stone")
        # In order, from the first word, and no longer than the phrase.
        self.assertIsNone(help_index.lookup(entries, "skin stone", MORTAL))
        self.assertIsNone(help_index.lookup(entries[2:], "skin", MORTAL))
        self.assertIsNone(help_index.lookup(entries[2:], "stone skin wall", MORTAL))
        self.assertFalse(help_index.phrase_prefix("inter", "'DIVINE INTERVENTION'"))

    def test_a_page_above_the_readers_trust_is_skipped(self) -> None:
        entries = help_index._parse_section(
            "66 GOBLIN~\nstaff\n~\n0 'TREASURE GOBLIN' GOBLIN~\npublic\n~\n0 $~\n",
            "x.are", 0)
        self.assertEqual(help_index.lookup(entries, "goblin", MORTAL).text.strip(), "public")
        self.assertEqual(help_index.lookup(entries, "goblin", 66).text.strip(), "staff")


class HelpCoversTheGame(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.entries = help_index.load_helps(AREA)

    def test_the_audit_finds_nothing(self) -> None:
        findings = help_audit.audit(self.entries)
        self.assertEqual(findings, [], "\n".join(findings))

    def test_every_exception_says_why(self) -> None:
        exc = help_audit.load_exceptions()
        for section in ("commands_without_help", "intended_gates", "skills_without_player_help"):
            for name, why in exc[section].items():
                self.assertTrue(isinstance(why, str) and len(why) > 20, (section, name))

    def test_help_text_is_ascii_without_tildes(self) -> None:
        bad = [(e.source, e.keyword) for e in self.entries
               if any(ord(c) > 126 for c in e.text) and e.source in
               ("commands.are", "skills.are", "spells.are", "toc.are")]
        self.assertEqual(bad, [])

    def test_bodies_fit_a_narrow_terminal(self) -> None:
        wide = sorted({(e.source, e.keyword) for e in self.entries
                       if e.words and e.words[0] not in WIDE_OK
                       for line in e.text.split("\n") if len(line.expandtabs()) > 79})
        self.assertEqual(wide, [])


class CorrectionsHold(unittest.TestCase):
    """What a mortal's HELP shows for the topics the audit corrected."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.entries = help_index.load_helps(AREA)

    def page(self, topic: str, trust: int = MORTAL) -> help_index.HelpEntry:
        entry = help_index.lookup(self.entries, topic, trust)
        self.assertIsNotNone(entry, topic)
        return entry

    def says(self, topic: str, *texts: str, trust: int = MORTAL) -> None:
        body = " ".join(self.page(topic, trust).text.split())
        for text in texts:
            self.assertIn(text, body, "HELP %s" % topic)

    def lacks(self, topic: str, *texts: str, trust: int = MORTAL) -> None:
        body = " ".join(self.page(topic, trust).text.split())
        for text in texts:
            self.assertNotIn(text, body, "HELP %s" % topic)

    def test_psionic_pages_describe_the_code(self) -> None:
        self.says("clairvoyance", "Syntax: clairvoyance <character>", "anywhere in the world")
        self.lacks("clairvoyance", "concealed exits")
        self.says("shift", "It does not move you", "stunned until the next tick")
        self.says("project", "moves on by itself", "passes closed doors")
        self.says("transfusion", "You lose exactly 50", "20 mana")
        self.assertLessEqual(self.page("transfusion").level, 0)
        # ASTRAL WALK <name> works since full_command_names (interp.c,
        # 2026-10-30); the page used to warn that it looked for "walk".
        self.says("astral walk", "astral walk <character>", "astral <character>",
                  "stunned until the next tick", "out of a no-recall room")
        self.lacks("astral walk", "Type ASTRAL, not ASTRAL WALK")
        self.says("ego whip", "ego whip [victim]", "ego [victim]")
        self.says("psionic armor", "psionic armor [character]")
        self.lacks("psionic armor", "looks for a character")
        self.says("psionics", "28 transfusion", "WALKTO SALIR")

    def test_one_page_per_psionic_power(self) -> None:
        for power in ("clairvoyance", "shift", "project", "transfusion", "astral walk",
                      "confuse", "ego whip", "mindbar", "mindblast", "nightmare",
                      "torment", "enervate", "psionics"):
            owners = [e for e in self.entries if power in e.words]
            self.assertEqual(len(owners), 1, (power, [(e.source, e.keyword) for e in owners]))

    def test_stealth_skills_describe_the_code(self) -> None:
        self.says("search", "search <direction>", "sets the trap off", "six seconds")
        self.says("track", "does not move you", "3 movement points", "six ordinary directions")
        self.lacks("track", "weather", "footprints")
        self.says("sneak", "your level in ticks", "metal armour")
        self.says("stealth", "halves your current movement points", "12 ticks",
                  "while you are sneaking or hiding")
        self.says("levitate", "always works, costs 10 mana", "tenth of your level")
        self.lacks("levitate", "continuous mana drain")
        self.says("dual wield", "DUAL WIELD skill", "shield", "two-handed", "enchanted",
                  "above 5", "REMOVE")
        self.lacks("secondary", "accuracy penalt", "WIELD your main weapon again")
        self.says("backstab", "any kind")
        self.lacks("backstab", "requires a piercing weapon", "hidden when you initiate")

    def test_missing_topics_exist(self) -> None:
        self.says("colour spray", "COLOUR SPRAY")
        self.says("color spray", "COLOUR SPRAY")
        self.says("bewitch weapon", "no disarm will budge it")
        self.says("enchant item", "evaporate or explode")
        self.says("unalias", "unalias <alias>")
        self.says("blow", "PLAY (or BLOW)")
        self.says("say", "'Hello is the same as SAY Hello")
        self.says("diagnostics", "next player file backup", trust=69)
        self.says("remove align", "destroys the object")
        self.says("restore mana", "5d10 mana")
        self.says("empower", "+20 hitroll and damroll", "not the quest master's")
        self.says("titanic", "five times")          # 5x in all since 2026-11-12
        self.says("empower spell", "half again to the experience")
        self.says("divine protection", "counter-strike")
        self.says("vengeance", "for good")
        self.says("vengence", "for good")

    def test_staff_and_public_pages_split_by_trust(self) -> None:
        self.says("farslay", "600 quest points", "for good")
        self.says("farslay", "never misses", trust=70)
        self.lacks("farslay", "oracle ban")
        self.says("oracleadmin", "oracle ban <player>", trust=66)
        self.says("goblin", "chase")
        self.says("goblin", "goblin dismiss", trust=65)
        self.says("teleport", "random location")
        self.says("teleportspell", "random location", trust=70)
        self.says("invisspell", "invisible", trust=70)
        self.says("empower spell", "+20 hitroll", trust=70)

    def test_guards_and_disabled_commands(self) -> None:
        self.says("qui", "QUI is QUIET")
        self.says("sla", "If you want to SLAY, spell it out.", trust=66)
        self.says("wizinfo", "does not send anything", trust=60)
        self.says("ignore", "IGNORE CLEAR empties it", "staff cannot be ignored")
        for disabled in ("restorechar", "edit"):
            self.assertIsNone(help_index.lookup(self.entries, disabled, 72), disabled)

    def test_commands_that_show_a_help_page_get_their_page(self) -> None:
        # RULES, NEWS and STORY are do_help(ch, "<name>"); a one-line page
        # about the command shadowed what they are there to show.
        src = (ROOT / "src" / "act_info.c").read_text(encoding="latin-1")
        shown = set(re.findall(r'do_help\(\s*ch\s*,\s*"(\w+)"\s*\)', src))
        self.assertTrue({"rules", "news", "story"} <= shown)
        self.says("rules", "USE COMMON SENSE")
        self.says("story", "Judicandus Bramsheer")
        self.lacks("news", "Shows recent news posts")

    def test_groups(self) -> None:
        self.says("enchantment", "enchant item")
        self.says("healing", "divine intervention")
        self.says("weather group", "HELP GROUP WEATHER")
        self.says("weather", "HELP GROUP WEATHER")

    def test_level_tables_are_the_skill_tables(self) -> None:
        # A fresh table line for each of the five maladictions the
        # necromancers were told they could never cast.
        table = {n: lv for n, lv, f in help_audit.skills()}
        for spell in ("blindness", "curse", "plague", "poison", "weaken"):
            self.assertLess(table[spell][5], 62, spell)
            self.says(spell, "Necromancer:%d" % table[spell][5])

    def test_keywords_page_is_generated(self) -> None:
        text = (AREA / "toc.are").read_text(encoding="latin-1")
        start, end = help_audit.keywords_entry_span(text)
        self.assertEqual(text[start:end], help_audit.keywords_text(self.entries))
        words = text[start:end]
        for word in ("colour spray", "astral walk", "unalias", "vengeance"):
            self.assertIn(word, words)


def fixture_entries(*files: tuple) -> list:
    """Help entries from synthetic area files, read through help_index as
    the game reads them: each file is (name, '#HELPS' body), listed in
    area.lst in the order given."""
    with tempfile.TemporaryDirectory() as tmp:
        area = Path(tmp)
        (area / "area.lst").write_text(
            "".join(name + "\n" for name, body in files) + "$\n", encoding="latin-1")
        for name, body in files:
            (area / name).write_text("#HELPS\n" + body + "0 $~\n#$\n", encoding="latin-1")
        return help_index.load_helps(area)


def page(level: int, keywords: str, body: str) -> str:
    return "%d %s~\n%s\n~\n" % (level, keywords, body)


GROUPS = ["rom basics", "necromancy", "necro basics", "weather"]


def kinds(findings) -> list:
    return sorted(f.kind for f in findings)


class ResolveReadsLikeDoHelp(unittest.TestCase):
    """help_index.resolve is do_help from the top, group and first word
    included."""

    def setUp(self) -> None:
        self.entries = fixture_entries(("h.are", page(0, "WEATHER", "the command")
                                        + page(0, "GAINLIST", "trainers")
                                        + page(63, "PETRIFY", "staff")))

    def test_each_step(self) -> None:
        r = help_index.resolve
        self.assertEqual(r(self.entries, "group weather", 1, GROUPS).how, "group-command")
        self.assertEqual(r(self.entries, "weather", 1, GROUPS).how, "exact")
        self.assertEqual(r(self.entries, "gain", 1, GROUPS).how, "prefix")
        res = r(self.entries, "necro", 1, GROUPS)
        self.assertEqual((res.how, res.group), ("group", "necromancy"))
        self.assertEqual(r(self.entries, "gainlist trainers", 1, GROUPS).how, "first-word")
        self.assertIsNone(r(self.entries, "pet", 1, GROUPS).how)
        self.assertEqual(r(self.entries, "pet", 72, GROUPS).entry.keyword, "PETRIFY")


class SeeAlsoAndHelpReferences(unittest.TestCase):
    def test_lists_are_read_whole(self) -> None:
        text = ("Body.\n\nSee also: ALPHA, 'BRAVO TWO', CHARLIE and DELTA,\nECHO\n"
                "See also helps on FOXTROT, GOLF and HOTEL.\nSee also: HELP INDIA\n")
        self.assertEqual(help_audit.see_also_lists(text), [
            (3, ["ALPHA", "'BRAVO TWO'", "CHARLIE", "DELTA", "ECHO"]),
            (5, ["FOXTROT", "GOLF", "HOTEL"]),
            (6, ["INDIA"])])

    def test_help_queries_in_prose(self) -> None:
        text = ("See HELP STASHLINK for that, or HELP GROUP <name>.\n"
                "HELP RULES        HELP BEGINNERS\nFor the spell, HELP EMPOWER SPELL.\n"
                "Type 'help KEYWORD' or help <topic>.\nSee also: HELP NOTME\n")
        self.assertEqual([t for n, t in help_audit.help_references(text)],
                         ["STASHLINK", "RULES", "BEGINNERS", "EMPOWER SPELL", "KEYWORD"])

    def findings(self, see: str, level: int = 0, aliases=None) -> list:
        entries = fixture_entries(("h.are",
                                   page(level, "RIDE", "Riding.\n\nSee also: " + see)
                                   + page(0, "FLY", "fly") + page(0, "'SECOND ATTACK'", "two")
                                   + page(0, "HIDE", "hide") + page(63, "PETRIFY", "staff")
                                   + page(60, "WIZINVIS", "staff only")))
        return help_audit.reference_findings(entries, GROUPS, aliases)

    def test_exact_keywords_and_whole_groups_pass(self) -> None:
        self.assertEqual(self.findings("FLY, 'SECOND ATTACK', SECOND ATTACK, NECROMANCY, "
                                       "GROUP WEATHER"), [])

    def test_a_prefix_to_another_topic_fails(self) -> None:
        found = self.findings("PET")
        self.assertEqual(kinds(found), ["see-also"])
        self.assertEqual(found[0].key, "see-also: RIDE -> PET")
        self.assertIn("reaches nothing at trust 1", found[0])
        self.assertIn("PETRIFY (h.are:63) by prefix at trust 72", found[0])
        self.assertEqual(kinds(self.findings("FL")), ["see-also"])

    def test_a_group_by_prefix_fails(self) -> None:
        self.assertEqual(kinds(self.findings("NECRO")), ["see-also"])

    def test_the_first_word_fallback_fails(self) -> None:
        found = self.findings("HIDE SNEAK")
        self.assertEqual(kinds(found), ["see-also"])
        self.assertIn("first-word fallback", found[0])

    def test_a_page_above_the_reader_is_its_own_kind(self) -> None:
        self.assertEqual(kinds(self.findings("WIZINVIS")), ["see-also-above-reader"])
        self.assertEqual(self.findings("WIZINVIS", level=60), [])

    def test_a_display_label_is_malformed(self) -> None:
        found = self.findings("GODTALK (@), FLY")
        self.assertEqual(kinds(found), ["see-also-malformed"])
        self.assertEqual(found[0].key, "see-also-malformed: RIDE -> GODTALK (@)")

    def test_a_listed_alias_passes(self) -> None:
        self.assertEqual(self.findings("PET", aliases={"PET": "a reason long enough"}), [])

    def test_help_queries_resolve_the_same_way(self) -> None:
        entries = fixture_entries(("h.are", page(0, "STASH", "See HELP STASHLINK and HELP FLY.")
                                   + page(0, "FLY", "fly")))
        found = help_audit.reference_findings(entries, GROUPS)
        self.assertEqual([(f.kind, f.key) for f in found],
                         [("help-ref", "help-ref: STASH -> STASHLINK")])


class AliasPairs(unittest.TestCase):
    CMDS = {"nerve": "do_nerve_damage", "nochannels": "do_nochannels", "listen": "do_listen",
            "group": "do_group", "groups": "do_groups", "remove": "do_remove"}
    SKILLS = {"nerve damage", "listen at door", "remove curse"}
    BODIES = {"do_listen": "chance = learned[gsn_listen_at_door];", "do_remove": "",
              "do_nerve_damage": ""}

    def pairs(self, body: str, distinct=None) -> list:
        entries = fixture_entries(("h.are", body))
        return help_audit.alias_pair_findings(entries, self.CMDS, self.SKILLS, self.BODIES,
                                              {}, distinct or {})

    def test_a_command_and_its_skill_on_two_pages_fail(self) -> None:
        found = self.pairs(page(0, "NERVE", "a") + page(0, "'NERVE DAMAGE'", "b")
                           + page(0, "LISTEN", "c") + page(0, "'LISTEN AT DOOR'", "d"))
        self.assertEqual(sorted(f.key for f in found),
                         ["alias-pair: listen / listen at door", "alias-pair: nerve / nerve damage"])

    def test_a_suffix_of_one_command_fails(self) -> None:
        self.assertEqual(kinds(self.pairs(page(63, "NOCHANNEL", "a") + page(63, "NOCHANNELS", "b"))),
                         ["alias-pair"])

    def test_distinct_things_pass(self) -> None:
        # Two commands with functions of their own; a command and a spell it
        # does not run; one page holding both words.
        self.assertEqual(self.pairs(page(0, "GROUP", "a") + page(0, "GROUPS", "b")
                                    + page(0, "REMOVE", "c") + page(0, "'REMOVE CURSE'", "d")
                                    + page(0, "NERVE 'NERVE DAMAGE'", "e")), [])

    def test_the_staff_split_and_a_listed_pair_pass(self) -> None:
        self.assertEqual(self.pairs(page(63, "NOCHANNEL", "a") + page(0, "NOCHANNELS", "b")), [])
        self.assertEqual(self.pairs(page(0, "NERVE", "a") + page(0, "'NERVE DAMAGE'", "b"),
                                    {"nerve / nerve damage": "why"}), [])


class StaffCommandsAndSyntax(unittest.TestCase):
    ROWS = [("mirror", 65, 1, "do_mirror"), ("save", 0, 1, "do_save"),
            ("drop", 0, 1, "do_drop"), ("goblin", 65, 1, "do_goblin")]

    def test_a_staff_command_with_public_help_fails(self) -> None:
        entries = fixture_entries(("h.are", page(0, "MIRROR", "a") + page(65, "GOBLIN", "s")
                                   + page(0, "GOBLIN 'TREASURE GOBLIN'", "p")))
        found = help_audit.staff_help_findings(entries, self.ROWS, {}, {})
        self.assertEqual([f.key for f in found], ["staff-command-public-help: mirror"])
        self.assertEqual(help_audit.staff_help_findings(entries, self.ROWS, {}, {"mirror": "x"}), [])
        staff = fixture_entries(("h.are", page(65, "MIRROR", "a")))
        self.assertEqual(help_audit.staff_help_findings(staff, self.ROWS, {}, {}), [])

    def test_syntax_lines_start_with_something_the_game_answers(self) -> None:
        entries = fixture_entries(("h.are", page(0, "X", "Syntax: mirr <name>\nSyntax: wave\n"
                                                 "Syntax: cast 'nerve damage'\nSyntax: (automatic)\n"
                                                 "Syntax: frobnicate <thing>")))
        found = help_audit.syntax_findings(entries, self.ROWS + [("cast", 0, 1, "do_cast")],
                                           {"wave"}, {"nerve damage"})
        self.assertEqual([f.key for f in found], ["syntax-unknown-command: X: frobnicate"])

    def test_a_refused_token_fails_while_the_source_refuses_it(self) -> None:
        entries = fixture_entries(("h.are", page(0, "DROP", "Syntax: drop <object>\n"
                                                 "Syntax: drop <amount> coins\n"
                                                 "Syntax: drop <amount> gold")))
        proof = {"do_drop": 'if (!str_cmp(arg,"coins")) send("specify which type of coin")'}
        rules = {"drop": help_audit.SYNTAX_REFUSALS["drop"]}
        found = help_audit.refused_token_findings(entries, proof, rules)
        self.assertEqual([f.key for f in found], ["syntax-refused-token: drop coins"])
        stale = help_audit.refused_token_findings(entries, {"do_drop": ""}, rules)
        self.assertEqual([f.key for f in stale], ["syntax-refusal-stale: drop"])

    def test_a_level_the_command_does_not_have(self) -> None:
        entries = fixture_entries(("h.are", page(0, "SAVE", "You must be at least level 3 to save.")
                                   + page(0, "DROP", "You must be level 1 to drop.")))
        bodies = {"do_save": "save_char_obj(ch);", "do_drop": "drop();"}
        found = help_audit.level_claim_findings(entries, self.ROWS, bodies)
        self.assertEqual([f.key for f in found], ["help-level-claim: SAVE"])
        gated = {"do_save": "if (ch->level < 3) return;"}
        self.assertEqual(help_audit.level_claim_findings(entries, self.ROWS, gated), [])


class Baseline(unittest.TestCase):
    def test_known_findings_pass_new_ones_fail_and_stale_ones_are_named(self) -> None:
        a = help_audit.Finding("see-also", "RIDE -> PET", "msg a")
        b = help_audit.Finding("alias-pair", "nerve / nerve damage", "msg b")
        new, known, stale = help_audit.split_by_baseline(
            [a, b], {"see-also: RIDE -> PET", "help-ref: GONE -> AWAY"})
        self.assertEqual((new, known, stale), ([b], [a], ["help-ref: GONE -> AWAY"]))
        self.assertEqual(new[0], "msg b")

    def test_write_and_read_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "baseline.json"
            self.assertEqual(help_audit.load_baseline(path), set())
            f = help_audit.Finding("see-also", "RIDE -> PET", "msg")
            self.assertEqual(help_audit.write_baseline([f, f], path), 1)
            self.assertEqual(help_audit.load_baseline(path), {"see-also: RIDE -> PET"})
            self.assertTrue(path.read_bytes().isascii())

    def test_the_shipped_baseline_names_only_known_kinds(self) -> None:
        kinds_known = {"see-also", "see-also-above-reader", "see-also-malformed", "help-ref",
                       "help-ref-above-reader", "alias-pair", "staff-command-public-help",
                       "syntax-unknown-command", "syntax-refused-token", "help-level-claim"}
        for key in help_audit.load_baseline():
            self.assertIn(key.split(": ", 1)[0], kinds_known, key)

    def test_the_new_exception_sections_say_why(self) -> None:
        exc = help_audit.load_exceptions()
        for section in ("distinct_pages", "staff_commands_public_help", "reference_aliases"):
            for name, why in exc.get(section, {}).items():
                self.assertTrue(isinstance(why, str) and len(why) > 20, (section, name))


class Reports(unittest.TestCase):
    def test_lengths_and_inventory(self) -> None:
        entries = fixture_entries(("h.are", page(0, "SHORT TINY", "one two three")
                                   + page(60, "LONG", " ".join(["word"] * 300))))
        report = help_audit.lengths_report(entries)
        self.assertIn("2 help pages, 303 words", report)
        self.assertIn("over 250 words: 1 pages", report)
        inv = help_audit.inventory(entries, {"shared_keywords": {}})
        self.assertIn("| 1 | SHORT | TINY | 0 | h.are | 3 |", inv)
        self.assertIn("| 2 | LONG |  | 60 | h.are | 300 |", inv)
        self.assertIn("## Groups answered from the group table", inv)


if __name__ == "__main__":
    unittest.main()

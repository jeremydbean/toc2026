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
        self.says("astral walk", "Type ASTRAL, not ASTRAL WALK", "stunned until the next tick",
                  "out of a no-recall room")
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
        self.says("titanic", "six times")
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
        self.says("ignore", "is not available")
        self.says("newcorpse", "no longer writes those records", "PRESTORE", trust=67)
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


if __name__ == "__main__":
    unittest.main()

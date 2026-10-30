"""The psionic awakening: when it rolls, when it cannot, and what it writes down.

Psionics awaken between levels 18 and 21, one roll per level gained
inside that band. Everything here guards a way that was, or could
again be, quietly skipped:

- the roll lived open-coded at two call sites, where it could not be
  logged, a login re-ran it, and a grant flagged above the band waited
  on a chance that was never coming back;
- `psionic_grant_pending` was written to the save file and read by
  nothing at all, so a player was told twice that psionics were coming
  and they never did;
- the offline branch of GRANTPSI loads a copy of the character, and an
  early return past its save-and-extract loses the grant and leaks the
  copy for the life of the process.

Source inspection rather than a live server: these are structural
rules about where a decision lives, and a live run costs a minute to
prove one path of four.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="latin-1")


def function_body(source: str, signature: str) -> str:
    """The text of one C function, from its signature to the closing brace."""
    start = source.index(signature)
    depth = 0
    seen = False
    i = start
    while i < len(source):
        ch = source[i]
        # A colour token -- "{0E", with no closing brace -- sits in a
        # string, so string and character literals are stepped over.
        if ch in "\"'":
            j = i + 1
            while j < len(source) and source[j] != ch:
                j += 2 if source[j] == "\\" else 1
            i = j + 1
            continue
        if ch == "{":
            depth += 1
            seen = True
        elif ch == "}":
            depth -= 1
            if seen and depth == 0:
                return source[start:i + 1]
        i += 1
    raise AssertionError("unterminated: " + signature)


class AwakeningBandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.merc = read("src", "merc.h")
        cls.stubs = read("src", "stubs.c")
        cls.wiz = read("src", "act_wiz.c")
        cls.update = read("src", "update.c")
        cls.save = read("src", "save.c")
        cls.check = function_body(cls.stubs, "void do_check_psi(")
        cls.grant = function_body(cls.stubs, "int grant_psionics(")
        cls.grantpsi = function_body(cls.wiz, "void do_grantpsi(")

    def test_the_band_is_named_once(self) -> None:
        self.assertIn("#define PSI_AWAKEN_MIN          18", self.merc)
        self.assertIn("#define PSI_AWAKEN_MAX          21", self.merc)

    def test_the_roll_lives_in_do_check_psi_and_nowhere_else(self) -> None:
        """It was open-coded at both call sites, where nothing could log it."""
        self.assertIn("number_range( PSI_AWAKEN_MIN, PSI_AWAKEN_MAX )",
                      self.check)
        for name, source in (("act_wiz.c", self.wiz),
                             ("update.c", self.update)):
            self.assertNotIn(
                "number_range(18,21)", source,
                "%s still rolls for psionics itself" % name)

    def test_only_a_level_gain_rolls(self) -> None:
        """A login that re-rolled would be a relog-until-it-lands exploit."""
        self.assertIn('!str_cmp( argument, "levelup" )', self.check)
        self.assertIn('do_check_psi(victim,"levelup")', self.wiz)
        self.assertIn('do_check_psi(ch,"levelup")', self.update)
        # Login calls it for the flag, not for a fresh roll -- from
        # psionic_login() at game entry, never from load_char_obj, which
        # also loads characters for GRANTPSI and STASH LINK on a blank
        # descriptor that its output crashed.
        login = function_body(self.stubs, "void psionic_login(")
        self.assertIn('do_check_psi( ch, "" )', login)
        self.assertNotIn("do_check_psi", self.save)
        self.assertNotIn("grant_psionics", self.save)
        self.assertNotIn("psionic_restore_known", self.save)

    def test_a_pending_flag_is_read_back(self) -> None:
        """PsiGrant was saved, loaded, and then consulted by nothing."""
        self.assertIn("psionic_grant_pending", self.check)
        self.assertIn('KEY( "PsiGrant"', self.save)

    def test_a_grant_lands_only_on_a_level_gained(self) -> None:
        """Owner, 2026-10-27: no grant lands at a login or at GRANTPSI
        itself unless NOW asked for it. A flag above the band used to land
        at the next login, and GRANTPSI above the band at once."""
        before_gain = self.check.split("if ( !on_level_gain )", 1)[0]
        self.assertNotIn("grant_psionics", before_gain)
        self.assertNotRegex(self.grantpsi, r"victim->level\s*>\s*PSI_AWAKEN_MAX\s*\)\s*\{\s*immediate")

    def test_grantpsi_has_three_modes(self) -> None:
        for word in ('"now"', '"level"', "PSI_GRANT_NEXT_LEVEL", "PSI_GRANT_BAND"):
            self.assertIn(word, self.grantpsi, word)
        for name, value in (("PSI_GRANT_NONE", 0), ("PSI_GRANT_BAND", 1),
                            ("PSI_GRANT_NEXT_LEVEL", 2)):
            self.assertRegex(self.merc, r"#define %s\s+%d\b" % (name, value))

    def test_the_offline_copy_is_saved_and_extracted_on_every_path(self) -> None:
        """An early return here loses the grant and leaks the character."""
        # The last one is the grant branch; an earlier
        # only decides how the argument is read.
        immediate = self.grantpsi.rsplit("if ( immediate )", 1)[1]
        immediate = immediate[:immediate.index("return;")]
        # The save is grantpsi_save, which says how it landed (review,
        # 2026-10-30); the copy is freed on every path, the failed one too.
        self.assertIn("grantpsi_save( victim )", immediate)
        self.assertIn("extract_char( victim, true )", immediate)
        act_wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        helper = act_wiz[act_wiz.index("static int grantpsi_save("):]
        self.assertIn("save_char_obj( victim );", helper[:helper.index("\n}\n")])

    def test_a_miss_is_written_down_with_its_arithmetic(self) -> None:
        """"Did I miss the roll, or did it never fire?" has to be answerable."""
        self.assertIn("psi_log", self.check)
        self.assertIn("awakening roll at level", self.check)
        for phrase in ("rolled", "hits on", "missed", "AWAKENED"):
            self.assertIn(phrase, self.check, phrase)

    def test_a_staff_grant_is_certain_where_it_lands(self) -> None:
        """A GRANTPSI never rides the band's one-in-four rolls (Alaric,
        granted at 17, missed three of them): LEVEL pays on the next level
        gained, a plain grant at the first level gained inside the band.
        Both pay before the roll a remort's owing takes."""
        level_gain = self.check.split("if ( !on_level_gain )", 1)[1]
        roll = level_gain.index("roll = number_range(")
        nxt = level_gain.index("psionic_grant_pending == PSI_GRANT_NEXT_LEVEL")
        band_test = level_gain.index("ch->level < PSI_AWAKEN_MIN || ch->level > PSI_AWAKEN_MAX")
        band = level_gain.index("psionic_grant_pending == PSI_GRANT_BAND")
        self.assertLess(nxt, band_test)
        self.assertLess(band_test, band)
        self.assertLess(band, roll)
        self.assertEqual(level_gain[:roll].count("grant_psionics( ch, 100, true );"), 2)

    def test_every_grant_says_which_power_and_why(self) -> None:
        self.assertGreaterEqual(self.grant.count("psi_log("), 6)
        for phrase in ("roll %d vs chance %d", "granted %s", "grant complete",
                       "restored %s", "set: holds %d of %d"):
            self.assertIn(phrase, self.grant, phrase)

    def test_a_certain_chance_cannot_miss(self) -> None:
        """number_percent() is 1..100, so `>= chance` missed 1% at chance 100."""
        self.assertIn("bool missed = ( roll > chance );", self.grant)
        self.assertNotIn("number_percent() >= chance", self.grant)

    def test_an_abandoned_grant_clears_its_flag(self) -> None:
        """Otherwise it retries on every level check for ever."""
        tail = self.grant.split("if ( selected == 0 )", 1)[1]
        self.assertIn("psionic_grant_pending = PSI_GRANT_NONE", tail[:tail.index("}")])

    def test_the_name_list_and_the_sets_are_the_same_seventeen(self) -> None:
        """psionic_sync_known walks one, grant_psionics walks the other."""
        names = re.search(r"psionic_skill_names\[\] =\s*\{(.*?)\};",
                          self.stubs, re.S).group(1)
        sets = re.search(r"psi_sets\[4\]\[6\] = \{(.*?)\};",
                         self.stubs, re.S).group(1)
        self.assertEqual(len(re.findall(r'"[^"]+"', names)), 17)
        self.assertEqual(len(re.findall(r"&gsn_\w+", sets)), 17)


if __name__ == "__main__":
    unittest.main()

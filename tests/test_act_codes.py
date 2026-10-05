"""act() codes: every one written is one act() knows, and typed text is never a format.

act_new reads $ codes out of its format string. The live log carried
"Act: bad code 50" -- a $2 -- because the echo of SAY, ORDER and FORCE built
their format with snprintf around what the player typed, so a $ in it was
read as a code: the speaker's own echo came back mangled while the room,
which got the text as $t, saw it plain. The WHOOSH social had "$ " where it
meant "*". EMOTE builds its format from the text on purpose -- $e, $s and $m
there become the emoter's pronouns -- and is left as it is (2026-10-05).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def known_codes() -> set:
    """The codes act_new in src/comm.c handles, read from its switch."""
    comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
    body = comm[comm.index("void act_new("):]
    body = body[:body.index("\n}\n")]
    return set(re.findall(r"case '(.)':", body))


KNOWN = known_codes()
CALL = re.compile(r'\bact\w*\s*\(\s*"((?:[^"\\]|\\.)*)"')


class ActCodeTests(unittest.TestCase):
    def test_the_codes_are_read_from_act_new(self) -> None:
        self.assertTrue(set("tTnNeEmMsSpPd") <= KNOWN, KNOWN)

    def test_every_literal_act_format_uses_known_codes(self) -> None:
        bad = []
        for path in sorted((ROOT / "src").glob("*.c")):
            text = path.read_text(encoding="latin-1")
            for match in CALL.finditer(text):
                for code in re.findall(r"\$(.)", match.group(1)):
                    if code not in KNOWN:
                        line = text[:match.start()].count("\n") + 1
                        bad.append(f"{path.name}:{line} ${code}")
        self.assertEqual([], bad)

    def test_every_social_uses_known_codes(self) -> None:
        text = (ROOT / "area" / "social.are").read_text(encoding="latin-1")
        bad = [f"social.are line {n}: ${c}"
               for n, line in enumerate(text.splitlines(), 1)
               for c in re.findall(r"\$(.)", line) if c not in KNOWN]
        self.assertEqual([], bad)

    def test_typed_text_reaches_act_as_t_not_as_the_format(self) -> None:
        comm = (ROOT / "src" / "act_comm.c").read_text(encoding="latin-1")
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        self.assertIn("You say '$t'{00", comm)
        self.assertNotIn("You say '%s'", comm)
        self.assertIn("act( \"$n orders you to '$t'.\", ch, argument, och, TO_VICT );", comm)
        self.assertNotIn("orders you to '%s'", comm)
        self.assertIn("\"$n forces you to '$t'.\"", wiz)
        self.assertNotIn("forces you to '%s'", wiz)


class PrintfFormatTests(unittest.TestCase):
    """DUMP wrote stat_mob and identify_obj output with fprintf(fp, buf), so
    a % in an area description ("Dylan", "Perellia", limbo) was read as a
    conversion -- undefined behaviour, and a crash for the right text."""

    def test_no_printf_takes_a_variable_as_its_format(self) -> None:
        pattern = re.compile(r"\b(?:f?printf|syslog)\(\s*(?:[A-Za-z_][\w>.-]*\s*,\s*)?[A-Za-z_][\w>.-]*\s*\)")
        bad = []
        for path in sorted((ROOT / "src").glob("*.c")):
            for n, line in enumerate(path.read_text(encoding="latin-1").splitlines(), 1):
                if pattern.search(line):
                    bad.append(f"{path.name}:{n}: {line.strip()}")
        self.assertEqual([], bad)


if __name__ == "__main__":
    unittest.main()

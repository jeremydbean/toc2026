"""A buff that runs out takes the pool it raised with it, on the same tick.

char_update regenerates first and expires affects after, so a TITANIC
(five times the maximum, from Hermie or staff) that ran out left its
holder thousands of hit points over the new maximum until the next tick's
regeneration clamped them -- and for good under AFF2_NO_RECOVER. The play
journal's sanity check, which runs before that clamp, logged it on
2026-10-22 as "5474 of 924 hit points". The staff TITANIC toggle already
clamped when it stripped the buff; the tick's expiry did not.

Only expiry clamps: affect_join and a recast remove an affect and add it
back, and must not cost the pool in between.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
UPDATE = ROOT / "src" / "update.c"
HANDLER = ROOT / "src" / "handler.c"


def function_body(text: str, signature: str) -> str:
    start = text.index(signature)
    brace = text.index("{", start)
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[brace:index + 1]
    raise AssertionError(f"unterminated {signature}")


def strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


class BuffExpiryTests(unittest.TestCase):
    def setUp(self) -> None:
        source = UPDATE.read_text(encoding="latin-1")
        self.body = strip_comments(function_body(source, "void char_update( void )"))

    def test_expiry_marks_and_clamps_every_pool(self) -> None:
        removal = self.body.index("affect_remove( ch, paf );")
        self.assertRegex(self.body[removal:removal + 80], r"expired\s*=\s*true",
                         "the tick's affect expiry must note that something ran out")
        clamp = self.body.index("if ( expired )", removal)
        block = self.body[clamp:clamp + 400]
        for pool, maximum in (("hit", "max_hit"), ("mana", "max_mana"), ("move", "max_move")):
            self.assertRegex(
                block, rf"ch->{pool}\s*>\s*ch->{maximum}\s*\)\s*ch->{pool}\s*=\s*ch->{maximum}",
                f"an expired buff must take {pool} down to the new maximum")

    def test_clamp_follows_regeneration(self) -> None:
        # The regeneration's own clamp runs earlier in the tick; the
        # expiry clamp is only useful after it.
        regen = self.body.index("ch->hit  += hit_gain(ch);")
        clamp = self.body.index("if ( expired )")
        self.assertLess(regen, clamp)

    def test_what_wore_off_is_logged(self) -> None:
        # The review on 2026-10-22 had to infer the expiry from timing.
        log = self.body.index('watch_log( ch, "affects off: %s%s", ended, change );')
        clamp = self.body.index("if ( expired )")
        self.assertGreater(log, clamp, "logged after the clamp, so the hp change shows")
        for part in ("max hp", "max mana", "max moves", "; hp "):
            self.assertIn(part, self.body[clamp:log])

    def test_affect_remove_itself_does_not_clamp(self) -> None:
        # affect_join and recasts go through affect_remove: clamping there
        # would cost a refreshed buff its pool.
        body = strip_comments(function_body(HANDLER.read_text(encoding="latin-1"),
                                            "void affect_remove( CHAR_DATA *ch, AFFECT_DATA *paf )"))
        self.assertNotRegex(body, r"ch->hit\s*=\s*ch->max_hit")


if __name__ == "__main__":
    unittest.main()

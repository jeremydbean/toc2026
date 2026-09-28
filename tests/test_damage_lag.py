"""No player command may deal damage and hand the turn straight back.

A harmful ability that costs no lag can be typed as fast as the player
can type, and the damage piles up with nothing throttling it. ENERVATE
was reported for this and turned out to be innocent -- every path of it
that deals damage pays 12 beats, and the log that prompted the report
was an immortal, who bypasses lag entirely by design (see comm.c). The
two the sweep did find were a *missed* NERVE DAMAGE, which still drew
four dice of blood and returned free, and BOMB, which takes half a
target's maximum hit points with no roll, nothing consumed and no lag
at all.

The rule this file keeps: wherever a `do_` command calls `damage()` and
then returns, a `WAIT_STATE` must lie either before the call -- the
kick/backstab style, which pays up front and so covers every path below
it -- or between the call and the return.

Two kinds of return are exempt and are named in KILLED_GUARDS: the
stock "the victim died, do not touch the pointer" guard, where the
fight is over and lag is moot, and one self-inflicted brewing accident.

A failed attempt that deals no damage is deliberately not covered. It
costs mana and nothing else, which is the intended design.

This is a source scan rather than a live test because the paths are
failure branches inside combat, most of which need a particular victim
and a particular roll to reach.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A return straight after damage() is fine when the victim is already
# dead: the fight is over, and the stock guard exists so nothing touches
# a freed pointer. Each entry is (function: why).
KILLED_GUARDS = {
    "do_dirt": "returns only when the blinding blow killed the victim",
    "do_stunning_blow": "returns only when the blow killed the victim",
    "do_enervate": "returns only when the drain killed the victim",
    "do_mindleech": "returns only when the leech killed the victim",
    "do_concoct": "hurts the brewer, not a target -- nothing to spam",
}

TOKENS = re.compile(r"\bdamage\s*\(|WAIT_STATE|\breturn\b")


def commands():
    """Every do_ function in the C sources, as (file, name, body)."""
    for path in sorted((ROOT / "src").glob("*.c")):
        text = path.read_text(encoding="latin-1")
        for part in re.split(r"\n(?=(?:void|bool|int)\s+\w+\s*\()", text):
            m = re.match(r"(?:void|bool|int)\s+(do_\w+)\s*\(", part)
            if m:
                yield path.name, m.group(1), part


class DamageAlwaysCostsLag(unittest.TestCase):
    def test_no_command_deals_damage_and_returns_without_lag(self) -> None:
        offenders = []

        for filename, fn, body in commands():
            if "damage" not in body:
                continue

            lines = body.split(chr(10))
            paid = False       # lag already taken, ahead of any roll
            armed = False      # damage() has happened and is unpaid for

            for m in TOKENS.finditer(body):
                token = m.group(0)
                line_no = body[:m.start()].count(chr(10))

                if token == "WAIT_STATE":
                    # A command that lags before it rolls -- kick, smite,
                    # backstab, shoot -- has already paid for every path
                    # below it, so nothing after it can be free.
                    paid = True
                    armed = False
                elif token.startswith("damage"):
                    armed = not paid
                elif armed:
                    armed = False
                    if fn in KILLED_GUARDS:
                        continue
                    offenders.append(
                        "%s %s: line %d of the function returns after "
                        "damage() with no WAIT_STATE -- %s"
                        % (filename, fn, line_no + 1,
                           lines[line_no].strip()[:60])
                    )

        self.assertEqual(
            offenders, [],
            "harmful abilities that hand the turn straight back:"
            + chr(10) + "  " + (chr(10) + "  ").join(offenders),
        )

    def test_the_two_that_were_found_stay_fixed(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        body = fight.split("void do_nerve_damage(")[1].split(chr(10) + "void ")[0]
        after = body[body.index("You missed the nerve"):]
        self.assertLess(
            after.index("WAIT_STATE"), after.index("return;"),
            "a missed nerve strike still deals 4d4 and must pay the lag",
        )

        act_obj = (ROOT / "src" / "act_obj.c").read_text(encoding="utf-8")
        body = act_obj.split("void do_bomb(")[1].split(chr(10) + "void ")[0]
        after = body[body.index("victim->max_hit / 2"):]
        self.assertLess(
            after.index("WAIT_STATE"), after.index("return;"),
            "the bomb takes half a target's maximum hit points for free",
        )

    def test_every_exemption_still_names_a_real_function(self) -> None:
        """An allowlist that has outlived its code hides the next bug."""
        found = {fn for _, fn, _ in commands()}
        missing = sorted(set(KILLED_GUARDS) - found)
        self.assertEqual(missing, [], "exemptions for functions that are gone")


if __name__ == "__main__":
    unittest.main()

"""VAMPIRIC TOUCH drinks what it took; a shield's reflection spares the invulnerable (review, 2026-11-04).

VAMPIRIC TOUCH healed its caster from the rolled number before damage()
had decided anything: an injured caster gained hit points from a target
with INVULN ABSORB that lost none, and from a target with one hit point
as though it had many. The drink now happens in damage(), where hit
points really come off, from what was taken and never past what the
victim had (damage_drain_next), as a vampiric weapon's already did.

A fire or frost shield's reflection took hit points straight off the
attacker with ch->hit -= dam1, so an immortal with INVULN, either mode,
was hurt by a magic missile at a shielded target. It asks the shared
is_invulnerable() now -- trust, never a switched mobile.

Hit points regenerate on the tick, so the live checks count how many of
several landed touches came out exactly right rather than trusting one.
Synthetic Z characters in the fixture world's arena.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (LiveMud, MIND_ARENA, SPARRING_GUARD, create_character, login,
                      patch_player_file, skip_reason)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zdrainpw1"
GREMLIN = 3702
HP = re.compile(r"Hp: (-?\d+)/(\d+)")


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def hp(staff, word: str, kind: str = "char") -> int:
    found = HP.search(staff.sync(f"stat {kind} {word}"))
    assert found, word
    return int(found.group(1))


class DrainSourceTests(unittest.TestCase):
    def test_the_touch_heals_only_through_damage(self) -> None:
        magic2 = (ROOT / "src" / "magic2.c").read_text(encoding="latin-1")
        touch = magic2.split("void spell_vampiric_touch(", 1)[1].split("\n}\n", 1)[0]
        self.assertNotIn("ch->hit", touch)
        self.assertLess(touch.index("damage_drain_next( 2 )"), touch.index("damage( ch, victim"))

        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        body = fight.split("bool damage( CHAR_DATA *ch, CHAR_DATA *victim", 1)[1]
        body = body.split("\n}\n", 1)[0]
        self.assertIn("drain_next_divisor = 0;", body, "taken at entry")
        subtraction = body.index("victim->hit -= dam;")
        guard = body.rindex("!dummy_absorb( ch, victim, dam, dt )", 0, subtraction)
        drink = body.index("ch->hit = UMIN( ch->max_hit, ch->hit + taken / drain );")
        self.assertLess(guard, subtraction)
        self.assertLess(subtraction, drink)
        block = body[subtraction:drink]
        self.assertIn("dam + victim->hit", block, "never the overkill")
        self.assertIn("!is_treasure_goblin( victim )", block)

    def test_reflection_asks_the_shared_predicate(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1")
        reflect = fight.split("if( shield > 0 )", 1)[1].split("Sleep spells and extremely", 1)[0]
        self.assertIn("is_invulnerable( ch ) && IS_SET(ch->act, PLR_INVULN_ABSORB)", reflect)
        at = reflect.index("ch->hit -= dam1;")
        self.assertIn("if ( !is_invulnerable( ch ) )", reflect[:at])
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        pred = wiz.split("bool is_invulnerable( CHAR_DATA *ch )", 1)[1].split("}", 1)[0]
        self.assertIn("!IS_NPC(ch)", pred, "a switched mobile is never protected")
        # Staff by level (owner, 2026-11-12: trusted mortals act as mortals).
        self.assertIn("is_staff( ch )", pred, "level, not trust")
        self.assertNotIn("IS_TRUSTED", pred)


PROMPT = re.compile(r"<(-?\d+)hp")
# A combat round's lines: the caster's own blows and guards, and a blow
# that reaches the caster. The touch's lines, a death and its experience
# are none of these.
ROUND = re.compile(r"(?m)^(You (block|parry|dodge|evade)\b|Your (?!touch\b)\w+ "
                   r"|.+ is unaffected by your (?!touch\b)\w+|.+'s \w+ .*\byou\b)")


def touch(caster, target: str) -> tuple:
    """Whether the touch landed cleanly, and what it gave the caster: the
    prompt just before "You touch" against the one just after it.

    The window is clean only when no combat round lies in it. A round
    can land in the same burst of output -- the input pass runs the cast
    and violence_update runs in the same pulse,
    before the prompt is written -- and its blows and parries then move
    the caster's hit points inside the window: [4, 3, -16] against the
    invulnerable ward failed CI on 2026-11-08, about one window in seven
    on a loaded machine. Such a window proves nothing and is not counted;
    the callers cast again."""
    said = caster.sync(f"cast 'vampiric touch' {target}", timeout=60)
    at = said.find("You touch")
    if at < 0:
        return False, 0, said
    before = list(PROMPT.finditer(said, 0, at))
    after = PROMPT.search(said, at)
    assert before and after, said
    start = said.find("\n", before[-1].end())
    if ROUND.search(said[start:after.start()]):
        return False, 0, said
    return True, int(after.group(1)) - int(before[-1].group(1)), said


@unittest.skipIf(SKIP is not None, SKIP or "")
class DrainLiveTests(unittest.TestCase):
    def landed(self, god, caster, target: str, want: int) -> list:
        gains = []
        for _ in range(want * 5):
            hit, gain, said = touch(caster, target)
            god.sync("peace")
            if hit:
                gains.append((gain, said))
            if len(gains) >= want:
                break
        self.assertGreaterEqual(len(gains), want, gains)
        return gains

    def test_the_touch_drinks_what_it_takes(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zdraingod", Levl=70, Room=MIND_ARENA,
                 HMV="20000 20000 1000 1000 1000 1000")
            # The caster outranks the ward by eight levels, so the ward
            # saves against one touch in twenty (saves_spell's floor).
            make(mud, "Zdraincast", Levl=70, Room=MIND_ARENA, Cla=0,
                 HMV="5000 30000 30000 30000 1000 1000", HMVP="30000 30000 1000")
            # Invulnerable is an immortal's, by level (owner, 2026-11-12:
            # trusted mortals act as mortals); 62 is INVULN's own level.
            make(mud, "Zdrainward", Levl=62, Room=MIND_ARENA,
                 HMV="500 500 100 100 100 100")
            with mud.connect(timeout=120) as god, mud.connect(timeout=120) as caster, \
                    mud.connect(timeout=120) as ward:
                login(god, "Zdraingod", PW)
                login(caster, "Zdraincast", PW)
                login(ward, "Zdrainward", PW)
                for client in (god, caster, ward):
                    client.sync("scroll 0")
                god.must("set skill zdraincast 'vampiric touch' 100", "")

                # An invulnerable target loses nothing, so feeds nothing.
                ward.must("invuln absorb", "no effect")
                # A tick can fall between the two prompts and heal the
                # caster; it cannot do so for most of them. The old code
                # fed on every one.
                before = hp(god, "zdrainward")
                gains = [g for g, _ in self.landed(god, caster, "zdrainward", 3)]
                self.assertGreaterEqual(gains.count(0), 2, gains)
                self.assertEqual(hp(god, "zdrainward"), before)
                ward.must("invuln off", "off")

                # One hit point to give: half of it rounds to nothing.
                fed = []
                for _ in range(15):
                    god.must(f"load mob {GREMLIN}", "")
                    god.must("set char gremlin hp 1", "")
                    god.must("restore gremlin", "")
                    hit, gain, said = touch(caster, "gremlin")
                    god.sync("peace")
                    god.sync("purge gremlin")
                    if hit:
                        fed.append(gain)
                        if len(fed) >= 3:
                            break
                self.assertGreaterEqual(fed.count(0), 2, fed)

                # A target that loses hit points feeds the caster: the
                # control, so the checks above are not passing on nothing.
                god.must(f"load mob {SPARRING_GUARD}", "You create")
                god.must("set char sparring hp 30000", "")
                god.must("restore sparring", "")
                gains = [g for g, _ in self.landed(god, caster, "sparring", 3)]
                self.assertTrue(any(g > 0 for g in gains), gains)
                # Half of at most dice(5, level / 3), the caster at 70.
                self.assertTrue(all(0 <= g <= 5 * (70 // 3) // 2 for g in gains), gains)

                # The training dummy absorbs every blow, so it feeds nobody.
                god.sync("purge sparring")
                god.must("transfer zdraincast 2419", "Ok.")
                gains = []
                for _ in range(15):
                    hit, gain, _said = touch(caster, "dummy")
                    if hit:
                        gains.append(gain)
                    if len(gains) >= 3:
                        break
                self.assertGreaterEqual(gains.count(0), 2, gains)


@unittest.skipIf(SKIP is not None, SKIP or "")
class ReflectionLiveTests(unittest.TestCase):
    def missile(self, staff, attacker, name: str) -> tuple:
        """One magic missile that landed on the shielded guard, with the
        caster's hit points either side of it. A cast whose reply holds
        no missile (lost concentration, a reply that came back empty on
        a busy runner -- CI, 2026-11-05) proves nothing either way and is
        cast again."""
        for _ in range(4):
            staff.sync(f"restore {name}")
            before = hp(staff, name)
            said = attacker.sync("cast 'magic missile' sparring", timeout=60)
            after = hp(staff, name)
            staff.sync("peace")
            if "missile" in said.lower():
                return before, after, said
        self.fail(f"no magic missile landed: {said!r}\n{attacker.transcript[-1500:]}")

    def test_an_invulnerable_attacker_takes_nothing_from_either_shield(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zrefgod", Levl=70, Room=MIND_ARENA,
                 HMV="20000 20000 30000 30000 1000 1000")
            make(mud, "Zreftrust", Levl=30, Room=MIND_ARENA, Cla=0,
                 HMV="3000 3000 30000 30000 1000 1000", HMVP="3000 30000 1000")
            with mud.connect(timeout=120) as god, mud.connect(timeout=120) as low:
                login(god, "Zrefgod", PW)
                login(low, "Zreftrust", PW)
                god.sync("scroll 0")
                low.sync("scroll 0")
                for skill in ("fire shield", "frost shield", "magic missile"):
                    god.must(f"set skill zrefgod '{skill}' 100", "")
                god.must("set skill zreftrust 'magic missile' 100", "")
                god.must("trust zreftrust 62", "")

                for shield in ("fire shield", "frost shield"):
                    god.sync("purge sparring")
                    god.must(f"load mob {SPARRING_GUARD}", "You create")
                    god.must("set char sparring hp 30000", "")
                    god.must("restore sparring", "")
                    god.must(f"cast '{shield}' sparring", "")
                    for mode in ("absorb", "damage"):
                        god.must(f"invuln {mode}", "Invulnerability on")
                        before, after, said = self.missile(god, god, "zrefgod")
                        self.assertEqual(after, before, f"{shield} {mode}: {said}")
                    god.must("invuln off", "off")

                    # Level, not trust (owner, 2026-11-12: trusted mortals
                    # act as mortals): a level 30 trusted to immortal rank
                    # may type INVULN, is told it is an immortal's, and the
                    # shield burns them like anyone.
                    low.must("invuln absorb", "an immortal's")

                    # Unprotected, the shield burns: the check is live.
                    burned = False
                    for _ in range(3):
                        before, after, said = self.missile(god, low, "zreftrust")
                        if after < before:
                            burned = True
                            break
                    self.assertTrue(burned, f"{shield} never reflected: {said}")


if __name__ == "__main__":
    unittest.main()

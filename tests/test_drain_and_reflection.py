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
        self.assertIn("IS_TRUSTED(ch, LEVEL_IMMORTAL)", pred, "trust, not level")


PROMPT = re.compile(r"<(-?\d+)hp")


def touch(caster, target: str) -> tuple:
    """Whether the touch landed, and what it gave the caster: the prompt
    just before "You touch" against the one just after it. Combat rounds
    and ticks fall outside that window; the touch's own lines are all
    that lie inside it."""
    said = caster.sync(f"cast 'vampiric touch' {target}", timeout=60)
    at = said.find("You touch")
    if at < 0:
        return False, 0, said
    before = PROMPT.findall(said[:at])
    after = PROMPT.search(said, at)
    assert before and after, said
    return True, int(after.group(1)) - int(before[-1]), said


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
            make(mud, "Zdraincast", Levl=40, Room=MIND_ARENA, Cla=0,
                 HMV="200 30000 30000 30000 1000 1000", HMVP="30000 30000 1000")
            # Invulnerable by trust at a low level: an immortal's level
            # saves against nearly every touch.
            make(mud, "Zdrainward", Levl=5, Room=MIND_ARENA,
                 HMV="500 500 100 100 100 100")
            with mud.connect(timeout=120) as god, mud.connect(timeout=120) as caster, \
                    mud.connect(timeout=120) as ward:
                login(god, "Zdraingod", PW)
                login(caster, "Zdraincast", PW)
                login(ward, "Zdrainward", PW)
                for client in (god, caster, ward):
                    client.sync("scroll 0")
                god.must("set skill zdraincast 'vampiric touch' 100", "")
                god.must("trust zdrainward 62", "")

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
                for _ in range(8):
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
                self.assertTrue(all(0 <= g <= 5 * 13 // 2 for g in gains), gains)

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
        before = hp(staff, name)
        said = attacker.sync("cast 'magic missile' sparring", timeout=60)
        after = hp(staff, name)
        staff.sync("peace")
        return before, after, said

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

                    # Trust, not level: a level 30 trusted to immortal rank.
                    low.must("invuln absorb", "Invulnerability on")
                    before, after, said = self.missile(god, low, "zreftrust")
                    self.assertEqual(after, before, f"{shield} trusted: {said}")
                    low.must("invuln off", "off")

                    # Without it, the shield burns: the check is live.
                    burned = False
                    for _ in range(3):
                        god.must("restore zreftrust", "")
                        before, after, said = self.missile(god, low, "zreftrust")
                        if after < before:
                            burned = True
                            break
                    self.assertTrue(burned, f"{shield} never reflected: {said}")


if __name__ == "__main__":
    unittest.main()

"""Two monster wards that never worked, and a staff toggle that stops damage.

`dshield` and `baura` had sat in the skill table since before the
repository's history as `spell_null`: no caster, no class group, so
nothing in the game could ever produce either affect. The only other
mention of them was a pair of blocks in `update.c` that swept up
immunities the affect never granted -- and swept them while the ward was
still standing rather than after it fell, so they were wrong as well as
unreachable. They surfaced only through `set skill <char> all`, which
walked the whole table and put two skills on a player that nothing in the
game explained.

They are monster abilities now: no class can reach them, `spec_dominion_
ward` casts them, and the immunity rides on the affect through
`APPLY_IMMUNITY` the way iron skin's does, so it lifts exactly when the
ward does.

INVULN is separate work that shares a test file because both are about
damage not landing.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]

PASSWORD = "Zward1"

# The Inner Fortress, where a Lord General stands. It carries the ward.
BATTLEGROUND_ROOM = 29315
MUD_SCHOOL = 3700

# MAX_LEVEL is 70, so nothing at 72 is reachable by any class.
UNREACHABLE_LEVEL = 72


def run(client, command: str, settle: float = 2.2) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def hitpoints(client) -> int:
    run(client, "", 1.0)
    found = re.search(r"<(\d+)hp", client.transcript[-300:])
    return int(found.group(1)) if found else -1


# The ward's proc is not tested live, on purpose.
#
# spec_dominion_ward runs every PULSE_MOBILE -- four seconds -- and rolls
# one in sixty-four, so the expected wait is over four minutes and there
# is no upper bound on it. A test that waits for it either takes minutes
# or fails for no reason, and the first version of this file did the
# latter: twenty rounds gave it an eighty percent chance, so it passed
# here and failed one CI run in five.
#
# That it fires at all was watched by hand against a level 68 Lord
# General in the Battleground while the odds were still one in eight.
# What is worth holding automatically is the wiring -- the spell exists,
# the immunity is carried on the affect, the spec is registered, four
# mobiles have it -- and WardSourceTests below does that.


@unittest.skipIf(SKIP is not None, SKIP or "")
class InvulnTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mud = LiveMud()
        self.mud.__enter__()
        with self.mud.connect(timeout=120) as client:
            create_character(client, "Zinvuln", PASSWORD)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        patch_player_file(self.mud, "Zinvuln", Levl=70,
                          Room=BATTLEGROUND_ROOM)

    def tearDown(self) -> None:
        self.mud.__exit__(None, None, None)

    def test_the_toggle_and_its_two_readings(self) -> None:
        with self.mud.connect(timeout=120) as client:
            login(client, "Zinvuln", PASSWORD)

            self.assertIn("Invulnerability on", run(client, "invuln", 1.5))
            self.assertIn("Invulnerability off", run(client, "invuln", 1.5))
            self.assertIn("visibly have no effect",
                          run(client, "invuln absorb", 1.5))
            self.assertIn("read normally",
                          run(client, "invuln damage", 1.5))
            self.assertIn("Syntax:", run(client, "invuln wibble", 1.5))
            self.assertIn("Invulnerability off", run(client, "invuln off", 1.5))

    def test_nothing_reaches_an_invulnerable_immortal(self) -> None:
        with self.mud.connect(timeout=120) as client:
            login(client, "Zinvuln", PASSWORD)
            run(client, "invuln damage", 1.5)

            before = hitpoints(client)
            self.assertGreater(before, 0)
            run(client, "kill general", 2.5)

            fight = ""
            for _ in range(10):
                fight += run(client, "", 2.5)

            # Blows land and are described; nothing comes off.
            self.assertRegex(fight, r"(?i)(hits|slash|pound|crush|maul|pierce)")
            self.assertEqual(hitpoints(client), before,
                             "an invulnerable immortal lost hit points")

    def test_absorb_reads_as_the_immunity_the_game_already_has(self) -> None:
        """Not a second wording for the same idea: the one a weapon gets
        when it hits something immune to it, naming the attack."""
        with self.mud.connect(timeout=120) as client:
            login(client, "Zinvuln", PASSWORD)
            run(client, "invuln absorb", 1.5)

            before = hitpoints(client)
            run(client, "kill general", 2.5)
            fight = ""
            for _ in range(10):
                fight += run(client, "", 2.5)
                if "powerless against you" in fight:
                    break

            self.assertIn("powerless against you", fight, fight[-600:])
            self.assertEqual(hitpoints(client), before)

    def test_it_protects_a_trusted_mortal(self) -> None:
        """The case that was broken. interp.c gates every command on
        get_trust(), so a builder trusted to immortal rank could run
        INVULN and was told it was on -- but the effect asked
        IS_IMMORTAL(), which reads the level, so the blows landed."""
        with self.mud.connect(timeout=120) as client:
            create_character(client, "Ztrusted", PASSWORD)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        # A mortal level with an immortal trust: the two disagree, which
        # is the whole point of the fixture.
        patch_player_file(self.mud, "Ztrusted", Levl=45, Tru=65,
                          Room=BATTLEGROUND_ROOM,
                          HpManaMove="20000 20000 20000 20000 20000 20000")

        with self.mud.connect(timeout=120) as client:
            login(client, "Ztrusted", PASSWORD)
            self.assertIn("read normally", run(client, "invuln damage", 1.5))

            before = hitpoints(client)
            self.assertGreater(before, 0)
            run(client, "kill general", 2.5)

            fight = ""
            for _ in range(10):
                fight += run(client, "", 2.5)

            self.assertRegex(fight, r"(?i)(hits|slash|pound|crush|maul|pierce)")
            self.assertEqual(hitpoints(client), before,
                             "a trusted mortal lost hit points")

    def test_the_flag_is_not_shown_to_anyone(self) -> None:
        """Deliberately unlike WIZINVIS and CLOAK: nothing advertises it."""
        with self.mud.connect(timeout=120) as client:
            login(client, "Zinvuln", PASSWORD)
            run(client, "invuln", 1.5)
            sheet = run(client, "score", 2.0)
            self.assertNotIn("INVULN", sheet)
            self.assertNotIn("ABSORB", sheet)


class InvulnSourceTests(unittest.TestCase):
    def test_it_asks_trust_and_not_level(self) -> None:
        """Whatever gates the command has to be what gates the effect,
        and interp.c gates on get_trust()."""
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="utf-8")
        body = wiz.split("bool is_invulnerable(", 1)[1]
        body = body.split(chr(10) + "}", 1)[0]
        tight = "".join(body.split())
        self.assertIn("IS_TRUSTED(ch,LEVEL_IMMORTAL)", tight)
        self.assertNotIn("IS_IMMORTAL", tight)
        # The NPC guard is load bearing: PLR_INVULN shares a bitfield
        # with ACT_*, so a mobile would answer with an unrelated bit.
        self.assertIn("!IS_NPC(ch)", tight)


class WardSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.const = (ROOT / "src" / "const.c").read_text(encoding="utf-8")
        cls.magic = (ROOT / "src" / "magic.c").read_text(encoding="utf-8")
        cls.update = (ROOT / "src" / "update.c").read_text(encoding="utf-8")
        cls.special = (ROOT / "src" / "special.c").read_text(encoding="utf-8")
        cls.wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="utf-8")

    def entry(self, name: str) -> str:
        body = self.const.split('\t"%s",\n' % name, 1)[1]
        return body.split("    },", 1)[0]

    def test_neither_ward_can_be_reached_by_any_class(self) -> None:
        for name in ("dshield", "baura"):
            with self.subTest(ward=name):
                levels = re.search(r"\{([^}]*)\}", self.entry(name)).group(1)
                self.assertEqual(
                    [int(n) for n in re.findall(r"\d+", levels)],
                    [UNREACHABLE_LEVEL] * 6,
                )

    def test_both_wards_have_a_spell_behind_them_now(self) -> None:
        self.assertIn("spell_dshield", self.entry("dshield"))
        self.assertIn("spell_baura", self.entry("baura"))
        for fun in ("void spell_dshield", "void spell_baura"):
            with self.subTest(fun=fun):
                self.assertIn(fun, self.magic)

    def test_the_immunity_rides_on_the_affect(self) -> None:
        """So it lifts when the ward does, rather than being swept up."""
        for fun, flags in (("spell_baura", ("IMM_MAGIC",)),
                           ("spell_dshield", ("IMM_WEAPON", "IMM_MAGIC"))):
            body = self.magic.split("void " + fun, 1)[1].split("\n}", 1)[0]
            with self.subTest(fun=fun):
                self.assertIn("APPLY_IMMUNITY", body)
                for flag in flags:
                    self.assertIn(flag, body)

        # And the old sweep, which tested "still affected" rather than
        # "no longer affected", is gone.
        self.assertNotIn('skill_lookup("dshield")', self.update)
        self.assertNotIn('skill_lookup("baura")', self.update)

    def test_the_aura_is_occasional_rather_than_permanent(self) -> None:
        """The roll only counts while the ward is down, so the uptime is
        duration over duration plus downtime. One in eight, four seconds
        apart, against a ninety second affect is three quarters of the
        fight -- a permanent immunity to magic rather than a ward."""
        body = self.special.split("bool spec_dominion_ward", 1)[1]
        body = body.split(chr(10) + "}", 1)[0]
        self.assertIn("number_bits( 6 ) == 0", body)
        self.assertIn("!is_affected( mob, sn )", body)
        # And the shield stays a last stand: only below half health.
        self.assertIn("mob->hit * 2 < mob->max_hit", body)

    def test_a_builder_can_put_the_ward_on_a_mobile(self) -> None:
        self.assertIn("bool spec_dominion_ward", self.special)
        self.assertIn('{ "spec_dominion_ward",', self.special)

        used = 0
        for name in ("korzath2.are", "valhalla.are"):
            text = (ROOT / "area" / name).read_text(encoding="latin-1")
            used += text.count("spec_dominion_ward")
        self.assertEqual(used, 4)

    def test_set_skill_all_skips_what_no_class_can_learn(self) -> None:
        """It used to put both wards in a player's skill list."""
        body = self.wiz.split("if ( fAll )", 1)[1].split("    else", 1)[0]
        self.assertIn("skill_level[class_index] <= LEVEL_HERO", body)


if __name__ == "__main__":
    unittest.main()

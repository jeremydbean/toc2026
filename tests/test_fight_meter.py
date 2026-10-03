"""The fight meter and the online roster, both carried to Mudlet by GMCP.

The meter counts every player's damage and rounds in every fight. The
game has to measure it: with damage numbers off -- the default -- the
combat text carries no figure for a client to add up. It rides on
Char.Target, which the output loop already builds from the character's
state and hash-deduplicates, so the running average arrives as it
changes and the last fight's goes out with "not fighting".

The roster lists who else is on, as far as the viewer could tell. It
must not use can_see(): that rolls dice for stealth and shadowmeld, so
the list would flicker, and it asks about the viewer's eyes, so being
blind or in the dark would empty it.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="latin-1")


def body(source: str, signature: str) -> str:
    start = source.index(signature)
    text = source[start:source.index("\n}", start)]
    return re.sub(r"/\*.*?\*/", " ", text, flags=re.S)


class FightMeterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fight = read("src", "fight.c")
        cls.gmcp = read("src", "gmcp.c")
        cls.merc = read("src", "merc.h")

    def test_a_fight_starts_the_meter_from_nothing(self) -> None:
        start = body(self.fight, "void set_fighting(")
        for line in ("meter_damage = 0", "meter_rounds = 0",
                     "meter_active = true"):
            self.assertIn(line, start)

    def test_a_fight_ending_keeps_its_numbers(self) -> None:
        """They become the last fight; only the next fight clears them."""
        stop = body(self.fight, "void stop_fighting(")
        self.assertIn("meter_active = false", stop)
        self.assertNotIn("meter_damage = 0", stop)

    def test_a_round_is_a_violence_round(self) -> None:
        """The same thing the training dummy's report counts, so the two
        figures agree, and counted only when the round is swung."""
        loop = body(self.fight, "void violence_update(")
        awake = loop.split("IS_AWAKE(ch) && ch->in_room == victim->in_room", 1)[1]
        self.assertLess(awake.index("meter_rounds++"),
                        awake.index("multi_hit( ch, victim"))
        self.assertLess(awake.index("multi_hit( ch, victim"),
                        awake.index("else"))

    def test_every_landed_blow_counts_dummy_included(self) -> None:
        damage = body(self.fight, "bool damage(")
        record = damage.index("meter_damage += dam")
        self.assertLess(record, damage.index("dummy_absorb( ch, victim, dam, dt )"))
        guard = damage[damage.rfind("if (", 0, record):record]
        for term in ("dam > 0", "ch != victim", "!IS_NPC(ch)", "meter_active"):
            self.assertIn(term, guard, term)

    def test_the_meter_is_never_saved(self) -> None:
        save = read("src", "save.c")
        for field in ("meter_damage", "meter_rounds", "meter_active"):
            self.assertIn(field, self.merc)
            self.assertNotIn(field, save, field)

    def test_it_rides_on_char_target(self) -> None:
        target = body(self.gmcp, "void gmcp_send_target(")
        self.assertEqual(2, target.count("gmcp_meter_append( json"))
        self.assertIn('",\\"last\\":{"', target)
        helper = body(self.gmcp, "static void gmcp_meter_append(")
        self.assertIn('\\"per_round\\":%ld', helper)
        # A fight won with its opening blow has damage and no round.
        self.assertIn("UMAX( 1, pc->meter_rounds )", helper)

    def test_a_switched_character_sends_no_meter(self) -> None:
        target = body(self.gmcp, "void gmcp_send_target(")
        self.assertIn("pc = IS_NPC(ch) ? NULL : ch->pcdata;", target)


class OnlineRosterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.handler = read("src", "handler.c")
        cls.gmcp = read("src", "gmcp.c")
        cls.rule = body(cls.handler, "bool online_can_list(")

    def test_the_roster_does_not_roll_dice(self) -> None:
        self.assertNotIn("number_percent", self.rule)
        self.assertNotIn("concealment_chance", self.rule)

    def test_the_viewers_eyes_do_not_empty_it(self) -> None:
        self.assertNotIn("AFF_BLIND", self.rule)
        self.assertNotIn("room_is_dark", self.rule)

    def test_who_you_could_not_see_is_never_listed(self) -> None:
        for term in ("PLR_WIZINVIS", "invis_level", "PLR_CLOAKED",
                     "AFF2_STEALTH", "AFF2_SHADOWMELD", "AFF_HIDE",
                     "AFF_INVISIBLE", "AFF_DETECT_HIDDEN", "AFF_DETECT_INVIS"):
            self.assertIn(term, self.rule, term)
        # Trust, the way wizi is decided everywhere else -- read through
        # sight_trust(), which is get_trust() raised to level 59 only for
        # a wearer of the Triforce, exactly as can_see() reads it.
        self.assertIn("sight_trust( ch ) < wch->invis_level", self.rule)
        sight = body(self.handler, "int sight_trust(")
        self.assertIn("get_trust(", sight)

    def test_holylight_sees_through_concealment_but_not_wizi(self) -> None:
        holy = self.rule.index("PLR_HOLYLIGHT")
        self.assertLess(self.rule.index("invis_level"), holy)
        self.assertLess(holy, self.rule.index("AFF2_STEALTH"))

    def test_you_are_not_on_your_own_roster(self) -> None:
        self.assertIn("ch == wch", self.rule)

    def test_the_feed_is_deduplicated_and_reset_with_the_rest(self) -> None:
        send = body(self.gmcp, "void gmcp_send_online(")
        self.assertIn("online_can_list( ch, wch )", send)
        self.assertNotIn("can_see(", send)
        self.assertIn("d->gmcp_online_valid && d->gmcp_last_online_hash == hash",
                      send)
        self.assertIn("od->original != NULL && get_trust( ch ) < 67", send)
        self.assertIn("d->gmcp_online_valid = false;", self.gmcp)
        self.assertIn("gmcp_send_online( d );", read("src", "comm.c"))

    def test_the_package_asks_for_it_and_draws_it(self) -> None:
        package = read("mudlet", "package", "TimesOfChaos.xml")
        self.assertIn('"Char.Online 1"', package)
        self.assertIn('register("gmcp.Char.Online"', package)
        self.assertIn("function tocMudlet.onOnline()", package)
        self.assertIn('name = "tocMudlet.online"', package)


if __name__ == "__main__":
    unittest.main()

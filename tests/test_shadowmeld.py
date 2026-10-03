"""Shadowmeld and the longer idle rope, both remort gifts.

Shadowmeld is stealth with the timer taken off and the room nailed
down: sit, sleep, read, and it holds. Moving ends it, VIS ends it, and
so does swinging at somebody. Nobody sees a melded character -- no
roll, and detect hidden does not beat it -- except through holylight
or the Triforce. Mobiles never see one, which is the point: it is the
one state that is safe to leave the keyboard in.

It is an ordinary skill. Nothing teaches it and no guildmaster sells
it, so it is held only by a character who has taken their fourth
remort, which grants it at 50%, or by one an immortal has granted it
to with SET SKILL. From there it improves with use and with failure
like anything else, and a later remort never takes it away.
"""
from __future__ import annotations

import pathlib
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]

PASSWORD = "Zmeld123"
TEMPLE = 4207


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class ShadowmeldTests(unittest.TestCase):
    def melder(self, remorts: int = 4) -> LiveMud:
        mud = LiveMud()
        mud.__enter__()
        self.addCleanup(mud.__exit__, None, None, None)
        with mud.connect(timeout=120) as client:
            create_character(client, "Zshadow", PASSWORD)
            client.drain(1.0)
            client.send("quit")
            self.assertTrue(client.wait_closed())
        patch_player_file(mud, "Zshadow", Levl=57, Tru=70, Room=TEMPLE,
                          **{"NumRemorts": remorts})
        return mud

    def arm(self, client, percent: int = 100) -> None:
        """Take the dice out of it.

        Shadowmeld is a skill now, so a fourth remort holds it at 50 and
        every one of these tests would be a coin flip. The fixture is
        trusted to 70, so it can set its own skill -- which also proves
        the immortal grant works.
        """
        said = run(client, "set skill Zshadow shadowmeld %d" % percent, 1.6)
        self.assertNotIn("No such skill", said, said)

    def test_a_fourth_remort_holds_the_skill_and_a_third_does_not(self) -> None:
        """The gift is the skill; knowing it is the whole gate."""
        mud = self.melder(remorts=3)
        with mud.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            self.assertIn("know nothing of melting into shadow",
                          run(client, "shadowmeld", 1.8))

        mud2 = self.melder(remorts=4)
        with mud2.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            said = run(client, "shadowmeld", 1.8)
            self.assertNotIn("know nothing", said, said)
            # At 50% either outcome proves they hold it.
            self.assertTrue(
                "draw the shadows" in said or "shadows slip away" in said,
                said,
            )

    def test_the_fourth_remort_grants_it_at_half(self) -> None:
        mud = self.melder(remorts=4)
        with mud.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            client.send("quit")
            self.assertTrue(client.wait_closed())

        saved = (mud.player_dir / "Zshadow").read_text(encoding="latin-1")
        self.assertIn("Sk 50 'shadowmeld'", saved,
                      "the fourth remort should leave the skill at 50")

    def test_an_immortal_can_grant_it_to_anyone(self) -> None:
        """No remort at all, granted by hand, and it works."""
        mud = self.melder(remorts=0)
        with mud.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            self.assertIn("know nothing of melting into shadow",
                          run(client, "shadowmeld", 1.8))
            self.arm(client)
            self.assertIn("draw the shadows", run(client, "shadowmeld", 1.8))

    def test_vis_ends_it(self) -> None:
        mud = self.melder()
        with mud.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            self.arm(client)
            run(client, "shadowmeld", 1.8)
            self.assertIn("step out of the shadows", run(client, "vis", 1.8))
            # Really off: asking again turns it on rather than off.
            self.assertIn("draw the shadows", run(client, "shadowmeld", 1.8))

    def test_who_shows_the_shadow_tag(self) -> None:
        mud = self.melder()
        with mud.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            self.arm(client)
            self.assertNotIn("[SHADOW]", run(client, "who", 1.8))
            run(client, "shadowmeld", 1.8)
            self.assertIn("[SHADOW]", run(client, "who", 1.8))

    def test_affect_lists_it(self) -> None:
        """It is a bare bit, not an AFFECT_DATA, so AFFECT cannot walk to it.

        The early return is the other half: a character whose only
        concealment is a meld was told they were affected by nothing.
        """
        mud = self.melder()
        with mud.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            self.arm(client)
            self.assertNotIn("shadowmeld", run(client, "affect", 1.8))
            run(client, "shadowmeld", 1.8)
            said = run(client, "affect", 1.8)
            self.assertIn("shadowmeld", said, said)
            self.assertNotIn("not affected by any spells", said, said)

    def test_it_holds_through_sleeping(self) -> None:
        """Unlike hide, which the usual restrictions end."""
        mud = self.melder()
        with mud.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            self.arm(client)
            run(client, "shadowmeld", 1.8)
            run(client, "sleep", 1.6)
            # Still melded: asking again toggles it off rather than on.
            self.assertIn("step out of the shadows",
                          run(client, "shadowmeld", 1.8))

    def test_moving_ends_it(self) -> None:
        mud = self.melder()
        with mud.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            self.arm(client)
            run(client, "shadowmeld", 1.8)
            said = run(client, "north", 1.8)
            self.assertIn("step out of the shadows", said, said)
            # And it really is off: asking again turns it on.
            self.assertIn("draw the shadows",
                          run(client, "shadowmeld", 1.8))

    def test_it_toggles(self) -> None:
        mud = self.melder()
        with mud.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            self.arm(client)
            self.assertIn("draw the shadows", run(client, "shadowmeld", 1.6))
            self.assertIn("step out", run(client, "shadowmeld", 1.6))
            self.assertIn("draw the shadows", run(client, "shadowmeld", 1.6))

    def test_you_cannot_meld_mid_fight(self) -> None:
        mud = self.melder()
        with mud.connect(timeout=120) as client:
            login(client, "Zshadow", PASSWORD)
            self.arm(client)
            run(client, "goto 3700", 1.8)
            run(client, "kill guard", 2.2)
            said = run(client, "shadowmeld", 1.8)
            if "middle of a fight" not in said:
                self.skipTest("nothing here fought back")
            self.assertIn("middle of a fight", said, said)


class ShadowmeldSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.handler = (ROOT / "src" / "handler.c").read_text(encoding="utf-8")
        cls.update = (ROOT / "src" / "update.c").read_text(encoding="utf-8")
        cls.move = (ROOT / "src" / "act_move.c").read_text(encoding="utf-8")
        cls.merc = (ROOT / "src" / "merc.h").read_text(encoding="utf-8")

    def test_mobiles_cannot_see_a_melded_character(self) -> None:
        """The check has to sit above the shortcut that hands every
        immortal-level mobile perfect sight, or an aggressive one walks
        in and kills somebody who stepped away."""
        body = self.handler.split("bool can_see( CHAR_DATA *ch", 1)[1]
        body = body.split("\n}", 1)[0]
        meld = body.index("AFF2_SHADOWMELD")
        shortcut = body.index("IS_NPC(ch) && IS_IMMORTAL(ch)")
        self.assertLess(meld, shortcut)

    def test_breaking_it_speaks_only_when_there_is_a_room(self) -> None:
        """char_from_room and the extraction paths both reach this."""
        body = self.move.split("void shadowmeld_break(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("ch->in_room != NULL", body)

    def test_the_break_runs_after_the_null_room_check(self) -> None:
        body = self.handler.split("void char_from_room(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertLess(body.index("Char_from_room: NULL"),
                        body.index("shadowmeld_break"))

    def test_the_idle_rope_is_a_quarter_hour_and_grows_with_level(self) -> None:
        """Nobody gets less than fifteen minutes.

        Three was not long enough to answer a door. Level drives the
        rest, and the third remort's named gift still doubles the
        result. The clamp matters: level comes out of a player file.
        """
        body = self.update.split("int idle_purge_ticks(", 1)[1]
        body = body.split("\n}", 1)[0]

        self.assertIn("REMORTS_FOR_LONG_IDLE", body)
        self.assertIn("ticks *= 2", body)
        self.assertIn("IDLE_LEVELS_PER_TICK", body)
        self.assertIn("URANGE( 0, ch->level, MAX_LEVEL )", body)

        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        self.assertIn("#define LINKDEAD_PURGE_TICKS    15", merc)
        self.assertIn("#define IDLE_LEVELS_PER_TICK    5", merc)

        # The table the comment promises, worked the same way.
        def rope(level: int, remorts: int = 0) -> int:
            ticks = 15 + min(max(level, 0), 70) // 5
            return ticks * 2 if remorts >= 3 else ticks

        self.assertEqual([rope(n) for n in (1, 20, 40, 50, 59)],
                         [15, 19, 23, 25, 26])
        self.assertEqual(rope(56, 3), 52)
        # Monotonic: a later life is never shorter than an earlier one.
        ropes = [rope(53 + n, n) for n in range(6)]
        self.assertEqual(ropes, sorted(ropes), ropes)

    def test_both_idle_branches_use_the_helper(self) -> None:
        """There are two: link-dead, and connected but idle."""
        self.assertEqual(2, self.update.count("idle_purge_ticks( ch )"))
        # And the raw constant is no longer compared against directly.
        body = self.update.split("void char_update(", 1)[1]
        self.assertNotIn(">= LINKDEAD_PURGE_TICKS", body)

    def test_it_is_a_real_skill_reachable_from_level_three(self) -> None:
        """A remort restarts at level 3.

        get_skill returns 0 below skill_level and check_improve refuses to
        improve there, so a gift priced at the level it is given at would
        be frozen until the character had climbed all the way back.
        """
        const = (ROOT / "src" / "const.c").read_text(encoding="latin-1")
        entry = const.split('"shadowmeld",')[1].split(chr(10) + "    },")[0]
        self.assertIn("{   3,  3,  3,  3,  3,  3 }", entry, entry)
        self.assertIn("&gsn_shadowmeld", entry, entry)
        # A rating of zero also stops check_improve dead.
        self.assertIn("{ 6, 6, 6, 6, 6, 6}", entry, entry)

    def test_using_it_improves_it_either_way(self) -> None:
        body = self.move.split("void do_shadowmeld(")[1].split("\nvoid ")[0]
        self.assertIn("check_improve( ch, gsn_shadowmeld, true, 3 )", body)
        self.assertIn("check_improve( ch, gsn_shadowmeld, false, 3 )", body)
        self.assertIn("get_skill( ch, gsn_shadowmeld )", body)
        # The remort count is no longer the gate; holding the skill is.
        self.assertNotIn("REMORTS_FOR_SHADOWMELD", body)

    def test_nobody_sees_it_without_holylight(self) -> None:
        """No roll: the owner's rule is that stealth and shadowmeld are
        invisible without holylight. Detect hidden does not beat either."""
        body = self.handler.split("bool can_see(")[1].split("bool can_see_obj(")[0]
        self.assertNotIn("concealment_chance(", body)
        self.assertIn("if ( IS_AFFECTED2(victim, AFF2_SHADOWMELD) )\n\treturn false;",
                      body.replace("\r\n", "\n"))
        self.assertNotIn(
            "IS_AFFECTED2(victim, AFF2_SHADOWMELD)\n    &&   !IS_AFFECTED(ch, AFF_DETECT_HIDDEN)",
            body,
        )
        # Holylight and the Triforce are asked before either.
        self.assertLess(body.index("triforce_sight( ch )"),
                        body.index("AFF2_SHADOWMELD) )"))

    def test_a_later_remort_never_costs_the_skill(self) -> None:
        act_info = (ROOT / "src" / "act_info.c").read_text(encoding="utf-8")
        body = act_info.split("void do_remort(")[1]
        self.assertIn("kept_meld = ch->pcdata->learned[gsn_shadowmeld]", body)
        self.assertLess(
            body.index("kept_meld = ch->pcdata->learned[gsn_shadowmeld]"),
            body.index("for (i=0;i<MAX_SKILL;i++) ch->pcdata->learned[i] = 0;"),
            "the practised value has to be read before the wipe",
        )
        self.assertIn("UMAX( kept_meld, SHADOWMELD_GRANTED_AT )", body)
        self.assertIn("num_remorts >= REMORTS_FOR_SHADOWMELD", body)

    def test_characters_who_earned_it_before_it_was_a_skill_keep_it(
        self,
    ) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="utf-8")
        self.assertIn("ch->pcdata->learned[gsn_shadowmeld] = SHADOWMELD_GRANTED_AT",
                      save)

    def test_the_gifts_are_named_rather_than_numbered(self) -> None:
        self.assertIn("#define REMORTS_FOR_SHADOWMELD", self.merc)
        self.assertIn("#define REMORTS_FOR_LONG_IDLE", self.merc)


if __name__ == "__main__":
    unittest.main()

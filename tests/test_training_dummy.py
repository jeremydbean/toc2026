"""The training yard: a fight nobody can lose, and a number at the end.

The yard exists so that "is this sword better than that one" has an
answer other than an impression formed over an evening. Everything
guarded here is a way that answer could quietly stop being true: a
dummy that can be killed, a player who can be, a reading taken
against something that changed half way through, or a benchmark that
was invented rather than measured.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(*parts: str) -> str:
    return ROOT.joinpath(*parts).read_text(encoding="latin-1")


def without_comments(text: str) -> str:
    """Strip C comments so an assertion cannot be met by prose."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


class TrainingDummyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dummy = read("src", "dummy.c")
        cls.fight = read("src", "fight.c")
        cls.area = read("area", "dummy.are")
        cls.merc = read("src", "merc.h")

    # ------------------------------------------------------------ the place
    def test_the_area_is_loaded_after_dresden(self) -> None:
        """The practice ring resets into Dresden's square, so the
        square has to exist by the time this file is read."""
        listed = read("area", "area.lst")
        self.assertIn("dummy.are", listed)
        self.assertLess(listed.index("dresden.are"), listed.index("dummy.are"))

    def test_the_yard_allows_a_fight(self) -> None:
        """ROOM_ARENA is what makes it possible.

        is_safe() returns false for an arena before it tests anything
        else, so blows land there that would be refused in a room
        that was merely safe.
        """
        self.assertRegex(self.area, r"\n0 L?V 1\r?\n", "the yard is not an arena")
        is_safe = self.fight.split("bool is_safe(", 1)[1][:900]
        self.assertIn("ROOM_ARENA", is_safe)

    def test_the_dummy_and_the_way_in_both_reset(self) -> None:
        self.assertRegex(self.area, r"M 0 2400 1 2419")
        # The Grand Knight's sparring room, whose description has had
        # practice dummies and sparring circles in it all along.
        self.assertRegex(self.area, r"O 0 2404 0 4462")

    def test_the_way_in_costs_nothing(self) -> None:
        """A portal's value[0] of 1 charges 50 gold, which is not what
        a training yard is for."""
        self.assertRegex(self.area, r"\n30 0 0\r?\n0 2419 0 0 0")

    # ----------------------------------------------------------- nobody dies
    def test_the_absorb_sits_on_the_damage_subtraction(self) -> None:
        """The same chokepoint invulnerability uses.

        Everything above that line, dam_message included, still runs,
        so a practice blow reads exactly like a real one -- which is
        the point, since the reading has to be of the real thing.
        """
        # The subtraction sits on its own line under the if, so the
        # guard is the statement just above it, not the same line.
        before = self.fight.split("victim->hit -= dam;")[0]
        tail = "".join(before.splitlines()[-4:])
        self.assertIn("dummy_absorb( ch, victim, dam, dt )", tail,
                      "the guard is no longer on the subtraction")
        self.assertIn("is_invulnerable( victim )", tail,
                      "invulnerability lost its place on the same line")

    def test_the_dummy_absorbs_and_the_player_is_only_floored(self) -> None:
        body = self.dummy.split("bool dummy_absorb(", 1)[1].split("\n}", 1)[0]
        # Floored rather than made invulnerable: a brutal dummy that
        # holds you at 1 has told you something.
        self.assertIn("victim->hit = 1", body)
        self.assertIn("is_training_dummy( victim )", body)
        self.assertIn("is_training_dummy( ch )", body)

    # --------------------------------------------------- the numbers are real
    def test_the_benchmark_is_measured_not_invented(self) -> None:
        """"You would kill one in nine seconds" is only worth reading
        if the thing being killed is a real measure of the world."""
        body = self.dummy.split("long dummy_typical_hp(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("mob_index_hash", body)
        self.assertIn("proto->level != level", body)
        self.assertIn("cached[level]", body, "the walk must be cached")

    def test_a_run_cannot_be_reconfigured_half_way(self) -> None:
        """A reading blended from two opponents is worse than none."""
        self.assertIn("dummy_started != 0", self.dummy)
        self.assertIn("DUMMY REPORT first", self.dummy)

    def test_the_report_gives_both_directions_and_heals_both(self) -> None:
        body = self.dummy.split("static void dummy_report(", 1)[1]
        body = body.split("\nvoid do_dummy(", 1)[0]
        self.assertIn("WHAT YOU DID", body)
        self.assertIn("WHAT IT DID TO YOU", body)
        self.assertIn("per second", body)
        # The healing moved into the shared stand-down; the report
        # still has to reach it, and it still has to clear the run.
        self.assertIn("dummy_stand_down( ch, dummy )", body)
        heal = self.dummy.split("static void dummy_stand_down(", 1)[1]
        heal = heal.split("\n}", 1)[0]
        self.assertIn("dummy->hit = dummy->max_hit", heal)
        # The player goes back to how they came in, not to full -- see
        # test_you_leave_as_you_came_in.
        self.assertIn("dummy_restore_vitals( ch )", heal)
        self.assertNotIn("ch->hit = ch->max_hit", heal)
        self.assertIn("dummy_session_clear", heal)

    def test_the_dummy_forgets_when_the_run_ends(self) -> None:
        """Reported in play: it attacked again the instant the report
        printed.

        An attacked mobile records who hit it, and one that hates you
        attacks on sight, so stopping the fight was never enough on
        its own. Right for every other mobile in the world; wrong for
        this one.
        """
        # It lives in dummy_stand_down now, which is what REPORT,
        # RESET and LEAVE all go through -- so one fix covers three
        # ways of ending a run instead of one.
        body = self.dummy.split("static void dummy_stand_down(", 1)[1]
        body = body.split("\n}", 1)[0]
        # This player's grudge only: see
        # test_one_run_ending_does_not_end_anybody_elses.
        self.assertIn("remove_hate( dummy, ch )", body)
        self.assertIn("do_stop_hunting", body)
        self.assertIn("dummy->position = POS_STANDING", body)
        report = self.dummy.split("static void dummy_report(", 1)[1]
        self.assertIn("dummy_stand_down( ch, dummy )", report)

    def test_the_dummy_never_holds_a_grudge(self) -> None:
        """At the source, not only on the way out: a hate list is how
        a mobile goes back for somebody, and left to hate, the dummy
        charged the next player in a group the moment the first one's
        run ended, screaming at them for fleeing."""
        body = self.fight.split("void add_hate (", 1)[1].split("\n}", 1)[0]
        self.assertIn("is_training_dummy( vict )", body)
        self.assertLess(body.index("is_training_dummy( vict )"),
                        body.index("alloc_mem"))

    def test_the_record_holder_is_named_by_copy(self) -> None:
        """Found live: a pointer into the board named whoever landed in
        that slot after the insertion shifted it, so a new leader was
        told they had beaten themselves."""
        submit = self.dummy.split("static void dps_board_submit(", 1)[1]
        submit = submit.split("\n}", 1)[0]
        self.assertIn("char others_name[16];", submit)
        self.assertIn("toc_strlcpy( others_name, dps_board[i].name", submit)
        self.assertNotIn("others_name = dps_board", submit)

    def test_one_run_ending_does_not_end_anybody_elses(self) -> None:
        """Found live with two players benchmarking side by side.

        The stand-down called stop_fighting( dummy, true ), which stops
        every fight the dummy is in. The first player's bell ended the
        second player's fight too, their round counter stopped being
        asked, and their bell never came.
        """
        body = without_comments(
            self.dummy.split("static void dummy_stand_down(", 1)[1]
            .split("\n}", 1)[0])
        self.assertNotIn("stop_fighting( ch, true )", body)
        self.assertNotIn("stop_fighting( dummy, true )", body)
        self.assertNotIn("remove_all_hates", body)
        self.assertIn("if ( dummy->fighting == ch )", body)
        left = self.dummy.split("void dummy_left_yard(", 1)[1].split("\n}", 1)[0]
        self.assertNotIn("remove_all_hates", left)

    def test_it_defaults_to_your_own_level(self) -> None:
        """Almost everybody is asking how they do against something
        their own size; anything else is a different question."""
        self.assertIn("dummy->level != ch->level", self.dummy)
        self.assertIn("dummy_configure( dummy, ch->level", self.dummy)

    def test_the_damage_type_can_be_changed(self) -> None:
        """Testing resistances is half of what gear testing is."""
        self.assertIn("dummy_attack_table", self.dummy)
        for school in ("fire", "cold", "lightning", "acid", "holy"):
            self.assertIn('"%s"' % school, self.dummy, school)
        self.assertIn("dummy->dam_type", self.dummy)

    # ------------------------------------------------- getting out
    def test_leave_is_a_command_and_only_works_in_the_yard(self) -> None:
        """You get in by entering the practice ring, so the way out
        should be the same shape rather than a compass direction."""
        interp = read("src", "interp.c")
        self.assertRegex(interp, r'\{ "leave",\s+do_leave,')
        body = self.dummy.split("void do_leave(", 1)[1].split("\n}", 1)[0]
        self.assertIn("ROOM_VNUM_TRAINING_YARD", body)
        self.assertIn("ROOM_VNUM_YARD_DOOR", body)
        self.assertIn("#define ROOM_VNUM_YARD_DOOR         4462", self.merc)

    def test_leaving_mid_run_still_gives_you_the_numbers(self) -> None:
        """Walking out would otherwise throw away the only reason to
        have been in there."""
        body = self.dummy.split("void do_leave(", 1)[1].split("\n}", 1)[0]
        self.assertIn("dummy_report(", body)

    def test_the_yard_has_no_walking_exit(self) -> None:
        """You arrive through the ring and you leave through it.

        Removing the exit makes LEAVE the only way out on foot, so
        the two things below are what stop that being a trap.
        """
        room = self.area.split("#2419", 1)[1].split("\n#", 1)[0]
        self.assertNotRegex(room, r"\nD\s*\d",
                            "the yard has a walking exit again")

    def test_nobody_can_be_shut_in_the_yard(self) -> None:
        """With no exit, RECALL is the escape hatch for a player who
        never reads the room -- so the yard must never become
        no-recall.  ROOM_NO_RECALL is N; the yard carries V alone."""
        room = self.area.split("#2419", 1)[1].split("\n#", 1)[0]
        flags = [line for line in room.splitlines()
                 if re.fullmatch(r"0 [A-Za-z]+ 1", line.strip())]
        self.assertEqual(1, len(flags), "the yard's flag line changed")
        self.assertNotIn("N", flags[0].split()[1],
                         "the yard became no-recall and is now a trap")

    def test_the_room_says_how_to_get_out(self) -> None:
        """The only way out has to be discoverable by looking."""
        room = self.area.split("#2419", 1)[1].split("\n#", 1)[0]
        self.assertIn("LEAVE RING", room)

    def test_leave_takes_the_ring_by_name(self) -> None:
        """LEAVE RING is what the room tells you to type."""
        body = self.dummy.split("void do_leave(", 1)[1].split("\n}", 1)[0]
        self.assertIn('str_prefix( arg, "ring" )', body)
        # A bare LEAVE still works: there is only one thing to leave.
        self.assertIn("arg[0] != '\\0'", body)

    # --------------------------------------------------------- reset
    def test_reset_clears_the_numbers_and_works_mid_run(self) -> None:
        """Reported in play.  The stance going back to default while
        the numbers stay up is half a reset, and the half it leaves
        is the half that makes the next reading wrong.

        It is also the one setting change that belongs inside a run,
        because throwing the run away is exactly what it means.
        """
        body = without_comments(self.dummy)
        self.assertIn("is_reset = ( strlen( arg1 ) >= 3", body)
        self.assertIn("!is_reset && ch->pcdata->dummy_started != 0", body,
                      "reset is still caught by the mid-run guard")
        reset = body.split("if ( is_reset )", 1)[1][:600]
        self.assertIn("dummy_stand_down( ch, dummy )", reset)

    def test_report_and_reset_stand_down_the_same_way(self) -> None:
        """Two copies of forget-the-grudge-and-heal is one copy that
        will be fixed and one that will not."""
        self.assertEqual(2, self.dummy.count("dummy_stand_down( ch, dummy )"))
        helper = self.dummy.split("static void dummy_stand_down(", 1)[1]
        helper = helper.split("\n}", 1)[0]
        for part in ("remove_hate( dummy, ch )", "do_stop_hunting",
                     "dummy->hit = dummy->max_hit", "dummy_session_clear"):
            self.assertIn(part, helper, part)

    # ------------------------------------------------- magic and haste
    def test_it_can_cast_at_you(self) -> None:
        """A damage school delivered by a weapon tests a resistance.
        The same school from a spell tests a saving throw as well,
        which is a different question about the same armour."""
        self.assertIn("dummy_spell_table", self.dummy)
        for kind in ("force", "fire", "cold", "lightning", "acid", "harm"):
            self.assertIn('"%s"' % kind, self.dummy, kind)
        spec = self.dummy.rsplit("bool spec_training_dummy(", 1)[1]
        spec = spec.split("\n}", 1)[0]
        self.assertIn("skill_table[sn].spell_fun", spec)
        self.assertIn("mob->position != POS_FIGHTING", spec)

    def test_the_spell_is_fixed_not_random(self) -> None:
        """A reading you cannot reproduce is not a measurement, so it
        casts what it was told to and nothing else."""
        spec = self.dummy.rsplit("bool spec_training_dummy(", 1)[1]
        spec = spec.split("\n}", 1)[0]
        self.assertNotIn("number_bits", spec)
        self.assertNotIn("number_range", spec)
        self.assertIn("dummy_spell_table[dummy_spell].spell", spec)

    def test_the_spec_survives_an_area_reset(self) -> None:
        """Assigned in code rather than in the area file, so a reset
        rebuilding the mobile cannot quietly take the casting away."""
        cfg = self.dummy.rsplit("static void dummy_configure(", 1)[1]
        cfg = cfg.split("\n}", 1)[0]
        self.assertIn('spec_lookup( "spec_training_dummy" )', cfg)
        self.assertIn("AFF_HASTE", cfg)
        special = read("src", "special.c")
        self.assertIn('{ "spec_training_dummy",', special)

    # --------------------------------------------------- the breakdown
    def test_damage_is_split_by_where_it_came_from(self) -> None:
        """"You did 4,200" does not say whether it was the sword or
        the spellbook, which is the thing you came here to find."""
        self.assertIn("dummy_dealt_from", self.merc)
        self.assertIn("dummy_taken_from", self.merc)
        src = self.dummy.split("static int dummy_source(", 1)[1]
        src = src.split("\n}", 1)[0]
        self.assertIn("TYPE_HIT", src)
        self.assertIn("spell_fun != spell_null", src)

    def test_blows_turned_aside_are_counted(self) -> None:
        """A parry returns out of damage() above the subtraction the
        yard hooks, so without a hook of its own the report cannot
        tell a parry from a swing that never happened -- which is
        most of what somebody comparing two shields wants to know.
        """
        for how in ("DUMMY_AVOID_DUCK", "DUMMY_AVOID_PARRY",
                    "DUMMY_AVOID_DODGE", "DUMMY_AVOID_SHIELD"):
            self.assertIn(how, self.merc, how)
            self.assertIn("dummy_defended( ch, victim, dt, %s )" % how,
                          self.fight, how)
        body = self.dummy.split("void dummy_defended(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("dummy_avoided[how]++", body)
        self.assertIn("dummy_evaded[how]++", body)

    def test_the_defence_hooks_sit_before_the_returns(self) -> None:
        """Counted on the way out, or not counted at all."""
        block = self.fight.split("Check for parry, and dodge.", 1)[1][:1400]
        for check in ("check_ducking", "check_parry", "check_dodge",
                      "check_shield_block"):
            after = block.split(check, 1)[1][:200]
            self.assertLess(after.index("dummy_defended"),
                            after.index("return false"), check)

    def test_percentages_are_of_attempts(self) -> None:
        """A shield that stops a third of everything should read as a
        third; against landed blows only it would read as nothing."""
        report = self.dummy.split("static void dummy_report(", 1)[1]
        self.assertIn("pc->dummy_avoided[i] * 100 / attempts", report)

    # ------------------------------------------- attack by attack
    def test_every_attack_is_itemised_by_name(self) -> None:
        """Three spells cast should read as three lines.

        dt is already the skill that caused the blow, or the
        weapon's attack type, so the split needs no guessing.
        """
        self.assertIn("DUMMY_MAX_SOURCES", self.merc)
        self.assertIn("dummy_out[DUMMY_MAX_SOURCES]", self.merc)
        self.assertIn("dummy_in[DUMMY_MAX_SOURCES]", self.merc)
        name = self.dummy.split("static const char *dummy_dt_name(", 1)[1]
        name = name.split("\n}", 1)[0]
        self.assertIn("skill_table[dt].name", name)
        self.assertIn("attack_table[dt - TYPE_HIT].name", name)

    def test_a_full_table_still_totals_correctly(self) -> None:
        """The itemised list is a display. Running out of rows must
        cost the detail, never the arithmetic."""
        slot = self.dummy.split("static DUMMY_SOURCE_DATA *dummy_slot(",
                                1)[1].split("\n}", 1)[0]
        self.assertIn("return NULL", slot)
        tally = self.dummy.split("static void dummy_tally(", 1)[1]
        tally = tally.split("\n}", 1)[0]
        self.assertIn("if ( row == NULL )", tally)
        self.assertIn("return", tally)

    def test_both_directions_are_itemised(self) -> None:
        report = self.dummy.split("static void dummy_report(", 1)[1]
        report = report.split("\nvoid do_dummy(", 1)[0]
        self.assertIn("dummy_itemise( ch, pc->dummy_out, dealt )", report)
        self.assertIn("dummy_itemise( ch, pc->dummy_in, taken )", report)

    def test_a_turned_aside_blow_counts_as_an_attempt(self) -> None:
        """Otherwise a weapon that keeps getting parried reads as a
        perfect hit rate on the few that landed."""
        body = self.dummy.split("void dummy_defended(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("dummy_tally( pc->dummy_out, dt, 0 )", body)
        self.assertIn("dummy_tally( pc->dummy_in, dt, 0 )", body)

    def test_the_biggest_contributor_is_first(self) -> None:
        """The first line should be the answer to "what is actually
        doing the work"."""
        srt = self.dummy.split("static void dummy_sort(", 1)[1]
        srt = srt.split("\n}", 1)[0]
        self.assertIn("table[j].damage > table[pick].damage", srt)

    def test_the_tables_are_cleared_with_the_session(self) -> None:
        clear = self.dummy.split("static void dummy_session_clear(", 1)[1]
        clear = clear.split("\n}", 1)[0]
        self.assertIn("memset( ch->pcdata->dummy_out", clear)
        self.assertIn("memset( ch->pcdata->dummy_in", clear)

    # ------------------------------------------------- benchmarking
    def test_the_benchmark_turns_off_every_defence_at_once(self) -> None:
        """One guard on the block that rolls all four, so a benchmark
        cannot end up skipping some defences and not others."""
        self.assertIn("dummy_skips_defence( victim )", self.fight)
        block = self.fight.split("Check for parry, and dodge.", 1)[1][:400]
        self.assertIn("!dummy_skips_defence( victim )", block)
        body = self.dummy.split("bool dummy_skips_defence(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("dummy_bench", body)
        self.assertIn("is_training_dummy( victim )", body)

    def test_only_the_dummy_stops_defending(self) -> None:
        """Your own parries are your armour, and measuring it is the
        other half of why anybody is in the yard."""
        # It takes the defender and nothing else, so it cannot
        # structurally turn off the attacker's parries as well.
        self.assertIn("bool dummy_skips_defence( CHAR_DATA *victim )",
                      self.dummy)
        self.assertIn("bool    dummy_skips_defence( CHAR_DATA *victim );",
                      self.merc)

    def test_the_run_ends_itself_after_its_rounds(self) -> None:
        """A run you stop by hand is a different length every time,
        so two readings cannot be compared."""
        self.assertIn("dummy_round_limit( ch, victim )", self.fight)
        body = self.dummy.split("bool dummy_round_limit(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("dummy_rounds < dummy_bench_rounds", body)
        self.assertIn("dummy_report( ch, victim )", body)

    def test_the_limit_is_asked_before_the_swing(self) -> None:
        """Otherwise a run of fifty is fifty-one."""
        loop = self.fight.split("void violence_update(", 1)[1]
        loop = loop.split("\n}", 1)[0]
        self.assertLess(loop.index("dummy_round_limit"),
                        loop.index("multi_hit( ch, victim"))

    def test_a_run_that_never_started_cannot_end(self) -> None:
        """Otherwise typing KILL and waiting reports on nothing."""
        body = self.dummy.split("bool dummy_round_limit(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("dummy_started == 0", body)

    def test_the_benchmark_is_the_default(self) -> None:
        """Fifty rounds and a bell unless you ask for endless.

        It was the other way round until the owner turned it on
        2026-10-01: the benchmark is the run worth comparing, so it is
        the one a player should get without knowing to ask for it.
        """
        self.assertIn("static bool dummy_bench = true;", self.dummy)
        self.assertIn("#define DUMMY_BENCH_ROUNDS 50", self.merc)
        reset = without_comments(self.dummy).split("if ( is_reset )", 1)[1]
        self.assertIn("dummy_bench = true", reset[:700])
        self.assertIn('!str_prefix( arg1, "endless" )', self.dummy)

    def test_bench_sets_rather_than_toggles(self) -> None:
        """As a toggle, the first DUMMY BENCH on a dummy somebody had
        already benched switched it off, which read as failing."""
        code = without_comments(self.dummy)
        self.assertNotIn("dummy_bench = !dummy_bench", code)
        bench = code.split('!str_prefix( arg1, "bench" )', 1)[1]
        bench = bench.split('!str_prefix( arg1, "endless" )', 1)[0]
        self.assertIn("dummy_bench = true", bench)

    def test_the_report_gives_damage_per_round(self) -> None:
        """Per second moves with how long the rounds took; per round
        is the figure two benchmark runs can be compared on."""
        report = self.dummy.split("static void dummy_report(", 1)[1]
        report = report.split("\nvoid do_dummy(", 1)[0]
        self.assertIn("per round", report)
        self.assertIn("dealt / rounds", report)

    def test_the_round_count_is_bounded(self) -> None:
        body = self.dummy.split('!str_prefix( arg1, "bench" )', 1)[1][:1500]
        self.assertIn("rounds < 1 || rounds > 1000", body)

    # --------------------------------------------- the rules of the yard
    def test_you_leave_as_you_came_in(self) -> None:
        """A fight you cannot lose is otherwise a free heal for anybody
        who walks in half dead, and a free mana refill on top."""
        start = self.dummy.split("if ( player->pcdata->dummy_started == 0 )",
                                 1)[1][:2200]
        for pool in ("hit", "mana", "move"):
            self.assertRegex(start, r"dummy_pre_%s\s*=\s*player->%s;"
                             % (pool, pool))
        restore = self.dummy.split("static void dummy_restore_vitals(", 1)[1]
        restore = restore.split("\n}", 1)[0]
        for pool in ("hit", "mana", "move"):
            self.assertIn("pc->dummy_pre_%s" % pool, restore)
        self.assertNotIn("max_hit;", restore.replace("UMAX( 1, ch->max_hit )", ""))

    def test_a_reset_with_no_run_touches_nothing(self) -> None:
        """No run, no snapshot: restoring then would set you to zero."""
        restore = self.dummy.split("static void dummy_restore_vitals(", 1)[1]
        restore = restore.split("\n}", 1)[0]
        self.assertIn("pc->dummy_started == 0", restore)
        self.assertLess(restore.index("dummy_started == 0"),
                        restore.index("ch->hit"))

    def test_leaving_mid_run_puts_you_back_on_the_way_out(self) -> None:
        """A snapshot carried out of the yard could be cashed in: start
        at full, leave, get hurt elsewhere, come back and end it."""
        handler = read("src", "handler.c")
        body = handler.split("void char_from_room(", 1)[1].split("\n}", 1)[0]
        self.assertIn("dummy_left_yard( ch )", body)
        # After the null check, before the room pointers change.
        self.assertLess(body.index("ch->in_room == NULL"),
                        body.index("dummy_left_yard( ch )"))
        self.assertLess(body.index("dummy_left_yard( ch )"),
                        body.index("ch->in_room->people = ch->next_in_room"))
        left = self.dummy.split("void dummy_left_yard(", 1)[1].split("\n}", 1)[0]
        self.assertIn("dummy_restore_vitals( ch )", left)
        self.assertIn("dummy_session_clear( ch )", left)

    def test_nothing_is_learned_in_the_yard(self) -> None:
        skills = read("src", "skills.c")
        body = skills.split("void check_improve(", 1)[1][:700]
        self.assertIn("dummy_blocks_improve( ch )", body)
        block = self.dummy.split("bool dummy_blocks_improve(", 1)[1]
        self.assertIn("ROOM_VNUM_TRAINING_YARD", block.split("\n}", 1)[0])

    def test_the_room_points_at_the_help(self) -> None:
        room = self.area.split("#2419", 1)[1].split("\n#", 1)[0]
        self.assertIn("HELP DUMMY", room)

    # ---------------------------------------------------- the board
    def test_only_the_standard_run_is_ranked(self) -> None:
        """Every setting can move the answer, so a board that let any
        of them vary would rank the settings rather than the gear."""
        std = self.dummy.split("static bool dummy_run_is_standard(", 1)[1]
        std = std.split("\n}", 1)[0]
        for term in ("dummy_bench_rounds == DUMMY_BENCH_ROUNDS",
                     "dummy_shape  == DUMMY_SHAPE_DEFAULT",
                     "dummy_attack == DUMMY_ATTACK_DEFAULT",
                     "dummy_spell  == DUMMY_SPELL_NONE", "!dummy_hasted",
                     "dummy->level == ch->level"):
            self.assertIn(term, std, term)

    def test_immortals_are_not_ranked(self) -> None:
        """By trust, the way every other staff test is asked."""
        refusal = self.dummy.split("static const char *dummy_board_refusal(",
                                   1)[1].split("\n}", 1)[0]
        self.assertIn("IS_TRUSTED( ch, LEVEL_IMMORTAL )", refusal)

    def test_a_dummy_changed_mid_run_is_not_ranked(self) -> None:
        """The dummy is shared; anybody can change it under you."""
        self.assertIn("dummy_config_epoch++", self.dummy.rsplit(
            "static void dummy_configure(", 1)[1][:400])
        refusal = self.dummy.split("static const char *dummy_board_refusal(",
                                   1)[1].split("\n}", 1)[0]
        self.assertIn("pc->dummy_epoch != dummy_config_epoch", refusal)
        for command in ('"bench"', '"endless"'):
            branch = self.dummy.split("!str_prefix( arg1, %s )" % command, 1)[1]
            self.assertIn("dummy_config_epoch++", branch[:1800], command)

    def test_the_run_is_read_before_the_report_clears_it(self) -> None:
        limit = self.dummy.split("bool dummy_round_limit(", 1)[1]
        limit = limit.split("\n}", 1)[0]
        for read_first in ("total   = ch->pcdata->dummy_dealt",
                           "refusal = dummy_board_refusal( ch, victim )"):
            self.assertLess(limit.index(read_first),
                            limit.index("dummy_report( ch, victim )"))
        self.assertIn("dps_board_submit( ch, total, seconds )", limit)

    def test_a_tie_does_not_take_the_place(self) -> None:
        """Whoever got there first keeps it."""
        submit = self.dummy.split("static void dps_board_submit(", 1)[1]
        submit = submit.split("\n}", 1)[0]
        self.assertIn("if ( total > dps_board[at].total )", submit)
        self.assertIn("total > previous", submit)

    def test_the_board_survives_a_crash_mid_write(self) -> None:
        save = self.dummy.split("static void dps_board_save(", 1)[1]
        save = save.split("\n}", 1)[0]
        self.assertIn('DPSBOARD_FILE ".tmp"', save)
        self.assertIn('rename( DPSBOARD_FILE ".tmp", DPSBOARD_FILE )', save)
        self.assertIn("fpReserve", save)

    def test_number_one_earns_the_achievement(self) -> None:
        submit = self.dummy.split("static void dps_board_submit(", 1)[1]
        submit = submit.split("\n}", 1)[0]
        self.assertIn("ACHIEVEMENT_EVENT_DPS_CHAMPION", submit)
        source = read("src", "achievements.c")
        self.assertIn('"benchmark-champion"', source)
        self.assertIn("ACHIEVEMENT_EVENT_DPS_CHAMPION", self.merc)

    def test_the_board_is_dummy_leaderboard(self) -> None:
        """DUMMY LEADERBOARD is the command, on the owner's word. A
        top-level LEADERBOARD claimed a general word for one feature,
        beside a pkill ranking a player could expect it to show."""
        interp = read("src", "interp.c")
        self.assertNotIn('{ "leaderboard",', interp)
        self.assertNotIn("do_leaderboard", read("src", "interp.h"))
        body = self.dummy.split("void do_dummy(", 1)[1]
        self.assertIn('!str_prefix( arg1, "leaderboard" )', body)
        # Ahead of the no-dummy-here check, so it works outside the yard.
        self.assertLess(body.index("dps_board_show( ch )"),
                        body.index("There is no training dummy here."))
        help_text = read("area", "commands.are")
        topic = help_text.split("0 LEADERBOARD BENCHMARK~", 1)[1].split("~", 1)[0]
        self.assertIn("Syntax: dummy leaderboard", topic)

    # ------------------------------------------------ in and out by name
    def test_the_way_in_is_enter_ring(self) -> None:
        """The route generator names a portal by its first keyword, so
        the ring's keywords lead with "ring" -- otherwise the published
        route says ENTER PRACTICE."""
        ring = self.area.split("#2404", 1)[1].replace("\r", "").split("\n")
        self.assertTrue(ring[1].startswith("ring "), ring[1])
        import json
        routes = json.loads(read("webadmin", "directions.json"))["routes"]
        yard = [r for r in routes if r.get("vnum") == 2419][0]
        self.assertTrue(yard["commands"].endswith(";enter ring"),
                        yard["commands"])

    def test_the_sparring_room_says_what_to_type(self) -> None:
        dresden = read("area", "dresden.are")
        room = dresden.split("#4462", 1)[1].split("\n#", 1)[0]
        self.assertIn("ENTER", room)
        self.assertIn("RING to step through", room)
        self.assertIn("LEAVE RING", room)

    def test_the_help_gives_the_way_there_from_the_route(self) -> None:
        """Written directions go stale when the world changes; these are
        checked against the generated route, so they cannot."""
        import json
        routes = json.loads(read("webadmin", "directions.json"))["routes"]
        yard = [r for r in routes if r.get("vnum") == 2419][0]
        walk = []
        for step in yard["steps"][:-1]:          # the last is the ring
            m = re.fullmatch(r"(\w+) x(\d+)", step)
            walk.append("%s %s" % (m.group(1), m.group(2)) if m else step)
        expected = ", ".join(walk)
        topic = read("area", "commands.are").replace("\r", "")
        topic = topic.split("0 DUMMY TRAINING YARD~", 1)[1].split("\n~", 1)[0]
        flat = " ".join(topic.split())
        self.assertIn(expected, flat, "HELP DUMMY's directions are stale")
        for words in ("WALK DUMMY", "ENTER RING", "LEAVE RING"):
            self.assertIn(words, topic, words)

    # ------------------------------------------ the board is runtime state
    def test_the_board_file_is_runtime_state_everywhere(self) -> None:
        """Never tracked, never restored from a checkout, always
        synced, and never inherited by a test world."""
        self.assertIn("area/dpsboard.txt",
                      read(".gitignore"))
        self.assertIn('"dpsboard.txt"', read("tests", "live_mud.py"))
        deploy = read("deploy", "windows-vm", "toc-deploy")
        self.assertIn("dpsboard.txt", deploy.split("runtime_txt=", 1)[1][:400])
        self.assertIn("area/dpsboard.txt",
                      read(".github", "workflows", "validate.yml"))

    def test_every_synced_file_is_one_that_exists(self) -> None:
        """The sync skips a missing path without a word, which is how
        seven runtime files went unbacked for ten months: they were
        listed without the .txt the game writes."""
        import re as _re
        sync = read("deploy", "windows-vm", "toc-state-sync")
        files = _re.search(r'STATE_FILES="([^"]*)"', sync).group(1).split()
        self.assertIn("area/dpsboard.txt", files)
        source = "".join(read("src", f.name) for f in
                         (ROOT / "src").iterdir()
                         if f.suffix in (".c", ".h"))
        for path in files:
            name = path.split("/", 1)[1]
            on_disk = (ROOT / path).exists()
            written = ('"%s"' % name in source
                       or '/%s"' % name in source)
            self.assertTrue(on_disk or written,
                            "%s is neither tracked nor written by the game"
                            % path)

    # ------------------------------------------------- one at a time
    def test_the_yard_takes_one_fighter_at_a_time(self) -> None:
        """ROOM_SOLITARY: room_is_private() counts mortal players only
        and can_enter_private_room() lets immortals in anyway, which is
        the rule asked for exactly."""
        room = self.area.split("#2419", 1)[1].split("\n#", 1)[0]
        line = [l for l in room.splitlines()
                if re.fullmatch(r"0 [A-Za-z]+ 1", l.strip())][0]
        self.assertIn("L", line.split()[1], "the yard is not solitary")
        self.assertIn("V", line.split()[1], "the yard is not an arena")

    def test_a_portal_asks_whether_the_room_is_full(self) -> None:
        """do_enter never asked, so a portal walked past every private
        room in the world -- and the ring into the yard is a portal.
        Asked before the fare, so a refusal costs nothing."""
        move = read("src", "act_move.c")
        body = move.split("void do_enter(", 1)[1].split("\n}", 1)[0]
        self.assertIn("can_enter_private_room( ch, to_room )", body)
        self.assertLess(body.index("can_enter_private_room( ch, to_room )"),
                        body.index("switch( obj->value[0])"))
        self.assertGreater(body.index("can_enter_private_room( ch, to_room )"),
                           body.index("to_room = get_room_index"))

    def test_the_ring_sits_on_one_line(self) -> None:
        """An object's long description ends at its ~ on the same line;
        a line break before it is a blank line under the object, since
        the game adds its own."""
        ring = self.area.split("#2404", 1)[1].split("\n#", 1)[0]
        lines = ring.replace("\r", "").split("\n")
        # [1] keywords, [2] short, [3] long -- ending on its own ~.
        self.assertTrue(lines[3].endswith("~"), repr(lines[3]))

    def test_walk_dummy_finds_it(self) -> None:
        """The Mudlet walker matches the published route's area and
        room names, so the word has to be in one of them."""
        header = self.area.split("\n", 1)[0]
        self.assertIn("Dummy", header)
        import json
        routes = json.loads(read("webadmin", "directions.json"))["routes"]
        yard = [r for r in routes if r.get("vnum") == 2419]
        self.assertEqual(1, len(yard))
        haystack = " ".join(str(yard[0].get(k, "")) for k in
                            ("area_display", "area", "room")).lower()
        self.assertIn("dummy", haystack)

    def test_no_quest_sends_you_after_the_dummy(self) -> None:
        """It cannot die, so a quest to kill it could never finish."""
        quest = read("src", "quest.c")
        body = quest.split("static bool quest_area_is_excluded(", 1)[1]
        body = body.split("\n}", 1)[0]
        self.assertIn("QUEST_EXCLUDED_YARD", body)
        self.assertIn('#define QUEST_EXCLUDED_YARD     "dummy.are"', self.merc)

    def test_the_session_is_not_persisted(self) -> None:
        """A training run is something you are doing, not something
        you are: none of it belongs in a player file."""
        save = read("src", "save.c")
        for field in ("dummy_dealt", "dummy_taken", "dummy_started",
                      "dummy_level", "dummy_dealt_from", "dummy_taken_from",
                      "dummy_avoided", "dummy_evaded", "dummy_attempts",
                      "dummy_worst", "dummy_out", "dummy_in",
                      "dummy_rounds", "dummy_epoch", "dummy_standard",
                      "dummy_pre_hit", "dummy_pre_mana", "dummy_pre_move"):
            self.assertIn(field, self.merc, field)
            self.assertNotIn(field, save, field + " reached save.c")


if __name__ == "__main__":
    unittest.main()

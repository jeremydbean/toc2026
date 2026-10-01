from __future__ import annotations

import re
import unittest
from pathlib import Path

from webadmin.area_parser import AreaParser


ROOT = Path(__file__).resolve().parents[1]


def function_body(source: str, start: str, end: str) -> str:
    if not end:
        prefix, separator, body = source.partition(start)
        if not separator:
            raise AssertionError(f"Could not locate {start!r}")
        return body

    match = re.search(
        rf"{re.escape(start)}(?P<body>.*?){re.escape(end)}",
        source,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError(f"Could not locate {start!r} before {end!r}")
    return match.group("body")



def without_comments(source: str) -> str:
    """C source with its comments removed.

    A test that greps for a line of code will otherwise match the
    comment that explains why that line was taken out, which is the
    opposite of what it is asking.
    """
    return re.sub(r"/\*.*?\*/", " ", source, flags=re.S)


class AutomaticQuestSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.quest = (ROOT / "src" / "quest.c").read_text(encoding="utf-8")
        cls.fight = (ROOT / "src" / "fight.c").read_text(encoding="utf-8")
        cls.act_comm = (ROOT / "src" / "act_comm.c").read_text(
            encoding="utf-8"
        )
        cls.act_info = (ROOT / "src" / "act_info.c").read_text(
            encoding="utf-8"
        )
        cls.act_obj = (ROOT / "src" / "act_obj.c").read_text(encoding="utf-8")
        cls.save = (ROOT / "src" / "save.c").read_text(encoding="utf-8")
        cls.achievements = (ROOT / "src" / "achievements.c").read_text(
            encoding="utf-8"
        )
        cls.help = (ROOT / "area" / "commands.are").read_text(
            encoding="latin-1"
        )
        cls.parser = AreaParser(ROOT / "area")
        cls.parser.parse_all()

    def test_target_selection_uses_suitable_live_mobiles(self) -> None:
        suitability = function_body(
            self.quest,
            "static bool automatic_quest_target_is_suitable",
            "void generate_quest(CHAR_DATA *ch, CHAR_DATA *questman)",
        )
        generation = function_body(
            self.quest,
            "void generate_quest(CHAR_DATA *ch, CHAR_DATA *questman)",
            "void quest_update",
        )

        for contract in (
            "FOR_EACH_CHARACTER( iter, candidate )",
            "number_range(1, ++candidate_count)",
            "!can_see_room(ch, room)",
            "room_is_private(room)",
            "ROOM_SAFE",
            "ROOM_DT",
            "ROOM_JAIL",
            "ACT_GAIN",
            "ACT_NOKILL",
            "ACT_QUESTM",
            "ACT_PET",
            "AFF2_GHOST",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, suitability + generation)

        self.assertNotIn("number_range(50, 30000)", generation)
        self.assertNotIn("get_char_world", generation)
        self.assertNotIn("find_location", generation)

    def test_hyrule_is_never_a_quest_destination(self) -> None:
        """443 rooms, generated, and its dungeons refuse recall.

        A quest pointing at a mobile seven floors down is a half-hour
        march through content the player may never have seen, for a
        quest reward. The area is matched on its file rather than a vnum
        range: it is generated, so the vnums are the generator's
        business, but the file it is written to is fixed.
        """
        merc = (ROOT / "src" / "merc.h").read_text(encoding="utf-8")
        self.assertIn('#define QUEST_EXCLUDED_AREA     "hyrule.are"', merc)

        body = self.quest.split("static bool quest_area_is_excluded(")[1]
        body = body.split(chr(10) + "}")[0]
        self.assertIn("room->area->file_name", body)
        self.assertIn("QUEST_EXCLUDED_AREA", body)

        check = self.quest.split("automatic_quest_target_is_suitable( CHAR_DATA")[1]
        check = check.split(chr(10) + "}")[0]
        self.assertIn("quest_area_is_excluded(room)", check)

        # And the file the constant names is really the one in play.
        self.assertTrue(
            (ROOT / "area" / "hyrule.are").is_file(),
            "the excluded area file has been renamed; the constant is stale",
        )

    def test_group_members_and_pet_owners_receive_kill_credit(self) -> None:
        credit = function_body(
            self.quest, "void quest_record_kill", "void quest_handle_logout"
        )

        self.assertIn("credit->master", credit)
        self.assertIn("is_same_group(member, credit)", credit)
        self.assertIn("credit_automatic_quest_kill(credit, target_vnum)", credit)
        self.assertIn("ch->questmob = -1", self.quest)
        self.assertIn("save_char_obj(ch)", self.quest)
        self.assertIn("quest_record_kill(ch, victim)", self.fight)
        self.assertNotIn("ch->questmob = -1", self.fight)

    def test_recovery_tokens_are_bound_nested_and_cleaned_up(self) -> None:
        generation = function_body(
            self.quest,
            "void generate_quest(CHAR_DATA *ch, CHAR_DATA *questman)",
            "void quest_update",
        )
        completion = function_body(self.quest, "void do_quest", "void generate_quest")

        self.assertIn("questitem->value[4] = quest_token_owner_tag(ch)", generation)
        self.assertIn("questitem->owner = str_dup(ch->name)", generation)
        self.assertIn("find_automatic_quest_token(obj->contains", self.quest)
        self.assertIn("remove_automatic_quest_tokens(ch)", completion)

        for source in (self.act_obj, self.save):
            with self.subTest(source=source[:20]):
                self.assertIn("OBJ_VNUM_QUEST_TOKEN_FIRST", source)
                self.assertIn("OBJ_VNUM_QUEST_TOKEN_LAST", source)
                self.assertIn("obj->value[4] != 0", source)
        self.assertIn("obj->value[4] != ch->pcdata->id + 1", self.act_obj)
        self.assertIn("str_cmp(obj->owner, ch->name)", self.act_obj)

    def test_turn_in_and_abort_work_at_any_questmaster(self) -> None:
        command = function_body(self.quest, "void do_quest", "void generate_quest")

        self.assertNotIn("ch->questgiver != questman", command)
        self.assertNotIn("questgiver->", command)
        self.assertNotIn("Heroes cannot abandon quests", command)
        self.assertIn("Report to any questmaster", command)
        self.assertIn("Completed quests may be turned in to any questmaster", self.help)

    def test_timeout_cooldown_and_logout_transitions_are_clean(self) -> None:
        updater = function_body(self.quest, "void quest_update", "")
        logout = function_body(
            self.quest, "void quest_handle_logout", "void do_quest"
        )

        self.assertIn("remove_automatic_quest_tokens(ch)", updater)
        self.assertIn("ch->questrush = false", updater)
        self.assertGreaterEqual(updater.count("save_char_obj(ch)"), 2)
        self.assertIn("ch->queststreak = 0", logout)
        self.assertIn("quest_handle_logout(ch)", self.act_comm)
        self.assertIn(
            "Finish or abort your active automatic quest before remorting",
            self.act_info,
        )

    def test_shop_rewards_are_real_available_and_bounded(self) -> None:
        command = function_body(self.quest, "void do_quest", "void generate_quest")
        reward_vnums = (24, 3081, 4639, 20303, 20304, 20305, 20306)

        for vnum in reward_vnums:
            with self.subTest(vnum=vnum):
                self.assertIn(vnum, self.parser.objects)

        keepsake = self.parser.objects[20306]
        self.assertIn("questmaster", keepsake.short_desc.lower())
        self.assertIn("#define QUEST_ITEM5 20306", self.quest)
        self.assertIn("number_range(1,3)", command)
        self.assertIn("ch->practice >= SHRT_MAX", command)
        self.assertIn("cache_rewards[cache_index]", command)

    def test_completion_rewards_and_new_achievements_are_wired(self) -> None:
        completion = function_body(
            self.quest,
            "static void complete_automatic_quest",
            "void quest_record_kill",
        )

        self.assertIn("quest_streak_bonus(ch)", completion)
        self.assertIn("ch->nextquest = ch->level >= 50 ? 5 : 15", completion)
        self.assertIn("ACHIEVEMENT_EVENT_QUEST_RUSH", completion)
        self.assertIn("ACHIEVEMENT_EVENT_QUEST_LAST_MINUTE", completion)
        self.assertNotIn("50%%%% chance", completion)
        self.assertIn("add_quest_points(ch, wagered * 2)", self.quest)

        for key in (
            "two-hundred-fifty-quests",
            "twenty-five-quest-streak",
            "quest-rush",
            "quest-last-minute",
            "quest-gamble-win",
            "quest-keepsake",
        ):
            with self.subTest(key=key):
                self.assertIn(f'{{ "{key}"', self.achievements)

    def test_the_short_hero_cooldown_reaches_every_hero(self) -> None:
        """50 was the ceiling before remorts raised it to 59.

        Four places shortened the wait for a character with nothing left to
        level, and all four tested for exactly 50, so the heroes they were
        written for never matched.
        """
        self.assertNotIn("ch->level == 50", self.quest)
        self.assertEqual(self.quest.count("ch->level >= 50"), 4)

    def test_the_command_list_does_not_need_a_questmaster(self) -> None:
        """Everything that talks to the mob needs one present; printing the
        syntax does not, and gating it behind one meant the only way to
        learn the command was to already be standing at it."""
        command = function_body(self.quest, "void do_quest", "static bool")

        self.assertIn("static void quest_show_commands", self.quest)
        gate = command.index("You can't do that here")
        self.assertLess(
            command.index("quest_show_commands(ch)"), gate,
            "the command list has to be answerable before the questmaster "
            "check, not only after it",
        )
        for word in ("list", "buy", "request", "complete", "abort"):
            with self.subTest(word=word):
                self.assertIn('str_prefix(arg1, "%s")' % word, command)

    def test_subcommands_accept_abbreviations(self) -> None:
        """str_prefix matches an empty string against anything, so each
        test needs the emptiness guard beside it or a bare AQUEST would be
        read as AQUEST INFO."""
        command = function_body(self.quest, "void do_quest", "static bool")

        for word in ("info", "points", "time", "gamble"):
            with self.subTest(word=word):
                self.assertIn(
                    'str_prefix(arg1, "%s") && arg1[0] != \'\\0\'' % word,
                    command,
                )
        self.assertNotIn("strcmp(arg1", command)

    def test_a_character_below_level_four_can_be_given_a_quest(self) -> None:
        """The floor was an absolute level 3 and the ceiling excluded the
        player's own level, so nothing under level 4 had a legal target --
        and each attempt spent a cooldown to be told so."""
        suitability = function_body(
            self.quest,
            "static bool automatic_quest_target_is_suitable",
            "void generate_quest",
        )
        generation = function_body(
            self.quest,
            "void generate_quest(CHAR_DATA *ch, CHAR_DATA *questman)",
            "void quest_update",
        )

        self.assertIn("(ch->level < 6 ? 1 : 3)", suitability)
        self.assertIn("index->level > ch->level", suitability)
        self.assertIn("ch->nextquest = 1;", generation)

    def test_every_level_may_quest_including_immortals(self) -> None:
        """A flat `ch->level > 59` refused staff a quest outright.

        What they were told was "there are no suitable quests at the
        moment", which was not true: the pool had never been looked
        at. Nothing about questing needs a mortal, and being unable to
        try the feature is a poor position to judge it from.

        No special case replaces it. The per-target ceiling,
        `index->level > ch->level`, simply stops binding once the
        character is above the mortal cap.
        """
        suitability = function_body(
            self.quest,
            "static bool automatic_quest_target_is_suitable",
            "void generate_quest",
        )
        # Comments included the removed line to explain it, and a
        # test that reads them cannot tell an explanation from a
        # reinstatement.
        self.assertNotIn("ch->level > 59", without_comments(self.quest))
        self.assertNotIn("LEVEL_IMMORTAL", suitability)
        self.assertNotIn("IS_IMMORTAL", suitability)
        # And the ceiling that does the work is still there.
        self.assertIn("index->level > ch->level", suitability)

    def test_the_questmaster_names_an_area_a_player_would_recognise(self):
        """area->name is the #AREA line -- "{1 70} Killum Hyrule" -- so the
        directions read out the level range and the builder's handle."""
        generation = function_body(
            self.quest,
            "void generate_quest(CHAR_DATA *ch, CHAR_DATA *questman)",
            "void quest_update",
        )

        # Shared since 2026-10-01 so the client's quest strip names the
        # region in the same words the quest master says aloud.
        self.assertIn("\nvoid quest_area_name( const char *raw", self.quest)
        self.assertIn("quest_area_name( where->area",
                      (ROOT / "src" / "gmcp.c").read_text(encoding="latin-1"))
        self.assertIn("quest_area_name( room->area", generation)
        self.assertEqual(generation.count("room->name, area_name)"), 2)
        self.assertNotIn("room->name, room->area->name)", generation)

    def test_the_shop_listing_is_a_literal_not_a_format_string(self) -> None:
        """send_to_char does not collapse %%, so the bonus lines printed
        "+10%%" to the player."""
        listing = function_body(
            self.quest, '"{09.-[ Quest Shop ]', '"{09\'---'
        )
        self.assertNotIn("%%", listing)

    def test_recovery_tokens_cannot_be_drunk(self) -> None:
        """They were ITEM_POTION with every spell slot zero. Quaffing one
        destroyed it and left the quest unfinishable."""
        tokens = range(25038, 25043)
        self.assertEqual(
            {v: self.parser.objects[v].item_type for v in tokens},
            {v: "13" for v in tokens},
            "every recovery token should be ITEM_TRASH (13)",
        )

    def test_the_help_file_holds_no_stray_utf8(self) -> None:
        """commands.are is Latin-1. A UTF-8 em-dash written into it reaches
        the player as three garbage characters."""
        raw = (ROOT / "area" / "commands.are").read_bytes()
        self.assertNotIn(b"\xe2\x80", raw)


if __name__ == "__main__":
    unittest.main()


class EmergencyContractTests(unittest.TestCase):
    """The rare five-minute contract worth five times the points.

    Three ways to get this wrong, and all three are quiet: a quest
    that is both an emergency and a rush pays ten times; a clear that
    misses one site carries the multiplier into the next quest; and
    reading the flag after it has been cleared pays nothing at all.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.quest = (ROOT / "src" / "quest.c").read_text(encoding="utf-8")
        cls.merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")

    def test_the_numbers_are_named_once(self) -> None:
        self.assertIn("#define QUEST_EMERGENCY_CHANCE      5", self.merc)
        self.assertIn("#define QUEST_EMERGENCY_MINUTES     5", self.merc)
        self.assertIn("#define QUEST_EMERGENCY_MULTIPLIER  5", self.merc)

    def test_it_is_rolled_ahead_of_the_rush_and_excludes_it(self) -> None:
        offer = self.quest.split("if (chance(QUEST_EMERGENCY_CHANCE))", 1)
        self.assertEqual(len(offer), 2, "the emergency roll went missing")
        self.assertIn("else if (chance(20))", offer[1],
                      "the rush contract must be the alternative, not a "
                      "second roll that can also land")
        body = offer[1][:offer[1].index("else if (chance(20))")]
        self.assertIn("ch->questrush = false;", body)
        self.assertIn("ch->questemergency = true;", body)

    def test_the_multiplier_replaces_the_rush_rather_than_stacking(self) -> None:
        self.assertRegex(
            self.quest,
            r"if \( completed_emergency \)\s*\n\s*pointreward \*= "
            r"QUEST_EMERGENCY_MULTIPLIER;\s*\n\s*else if \( completed_rush \)")

    def test_the_flag_is_read_before_anything_clears_it(self) -> None:
        body = self.quest.split("static void complete_automatic_quest", 1)[1]
        read_at = body.index("completed_emergency = ch->questemergency")
        cleared_at = body.index("ch->questemergency = false")
        self.assertLess(read_at, cleared_at)

    def test_every_questrush_clear_clears_the_emergency_too(self) -> None:
        """A stale flag would pay five times on the following quest."""
        lines = self.quest.split("\n")
        for i, line in enumerate(lines):
            if "ch->questrush" in line and "false" in line:
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                self.assertIn(
                    "questemergency", nxt,
                    "quest.c:%d clears questrush and leaves questemergency "
                    "set" % (i + 1))

    def test_the_player_is_told_which_contract_they_hold(self) -> None:
        self.assertIn("EMERGENCY CONTRACT!", self.quest)
        self.assertIn("EMERGENCY CONTRACT -", self.quest)
        self.assertIn("ACHIEVEMENT_EVENT_QUEST_EMERGENCY", self.quest)

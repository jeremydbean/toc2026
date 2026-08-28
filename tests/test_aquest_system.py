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
        self.assertIn("ch->nextquest = ch->level == 50 ? 5 : 15", completion)
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


if __name__ == "__main__":
    unittest.main()

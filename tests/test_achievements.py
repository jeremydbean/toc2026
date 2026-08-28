from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from scripts.build_hyrule_area import BOSS_MOBS
from webadmin.area_parser import AreaParser


ROOT = Path(__file__).resolve().parents[1]
ENTRY_RE = re.compile(
    r'^\s*\{\s*"(?P<key>[^"]+)",\s*'
    r'"(?P<title>[^"]+)",\s*'
    r'"(?P<description>[^"]+)",\s*'
    r'(?P<category>ACH_CAT_[A-Z_]+),\s*'
    r'(?P<points>\d+),\s*'
    r'(?P<hidden>true|false),\s*'
    r'(?P<requirement>ACH_REQ_[A-Z_]+),\s*'
    r'(?P<target>\d+L?|ACHIEVEMENT_EVENT_[A-Z_]+),\s*'
    r'(?P<auxiliary>\d+)\s*\},?\s*$',
    re.MULTILINE,
)


class AchievementSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "src" / "achievements.c").read_text(encoding="utf-8")
        cls.merc = (ROOT / "src" / "merc.h").read_text(encoding="utf-8")
        cls.save = (ROOT / "src" / "save.c").read_text(encoding="utf-8")
        cls.comm = (ROOT / "src" / "comm.c").read_text(encoding="utf-8")
        cls.entries = [match.groupdict() for match in ENTRY_RE.finditer(cls.source)]
        cls.area_parser = AreaParser(ROOT / "area")
        cls.area_parser.parse_all()
        cls.manifest = json.loads(
            (ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8")
        )

    def test_catalog_has_stable_unique_keys_and_fits_reserved_capacity(self) -> None:
        catalog_lines = re.findall(r'^[ \t]*\{[ \t]*"', self.source, re.MULTILINE)
        self.assertEqual(len(self.entries), len(catalog_lines))
        self.assertEqual(len(self.entries), 111)

        keys = [entry["key"] for entry in self.entries]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all(re.fullmatch(r"[a-z0-9-]+", key) for key in keys))

        capacity = int(re.search(r"#define MAX_ACHIEVEMENTS\s+(\d+)", self.merc).group(1))
        self.assertLessEqual(len(self.entries), capacity)

    def test_catalog_supports_all_categories_progress_and_hidden_unlocks(self) -> None:
        self.assertEqual(
            {entry["category"] for entry in self.entries},
            {
                "ACH_CAT_CHARACTER",
                "ACH_CAT_COMBAT",
                "ACH_CAT_ENCOUNTERS",
                "ACH_CAT_QUESTS",
                "ACH_CAT_EXPLORATION",
                "ACH_CAT_COLLECTION",
                "ACH_CAT_CRAFTING",
                "ACH_CAT_MISADVENTURE",
                "ACH_CAT_HYRULE",
            },
        )
        self.assertGreaterEqual(
            sum(entry["hidden"] == "true" for entry in self.entries), 2
        )
        self.assertTrue(all(int(entry["points"]) > 0 for entry in self.entries))
        self.assertIn("achievement_progress", self.source)
        self.assertIn("achievement_format_date", self.source)

    def test_summary_is_compact_and_paged_colors_are_converted(self) -> None:
        pager = self.comm.split("void page_to_char", 1)[1].split(
            "void show_string", 1
        )[0]

        self.assertIn("color_convert( txt, ch, color_is_enabled( ch ), &colorized )", pager)
        self.assertIn("page_text = dstring_cstr( &colorized )", pager)
        self.assertIn("safe_strcat(ptr, total_len, page_text)", pager)
        self.assertIn("category += 2", self.source)
        self.assertIn("Progress by category (earned/total, points)", self.source)
        self.assertNotIn("Categories: Character", self.source)

    def test_hyrule_boss_achievements_match_generated_dungeon_contract(self) -> None:
        actual = {
            int(entry["auxiliary"]): int(entry["target"])
            for entry in self.entries
            if entry["requirement"] == "ACH_REQ_BOSS"
            and entry["category"] == "ACH_CAT_HYRULE"
        }
        expected = {
            dungeon["boss_vnum"]: BOSS_MOBS[dungeon["level"]]
            for dungeon in self.manifest["dungeons"]
        }
        self.assertEqual(actual, expected)
        self.assertIn("is_same_group(member, credit)", self.source)

    def test_world_bosses_exist_at_their_catalog_rooms(self) -> None:
        entries = [
            entry
            for entry in self.entries
            if entry["requirement"] == "ACH_REQ_BOSS"
            and entry["category"] == "ACH_CAT_ENCOUNTERS"
        ]
        self.assertEqual(len(entries), 17)

        for entry in entries:
            with self.subTest(key=entry["key"]):
                mob = self.area_parser.mobiles[int(entry["target"])]
                self.assertIn(int(entry["auxiliary"]), mob.spawn_rooms)
                self.assertGreaterEqual(mob.level, 57)

    def test_rare_collection_items_exist(self) -> None:
        entries = [
            entry
            for entry in self.entries
            if entry["requirement"] == "ACH_REQ_OBJECT"
            and entry["category"] == "ACH_CAT_COLLECTION"
        ]
        self.assertEqual(len(entries), 17)
        for entry in entries:
            with self.subTest(key=entry["key"]):
                self.assertIn(int(entry["target"]), self.area_parser.objects)

    def test_save_format_uses_stable_keys_and_persistent_progress_fields(self) -> None:
        for keyword in (
            "Achv",
            "AchKills",
            "AchQuests",
            "AchDeaths",
            "AchExplore",
            "AchMaps",
            "AchCompass",
            "AchTriforce",
        ):
            with self.subTest(keyword=keyword):
                self.assertIn(keyword, self.source + self.save)

        self.assertIn("achievement_table[index].key", self.source)
        self.assertIn("achievement_index_by_key", self.source)
        self.assertIn("achievement_write_char( ch, fp )", self.save)
        self.assertIn("achievement_load_earned( ch, achievement_key, earned )", self.save)

    def test_all_primary_player_events_are_wired(self) -> None:
        fight = (ROOT / "src" / "fight.c").read_text(encoding="utf-8")
        quest = (ROOT / "src" / "quest.c").read_text(encoding="utf-8")
        handler = (ROOT / "src" / "handler.c").read_text(encoding="utf-8")
        act_obj = (ROOT / "src" / "act_obj.c").read_text(encoding="utf-8")
        magic2 = (ROOT / "src" / "magic2.c").read_text(encoding="utf-8")
        update = (ROOT / "src" / "update.c").read_text(encoding="utf-8")
        comm = (ROOT / "src" / "comm.c").read_text(encoding="utf-8")
        interp = (ROOT / "src" / "interp.c").read_text(encoding="utf-8")
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")

        self.assertIn("achievement_record_kill(ch, victim)", fight)
        self.assertIn("achievement_record_death( victim )", fight)
        self.assertGreaterEqual(fight.count("achievement_check_state(ch, true)"), 2)
        self.assertEqual(quest.count("achievement_record_quest(ch)"), 1)
        for event in (
            "ACHIEVEMENT_EVENT_QUEST_RUSH",
            "ACHIEVEMENT_EVENT_QUEST_LAST_MINUTE",
            "ACHIEVEMENT_EVENT_QUEST_GAMBLE_WIN",
        ):
            with self.subTest(event=event):
                self.assertIn(event, quest)
        self.assertIn("achievement_record_room(ch, pRoomIndex->vnum", handler)
        self.assertIn("achievement_record_object(ch, obj->pIndexData->vnum", handler)
        self.assertIn("ACHIEVEMENT_EVENT_DEATH_ITEM", handler)
        self.assertIn("ACHIEVEMENT_EVENT_PUZZLE_TRAP", act_obj)
        for event in (
            "ACHIEVEMENT_EVENT_BREW",
            "ACHIEVEMENT_EVENT_CONCOCT",
            "ACHIEVEMENT_EVENT_SCRIBE",
            "ACHIEVEMENT_EVENT_FARSLAY_SCROLL",
            "ACHIEVEMENT_EVENT_FARSLAYED",
            "ACHIEVEMENT_EVENT_FARSLAY_BACKFIRE",
            "ACHIEVEMENT_EVENT_FARSLAY_KILL",
            "ACHIEVEMENT_EVENT_DEATH_RAY",
        ):
            with self.subTest(event=event):
                self.assertIn(event, magic2)
        self.assertIn('spell_one = skill_lookup("vengence")', magic2)
        self.assertNotIn('skill_lookup("csst")', magic2)
        self.assertIn("achievement_check_state(ch, true)", update)
        self.assertIn("ACHIEVEMENT_EVENT_DEATH_TRAP", update)
        self.assertIn("achievement_check_state(ch, false)", comm)
        self.assertRegex(interp, r'"achievements"\s*,\s*do_achievements')
        self.assertIn("src/achievements.c", cmake)

    def test_player_help_and_documentation_are_present(self) -> None:
        command_help = (ROOT / "area" / "commands.are").read_text(encoding="latin-1")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        guide = (ROOT / "wiki" / "achievements.md").read_text(encoding="utf-8")

        self.assertIn("0 ACHIEVEMENT ACHIEVEMENTS~", command_help)
        self.assertIn("wiki/achievements.md", readme)
        self.assertIn("Existing Characters", guide)
        self.assertIn("lifetime mobile-kill", guide)


if __name__ == "__main__":
    unittest.main()

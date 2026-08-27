from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from scripts.build_hyrule_area import BOSS_MOBS


ROOT = Path(__file__).resolve().parents[1]
ENTRY_RE = re.compile(
    r'^\s*\{\s*"(?P<key>[^"]+)",\s*'
    r'"(?P<title>[^"]+)",\s*'
    r'"(?P<description>[^"]+)",\s*'
    r'(?P<category>ACH_CAT_[A-Z_]+),\s*'
    r'(?P<points>\d+),\s*'
    r'(?P<hidden>true|false),\s*'
    r'(?P<requirement>ACH_REQ_[A-Z_]+),\s*'
    r'(?P<target>\d+)L?,\s*'
    r'(?P<auxiliary>\d+)\s*\},?\s*$',
    re.MULTILINE,
)


class AchievementSystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "src" / "achievements.c").read_text(encoding="utf-8")
        cls.merc = (ROOT / "src" / "merc.h").read_text(encoding="utf-8")
        cls.save = (ROOT / "src" / "save.c").read_text(encoding="utf-8")
        cls.entries = [match.groupdict() for match in ENTRY_RE.finditer(cls.source)]
        cls.manifest = json.loads(
            (ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8")
        )

    def test_catalog_has_stable_unique_keys_and_fits_reserved_capacity(self) -> None:
        catalog_lines = re.findall(r'^[ \t]*\{[ \t]*"', self.source, re.MULTILINE)
        self.assertEqual(len(self.entries), len(catalog_lines))
        self.assertEqual(len(self.entries), 43)

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
                "ACH_CAT_QUESTS",
                "ACH_CAT_EXPLORATION",
                "ACH_CAT_HYRULE",
            },
        )
        self.assertGreaterEqual(
            sum(entry["hidden"] == "true" for entry in self.entries), 2
        )
        self.assertTrue(all(int(entry["points"]) > 0 for entry in self.entries))
        self.assertIn("achievement_progress", self.source)
        self.assertIn("achievement_format_date", self.source)

    def test_hyrule_boss_achievements_match_generated_dungeon_contract(self) -> None:
        actual = {
            int(entry["auxiliary"]): int(entry["target"])
            for entry in self.entries
            if entry["requirement"] == "ACH_REQ_BOSS"
        }
        expected = {
            dungeon["boss_vnum"]: BOSS_MOBS[dungeon["level"]]
            for dungeon in self.manifest["dungeons"]
        }
        self.assertEqual(actual, expected)
        self.assertIn("is_same_group(member, credit)", self.source)

    def test_save_format_uses_stable_keys_and_persistent_progress_fields(self) -> None:
        for keyword in (
            "Achv",
            "AchKills",
            "AchQuests",
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
        update = (ROOT / "src" / "update.c").read_text(encoding="utf-8")
        comm = (ROOT / "src" / "comm.c").read_text(encoding="utf-8")
        interp = (ROOT / "src" / "interp.c").read_text(encoding="utf-8")
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")

        self.assertIn("achievement_record_kill(ch, victim)", fight)
        self.assertGreaterEqual(fight.count("achievement_check_state(ch, true)"), 2)
        self.assertEqual(quest.count("achievement_record_quest(ch)"), 2)
        self.assertIn("achievement_record_room(ch, pRoomIndex->vnum", handler)
        self.assertIn("achievement_record_object(ch, obj->pIndexData->vnum", handler)
        self.assertIn("achievement_check_state(ch, true)", update)
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

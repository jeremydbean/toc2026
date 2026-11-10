"""The Gear Finder and the Oracle see gear that a death makes.

An area file says only what a reset places, so the dashboard's Gear Finder
(get_best_gear in webadmin/server.py) never saw what the game makes when
something dies: a Hyrule guardian's drop table (hyrule_boss_drops in
src/hyrule.c), Ganon's relic, a cleared room's boomerang, a holiday boss's
drops in its season and the black market's rarities. An independent review
(2026-11-10) found the Aquamentus coat and helm, 30650 and 30651, missing
from a level 25 warrior's list though any player who kills Aquamentus may
find them.

webadmin/gear_drops.py mirrors the C tables that make them. The first class
holds every mirrored number to its source -- the C arrays, merc.h and the
Hyrule generator -- and runs without the dashboard; the second asks the
finder and the Oracle, and skips without fastapi.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from webadmin import gear_drops  # noqa: E402  (no fastapi needed)

try:
    import fastapi  # noqa: F401  -- webadmin.server will not import without it

    WEBADMIN_UNAVAILABLE_REASON = None
except Exception as exc:  # pragma: no cover - C-only environments skip this
    WEBADMIN_UNAVAILABLE_REASON = (
        f"webadmin dependencies unavailable ({type(exc).__name__}: {exc}). "
        "Install webadmin/requirements.txt."
    )


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="latin-1")


MERC = source("src/merc.h")
HYRULE_C = source("src/hyrule.c")
FIGHT_C = source("src/fight.c")
MOVE_C = source("src/act_move.c")
SEASON_C = source("src/season.c")
HOLIDAY_C = source("src/holiday.c")
MARKET_C = source("src/blackmarket.c")
GOBLIN_C = source("src/goblin.c")
DISASTER_C = source("src/disaster.c")
MANIFEST = json.loads((ROOT / "data" / "hyrule_first_quest.json").read_text(encoding="utf-8"))


def define(name: str, text: str = MERC) -> int:
    match = re.search(rf"#define\s+{name}\s+(-?\d+)\b", text)
    if match is None:
        raise AssertionError(f"no #define {name}")
    return int(match.group(1))


def c_array(text: str, name: str) -> str:
    return text.split(f"{name}[] =", 1)[1].split("};", 1)[0]


def values(body: str, local: str = "") -> list[int]:
    """The numbers in a C initialiser, names resolved through merc.h (and a
    file's own #defines)."""
    out = []
    body = re.sub(r"/\*.*?\*/", " ", body, flags=re.S)
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|-?\d+", body):
        if token[0].isdigit() or token[0] == "-":
            out.append(int(token))
        elif token.isupper() or token.startswith(("OBJ_", "MOB_")):
            try:
                out.append(define(token, local + MERC))
            except AssertionError:
                if token.startswith(("OBJ_", "MOB_")):
                    raise
    return out


class MirrorTests(unittest.TestCase):
    """Every table in webadmin/gear_drops.py says what its C says."""

    def test_the_guardians_tables_are_hyrule_c_and_merc_h(self) -> None:
        self.assertEqual(list(gear_drops.GUARDIAN_VNUMS),
                         values(HYRULE_C.split("hyrule_guardian_vnums[9] =", 1)[1].split("};", 1)[0]))
        self.assertEqual(list(gear_drops.GUARDIAN_EXTRA_DROPS),
                         values(HYRULE_C.split("hyrule_boss_extra_drops[9] =", 1)[1].split("};", 1)[0]))
        self.assertEqual(gear_drops.BOSS_DROP_FIRST, define("OBJ_VNUM_HYRULE_BOSS_DROP_FIRST"))
        self.assertEqual(gear_drops.BOSS_DROPS_PER_GUARDIAN, define("HYRULE_BOSS_DROPS_PER_GUARDIAN"))
        self.assertEqual(gear_drops.BOSS_DROPS_PER_KILL, define("HYRULE_BOSS_DROPS_PER_KILL"))
        self.assertEqual(gear_drops.BOSS_EXTRA_FIRST, define("OBJ_VNUM_HYRULE_BOSS_EXTRA_FIRST"))
        self.assertEqual(gear_drops.BOSS_EXTRA_STRIDE, define("HYRULE_BOSS_EXTRA_STRIDE"))
        self.assertEqual(gear_drops.GANON_VNUM, define("HYRULE_GANON_VNUM"))
        self.assertEqual(gear_drops.SILVER_ARROW, define("OBJ_VNUM_HYRULE_SILVER_ARROW"))
        # Three distinct pieces of the table, drawn uniformly.
        drops = HYRULE_C.split("void hyrule_boss_drops(", 1)[1].split("\n}\n", 1)[0]
        count = HYRULE_C.split("int hyrule_boss_drop_count(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("HYRULE_BOSS_DROPS_PER_GUARDIAN + hyrule_boss_extra_drops[level - 1]", count)
        self.assertIn("total = hyrule_boss_drop_count( level );", drops)
        self.assertIn("get_obj_index( hyrule_boss_drop_vnum( level, n ) )", drops)
        self.assertIn("number_range( 0, total - 1 )", drops)
        self.assertIn("if ( seen )", drops)
        self.assertIn("hyrule_boss_drops( ch, corpse )", FIGHT_C)

    def test_the_guardians_tables_are_the_generators(self) -> None:
        from scripts.build_hyrule_area import BOSS_MOBS, boss_drop_vnum, boss_drops

        self.assertEqual(list(gear_drops.GUARDIAN_VNUMS), [BOSS_MOBS[level] for level in range(1, 10)])
        for level in range(1, 10):
            with self.subTest(level=level):
                self.assertEqual(gear_drops.boss_drop_vnums(level),
                                 [boss_drop_vnum(level, i) for i in range(len(boss_drops(level)))])

    def test_ganons_relics_are_fight_c(self) -> None:
        self.assertEqual(list(gear_drops.GANON_LOOT), values(c_array(FIGHT_C, "hyrule_ganon_loot_vnums")))
        corpse = FIGHT_C.split("OBJ_DATA *make_corpse(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("loot_vnum = hyrule_ganon_loot_vnums[loot_index]", corpse)

    def test_the_gates_are_act_move_c_and_the_generator(self) -> None:
        from scripts.build_hyrule_area import ENTRY_NEEDS, GUARDIAN_ALSO, GUARDIAN_NEEDS

        table = MOVE_C.split("hyrule_progress_gate[] =", 1)[1].split("};", 1)[0]
        rows = {}
        for chunk in table.split("{ ")[1:]:
            fields = [f.strip() for f in re.sub(r'(?:"[^"]*"\s*)+', "STR ",
                                                chunk.split("},", 1)[0]).replace("\n", " ").split(",")]
            fields = [f for f in fields if f]
            rows[int(fields[0])] = (int(fields[6]), int(fields[8]), int(fields[9]))
        self.assertEqual(rows, gear_drops.HYRULE_GATES)
        for level in range(2, 10):
            self.assertEqual(gear_drops.HYRULE_GATES[level],
                             (ENTRY_NEEDS[level], GUARDIAN_NEEDS[level], GUARDIAN_ALSO.get(level, 0)))

    def test_where_each_needed_thing_is_found_is_the_generators(self) -> None:
        from scripts.build_hyrule_area import CHEST_PRIZES, TOOL_SOURCES

        for tool, (level, _where) in TOOL_SOURCES.items():
            self.assertEqual(gear_drops.HYRULE_FOUND_IN[tool], level, tool)
        for level, prizes in CHEST_PRIZES.items():
            for prize in prizes:
                if prize in gear_drops.HYRULE_FOUND_IN:
                    self.assertEqual(gear_drops.HYRULE_FOUND_IN[prize], level, prize)
        cellars = {cellar["item_vnum"]: dungeon["level"]
                   for dungeon in MANIFEST["dungeons"] for cellar in dungeon.get("cellars", [])}
        self.assertEqual(gear_drops.HYRULE_FOUND_IN[gear_drops.SILVER_ARROW],
                         cellars[gear_drops.SILVER_ARROW])
        needed = {v for row in gear_drops.HYRULE_GATES.values() for v in row if v}
        self.assertLessEqual(needed | {gear_drops.SILVER_ARROW}, set(gear_drops.HYRULE_FOUND_IN))
        self.assertEqual(gear_drops.DUNGEON_TITLES,
                         {d["level"]: d["title"] for d in MANIFEST["dungeons"]})

    def test_the_wearable_clear_rewards_are_hyrule_c(self) -> None:
        from webadmin.area_parser import AreaParser

        parser = AreaParser(ROOT / "area")
        parser.parse_all()
        rows = values(c_array(HYRULE_C, "hyrule_clear_rewards"))
        pairs = list(zip(rows[0::2], rows[1::2]))
        wearable = {obj: room for room, obj in pairs
                    if parser.objects[obj].item_type in ("5", "9")}
        self.assertEqual({obj: room for obj, (_lvl, room) in gear_drops.CLEAR_REWARD_GEAR.items()},
                         wearable)
        for obj, (level, room) in gear_drops.CLEAR_REWARD_GEAR.items():
            self.assertTrue(parser.rooms[room].name.startswith("Level %d:" % level), obj)

    def test_the_holiday_bosses_are_season_c_and_holiday_c(self) -> None:
        roles = {"EVENT_DROP_PRIMARY": 0, "EVENT_DROP_FALLBACK": 1, "EVENT_DROP_RARE": 2}
        for name, value in roles.items():
            self.assertEqual(define(name), value)
        tables = {define("MOB_VNUM_EVENT_HORSEMAN"): c_array(SEASON_C, "horseman_drops"),
                  define("MOB_VNUM_EVENT_FATHER"): c_array(SEASON_C, "father_winter_drops")}
        self.assertEqual(set(tables), set(gear_drops.EVENT_BOSSES))
        holidays = self.holiday_rows()
        for mob, body in tables.items():
            rows = []
            for line in re.findall(r"\{\s*(\w+),\s*(\d+),\s*(\w+)\s*\}", body):
                if line[0] == "0":
                    continue        # the table's end
                rows.append((define(line[0]), int(line[1]), roles[line[2]]))
            holiday, start, end, table = gear_drops.EVENT_BOSSES[mob]
            with self.subTest(mob=mob):
                self.assertEqual(list(table), rows)
                key = "halloween" if mob == define("MOB_VNUM_EVENT_HORSEMAN") else "xmas"
                self.assertEqual((holiday, start, end), holidays[key][:3])
        self.assertEqual(gear_drops.EVENT_BOSS_ROOM, define("EVENT_BOSS_SPAWN_ROOM"))
        # The bosses come only in those two holidays.
        self.assertIn("case SEASON_HALLOWEEN: return MOB_VNUM_EVENT_HORSEMAN;", SEASON_C)
        self.assertIn("case SEASON_CHRISTMAS: return MOB_VNUM_EVENT_FATHER;", SEASON_C)
        self.assertIn("if ( get_current_season() != SEASON_NORMAL )", SEASON_C)

    def holiday_rows(self) -> dict[str, tuple]:
        """holidays[] in src/holiday.c: key -> (name, start, end, drop, chance),
        fixed-date rows only (the others' dates move with Easter and
        Thanksgiving)."""
        table = c_array(HOLIDAY_C, "holidays")
        rows = {}
        for match in re.finditer(
                r'\{ "(\w+)", "([^"]+)", (RULE_\w+), (-?\d+), (-?\d+), (-?\d+), (-?\d+),'
                r'(.*?)(OBJ_VNUM_\w+), (\d+),\s*MOB_VNUM_VENDOR', table, re.S):
            key, name, rule = match.group(1), match.group(2), match.group(3)
            if rule != "RULE_FIXED":
                rows[key] = (name, None, None, define(match.group(9)), int(match.group(10)))
                continue
            m1, d1, m2, d2 = (int(match.group(i)) for i in range(4, 8))
            rows[key] = (name, (m1, d1), (m2, d2), define(match.group(9)), int(match.group(10)))
        return rows

    def test_the_worn_holiday_treats_are_holiday_c(self) -> None:
        from webadmin.area_parser import AreaParser, WEAR_FLAGS, decode_flags

        parser = AreaParser(ROOT / "area")
        parser.parse_all()
        rows = self.holiday_rows()
        self.assertGreaterEqual(len(rows), 12)
        worn = {}
        for key, (name, start, end, drop, chance) in rows.items():
            obj = parser.objects[drop]
            flags = set(decode_flags(obj.wear_flags, WEAR_FLAGS)) - {"take"}
            if obj.item_type == "1" or flags - {"wield"} or (flags and obj.item_type == "5"):
                self.assertIsNotNone(start, f"{key}'s worn treat needs its dates mirrored")
                worn[drop] = (name, start, end, chance)
        self.assertEqual(worn, gear_drops.HOLIDAY_TREATS)
        drop = HOLIDAY_C.split("void holiday_corpse_drop(", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("number_percent() > h->drop_chance", drop)

    def test_the_rarities_are_the_black_markets(self) -> None:
        self.assertEqual(list(gear_drops.BM_BOSS_DROPS), values(c_array(MARKET_C, "bm_boss_drops")))
        self.assertEqual(list(gear_drops.BM_CAKES), values(c_array(MARKET_C, "bm_cakes")))
        self.assertEqual(list(gear_drops.BM_CHARMS), values(c_array(MARKET_C, "bm_charms")))
        self.assertEqual(gear_drops.BM_BOSS_DROP_CHANCE, define("BM_BOSS_DROP_CHANCE", MARKET_C))
        self.assertEqual(gear_drops.BM_CAKE_CHANCE, define("BM_CAKE_CHANCE", MARKET_C))
        self.assertEqual(gear_drops.BM_CHARM_CHANCE, define("BM_CHARM_CHANCE", MARKET_C))
        self.assertEqual(gear_drops.GOBLIN_RARE_CHANCE, define("GOBLIN_RARE_CHANCE", GOBLIN_C))
        self.assertEqual(gear_drops.DRAGON_RARE_CHANCE, define("DRAGON_RARE_CHANCE", DISASTER_C))
        self.assertEqual(gear_drops.GOBLIN_VNUM, define("MOB_VNUM_TREASURE_GOBLIN"))
        self.assertEqual(gear_drops.DEALER_VNUM, define("MOB_VNUM_BLACK_MARKET"))
        self.assertEqual(gear_drops.DRAGON_VNUM, define("MOB_VNUM_BLACK_DRAGON", DISASTER_C))
        rarity = MARKET_C.split("int black_market_rarity( void )", 1)[1].split("\n}\n", 1)[0]
        self.assertEqual(re.findall(r"BM_PICK\( (\w+) \)", rarity),
                         ["bm_boss_drops", "bm_cakes", "bm_charms"])
        self.assertIn("number_range( 0, 2 )", rarity)
        self.assertIn("vnum = black_market_rarity();", GOBLIN_C)
        self.assertIn("number_percent() <= DRAGON_RARE_CHANCE", DISASTER_C)

    def test_chances_follow_the_c(self) -> None:
        found = gear_drops.dynamic_sources(_FakeWorld(), datetime.date(2026, 10, 20))
        coat = found[30650][0]
        self.assertEqual(coat["kind"], "hyrule_guardian")
        self.assertAlmostEqual(coat["chance"], round(3 / 11, 4))
        ganon_piece = found[gear_drops.boss_drop_vnums(9)[0]][0]
        self.assertAlmostEqual(ganon_piece["chance"], 0.3)
        self.assertAlmostEqual(found[30577][0]["chance"], round(1 / 3, 4))
        # The pumpkin charm: its own 75%, or laid when nothing else fell.
        charm = [s for s in found[29924] if s["kind"] == "event_boss"][0]
        self.assertAlmostEqual(charm["chance"], 0.75 + 0.25 * 0.5 * 0.5)
        goblin = [s for s in found[29920] if s["kind"] == "treasure_goblin"][0]
        self.assertAlmostEqual(goblin["chance"], round(0.10 / 3 / 6, 4))
        self.assertTrue(gear_drops.offered(found[29920]))
        out = gear_drops.dynamic_sources(_FakeWorld(), datetime.date(2026, 8, 15))
        self.assertFalse(gear_drops.offered(out[29920]))
        self.assertTrue(gear_drops.offered(out[9943]))         # no holiday's
        self.assertTrue(gear_drops.in_window(datetime.date(2027, 1, 3), (12, 16), (1, 6)))
        self.assertFalse(gear_drops.in_window(datetime.date(2027, 1, 7), (12, 16), (1, 6)))


class _FakeWorld:
    """Every vnum the tables name, as an object of level 1."""

    def __init__(self) -> None:
        class Obj:
            short_desc = "a thing"
            level = 1

        vnums = set(gear_drops.GANON_LOOT) | set(gear_drops.CLEAR_REWARD_GEAR) \
            | set(gear_drops.BM_BOSS_DROPS) | set(gear_drops.BM_CAKES) \
            | set(gear_drops.BM_CHARMS) | set(gear_drops.HOLIDAY_TREATS)
        for level in range(1, 10):
            vnums |= set(gear_drops.boss_drop_vnums(level))
        for _h, _s, _e, table in gear_drops.EVENT_BOSSES.values():
            vnums |= {row[0] for row in table}
        self.objects = {v: Obj() for v in vnums}
        self.mobiles = {}
        self.rooms = {}


@unittest.skipIf(WEBADMIN_UNAVAILABLE_REASON is not None, WEBADMIN_UNAVAILABLE_REASON or "")
class FinderAndOracleTests(unittest.TestCase):
    """The real world, asked through the dashboard."""

    @classmethod
    def setUpClass(cls) -> None:
        from webadmin import server

        cls.server = server
        cls.saved = server.parser
        server.parser = server.load_area_parser(server.AREA_PATH)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.parser = cls.saved

    def find(self, level: int, day: datetime.date, class_name: str = "warrior") -> dict:
        with patch.object(self.server, "_gear_today", lambda: day):
            return asyncio.run(self.server.get_best_gear(
                class_name=class_name, race_name="human", level=level, limit=50))

    @staticmethod
    def by_vnum(result: dict) -> dict:
        return {item["vnum"]: item for items in result.values() for item in items}

    def test_a_level_25_warrior_finds_aquamentus_coat_and_helm(self) -> None:
        found = self.by_vnum(self.find(25, datetime.date(2026, 11, 10)))
        for vnum in (30650, 30651):
            with self.subTest(vnum=vnum):
                self.assertIn(vnum, found)
                item = found[vnum]
                self.assertEqual(item["level"], 8)
                self.assertIn("dropped by Aquamentus", item["source"])
                self.assertIn("Level 1: Hall of Threefold Scorches", item["source"])
                self.assertIn("3 of its 11 pieces fall each kill (27%)", item["source"])
                drop = item["drop_sources"][0]
                self.assertEqual(drop["kind"], "hyrule_guardian")
                self.assertEqual(drop["mob_vnum"], 30222)
                self.assertEqual(drop["room"], 30413)
                self.assertAlmostEqual(drop["chance"], 0.2727)
                self.assertEqual(drop["level"], 8)
                # Level 1 asks for nothing: its entrance is open and its
                # guardian's chamber has no gate.
                self.assertEqual(drop["requires"], [])
                self.assertIsNone(drop["seasonal"])
        # A later guardian's table says what the way there needs.
        dodongo = found[30657]
        self.assertIn("the first Triforce shard (from Level 1: The Eagle's chest) "
                      "to enter Level 2: The Moon", dodongo["drop_sources"][0]["requires"])
        self.assertIn("a small boomerang or the Magical Boomerang (found in Level 1: "
                      "The Eagle) to reach The Dodongo's chamber", dodongo["source"])

    def test_ganons_relics_say_the_silver_arrow_finishes_him(self) -> None:
        found = self.by_vnum(self.find(59, datetime.date(2026, 11, 10)))
        tunic = found[30577]
        self.assertIn("one of his 3 relics falls each kill (33%)", tunic["source"])
        self.assertIn("a silver arrow (found in Level 9: Death Mountain) to finish him",
                      tunic["source"])
        self.assertIn("the Magical Key (found in Level 8: The Lion) to reach Ganon's chamber",
                      tunic["drop_sources"][0]["requires"])

    def test_gear_above_the_level_is_not_offered(self) -> None:
        found = self.by_vnum(self.find(7, datetime.date(2026, 11, 10)))
        self.assertNotIn(30650, found)        # a level 8 coat

    def test_a_holiday_bosses_drops_only_in_its_holiday(self) -> None:
        october = self.by_vnum(self.find(50, datetime.date(2026, 10, 20)))
        reaper = october[29920]
        self.assertEqual(reaper["drop_sources"][0]["kind"], "event_boss")
        self.assertIn("Hallows End only (Oct 18 - Nov 1)", reaper["source"])
        self.assertIn("dropped by the Headless Horseman, Center of Oak Tree Square: 50% a kill",
                      reaper["source"])
        self.assertNotIn(29922, october)      # Father Winter's, not his
        august = self.by_vnum(self.find(50, datetime.date(2026, 8, 15)))
        self.assertNotIn(29920, august)
        # Valhalla's clovers belong to no holiday: the rarities are always
        # about, so they are listed all year, with the odds.
        clover = august[9944]
        self.assertIn("sold by Vesh the Smuggler", clover["source"])
        self.assertIn("in 15% of his stocks", clover["source"])
        self.assertEqual({s["kind"] for s in clover["drop_sources"]},
                         {"black_market", "treasure_goblin", "black_dragon"})

    def test_reset_gear_keeps_its_reset_source(self) -> None:
        found = self.by_vnum(self.find(8, datetime.date(2026, 11, 10)))
        guard = found[30339]                  # the Heart Guard, a G reset on Aquamentus
        self.assertNotIn("drop_sources", guard)
        self.assertEqual(guard["source"], "from Aquamentus")

    def test_the_oracle_names_the_guardian_drop_and_its_odds(self) -> None:
        prof = {"class_name": "warrior", "race": "human", "level": 8, "equipment": []}
        server = self.server
        with patch.object(server, "parse_player_file", lambda name: prof), \
                patch.object(server, "_oracle_live_lookup",
                             lambda reqs, asker=None: ["" for _ in reqs]), \
                patch.object(server, "_gear_today", lambda: datetime.date(2026, 11, 10)):
            ctx = server._oracle_context("Zgear", "what is the best body armor I can get?")
            drop = server._oracle_drop_lines(
                "where does the coat of aquamentus scale drop?",
                server.parser.objects, server.parser.mobiles, server.parser.rooms)
        self.assertIn("Body: a coat of Aquamentus scale (lvl 8), dropped by Aquamentus, "
                      "Level 1: Hall of Threefold Scorches (27% a kill)", ctx)
        self.assertIn("Asked about the body slot: the best this supplicant can get at "
                      "level 8 is a coat of Aquamentus scale (lvl 8), dropped by Aquamentus, "
                      "Level 1: Hall of Threefold Scorches: 3 of its 11 pieces fall each "
                      "kill (27%)", ctx)
        self.assertIn("falls by chance", ctx)
        self.assertNotIn("Seasonal Items", ctx)
        self.assertEqual(len(drop), 1)
        self.assertIn("dropped by Aquamentus", drop[0])
        self.assertNotIn("nothing in the world loads it", drop[0])

    def test_the_oracle_gives_a_holiday_piece_its_dates(self) -> None:
        server = self.server
        with patch.object(server, "_gear_today", lambda: datetime.date(2026, 8, 15)):
            drop = server._oracle_drop_lines(
                "where does the horseman's reaper drop?",
                server.parser.objects, server.parser.mobiles, server.parser.rooms)
        self.assertEqual(len(drop), 1)
        self.assertIn("Hallows End only (Oct 18 - Nov 1)", drop[0])
        self.assertIn("treasure goblin", drop[0])


if __name__ == "__main__":
    unittest.main()

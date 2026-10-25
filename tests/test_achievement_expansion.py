"""The 2026-10-25 achievement expansion, REDEEM, and the crafting rebuild.

What has to stay true:

- 175 new achievements, 378 in all, every key unique and every one of
  them reachable from a hook that fires at the successful event.
- The five original metas count the lists they counted on 2026-10-24.
  Adding a boss, a relic, a crafting feat or a death must never change
  what "every listed world boss" asks of somebody.
- Counters and sets are saved by name, survive a reload and a remort,
  and a file from before the expansion loads with them at zero.
- Hidden achievements stay hidden, search included, and the full list is
  cut into parts the pager can hold, with colour on or off.
- Marks are points less what REDEEM spent; spending never lowers points.
- BREW, CONCOCT and SCRIBE refuse before they roll, cost nothing on a
  refusal, and count toward the crafting tiers and the recipe book.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zachieve25"
TEMPLE = 4207
ALTAR = 4208

ROW_RE = re.compile(
    r'^\s*\{\s*"(?P<key>[^"]+)",\s*"(?P<title>[^"]+)",\s*"(?P<desc>[^"]+)",\s*'
    r'(?P<cat>ACH_CAT_[A-Z_]+),\s*(?P<points>\d+),\s*(?P<hidden>true|false),\s*'
    r'(?P<req>ACH_REQ_[A-Z_]+),\s*(?P<target>[^,]+),\s*(?P<aux>[^}]+?)\s*\},?\s*$',
    re.MULTILINE,
)

FROZEN = {
    "cohort_world_bosses_v1": [
        "boss-tarrasque", "boss-borg", "boss-korzath", "boss-master-guardian",
        "boss-white-light", "boss-smaug", "boss-minotaur-god", "boss-zeus",
        "boss-odin", "boss-ra", "boss-dagahze", "boss-lolth",
        "boss-eilistraee", "boss-dracolich", "boss-ashen-herald",
        "boss-lord-british", "boss-lanatir"],
    "cohort_rare_items_v1": [
        "relic-power-of-world", "relic-lifetaker", "relic-starlight-sword",
        "relic-minotaur-claws", "relic-aegis", "relic-thunder-bolt",
        "relic-amulet-of-ra", "relic-sword-of-sun", "relic-elfbane",
        "relic-lanatir-sphere", "relic-hammer-of-wrath", "relic-angels-heart",
        "relic-british-crown", "relic-british-sceptre", "relic-british-amulet",
        "relic-farslayer", "relic-farslay-scroll"],
    "cohort_crafting_v1": [
        "first-brew", "first-concoction", "first-scroll", "scribe-farslay-scroll"],
    "cohort_misadventures_v1": [
        "death-by-deathtrap", "death-by-puzzle-trap", "death-by-item",
        "death-by-farslay", "death-by-farslay-backfire", "death-by-death-ray"],
    "cohort_hyrule_bosses_v1": [
        "hyrule-eagle", "hyrule-moon", "hyrule-manji", "hyrule-snake",
        "hyrule-lizard", "hyrule-dragon", "hyrule-demon", "hyrule-lion",
        "hyrule-death-mountain"],
}


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


def cohort(text: str, name: str) -> list[str]:
    body = text[text.index("static const char *const %s[] =" % name):]
    body = body[:body.index("};")]
    return re.findall(r'"([a-z0-9-]+)"', body)


def run(client, command: str, settle: float = 1.4) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.drain(1.0)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError("character did not leave the world")
    if fields:
        patch_player_file(mud, name, **fields)


def add_lines(mud: LiveMud, name: str, objects=(), player_lines=()) -> None:
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    if player_lines:
        at = text.index("\nEnd\n")
        text = text[:at] + "\n" + "\n".join(player_lines) + text[at:]
    text = text.replace("#END", "".join(objects) + "#END", 1)
    path.write_text(text, encoding="latin-1")


def obj(vnum: int, level: int = 1) -> str:
    return "#O\nVnum %d\nNest 0\nWear -1\nLev %d\nCond 100\nEnd\n\n" % (vnum, level)


def kill_at_one_hit_point(staff, hero, boss_room: int) -> bool:
    """The hero kills Aquamentus at one hit point. Before every swing the
    staff character steps in, sets whichever guardian stands first in the
    room -- the one the hero's KILL picks -- to one hit point and steps out
    again: staff in the room spoil a Fair Fight, and a reset can put a
    second, unhurt guardian in front of the first (CI, 2026-10-25, where
    the hero was still fighting at QUIT)."""
    for _ in range(5):
        run(staff, "goto %d" % boss_room, 1.0)
        run(staff, "set char aquamentus hp 1", 1.0)
        run(staff, "restore aquamentus", 1.0)
        run(staff, "goto %d" % TEMPLE, 1.0)
        out = run(hero, "kill aquamentus", 4.0)
        if "is DEAD" in out:
            return True
        if "They aren't here" in out:
            return "is DEAD" in hero.transcript
    return False


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ach = source("achievements.c")
        table = cls.ach[cls.ach.index("achievement_table[] ="):]
        cls.table = table[:table.index("\n};\n")]
        cls.rows = [m.groupdict() for m in ROW_RE.finditer(cls.table)]
        cls.keys = [r["key"] for r in cls.rows]
        cls.new = cls.rows[203:]
        cls.everything = "".join(
            p.read_text(encoding="latin-1") for p in (ROOT / "src").glob("*.c")
            if p.name != "achievements.c")

    def test_counts_capacity_and_keys(self) -> None:
        self.assertEqual(len(self.rows), 378)
        self.assertEqual(len(self.new), 175)
        self.assertEqual(len(self.keys), len(set(self.keys)))
        merc = source("merc.h")
        self.assertGreaterEqual(int(re.search(r"#define MAX_ACHIEVEMENTS\s+(\d+)", merc).group(1)), 512)
        self.assertIn("achievement_table_must_fit", self.ach)
        # Every old key, in the order it was, first: an earned set is
        # saved by key, so nothing about old rows may move.
        self.assertEqual(self.keys[0], "level-5")
        self.assertEqual(self.keys[202], "benchmark-champion")

    def test_the_guide_lists_every_new_achievement(self) -> None:
        guide = (ROOT / "wiki" / "achievements.md").read_text(encoding="utf-8")
        catalog = guide[guide.index("### Catalog"):guide.index("### Deferred candidates")]
        listed = re.findall(r"^\| `([a-z0-9-]+)` \|", catalog, re.MULTILINE)
        self.assertEqual(listed, [r["key"] for r in self.new])
        self.assertIn("**378**", guide)
        self.assertNotIn("uses 196", guide)

    def test_new_points_are_cosmetic_and_in_their_bands(self) -> None:
        for row in self.new:
            with self.subTest(key=row["key"]):
                points = int(row["points"])
                self.assertGreaterEqual(points, 5)
                self.assertLessEqual(points, 100)
                if row["req"] == "ACH_REQ_COHORT" and points >= 75:
                    continue
                self.assertLessEqual(points, 60)

    def test_original_metas_count_frozen_lists(self) -> None:
        for name, keys in FROZEN.items():
            with self.subTest(cohort=name):
                self.assertEqual(cohort(self.ach, name), keys)
        progress = self.ach[self.ach.index("static long achievement_progress("):]
        for req, co in (("ACH_REQ_WORLD_BOSSES", "ACH_COHORT_WORLD_BOSSES_V1"),
                        ("ACH_REQ_RARE_ITEMS", "ACH_COHORT_RARE_ITEMS_V1"),
                        ("ACH_REQ_CRAFTING_FEATS", "ACH_COHORT_CRAFTING_V1"),
                        ("ACH_REQ_MISADVENTURES", "ACH_COHORT_MISADVENTURES_V1"),
                        ("ACH_REQ_HYRULE_BOSSES", "ACH_COHORT_HYRULE_BOSSES_V1")):
            case = progress[progress.index("case %s:" % req):]
            self.assertIn(co, case[:200], req)

    def test_every_cohort_names_real_keys(self) -> None:
        names = re.findall(r"static const char \*const (cohort_\w+)\[\]", self.ach)
        self.assertEqual(len(names), 18)
        for name in names:
            for key in cohort(self.ach, name):
                with self.subTest(cohort=name, key=key):
                    self.assertIn(key, self.keys)

    def test_every_new_event_and_counter_has_a_hook(self) -> None:
        merc = source("merc.h")
        events = set(re.findall(r"(ACHIEVEMENT_EVENT_[A-Z_]+)", " ".join(r["target"] for r in self.new)))
        hooks = self.everything + self.ach.replace(self.table, "")
        self.assertGreater(len(events), 30)
        for event in sorted(events):
            with self.subTest(event=event):
                self.assertTrue(event in hooks, event + " is never raised")
        craft = source("magic2.c")
        craft = craft[craft.index("static void craft_succeeded("):]
        craft = craft[:craft.index("\n}\n")]
        self.assertIn("achievement_count( ch, counter, 1 )", craft)
        for counter in re.findall(r"ACH_CTR_[A-Z_]+", merc):
            if counter == "ACH_CTR_COUNT":
                continue
            if counter in ("ACH_CTR_BREWS", "ACH_CTR_CONCOCTIONS", "ACH_CTR_SCROLLS"):
                self.assertIn(counter, craft)
                continue
            with self.subTest(counter=counter):
                self.assertTrue(re.search(r"achievement_(party_)?count\([^;]*%s" % counter,
                                          self.everything + self.ach), counter + " is never counted")
        for event_range in ("ACHIEVEMENT_EVENT_DISASTER_FIRST + type",
                            "ACHIEVEMENT_EVENT_HYRULE_CHEST_FIRST + dungeon",
                            "ACHIEVEMENT_EVENT_HYRULE_BAND_FIRST + dungeon"):
            self.assertIn(event_range, self.everything + self.ach)

    def test_staff_actions_earn_nothing_new(self) -> None:
        self.assertIn("#define ACH_STAFF(ch) IS_TRUSTED((ch), LEVEL_IMMORTAL)", self.ach)
        party = self.ach[self.ach.index("static bool achievement_party_member("):]
        self.assertIn("!ACH_STAFF(member)", party[:300])
        special = source("special.c")
        mercy = special[special.index("herbie_visit( mob, most_hurt );"):]
        self.assertIn("ACHIEVEMENT_EVENT_WINGS_OF_MERCY", mercy[:300])
        wiz = source("act_wiz.c")
        self.assertNotIn("WINGS_OF_MERCY", wiz)

    def test_hidden_rows_never_match_a_search(self) -> None:
        # A visible meta must not name its hidden members either.
        hidden_words = ("goriya", "armos", "bush", "lake", "digdogger", "rod's fire",
                        "pols voice", "hint", "passenger", "portal")
        for row in self.rows:
            if row["hidden"] == "true":
                continue
            for word in hidden_words:
                if row["key"].startswith("hyrule-") and row["req"] != "ACH_REQ_COHORT":
                    continue
                with self.subTest(key=row["key"], word=word):
                    self.assertIsNone(re.search(r"\b%s\b" % re.escape(word), row["desc"].lower()))
        match = self.ach[self.ach.index("static bool achievement_matches_search("):]
        match = match[:match.index("\n}\n")]
        self.assertIn("definition->hidden && ch->pcdata->achievement_earned[index] == 0", match)

    def test_list_views_are_cut_into_parts_the_pager_holds(self) -> None:
        self.assertRegex(self.ach, r"#define ACHIEVEMENT_PART_BYTES (\d+)")
        size = int(re.search(r"#define ACHIEVEMENT_PART_BYTES (\d+)", self.ach).group(1))
        # Colour tokens convert to escapes up to about twice as long; the
        # pager block holds 32,000.
        self.assertLess(size * 2 + 4096, 32000)

    def test_remort_leaves_the_achievement_record_alone(self) -> None:
        info = source("act_info.c")
        remort = info[info.index("void do_remort("):]
        remort = remort[:remort.index("\n}\n")]
        for field in ("achievement_counter", "achievement_set", "achievement_earned",
                      "achievement_marks_spent"):
            self.assertNotIn(field, remort)

    def test_fair_fight_counts_everyone_present(self) -> None:
        fair = self.ach[self.ach.index("static void achievement_hyrule_fair_fight("):]
        fair = fair[:fair.index("\n}\n")]
        self.assertIn("ACH_STAFF(member) || member->level > hyrule_band_ceiling[dungeon]", fair)
        self.assertIn("IS_AFFECTED(member, AFF_CHARM)", fair)
        self.assertIn("{ 8, 14, 20, 27, 33, 40, 46, 52, 59 }", self.ach)


class CraftingTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.magic2 = source("magic2.c")
        cls.const = source("const.c")
        table = cls.magic2[cls.magic2.index("static const CRAFT_RECIPE craft_recipes[] ="):]
        table = table[:table.index("\n};\n")]
        cls.recipes = re.findall(
            r"\{ CRAFT_(BREW|CONCOCT|SCRIBE), \{ (\d+), (\d+), (\d+) \}, "
            r"\{ ([^}]*) \}, \"([^\"]+)\", \"([^\"]+)\"", table)

    def test_recipe_counts_and_unique_ingredients(self) -> None:
        kinds = [r[0] for r in self.recipes]
        self.assertEqual(kinds.count("BREW"), 20)
        self.assertEqual(kinds.count("CONCOCT"), 20)
        self.assertEqual(kinds.count("SCRIBE"), 12)
        seen = set()
        for method, a, b, c, *_ in self.recipes:
            parts = (method, tuple(sorted(int(x) for x in (a, b, c) if x != "0")))
            self.assertNotIn(parts, seen)
            seen.add(parts)
        used = {int(x) for r in self.recipes for x in r[1:4]}
        for component in (57, 82, 85, 86):
            self.assertIn(component, used, "component %d still unused" % component)

    def test_every_spell_is_real_and_the_signature_is_one_of_them(self) -> None:
        for method, a, b, c, spells, colour, signature in self.recipes:
            names = re.findall(r'"([^"]+)"', spells)
            with self.subTest(colour=colour):
                self.assertIn(signature, names)
                for name in names:
                    entry = re.search(r'\{\s*\n\s*"%s",\s*\n[^\n]*\n\s*(spell_\w+)' % re.escape(name), self.const)
                    self.assertIsNotNone(entry, name)
                    self.assertNotEqual(entry.group(1), "spell_null", name)
        # A Varied Recipe Book III wants twenty distinct identities.
        identities = {(r[0], r[6]) for r in self.recipes}
        self.assertGreaterEqual(len(identities), 30)

    def test_refusals_cost_nothing_and_lag_comes_first(self) -> None:
        for fn, nxt in (("void do_brew", "void do_concoct"), ("void do_concoct", "void do_scribe"),
                        ("void do_scribe", "void spell_vengence")):
            body = self.magic2[self.magic2.index(fn):self.magic2.index(nxt)]
            with self.subTest(fn=fn):
                self.assertLess(body.index("craft_find("), body.index("WAIT_STATE("))
                self.assertLess(body.index("WAIT_STATE("), body.index("number_percent()"))
                self.assertNotIn("extract_obj", body[:body.index("WAIT_STATE(")])
        for name in ("herbal brewing", "concoct", "scribe"):
            entry = re.search(r'"%s",\s*\n[^\n]*\n[^\n]*\n\s*&gsn_\w+,\s*SLOT\(\s*\d+\),\s*\d+,\s*(\d+)' % name, self.const)
            self.assertGreater(int(entry.group(1)), 0, name)

    def test_component_ceiling_counts_components_only(self) -> None:
        update = source("update.c")
        count = update[update.index("count_components"):]
        self.assertIn("pObjIndex->item_type == ITEM_SPELL_COMPONENT", count[:1200])
        self.assertIn("component_scatter_room(", update)
        interp = source("interp.c")
        self.assertRegex(interp, r'"scribe",\s*do_scribe,\s*POS_RESTING')
        act_obj = source("act_obj.c")
        self.assertIn("skill_table[sn].target == TAR_OBJ_INV", act_obj)


@unittest.skipIf(SKIP is not None, SKIP or "")
class LiveTests(unittest.TestCase):
    def test_old_saves_metas_marks_paging_and_persistence(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zoldhand", Levl=54, Room=TEMPLE, Cla=0, Attr="25 25 25 25 25")
            # An old file: five of the new bosses already earned, and an
            # old achievement whose date must survive untouched.
            add_lines(mud, "Zoldhand", [obj(54), obj(70), obj(63), obj(70), obj(63)], [
                "Achv first-kill 1600000000",
                "Achv boss-blaine 1700000000",
                "Achv boss-roland 1700000000",
                "Achv boss-archangel 1700000000",
                "Achv boss-moon-guardian 1700000000",
                "Achv boss-starfire 1700000000",
                "Sk 100 'concoct'",
            ])
            with mud.connect(timeout=120) as client:
                login(client, "Zoldhand", PW)
                run(client, "scroll 0")
                summary = run(client, "achievements", 2.0)
                points = int(re.search(r"Points: (\d+)", summary).group(1))
                marks = int(re.search(r"Marks to spend: (\d+)", summary).group(1))
                self.assertEqual(points, marks, summary)
                encounters = run(client, "achievements encounters", 2.0)
                self.assertIn("All Things Serve the Beam", encounters)
                # Five new bosses are not five listed world bosses: Boss
                # Hunter still reads 0 of 5 (and the file says so below).
                self.assertRegex(encounters, r"Defeat five listed world bosses\. \(0/5\)")

                # A hidden one is found by no search.
                self.assertIn("No achievements match", run(client, "achievements goriya", 1.5))

                # A combination that makes nothing costs nothing and takes
                # no roll.
                refused = run(client, "concoct newt tooth", 1.5)
                self.assertIn("won't do anything", refused)
                self.assertIn("eye of newt", run(client, "inventory", 1.2))
                made = ""
                for _ in range(2):
                    made = run(client, "concoct feather tooth", 4.5)
                    if "feathered gold" in made:
                        break
                self.assertIn("feathered gold potion", made, made)

                # The full list, colour off and paging on, in parts.
                run(client, "color off", 1.0)
                run(client, "scroll 30", 1.0)
                titles = set()
                mark = len(client.transcript)
                client.send("achievements all")
                client.drain(2.0)
                self.assertIn("[Hit Return to continue]", client.transcript[mark:])
                for _ in range(40):
                    if "part 1 of" in client.transcript[mark:]:
                        break
                    client.send("")
                    client.drain(0.8)
                paged = client.transcript[mark:]
                total = int(re.search(r"part 1 of (\d+)", paged).group(1))
                self.assertGreaterEqual(total, 2)
                run(client, "scroll 0", 1.0)
                for part in range(1, total + 1):
                    out = run(client, "achievements all %d" % part, 2.0)
                    self.assertNotIn("\x1b[", out)
                    titles.update(re.findall(r"\] (.+?)  \d+ points", out))
                self.assertIn("That view has only", run(client, "achievements all %d" % (total + 1), 1.5))

                # REDEEM: a trophy for an earned achievement. Read the
                # balance again first: the concoction earned points.
                before = run(client, "achievements", 2.0)
                points = int(re.search(r"Points: (\d+)", before).group(1))
                marks = int(re.search(r"Marks to spend: (\d+)", before).group(1))
                listing = run(client, "redeem", 1.5)
                self.assertIn("REDEEM TROPHY", listing)
                trophy = run(client, "redeem trophy first blood", 1.5)
                self.assertIn("trophy for 'First Blood'", trophy)
                after = run(client, "achievements", 2.0)
                self.assertEqual(int(re.search(r"Points: (\d+)", after).group(1)), points)
                self.assertEqual(int(re.search(r"Marks to spend: (\d+)", after).group(1)), marks - 25)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            text = (mud.player_dir / "Zoldhand").read_text(encoding="latin-1")
            self.assertIn("Achv first-kill 1600000000", text)
            self.assertNotIn("Achv five-world-bosses", text)
            self.assertIn("AchSpent 25 0", text)
            self.assertRegex(text, r"AchCount concoctions [1-9]")
            self.assertRegex(text, r"AchSet recipes 2\d{5} ~")
            self.assertIn("Achv first-concoction", text)

            # A remort keeps all of it.
            with mud.connect(timeout=120) as client:
                login(client, "Zoldhand", PW)
                run(client, "scroll 0")
                run(client, "remort %s cleric none human" % PW, 4.0)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            again = (mud.player_dir / "Zoldhand").read_text(encoding="latin-1")
            self.assertIn("Achv first-kill 1600000000", again)
            self.assertIn("AchSpent 25 0", again)
            self.assertRegex(again, r"AchCount concoctions [1-9]")
            self.assertRegex(again, r"AchSet recipes 2\d{5} ~")

    def test_walking_and_the_stash_are_recorded(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zwanderer", Levl=20, Room=TEMPLE)
            add_lines(mud, "Zwanderer", [obj(3701)])
            with mud.connect(timeout=120) as client:
                login(client, "Zwanderer", PW)
                run(client, "scroll 0")
                for step in ("south", "south", "north", "north", "west"):
                    run(client, step, 1.0)
                self.assertIn("safe keeping", run(client, "stash put dagger", 1.5))
                self.assertIn("out of your stash", run(client, "stash get dagger", 1.5))
                client.send("quit")
                self.assertTrue(client.wait_closed())
            text = (mud.player_dir / "Zwanderer").read_text(encoding="latin-1")
            self.assertRegex(text, r"AchSet rooms [\d -]+~")
            self.assertRegex(text, r"AchSet areas \d+")
            self.assertIn("Achv stash-deposit", text)
            self.assertIn("Achv stash-withdraw", text)

    def test_a_fair_fight_is_spoiled_by_anyone_above_the_band(self) -> None:
        boss_room = 30413
        with LiveMud() as mud:
            make(mud, "Zstaffach", Levl=70, Room=boss_room)
            make(mud, "Zfairhero", Levl=8, Room=boss_room, AfBy=512,
                 HMV="3000 3000 100 100 100 100", HMVP="3000 100 100", Hit=60, Dam=60)  # infravision: the hall is dark
            make(mud, "Zbighero", Levl=30, Room=TEMPLE)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zstaffach", PW)
                login(hero, "Zfairhero", PW)
                run(staff, "scroll 0")
                run(hero, "scroll 0")
                # The guardian's own reset has him here already.
                fell = kill_at_one_hit_point(staff, hero, boss_room)
                self.assertTrue(fell, "Zfairhero never killed the guardian")
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
                text = (mud.player_dir / "Zfairhero").read_text(encoding="latin-1")
                self.assertIn("Achv hyrule-eagle", text)
                self.assertIn("Achv hyrule-band-1", text)

            patch_player_file(mud, "Zbighero", Room=boss_room)
            make(mud, "Zfairtwo", Levl=8, Room=boss_room, AfBy=512,
                 HMV="3000 3000 100 100 100 100", HMVP="3000 100 100", Hit=60, Dam=60)
            with mud.connect(timeout=120) as staff, \
                    mud.connect(timeout=120) as hero, \
                    mud.connect(timeout=120) as big:
                login(staff, "Zstaffach", PW)
                login(big, "Zbighero", PW)
                login(hero, "Zfairtwo", PW)
                run(staff, "goto %d" % boss_room, 1.2)
                if "Aquamentus" not in run(staff, "look", 1.2):
                    run(staff, "load mob 30222", 1.2)
                fell = kill_at_one_hit_point(staff, hero, boss_room)
                self.assertTrue(fell, "Zfairtwo never killed the guardian")
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
            text = (mud.player_dir / "Zfairtwo").read_text(encoding="latin-1")
            self.assertIn("Achv hyrule-eagle", text)
            self.assertNotIn("Achv hyrule-band-1", text)

    def test_a_wimpy_boss_counts_anywhere_in_his_palace(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zstaffpal", Levl=70, Room=10000)
            with mud.connect(timeout=120) as staff:
                login(staff, "Zstaffpal", PW)
                run(staff, "scroll 0")
                run(staff, "load mob 10000", 1.2)
                run(staff, "slay augustus", 2.0)
                staff.send("quit")
                self.assertTrue(staff.wait_closed())
            text = (mud.player_dir / "Zstaffpal").read_text(encoding="latin-1")
            self.assertIn("Achv boss-starfire", text)


if __name__ == "__main__":
    unittest.main()

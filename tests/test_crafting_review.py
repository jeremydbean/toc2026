"""SCRIBE, CONCOCT, BREW and RECITE after the crafting review (2026-10-27).

Five findings, each played here against a disposable world with Z fixtures:

- RECITE read a scroll at itself ("recite blank blank"): the remove-align
  scroll's explosion extracted the scroll it was reading, then RECITE
  extracted it again. A scroll is never its own target, and a spell that
  works on an object works on one the reader carries -- both refused before
  any lag, roll or reading.
- The ironbound scroll cast stone skin and shield before a major globe,
  which forms around no other protective magic: the globe, its signature,
  never landed. It is giant strength, bless and the globe now.
- A craft ignored its save. The ingredients out and the product in are on
  the disk or undone: a save that failed puts memory back to match the
  file; one the disk has not confirmed keeps the new state and says so.
- Staff heard a wizinvis scriber's name at LEVEL_IMMORTAL.
- A CONCOCT blast that killed left the ingredients it had spent in the
  corpse.

And what came with them: PREVIEW (free, read-only), product keywords and a
ground line, an audit row per attempt in log/play.tsv, and a refusal for
ingredients named past what a craft takes.
"""
from __future__ import annotations

import os
import re
import signal
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zcraftpw1"
TEMPLE = 4207
HALLS = 4202            # not safe: a blast may land
FEATHER, TOOTH = 63, 70  # feathered gold: fly and haste
TARRASQUE, CUBE, OOZE = 85, 86, 87      # ironbound
WING, SALIVA, BLOOD = 80, 84, 76        # blank: remove align
DAGGER = 3701


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def add(mud: LiveMud, name: str, objects: str = "", skills=()) -> None:
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    if skills:
        end = text.index("\nEnd\n")
        text = text[:end] + "".join(f"\nSk 100 '{s}'" for s in skills) + text[end:]
    path.write_text(text.replace("#END", objects + "#END", 1), encoding="latin-1")


def obj(vnum: int, extra: str = "") -> str:
    return "#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 100\n%sEnd\n\n" % (vnum, extra)


def low_skill(mud: LiveMud, name: str, skill: str, percent: int) -> None:
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    path.write_text(text.replace(f"Sk 100 '{skill}'", f"Sk {percent} '{skill}'"),
                    encoding="latin-1")


def file_vnums(mud: LiveMud, name: str) -> list:
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    return [int(v) for v in re.findall(r"^Vnum (\d+)$", text, re.M)]


def craft_rows(mud: LiveMud) -> list:
    path = mud.root / "log" / "play.tsv"
    if not path.exists():
        return []
    rows = [line.split("\t") for line in path.read_text(encoding="latin-1").splitlines()]
    return [r for r in rows if len(r) > 1 and r[1] == "craft"]


def fault(mud: LiveMud, point: str) -> None:
    (mud.root / "fault.once").write_text(point + "\n")


def crash(mud: LiveMud) -> None:
    os.kill(mud.proc.pid, signal.SIGKILL)
    mud.proc.wait(timeout=15)
    mud.restart()


def until(client, command: str, *wanted: str, tries: int = 3) -> str:
    """Repeat a craft until its reply holds one of `wanted` (the roll is
    real); the fixture carries an ingredient set per try."""
    out = ""
    for _ in range(tries):
        out = client.sync(command, timeout=30)
        if any(w in out for w in wanted):
            return out
    return out


class CraftingSourceTests(unittest.TestCase):
    """The recipe table checked against the game's own skill table."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.magic2 = source("magic2.c")
        const = source("const.c")
        table = cls.magic2[cls.magic2.index("static const CRAFT_RECIPE craft_recipes[] ="):]
        table = table[:table.index("\n};\n")]
        cls.recipes = re.findall(
            r"\{ CRAFT_(BREW|CONCOCT|SCRIBE), \{ (\d+), (\d+), (\d+) \}, "
            r"\{ ([^}]*) \}, \"([^\"]+)\", \"([^\"]+)\"", table)
        # name -> (spell_fun, target), from every skill_table row.
        cls.skills = {}
        for m in re.finditer(r'\{\s*\n\s*"([^"]+)",\s*\n[^\n]*\n\s*(spell_\w+),\s*(TAR_\w+)', const):
            cls.skills.setdefault(m.group(1), (m.group(2), m.group(3)))
        limbo = (ROOT / "area" / "limbo.are").read_text(encoding="latin-1")
        cls.limbo_vnums = {int(v) for v in re.findall(r"^#(\d+)\s*$", limbo, re.M)}

    def test_every_spell_is_named_exactly_and_casts(self) -> None:
        self.assertIn("    return 0;\n}", self.magic2[self.magic2.index("static int craft_spell("):])
        for method, a, b, c, spells, colour, signature in self.recipes:
            for name in re.findall(r'"([^"]+)"', spells):
                with self.subTest(recipe=colour, spell=name):
                    self.assertIn(name, self.skills, "not an exact skill name")
                    self.assertNotEqual(self.skills[name][0], "spell_null")

    def test_targets_suit_how_the_product_is_used(self) -> None:
        for method, a, b, c, spells, colour, signature in self.recipes:
            targets = {self.skills[n][1] for n in re.findall(r'"([^"]+)"', spells)}
            with self.subTest(recipe=colour):
                if method in ("BREW", "CONCOCT"):
                    # Quaffed: there is no object to aim at, and no foe.
                    self.assertNotIn("TAR_OBJ_INV", targets)
                    self.assertNotIn("TAR_CHAR_OFFENSIVE", targets)
                elif "TAR_OBJ_INV" in targets:
                    # A scroll read at an object casts every slot at it.
                    self.assertEqual(targets, {"TAR_OBJ_INV"})

    def test_no_recipe_casts_spells_that_refuse_each_other(self) -> None:
        # From the spells' own refusals (magic.c, magic2.c): a major globe
        # forms around no shroud, armor, shield or stone skin, and armor,
        # shield and shroud refuse a globe; frenzy refuses calm; haste and
        # slow refuse each other.
        exclusive = [({"major globe"}, {"shroud", "armor", "shield", "stone skin"}),
                     ({"frenzy"}, {"calm"}), ({"haste"}, {"slow"})]
        for method, a, b, c, spells, colour, signature in self.recipes:
            names = set(re.findall(r'"([^"]+)"', spells))
            for left, right in exclusive:
                with self.subTest(recipe=colour):
                    self.assertFalse(names & left and names & right, names)

    def test_ingredients_and_products_exist(self) -> None:
        for method, a, b, c, *_ in self.recipes:
            for vnum in (int(a), int(b), int(c)):
                if vnum:
                    self.assertIn(vnum, self.limbo_vnums)
        for product in (74, 75, 90):
            self.assertIn(product, self.limbo_vnums)

    def test_ironbound_keeps_its_globe_and_its_signature(self) -> None:
        row = [r for r in self.recipes if r[5] == "ironbound"]
        self.assertEqual(len(row), 1)
        self.assertEqual(row[0][6], "major globe")
        self.assertIn('"major globe"', row[0][4])

    def test_the_order_of_things(self) -> None:
        act_obj = source("act_obj.c")
        recite = act_obj[act_obj.index("void do_recite("):]
        recite = recite[:recite.index("\n}\n")]
        self.assertLess(recite.index("obj == scroll"), recite.index("WAIT_STATE("))
        self.assertLess(recite.index("obj->carried_by != ch"), recite.index("WAIT_STATE("))
        concoct = self.magic2[self.magic2.index("void do_concoct("):]
        concoct = concoct[:concoct.index("\n}\n")]
        self.assertLess(concoct.index("craft_commit("), concoct.index("damage( ch, ch"))
        succeeded = self.magic2[self.magic2.index("static void craft_succeeded("):]
        self.assertIn("staff_notice_level( ch, LEVEL_IMMORTAL )", succeeded[:2500])
        self.assertNotIn("wizinfo( buf, LEVEL_IMMORTAL )", self.magic2)


@unittest.skipIf(SKIP is not None, SKIP or "")
class CraftingLiveTests(unittest.TestCase):
    def test_recite_never_reads_a_scroll_at_itself_or_the_floor(self) -> None:
        blank = obj(90, "Name blank scroll~\nShD a blank scroll~\nVal 30 0 0 0 0\n"
                        "Spell 1 'remove align'\n")
        with LiveMud() as mud:
            # Not the Temple: what is dropped there does not stay on the floor.
            make(mud, "Zreader", Levl=30, Cla=0, Room=HALLS)
            add(mud, "Zreader", blank + obj(DAGGER) + obj(54), skills=("scrolls",))
            with mud.connect(timeout=120) as client:
                login(client, "Zreader", PW)
                client.sync("scroll 0")
                itself = client.must("recite blank blank", "cannot read")
                self.assertNotIn("You recite", itself)
                # Mud School's dagger burns up when dropped out here; an eye
                # of newt stays where it falls.
                client.must("drop newt", "You drop")
                floor = client.must("recite blank newt", "must be carrying")
                self.assertNotIn("You recite", floor)
                kept = client.sync("inventory")
                self.assertIn("a blank scroll", kept)
                read = until(client, "recite blank dagger", "You recite")
                self.assertIn("You recite", read)
                self.assertNotIn("a blank scroll", client.sync("inventory"))
                # The game is still answering: nothing was freed twice.
                self.assertIn("Zreader", client.sync("score"))

    def test_ironbound_scroll_previewed_made_and_read(self) -> None:
        sets = "".join(obj(v) for v in (TARRASQUE, CUBE, OOZE) * 3)
        with LiveMud() as mud:
            make(mud, "Zscriber", Levl=30, Cla=0, Room=TEMPLE,
                 HMV="300 300 300 300 300 300", HMVP="300 300 300")
            add(mud, "Zscriber", sets, skills=("scribe", "scrolls"))
            with mud.connect(timeout=120) as client:
                login(client, "Zscriber", PW)
                client.sync("scroll 0")
                # PREVIEW costs nothing: no lag, nothing used.
                preview = client.must("scribe preview tarrasque cube ooze", "PREVIEW")
                for words in ("ironbound scroll", "giant strength", "bless", "major globe",
                              "Your chance to make it: 95%", "RECITE works"):
                    self.assertIn(words, preview)
                self.assertNotIn("stone skin", preview)
                self.assertEqual(client.sync("inventory").count("tarrasque"), 1,
                                 "three vials, shown once as (3)")
                self.assertIn("named more",
                              client.sync("scribe tarrasque cube ooze tarrasque"))
                made = until(client, "scribe tarrasque cube ooze", "You finish")
                self.assertIn("You finish an ironbound scroll", made)
                # On the ground it says what it is.
                client.must("drop ironbound", "You drop")
                self.assertIn("An ironbound scroll lies here, freshly scribed.",
                              client.sync("look"))
                client.must("get globe", "You get")        # a new keyword
                # RECITE mispronounces on a roll of 100 even at 100% (CI,
                # 2026-10-28): it says "You recite" either way and keeps the
                # scroll, so read it again until it is not a mispronounce.
                for _ in range(5):
                    read = client.sync("recite globe", timeout=30)
                    if "mispronounce" not in read:
                        break
                self.assertIn("You recite", read)
                self.assertNotIn("mispronounce", read)
                affects = client.sync("affects")
                for spell in ("giant strength", "bless", "major globe"):
                    self.assertIn(spell, affects.lower(), affects)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            rows = [r for r in craft_rows(mud) if r[8] == "major globe"]
            text = (mud.player_dir / "Zscriber").read_text(encoding="latin-1")

        made_rows = [r for r in rows if r[16] == "made"]
        self.assertTrue(made_rows, rows)
        row = made_rows[0]
        self.assertEqual(row[2], "Zscriber")
        self.assertEqual(sorted(row[10].split(",")), sorted(str(v) for v in (TARRASQUE, CUBE, OOZE)))
        self.assertEqual((row[11], row[12], row[13]),
                         ("90", "giant strength,bless,major globe", "30"))
        self.assertEqual((row[15], row[18]), ("95", "saved"))
        self.assertNotIn(str(TEMPLE), "\t".join(row[6:]))
        # The scroll was read; each attempt spent a set, the rest are carried.
        self.assertEqual(text.count("Vnum %d\n" % TARRASQUE), 3 - len(rows))

    def test_old_crafted_items_still_load_answer_and_save(self) -> None:
        old = obj(90, "Name ironbound scroll~\nShD an ironbound scroll~\nVal 30 0 0 0 0\n"
                      "Spell 1 'stone skin'\nSpell 2 'shield'\nSpell 3 'major globe'\n")
        tea = obj(74, "Name blue container~\nShD a blue container of tea~\nVal 20 0 0 0 0\n"
                      "Spell 1 'cure light'\nSpell 2 'refresh'\n")
        with LiveMud() as mud:
            make(mud, "Zkeeper", Levl=30, Cla=0, Room=TEMPLE)
            add(mud, "Zkeeper", old + tea)
            with mud.connect(timeout=120) as client:
                login(client, "Zkeeper", PW)
                client.sync("scroll 0")
                held = client.sync("inventory")
                self.assertIn("an ironbound scroll", held)
                self.assertIn("a blue container of tea", held)
                # The words players typed before still find them.
                self.assertIn("ironbound scroll", client.must("look ironbound", "scroll"))
                client.must("drop blue", "You drop")
                client.must("get blue", "You get")
                client.send("quit")
                self.assertTrue(client.wait_closed())
            text = (mud.player_dir / "Zkeeper").read_text(encoding="latin-1")
        # Nothing rewrote an old product's spells: the old scroll is what it was.
        self.assertIn("Name ironbound scroll~", text)
        self.assertIn("Spell 3 'major globe'", text)
        self.assertIn("Spell 1 'stone skin'", text)
        self.assertIn("Name blue container~", text)

    def test_a_craft_is_on_the_disk_or_undone(self) -> None:
        pairs = "".join(obj(v) for v in (FEATHER, TOOTH) * 2)
        with LiveMud(extra_env={"TOC_FAULT_FILE": "../fault.once"}) as mud:
            make(mud, "Zcrafter", Levl=30, Cla=0, Room=TEMPLE)
            add(mud, "Zcrafter", pairs, skills=("concoct",))
            with mud.connect(timeout=120) as client:
                login(client, "Zcrafter", PW)
                client.sync("scroll 0")
                self.assertIn("named more", client.sync("concoct feather tooth newt"))
                self.assertIn("won't do anything", client.sync("concoct preview feather 2.feather"))
                fault(mud, "craft-save")
                undone = client.sync("concoct feather tooth", timeout=30)
                self.assertRegex(undone, r"could not be saved|could not write your file", undone)
                held = client.sync("inventory")
                self.assertIn("phoenix feather", held)
                self.assertNotIn("feathered gold", held)
            crash(mud)
            after_fail = file_vnums(mud, "Zcrafter")

            with mud.connect(timeout=120) as client:
                login(client, "Zcrafter", PW)
                client.sync("scroll 0")
                fault(mud, "dirsync-Zcrafter")
                mark = len(client.transcript)
                kept = until(client, "concoct feather tooth", "pour off")
                self.assertIn("feathered gold", kept)
                # The roll is 95%: the unconfirmed save may be a spent
                # attempt's before the potion's, so read the whole stretch.
                self.assertIn("has not confirmed it yet", client.transcript[mark:])
            crash(mud)
            after_uncertain = file_vnums(mud, "Zcrafter")
            rows = craft_rows(mud)

        self.assertEqual((after_fail.count(FEATHER), after_fail.count(TOOTH)), (2, 2))
        self.assertNotIn(75, after_fail)
        # Unconfirmed is not undone: the file is the new one, every attempt
        # after the undone one spent a pair.
        later = len(rows) - 1
        self.assertEqual(after_uncertain.count(75), 1, after_uncertain)
        self.assertEqual(after_uncertain.count(FEATHER), 2 - later, (after_uncertain, rows))
        self.assertEqual([r[18] for r in rows][:1], ["undone"])
        self.assertIn("unconfirmed", [r[18] for r in rows])

    def test_a_blast_spends_its_ingredients_before_it_burns(self) -> None:
        # A blast is 2d10 and a player dies at -11, so from one hit point
        # it kills only on 12 or more -- about one blast in two; the rest
        # leave the brewer incapacitated, and staff stand them back up at
        # one hit point to try again (CI, 2026-10-27).
        tries, singed_pairs = 30, 8
        with LiveMud(extra_env={"TOC_FAULT_FILE": "../fault.once"}) as mud:
            make(mud, "Zsinged", Levl=30, Cla=0, Room=HALLS,
                 HMV="300 300 300 300 300 300", HMVP="300 300 300")
            make(mud, "Zdoomed", Levl=30, Cla=0, Room=HALLS,
                 HMV="1 300 300 300 300 300", HMVP="300 300 300")
            make(mud, "Zblaststaff", Levl=70, Room=HALLS)
            add(mud, "Zsinged", "".join(obj(v) for v in (FEATHER, TOOTH) * singed_pairs),
                skills=("concoct",))
            add(mud, "Zdoomed", "".join(obj(v) for v in (FEATHER, TOOTH) * tries),
                skills=("concoct",))
            for name in ("Zsinged", "Zdoomed"):
                low_skill(mud, name, "concoct", 2)          # 46%: blasts are likely
            with mud.connect(timeout=120) as singed, mud.connect(timeout=120) as doomed, \
                    mud.connect(timeout=120) as staff:
                login(singed, "Zsinged", PW)
                login(doomed, "Zdoomed", PW)
                login(staff, "Zblaststaff", PW)
                for client in (singed, doomed, staff):
                    client.sync("scroll 0")
                staff.must("set char zdoomed hp 1", "")
                staff.must("restore zdoomed", "")
                died = ""
                for _ in range(tries):
                    out = doomed.sync("concoct feather tooth", timeout=30)
                    if "You have been KILLED" in out:
                        died = out
                        break
                    if "Something isn't right" in out:
                        # Burned but alive: back to one hit point, and again.
                        staff.must("restore zdoomed", "")
                self.assertIn("Something isn't right", died)
                self.assertIn("You have been KILLED", died)
                # Relocated as any death is, and still answering.
                self.assertIn("Zdoomed", doomed.sync("score"))

                blast = until(singed, "concoct feather tooth", "Something isn't right",
                              tries=singed_pairs)
                self.assertIn("Something isn't right", blast)
                self.assertNotIn("KILLED", blast)
                singed_left = singed.sync("inventory")
            crash(mud)
            doomed_file = file_vnums(mud, "Zdoomed")
            corpses = []
            for path in (mud.root / "corpse" / "live").glob("*.corpse"):
                text = path.read_text(encoding="latin-1")
                if "Zdoomed" in text:
                    corpses += [int(v) for v in re.findall(r"^Vnum (\d+)$", text, re.M)]
            rows = craft_rows(mud)

        mine = [r for r in rows if r[2] == "Zsinged"]
        blasts = [r for r in mine if r[16] == "exploded"]
        self.assertEqual(len(blasts), 1, mine)
        self.assertGreaterEqual(int(blasts[0][17]), 2, "burn damage recorded")
        self.assertEqual(blasts[0][18], "saved")
        # Every attempt spent a pair; at least one is left.
        self.assertIn("phoenix feather", singed_left)

        theirs = [r for r in rows if r[2] == "Zdoomed"]
        attempts = len(theirs)
        self.assertEqual(theirs[-1][16], "exploded", theirs)
        # Each attempt spent a pair, the fatal one included: neither the
        # file nor the corpse holds the ingredients the blast used.
        self.assertEqual(doomed_file.count(FEATHER) + corpses.count(FEATHER), tries - attempts,
                         (doomed_file, corpses))
        self.assertEqual(doomed_file.count(TOOTH) + corpses.count(TOOTH), tries - attempts)

    def test_a_wizinvis_scriber_is_not_named_below_their_level(self) -> None:
        blanks = "".join(obj(v) for v in (WING, SALIVA, BLOOD) * 3)
        with LiveMud() as mud:
            make(mud, "Zhidscribe", Levl=70, Room=TEMPLE)
            add(mud, "Zhidscribe", blanks, skills=("scribe",))
            make(mud, "Zlowstaff", Levl=65, Room=TEMPLE)
            make(mud, "Zhighstaff", Levl=70, Room=TEMPLE)
            with mud.connect(timeout=120) as imp, mud.connect(timeout=120) as low, \
                    mud.connect(timeout=120) as high:
                login(imp, "Zhidscribe", PW)
                login(low, "Zlowstaff", PW)
                login(high, "Zhighstaff", PW)
                for client in (imp, low, high):
                    client.sync("scroll 0")
                imp.must("wizinvis 70", "vanish into thin air")
                low.drain(1.0)
                high.drain(1.0)
                low_mark, high_mark = len(low.transcript), len(high.transcript)
                made = until(imp, "scribe wing saliva blood", "You finish")
                self.assertIn("You finish a blank scroll", made)
                low.drain(2.0)
                high.drain(2.0)
                heard_low = low.transcript[low_mark:]
                heard_high = high.transcript[high_mark:]
            rows = [r for r in craft_rows(mud) if r[8] == "remove align"]

        self.assertNotIn("has scribed", heard_low)
        self.assertNotIn("Zhidscribe", heard_low)
        self.assertIn("Zhidscribe has scribed a blank scroll", heard_high)
        # The public journal names nobody hidden.
        self.assertTrue(rows)
        self.assertTrue(all(r[2] == "-" for r in rows), rows)


if __name__ == "__main__":
    unittest.main()

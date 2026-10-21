"""The black market: Vesh, seen only up close, one of each to a customer.

Owner's design (2026-10-20): a rare dealer -- in the world about one
hour in ten -- who moves about once a minute and cannot be found from
afar: not by WHERE, the travel spells, clairvoyance, PROJECT, LOCATE
OBJECT or the Oracle. SCAN sees him one room away and no further. He
carries five things at most, drawn each visit from a pool of hundreds:
the best gear the world places for every slot at every five levels, the
holiday bosses' drops out of season, training cakes and lucky clovers.
A character may buy one of each item from a stock, kept in the player
file so a relog does not reset it. The first purchase gives that buyer
alone a window to buy; when it ends, or the buyer walks off, he vanishes.
Appearances and purchases reach the log and WIZINFO with the room.
"""
from __future__ import annotations

import pathlib
import re
import sys
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_seasonal_areas as gen  # noqa: E402  (its section/record reader)

PASSWORD = "Zmarket1pass"
TEMPLE = 4207          # the dealer is called here
NEXT_DOOR = 4202       # east of the Temple
TWO_AWAY = 4201        # east again
# The holiday drops and cakes, the wedding cake and the lucky clovers.
RARITIES = set(range(29920, 29928)) | {9943, 9944}


def body(path: str, start: str) -> str:
    source = (ROOT / path).read_text(encoding="latin-1")
    text = source[source.index(start):]
    return text[:text.index("\n}\n")]


def object_keywords() -> dict[int, str]:
    """Every object's keyword line, by vnum, from the areas area.lst loads."""
    out: dict[int, str] = {}
    for entry in (ROOT / "area" / "area.lst").read_text(encoding="latin-1").split("\n"):
        path = ROOT / "area" / entry.strip()
        if not entry.strip() or not path.is_file():
            continue
        for name, section in gen.sections(gen.read(path)):
            if name == "OBJECTS":
                for vnum, rec in gen.records(section)[1].items():
                    out[vnum] = rec[1].rstrip("~").strip()
    return out


def run(client, command: str, settle: float = 1.6) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class BlackMarketSourceTests(unittest.TestCase):
    def test_sight_is_his_own_room_only(self) -> None:
        see = body("src/handler.c", "bool can_see(")
        self.assertIn("is_unfindable_mob( victim ) && !black_market_sees( ch, victim )", see)
        self.assertLess(see.index("wizinvis_hides"), see.index("is_unfindable_mob"),
                        "checked before the immortal-mobile shortcut below it")
        self.assertLess(see.index("is_unfindable_mob"), see.index("PLR_HOLYLIGHT"))
        obj = body("src/handler.c", "bool can_see_obj(")
        self.assertIn("black_market_holds( obj )", obj)
        sees = body("src/blackmarket.c", "bool black_market_sees(")
        self.assertIn("MOB_VNUM_PSIONIC_PROJECTION", sees, "PROJECT's stand-in never sees him")

    def test_scan_stops_at_one_room_and_the_oracle_does_not_know(self) -> None:
        scan = body("src/act_info.c", "void do_scan(")
        self.assertIn("is_unfindable_mob( rch ) && counter > 1", scan)
        oracle = body("src/oracle.c", "static bool oracle_can_see_char(")
        self.assertIn("is_unfindable_mob( vch )", oracle)
        self.assertIn("is_black_market_dealer( ch ) || is_treasure_goblin( ch )",
                      body("src/blackmarket.c", "bool is_unfindable_mob("))

    def test_a_purge_cannot_leave_a_dangling_dealer(self) -> None:
        self.assertIn("black_market_forget( ch );", body("src/handler.c", "void extract_char("))

    def test_the_purchase_record_is_read_under_its_letter(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        case_b = save[save.index("\tcase 'B':"):save.index("\tcase 'C':")]
        self.assertIn('"BlackMarket"', case_b)
        self.assertIn('"BlackMarket %ld %s~\\n"', save)

    def test_he_never_stands_in_a_guild_hall_or_a_closed_area(self) -> None:
        room_ok = body("src/blackmarket.c", "static bool bm_room_ok(")
        self.assertIn("guild_hall_rooms(", room_ok)
        for flag in ("ROOM_NO_MOB", "ROOM_DT", "ROOM_PRIVATE", "ROOM_IMP_ONLY",
                     "ROOM_GODS_ONLY", "ROOM_NEWBIES_ONLY"):
            self.assertIn(flag, room_ok)

    def test_nothing_progression_based_is_ever_sold(self) -> None:
        """Owner, 2026-10-20: never the Triforce, its pieces, the Master
        Sword or anything else a player's progress depends on."""
        prog = body("src/blackmarket.c", "static bool bm_progression(")
        for term in ("BM_HYRULE_OBJ_FIRST", "BM_HYRULE_OBJ_LAST", "ITEM_KEY", "bm_is_key"):
            self.assertIn(term, prog)
        source = (ROOT / "src" / "blackmarket.c").read_text(encoding="latin-1")
        self.assertIn("#define BM_HYRULE_OBJ_FIRST   30200", source)
        self.assertIn("bm_progression( pObj )", body("src/blackmarket.c", "static bool bm_sellable("))
        self.assertIn("bm_progression( pObj )", body("src/blackmarket.c", "static bool bm_stock_one("))
        build = body("src/blackmarket.c", "static void bm_build_gear(")
        self.assertIn("bm_vnum_ok( room->exit[door]->key )", build)
        self.assertIn("bm_vnum_ok( pObj->value[2] )", build)

    def test_what_nothing_places_costs_five_times_as_much(self) -> None:
        """Owner, 2026-10-20: anything not normally obtainable, or not
        carried by a mobile, is marked up five times."""
        source = (ROOT / "src" / "blackmarket.c").read_text(encoding="latin-1")
        self.assertIn("#define BM_RARE_MARKUP        5", source)
        price = body("src/blackmarket.c", "static long bm_price(")
        self.assertIn("!bm_placed[pObj->vnum]", price)
        self.assertIn("price *= BM_RARE_MARKUP", price)
        for vnum in ("9943", "9944"):      # the lucky clovers
            self.assertIn(vnum, source)
        # The wedding cake is load-limited to one: never stocked, and the
        # stocking itself refuses anything maxload.txt limits.
        self.assertNotIn("9955", body("src/blackmarket.c", "static const int bm_cakes[]"))
        self.assertIn("get_maxload_index( pObj->vnum ) != NULL",
                      body("src/blackmarket.c", "static bool bm_stock_one("))

    def test_rare_and_small_stock_from_a_big_pool(self) -> None:
        """Owner, 2026-10-20: hundreds of possible items, five at a time,
        about one hour in ten."""
        source = (ROOT / "src" / "blackmarket.c").read_text(encoding="latin-1")
        self.assertIn("#define BM_STOCK_MAX       5", source)
        self.assertIn("#define BM_PER_SLOT        3", source)
        self.assertIn("#define BM_BAND_WIDTH      5", source)
        self.assertIn("#define BM_GEAR_MIN_LEVEL  29", source)
        self.assertIn("pObj->level < BM_GEAR_MIN_LEVEL", body("src/blackmarket.c", "static void bm_build_gear("))
        def seconds(name: str) -> int:
            m = re.search(r"#define %s\s+\((\d+)((?: \* 60)+)\)" % name, source)
            return int(m.group(1)) * 60 ** m.group(2).count("60")

        here = (seconds("BM_STAY_MIN") + seconds("BM_STAY_MAX")) / 2
        away = (seconds("BM_AWAY_MIN") + seconds("BM_AWAY_MAX")) / 2
        self.assertAlmostEqual(0.10, here / (here + away), delta=0.02)

    def test_too_long_in_one_area_and_he_crosses_the_world(self) -> None:
        source = (ROOT / "src" / "blackmarket.c").read_text(encoding="latin-1")
        self.assertIn("#define BM_AREA_MAX        ( 10 * 60 )", source)
        update = body("src/blackmarket.c", "void black_market_update(")
        self.assertIn("bm_random_room_away( dealer->in_room->area )", update)
        self.assertLess(update.index("bm_has_customer( dealer ) )\n    {"),
                        update.index("bm_area_stale( dealer )"),
                        "never while somebody is standing with him")
        self.assertIn("room->area != avoid", body("src/blackmarket.c", "static ROOM_INDEX_DATA *bm_random_room_away("))

    def test_only_standing_there_or_scanning_sees_him(self) -> None:
        """CLAIRVOYANCE looks at a friend's room by setting in_room without
        moving the looker there; that must not show him."""
        sees = body("src/blackmarket.c", "bool black_market_sees(")
        self.assertIn("if ( scan )", sees)
        self.assertIn("rch == looker", sees)
        self.assertIn("black_market_sees( ch, black_market_holder( obj ) )",
                      body("src/handler.c", "bool can_see_obj("))

    def test_he_never_dies_and_a_hand_loaded_copy_is_not_the_market(self) -> None:
        kill = body("src/fight.c", "static void raw_kill_internal(")
        self.assertLess(kill.index("black_market_cheats_death( ch, victim )"),
                        kill.index("make_corpse( victim );"))
        self.assertIn("keeper != black_market_dealer",
                      body("src/blackmarket.c", "bool black_market_buy_refuses("))
        forget = body("src/blackmarket.c", "void black_market_forget(")
        self.assertIn("BM_AWAY_MIN, BM_AWAY_MAX", forget,
                      "however he went, he is away for the away time")
        self.assertIn("is_unfindable_mob( vict )", body("src/fight.c", "void add_hate ("))

    def test_appearances_and_purchases_reach_staff(self) -> None:
        arrive = body("src/blackmarket.c", "bool black_market_arrive(")
        record = body("src/blackmarket.c", "void black_market_record(")
        for fn in (arrive, record):
            self.assertIn("log_string( line );", fn)
            self.assertIn("wizinfo( line, LEVEL_IMMORTAL );", fn)
            self.assertIn("bm_where(", fn)

    def test_the_dealer_is_a_shopkeeper_that_buys_nothing(self) -> None:
        text = (ROOT / "area" / "seasonal.are").read_text(encoding="latin-1")
        shops = text[text.index("#SHOPS"):]
        self.assertRegex(shops, r"(?m)^29940 0 0 0 0 0 100 0 0 23$")


@unittest.skipIf(SKIP is not None, SKIP or "")
class BlackMarketLiveTests(unittest.TestCase):
    def test_seen_up_close_one_of_each_then_gone(self) -> None:
        keywords = object_keywords()
        with LiveMud(extra_env={"TOC_BLACK_MARKET_STILL": "1"}) as mud:
            for name in ("Zbuyer", "Zrival", "Zfixer"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zbuyer", Levl=59, NewPlat=200000, Room=NEXT_DOOR)
            patch_player_file(mud, "Zrival", Levl=59, NewPlat=200000, Room=TEMPLE)
            patch_player_file(mud, "Zfixer", Levl=70, Room=TEMPLE)

            with mud.connect(timeout=120) as buyer, mud.connect(timeout=120) as rival, \
                    mud.connect(timeout=120) as fixer:
                login(buyer, "Zbuyer", PASSWORD)
                login(rival, "Zrival", PASSWORD)
                login(fixer, "Zfixer", PASSWORD)
                for client in (buyer, rival, fixer):
                    run(client, "scroll 0", 1.0)

                self.assertIn("is away", run(fixer, "blackmarket", 1.6))
                self.assertIn("in room %d" % TEMPLE, run(fixer, "blackmarket here", 2.0))
                # The appearance reaches staff, with the room.
                self.assertIn("[WIZINFO] Black market: the dealer appeared in room %d"
                              % TEMPLE, fixer.transcript)
                status = run(fixer, "blackmarket", 1.6)
                pool = int(re.search(r"Pool: (\d+) pieces", status).group(1))
                self.assertGreaterEqual(pool, 100, status)

                # Restock after restock: five at most, nothing of Hyrule's.
                for _ in range(12):
                    run(fixer, "blackmarket restock", 0.5)
                    sample = run(fixer, "blackmarket", 0.8)
                    vnums = [int(v) for v in re.findall(r"\((\d+)\)\s*$", sample, re.M)]
                    self.assertTrue(0 < len(vnums) <= 5, sample)
                    self.assertEqual([], [v for v in vnums if 30200 <= v <= 30999], sample)
                    # Gear from level 29; below that only the rarities.
                    for level, v in re.findall(r"^\s*\[\s*(\d+)\s+\S+\] .*\((\d+)\)\s*$", sample, re.M):
                        if int(v) not in RARITIES:
                            self.assertGreaterEqual(int(level), 29, sample)
                status = run(fixer, "blackmarket", 1.6)
                stock = [int(v) for v in re.findall(r"\((\d+)\)\s*$", status, re.M)]

                # Clairvoyance on somebody standing with him shows the room,
                # not him.
                run(fixer, "set skill zbuyer clairvoyance 100", 1.0)
                seen = run(buyer, "clairvoyance zrival", 2.0)
                self.assertIn("image of", seen)
                self.assertNotIn("Vesh", seen)

                # One room away, SCAN shows him; nothing else does.
                self.assertIn("Vesh", run(buyer, "scan", 1.8))
                for cmd in ("look vesh", "where vesh", "consider vesh"):
                    self.assertNotIn("Vesh", run(buyer, cmd, 1.6), cmd)

                # Two rooms away even a hero's longer scan does not reach him.
                run(buyer, "east", 1.6)
                self.assertNotIn("Vesh", run(buyer, "scan", 1.8))

                # In his room he is plainly the rare black market.
                run(buyer, "west", 1.6)
                self.assertIn("(Rare) Vesh the Smuggler", run(buyer, "west", 1.6))
                self.assertIn("black market", run(buyer, "look vesh", 1.6))
                listing = run(buyer, "list", 1.8)
                self.assertIn("One of each to a customer", listing)
                # The first piece a level 59 can carry (a heavy breastplate
                # may be too much for thirteen strength).
                vnum, want = 0, ""
                for v in stock:
                    if v in keywords and "You buy" in run(buyer, "buy %s" % keywords[v], 2.0):
                        vnum, want = v, keywords[v]
                        break
                self.assertTrue(vnum, "nothing in the stock could be bought:\n" + status)
                fixer.drain(1.0)
                self.assertIn("[WIZINFO] Black market: Zbuyer bought", fixer.transcript)
                self.assertIn("One to a customer", run(buyer, "buy %s" % want, 2.0))
                self.assertIn("(you have had yours)", run(buyer, "list", 1.8))
                self.assertIn("uninterested", run(buyer, "sell '%s'" % want, 1.8))
                # The sale is the buyer's alone while it lasts.
                # (The stock is random; a keyword line may not resolve for a
                # shop lookup, so every other piece is tried and none may sell.)
                others = [keywords[v] for v in stock if v in keywords and v != vnum]
                replies = [run(rival, "buy %s" % kw, 2.0) for kw in others]
                self.assertFalse(any("You buy" in r for r in replies), replies)
                if others:
                    self.assertTrue(any("with a customer" in r for r in replies), replies)

                # The buyer walks off, and he is gone from the Temple.
                run(buyer, "east", 1.6)
                buyer.drain(6.0)
                status = run(fixer, "blackmarket", 1.6)
                self.assertNotIn("in room %d" % TEMPLE, status)
                self.assertIn("The dealer is in room", status)
                rival.drain(1.0)
                self.assertNotIn("(Rare) Vesh", run(rival, "look", 1.6))

                buyer.send("quit")
                self.assertTrue(buyer.wait_closed())
            saved = (mud.player_dir / "Zbuyer").read_text(encoding="latin-1")
            self.assertRegex(saved, re.compile(r"^BlackMarket \d+ .*\b%d\b.*~$" % vnum, re.M))
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")
            self.assertIn("Black market: Zbuyer bought", log)
            self.assertIn("Black market: the dealer vanished from room %d" % TEMPLE, log)
            # The buyer is watched (LOG ALL), and log/ is public within
            # minutes: their lines beside the dealer name no room.
            self.assertRegex(log, r"Log Zbuyer \[-\]: buy ")
            self.assertNotRegex(log, r"Log Zbuyer \[%d\]: (buy|list)" % TEMPLE)

            # A relog does not hand the allowance back.
            with mud.connect(timeout=120) as buyer, mud.connect(timeout=120) as fixer:
                login(buyer, "Zbuyer", PASSWORD)
                login(fixer, "Zfixer", PASSWORD)
                run(buyer, "scroll 0", 1.0)
                run(fixer, "blackmarket here", 1.6)
                run(buyer, "west", 1.6)
                self.assertIn("One to a customer", run(buyer, "buy %s" % want, 2.0))
                # He cannot be attacked, and when dismissed he is gone.
                # Waited for, not drained for: the purchase saved the buyer,
                # and under the sanitizer build with a second server on the
                # runner that save outlasted a fixed 1.6 s window (CI run
                # 411 read an empty reply here).
                buyer.buffer = ""
                buyer.send("kill vesh")
                buyer.expect("shopkeeper wouldn't like that", timeout=15)
                self.assertIn("gone", run(fixer, "blackmarket dismiss", 1.6))
                buyer.drain(1.0)
                self.assertNotIn("(Rare) Vesh", run(buyer, "look", 1.6))
                self.assertIn("is away", run(fixer, "blackmarket", 1.6))

"""The alignment system, rebuilt (src/alignment.c, owner 2026-10-21).

One number from -1000 to 1000 as ever, now in seven named tiers with
perks, moved by whom you slay (toward the light for the evil, the dark for
the good, not at all for the neutral), by quest targets of a side and by
DEVOTE at the Temple. Slaying the other side pays more experience and
nothing pays less; shopkeepers of your side charge a tenth less and those
of the other side a tenth more.

It replaced a rule that pushed you away from every victim, which made the
ends one-way doors -- at -1000 every mobile is "more good" than you, so
every kill pushed you down and nothing raised you (112 characters sat at
-1000 and 217 at 1000, 2026-10-21) -- and an experience table that paid as
little as a quarter of a kill for the "wrong" victim, with two branches it
could never reach.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zalign1pass"
FIELD = 4202            # east of the Temple: not safe
TEMPLE = 4207
SUB_SWORD = 3702        # the newbie sword, made 20d20 by the warden
SILVER_PLATE = 631      # anti-evil body armour, ofcol.are
WORKER = 12002          # sentinel, not wimpy, not a school monster (NOALIGN)


def source(name: str) -> str:
    return (ROOT / "src" / name).read_text(encoding="latin-1")


def body(name: str, signature: str) -> str:
    text = source(name)
    start = text.index(signature)
    return text[start:text.index("\n}\n", start)]


def run(client, command: str, settle: float = 1.6) -> str:
    start = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[start:]


def saved(mud, name: str) -> str:
    return (mud.root / "player" / name).read_text(encoding="latin-1")


def tier(a: int) -> int:
    """alignment_tier, mirrored."""
    for floor, t in ((900, 3), (550, 2), (300, 1)):
        if a >= floor:
            return t
    if a > -300:
        return 0
    return -1 if a > -550 else -2 if a > -900 else -3


def xp_percent(slayer: int, victim: int) -> int:
    """alignment_xp_percent, mirrored."""
    side = 1 if victim >= 300 else -1 if victim <= -300 else 0
    if side == 0:
        return 100
    t = tier(slayer)
    if t == 0:
        return 110
    if (t > 0 and side < 0) or (t < 0 and side > 0):
        return 100 + 10 * abs(t)
    return 100


class AlignmentSourceTests(unittest.TestCase):
    def test_tiers_meet_is_good_and_is_evil(self) -> None:
        merc = source("merc.h")
        self.assertIn("#define IS_GOOD(ch)             (ch->alignment >= 300)", merc)
        self.assertIn("#define IS_EVIL(ch)             (ch->alignment <= -300)", merc)
        tiers = body("alignment.c", "int alignment_tier(")
        for line in ("if ( a >= 300 )  return 1;", "if ( a > -300 )  return 0;"):
            self.assertIn(line, tiers)

    def test_kills_go_through_the_module(self) -> None:
        compute = body("fight.c", "int xp_compute(")
        self.assertIn("alignment_kill( gch, victim );", compute)
        self.assertIn("xp = base_exp * alignment_xp_percent( gch, victim ) / 100;", compute)
        self.assertNotIn("goodie two shoes", compute)
        self.assertNotIn("gch->alignment", compute)

    def test_no_kill_pays_less(self) -> None:
        for slayer in range(-1000, 1001, 50):
            for victim in range(-1000, 1001, 50):
                self.assertGreaterEqual(xp_percent(slayer, victim), 100)
        self.assertEqual(xp_percent(1000, -1000), 130)
        self.assertEqual(xp_percent(-1000, 1000), 130)
        self.assertEqual(xp_percent(0, 800), 110)

    def test_the_ends_are_not_traps(self) -> None:
        kill = body("alignment.c", "void alignment_kill(")
        self.assertIn("alignment_shift( gch, victim->alignment < 0 ? amount : -amount, true );", kill)
        self.assertIn("alignment_side( victim->alignment ) == 0", kill,
                      "the neutral move nothing")

    def test_damage_hooks(self) -> None:
        damage = body("fight.c", "bool damage(")
        self.assertLess(damage.index("alignment_damage_mod( ch, victim, dam, dam_type )"),
                        damage.index("switch(check_immune(victim,dam_type))"))
        sub = damage.index("victim->hit -= dam;")
        self.assertLess(sub, damage.index("alignment_drain( ch, victim, dam, dt );"))
        self.assertIn("gain = alignment_regen( ch, gain );", body("update.c", "int hit_gain("))

    def test_every_gear_check_is_the_helper(self) -> None:
        pattern = re.compile(r"ITEM_ANTI_EVIL\)?\s*\)?\s*&&\s*IS_EVIL")
        for path in sorted((ROOT / "src").glob("*.c")):
            if path.name == "alignment.c":
                continue
            self.assertIsNone(pattern.search(path.read_text(encoding="latin-1")), path.name)

    def test_every_shop_price_is_adjusted(self) -> None:
        act_obj = source("act_obj.c")
        calls = len(re.findall(r"get_cost\s*\(\s*keeper", act_obj))
        wrapped = len(re.findall(r"alignment_price\(\s*ch,\s*keeper,\s*get_cost\(", act_obj))
        # Every price shown or paid goes through alignment_price; the fifth
        # call is the haggle cap, which must stay the unadjusted list price
        # (test_haggling_never_pays_above_worth).
        self.assertEqual((calls, wrapped), (5, 4), "every shop price goes through alignment_price")
        price = body("alignment.c", "long alignment_price(")
        self.assertIn("is_black_market_dealer( keeper )", price, "the dealer never haggles")
        self.assertIn("return ours == theirs ? cost : cost - share;", price,
                      "nobody is paid above list for what they sell")
        self.assertIn("return UMIN( cost, UMAX( cost - share, worth ) );", price)

    def test_no_shop_loop(self) -> None:
        """Buying at one shop and selling at another can never profit: no
        shop buys back above an item's worth, and the discount never sells
        below it. The first draft paid a keeper's own side a tenth more,
        which opened thousands of such loops."""
        buybacks = []
        listed = set((ROOT / "area" / "area.lst").read_text().split())
        for path in (ROOT / "area").glob("*.are"):
            if path.name not in listed:
                continue
            text = path.read_text(encoding="latin-1")
            if "#SHOPS" not in text:
                continue
            for line in text.split("#SHOPS", 1)[1].splitlines()[1:]:
                tokens = line.split(";")[0].split()
                if not tokens:
                    continue
                if tokens[0] == "0":
                    break
                buybacks.append((int(tokens[7]), path.name, tokens[0]))
        self.assertGreater(len(buybacks), 100)
        self.assertLessEqual(max(buybacks)[0], 100, max(buybacks))
        # The discount's floor, mirrored, never goes below worth.
        for worth in range(1, 4000):
            for markup in (101, 105, 110, 120, 150, 170, 250):
                cost = worth * markup // 100
                if cost <= 0:
                    continue
                floor = cost // markup * 100 + (cost % markup * 100 + markup - 1) // markup
                self.assertGreaterEqual(min(cost, max(cost - cost // 10, floor)), worth)

    def test_quiet_shifts_and_drain_guards(self) -> None:
        shift = body("alignment.c", "void alignment_shift(")
        self.assertIn("if ( loud && IS_SET(ch->act, PLR_DAMAGE_NUMBERS) )", shift)
        self.assertIn("if ( loud && alignment_side( now ) != alignment_side( was ) )\n"
                      "        alignment_check_gear( ch );", shift)
        self.assertIn("alignment_shift( ch, -1, false );", source("fight.c"),
                      "a vampiric weapon moves its wielder quietly")
        self.assertNotIn("alignment_shift( ch, -1, true )", source("fight.c"))
        drain = body("alignment.c", "void alignment_drain(")
        self.assertIn("is_treasure_goblin( victim )", drain)
        self.assertIn("dam += victim->hit;", drain, "overkill is not drained")
        self.assertIn("alignment_check_gear( gch );", body("fight.c", "void group_gain("))

    def test_haggling_never_pays_above_worth(self) -> None:
        sell = source("act_obj.c")
        sell = sell[sell.index("You haggle with the shopkeeper"):]
        sell = sell[:sell.index("purse")]
        self.assertIn("cost = UMIN(cost,95 * get_cost(keeper,obj,true) / 100);", sell,
                      "the cap is the unadjusted price: the other side's markup raised it")
        self.assertIn("cost = UMIN( cost, worth );", sell)
        self.assertIn("xp = base_exp * alignment_xp_percent( gch, victim ) / 100;\n\n"
                      "    alignment_kill( gch, victim );", body("fight.c", "int xp_compute("),
                      "experience reads the alignment the slayer struck with")
        self.assertIn("alignment_check_gear( ch );", body("fight.c", "void violence_update("))

    def test_the_healer_refuses_what_nosummon_closes(self) -> None:
        work = body("magic.c", "bool remove_curse_has_work(")
        self.assertIn("PLR_NOSUMMON", work)
        self.assertIn("Type NOSUMMON to open it", source("misc.c"))
        # Only when NOSUMMON is what hides cursed gear: a new character has
        # it on and nothing cursed, and is told there is no curse (CI on
        # dc3a8c80, test_review_oct21).
        self.assertIn("remove_curse_gear_cursed( ch )", source("misc.c"))

    def test_gmcp_status_carries_the_tier(self) -> None:
        gmcp = source("gmcp.c")
        self.assertIn('",\\"tier\\":"', gmcp)
        self.assertIn("d->gmcp_last_tier != alignment_tier( ch->alignment )", gmcp)
        self.assertNotIn('",\\\\"alignment\\\\":"', gmcp, "the tier alone: a number would go stale")
        self.assertIn("status.tier", (ROOT / "mudlet" / "package" / "TimesOfChaos.xml")
                      .read_text(encoding="utf-8"))

    def test_commands_do_not_steal_prefixes(self) -> None:
        order = [m.group(1) for m in re.finditer(r'\{ "([a-z_]+)",', source("interp.c"))]
        self.assertEqual(next(w for w in order if w.startswith("al")), "alias")
        self.assertNotEqual(next(w for w in order if w.startswith("de")), "devote")
        self.assertEqual(next(w for w in order if w.startswith("dev")), "devote")
        self.assertEqual(next(w for w in order if w.startswith("alig")), "alignment")

    def test_saves(self) -> None:
        save = source("save.c")
        reader = save[save.index("case 'A':", save.index("void fread_char")):]
        reader = reader[:reader.index("case 'B':")]
        self.assertIn('!str_cmp( word, "AlignDeed" )', reader)
        self.assertIn("ch->alignment = (sh_int) URANGE( -1000, align, 1000 );", reader)


@unittest.skipIf(SKIP is not None, SKIP or "")
class AlignmentLiveTests(unittest.TestCase):
    def test_slaying_devotion_and_the_card(self) -> None:
        with LiveMud() as mud:
            for name in ("Zslayer", "Zwarden"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zslayer", Levl=20, Room=FIELD, Alig=-1000, NewPlat=500)
            patch_player_file(mud, "Zwarden", Levl=70, Room=FIELD)

            with mud.connect(timeout=120) as slayer, mud.connect(timeout=120) as warden:
                login(slayer, "Zslayer", PASSWORD)
                login(warden, "Zwarden", PASSWORD)
                run(slayer, "damagenumbers", 1.0)
                # A new character has 20 hit points and a sword that scratches:
                # give them a body that lasts and a blade that ends a fight.
                run(warden, "set char zslayer hp 3000", 1.0)
                run(warden, "load obj %d" % SUB_SWORD, 1.0)
                run(warden, "set obj sword v1 20", 1.0)
                run(warden, "set obj sword v2 20", 1.0)
                run(warden, "set obj sword level 1", 1.0)
                run(warden, "give sword zslayer", 1.0)
                run(slayer, "wield sword", 1.5)

                def worker(level: int, align: int) -> None:
                    run(warden, "restore zslayer", 1.0)
                    run(warden, "load mob %d" % WORKER, 1.0)
                    run(warden, "set mob worker level %d" % level, 1.0)
                    run(warden, "set mob worker align %d" % align, 1.0)

                def slay() -> str:
                    # Fight until it falls: a blow can miss.
                    start = len(slayer.transcript)
                    slayer.send("kill worker")
                    for _ in range(10):
                        slayer.drain(3.0)
                        if "is DEAD" in slayer.transcript[start:]:
                            break
                    slayer.drain(1.0)
                    self.assertIn("is DEAD", slayer.transcript[start:])
                    return slayer.transcript[start:]

                # A Fiend slaying the evil climbs: the old rule pushed down.
                worker(15, -800)
                self.assertIn("Your alignment has risen by 8.", slay())

                # Across a tier line, everyone is told.
                run(warden, "set char zslayer align -905", 1.0)
                worker(15, -800)
                self.assertIn("Your soul brightens: you are now Vile.",
                              slay())

                # The neutral move nothing; a foe far below you moves nothing.
                worker(15, 0)
                self.assertNotIn("Your alignment has", slay())
                worker(1, 900)
                self.assertNotIn("Your alignment has", slay())

                card = run(slayer, "alignment", 3.5)   # behind the kill's lag
                self.assertIn("You are Vile, the second of three tiers of the dark", card)
                self.assertIn("Fiend is 3 toward the dark.", card)
                self.assertIn("drain 4%", card)
                self.assertIn("You are Vile.", run(slayer, "score", 1.2))

                # DEVOTE is a Temple deed, paid for, and then waits -- and a
                # devotion across a line takes off gear that will not follow.
                self.assertIn("Devotion is made at the Temple", run(slayer, "devote light", 1.0))
                run(warden, "set char zslayer align -250", 1.0)
                run(warden, "load obj %d" % SILVER_PLATE, 1.0)
                run(warden, "set obj plate level 1", 1.0)   # loaded at the warden's 70
                run(warden, "give plate zslayer", 1.0)
                self.assertIn("You wear silver plate on your body.", run(slayer, "wear plate", 1.5))
                run(warden, "transfer zslayer %d" % TEMPLE, 1.0)
                slayer.drain(1.0)
                reply = run(slayer, "devote dark", 4.0)
                self.assertIn("whisper to what listens below", reply)
                self.assertIn("Your alignment has lowered by 100.", reply)
                self.assertIn("Your soul darkens: you are now Ruthless.", reply)
                self.assertIn("You are zapped by silver plate.", reply)
                self.assertIn("The gods will hear you again in 30 minutes.",
                              run(slayer, "devote light", 4.0))

                slayer.send("quit")
                self.assertTrue(slayer.wait_closed())
            text = saved(mud, "Zslayer")
            self.assertRegex(text, r"(?m)^AlignDeed \d+$")
            self.assertRegex(text, r"(?m)^Alig\s+-350$")

            # A file left at 1005 by the old unclamped branch loads at 1000.
            patch_player_file(mud, "Zslayer", Alig=1005)
            with mud.connect(timeout=120) as slayer:
                login(slayer, "Zslayer", PASSWORD)
                slayer.drain(1.0)
                slayer.send("quit")
                self.assertTrue(slayer.wait_closed())
            self.assertRegex(saved(mud, "Zslayer"), r"(?m)^Alig\s+1000$")


if __name__ == "__main__":
    unittest.main()

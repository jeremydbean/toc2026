from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def function_body(source: str, name: str) -> str:
    match = re.search(
        rf"(?:static\s+)?(?:bool|void|long|int)\s+{name}\s*\([^)]*\)\s*\{{",
        source,
    )
    if match is None:
        raise AssertionError(f"{name} implementation was not found")

    start = match.end()
    depth = 1
    index = start
    while index < len(source) and depth:
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
        index += 1
    if depth:
        raise AssertionError(f"{name} has unbalanced braces")
    return source[start : index - 1]


class MoneySafetyRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.act_obj = (ROOT / "src" / "act_obj.c").read_text(encoding="utf-8")
        cls.act_comm = (ROOT / "src" / "act_comm.c").read_text(
            encoding="utf-8"
        )
        cls.fight = (ROOT / "src" / "fight.c").read_text(encoding="utf-8")
        cls.save = (ROOT / "src" / "save.c").read_text(encoding="utf-8")
        cls.special = (ROOT / "src" / "special.c").read_text(encoding="utf-8")
        cls.help = (ROOT / "area" / "commands.are").read_text(
            encoding="latin-1"
        )

    def test_combined_coin_value_is_checked_before_exact_adjustments(self) -> None:
        body = function_body(self.act_obj, "can_adjust_coin_balance")
        self.assertIn("coins_to_copper_checked(ch, &total)", body)
        self.assertIn("amount > LONG_MAX / multiplier", body)
        self.assertIn("LONG_MAX - total", body)
        self.assertIn(
            "coins_to_copper_checked(ch, &total_copper)",
            function_body(self.act_obj, "has_enough_gold"),
        )
        self.assertIn(
            "coins_to_copper_checked(ch, &total) ? total : 0",
            function_body(self.act_obj, "coins_to_copper"),
        )

    def test_bank_transactions_preflight_and_save_atomically(self) -> None:
        deposit = function_body(self.act_obj, "do_deposit")
        withdraw = function_body(self.act_obj, "do_withdraw")

        self.assertLess(
            deposit.index("amount_copper > LONG_MAX - ch->pcdata->bank"),
            deposit.index("normalize_coins(ch, carried_copper - amount_copper)"),
        )
        self.assertLess(
            withdraw.index("carried_copper > LONG_MAX - amount_copper"),
            withdraw.index("ch->pcdata->bank -= amount_copper"),
        )
        self.assertIn("save_char_obj(ch)", deposit)
        self.assertIn("save_char_obj(ch)", withdraw)

    def test_gameplay_paths_do_not_mutate_coin_fields_directly(self) -> None:
        gameplay = self.act_obj + self.act_comm + self.special
        direct_mutation = re.compile(
            r"new_(?:gold|silver|copper|platinum)\s*(?:\+=|-=)"
        )
        self.assertIsNone(direct_mutation.search(gameplay))

    def test_partial_pickup_rebuilds_the_visible_money_pile(self) -> None:
        resize = function_body(self.act_obj, "resize_money_pile")
        get = function_body(self.act_obj, "do_get")
        self.assertIn("replacement = create_money(amount, obj->value[1])", resize)
        self.assertIn("obj->item_type != ITEM_MONEY", self.act_obj)
        self.assertIn("query_carry_coins( ch, obj->value[0] )", self.act_obj)
        self.assertIn(
            "resize_money_pile(container, container->value[0] - amount)", get
        )

    def test_large_npc_coin_balances_are_split_without_int_narrowing(self) -> None:
        helper = function_body(self.fight, "add_coin_piles_to_corpse")
        corpse = function_body(self.fight, "make_corpse")
        self.assertIn("amount > INT_MAX ? INT_MAX : (int)amount", helper)
        self.assertIn("add_coin_piles_to_corpse", corpse)
        self.assertNotRegex(corpse, r"\(int\)\(ch->new_")

    def test_long_money_fields_round_trip_without_int_truncation(self) -> None:
        for keyword, field in (
            ("NewGold", "ch->new_gold"),
            ("NewPlat", "ch->new_platinum"),
            ("NewSilv", "ch->new_silver"),
            ("NewCopp", "ch->new_copper"),
            ("CasinoWon", "ch->pcdata->casino_winnings"),
            ("CasinoLost", "ch->pcdata->casino_losses"),
        ):
            with self.subTest(keyword=keyword):
                self.assertRegex(
                    self.save,
                    rf'KEY\(\s*"{keyword}"\s*,\s*{re.escape(field)}\s*,\s*fread_long',
                )

    def test_casino_totals_saturate_and_special_wins_emit_events(self) -> None:
        record = function_body(self.act_obj, "casino_record_total")
        self.assertIn("amount > LONG_MAX - *total", record)
        self.assertIn("achievement_check_economy", record)
        for event in (
            "ACHIEVEMENT_EVENT_SLOTS_JACKPOT",
            "ACHIEVEMENT_EVENT_ROULETTE_STRAIGHT",
            "ACHIEVEMENT_EVENT_POKER_ROYAL_FLUSH",
        ):
            with self.subTest(event=event):
                self.assertIn(event, self.act_obj)

    def test_thief_percentage_avoids_multiplying_the_full_balance(self) -> None:
        percentage = function_body(self.special, "thief_percentage")
        thief = function_body(self.special, "spec_thief")
        self.assertIn("(balance / 100L) * percent", percentage)
        self.assertIn("adjust_coin_balance(victim, -gold, coin_type)", thief)
        self.assertNotRegex(thief, r"victim->new_\w+\s*\*")

    def test_bank_and_casino_help_matches_runtime_defaults_and_limits(self) -> None:
        self.assertIn("if omitted, platinum is assumed", self.help)
        self.assertIn("1 to 100,000 gold", self.help)
        self.assertIn("Bets above 500 gold require confirmation", self.help)


if __name__ == "__main__":
    unittest.main()

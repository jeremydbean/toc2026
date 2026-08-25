import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BankInterestRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        update_source = (ROOT / "src" / "update.c").read_text(encoding="utf-8")
        match = re.search(
            r"static void bank_interest\s*\([^)]*\)\s*\{(?P<body>.*?)\n\}",
            update_source,
            re.DOTALL,
        )
        if match is None:
            raise AssertionError("bank_interest implementation was not found")
        cls.body = match.group("body")

    def test_capped_catch_up_consumes_all_complete_elapsed_days(self) -> None:
        timestamp_update = (
            "current_time - (elapsed % BANK_INTEREST_SECS)"
        )
        self.assertIn(timestamp_update, self.body)
        self.assertNotIn("bank_interest_time += days *", self.body)

    def test_below_minimum_days_are_consumed_before_returning(self) -> None:
        timestamp_position = self.body.index(
            "current_time - (elapsed % BANK_INTEREST_SECS)"
        )
        minimum_position = self.body.index("bank < BANK_INTEREST_MIN")
        self.assertLess(timestamp_position, minimum_position)

    def test_interest_output_uses_readable_coin_denominations(self) -> None:
        self.assertIn("format_coins( gain, coins_buf", self.body)
        self.assertNotIn("earned %ld copper in interest", self.body)

    def test_interest_cannot_overflow_the_bank_balance(self) -> None:
        self.assertIn("LONG_MAX - ch->pcdata->bank", self.body)


if __name__ == "__main__":
    unittest.main()

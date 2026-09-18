"""Bank interest: the rate, and the lifetime total.

1% a day compounds to roughly 3700% a year, which made a balance a better
income than playing; it is a quarter of a percent now. The exact figure is
worth pinning because the payout divides before it multiplies -- dividing
first keeps a large balance from overflowing across the seven-day catch-up,
and that changes the rounding, so the arithmetic is asserted rather than
assumed.

The lifetime total is new: interest arrives while you are offline and the
notice scrolls past on login, so score is the only place you can see what
the account has earned.

These wait for a game tick, which is randomised between 40 and 80 seconds,
so they are slow by nature rather than by accident.
"""
from __future__ import annotations

import re
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from live_mud import (  # noqa: E402
    LiveMud,
    create_character,
    login,
    patch_player_file,
    skip_reason,
)

SKIP = skip_reason()

PASSWORD = "Zbankint1"

ONE_DAY = 86400
DIVISOR = 400          # 0.25%
STARTING_BALANCE = 4_000_000  # 4 platinum; over the 1p minimum, and a
                             # day of interest is exactly 10_000 copper


def run(client, command: str, settle: float = 2.5) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


@unittest.skipIf(SKIP is not None, SKIP or "")
class BankInterestTests(unittest.TestCase):
    def prepare(self, mud: LiveMud, name: str, days: int = 1) -> None:
        with mud.connect(timeout=120) as client:
            create_character(client, name, PASSWORD)
            client.send("quit")
            client.wait_closed()
        patch_player_file(
            mud, name,
            BankCP=STARTING_BALANCE,
            IntTime=int(time.time()) - (ONE_DAY * days) - 60,
        )

    def test_a_day_pays_a_quarter_percent(self) -> None:
        with LiveMud() as mud:
            self.prepare(mud, "Zbankone")
            with mud.connect(timeout=120) as client:
                login(client, "Zbankone", PASSWORD)

                # The tick is randomised between 40 and 80 seconds.
                client.expect("earned", timeout=150)
                client.drain(2.0)

                self.assertIn("0.25% daily", client.transcript)

                shown = run(client, "score", settle=3.0)
                match = re.search(r"Bank:\s+(\d+)p (\d+)g (\d+)s (\d+)c", shown)
                self.assertIsNotNone(match, "score should show the balance")

                platinum, gold, silver, copper = (int(g) for g in match.groups())
                total = (platinum * 1_000_000 + gold * 10_000
                         + silver * 100 + copper)
                expected = STARTING_BALANCE + STARTING_BALANCE // DIVISOR
                self.assertEqual(total, expected)

    def test_score_reports_the_lifetime_total(self) -> None:
        with LiveMud() as mud:
            self.prepare(mud, "Zbanktwo")
            with mud.connect(timeout=120) as client:
                login(client, "Zbanktwo", PASSWORD)
                client.expect("earned", timeout=150)
                client.drain(2.0)

                shown = run(client, "score", settle=3.0)
                self.assertIn("Interest:", shown)

                # Not the zero it starts at: the payment was recorded.
                interest_row = next(row for row in shown.splitlines()
                                    if "Interest:" in row)
                self.assertRegex(interest_row, r"[1-9]")

    def test_the_catch_up_is_capped_at_seven_days(self) -> None:
        """Ten days offline pays seven, not ten."""
        with LiveMud() as mud:
            self.prepare(mud, "Zbankthr", days=10)
            with mud.connect(timeout=120) as client:
                login(client, "Zbankthr", PASSWORD)
                client.expect("earned", timeout=150)
                client.drain(2.0)

                self.assertIn("7 days", client.transcript)

                shown = run(client, "score", settle=3.0)
                match = re.search(r"Bank:\s+(\d+)p (\d+)g (\d+)s (\d+)c", shown)
                platinum, gold, silver, copper = (int(g) for g in match.groups())
                total = (platinum * 1_000_000 + gold * 10_000
                         + silver * 100 + copper)
                expected = STARTING_BALANCE + (STARTING_BALANCE // DIVISOR) * 7
                self.assertEqual(total, expected)


if __name__ == "__main__":
    unittest.main()

"""Mana and endurance wrapped negative by the old 16-bit store (2026-11-16).

Before 2026-11-13 a step stored (int16_t)(move - cost), so a character
with more than 32,767 endurance read it negative and the tick climbed
back a few dozen a tick for days. The login fix 20261116-wrapped-pools
puts back the wrapped value plus 65,536 when the maximum allows it, and
nothing below zero otherwise; a second login says nothing, and a
character with no negative pool is marked and told nothing. Synthetic Z
characters in a disposable world only.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zwrappass1"
FIX = "20261116-wrapped-pools"
NOTICE = "an old bug had turned your endurance or mana negative"


def plant(mud, name, mana, max_mana, move, max_move) -> None:
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    text, n = re.subn(r"(?m)^HMV  (\S+) (\S+) \S+ \S+ \S+ \S+$",
                      lambda m: "HMV  %s %s %d %d %d %d" % (m.group(1), m.group(2), mana, max_mana, move, max_move),
                      text)
    assert n == 1, text
    text, n = re.subn(r"(?m)^HMVP (\S+) \S+ \S+$",
                      lambda m: "HMVP %s %d %d" % (m.group(1), max_mana, max_move), text)
    assert n == 1
    # A new character is marked with every fix; take this one off.
    text, n = re.subn(r"(?m)^(Fixes .*?) ?%s(.*~)$" % re.escape(FIX), r"\1\2", text)
    assert n == 1, "fixture has no %s mark" % FIX
    path.write_text(text, encoding="latin-1")


def pools(mud, name) -> tuple:
    m = re.search(r"(?m)^HMV  \S+ \S+ (\S+) (\S+) (\S+) (\S+)$",
                  (mud.player_dir / name).read_text(encoding="latin-1"))
    return tuple(int(v) for v in m.groups())


def fixes(mud, name) -> str:
    m = re.search(r"(?m)^Fixes (.*)~$", (mud.player_dir / name).read_text(encoding="latin-1"))
    return m.group(1) if m else ""


@unittest.skipIf(SKIP is not None, SKIP or "")
class WrappedPoolTests(unittest.TestCase):
    def test_unwrapped_once(self) -> None:
        with LiveMud() as mud:
            for name in ("Zwrapped", "Zwrapsmall", "Zwrapclean"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    client.wait_closed()
                patch_player_file(mud, name, Levl=20, Room=4207)
            # 41,287 of 100,000 endurance, wrapped; mana fine.
            plant(mud, "Zwrapped", 50, 100, 41287 - 65536, 100000)
            # A maximum a 16-bit store never wrapped: nothing below zero.
            plant(mud, "Zwrapsmall", -5, 100, -12, 200)
            plant(mud, "Zwrapclean", 50, 100, 150, 200)

            for name, expect in (("Zwrapped", (50, 100, 41287, 100000)),
                                 ("Zwrapsmall", (0, 100, 0, 200)),
                                 ("Zwrapclean", (50, 100, 150, 200))):
                with mud.connect(timeout=120) as client:
                    login(client, name, PW)
                    seen = client.transcript + client.sync("save")
                    if name == "Zwrapclean":
                        self.assertNotIn(NOTICE, seen, name)
                    else:
                        self.assertIn(NOTICE, seen, name)
                    client.send("quit")
                    client.wait_closed()
                got = pools(mud, name)
                # Regeneration may have added a little since the login.
                self.assertEqual((got[1], got[3]), (expect[1], expect[3]), name)
                self.assertGreaterEqual(got[0], expect[0], name)
                self.assertGreaterEqual(got[2], expect[2], name)
                self.assertLess(got[2], expect[2] + 1000, name)
                self.assertIn(FIX, fixes(mud, name).split(), name)

            # A second login says nothing.
            with mud.connect(timeout=120) as client:
                login(client, "Zwrapped", PW)
                self.assertNotIn(NOTICE, client.transcript + client.sync("save"))
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1", errors="replace")
            self.assertIn("Wrapped pools: Zwrapped's mana 50 -> 50, endurance -24249 -> 41287.", log)


class WrappedPoolSourceTests(unittest.TestCase):
    def test_fix_is_listed_and_no_16_bit_pool_store_remains(self) -> None:
        fixes_c = (ROOT / "src" / "fixes.c").read_text(encoding="utf-8")
        self.assertIn('"%s"' % FIX, fixes_c)
        for path in (ROOT / "src").glob("*.c"):
            text = path.read_text(encoding="latin-1")
            self.assertIsNone(re.search(r"\((?:int16_t|sh_int)\)\s*\(\s*\w+->(?:move|mana|hit)\b", text),
                              path.name)

    def test_plague_floors_and_a_negative_pool_is_an_anomaly(self) -> None:
        update = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        self.assertIn("ch->mana = UMAX( 0, ch->mana - dam );", update)
        self.assertIn("ch->move = UMAX( 0, ch->move - dam );", update)
        self.assertNotRegex(update, r"ch->(mana|move) -= dam;")
        playlog = (ROOT / "src" / "playlog.c").read_text(encoding="latin-1")
        tick = playlog.split("void playlog_tick", 1)[1].split("\n}\n", 1)[0]
        self.assertIn('anomaly( ch, 7, "negative mana or endurance"', tick)
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        self.assertIn("play_anom_last[8]", merc)


if __name__ == "__main__":
    unittest.main()

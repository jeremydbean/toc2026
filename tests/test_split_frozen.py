"""SPLIT never pays a member whose file is held still (review, 2026-11-03).

An unrecorded death holds the owner's file still: every save of theirs is
refused, and what they gain meanwhile is gone when their file comes back
at the next login (tests/test_death_unrecorded_trade.py). SPLIT asked
whether the splitter was frozen, but not the members it paid: a healthy
character split two gold with a frozen one, saved, and kept one gold --
the frozen member's gold went with their file. Total wealth fell.

do_split now refuses the whole split when any member it would pay is
held still, before a coin moves, for every denomination and for the
autosplit that picking up coin does. These tests count every copper on
the three characters across the attempts, a quit and login of the frozen
one, and a split that works again once the death is settled. Synthetic Z
characters only.
"""
from __future__ import annotations

import unittest

from live_mud import BANK_ROOM_VNUM, LiveMud, create_character, login, patch_player_file, skip_reason
from test_death_unrecorded_trade import full_fixes, wealth

SKIP = skip_reason()
PW = "Zsppass1"
STAFF, SPLITTER, FROZEN, MEMBER = "Zspstaff", "Zsplitter", "Zspfrozen", "Zspmember"
REFUSED = "nothing can pass between you"
ENV = {"TOC_FAULT": "autowrite", "TOC_FAULT_FILE": "../fault.once"}
GOLD = 10000


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def journal(mud: LiveMud) -> list[list[str]]:
    path = mud.root / "log" / "play.tsv"
    return [line.split("\t") for line in path.read_text(encoding="latin-1").splitlines()]


@unittest.skipIf(SKIP is not None, SKIP or "")
class SplitFrozenMemberTests(unittest.TestCase):
    def test_no_split_pays_a_frozen_member_and_wealth_is_conserved(self) -> None:
        with LiveMud(extra_env=ENV) as mud:
            make(mud, STAFF, Levl=70, Room=BANK_ROOM_VNUM, NewGold=3)
            make(mud, SPLITTER, Levl=20, Room=BANK_ROOM_VNUM,
                 NewPlat=3, NewGold=3, NewSilv=3, NewCopp=3, BankCP=0)
            make(mud, MEMBER, Levl=20, Room=BANK_ROOM_VNUM,
                 NewPlat=0, NewGold=0, NewSilv=0, NewCopp=0, BankCP=0)
            make(mud, FROZEN, Levl=20, Room=BANK_ROOM_VNUM,
                 NewPlat=0, NewGold=0, NewSilv=0, NewCopp=0, BankCP=0,
                 HMV="300 300 300 300 300 300")
            path = mud.player_dir / FROZEN
            path.write_text(path.read_text(encoding="latin-1").replace(
                next(l for l in path.read_text(encoding="latin-1").splitlines()
                     if l.startswith("Fixes ")), "Fixes " + full_fixes() + "~", 1),
                encoding="latin-1")
            names = (SPLITTER, MEMBER, FROZEN)
            before = sum(wealth(mud, n) for n in names)

            staff, splitter, member, frozen = (mud.connect(timeout=120) for _ in range(4))
            clients = [staff, splitter, member, frozen]
            try:
                for client, name in zip(clients, (STAFF,) + names):
                    login(client, name, PW)
                    client.sync("scroll 0")
                staff.must(f"slay {FROZEN.lower()}", "")
                staff.must(f"transfer {FROZEN.lower()} {BANK_ROOM_VNUM}", "Ok.")
                self.assertIn("has not been laid to rest yet",
                              frozen.sync(f"give 1 copper {SPLITTER.lower()}"))

                for follower in (member, frozen):
                    follower.must(f"follow {SPLITTER.lower()}", "You now follow")
                splitter.must(f"group {MEMBER.lower()}", "")
                splitter.must(f"group {FROZEN.lower()}", "")
                self.assertIn(FROZEN, splitter.sync("group"))

                # Every denomination, with two members to pay: refused whole.
                for coin in ("platinum", "gold", "silver", "copper"):
                    said = splitter.sync(f"split 3 {coin}")
                    self.assertIn(REFUSED, said, coin)
                    self.assertNotIn("You split", said, coin)

                # Autosplit: coin picked up is kept whole, not split.
                if "removed" in splitter.sync("autosplit"):
                    splitter.must("autosplit", "splitting set")
                staff.must("drop 3 gold", "")
                said = splitter.sync("get gold")
                self.assertIn(REFUSED, said)
                splitter.must("save", "Saving")
                member.must("save", "Saving")

                # The frozen member's file comes back as it was.
                frozen.send("quit")
                self.assertTrue(frozen.wait_closed())
                frozen.close()
                frozen = clients[3] = mud.connect(timeout=120)
                login(frozen, FROZEN, PW)
                frozen.sync("scroll 0")
                frozen.must("save", "Saving")
                after = sum(wealth(mud, n) for n in names)
                self.assertEqual(after, before + 3 * GOLD, "the staff's three gold, no more")
                self.assertEqual(wealth(mud, MEMBER), 0)
                self.assertEqual(wealth(mud, FROZEN), 0)

                # Settled: the same split works and every copper is kept.
                frozen.must(f"follow {SPLITTER.lower()}", "You now follow")
                splitter.must(f"group {FROZEN.lower()}", "")
                said = splitter.sync("split 3 gold")
                self.assertIn("You split 3 gold", said)
                for client in (splitter, member, frozen):
                    client.must("save", "Saving")
                self.assertEqual(sum(wealth(mud, n) for n in names), after)
                self.assertEqual((wealth(mud, MEMBER), wealth(mud, FROZEN)), (GOLD, GOLD))
            finally:
                for client in clients:
                    client.close()

            rows = [r for r in journal(mud) if len(r) > 13 and r[2] == SPLITTER
                    and r[1] == "cmd" and r[10] == "split"]
            self.assertEqual([r[13] for r in rows][:4], ["refusal:other-frozen"] * 4)
            self.assertEqual(rows[-1][13], "success:-")
            done = [r for r in journal(mud) if len(r) > 10 and r[1] == "outcome"
                    and r[6] == "split"]
            self.assertEqual(len(done), 1)
            self.assertIn("split=3 gold members=3 share=1", done[0][10])


if __name__ == "__main__":
    unittest.main()

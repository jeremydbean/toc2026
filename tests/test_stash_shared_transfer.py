"""STASH TAKE between linked characters is one transfer (review, 2026-11-03).

The review found the shared stash's TAKE never asked whether the owner's
file was held still by an unsettled death: the object left the frozen
owner's stash in memory, the taker saved it into theirs, and the owner's
refused save left it in their file too -- a copy at the owner's next
login. The two saves were also unchecked, so a failed one either lost
the object or copied it.

STASH TAKE now refuses while either side is held still (looking -- STASH
and STASH OF -- still works), and moves the object as a receipted
transfer: a pending "transfer" record in the recovery ledger, the owner
saved without it, the taker saved with it, the receipt closed. A failed
owner save puts it back; a failed taker save gives it back to the owner;
an unconfirmed save is kept. These tests count each uniquely named
object across both characters' files after every case. Synthetic Z
characters only, in disposable worlds.
"""
from __future__ import annotations

import re
import time
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason
from test_death_unrecorded import kill_server, ledger
from test_death_unrecorded_trade import full_fixes

SKIP = skip_reason()
PW = "Zsbpass1"
OWNER, TAKER, STAFF = "Zsbowner", "Zsbtaker", "Zsbstaff"
ALTAR, BANK = 4208, 4
DAGGER = 3701
FROZEN = "has not been laid to rest yet"


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def copies(mud: LiveMud, name: str, token: str) -> int:
    """Objects in a character's saved file whose name holds `token`."""
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    return len(re.findall(r"^Name [^~\n]*\b%s\b" % token, text, re.M))


def both(mud: LiveMud, token: str) -> tuple[int, int]:
    return copies(mud, OWNER, token), copies(mud, TAKER, token)


def transfers(mud: LiveMud) -> list[list[str]]:
    path = ledger(mud)
    if not path.is_file():
        return []
    rows = [line.split("\t") for line in path.read_text(encoding="latin-1").splitlines()]
    return [r for r in rows if len(r) > 9 and r[2] == "transfer"]


def states_for(mud: LiveMud, token: str) -> list[str]:
    """The transfer states recorded for the operation that moved `token`."""
    rows = transfers(mud)
    ops = {r[6] for r in rows if token in r[9]}
    return [r[3] for r in rows if r[6] in ops]


def outcomes(mud: LiveMud) -> list[list[str]]:
    path = mud.root / "log" / "play.tsv"
    if not path.is_file():
        return []
    rows = [line.split("\t") for line in path.read_text(encoding="latin-1").splitlines()]
    return [r for r in rows if len(r) > 10 and r[1] == "outcome" and r[6] == "stash-take"]


def fault(mud: LiveMud, point: str) -> None:
    (mud.root / "fault.once").write_text(point + "\n", encoding="ascii")


def setup_world(mud: LiveMud, owner_room: int = ALTAR, owner_fixes: str | None = None,
                taker_fixes: str | None = None) -> None:
    make(mud, STAFF, Levl=70, Room=owner_room)
    make(mud, OWNER, Levl=20, Room=owner_room, StashLinks=f"{TAKER}~")
    make(mud, TAKER, Levl=20, Room=ALTAR, StashLinks=f"{OWNER}~")
    for name, fixes in ((OWNER, owner_fixes), (TAKER, taker_fixes)):
        if fixes is None:
            continue
        path = mud.player_dir / name
        text = re.sub(r"^Fixes .*~$", "Fixes " + fixes + "~",
                      path.read_text(encoding="latin-1"), count=1, flags=re.M)
        path.write_text(text, encoding="latin-1")


def hand_over(staff, holder, holder_name: str, token: str) -> None:
    """A dagger named for `token`, from staff into `holder`'s stash."""
    staff.must(f"load obj {DAGGER}", "You create")
    staff.must(f"string obj dagger name {token} dagger", "")
    staff.must(f"string obj {token} short a {token} dagger", "")
    staff.must(f"give {token} {holder_name.lower()}", "You give")
    holder.must(f"stash put {token}", "You put")


ENV = {"TOC_FAULT": "autowrite", "TOC_FAULT_FILE": "../fault.once"}


@unittest.skipIf(SKIP is not None, SKIP or "")
class SharedStashFaultTests(unittest.TestCase):
    def test_transfer_saves_owner_then_taker_and_undoes_a_failed_save(self) -> None:
        with LiveMud(extra_env=ENV) as mud:
            setup_world(mud)
            gems = ("zgema", "zgemb", "zgemc", "zgemd")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as owner:
                login(staff, STAFF, PW)
                login(owner, OWNER, PW)
                staff.sync("scroll 0")
                owner.sync("scroll 0")
                for gem in gems:
                    hand_over(staff, owner, OWNER, gem)
                owner.send("quit")
                self.assertTrue(owner.wait_closed())
            for gem in gems:
                self.assertEqual(both(mud, gem), (1, 0), gem)

            with mud.connect(timeout=120) as taker:
                login(taker, TAKER, PW)
                taker.sync("scroll 0")

                # A plain take: out of the owner's file, into the taker's.
                taker.must(f"stash take {OWNER} zgema", "You take")
                self.assertEqual(both(mud, "zgema"), (0, 1))
                self.assertEqual(states_for(mud, "zgema"), ["pending", "committed"])

                # The owner's save fails: nothing moves.
                fault(mud, "stash-owner-save")
                said = taker.sync(f"stash take {OWNER} zgemb")
                self.assertIn("nothing was taken", said)
                taker.must("save", "Saving")
                self.assertEqual(both(mud, "zgemb"), (1, 0))
                self.assertEqual(states_for(mud, "zgemb"), ["pending", "abandoned"])
                self.assertIn("zgemb", taker.sync(f"stash of {OWNER}"), "back in their stash")

                # The taker's save fails: it goes back to the owner, saved.
                fault(mud, "stash-taker-save")
                said = taker.sync(f"stash take {OWNER} zgemc")
                self.assertIn("went back into their stash", said)
                taker.must("save", "Saving")
                self.assertEqual(both(mud, "zgemc"), (1, 0))
                self.assertEqual(states_for(mud, "zgemc"), ["pending", "abandoned"])

                # The owner's save lands but is not confirmed: never undone.
                fault(mud, f"dirsync-{OWNER}")
                said = taker.sync(f"stash take {OWNER} zgemd")
                self.assertIn("You take", said)
                self.assertIn("not confirmed", said)
                self.assertEqual(both(mud, "zgemd"), (0, 1))
                self.assertEqual(states_for(mud, "zgemd"), ["pending", "committed"])

                taker.send("quit")
                self.assertTrue(taker.wait_closed())

            for gem, where in (("zgema", (0, 1)), ("zgemb", (1, 0)), ("zgemc", (1, 0)),
                               ("zgemd", (0, 1))):
                self.assertEqual(both(mud, gem), where, gem)
            results = [r[7] for r in outcomes(mud)]
            self.assertEqual(results, ["success", "failure", "failure", "uncertain"])

    def test_both_saves_failing_and_a_crash_between_never_make_a_copy(self) -> None:
        env = dict(ENV, TOC_FAULT="autowrite,stash-owner-rewrite")
        with LiveMud(extra_env=env) as mud:
            setup_world(mud)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as owner:
                login(staff, STAFF, PW)
                login(owner, OWNER, PW)
                staff.sync("scroll 0")
                owner.sync("scroll 0")
                hand_over(staff, owner, OWNER, "zgeme")
                hand_over(staff, owner, OWNER, "zgemf")
                owner.send("quit")
                self.assertTrue(owner.wait_closed())

            taker = mud.connect(timeout=120)
            try:
                login(taker, TAKER, PW)
                taker.sync("scroll 0")
                # The taker's save fails and so does putting it back: the
                # owner is an offline copy about to be freed, so the taker
                # holds it, and their next save keeps it.
                fault(mud, "stash-taker-save")
                said = taker.sync(f"stash take {OWNER} zgeme")
                self.assertIn("You hold it", said)
                self.assertEqual(both(mud, "zgeme"), (0, 0), "in memory only, for now")
                self.assertIn("retry", states_for(mud, "zgeme"))
                taker.must("save", "Saving")
                self.assertEqual(both(mud, "zgeme"), (0, 1))

                # A crash between the two saves: in neither file, never both,
                # and the pending receipt names it.
                fault(mud, "stash-crash-between")
                taker.send(f"stash take {OWNER} zgemf")
                deadline = time.monotonic() + 30
                while mud.proc.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.2)
                self.assertIsNotNone(mud.proc.poll(), "the crash point ended the server")
            finally:
                taker.close()
            self.assertEqual(both(mud, "zgemf"), (0, 0))
            self.assertEqual(states_for(mud, "zgemf"), ["pending"])
            self.assertTrue(any("zgemf" in r[9] and OWNER in r[9] and TAKER in r[9]
                                for r in transfers(mud)), "the receipt names both")

            mud.restart()
            with mud.connect(timeout=120) as taker:
                login(taker, TAKER, PW)
                taker.sync("scroll 0")
                taker.must("save", "Saving")
            self.assertEqual(both(mud, "zgeme"), (0, 1), "kept across the restart")
            self.assertEqual(both(mud, "zgemf"), (0, 0))


@unittest.skipIf(SKIP is not None, SKIP or "")
class SharedStashFrozenTests(unittest.TestCase):
    def test_a_frozen_owner_or_taker_moves_nothing_and_can_still_look(self) -> None:
        with LiveMud(extra_env=ENV) as mud:
            setup_world(mud, owner_room=BANK, owner_fixes=full_fixes())
            staff = mud.connect(timeout=120)
            owner = mud.connect(timeout=120)
            taker = mud.connect(timeout=120)
            try:
                login(staff, STAFF, PW)
                login(owner, OWNER, PW)
                login(taker, TAKER, PW)
                for client in (staff, owner, taker):
                    client.sync("scroll 0")
                hand_over(staff, owner, OWNER, "zgemg")
                staff.must(f"goto {ALTAR}", "")
                hand_over(staff, taker, TAKER, "zgemh")
                staff.must(f"goto {BANK}", "")
                self.assertEqual(both(mud, "zgemg"), (1, 0))
                self.assertEqual(both(mud, "zgemh"), (0, 1))

                # An unsettled death: the owner's saves are refused from now.
                staff.must(f"slay {OWNER.lower()}", "")
                staff.must(f"transfer {OWNER.lower()} {ALTAR}", "Ok.")

                # The healthy partner cannot take from the frozen owner ...
                said = taker.sync(f"stash take {OWNER} zgemg")
                self.assertIn(FROZEN, said)
                self.assertNotIn("You take", said)
                # ... but may still look.
                self.assertIn("zgemg", taker.sync(f"stash of {OWNER}"))

                # The frozen owner cannot take from the partner, nor put away,
                # nor take out -- but sees their own stash and the partner's.
                self.assertIn(FROZEN, owner.sync(f"stash take {TAKER} zgemh"))
                self.assertIn(FROZEN, owner.sync("stash get zgemg"))
                self.assertIn("zgemg", owner.sync("stash"))
                self.assertIn("zgemh", owner.sync(f"stash of {TAKER}"))

                taker.must("save", "Saving")
                owner.send("quit")
                self.assertTrue(owner.wait_closed())
                owner.close()
                owner = mud.connect(timeout=120)
                login(owner, OWNER, PW)
                owner.sync("scroll 0")
                owner.must("save", "Saving")
                taker.must("save", "Saving")
            finally:
                for client in (staff, owner, taker):
                    client.close()
            self.assertEqual(both(mud, "zgemg"), (1, 0), "one copy, the owner's")
            self.assertEqual(both(mud, "zgemh"), (0, 1), "one copy, the partner's")
            self.assertEqual([r for r in transfers(mud)], [], "nothing was even begun")


if __name__ == "__main__":
    unittest.main()

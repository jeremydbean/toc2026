"""The independent review of f1388da0..ed292882 (2026-11-09).

1. "Connect anyway?" answered after the holder changed their password took
   the character on a credential that no longer stood. The descriptor keeps
   a fingerprint of the hash it was let in against (auth_fp); the yes is
   checked against the character as the game holds it now -- playing,
   link-dead, switched out of, or at its MOTD -- and asks for the password
   again, disturbing nobody, when it differs. Deny, ban, wizlock and a
   lockout are asked again too.
2. A password beginning with '!' was accepted by PASSWORD and creation,
   and login replaced it with the previous line (command history). The
   password prompts take a line whole and never keep it as history.
3. An unreadable lockout file was taken for an absent one and replaced by
   the next lockout. It is now left alone until a boot reads it whole.
5. The fifteen-minute window measured a gap between failures instead of
   fifteen minutes (tests/test_lock_window.c, run here, holds the clock).
6. The healer called its cap on castings an empty purse.

Synthetic Z fixtures in throwaway worlds; Killuminati is the synthetic
creator a test world needs for creator-only commands (AGENTS.md).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from live_mud import (LiveMud, SPARRING_FLOOR, SPARRING_GUARD, create_character, login,
                      patch_player_file, skip_reason)
from test_mudlet_extras import gmcp, mudlet_hello, wait_gmcp

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
CC = os.environ.get("CC", "cc").split()[-1]
ALTAR = 4208


def quit_out(client) -> None:
    client.sync("save")
    client.send("quit")
    assert client.wait_closed(30), "quit did not close the connection"


def make(mud: LiveMud, name: str, password: str, **fields) -> None:
    with mud.connect() as client:
        create_character(client, name, password)
        quit_out(client)
    if fields:
        patch_player_file(mud, name, **fields)


def to_connect_anyway(mud: LiveMud, name: str, password: str):
    """A second connection that gives the right password while the
    character is held, and is asked whether to connect anyway."""
    other = mud.connect()
    other.expect("by what name", "name:")
    other.send(name)
    other.expect("password")
    other.send(password)
    other.expect("connect anyway", timeout=30)
    return other


def still_connected(client) -> bool:
    try:
        client.sync("time", timeout=20)
        return True
    except AssertionError:
        return False


# --- 1. "connect anyway?" ----------------------------------------------------

@unittest.skipIf(SKIP is not None, SKIP or "")
class ConnectAnywayTests(unittest.TestCase):

    def assert_asked_again(self, other, holder) -> None:
        other.send("y")
        other.expect("password has changed since you gave it", timeout=30)
        self.assertTrue(still_connected(holder), "the holder was disconnected")

    def test_online_password_change_is_asked_again(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zcaonline", "Zcapass11")
            holder = mud.connect()
            login(holder, "Zcaonline", "Zcapass11")
            other = to_connect_anyway(mud, "Zcaonline", "Zcapass11")
            holder.must("password Zcapass11 Zcapass22", "Ok.")
            self.assert_asked_again(other, holder)
            # The old password is refused at the prompt it was sent back to.
            other.send("Zcapass11")
            other.expect("wrong password", timeout=30)
            self.assertTrue(other.wait_closed(30))
            self.assertTrue(still_connected(holder))
            # The new one, answered yes, takes over as it always did.
            taker = to_connect_anyway(mud, "Zcaonline", "Zcapass22")
            taker.send("y")
            taker.expect("reconnecting", timeout=30)
            self.assertTrue(holder.wait_closed(30), "the holder was not replaced")
            quit_out(taker)

    def test_link_dead_after_the_change(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zcalinkd", "Zcapass11")
            holder = mud.connect()
            login(holder, "Zcalinkd", "Zcapass11")
            other = to_connect_anyway(mud, "Zcalinkd", "Zcapass11")
            holder.must("password Zcapass11 Zcapass22", "Ok.")
            holder.close()                              # link-dead, still in the game
            time.sleep(1.0)
            other.send("y")
            other.expect("password has changed since you gave it", timeout=30)
            other.send("Zcapass22")
            other.expect("reconnecting", timeout=30)
            quit_out(other)

    def test_switched_holder(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zcaswitch", "Zcapass11", Levl=70, Room=SPARRING_FLOOR)
            holder = mud.connect()
            login(holder, "Zcaswitch", "Zcapass11")
            holder.must(f"load mob {SPARRING_GUARD}", "You create")
            holder.must("switch guard", "Possessed")
            other = to_connect_anyway(mud, "Zcaswitch", "Zcapass11")
            holder.must("return", "old self", "human once")
            holder.must("password Zcapass11 Zcapass22", "Ok.")
            holder.must("switch guard", "Possessed")
            self.assert_asked_again(other, holder)
            other.close()
            # Unchanged, a switched holder is taken over as before.
            taker = to_connect_anyway(mud, "Zcaswitch", "Zcapass22")
            taker.send("y")
            taker.expect("reconnecting", timeout=30)
            self.assertTrue(holder.wait_closed(30))
            quit_out(taker)

    def test_motd_stage_holder_then_changed(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zcamotd", "Zcapass11")
            holder = mud.connect()
            holder.expect("by what name", "name:")
            holder.send("Zcamotd")
            holder.expect("password")
            holder.send("Zcapass11")
            holder.expect("motd", "press", "continue", timeout=30)
            # Asked while the holder sits at the MOTD...
            other = to_connect_anyway(mud, "Zcamotd", "Zcapass11")
            # ...who then goes in and changes the password.
            login_rest = holder
            login_rest.send("")
            login_rest.drain(1.0)
            login_rest.send("")
            login_rest.must("password Zcapass11 Zcapass22", "Ok.")
            self.assert_asked_again(other, holder)
            other.close()
            quit_out(holder)

    def test_admission_is_asked_again(self) -> None:
        with LiveMud() as mud:
            make(mud, "Killuminati", "Zcreatorpw1", Levl=70)
            make(mud, "Zcawizlock", "Zcapass11")
            holder = mud.connect()
            login(holder, "Zcawizlock", "Zcapass11")
            other = to_connect_anyway(mud, "Zcawizlock", "Zcapass11")
            with mud.connect() as creator:
                login(creator, "Killuminati", "Zcreatorpw1")
                creator.must("wizlock", "Game Wizlocked.")
                other.send("y")
                other.expect("wizlocked", timeout=30)
                self.assertTrue(other.wait_closed(30))
                self.assertTrue(still_connected(holder), "a refused yes disturbed the holder")
                creator.must("wizlock", "Wizlock removed.")
                quit_out(creator)
            quit_out(holder)


class ConnectAnywaySourceTests(unittest.TestCase):
    def test_the_yes_is_checked_before_anybody_is_closed(self) -> None:
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        body = comm[comm.index("    case CON_BREAK_CONNECT:"):]
        body = body[:body.index("    case CON_CONFIRM_NEW_NAME:")]
        check = body.index("connect_anyway_still_allowed( d, ch )")
        self.assertLess(check, body.index("close_socket(d_old)"))
        allowed = comm[comm.index("static bool connect_anyway_still_allowed("):]
        allowed = allowed[:allowed.index("\n}\n")]
        for need in ("credential_fingerprint( holder->pcdata->pwd ) != d->auth_fp",
                     "PLR_DENY", "check_ban( d, BAN_ALL )", "wizlock", "login_lock_remaining( d )"):
            self.assertIn(need, allowed)
        # A fingerprint of the stored hash is kept, never the password.
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        self.assertIn("unsigned long       auth_fp;", merc)


# --- 2. '!' at the start of a password ----------------------------------------

@unittest.skipIf(SKIP is not None, SKIP or "")
class BangPasswordTests(unittest.TestCase):
    def test_password_create_gmcp_and_history(self) -> None:
        with LiveMud() as mud:
            # PASSWORD to a '!' password, quit, and log in with it.
            make(mud, "Zbangpass", "Zoldpass1")
            with mud.connect() as client:
                login(client, "Zbangpass", "Zoldpass1")
                client.must("password Zoldpass1 !Znewpass1", "Ok.")
                # '!' still repeats a command in the game. (Sent bare: sync
                # types TIME around a line, which '!' would repeat.)
                mark = len(client.transcript)
                client.send("say hello there")
                client.send("!")
                client.drain(2.0)
                self.assertEqual(client.transcript[mark:].count("hello there"), 2,
                                 client.transcript[mark:])
                quit_out(client)
            with mud.connect() as client:
                login(client, "Zbangpass", "!Znewpass1")
                # The password was never kept as the last command.
                mark = len(client.transcript)
                client.send("!")
                client.drain(2.0)
                self.assertNotIn("Znewpass1", client.transcript[mark:])
                quit_out(client)

            # A new character made with one, and logged into again.
            with mud.connect() as client:
                create_character(client, "Zbangnew", "!Zbangnew1")
                quit_out(client)
            with mud.connect() as client:
                login(client, "Zbangnew", "!Zbangnew1")
                quit_out(client)

            # Mudlet's saved login types it at the same prompt.
            m = mud.connect()
            m.expect("by what name")
            mudlet_hello(m, '[ "Char 1", "Char.Login 1" ]')
            wait_gmcp(m, "Char.Login.Default")
            gmcp(m, "Char.Login.Credentials",
                 json.dumps({"account": "Zbangpass", "password": "!Znewpass1"}))
            self.assertEqual(json.loads(wait_gmcp(m, "Char.Login.Result")), {"success": True})
            m.expect("motd", timeout=30)
            m.send("")
            m.sync("time")
            quit_out(m)

            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            for secret in ("Znewpass1", "Zbangnew1", "Zoldpass1"):
                self.assertNotIn(secret, log)


class BangPasswordSourceTests(unittest.TestCase):
    def test_the_password_prompts_are_kept_out_of_history(self) -> None:
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        helper = comm[comm.index("static bool descriptor_reads_password("):]
        helper = helper[:helper.index("\n}\n")]
        for state in ("CON_GET_OLD_PASSWORD", "CON_GET_NEW_PASSWORD", "CON_CONFIRM_NEW_PASSWORD"):
            self.assertIn(state, helper)
        body = comm[comm.index("bool read_from_buffer( DESCRIPTOR_DATA *d )"):]
        body = body[:body.index("\n}\n")]
        self.assertIn("if ( !from_alias && !secret && ( k > 1 || d->incomm[0] == '!' )", body)
        self.assertIn("if ( !from_alias && !secret )", body)


# --- 3. the lockout file ------------------------------------------------------

LOCK_RECORD = "203.0.113.7\t{until}\t1\t{last}\n"


@unittest.skipIf(SKIP is not None, SKIP or "")
class LockFileTests(unittest.TestCase):
    ENV = {"TOC_THROTTLE_LOOPBACK": "1", "TOC_LOGIN_LOCK_SECS": "30"}

    def lock_out_loopback(self, mud: LiveMud, name: str) -> None:
        for _ in range(5):
            with mud.connect(timeout=60) as client:
                first = client.expect("by what name", "too many failed login", timeout=60)
                if first == "too many failed login":
                    return
                client.send(name)
                client.expect("password", timeout=60)
                client.send("Zwrongpw99")
                client.expect("wrong password", timeout=60)

    def record(self) -> str:
        now = int(time.time())
        return "# planted\n" + LOCK_RECORD.format(until=now + 3600, last=now)

    def test_an_unopenable_file_is_never_written_over(self) -> None:
        with LiveMud(extra_env=self.ENV) as mud:
            make(mud, "Zlockfile", "Zlockpass1")
            path = mud.root / "log" / "login_lockouts.tsv"
            # A symbolic link to itself: there, and opening it fails
            # (ELOOP) whoever runs the test.
            path.symlink_to(path.name)
            mud.restart()
            self.lock_out_loopback(mud, "Zlockfile")
            self.assertTrue(path.is_symlink(), "the unreadable file was replaced")
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            self.assertIn("Login lockout: could not read", log)
            self.assertIn("Login lockout: not written", log)
            self.assertFalse((mud.root / "log" / "login_lockouts.tsv.tmp").exists())

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0,
                     "root reads a mode-000 file; CI's runner is not root")
    def test_a_permission_failure_keeps_the_file(self) -> None:
        with LiveMud(extra_env=self.ENV) as mud:
            make(mud, "Zlockperm", "Zlockpass1")
            path = mud.root / "log" / "login_lockouts.tsv"
            planted = self.record()
            path.write_text(planted)
            path.chmod(0)
            try:
                mud.restart()
                self.lock_out_loopback(mud, "Zlockperm")
            finally:
                path.chmod(0o600)
            self.assertEqual(path.read_text(), planted)

    def test_a_partial_read_keeps_the_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="toc-fault-") as tmp:
            fault = Path(tmp) / "fault"
            env = dict(self.ENV, TOC_FAULT_FILE=str(fault))
            with LiveMud(extra_env=env) as mud:
                make(mud, "Zlockpart", "Zlockpass1")
                make(mud, "Zlockstaff", "Zstaffpw11", Levl=70)
                path = mud.root / "log" / "login_lockouts.tsv"
                now = int(time.time())
                planted = self.record() + LOCK_RECORD.replace("203.0.113.7", "198.51.100.9").format(
                    until=now + 3600, last=now)
                path.write_text(planted)
                fault.write_text("lockfile-read\n")
                mud.restart()
                # Staff are told the file is not being kept (before the
                # lockout below shuts loopback out).
                with mud.connect() as staff:
                    login(staff, "Zlockstaff", "Zstaffpw11")
                    self.assertIn("NOT KEPT", staff.must("dns guard", "Login lockouts"))
                    quit_out(staff)
                self.lock_out_loopback(mud, "Zlockpart")
                self.assertEqual(path.read_text(), planted, "a file read in part was replaced")
                log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
                self.assertIn("was read only in part (1 address)", log)
                self.assertIn("Login lockout: not written", log)

    def test_a_readable_file_is_kept_and_extended(self) -> None:
        with LiveMud(extra_env=self.ENV) as mud:
            make(mud, "Zlockgood", "Zlockpass1")
            path = mud.root / "log" / "login_lockouts.tsv"
            path.write_text(self.record())
            mud.restart()
            self.lock_out_loopback(mud, "Zlockgood")
            text = path.read_text()
            self.assertIn("203.0.113.7\t", text, "the planted lockout survived")
            self.assertIn("127.0.0.1\t", text, "and the new one was written")


# --- 5. the rolling window ----------------------------------------------------

@unittest.skipIf(shutil.which(CC) is None, "no C compiler")
class LockWindowHarnessTests(unittest.TestCase):
    def test_the_harness_passes_in_both_standards(self) -> None:
        for std in ("gnu89", "c17"):
            with self.subTest(std=std), tempfile.TemporaryDirectory() as tmp:
                binary = Path(tmp) / "test_lock_window"
                build = subprocess.run(
                    [CC, f"-std={std}", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "src"),
                     "-o", str(binary), str(ROOT / "tests" / "test_lock_window.c"),
                     str(ROOT / "src" / "lockwindow.c")],
                    capture_output=True, text=True)
                self.assertEqual(build.returncode, 0, build.stderr)
                run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=60)
                self.assertEqual(run.stdout.strip(), "ok", run.stdout)


class LockWindowSourceTests(unittest.TestCase):
    def test_the_window_is_the_one_rule(self) -> None:
        lock = (ROOT / "src" / "loginlock.c").read_text(encoding="latin-1")
        self.assertIn("lock_window_add( &e->win, (long) current_time, LOCK_WINDOW_SECS, name )", lock)
        self.assertIn("lock_window_forget_name( &e->win, ch->name )", lock)
        # The gap test that reset the count is gone.
        self.assertNotIn("current_time - e->last_fail > LOCK_WINDOW", lock)
        self.assertNotIn('#include "merc.h"',
                         (ROOT / "src" / "lockwindow.c").read_text(encoding="latin-1"))
        self.assertIn("src/lockwindow.c", (ROOT / "CMakeLists.txt").read_text(encoding="utf-8"))


# --- 6. the healer's limit ------------------------------------------------------

@unittest.skipIf(SKIP is not None, SKIP or "")
class HealerLimitTests(unittest.TestCase):
    def test_a_full_pool_of_mana_fills_in_one_go(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zhealstaff", "Zstaffpw11", Levl=70)
            make(mud, "Zhealbig", "Zhealpw111", Levl=20, Room=ALTAR)
            with mud.connect() as staff, mud.connect() as player:
                login(staff, "Zhealstaff", "Zstaffpw11")
                login(player, "Zhealbig", "Zhealpw111")
                staff.must("set char zhealbig mana 30000", "")
                staff.must("set char zhealbig platinum 100000", "Platinum amount")
                said = player.must("heal mana", "your mind is full", "as many castings", "pay for")
                self.assertIn("your mind is full", said, "30,000 mana in one HEAL MANA")
                casts = int(re.search(r"\((\d+) castings?, ", said).group(1))
                self.assertGreater(casts, 100, "past the old cap of a hundred")
                quit_out(player)
                quit_out(staff)


class HealerSourceTests(unittest.TestCase):
    def test_three_reasons_three_answers(self) -> None:
        misc = (ROOT / "src" / "misc.c").read_text(encoding="latin-1")
        self.assertIn("that is all you can pay for.", misc)
        self.assertIn("that is as many castings as I give at once -- ask again for more.", misc)
        self.assertIn(", and your mind is full.", misc)
        self.assertIn("#define HEALER_MAX_CASTINGS 5000", misc)


if __name__ == "__main__":
    unittest.main()

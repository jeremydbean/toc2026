"""Passwords move to SHA-512 without a player noticing (owner, 2026-11-07).

"Let's move passwords to SHA-512. We don't want to mess up the player
experience, so make this extremely seamless for all players in all
circumstances and be extra careful. You can give them a notification at
first login telling them the password encryption has been updated."

src/password.c (see password.h):

- a new password -- creation, PASSWORD, RESETPWD -- is SHA-512 crypt, and
  every character of it counts;
- an old DES hash is moved to SHA-512 at the player's next login, as the
  SHA-512 crypt of the password as DES saw it (its first eight characters),
  marked by a salt starting ".8": whatever DES let in still gets in, and
  nothing else does -- so nothing a player types changes;
- they are told once, at that login; the move is logged;
- the SHA-512 is our own, checked against the specification's vectors at
  boot and against libxcrypt here, so a hash the game wrote is readable on
  any machine; if the self-test ever fails the game stays on DES.

tests/test_password.c checks the module against the system's libxcrypt;
the live tests below play every way a player meets a password.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, skip_reason

ROOT = Path(__file__).resolve().parents[1]
CC = os.environ.get("CC", "cc").split()[-1]
SKIP = skip_reason()


def _libcrypt():
    """The system's crypt(), wherever this platform keeps it: libxcrypt on
    Linux, libSystem on macOS (review, 2026-11-09: libcrypt.so.1 was
    assumed, and every password test failed on a Mac the game builds on)."""
    name = ctypes.util.find_library("crypt")
    if name is None:
        name = "/usr/lib/libSystem.B.dylib" if sys.platform == "darwin" else "libcrypt.so.1"
    lib = ctypes.CDLL(name)
    lib.crypt.restype = ctypes.c_char_p
    lib.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    return lib


def system_reads_sha512() -> bool:
    """Whether the system's crypt() reads SHA-512 crypt. libxcrypt does;
    macOS's reads DES alone."""
    out = _libcrypt().crypt(b"Zprobe", b"$6$saltsaltsalt")
    return out is not None and out.startswith(b"$6$saltsaltsalt$")


def crypt_link_flags() -> list[str]:
    """What the C harness links to reach crypt(): -lcrypt where libxcrypt
    is a library of its own, nothing on macOS (it is in libSystem), as the
    Makefile does."""
    return [] if sys.platform == "darwin" else ["-lcrypt"]


def des_hash(password: str, salt: str) -> str:
    """The hash every character had before: DES, salted with the name."""
    out = _libcrypt().crypt(password.encode("latin-1"), salt.encode("latin-1"))
    assert out is not None and len(out) == 13, out
    return out.decode("latin-1")


def stored_pass(mud: LiveMud, name: str) -> str:
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    match = re.search(r"(?m)^Pass (.*)~$", text)
    assert match, "no Pass line"
    return match.group(1)


def set_pass(mud: LiveMud, name: str, value: str) -> None:
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    text, n = re.subn(r"(?m)^Pass .*~$", lambda _m: "Pass %s~" % value, text)
    assert n == 1
    path.write_text(text, encoding="latin-1", newline="")


@unittest.skipIf(shutil.which(CC) is None, "no C compiler")
class PasswordHarnessTests(unittest.TestCase):
    def test_the_harness_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "test_password"
            build = subprocess.run(
                [CC, "-O2", "-std=gnu89", "-Wall", "-Werror", "-I", str(ROOT / "src"),
                 "-o", str(binary), str(ROOT / "tests" / "test_password.c"),
                 str(ROOT / "src" / "password.c"), *crypt_link_flags()],
                capture_output=True, text=True)
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=300)
        failed = [line for line in run.stdout.splitlines() if line.startswith("FAIL")]
        self.assertEqual(failed, [], run.stdout[-4000:])
        self.assertEqual(run.returncode, 0, run.stdout[-4000:])
        self.assertEqual(run.stdout.strip(), "ok")


class PasswordSourceTests(unittest.TestCase):
    def test_every_password_goes_through_the_module(self) -> None:
        for path in sorted((ROOT / "src").glob("*.c")):
            if path.name == "password.c":
                continue
            code = path.read_text(encoding="latin-1")
            code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
            self.assertNotRegex(code, r"\bcrypt\s*\(", path.name)
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        self.assertEqual(comm.count("password_matches( "), 4)
        self.assertIn("password_hash( argument, ch->name", comm)
        self.assertIn("login_password_upgrade( d, who );", comm)
        info = (ROOT / "src" / "act_info.c").read_text(encoding="latin-1")
        self.assertEqual(info.count("password_matches( arg1, ch->pcdata->pwd )"), 4)
        self.assertIn("password_hash( arg2, ch->name", info)
        self.assertIn("password_matches( argument, ch->pcdata->pwd )",
                      (ROOT / "src" / "act_comm.c").read_text(encoding="latin-1"))
        self.assertIn("password_hash( arg_pwd,",
                      (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1"))
        self.assertIn("src/password.c", (ROOT / "CMakeLists.txt").read_text(encoding="utf-8"))
        self.assertNotIn('#include "merc.h"',
                         (ROOT / "src" / "password.c").read_text(encoding="latin-1"))


@unittest.skipIf(SKIP is not None, SKIP or "")
class PasswordLiveTests(unittest.TestCase):
    """Synthetic Z fixtures in a throwaway world."""

    @staticmethod
    def _quit(client) -> None:
        """Out of the game for certain: a character left link-dead keeps
        the password it had, which the next login is checked against."""
        client.sync("save")
        client.send("quit")
        assert client.wait_closed(30), "quit did not close the connection"

    def _make(self, mud: LiveMud, name: str, password: str) -> None:
        with mud.connect() as client:
            create_character(client, name, password)
            self._quit(client)

    def _login(self, mud: LiveMud, name: str, password: str) -> str:
        with mud.connect() as client:
            login(client, name, password)
            client.sync("time")
            transcript = client.transcript
            self._quit(client)
        return transcript

    def _refused(self, mud: LiveMud, name: str, password: str) -> bool:
        with mud.connect() as client:
            client.expect("by what name", "name:")
            client.send(name)
            client.expect("password")
            client.send(password)
            said = client.expect("wrong password", "mv>", "[hit return", "press enter",
                                 "connect anyway", timeout=30)
            return said == "wrong password"

    def test_a_new_character_gets_sha512(self) -> None:
        with LiveMud() as mud:
            self._make(mud, "Zpwnew", "Zfreshpass99")
            stored = stored_pass(mud, "Zpwnew")
            self.assertTrue(stored.startswith("$6$"), stored)
            self.assertFalse(stored.startswith("$6$.8"), "a new password is not a moved one")
            self.assertEqual(len(stored), 106)
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            self.assertIn("Passwords: SHA-512 crypt self-test passed.", log)
            # Every character counts now.
            self.assertTrue(self._refused(mud, "Zpwnew", "Zfreshpa"))
            self.assertNotIn("stronger encryption", self._login(mud, "Zpwnew", "Zfreshpass99"))

    def test_an_old_password_moves_at_login_and_nothing_changes(self) -> None:
        with LiveMud() as mud:
            self._make(mud, "Zpwold", "Zwhatever1")
            set_pass(mud, "Zpwold", des_hash("Zlongpassw0rd", "Zp"))

            first = self._login(mud, "Zpwold", "Zlongpassw0rd")
            self.assertIn("now kept with stronger encryption", first)
            self.assertIn("log in exactly as you always have", first)
            # Boxed, in the unread-notes notice's colours (owner, 2026-11-07).
            self.assertIn("+------------------------------------------------------------+", first)
            self.assertRegex(first, r"\| log in exactly as you always have\. +\|")
            moved = stored_pass(mud, "Zpwold")
            self.assertTrue(moved.startswith("$6$.8"), moved)
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            self.assertIn("Passwords: Zpwold's password moved to SHA-512.", log)
            self.assertNotIn(moved, log)

            # Told once.
            second = self._login(mud, "Zpwold", "Zlongpassw0rd")
            self.assertNotIn("stronger encryption", second)
            self.assertEqual(stored_pass(mud, "Zpwold"), moved, "moved once")

            # Exactly what DES let in still gets in: the first eight,
            # and anything after them.
            self._login(mud, "Zpwold", "Zlongpas")
            self._login(mud, "Zpwold", "ZlongpasSOMETHINGELSE")
            # And nothing else does.
            self.assertTrue(self._refused(mud, "Zpwold", "Zlongpaz"))
            self.assertTrue(self._refused(mud, "Zpwold", "zlongpassw0rd"))

    def test_a_short_old_password_and_a_restart(self) -> None:
        with LiveMud() as mud:
            self._make(mud, "Zpwshort", "Zwhatever1")
            set_pass(mud, "Zpwshort", des_hash("Zsh0rt", "Zp"))
            self.assertIn("stronger encryption", self._login(mud, "Zpwshort", "Zsh0rt"))
            moved = stored_pass(mud, "Zpwshort")
            # The system's own crypt reads it: code from before this change,
            # put back by a rollback, still lets them in. (Where the system
            # reads SHA-512 at all: libxcrypt on Linux, which is where the
            # game is deployed; macOS's reads DES alone.)
            if sys.platform.startswith("linux") or system_reads_sha512():
                self.assertEqual(
                    _libcrypt().crypt(b"Zsh0rt", moved.encode()).decode(), moved)
            mud.restart()
            self.assertNotIn("stronger encryption", self._login(mud, "Zpwshort", "Zsh0rt"))
            self.assertTrue(self._refused(mud, "Zpwshort", "Zsh0rx"))

    def test_a_wrong_password_moves_nothing(self) -> None:
        with LiveMud() as mud:
            self._make(mud, "Zpwwrong", "Zwhatever1")
            des = des_hash("Zrightpw1", "Zp")
            set_pass(mud, "Zpwwrong", des)
            self.assertTrue(self._refused(mud, "Zpwwrong", "Zwrongpw1"))
            self.assertEqual(stored_pass(mud, "Zpwwrong"), des)

    def test_password_command_after_the_move_counts_every_character(self) -> None:
        with LiveMud() as mud:
            self._make(mud, "Zpwchange", "Zwhatever1")
            set_pass(mud, "Zpwchange", des_hash("Zoldpassword", "Zp"))
            with mud.connect() as client:
                login(client, "Zpwchange", "Zoldpass")      # the first eight, as DES allowed
                self.assertIn("stronger encryption", client.transcript)
                client.must("password Zoldpass Znewpassword9", "Ok.")
                self._quit(client)
            stored = stored_pass(mud, "Zpwchange")
            self.assertTrue(stored.startswith("$6$") and not stored.startswith("$6$.8"), stored)
            self.assertTrue(self._refused(mud, "Zpwchange", "Znewpass"))
            self.assertTrue(self._refused(mud, "Zpwchange", "Zoldpassword"))
            self.assertNotIn("stronger encryption", self._login(mud, "Zpwchange", "Znewpassword9"))

    def test_a_reconnect_after_the_move(self) -> None:
        with LiveMud() as mud:
            self._make(mud, "Zpwlink", "Zwhatever1")
            set_pass(mud, "Zpwlink", des_hash("Zlinkpassword", "Zp"))
            client = mud.connect()
            login(client, "Zpwlink", "Zlinkpassword")
            self.assertIn("stronger encryption", client.transcript)
            client.sync("time")
            client.close()                                  # link-dead, still in the game
            with mud.connect() as again:
                login(again, "Zpwlink", "Zlinkpas")         # the first eight
                self.assertNotIn("stronger encryption", again.transcript)
                self._quit(again)
            self.assertTrue(stored_pass(mud, "Zpwlink").startswith("$6$.8"))


if __name__ == "__main__":
    unittest.main()

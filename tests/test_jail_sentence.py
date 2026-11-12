"""JAIL's sentence: kept across everything, released only by staff or the
term staff set, and changed only by a save that landed (owner,
2026-11-12; src/jail.c).

  jail <player> status | indefinite | 30m | 2h | 7d | <days> | release | 0

Played here, live, each in a throwaway world with synthetic Z characters:
link loss, quit and login, a reboot, a saved room outside the cell or
nowhere at all, a term replaced from now, an indefinite one, release
leaving every restriction and the title the sentence did not impose,
expiry at login and online with nothing typed, a deadline past 2038, a
malformed one, a legacy file (no JailInfo, Jw_Timer 0), failed and
unconfirmed saves of a jail, a release and an expiry, offline targets,
bad durations, rank, a target at the password prompt, an unseen one and
a switched one.
"""
from __future__ import annotations

import re
import time
import unittest

from live_mud import (
    LiveMud,
    _enter_game,
    create_character,
    login,
    patch_player_file,
    room_of,
    skip_reason,
)

SKIP = skip_reason()
PW = "Zjailpw12"
CELL = 3
TEMPLE = 4207
SPARRING_GUARD = 32700

PLR_WARNED = 1 << 28
PLR_JAILED = 1 << 29
PLR_EXCON = 1 << 30
COMM_NOCHANNELS = 1 << 22
COMM_NOTITLE = 1 << 26

FAULT_ENV = {"TOC_FAULT_FILE": "../fault.once", "TOC_FAULT": "autowrite"}


def make(mud: LiveMud, name: str, level: int, room: int = TEMPLE, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed(), name
    patch_player_file(mud, name, Levl=level, Room=room, **fields)


def text(mud: LiveMud, name: str) -> str:
    return (mud.player_dir / name).read_text(encoding="latin-1")


def field(mud: LiveMud, name: str, key: str) -> str | None:
    for line in text(mud, name).split("\n"):
        if line.split(" ")[0] == key:
            return line[len(key):].strip()
    return None


def number(mud: LiveMud, name: str, key: str) -> int:
    value = field(mud, name, key)
    return int(value) if value is not None else 0


def drop_line(mud: LiveMud, name: str, key: str) -> None:
    path = mud.player_dir / name
    lines = [line for line in path.read_text(encoding="latin-1").split("\n")
             if line.split(" ")[0] != key]
    path.write_text("\n".join(lines), encoding="latin-1", newline="")


def fault(mud: LiveMud, point: str) -> None:
    (mud.root / "fault.once").write_text(point + "\n")


def quit_client(client) -> None:
    client.send("quit")
    assert client.wait_closed()


def boot_finished(mud: LiveMud) -> None:
    with mud.connect(timeout=120) as probe:
        probe.expect("by what name", "name:")


@unittest.skipIf(SKIP is not None, SKIP or "")
class SentenceKeepsTests(unittest.TestCase):
    def test_kept_through_link_loss_quit_reboot_and_changed_only_by_staff(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zwarden", 70)
            make(mud, "Zkept", 20)
            make(mud, "Zclean", 20)
            with mud.connect(timeout=120) as warden, mud.connect(timeout=120) as kept:
                login(warden, "Zwarden", PW)
                login(kept, "Zkept", PW)
                kept.must("title the Unbowed", "Ok", "title")
                # Restrictions and history that are not the sentence's.
                warden.must("nochannels zkept", "NO_CHANNEL flag set")
                warden.must("warn zkept", "WARNING flag set")
                warden.must("jail zkept 2h", "now in jail")
                self.assertEqual(CELL, room_of(warden, "Zkept"))
                act = number(mud, "Zkept", "Act")
                self.assertTrue(act & PLR_JAILED and act & PLR_WARNED, act)
                self.assertIn("the Unbowed", field(mud, "Zkept", "Titl"))
                self.assertIn(" 2 Zwarden", field(mud, "Zkept", "JailInfo"))
                deadline = number(mud, "Zkept", "Jw_Timer")
                self.assertAlmostEqual(deadline, time.time() + 7200, delta=120)
                # Staff take the sentence's notitle off and put their own on.
                warden.must("notitle zkept", "NO_TITLE flag removed")
                warden.must("notitle zkept", "NO_TITLE flag added")
                self.assertIn("imposed: nothing", warden.sync("jail zkept status"))

                # Link loss, and back.
                kept.close()
                time.sleep(2)
                self.assertIn("(link-dead)", warden.sync("jail zkept status"))
            with mud.connect(timeout=120) as warden, mud.connect(timeout=120) as kept:
                login(warden, "Zwarden", PW)
                login(kept, "Zkept", PW)
                self.assertEqual(CELL, room_of(warden, "Zkept"))
                quit_client(kept)
                self.assertIn("(offline)", warden.sync("jail zkept status"))
                quit_client(warden)

            # A reboot: the same deadline, the same cell.
            mud.restart()
            boot_finished(mud)
            self.assertEqual(deadline, number(mud, "Zkept", "Jw_Timer"))
            with mud.connect(timeout=120) as warden, mud.connect(timeout=120) as kept:
                login(warden, "Zwarden", PW)
                login(kept, "Zkept", PW)
                self.assertIn("You are jailed until", kept.transcript)
                self.assertEqual(CELL, room_of(warden, "Zkept"))
                self.assertEqual(deadline, number(mud, "Zkept", "Jw_Timer"))
                self.assertIn("is jailed (online) until", warden.sync("jail zkept status"))

                # A new term replaces the old one from now.
                self.assertIn("old term replaced", warden.sync("jail zkept 30m"))
                self.assertAlmostEqual(number(mud, "Zkept", "Jw_Timer"),
                                       time.time() + 1800, delta=120)
                # Indefinite is its own value, never an old timestamp.
                warden.must("jail zkept indefinite", "indefinitely")
                self.assertEqual("-1", field(mud, "Zkept", "Jw_Timer"))
                self.assertIn("indefinitely, until staff release",
                              warden.sync("jail zkept status"))
                self.assertIn("until staff release you", kept.sync("score"))

                # Release lifts the sentence and nothing else.
                warden.must("jail zkept release", "released from jail")
                self.assertEqual(TEMPLE, room_of(warden, "Zkept"))
                act = number(mud, "Zkept", "Act")
                comm = number(mud, "Zkept", "Comm")
                self.assertFalse(act & PLR_JAILED)
                self.assertTrue(act & PLR_WARNED and act & PLR_EXCON, act)
                self.assertTrue(comm & COMM_NOCHANNELS, "a nochannel staff gave before")
                self.assertTrue(comm & COMM_NOTITLE, "a notitle staff gave during")
                self.assertIn("the Unbowed", field(mud, "Zkept", "Titl"))
                self.assertEqual("0", field(mud, "Zkept", "Jw_Timer"))
                self.assertIsNone(field(mud, "Zkept", "JailInfo"))
                self.assertIn("isn't in jail", warden.sync("jail zkept release"))

                # What a sentence imposed itself it takes away again.
                warden.must("jail zclean 1d", "now in jail")
                comm = number(mud, "Zclean", "Comm")
                self.assertTrue(comm & COMM_NOCHANNELS and comm & COMM_NOTITLE)
                warden.must("jail zclean 0", "released from jail")
                comm = number(mud, "Zclean", "Comm")
                self.assertFalse(comm & (COMM_NOCHANNELS | COMM_NOTITLE), comm)

    def test_saved_room_offline_commands_and_expiry(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zwarden", 70)
            make(mud, "Zaway", 20)
            make(mud, "Zexpired", 20)
            make(mud, "Zsoon", 20)
            make(mud, "Zfuture", 20)
            make(mud, "Zbroken", 20)
            with mud.connect(timeout=120) as warden:
                login(warden, "Zwarden", PW)
                for name in ("zaway", "zexpired", "zsoon", "zfuture", "zbroken"):
                    self.assertIn("(offline; saved)", warden.sync("jail %s 1d" % name))
                self.assertIn("is jailed (offline) until", warden.sync("jail zaway status"))

                # A saved room outside the cell, then one that does not exist.
                for room in (TEMPLE, 99999):
                    patch_player_file(mud, "Zaway", Room=room)
                    with mud.connect(timeout=120) as away:
                        login(away, "Zaway", PW)
                        self.assertEqual(CELL, room_of(warden, "Zaway"), room)
                        quit_client(away)
                # Released offline: they come in at the Temple, not the cell.
                self.assertIn("released from jail (offline; saved)",
                              warden.sync("jail zaway release"))
                with mud.connect(timeout=120) as away:
                    login(away, "Zaway", PW)
                    self.assertEqual(TEMPLE, room_of(warden, "Zaway"))
                    quit_client(away)

                # A term that ran out while they were away ends at login.
                patch_player_file(mud, "Zexpired", Jw_Timer=int(time.time()) - 60)
                self.assertIn("served; released at their next login",
                              warden.sync("jail zexpired status"))
                with mud.connect(timeout=120) as expired:
                    login(expired, "Zexpired", PW)
                    self.assertIn("Your sentence has been served", expired.transcript)
                    self.assertEqual(TEMPLE, room_of(warden, "Zexpired"))
                    self.assertFalse(number(mud, "Zexpired", "Act") & PLR_JAILED)
                    quit_client(expired)

                # One that runs out online, with nothing typed.
                patch_player_file(mud, "Zsoon", Jw_Timer=int(time.time()) + 12)
                with mud.connect(timeout=120) as soon:
                    login(soon, "Zsoon", PW)
                    self.assertEqual(CELL, room_of(warden, "Zsoon"))
                    soon.expect("Your sentence has been served", timeout=40)
                    self.assertEqual(TEMPLE, room_of(warden, "Zsoon"))
                    self.assertFalse(number(mud, "Zsoon", "Act") & PLR_JAILED)
                    quit_client(soon)

                # A deadline past 2038 is a long, read whole.
                patch_player_file(mud, "Zfuture", Jw_Timer=4102444800)
                with mud.connect(timeout=120) as future:
                    login(future, "Zfuture", PW)
                    self.assertEqual(CELL, room_of(warden, "Zfuture"))
                    self.assertIn("until 2100-01-01 00:00 UTC",
                                  warden.sync("jail zfuture status"))
                    quit_client(future)
                self.assertEqual("4102444800", field(mud, "Zfuture", "Jw_Timer"))

                # A malformed one refuses the character, as any malformed
                # number does, and the file is left as it was.
                patch_player_file(mud, "Zbroken", Jw_Timer="soon")
                before = text(mud, "Zbroken")
                with mud.connect(timeout=120) as broken:
                    broken.expect("by what name", "name:")
                    broken.send("Zbroken")
                    broken.expect("could not be read")
                self.assertIn("could not be read", warden.sync("jail zbroken status"))
                self.assertEqual(before, text(mud, "Zbroken"))

    def test_a_legacy_sentence_is_indefinite_and_lifts_nothing_it_cannot_prove(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zwarden", 70)
            make(mud, "Zlegacy", 20)
            with mud.connect(timeout=120) as warden:
                login(warden, "Zwarden", PW)
                warden.must("jail zlegacy 1d", "now in jail")
                # As the old code left it: no JailInfo, Jw_Timer 0, its title.
                drop_line(mud, "Zlegacy", "JailInfo")
                drop_line(mud, "Zlegacy", "TitleSet")
                patch_player_file(mud, "Zlegacy", Jw_Timer=0, Titl=" . (JAILED)~")
                with mud.connect(timeout=120) as legacy:
                    login(legacy, "Zlegacy", PW)
                    self.assertEqual(CELL, room_of(warden, "Zlegacy"))
                    status = warden.sync("jail zlegacy status")
                    self.assertIn("indefinitely", status)
                    self.assertIn("before sentences were recorded", status)
                    warden.must("jail zlegacy release", "released from jail")
                    self.assertEqual(TEMPLE, room_of(warden, "Zlegacy"))
                    comm = number(mud, "Zlegacy", "Comm")
                    self.assertTrue(comm & COMM_NOCHANNELS and comm & COMM_NOTITLE, comm)
                    title = field(mud, "Zlegacy", "Titl")
                    self.assertNotIn("JAILED", title)
                    self.assertTrue(title.startswith("the "), title)
                    quit_client(legacy)


@unittest.skipIf(SKIP is not None, SKIP or "")
class SentenceSaveTests(unittest.TestCase):
    def test_failed_and_unconfirmed_saves(self) -> None:
        with LiveMud(extra_env=FAULT_ENV) as mud:
            make(mud, "Zwarden", 70)
            make(mud, "Zfault", 20)
            make(mud, "Zunsure", 20)
            make(mud, "Zoffsave", 20)
            with mud.connect(timeout=120) as warden, \
                 mud.connect(timeout=120) as faulty, \
                 mud.connect(timeout=120) as unsure:
                login(warden, "Zwarden", PW)
                login(faulty, "Zfault", PW)
                login(unsure, "Zunsure", PW)

                # A jail whose save fails changes nothing.
                fault(mud, "jail-write-Zfault")
                self.assertIn("NOT applied", warden.sync("jail zfault 1d"))
                self.assertIn("is not jailed", warden.sync("jail zfault status"))
                self.assertEqual(TEMPLE, room_of(warden, "Zfault"))

                # A release whose save fails leaves them jailed in the cell.
                warden.must("jail zfault 1d", "now in jail")
                fault(mud, "jail-write-Zfault")
                self.assertIn("NOT released", warden.sync("jail zfault release"))
                self.assertIn("is jailed", warden.sync("jail zfault status"))
                self.assertEqual(CELL, room_of(warden, "Zfault"))
                self.assertTrue(number(mud, "Zfault", "Act") & PLR_JAILED)

                # An unconfirmed save is the new state, said so.
                fault(mud, "dirsync-Zunsure")
                self.assertIn("not confirmed", warden.sync("jail zunsure 1d"))
                self.assertIn("is jailed", warden.sync("jail zunsure status"))
                self.assertEqual(CELL, room_of(warden, "Zunsure"))

                # Offline: a failed save leaves the file exactly as it was.
                before = text(mud, "Zoffsave")
                fault(mud, "jail-write-Zoffsave")
                self.assertIn("NOT applied", warden.sync("jail zoffsave 1d"))
                self.assertEqual(before, text(mud, "Zoffsave"))
                quit_client(faulty)

            # An expiry whose save fails is tried again, and lands.
            patch_player_file(mud, "Zfault", Jw_Timer=int(time.time()) + 10)
            with mud.connect(timeout=120) as warden, mud.connect(timeout=120) as faulty:
                login(warden, "Zwarden", PW)
                login(faulty, "Zfault", PW)
                fault(mud, "jail-write-Zfault")
                self.assertEqual(CELL, room_of(warden, "Zfault"))
                deadline = time.monotonic() + 40
                while "release could not be saved" not in mud.server_output():
                    self.assertLess(time.monotonic(), deadline, mud.server_output())
                    time.sleep(0.5)
                self.assertIn("is jailed", warden.sync("jail zfault status"))
                self.assertEqual(CELL, room_of(warden, "Zfault"))
                faulty.expect("Your sentence has been served", timeout=40)
                self.assertEqual(TEMPLE, room_of(warden, "Zfault"))
                self.assertFalse(number(mud, "Zfault", "Act") & PLR_JAILED)


@unittest.skipIf(SKIP is not None, SKIP or "")
class JailCommandTests(unittest.TestCase):
    def test_arguments_rank_and_targets(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zwarden", 70)
            make(mud, "Zlowgod", 62)
            make(mud, "Zstaffb", 70)
            make(mud, "Zvalid", 20)
            make(mud, "Zunseen", 20, AfBy=2)        # AFF_INVISIBLE
            with mud.connect(timeout=120) as warden:
                login(warden, "Zwarden", PW)
                before = text(mud, "Zvalid")
                for bad in ("-5", "0m", "0d", "5x", "31d", "721h", "43201m",
                            "99999999999999999999", "1.5d", "+3d", "d", "1d extra",
                            "2h 3h", ""):
                    reply = warden.sync(("jail zvalid %s" % bad).strip())
                    self.assertIn("Syntax: jail", reply, bad)
                    self.assertEqual(before, text(mud, "Zvalid"), bad)
                for good, secs in (("30d", 30 * 86400), ("720h", 720 * 3600),
                                   ("43200m", 43200 * 60), ("2", 2 * 86400)):
                    self.assertIn("(offline; saved)", warden.sync("jail zvalid %s" % good))
                    self.assertAlmostEqual(number(mud, "Zvalid", "Jw_Timer"),
                                           time.time() + secs, delta=120, msg=good)
                warden.must("jail zvalid 0", "released from jail")
                self.assertIn("No such character", warden.sync("jail znosuch 1d"))
                self.assertIn("No such character", warden.sync("jail ../area 1d"))

                # At the password prompt: refused, nobody loaded twice.
                with mud.connect(timeout=120) as arriving:
                    arriving.expect("by what name", "name:")
                    arriving.send("Zvalid")
                    arriving.expect("password")
                    self.assertIn("logging in", warden.sync("jail zvalid 1d"))
                    arriving.send(PW)
                    _enter_game(arriving)
                    self.assertIn("is not jailed (online)", warden.sync("jail zvalid status"))
                    quit_client(arriving)

                # Rank: a level 62 cannot jail a 70.
                with mud.connect(timeout=120) as low:
                    login(low, "Zlowgod", PW)
                    self.assertIn("You failed", low.sync("jail zwarden 1d"))
                    self.assertFalse(number(mud, "Zwarden", "Act") & PLR_JAILED)
                    # Unseen is still found by name.
                    with mud.connect(timeout=120) as unseen:
                        login(unseen, "Zunseen", PW)
                        self.assertIn("They aren't here", warden.sync("stat char zunseen"))
                        self.assertIn("now in jail", low.sync("jail zunseen 1d"))
                        self.assertIn("is jailed (online)", low.sync("jail zunseen status"))
                        quit_client(unseen)
                    self.assertEqual(str(CELL), field(mud, "Zunseen", "Room"))
                    quit_client(low)

                # Switched: brought back to the body, which goes to the cell.
                with mud.connect(timeout=120) as staffb:
                    login(staffb, "Zstaffb", PW)
                    staffb.sync("goto %d" % 32700)
                    staffb.must("load mob %d" % SPARRING_GUARD, "You create")
                    staffb.sync("switch sparring")
                    warden.must("jail zstaffb 1d", "now in jail")
                    staffb.drain(1.0)
                    self.assertEqual(CELL, room_of(warden, "Zstaffb"))
                    self.assertIn("You aren't switched", staffb.sync("return"))
                    # Even staff are held by a sentence: GOTO lands in the cell.
                    staffb.sync("goto %d" % TEMPLE)
                    self.assertEqual(CELL, room_of(warden, "Zstaffb"))
                    warden.must("jail zstaffb release", "released from jail")
                    quit_client(staffb)


if __name__ == "__main__":
    unittest.main()

"""One malformed number in one player file no longer stops the game.

fread_number and fread_long called exit(1) on a token that was not a
number, so a single damaged character file took the whole game down at
that player's name prompt, and every reconnect did it again (roadmap,
2026-11-09). While load_char_obj reads a player file the readers jump
back to it instead: the file is left exactly as it is, the login is
refused, staff are told, offline loads refuse it, and the copy is never
saved. Area files still fail fast at boot.
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

from live_mud import CREATION_STEPS, LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()


def quit_out(client) -> None:
    client.sync("save")
    client.send("quit")
    assert client.wait_closed(30)


def make(mud: LiveMud, name: str, password: str, **fields) -> None:
    with mud.connect() as client:
        create_character(client, name, password)
        quit_out(client)
    if fields:
        patch_player_file(mud, name, **fields)


def refused_at_login(mud: LiveMud, name: str) -> str:
    with mud.connect() as client:
        client.expect("by what name", "name:")
        client.send(name)
        client.expect("could not be read", timeout=30)
        assert client.wait_closed(30), "the refused connection stayed open"
        return client.transcript


def identity(mud: LiveMud, name: str) -> tuple[bytes | None, list[str], list[str]]:
    """What must never change under a refused login: the file, the
    character's rows in the recovery ledger, and its snapshots."""
    path = mud.player_dir / name
    data = path.read_bytes() if path.is_file() else None
    ledger = mud.player_dir / "recovery" / "ledger.tsv"
    rows = [line for line in ledger.read_text(encoding="latin-1").splitlines()
            if name.lower() in line.lower()] if ledger.exists() else []
    versions = mud.player_dir / "versions" / name
    copies = sorted(p.name for p in versions.iterdir()) if versions.is_dir() else []
    return data, rows, copies


def first_vnum(mud: LiveMud, name: str) -> int:
    match = re.search(r"(?m)^#O\nVnum (\d+)$",
                      (mud.player_dir / name).read_text(encoding="latin-1"))
    assert match, "the fixture carries nothing"
    return int(match.group(1))


@unittest.skipIf(SKIP is not None, SKIP or "")
class PlayerFileRefusalTests(unittest.TestCase):

    def test_a_malformed_number_refuses_one_character_not_the_game(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zbadfile", "Zbadpass11")
            make(mud, "Zbadpet", "Zbadpass11")
            make(mud, "Zgoodfile", "Zgoodpass1")
            make(mud, "Zfilestaff", "Zstaffpw11", Levl=70)

            bad = mud.player_dir / "Zbadfile"
            text = bad.read_text(encoding="latin-1")
            text, n = re.subn(r"(?m)^Levl \d+$", "Levl x7", text)
            self.assertEqual(n, 1)
            bad.write_text(text, encoding="latin-1", newline="")
            bad_bytes = bad.read_bytes()

            # A pet whose record goes wrong part way: the pet is the
            # character's from the start, so free_char takes it away.
            pet = mud.player_dir / "Zbadpet"
            text = pet.read_text(encoding="latin-1")
            self.assertIn("#END", text)
            text = text.replace("#END", "#PET\nVnum 98\nName Zpetname~\nLevl q3\nEnd\n\n#END", 1)
            pet.write_text(text, encoding="latin-1", newline="")
            pet_bytes = pet.read_bytes()

            refused_at_login(mud, "Zbadfile")
            refused_at_login(mud, "Zbadpet")
            # A pet whose mobile no longer exists, with no stand-in in the
            # world: left out, and the character plays on (create_mobile
            # with no index exited the game).
            make(mud, "Zgonepet", "Zgonepass1")
            gone = mud.player_dir / "Zgonepet"
            gone.write_text(gone.read_text(encoding="latin-1").replace(
                "#END", "#PET\nVnum 1\nName Zlostpet~\nLevl 3\nEnd\n\n#END", 1),
                encoding="latin-1", newline="")
            with mud.connect() as client:
                login(client, "Zgonepet", "Zgonepass1")
                quit_out(client)
            # Again: the game is still up, and still refuses.
            refused_at_login(mud, "Zbadfile")
            self.assertIsNone(mud.proc.poll(), "the game exited")
            self.assertEqual(bad.read_bytes(), bad_bytes, "the unreadable file was changed")
            self.assertEqual(pet.read_bytes(), pet_bytes)

            # Everybody else plays on; staff were told; offline tools refuse.
            with mud.connect() as good:
                login(good, "Zgoodfile", "Zgoodpass1")
                good.must("time", "")
                quit_out(good)
            with mud.connect() as staff:
                login(staff, "Zfilestaff", "Zstaffpw11")
                said = staff.sync("grantpsi zbadfile now")
                self.assertNotIn("granted", said.lower())
                quit_out(staff)
            self.assertEqual(bad.read_bytes(), bad_bytes)
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            self.assertIn("Zbadfile's file has a malformed value; it is left as it is", log)
            self.assertIn("Zbadpet's file has a malformed value", log)
            self.assertIsNone(mud.proc.poll())



@unittest.skipIf(SKIP is not None, SKIP or "")
class UnreadableNameTests(unittest.TestCase):
    """Review, 2026-11-09: a file that is there and cannot be opened was
    taken for a free name, and creating the character saved a level 1
    over it. Only proven absence is a new character."""

    def test_an_unopenable_file_is_refused_never_replaced(self) -> None:
        # player-open fails the open as a permission error would, so the
        # test runs as root too; player-read fails the read part way.
        env = {"TOC_FAULT": "player-open-Zpermheld player-read-Zreadfail"}
        with LiveMud(extra_env=env) as mud:
            make(mud, "Zpermheld", "Zpermpass1", Levl=20)
            make(mud, "Zreadfail", "Zreadpass1")
            held = identity(mud, "Zpermheld")
            readfail = identity(mud, "Zreadfail")
            self.assertIsNotNone(held[0])
            self.assertTrue(held[1], "the character has a recovery identity")

            for _ in range(2):
                said = refused_at_login(mud, "Zpermheld")
                self.assertNotIn("did i get that right", said.lower())
            refused_at_login(mud, "Zreadfail")
            self.assertEqual(identity(mud, "Zpermheld"), held)
            self.assertEqual(identity(mud, "Zreadfail"), readfail)

            # A file whose presence cannot be checked (a symlink loop:
            # stat says ELOOP, for root too) is not a free name either.
            loop = mud.player_dir / "Zloopname"
            os.symlink("Zloopname", loop)
            refused_at_login(mud, "Zloopname")
            self.assertEqual(os.readlink(loop), "Zloopname")

            # A name that became unreadable while somebody was creating it.
            with mud.connect() as client:
                client.expect("by what name", "name:")
                client.send("Zracer")
                client.expect("did i get that right")
                race = mud.player_dir / "Zracer"
                os.symlink("Zracer", race)
                client.send("Y")
                said = ""
                for _ in range(40):
                    client.drain(0.5)
                    said = client.buffer.lower()
                    if "taken by someone else" in said:
                        break
                    for needle, reply in CREATION_STEPS:
                        if needle in said and needle != "did i get that right":
                            client.buffer = ""
                            client.send("Zracepass1" if reply is None else reply)
                            break
                    else:
                        client.buffer = ""
                        client.send("")
                self.assertIn("taken by someone else", client.transcript.lower())
            self.assertEqual(os.readlink(race), "Zracer")
            self.assertFalse((mud.player_dir / "versions" / "Zracer").exists())

            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            self.assertIn("Zpermheld's file could not be opened; it is left as it is", log)
            self.assertIn("Zreadfail's file could not be read to the end", log)
            self.assertIn("Zloopname's file could not be checked", log)
            self.assertIn("New character Zracer@", log)
            self.assertIsNone(mud.proc.poll())

    @unittest.skipIf(os.geteuid() == 0, "root opens a mode-000 file; CI's runner is not root")
    def test_a_mode_000_file_is_refused_never_replaced(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zpermheld", "Zpermpass1", Levl=20)
            path = mud.player_dir / "Zpermheld"
            held = identity(mud, "Zpermheld")
            path.chmod(0)
            try:
                with mud.connect() as client:
                    client.expect("by what name", "name:")
                    client.send("Zpermheld")
                    client.expect("could not be read", timeout=30)
                    self.assertNotIn("did i get that right", client.transcript.lower())
            finally:
                path.chmod(0o644)
            self.assertEqual(identity(mud, "Zpermheld"), held)
            with mud.connect() as client:
                login(client, "Zpermheld", "Zpermpass1")
                self.assertRegex(client.must("score", "Level:"), r"Level:\s+20\b")
                quit_out(client)


@unittest.skipIf(SKIP is not None, SKIP or "")
class DamagedStructureTests(unittest.TestCase):
    """Review, 2026-11-09: a damaged section marker or a file cut short
    was loaded as far as it went, and the next save wrote the shorter
    character over the file. A player file is the character only when it
    is all there: known sections, and #END."""

    def test_damaged_files_are_refused_whole_ones_load(self) -> None:
        with LiveMud() as mud:
            names = ["Zsection", "Zcutend", "Zcutobj", "Zcutstash", "Zstraynote", "Zwholeone"]
            for name in names:
                make(mud, name, "Zdamaged11")
            vnum = first_vnum(mud, "Zwholeone")

            def damage(name: str, change) -> None:
                path = mud.player_dir / name
                text = path.read_text(encoding="latin-1")
                new = change(text)
                self.assertNotEqual(new, text, name)
                path.write_text(new, encoding="latin-1", newline="")

            damage("Zsection", lambda t: t.replace("#O\n", "#ZBROKEN\n", 1))
            damage("Zcutend", lambda t: t[:t.rindex("#END")])
            # Cut after an object's first whole line: the record never ends.
            damage("Zcutobj", lambda t: t[:re.search(r"(?m)^#O\nVnum \d+\n", t).end()])
            damage("Zcutstash", lambda t: t[:t.rindex("#END")]
                   + f"#STASH\n#O\nVnum {vnum}\nNest 0\n")
            damage("Zstraynote", lambda t: t.replace("#O\n", "stray words\n#O\n", 1))
            # A whole file with its stash still loads, as every save does.
            damage("Zwholeone", lambda t: t[:t.rindex("#END")]
                   + f"#STASH\n#O\nVnum {vnum}\nNest 0\nEnd\n\n#END\n")

            before = {name: identity(mud, name) for name in names}
            for name in names[:-1]:
                refused_at_login(mud, name)
                self.assertEqual(identity(mud, name), before[name], name)

            with mud.connect() as client:
                login(client, "Zwholeone", "Zdamaged11")
                quit_out(client)

            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            self.assertIn("Zsection's file has an unknown section", log)
            self.assertIn("Zcutend's file ends before its #END", log)
            self.assertIn("Zcutobj's file has an incomplete object record", log)
            self.assertIn("Zcutstash's file ends before its #END", log)
            self.assertIn("Zstraynote's file has a record that does not begin with #", log)
            self.assertNotIn("Zwholeone's file", log)
            self.assertIsNone(mud.proc.poll())


@unittest.skipIf(SKIP is not None, SKIP or "")
class UnfinishedObjectTests(unittest.TestCase):
    """Review, 2026-11-09: create_object puts an object in the world
    before its record is read, and a malformed value jumped out past the
    end that would have handed it to the character -- so every refused
    attempt left one more object in the world, owned by nobody."""

    def test_refused_loads_leave_nothing_in_the_world(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zorphan", "Zorphpass1")
            make(mud, "Zorphstaff", "Zstaffpw11", Levl=70)
            vnum = first_vnum(mud, "Zorphan")
            path = mud.player_dir / "Zorphan"
            text = path.read_text(encoding="latin-1")
            record = (f"#O\nVnum {vnum}\nName Zorphanartifact~\n"
                      "ExDe zorphnote~\na note~\n"
                      "Affect 0 10 5 -5 17 0 0\n"
                      "Affect 0 10 5 q 17 0 0\nNest 0\nEnd\n\n")
            path.write_text(text.replace("#END", record + "#END", 1),
                            encoding="latin-1", newline="")
            before = identity(mud, "Zorphan")

            with mud.connect() as staff:
                login(staff, "Zorphstaff", "Zstaffpw11")
                baseline = staff.sync(f"owhere {vnum}")
                for _ in range(3):
                    refused_at_login(mud, "Zorphan")
                said = staff.sync("owhere zorphanartifact")
                self.assertIn("Nothing like that", said)
                self.assertEqual(staff.sync(f"owhere {vnum}").count("["),
                                 baseline.count("["), "copies of the prototype grew")
                quit_out(staff)
            self.assertEqual(identity(mud, "Zorphan"), before)
            self.assertIsNone(mud.proc.poll())


def vnums(mud: LiveMud, name: str) -> list[int]:
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    return list(dict.fromkeys(int(v) for v in re.findall(r"(?m)^#O\nVnum (\d+)$", text)))


def in_world(client, vnum: int) -> int:
    said = client.must(f"oshow {vnum}", "In the world now:")
    return int(re.search(r"In the world now: (\d+)", said).group(1))


@unittest.skipIf(SKIP is not None, SKIP or "")
class DamagedObjectRecordTests(unittest.TestCase):
    """Review, 2026-11-09: a second Vnum in an object record rewrote the
    object's prototype, so releasing it read a NULL one and took the game
    down (or decremented the wrong one); and a known object whose record
    had no Nest was dropped with a "incomplete object" line, the login
    went ahead, and the next save wrote the character without it -- the
    object returned to the pool still in the object list. Each refuses
    the character now, the file stays as it is, and the counts do not
    move. A vanished prototype is still the old, kept case."""

    def test_identity_and_whole_records(self) -> None:
        with LiveMud() as mud:
            names = ["Zdupevnum", "Zdupevalid", "Znonest"]
            for name in names + ["Zvanished", "Zafterone"]:
                make(mud, name, "Zobjpass11")
            make(mud, "Zcountstaff", "Zstaffpw11", Levl=70)
            first, second = vnums(mud, "Zdupevnum")[:2]
            self.assertNotEqual(first, second)

            def add(name: str, record: str) -> None:
                path = mud.player_dir / name
                text = path.read_text(encoding="latin-1")
                path.write_text(text.replace("#END", record + "#END", 1),
                                encoding="latin-1", newline="")

            add("Zdupevnum", f"#O\nVnum {first}\nVnum 9999999\nNest q\nEnd\n\n")
            add("Zdupevalid", f"#O\nVnum {first}\nVnum {second}\nNest 0\nEnd\n\n")
            path = mud.player_dir / "Znonest"
            text = path.read_text(encoding="latin-1")
            self.assertIn("\nNest 0\n", text)
            path.write_text(text.replace("\nNest 0\n", "\n", 1), encoding="latin-1", newline="")
            # A prototype that is gone: dropped, and the character plays on.
            add("Zvanished", "#O\nVnum 9999999\nNest 0\nEnd\n\n")

            before = {name: identity(mud, name) for name in names}
            with mud.connect() as staff:
                login(staff, "Zcountstaff", "Zstaffpw11")
                counts = (in_world(staff, first), in_world(staff, second))
                for _ in range(2):
                    for name in names:
                        refused_at_login(mud, name)
                self.assertIsNone(mud.proc.poll(), "the game exited")
                self.assertEqual((in_world(staff, first), in_world(staff, second)), counts)
                quit_out(staff)
            for name in names:
                self.assertEqual(identity(mud, name), before[name], name)

            for name in ("Zvanished", "Zafterone"):
                with mud.connect() as client:
                    login(client, name, "Zobjpass11")
                    quit_out(client)
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
            self.assertIn("Zdupevnum's file has an object record with two vnums", log)
            self.assertIn("Zdupevalid's file has an object record with two vnums", log)
            self.assertIn("Znonest's file has an incomplete object record", log)
            self.assertNotIn("Zvanished's file", log)
            self.assertIsNone(mud.proc.poll())


class PlayerFileRefusalSourceTests(unittest.TestCase):
    def test_the_trap_is_armed_only_for_player_files(self) -> None:
        db = (ROOT / "src" / "db.c").read_text(encoding="latin-1")
        body = db[db.index("static void fread_malformed("):]
        body = body[:body.index("\n}\n")]
        self.assertIn("longjmp( *fread_player_trap, 1 )", body)
        self.assertIn("exit( 1 )", body, "area files still fail fast")
        number = db[db.index("int fread_number( FILE *fp )"):]
        number = number[:number.index("\n}\n")]
        self.assertNotIn("exit( 1 )", number)
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        load = save[save.index("bool load_char_obj( DESCRIPTOR_DATA *d, char *name )"):]
        load = load[:load.index("\n}\n")]
        self.assertIn("fread_player_trap = &trap;", load)
        self.assertIn("fread_player_trap = NULL;", load)
        saver = save[save.index("bool save_char_obj( CHAR_DATA *ch )"):]
        self.assertLess(saver.index("ch->pcdata->load_failed"), saver.index("fopen"))
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        self.assertEqual(comm.count("player_file_unreadable( ch )"), 2)
        self.assertIn("player_file_unreadable( d->character )", save)

    def test_absence_is_proven_and_a_file_must_be_whole(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        presence = save[save.index("int player_file_presence( const char *name )"):]
        presence = presence[:presence.index("\n}\n")]
        self.assertIn("errno != ENOENT", presence)
        free = comm[comm.index("static bool new_name_still_free("):]
        free = free[:free.index("\n}\n")]
        self.assertIn("player_file_presence(", free)
        self.assertNotIn("fopen", free, "a failed open is not absence")
        self.assertIn("player_file_presence( arg2 ) != PLAYER_FILE_ABSENT", wiz)
        load = save[save.index("bool load_char_obj( DESCRIPTOR_DATA *d, char *name )"):]
        load = load[:load.index("\n}\n")]
        self.assertIn("completed = true", load)
        self.assertIn("ferror( fp )", load)
        self.assertIn("fclose( fp ) != 0", load)
        self.assertLess(load.index("read_done:"), load.index("fread_obj_release_unfinished()"))
        obj = save[save.index("void fread_obj( CHAR_DATA *ch, FILE *fp )\n{"):]
        self.assertIn("fread_obj_unfinished            = obj;", obj)


if __name__ == "__main__":
    unittest.main()

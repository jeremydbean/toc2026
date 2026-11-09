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

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

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


if __name__ == "__main__":
    unittest.main()

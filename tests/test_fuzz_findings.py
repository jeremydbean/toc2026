"""What fuzzing the file readers found (fuzz/README.md, 2026-11-12).

Each test fails on the code before its fix:

- an area file cut off mid-string (no newline at its end) hung the boot:
  bug() counted lines with `while (getc != '\\n')`, which never ends at EOF;
- a spell slot no spell has abort()ed the boot (SIGABRT, a core) instead
  of stopping it like every other malformed area file;
- a room affect type outside room_aff_type[] was read out of bounds;
- a door reset naming a negative room read the exit through NULL;
- a #SOCIALS section past MAX_SOCIALS wrote past social_table[] (found
  while writing the area target's rewind, then confirmed by it under ASan);
- a player file key this build does not know crashed the game at that
  player's login (bug() was handed the word's pointer cut to an int and
  printed it with %s) -- what a rollback to an older build would meet --
  and, once that was fixed, a key holding "%n" did too: bug() takes its
  text as a format;
- a player file with no Room line, loaded offline (GRANTPSI here), stayed
  in the character list after extract_char refused it, and the player's
  next login reconnected into that roomless copy;
- a refused player file with a pet and no Room line crashed the game in
  free_char (stop_follower asked can_see of a master with no room);
- an alias whose name began with a quote (ALIAS "'ZQ" LOOK) was saved as
  a line the reader took for an opening quote, so the rest of the file was
  read out of step and the next login refused the character -- a player
  could lock themselves out (the roundtrip oracle: a file the game saved
  did not load);
- a class, race or guild past the tables was read past class_table and
  pc_race_table; a remort count of millions overflowed reset_char's
  arithmetic, as an old (gold) file's object cost did multiplied into
  copper; a second #PLAYER record was read over the first, leaking its
  aliases;
- freeing a refused, roomless copy whose strength rested on worn gear
  crashed (the wielded weapon was "dropped" into no room), and the same
  drop at a quit left a copy of the weapon on the floor -- a duplication;
- a player file whose Act carried bit A (ACT_IS_NPC) made its player a
  mobile with no prototype, read through NULL; a pet's without it, a
  player with no pcdata.

The leaks the player target found (the name every load started with, the
first of a repeated string key, the race names, capitalize()'s copies) are
replayed under LeakSanitizer by tests/test_fuzz_smoke.py and pinned here
by their source.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import live_mud
from live_mud import LiveMud, create_character, login, patch_player_file

ROOT = Path(__file__).resolve().parents[1]
BINARY = live_mud.find_binary()


def check_area(text: bytes, timeout: float = 30.0) -> tuple[int | None, str]:
    """Boot a world holding only this area with --check-area.

    Returns (exit status, output); the status is None when the boot did not
    finish within the timeout -- a hang.
    """
    assert BINARY is not None
    with tempfile.TemporaryDirectory(prefix="toc-fuzzfind-") as tmp:
        root = Path(tmp)
        area = root / "area"
        area.mkdir()
        for name in ("player", "gods", "heroes", "log", "corpse", "backups"):
            (root / name).mkdir()
        (area / "area.lst").write_text("zfuzz.are\n$\n")
        (area / "zfuzz.are").write_bytes(text)
        try:
            proc = subprocess.run([str(BINARY), "--check-area"], cwd=area,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  timeout=timeout)
        except subprocess.TimeoutExpired as hung:
            out = hung.stdout or b""
            return None, out.decode("latin-1", "replace")
        return proc.returncode, proc.stdout.decode("latin-1", "replace")


ROOM_HEADER = b"#AREA Fuzz Findings~\n\n#ROOMS\n"


def room(flags: bytes, extra: bytes = b"") -> bytes:
    return (ROOM_HEADER + b"#100\nA Room~\nA room.\n~\n0 " + flags + b" 0\n"
            + extra + b"S\n#0\n\n#$\n")


@unittest.skipIf(BINARY is None, "no merc binary; run make")
class AreaReaderFindings(unittest.TestCase):

    def test_a_file_cut_mid_string_stops_the_boot_instead_of_hanging(self) -> None:
        status, out = check_area(b"#AREA Cut~\n#MOBILES\n#100\nname~\nshort")
        self.assertIsNotNone(status, "the boot hung on a file cut off mid-string")
        self.assertEqual(status, 1, out[-2000:])
        self.assertIn("LINE:", out)

    def test_a_spell_slot_no_spell_has_stops_the_boot_cleanly(self) -> None:
        text = (b"#AREA Slots~\n\n#OBJECTS\n#100\npotion fuzz~\na potion~\n"
                b"A potion lies here.~\nglass~\n10 0 A\n5 999999 0 0 0\n"
                b"1 1 0 P\n#0\n\n#$\n")
        status, out = check_area(text)
        self.assertEqual(status, 1, "a bad slot must exit(1), not abort: %r\n%s"
                         % (status, out[-2000:]))
        self.assertIn("bad slot 999999", out)

    def test_a_room_affect_type_past_the_table_is_refused(self) -> None:
        status, out = check_area(room(b"DH", b"7 50 0 0 0 0 0 200 100\n"))
        self.assertEqual(status, 1, out[-2000:])
        self.assertIn("bad room affect type", out)
        status, out = check_area(room(b"DH", b"-3 50 0 0 0 0 0 200 100\n"))
        self.assertEqual(status, 1, out[-2000:])
        self.assertIn("bad room affect type", out)

    def test_a_room_affect_type_in_the_table_still_loads(self) -> None:
        status, out = check_area(room(b"DH", b"3 50 0 0 0 0 0 200 100\n"))
        self.assertEqual(status, 0, out[-2000:])
        self.assertIn("Validation OK", out)

    def test_every_room_affect_type_room_affect_knows_loads(self) -> None:
        # The table stopped at volcanic (3), so a SHOCKER room (4) was read
        # past its end -- and, once the loader checked, refused the boot.
        for kind in (0, 1, 2, 3, 4):
            with self.subTest(kind=kind):
                status, out = check_area(
                    room(b"DH", b"%d 50 0 0 0 0 0 2 6\n" % kind))
                self.assertEqual(status, 0, out[-2000:])
                self.assertIn("Validation OK", out)
        status, out = check_area(room(b"DH", b"5 50 0 0 0 0 0 200 100\n"))
        self.assertEqual(status, 1, out[-2000:])
        self.assertIn("bad room affect type", out)

    def test_the_room_affect_table_names_every_type(self) -> None:
        merc = (ROOT / "src" / "merc.h").read_text(encoding="latin-1")
        db = (ROOT / "src" / "db.c").read_text(encoding="latin-1")
        types = {name: int(value) for name, value in re.findall(
            r"#define\s+(STINKING_CLOUD|EXTRA_DIMENSIONAL|VOLCANIC|SHOCKER)\s+(\d+)",
            merc)}
        self.assertEqual(len(types), 4, types)
        count = int(re.search(r"#define\s+ROOM_AFF_TYPES\s+(\d+)", merc).group(1))
        self.assertEqual(count, max(types.values()) + 1)
        table = re.search(r"room_aff_type\s*\[ROOM_AFF_TYPES\]\s*=\s*\{(.*?)\};",
                          db, re.S)
        self.assertIsNotNone(table, "room_aff_type must be sized by ROOM_AFF_TYPES")
        names = re.findall(r'"([^"]*)"', table.group(1))
        self.assertEqual(len(names), count, names)
        self.assertEqual(names[types["SHOCKER"]], "shocker")

    def test_a_door_reset_in_a_negative_room_is_refused(self) -> None:
        # get_room_index answers NULL for a negative vnum without stopping
        # the boot, and load_resets read the exit through it.
        text = room(b"D", b"D0\nA door.\n~\ndoor~\n1 -1 100\n") \
            .replace(b"#$\n", b"#RESETS\nD 0 -100 0 2\nS\n\n#$\n")
        status, out = check_area(text)
        self.assertEqual(status, 1, "%r\n%s" % (status, out[-2000:]))
        self.assertIn("not door", out)

    def test_more_socials_than_the_table_holds_are_refused(self) -> None:
        many = b"".join(b"zsocial%d\n\n#\n" % i for i in range(600))
        status, out = check_area(b"#AREA Socials~\n\n#SOCIALS\n" + many + b"#0\n\n#$\n")
        self.assertEqual(status, 1, out[-2000:])
        self.assertIn("more than 512 socials", out)


def remove_key(mud: LiveMud, name: str, key: str) -> None:
    path = mud.player_dir / name
    lines = path.read_text(encoding="latin-1").split("\n")
    kept = [line for line in lines if line.split(" ")[0] != key]
    if len(kept) == len(lines):
        raise AssertionError("%s's file has no %s line" % (name, key))
    path.write_text("\n".join(kept), encoding="latin-1", newline="")


def quit_and_wait(client) -> None:
    client.send("quit")
    if not client.wait_closed():
        raise AssertionError("the character did not leave the world")


@unittest.skipIf(live_mud.skip_reason() is not None, live_mud.skip_reason() or "")
class PlayerReaderFindings(unittest.TestCase):

    def test_an_unknown_key_is_skipped_not_a_crash(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zunknownkey", "fuzzpass1")
                quit_and_wait(client)
            # A key from a newer build, as a rollback would leave it.
            patch_player_file(mud, "Zunknownkey", Zzyzxkey="5")
            # And one whose name is a format: bug() takes its text as one.
            patch_player_file(mud, "Zunknownkey", **{"Zz%n%s%n": "5"})
            with mud.connect(timeout=60) as client:
                login(client, "Zunknownkey", "fuzzpass1")
                client.must("score", "Zunknownkey")
            self.assertIn("Fread_char: no match. 'Zzyzxkey'", mud.server_output())
            self.assertIn("Fread_char: no match. 'Zz?n?s?n'", mud.server_output())

    def test_a_player_file_cannot_make_its_player_an_npc(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zactbit", "fuzzpass1")
                quit_and_wait(client)
            path = mud.player_dir / "Zactbit"
            text = path.read_text(encoding="latin-1")
            act = re.search(r"^Act\s+(-?\d+)$", text, re.M)
            self.assertIsNotNone(act, "a new character's file has an Act line")
            value = int(act.group(1)) | 1      # bit A: ACT_IS_NPC
            path.write_text(text[:act.start()] + "Act  %d" % value + text[act.end():],
                            encoding="latin-1", newline="")
            with mud.connect(timeout=60) as client:
                login(client, "Zactbit", "fuzzpass1")
                client.must("score", "Zactbit")
                quit_and_wait(client)
            # The save the quit made is a player's again.
            saved = re.search(r"^Act\s+(-?\d+)$",
                              path.read_text(encoding="latin-1"), re.M)
            self.assertIsNotNone(saved)
            self.assertEqual(int(saved.group(1)) & 1, 0)

    def test_quitting_leaves_no_copy_of_a_wielded_weapon_on_the_floor(self) -> None:
        # Found as a crash: freeing a refused, roomless copy took off a
        # strength item, and affect_modify "dropped" the wielded weapon
        # into no room. In play the same drop put a copy of the weapon --
        # still in the saved file -- on the floor at every quit.
        with LiveMud() as mud:
            for name in ("Zstrong", "Zwatcher"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, "fuzzpass1")
                    quit_and_wait(client)
            patch_player_file(mud, "Zstrong", Levl=70, Attr="3 13 13 13 13")
            patch_player_file(mud, "Zwatcher", Levl=70)
            with mud.connect(timeout=60) as strong, mud.connect(timeout=60) as watcher:
                login(strong, "Zstrong", "fuzzpass1")
                strong.must("load obj 600", "hand axe")         # weighs 5
                # Something carried between the two: extract_char's walk
                # had already taken the next object when the axe fell, so
                # the axe was left lying there.
                strong.must("load obj 601", "cleaver")
                strong.must("load obj 2390", "gauntlets")       # +4 strength
                strong.must("wear gauntlets", "gauntlets")
                strong.must("wield axe", "wield")
                strong.must("save", "")
                login(watcher, "Zwatcher", "fuzzpass1")
                room = live_mud.room_of(watcher, "Zstrong")
                watcher.must("goto %d" % room, "")
                self.assertNotIn("hand axe", watcher.sync("look").lower())
                quit_and_wait(strong)
                floor = watcher.sync("look").lower()
                self.assertNotIn("hand axe", floor, "the quit left the weapon behind")
            saved = (mud.player_dir / "Zstrong").read_text(encoding="latin-1")
            self.assertIn("Vnum 600\n", saved, "the weapon went with its owner")

    def test_an_alias_named_with_a_quote_cannot_lock_its_player_out(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zquoted", "fuzzpass1")
                reply = client.sync("alias \"'zq\" look")
                self.assertIn("may not start with a quote", reply)
                client.must("alias zz look", "zz")
                quit_and_wait(client)
            with mud.connect(timeout=60) as client:
                login(client, "Zquoted", "fuzzpass1")
                self.assertIn("zz", client.sync("alias"))
                quit_and_wait(client)

    def test_a_class_race_guild_or_remort_count_out_of_range_is_refused(self) -> None:
        names = ("Zbadclass", "Zbadrace", "Zbadguild", "Zbadremort", "Ztwoplayers",
                 "Zbadcost")
        with LiveMud() as mud:
            for name in names:
                with mud.connect(timeout=120) as client:
                    create_character(client, name, "fuzzpass1")
                    quit_and_wait(client)
            patch_player_file(mud, "Zbadclass", Cla=14)
            patch_player_file(mud, "Zbadrace", Race="dragon~")
            patch_player_file(mud, "Zbadguild", Gui=9)
            patch_player_file(mud, "Zbadremort", NumRemorts=794448000)
            # A file from before version 4 holds gold, multiplied into
            # copper as it is read; this figure overflowed the multiply.
            patch_player_file(mud, "Zbadcost", Vers=3, Cost=533333333333333331)
            # Its player record twice: the second used to be read over the
            # first, and its aliases took the first's slots unfreed.
            two = mud.player_dir / "Ztwoplayers"
            text = two.read_text(encoding="latin-1")
            record = text[:text.index("\nEnd\n") + len("\nEnd\n")]
            two.write_text(record + "\n" + text, encoding="latin-1", newline="")
            for name in names:
                before = (mud.player_dir / name).read_bytes()
                with mud.connect(timeout=60) as client:
                    client.expect("by what name", "name:")
                    client.send(name)
                    client.expect("could not be read", timeout=30)
                self.assertEqual((mud.player_dir / name).read_bytes(), before,
                                 "a refused file is left as it is")
            out = mud.server_output()
            self.assertIn("names a class the game does not have", out)
            self.assertIn("names a race no player may be", out)
            self.assertIn("names a guild the game does not have", out)
            self.assertIn("has a remort count no character can have", out)
            self.assertIn("has two player records", out)
            self.assertIn("whose gold price no price can be", out)

    def test_an_offline_load_with_no_room_leaves_no_copy_behind(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zroomless", "fuzzpass1")
                quit_and_wait(client)
            with mud.connect(timeout=120) as client:
                create_character(client, "Zgrantor", "fuzzpass1")
                quit_and_wait(client)
            remove_key(mud, "Zroomless", "Room")
            patch_player_file(mud, "Zgrantor", Levl=70)

            with mud.connect(timeout=60) as staff:
                login(staff, "Zgrantor", "fuzzpass1")
                staff.must("grantpsi Zroomless", "Grant flag applied")
                staff.must("grantpsi Zroomless", "Grant flag applied")

                with mud.connect(timeout=60) as victim:
                    login(victim, "Zroomless", "fuzzpass1")
                    look = victim.sync("look")
                    self.assertNotIn("Reconnecting", victim.transcript)
                    self.assertTrue(look.strip(), "no answer to LOOK")
                    quit_and_wait(victim)
                self.assertTrue(staff.sync("time").strip(), "the game stopped answering")

    def test_a_refused_file_with_a_pet_and_no_room_does_not_crash(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zpetless", "fuzzpass1")
                quit_and_wait(client)
            remove_key(mud, "Zpetless", "Room")
            path = mud.player_dir / "Zpetless"
            text = path.read_text(encoding="latin-1")
            pet = ("#PET\nVnum 2404\nName mercenary pet~\nSex  1\n"
                   "HMV  30 30 100 100 100 100\nPos  8\nEnd\n\n")
            # Then an object record with a number that is not one, which
            # refuses the file after the pet has been made.
            broken = "#O\nVnum 607x\nEnd\n\n"
            path.write_text(text.replace("#END", pet + broken + "#END", 1),
                            encoding="latin-1", newline="")

            with mud.connect(timeout=60) as client:
                client.expect("by what name", "name:")
                client.send("Zpetless")
                client.expect("could not be read", timeout=30)
            # Still serving: a new connection gets the greeting.
            with mud.connect(timeout=60) as client:
                client.expect("by what name", "name:")


class ReaderLeaksPinned(unittest.TestCase):
    """The leaks, by their source; the smoke test replays them under LSan."""

    def test_string_keys_release_what_they_replace(self) -> None:
        source = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        plain = re.findall(r"KEY\([^;]*fread_string", source)
        self.assertEqual(plain, [], "a string key assigned without freeing the old value")
        self.assertNotIn("race_lookup(fread_string", source.replace(" ", ""))

    def test_capitalize_allocates_nothing(self) -> None:
        source = (ROOT / "src" / "db.c").read_text(encoding="latin-1")
        body = source[source.index("char *capitalize( const char *str )"):]
        body = body[:body.index("\n}\n")]
        self.assertNotIn("str_dup", body)
        self.assertNotIn("alloc_mem", body)


if __name__ == "__main__":
    unittest.main()

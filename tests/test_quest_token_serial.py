"""A quest's recovery token is its questor's by serial, never by the file
Id (review, 2026-11-12).

A token's value[4] held the questor's Id plus one, and obj->owner their
name. The Id is number_range( 0, 65535 ) and never unique, and the name
went with RENAME and was never saved -- a token read back from a corpse
file named nobody, so its own questor could not pick it up. Tokens are
bound to player_serial now, written negative (value[4] = -serial) so a
tag from before can never be read for one; an old tag still answers
only its questor, by that Id and the name it carries. The login fix
20261112-quest-serial binds the old-tagged tokens a character holds to
their serial; one tagged for somebody else's Id stays nobody's.

The fixture's quiet room 32703 holds the drops, so no wandering janitor
can take one between a DROP and a GET.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zqtokenpw1"
ROOM = 32703
SHARED_ID = 4321
OTHER_ID = 999
TOKEN = 25038           # the Journal of Trinidad, the first quest token
REFUSED = "entrusted to another adventurer"
FIX = "20261112-quest-serial"


def token(tag: int) -> str:
    return ("#O\nVnum %d\nNest 0\nWear -1\nLev 1\nCond 100\nVal 0 0 0 0 %d\nEnd\n\n"
            % (TOKEN, tag))


def file_field(mud: LiveMud, name: str, key: str) -> int:
    found = re.search(rf"(?m)^{key} +(-?\d+)$",
                      (mud.player_dir / name).read_text(encoding="latin-1"))
    assert found, (name, key)
    return int(found.group(1))


def plant(mud: LiveMud, name: str, objects: str) -> None:
    path = mud.player_dir / name
    text = re.sub(r"(?m)^Fixes .*\n", "", path.read_text(encoding="latin-1"))
    path.write_text(text.replace("#END", objects + "#END", 1), encoding="latin-1")


class QuestTokenSourceTests(unittest.TestCase):
    def test_the_binding_is_the_serial(self) -> None:
        quest = (ROOT / "src" / "quest.c").read_text(encoding="latin-1")
        tag = quest.split("static int quest_token_owner_tag( CHAR_DATA *ch )", 1)[1]
        self.assertIn("return -player_serial( ch );", tag.split("\n}\n", 1)[0])
        self.assertIn("questitem->value[4] = quest_token_owner_tag(ch);", quest)
        # Nothing else reads the file Id as a token's owner.
        for name in ("act_obj.c", "magic2.c"):
            text = (ROOT / "src" / name).read_text(encoding="latin-1")
            self.assertNotIn("pcdata->id + 1", text, name)
            self.assertIn("quest_token_owned_by( obj, ch )", text, name)
        fixes = (ROOT / "src" / "fixes.c").read_text(encoding="latin-1")
        self.assertIn('{ "%s",' % FIX, fixes)


@unittest.skipIf(SKIP is not None, SKIP or "")
class QuestTokenLiveTests(unittest.TestCase):
    def test_a_token_answers_only_its_questor(self) -> None:
        with LiveMud(fixtures=True) as mud:
            for name in ("Zqtstaff", "Zqtowner", "Zqttwin", "Zqtother"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zqtstaff", Levl=70, Room=ROOM)
            patch_player_file(mud, "Zqtowner", Levl=20, Room=ROOM, Id=SHARED_ID)
            patch_player_file(mud, "Zqttwin", Levl=20, Room=ROOM, Id=SHARED_ID)
            patch_player_file(mud, "Zqtother", Levl=20, Room=ROOM, Id=OTHER_ID)
            serials = {n: file_field(mud, n, "Serial") for n in ("Zqtowner", "Zqttwin")}
            self.assertNotEqual(serials["Zqtowner"], serials["Zqttwin"])
            # Tokens from before: the owner's own, and one tagged for the
            # owner's Id that somebody else holds. Neither file is marked
            # as having had the fix, as an old file would not be.
            plant(mud, "Zqtowner", token(SHARED_ID + 1))
            plant(mud, "Zqtother", token(SHARED_ID + 1))
            plant(mud, "Zqttwin", "")

            clients = {}
            for name in ("Zqtstaff", "Zqtowner", "Zqttwin", "Zqtother"):
                client = mud.connect(timeout=120)
                login(client, name, PW)
                client.sync("scroll 0")
                clients[name] = client
            staff, owner, twin, other = (clients[n] for n in
                                         ("Zqtstaff", "Zqtowner", "Zqttwin", "Zqtother"))
            try:
                said = {n: "bound to you alone" in c.transcript for n, c in clients.items()}
                self.assertEqual(said, {"Zqtstaff": False, "Zqtowner": True,
                                        "Zqttwin": False, "Zqtother": False},
                                 "the login fix spoke to the owner alone")

                # The owner's old token, bound to their serial at login: the
                # twin sharing the Id cannot take it; the owner can.
                owner.must("drop journal", "You drop")
                self.assertIn(REFUSED, twin.sync("get journal"))
                owner.must("get journal", "You get")

                # A token bound by serial: the twin's. The owner, sharing
                # the Id, is refused; the twin takes it, and still does
                # under a new name -- the serial goes with a RENAME.
                staff.must(f"load obj {TOKEN} 1", "You create")
                twin_tag = -serials["Zqttwin"]
                staff.must(f"set obj journal v4 {twin_tag}", f"set to {twin_tag}")
                staff.must("drop journal", "You drop")
                self.assertIn(REFUSED, owner.sync("get journal"))
                twin.must("get journal", "You get")
                twin.must("drop journal", "You drop")
                staff.must("rename zqttwin Zqtrenamed", "renamed")
                twin.must("get journal", "You get")

                # Somebody else's old token stays nobody's: the fix did not
                # give it to its holder, and it names nobody.
                other.must("drop journal", "You drop")
                for client in (other, twin, owner):
                    self.assertIn(REFUSED, client.sync("get journal"))
            finally:
                for client in (owner, twin, other, staff):
                    client.send("quit")
                    client.wait_closed(30)
                    client.close()

            # The fix is marked whether it changed anything or not, and a
            # second login says nothing.
            for name in ("Zqtowner", "Zqtother"):
                self.assertRegex((mud.player_dir / name).read_text(encoding="latin-1"),
                                 rf"(?m)^Fixes .*\b{FIX}\b")
            with mud.connect(timeout=120) as again:
                login(again, "Zqtowner", PW)
                again.sync("scroll 0")
                self.assertFalse("bound to you alone" in again.transcript, "a second login is quiet")
                again.send("quit")
                again.wait_closed(30)
            renamed = file_field(mud, "Zqtrenamed", "Serial")
        self.assertEqual(renamed, serials["Zqttwin"])


if __name__ == "__main__":
    unittest.main()

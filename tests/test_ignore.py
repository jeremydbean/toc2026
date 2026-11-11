"""IGNORE: who a player will not hear.

IGNORE was a stub that answered "That command is not available." (owner,
2026-11-11: "fix ignore command"). It keeps a list of player names on the
character (pcdata->ignore, saved as `Ignore <names>~' under case 'I'; the
old game's `Ignoring' line is read into the same list), and whatever an
ignored player says, emotes, tells, group-tells or puts on a channel no
longer reaches the one ignoring them; their notes and HISTORY lines drop
out of that player's view. A tell is answered "<name> is ignoring you."
Staff cannot be ignored, and nothing but speech is touched.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Zignore1pass"
TEMPLE = 4207
SQUARE = 2401


def body(path: str, start: str) -> str:
    source = (ROOT / path).read_text(encoding="latin-1")
    text = source[source.index(start):]
    return text[:text.index("\n}\n")]


class IgnoreSourceTests(unittest.TestCase):
    def test_the_stub_is_gone(self) -> None:
        stubs = (ROOT / "src" / "stubs.c").read_text(encoding="latin-1")
        self.assertNotIn("do_ignore", stubs)
        self.assertIn("void do_ignore(", (ROOT / "src" / "act_comm.c").read_text(encoding="latin-1"))

    def test_every_channel_walk_asks(self) -> None:
        # Each per-listener delivery of speech asks is_ignoring: the shared
        # channel_say, the castle walk, the five channels with their own
        # walks, say's chat-pane loop, gtell, tell and reply.
        for start in ("static void channel_say(", "static void castle_say(",
                      "void do_gossip(", "void do_question(",
                      "void do_music(", "void do_shout(", "void do_yell(",
                      "void do_say(", "void do_gtell(",
                      "void do_tell(", "void do_reply("):
            with self.subTest(start):
                self.assertIn("is_ignoring(", body("src/act_comm.c", start))
        self.assertIn("act_speech(", body("src/act_comm.c", "void do_say("))
        self.assertIn("act_speech(", body("src/act_comm.c", "void do_emote("))
        self.assertIn("act_speech(", body("src/act_comm.c", "void do_pose("))
        self.assertIn("ignore_has_name(", body("src/act_comm.c", "bool is_note_to("))
        self.assertIn("ignore_has_name(", body("src/act_comm.c", "static int history_gather("))
        self.assertIn("act_is_speech && to != ch && is_ignoring( to, ch )",
                      body("src/comm.c", "void act_new("))

    def test_staff_are_never_ignored(self) -> None:
        helper = body("src/act_comm.c", "bool is_ignoring(")
        self.assertIn("IS_TRUSTED( speaker, LEVEL_IMMORTAL )", helper)

    def test_the_list_is_read_under_I(self) -> None:
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        case_i = save[save.index("\tcase 'I':\n", save.index("void fread_char(")):]
        case_i = case_i[:case_i.index("\tcase 'J':")]
        self.assertIn('"Ignore"', case_i)
        self.assertIn('"Ignoring"', case_i)
        self.assertIn('"Ignore %s~\\n"', save)


@unittest.skipIf(SKIP is not None, SKIP or "")
class IgnoreLiveTests(unittest.TestCase):
    def test_ignore_blocks_speech_and_keeps_its_list(self) -> None:
        with LiveMud() as mud:
            for name in ("Zigalpha", "Zigbeta", "Zigstaff"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zigalpha", Levl=10, Room=TEMPLE)
            patch_player_file(mud, "Zigbeta", Levl=10, Room=TEMPLE)
            patch_player_file(mud, "Zigstaff", Levl=70, Room=SQUARE)

            with mud.connect(timeout=120) as alpha, \
                    mud.connect(timeout=120) as beta, \
                    mud.connect(timeout=120) as staff:
                login(alpha, "Zigalpha", PASSWORD)
                login(beta, "Zigbeta", PASSWORD)
                login(staff, "Zigstaff", PASSWORD)
                for client in (alpha, beta, staff):
                    client.sync("scroll 0")

                alpha.must("ignore", "You are ignoring nobody.")
                alpha.must("ignore zigstaff", "The staff cannot be ignored.")
                alpha.must("ignore zigalpha", "You cannot ignore yourself.")
                alpha.must("ignore z1", "two to twelve letters")
                alpha.must("ignore zigbeta", "You are ignoring Zigbeta now")
                alpha.must("ignore", "You are ignoring (1 of 20): Zigbeta")

                # Everything Zigbeta says is lost on Zigalpha; a tell says so.
                beta.must("tell zigalpha whisperone", "Zigalpha is ignoring you.")
                beta.must("say spokentwo", "You say")
                beta.must("emote waves threefold", "waves threefold")
                beta.must("gossip gossipfour", "You gossip")
                beta.sync("note to all")
                beta.sync("note subject notefive")
                beta.sync("note + a note nobody ignoring me reads")
                beta.must("note send", "Note sent.")
                # Staff are always heard, and their gossip arriving says
                # every earlier line on Zigalpha's socket has arrived too.
                staff.must("gossip markerstaff", "You gossip")
                alpha.expect("markerstaff")
                heard = alpha.transcript
                for secret in ("whisperone", "spokentwo", "threefold", "gossipfour"):
                    self.assertNotIn(secret, heard, secret)
                self.assertNotIn("notefive", alpha.sync("note list"))
                history = alpha.sync("history gossip")
                self.assertIn("markerstaff", history)
                self.assertNotIn("gossipfour", history)

                # Zigbeta's own gossip still reached the staff.
                staff.drain(0.5)
                self.assertIn("gossipfour", staff.transcript)

                # Unignored, Zigbeta is heard again.
                alpha.must("ignore zigbeta", "You stop ignoring Zigbeta.")
                beta.must("tell zigalpha whispersix", "You tell Zigalpha")
                alpha.expect("whispersix")
                beta.must("say spokenseven", "You say")
                alpha.expect("spokenseven")
                self.assertIn("notefive", alpha.sync("note list"))

                # The list is kept across a quit.
                alpha.must("ignore zigbeta", "You are ignoring Zigbeta now")
                alpha.send("quit")
                self.assertTrue(alpha.wait_closed())

            saved = (mud.player_dir / "Zigalpha").read_text(encoding="latin-1")
            self.assertIn("Ignore Zigbeta~", saved)
            self.assertNotIn("Ignoring", saved)

            with mud.connect(timeout=120) as alpha:
                login(alpha, "Zigalpha", PASSWORD)
                alpha.must("ignore", "You are ignoring (1 of 20): Zigbeta")
                alpha.must("ignore clear", "You stop ignoring everybody.")
                alpha.must("ignore", "You are ignoring nobody.")
                alpha.send("quit")
                self.assertTrue(alpha.wait_closed())

            saved = (mud.player_dir / "Zigalpha").read_text(encoding="latin-1")
            self.assertNotRegex(saved, re.compile(r"^Ignor", re.M))

            # The old game's line, repeats and junk included, is tidied
            # into the list.
            patch_player_file(mud, "Zigalpha", Ignoring="zigbeta ZIGBETA x z9 zigcarol~")
            with mud.connect(timeout=120) as alpha:
                login(alpha, "Zigalpha", PASSWORD)
                alpha.must("ignore", "You are ignoring (2 of 20): Zigbeta Zigcarol")


if __name__ == "__main__":
    unittest.main()

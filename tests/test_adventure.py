"""ADVENTURE: what a character might do next, read-only (2026-11-15).

A view a player asks for, never sent unasked: the Mud School diploma, a
first fight and training, the guild choice before level 6, a quest, places
at their level and company, each only when it applies, with an exact
command or a route WALKTO publishes. It keeps no state: every line reads
what the game already keeps (src/adventure.c), and it leaves the tutorial
as the character set it.

Played in a disposable world (tests/live_mud.py copies area/; nothing
under player/, gods/, heroes/, backups/ or log/ is touched), with
synthetic Z characters only. The tutorial is left to its defaults: a new
character is made with it on, and a file from before it (no Tutorial line)
reads as off. TOC_TUTORIAL_GAP is long so no hint arrives unasked.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PW = "Zadvpass1"
TEMPLE = 4207
QUESTMASTER_ROOM = 2497
QUIET = {"TOC_NO_TUTORIAL": None, "TOC_TUTORIAL_GAP": "600"}
HEAD = "What you might do next"
ESC = "\x1b"


def make(mud: LiveMud, name: str, tutorial_line: bool = True, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    if fields:
        patch_player_file(mud, name, **fields)
    if not tutorial_line:
        # A file written before the tutorial existed: no Tutorial lines,
        # which reads as off (tutorial.c).
        path = mud.player_dir / name
        text = path.read_text(encoding="latin-1")
        path.write_text("\n".join(l for l in text.split("\n")
                                  if not l.startswith(("Tutorial ", "TutSchool ", "TutPending "))),
                        encoding="latin-1")


def tutorial_line(mud: LiveMud, name: str) -> str:
    for line in (mud.player_dir / name).read_text(encoding="latin-1").splitlines():
        if line.startswith("Tutorial "):
            return line
    return ""


def adventure(client) -> str:
    said = client.sync("adventure", timeout=30)
    assert HEAD in said, said
    # It must fit the default page (22 lines): a paged view eats the next
    # command as its "return".
    assert "Hit Return" not in said and "[Return" not in said, said
    return said


@unittest.skipIf(SKIP is not None, SKIP or "")
class AdventureTests(unittest.TestCase):
    def test_the_view_follows_the_character(self) -> None:
        with LiveMud(extra_env=QUIET) as mud:
            make(mud, "Zadvgod", Levl=70, Room=TEMPLE)
            # A new character, the tutorial on as creation leaves it.
            make(mud, "Zadvnewbie")
            # An existing character from before the tutorial: off.
            make(mud, "Zadvold", tutorial_line=False, Levl=4, Cla=0, Room=TEMPLE)
            make(mud, "Zadvlast", Levl=5, Cla=0, Room=TEMPLE)
            make(mud, "Zadvmonk", Levl=4, Cla=4, Room=TEMPLE)
            make(mud, "Zadvjoined", Levl=4, Gui=2, Room=TEMPLE)
            make(mud, "Zadvquester", Levl=10, Room=QUESTMASTER_ROOM)

            with mud.connect(timeout=120) as staff:
                login(staff, "Zadvgod", PW)

                # --- a new character: Mud School, a first fight; nothing
                # about guilds or quests yet; the tutorial still on.
                with mud.connect(timeout=120) as new:
                    login(new, "Zadvnewbie", PW)
                    said = adventure(new)
                    self.assertIn("* Mud School:", said)
                    self.assertIn("WALKTO MUD SCHOOL", said)
                    self.assertIn("* First fight:", said)
                    for absent in ("* Guild:", "* Quests:", "* Your quest:"):
                        self.assertNotIn(absent, said)
                    self.assertRegex(new.sync("tutorial status"), r"(?i)\bon\b")
                    new.sync("save")
                    new.send("quit")
                    new.wait_closed()
                self.assertTrue(tutorial_line(mud, "Zadvnewbie").startswith("Tutorial 1 "),
                                tutorial_line(mud, "Zadvnewbie"))

                # --- an existing character with the tutorial off: the guild
                # choice at level 4, no tutorial banner, nothing unasked, and
                # the tutorial still off after ADVENTURE, a save and a login.
                with mud.connect(timeout=120) as old:
                    login(old, "Zadvold", PW)
                    self.assertNotIn("[Tutorial]", old.transcript)
                    said = adventure(old)
                    self.assertIn("* Guild:", said)
                    self.assertIn("WALKTO MELANCHOLY", said)
                    self.assertNotIn("last level to choose", said)
                    self.assertIn("* Quests:", said)
                    self.assertIn("a quest ready now", said)
                    self.assertRegex(old.sync("tutorial status"), r"(?i)\boff\b")

                    # The diploma: carried, held, stashed.
                    staff.must("load obj 3715", "You create")
                    staff.must("give diploma zadvold", "You give")
                    said = adventure(old)
                    self.assertIn("HOLD DIPLOMA", said)
                    self.assertNotIn("WALKTO MUD SCHOOL", said)
                    old.sync("hold diploma")
                    self.assertNotIn("diploma", adventure(old).lower())
                    old.sync("remove diploma")
                    old.must("stash put diploma", "stash")
                    said = adventure(old)
                    self.assertIn("is in your stash", said)
                    self.assertIn("STASH GET DIPLOMA", said)

                    # Plain Telnet: colour off, nothing but plain text, lines
                    # that fit an 80-column screen.
                    old.sync("color off")
                    said = adventure(old)
                    self.assertNotIn(ESC, said)
                    self.assertNotIn("{0", said)
                    self.assertTrue(all(ord(c) < 128 for c in said), said)
                    for line in said.replace("\r", "").split("\n"):
                        self.assertLessEqual(len(line), 79, line)

                    # Nothing comes unasked: a quiet spell says nothing new.
                    mark = len(old.transcript)
                    old.drain(3.0)
                    self.assertNotIn(HEAD, old.transcript[mark:])
                    self.assertNotIn("[Tutorial", old.transcript[mark:])

                    old.must("save", "Saving")
                    old.send("quit")
                    old.wait_closed()
                self.assertTrue(tutorial_line(mud, "Zadvold").startswith("Tutorial 0 "),
                                tutorial_line(mud, "Zadvold"))
                with mud.connect(timeout=120) as old:
                    login(old, "Zadvold", PW)
                    self.assertNotIn("[Tutorial]", old.transcript)
                    said = adventure(old)
                    self.assertIn("* Guild:", said)
                    self.assertIn("is in your stash", said)
                    self.assertRegex(old.sync("tutorial status"), r"(?i)\boff\b")

                    # --- the guild window: level 5 is the last level; a
                    # monk and a member see nothing about guilds.
                    with mud.connect(timeout=120) as last, \
                            mud.connect(timeout=120) as monk, \
                            mud.connect(timeout=120) as joined:
                        login(last, "Zadvlast", PW)
                        login(monk, "Zadvmonk", PW)
                        login(joined, "Zadvjoined", PW)
                        self.assertIn("last level to choose", adventure(last))
                        self.assertNotIn("* Guild:", adventure(monk))
                        self.assertNotIn("* Guild:", adventure(joined))

                        # Company: players near the level, counted, never named.
                        said = adventure(old)
                        self.assertIn("* Company:", said)
                        self.assertNotRegex(said, r"Zadv(last|monk|joined)")
                        # A group replaces the count.
                        followed = last.sync("follow zadvold")
                        if "want any followers" in followed:
                            old.sync("nofollow")       # new characters start with it on
                            followed = last.sync("follow zadvold")
                        self.assertIn("You now follow", followed, followed)
                        old.must("group zadvlast", "joins your group")
                        said = adventure(old)
                        self.assertIn("you are grouped with 1 other", said, said)
                        self.assertNotIn("* Company:", said)

                        # --- level 6 gives the class's guild: the choice is gone.
                        staff.must("advance zadvlast 6", "")
                        said = adventure(last)
                        self.assertNotIn("* Guild:", said)

                # --- a quest: offered while none is out, then the one under
                # way, with no target named; and places at the level, each a
                # name WALKTO finds.
                with mud.connect(timeout=120) as quester:
                    login(quester, "Zadvquester", PW)
                    said = adventure(quester)
                    self.assertIn("a quest ready now", said)
                    self.assertIn("Places at your level", said)
                    places = re.findall(r"(?m)^\s+WALKTO (.+?)\s+(?:new to you|not yet walked end to end)\s*$",
                                        said.replace("\r", ""))
                    self.assertTrue(places, said)
                    self.assertLessEqual(len(places), 3)
                    for place in places:
                        self.assertNotIn("Hyrule", place)
                        walked = quester.sync("walkto " + place)
                        self.assertIn("You set off for", walked, (place, walked))
                        quester.sync("walkto stop")
                    # Every fixed WALKTO the view names is one WALKTO knows.
                    for place in ("mud school", "altar", "melancholy", "square"):
                        walked = quester.sync("walkto " + place)
                        self.assertIn("You set off for", walked, (place, walked))
                        quester.sync("walkto stop")
                    staff.must(f"transfer zadvquester {QUESTMASTER_ROOM}", "")
                    asked = quester.sync("aquest request", timeout=30)
                    self.assertNotIn("no quest", asked.lower(), asked)
                    said = adventure(quester)
                    self.assertIn("* Your quest:", said)
                    self.assertIn("AQUEST INFO", said)
                    self.assertNotIn("a quest ready now", said)


@unittest.skipIf(SKIP is not None, SKIP or "")
class AdventureReturnTests(unittest.TestCase):
    """ADVENTURE RETURN (2026-11-27): for a player coming back -- time away,
    what is under way and its time, the next command, and the hints they
    have had. Opt-in, and spoiler-free: no hint not yet had."""

    def test_a_returning_player_sees_what_they_left(self) -> None:
        import time as _time
        away = int(_time.time()) - 3 * 86400 - 600
        with LiveMud() as mud:
            make(mud, "Zadvstaff", Levl=70, Room=TEMPLE)
            # Two hints had: move (bit 0) and consider (bit 2).
            make(mud, "Zadvback", Levl=20, Room=TEMPLE, LastOut=away,
                 Rested="5000 1", Tutorial="1 5")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as back:
                login(staff, "Zadvstaff", PW)
                login(back, "Zadvback", PW)
                said = back.sync("adventure return", timeout=30)
                self.assertIn("Welcome back, Zadvback -- away 3 days.", said)
                self.assertRegex(said, r"Rested: \d+ bonus experience")
                self.assertIn("Hints you have had: move, consider.", said)
                self.assertIn("Next: TUTORIAL NEXT", said)
                self.assertNotIn("Hit Return", said)
                # A hint had, again; one not had, not shown.
                self.assertIn("CONSIDER", back.sync("tutorial consider"))
                self.assertIn("You have not had that hint yet", back.sync("tutorial wear"))
                # The plain view is unchanged, and points here.
                self.assertIn("ADVENTURE RETURN", adventure(back))

                staff.must(f"transfer zadvback {QUESTMASTER_ROOM}", "")
                asked = back.sync("aquest request", timeout=30)
                self.assertNotIn("no quest", asked.lower(), asked)
                said = back.sync("adventure back", timeout=30)
                self.assertRegex(said, r"\* An? (rush |emergency |daily )?quest: \d+ minutes? left\.")
                self.assertIn("Next: AQUEST INFO", said)


class AdventureSourceTests(unittest.TestCase):
    """It reads, and changes nothing: no save, no award, no tutorial step,
    no quest or reward touched."""

    def test_it_writes_nothing(self) -> None:
        src = (ROOT / "src" / "adventure.c").read_text(encoding="utf-8")
        body = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
        for call in ("save_char_obj", "achievement_unlock", "achievement_note",
                     "achievement_record", "achievement_set_insert", "tutorial_event", "tut_event",
                     "add_quest_points", "gain_exp", "SET_BIT", "REMOVE_BIT",
                     "->tutorial_on", "->tutorial_done", "->nextquest", "->guild ="):
            self.assertNotIn(call, body, call)

    def test_it_is_last_in_the_command_table(self) -> None:
        interp = (ROOT / "src" / "interp.c").read_text(encoding="utf-8")
        table = interp.split("cmd_table	[] =", 1)[1].split("/* End of list. */", 1)[0]
        names = re.findall(r'\{\s*"([^"]+)"', table)
        # After every command that was there before it (TUTORIAL was the
        # last), so no abbreviation that meant something moves.
        self.assertGreater(names.index("adventure"), names.index("tutorial"))
        self.assertEqual(names.index("adventure"), names.index("tutorial") + 1)
        self.assertEqual(names.count("adventure"), 1)


if __name__ == "__main__":
    unittest.main()

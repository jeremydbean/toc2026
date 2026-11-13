"""The new-player tutorial and the onboarding fixes beside it (2026-11-13).

- A character made now starts with the tutorial on, and its first entry
  says so and how to turn it off; a file with no Tutorial line (made
  before it) reads as off. TUTORIAL ON|OFF|STATUS|NEXT; what has been
  seen survives quitting, a lost link and a remort, and is never shown
  twice.
- Hints come from events, one at a time, and never during a fight.
- The guild choice at level 3 shows the exact commands; level 5 reminds;
  level 6 puts the guildless in their class's guild free and says so.
  Monks, necromancers and members hear none of it. PKILL at 15 is
  optional, never asks for a password, and is never turned on.
- Making a character, HELP at the class and alignment questions reads
  without choosing.
- JOIN's help, Mud School's signs, BEGINNERS and the first-entry line
  say what the game does.

Test worlds make characters with the tutorial off (TOC_NO_TUTORIAL in
tests/live_mud.py); these tests turn it back on.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import (
    SPARRING_FLOOR,
    LiveMud,
    _enter_game,
    create_character,
    login,
    patch_player_file,
    place_sparring_guard,
    skip_reason,
)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Ztutpass1"
TEMPLE = 4207
TUTORIAL_ON = {"TOC_NO_TUTORIAL": None, "TOC_TUTORIAL_CENSUS_SECS": "2"}
HINT = "[Tutorial:"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="latin-1")


def help_entry(text: str, header: str) -> str:
    start = text.index("\n" + header + "~\n")
    return text[start:text.index("\n~\n", start + 1)]


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    if fields:
        patch_player_file(mud, name, **fields)


def file_line(mud: LiveMud, name: str, key: str) -> str | None:
    for line in (mud.player_dir / name).read_text(encoding="latin-1").splitlines():
        if line.split(" ")[0] == key:
            return line
    return None


def upto(client, pattern: str) -> str:
    """Everything unread up to and including `pattern` (expect returns
    only the pattern)."""
    mark = len(client.transcript) - len(client.buffer)
    client.expect(pattern)
    return client.transcript[mark:]


def clear_hints(client) -> None:
    """See every hint the character has waiting or could ask for now, so
    the next one a test causes is the next shown."""
    for _ in range(16):
        if "seen every hint" in client.sync("tutorial next"):
            return
    raise AssertionError("TUTORIAL NEXT never ran out")


def drain_queue(client) -> None:
    """Let the hints already waiting come out by themselves."""
    for _ in range(12):
        if "a hint is waiting" not in client.sync("tutorial status"):
            return
        client.drain(7)
    raise AssertionError("the waiting hints never came")


def wait_for(client, text: str, seconds: int = 20, mark: int | None = None) -> str:
    """What arrived from `mark` (now, by default) until `text` did: pass the
    mark taken before a command when the hint may come with its reply."""
    mark = len(client.transcript) if mark is None else mark
    for _ in range(seconds):
        if text in client.transcript[mark:]:
            break
        client.drain(1)
    return client.transcript[mark:]


class TutorialSourceTests(unittest.TestCase):
    def test_join_help_says_the_level_six_guild_is_free(self) -> None:
        join = help_entry(read("area/commands.are"), "0 JOIN")
        self.assertNotIn("50 gold", join)
        self.assertIn("free", join)
        self.assertIn("until you reach level 6", join)
        self.assertIn("GAINLIST PREVIEW", join)

    def test_mud_school_signs_match_the_commands(self) -> None:
        school = read("area/school.are")
        self.assertNotIn("you need enough practices", school)
        self.assertIn("Training spends training sessions, not practices", school)
        self.assertIn("passed level 10", school)          # newbie_room_refuses
        self.assertNotIn("passed level 5.", school)
        self.assertIn("a banner, a vest, a shield, and a weapon", school)  # do_outfit
        self.assertIn("'HELP RECALL'", school)
        self.assertNotIn("Always type save before", school)

    def test_beginners_recall_and_the_first_entry_line(self) -> None:
        toc = read("area/toc.are")
        beginners = help_entry(toc, "-1 BEGINNERS")
        self.assertIn("somewhere else (HELP RECALL)", beginners)
        self.assertIn("TUTORIAL", beginners)
        self.assertIn("TUTORIAL OFF", help_entry(toc, "-1 'NEWBIE INFO' START BEGIN BEGINNER 'GETTING STARTED'"))
        comm = read("src/comm.c")
        self.assertNotIn("Welcome to ROM 2.4", comm)
        self.assertIn("Welcome to the Times of Chaos", comm)

    def test_help_tutorial_is_public_and_complete(self) -> None:
        page = help_entry(read("area/commands.are"), "0 TUTORIAL")
        for word in ("tutorial on", "tutorial off", "tutorial next", "TUTORIAL STATUS",
                     "older ones start with it off", "remorts"):
            self.assertIn(word, page)

    def test_the_hints_never_ask_for_a_password_or_turn_pk_on(self) -> None:
        tut = read("src/tutorial.c")
        texts = " ".join(re.findall(r'"([^"]*)"', tut[tut.index("static void tut_text"):
                                                       tut.index("static void tut_show")]))
        self.assertNotIn("password", texts.lower())
        self.assertNotIn("pkill <", texts.lower())
        self.assertIn("entirely optional", texts)
        self.assertIn("HELP PKILL", texts)
        self.assertIsNone(re.search(r"pk_state\s*=[^=]", tut))   # never sets it
        for command in ("HELP GUILDS", "GAINLIST PREVIEW <class> <guild>",
                        "WALKTO MELANCHOLY", "JOIN <guild>"):
            self.assertIn(command, texts)

    def test_tutorial_is_last_in_the_command_table_and_not_newbie(self) -> None:
        interp = read("src/interp.c")
        table = interp[re.search(r"cmd_table\s*\[\]", interp).start():]
        table = table[:table.index("/* End of list. */")]
        self.assertIn('{ "tutorial",       do_tutorial,', table)
        self.assertGreater(table.index('"tutorial"'), table.index('"cross"'))
        self.assertNotIn('"newbie",         do_tutorial', table)


@unittest.skipIf(SKIP is not None, SKIP or "")
class TutorialLiveTests(unittest.TestCase):
    def test_creation_help_first_entry_hints_and_persistence(self) -> None:
        with LiveMud(extra_env=TUTORIAL_ON) as mud:
            with mud.connect(timeout=120) as client:
                client.expect("by what name", "name:", "what is your name")
                client.send("Ztutnew")
                client.expect("did i get that right")
                client.send("Y")
                client.expect("password")
                client.send(PW)
                client.expect("retype password")
                client.send(PW)
                client.expect("what is your race")
                client.send("human")
                client.expect("what is your sex")
                client.send("m")
                menu = upto(client, "select a class")
                self.assertIn("strength: heavy weapons", menu)
                client.send("help")
                classes = upto(client, "select a class")
                self.assertIn("Six classes are played", classes)
                client.send("help monk")
                self.assertIn("select a class", upto(client, "select a class").lower())
                client.send("warrior")
                align = upto(client, "which alignment")
                self.assertIn("your weapon blows drain life", align)
                client.send("help")
                read_align = upto(client, "which alignment")
                self.assertIn("Alignment runs from -1000", read_align)
                client.buffer = ""
                client.send("n")
                _enter_game(client, PW)
                entry = client.transcript
                self.assertIn("Welcome to the Times of Chaos", entry)
                self.assertIn("The tutorial is ON", entry)
                self.assertIn("TUTORIAL OFF", entry)
                self.assertIn("ON", client.sync("tutorial status"))

                # Mud School, walked through to the diploma: the entrance's
                # step comes by itself, before the general ones.
                first = wait_for(client, f"{HINT} Mud School, step 1 of 11]", mark=0)
                self.assertIn("LOOK SIGN", first)
                self.assertIn("diploma", first)
                self.assertIn(f"{HINT} moving about]", wait_for(client, f"{HINT} moving about]", mark=0))
                before = len(client.transcript)
                client.sync("north")                      # 3757: train and practice
                second = wait_for(client, f"{HINT} Mud School, step 2 of 11]", mark=before)
                self.assertIn("TRAIN", second)
                client.sync("south")
                client.sync("north")
                client.drain(8)
                self.assertEqual(1, client.transcript.count("Mud School, step 2 of 11]"))
                self.assertEqual(1, client.transcript.count("Mud School, step 1 of 11]"))
                self.assertNotIn(f"{HINT} Mud School's signs]", client.transcript)
                self.assertIn("Mud School: 2 of 11 steps seen", client.sync("tutorial status"))

                # NEXT shows the next unseen one at once; CONSIDER typed
                # first makes its hint unnecessary.
                client.sync("consider nobody")
                nxt = client.sync("tutorial next")
                self.assertIn(HINT, nxt)
                self.assertNotIn("sizing up a fight", nxt)
                self.assertNotIn("moving about", nxt)

                # The Oracle: tried once, the hint is done and the
                # achievement earned; and nobody but a player killer comes
                # back dazed.
                self.assertIn("The Oracle's Sanctum", client.command("pray", 1.5))
                asked = client.command("ask what is a tick", 2.0)
                self.assertIn("Seeker of Answers", asked + client.transcript[-3000:])
                back = client.command("say done", 1.5)
                self.assertIn("settles gently", back)
                self.assertNotIn("dazed", back)
                self.assertIn("[x] asking the Oracle", client.sync("tutorial status"))

                off = client.must("tutorial off", "The tutorial is OFF")
                self.assertIn("TUTORIAL ON picks up", off)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            self.assertEqual("0", file_line(mud, "Ztutnew", "Tutorial").split()[1])
            with mud.connect(timeout=120) as client:
                login(client, "Ztutnew", PW)
                status = client.sync("tutorial status")
                self.assertIn("OFF", status)
                self.assertIn("[x] moving about", status)
                self.assertIn("[x] Mud School's signs", status)
                self.assertIn("[x] sizing up a fight", status)
                self.assertIn("Mud School: 2 of 11 steps seen", status)
                client.must("tutorial on", "The tutorial is ON")
                again = client.sync("tutorial next")
                self.assertNotIn("moving about]", again)
                self.assertNotIn("Mud School's signs]", again)
                # A lost link and a reconnect keep it all.
                client.sock.close()
            with mud.connect(timeout=120) as client:
                login(client, "Ztutnew", PW)
                status = client.sync("tutorial status")
                self.assertIn("The tutorial is ON", status)
                self.assertIn("[x] Mud School's signs", status)
                client.send("quit")
                self.assertTrue(client.wait_closed())

            # A file from before the tutorial: no line, so off, and silent.
            make(mud, "Ztutold")
            path = mud.player_dir / "Ztutold"
            text = path.read_text(encoding="latin-1")
            path.write_text("\n".join(l for l in text.split("\n") if not l.startswith("Tutorial ")),
                            encoding="latin-1", newline="")
            with mud.connect(timeout=120) as client:
                login(client, "Ztutold", PW)
                self.assertIn("The tutorial is OFF", client.sync("tutorial"))
                client.drain(8)
                self.assertNotIn("[Tutorial", client.transcript)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            self.assertIsNotNone(file_line(mud, "Ztutold", "Tutorial"))

            census = [l for l in (mud.root / "log" / "play.tsv").read_text(encoding="latin-1").splitlines()
                      if l.split("\t")[1:2] == ["tutorial"]]
            self.assertTrue(census, "no tutorial census row")
            self.assertEqual("-", census[-1].split("\t")[2])     # never a name
            self.assertIn("move=", census[-1])

    def test_guild_choice_levels_and_pk(self) -> None:
        with LiveMud(extra_env=TUTORIAL_ON) as mud:
            make(mud, "Ztutstaff", Levl=70, Room=TEMPLE)
            make(mud, "Ztutwar", Room=TEMPLE)                       # a warrior
            make(mud, "Ztutmonk", Room=TEMPLE, Cla=4)
            make(mud, "Ztutjoin", Room=TEMPLE, Gui=2)                # a warrior in the thieves
            with mud.connect(timeout=120) as staff:
                login(staff, "Ztutstaff", PW)
                with mud.connect(timeout=120) as war:
                    login(war, "Ztutwar", PW)
                    clear_hints(war)
                    # The diploma reaching them says what it is worth.
                    staff.must("load obj 3715", "You create")
                    staff.must("give diploma ztutwar", "You give")
                    got = wait_for(war, "the Mud School diploma]", 20)
                    self.assertIn("HOLD DIPLOMA", got)
                    war.must("hold diploma", "")
                    self.assertIn("diploma in hand", war.sync("tutorial status"))
                    staff.must("advance ztutwar 3", "")
                    choice = wait_for(war, "choosing a guild]", 30)
                    for command in ("HELP GUILDS", "GAINLIST PREVIEW <class> <guild>",
                                    "GAINLIST PREVIEW WARRIOR THIEF", "WALKTO MELANCHOLY",
                                    "JOIN <guild>", "at level 6 you join the warrior guild, free"):
                        self.assertIn(command, choice)
                    self.assertEqual(1, war.transcript.count("choosing a guild]"))
                    staff.must("advance ztutwar 5", "")
                    remind = war.sync("tutorial next")
                    self.assertIn("level 6 ends the choice", remind)
                    staff.must("advance ztutwar 6", "")
                    auto = war.sync("tutorial next")
                    self.assertIn("now in the warrior guild, free", " ".join(auto.split()))
                    staff.must("advance ztutwar 15", "")
                    pk = war.sync("tutorial next")
                    if "player killing" not in pk:
                        pk = war.sync("tutorial next")
                    self.assertIn("entirely optional", pk)
                    self.assertIn("HELP PKILL", pk)
                    self.assertNotIn("password", pk.lower())
                    self.assertNotIn("PKILLER", war.sync("score"))
                    war.send("quit")
                    self.assertTrue(war.wait_closed())
                self.assertRegex((mud.player_dir / "Ztutwar").read_text(encoding="latin-1"),
                                 r"\nGui\s+3\n")

                for name in ("Ztutmonk", "Ztutjoin"):
                    with mud.connect(timeout=120) as other:
                        login(other, name, PW)
                        other.must("tutorial on", "The tutorial is ON", "already on")
                        clear_hints(other)
                        staff.must(f"advance {name.lower()} 5", "")
                        other.drain(14)
                        for _ in range(4):
                            other.sync("tutorial next")
                        self.assertNotIn("choosing a guild]", other.transcript, name)
                        self.assertNotIn("the guild deadline]", other.transcript, name)
                        self.assertNotIn("JOIN <guild>", other.transcript, name)
                        other.send("quit")
                        self.assertTrue(other.wait_closed())
                staff.send("quit")
                staff.wait_closed()

    def test_no_hint_mid_fight_death_and_remort(self) -> None:
        with LiveMud(fixtures=True, extra_env=TUTORIAL_ON) as mud:
            make(mud, "Ztutgod", Levl=70, Room=TEMPLE)
            make(mud, "Ztutfight", Levl=20, Room=TEMPLE,
                 HMV="20000 20000 500 500 500 500", HMVP="20000 500 500")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Ztutgod", PW)
                login(hero, "Ztutfight", PW)
                hero.must("tutorial on", "The tutorial is ON", "already on")
                # Let what a first look queued come out, so nothing is
                # waiting but what the fight causes.
                drain_queue(hero)
                place_sparring_guard(staff, "Ztutgod", SPARRING_FLOOR)
                staff.must(f"transfer ztutfight {SPARRING_FLOOR}", "")
                mark = len(hero.transcript)
                hero.sync("kill sparring", 10)
                hero.drain(9)                             # rounds, and no hint
                self.assertIn("Fighting:", staff.must("stat char ztutfight", "Fighting"))
                self.assertNotIn(HINT, hero.transcript[mark:])
                staff.sync("peace")
                after = wait_for(hero, "fighting and fleeing]", 20)
                self.assertIn("WIMPY", after)

                staff.must("slay ztutfight", "")
                died = wait_for(hero, f"{HINT} dying]", 20)
                self.assertIn("GET ALL CORPSE", died)
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
                staff.send("quit")
                staff.wait_closed()

            before = file_line(mud, "Ztutfight", "Tutorial")
            patch_player_file(mud, "Ztutfight", Levl=54, Room=TEMPLE, Attr="25 25 25 25 25")
            with mud.connect(timeout=120) as hero:
                login(hero, "Ztutfight", PW)
                hero.sync("stand")
                hero.must(f"remort {PW} mage none human", "equipped by the Gods")
                status = hero.sync("tutorial status")
                self.assertIn("The tutorial is ON", status)
                self.assertIn("[x] dying", status)
                hero.send("quit")
                self.assertTrue(hero.wait_closed())
            self.assertEqual(before, file_line(mud, "Ztutfight", "Tutorial"))


if __name__ == "__main__":
    unittest.main()

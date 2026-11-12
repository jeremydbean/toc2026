"""Staff commands and staff help (review, 2026-11-12).

- A wizinvis creator's SHUTDOWN was a REBOOT: the marker that tells the
  wrappers not to start the game again, area/shutdown.txt, was written
  only when the caller was visible. Wizinvis now changes only what the
  players are told.
- GKICK had no rank check and took mobiles: a lower staff member kicked a
  higher one out of the room. It is players only, under rank_protects.
- WARN set PLR_WARNED and PLR_LOG on a mobile, whose act bits are ACT_
  flags, and announced it on INFO.
- QUI ran QUIET: "quiet" stood before "qui" in the command table, so the
  "spell QUIT out" reminder was unreachable.
- The level 50 message promised a hero quest that silences the player;
  the hero level is bought (AQUEST BUY HERO) and heroes level on to 54
  plus their remorts.
- JOBS names commands under the trust they need, and QUESTS the trust
  ANNOUNCE needs; both are held to the command table here.

The fixtures are synthetic Z characters, and a synthetic Killuminati --
the creator is a name -- in throwaway worlds.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "webadmin"))

import help_audit  # noqa: E402
import help_index  # noqa: E402
from live_mud import (  # noqa: E402
    LiveMud,
    create_character,
    login,
    patch_player_file,
    place_sparring_guard,
    room_of,
    skip_reason,
)

SKIP = skip_reason()
PASSWORD = "Zstaffcmd1"
TEMPLE = 4207


def make(mud: LiveMud, name: str, level: int) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PASSWORD)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, Levl=level, Room=TEMPLE)


def command_levels() -> dict:
    """Each command's lowest table level (FINGER has two rows)."""
    levels: dict = {}
    for name, level, _show, _fun in help_audit.commands():
        levels[name] = min(level, levels.get(name, level))
    return levels


class StaffHelpTests(unittest.TestCase):
    """No server: the help read as the game reads it, against interp.c."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.entries = help_index.load_helps(ROOT / "area")
        cls.levels = command_levels()

    def page(self, topic: str):
        res = help_index.resolve(self.entries, topic, 72)
        self.assertEqual(res.how, "exact", topic)
        return res.entry

    def test_jobs_names_each_command_under_its_trust(self) -> None:
        jobs = self.page("jobs")
        self.assertEqual(jobs.level, 60)
        blocks = re.findall(r"^  (\d\d)  (.*?)(?=^  \d\d  |^\S|\Z)", jobs.text, re.M | re.S)
        self.assertGreaterEqual(len(blocks), 10, jobs.text)
        wrong = []
        named = 0
        for trust, body in blocks:
            for word in re.findall(r"\b[A-Z][A-Z]+\b", body):
                level = self.levels.get(word.lower())
                if level is None or level < 60:
                    continue      # not a command, or a player's (BUG, TYPO)
                named += 1
                if level != int(trust):
                    wrong.append(f"{word} under {trust}, needs {level}")
        self.assertGreater(named, 40)
        self.assertEqual(wrong, [])

    def test_quests_says_the_trust_announce_needs(self) -> None:
        quests = self.page("quests")
        text = " ".join(quests.text.split())
        self.assertEqual(quests.level, 60)
        self.assertIn("ANNOUNCE reaches everybody online, from trust %d"
                      % self.levels["announce"], text)
        self.assertIn("REPOP (trust %d)" % self.levels["repop"], text)
        self.assertNotIn("reboot", text.lower())

    def test_commandments_describe_the_game_as_it_is(self) -> None:
        page = self.page("commandments")
        text = " ".join(page.text.split())
        self.assertEqual(page.level, 60)
        # The old preface said the rules had not been revised; they have.
        self.assertNotIn("have not been revised", text)
        self.assertIn("SHUTDOWN and REBOOT are the creator's", text)
        self.assertIn("BAN and DENY are the creator's", text)
        for command in ("shutdown", "reboot", "ban", "deny"):
            self.assertEqual(self.levels[command], 72, command)
        # Every staff command a rule names exists.
        for word in ("TRANSFER", "FORCE", "NOCHANNELS", "WARN", "JAIL", "FREEZE",
                     "PRESTORE", "IMMTALK", "WALKTO", "LORE", "COMPARE", "BUG"):
            self.assertIn(word, text)
            self.assertIn(word.lower(), self.levels, word)

    def test_shutdown_help_no_longer_warns_of_a_reboot(self) -> None:
        text = " ".join(self.page("shutdown").text.split())
        self.assertNotIn("writes no shutdown.txt", text)
        self.assertIn('a SHUTDOWN says "The game is shutting down."', text)

    def test_the_level_fifty_message_names_the_way_on(self) -> None:
        source = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        self.assertNotIn("COMMUNICATE", source)
        self.assertNotIn("Hero of the Realms", source)
        self.assertIn("AQUEST BUY HERO", source)
        self.assertIn("level 54 plus your remorts", source)

    def test_qui_stands_before_quiet(self) -> None:
        names = [name for name, *_ in help_audit.commands()]
        self.assertLess(names.index("question"), names.index("qui"))
        self.assertLess(names.index("qui"), names.index("quiet"))


@unittest.skipIf(SKIP is not None, SKIP or "")
class StaffCommandLiveTests(unittest.TestCase):
    def test_a_wizinvis_creator_shuts_the_game_down(self) -> None:
        with LiveMud() as mud:
            make(mud, "Killuminati", 70)
            make(mud, "Zlistener", 10)
            marker = mud.root / "area" / "shutdown.txt"
            # The repository carries a stale copy; the test world must not.
            marker.unlink(missing_ok=True)
            with mud.connect(timeout=120) as creator, \
                    mud.connect(timeout=120) as mortal:
                login(creator, "Killuminati", PASSWORD)
                login(mortal, "Zlistener", PASSWORD)
                # He logs in wizinvis, always.
                self.assertNotIn("Killuminati", mortal.sync("who"))
                mark = len(mortal.transcript)   # the greeting credits him
                creator.send("shutdown")
                self.assertTrue(mortal.wait_closed(timeout=60),
                                "the game did not close the connection")
                assert mud.proc is not None
                self.assertIsNotNone(mud.proc.wait(timeout=60))
                heard = mortal.transcript[mark:]
            self.assertIn("The game is shutting down.", heard)
            self.assertNotIn("Killuminati", heard)
            self.assertTrue(marker.is_file(), "no shutdown.txt: the game would restart")
            self.assertIn("Shutdown by Killuminati.",
                          marker.read_text(encoding="latin-1"))

    def test_gkick_warn_and_qui(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zkicker", 69)
            make(mud, "Zhigher", 70)
            make(mud, "Zkicked", 10)
            with mud.connect(timeout=120) as kicker, \
                    mud.connect(timeout=120) as higher, \
                    mud.connect(timeout=120) as mortal:
                login(kicker, "Zkicker", PASSWORD)
                login(higher, "Zhigher", PASSWORD)
                login(mortal, "Zkicked", PASSWORD)
                place_sparring_guard(higher, "Zhigher", TEMPLE)
                kicker.sync(f"goto {TEMPLE}")
                self.assertEqual(room_of(higher, "Zkicker"), TEMPLE)
                self.assertEqual(room_of(higher, "Zkicked"), TEMPLE)

                # Rank first: a 69 cannot kick a 70, and nothing is said.
                higher.drain(0.3)
                mark = len(higher.transcript)
                kicker.must("gkick zhigher south", "You failed.")
                self.assertEqual(room_of(higher, "Zhigher"), TEMPLE)
                self.assertNotIn("kicks you", higher.transcript[mark:])

                # Players only.
                kicker.must("gkick sparring south", "You can only kick players.")
                stat = higher.must("stat mob sparring", "Room:")
                self.assertRegex(stat, r"Room: %d\b" % TEMPLE)

                # A mortal still goes.
                kicker.must("gkick zkicked south", "You kick Zkicked full on")
                self.assertNotEqual(room_of(higher, "Zkicked"), TEMPLE)

                # WARN refuses a mobile, and INFO hears nothing.
                mortal.drain(0.5)
                mark = len(mortal.transcript)
                higher.must("warn sparring", "Only players can be warned.")
                mortal.sync("look")
                self.assertNotIn("has been warned", mortal.transcript[mark:])
                stat = higher.must("stat mob sparring", "Act")
                self.assertNotRegex(stat, r"Act 1:.*\bmountable\b")

                # QUI is QUIT's reminder; QUIE is QUIET.
                self.assertIn("you have to spell it out", mortal.sync("qui"))
                self.assertIn("only hear says and emotes", mortal.sync("quie"))
                self.assertIn("Quiet mode removed", mortal.sync("quiet"))
                self.assertIn("you have to spell it out", mortal.sync("QUI"))
                for client in (kicker, higher, mortal):
                    client.send("quit")
                    client.wait_closed()


    def test_lifting_a_warning_lifts_only_its_own_log(self) -> None:
        """Owner, 2026-11-12: WARN turned LOG on and lifting the warning
        turned it off, even a LOG staff had set with LOG <name>. Now a
        warning lifts only the LOG it turned on (WarnLog in the file)."""
        log_bit = 1 << 22            # PLR_LOG is (W)

        def saved(client, name: str) -> tuple[bool, str]:
            client.sync("save")
            text = (mud.player_dir / name).read_text(encoding="latin-1")
            act = int(re.search(r"(?m)^Act\s+(-?\d+)", text).group(1))
            warn = re.search(r"(?m)^WarnLog\s+(\d+)", text)
            return bool(act & log_bit), warn.group(1) if warn else "-"

        with LiveMud() as mud:
            make(mud, "Killuminati", 70)
            make(mud, "Zwarnone", 10)
            make(mud, "Zwarntwo", 10)
            with mud.connect(timeout=120) as creator, \
                    mud.connect(timeout=120) as one, \
                    mud.connect(timeout=120) as two:
                login(creator, "Killuminati", PASSWORD)
                login(one, "Zwarnone", PASSWORD)
                login(two, "Zwarntwo", PASSWORD)

                # The warning's own LOG goes with it, by WARN or by PARDON.
                creator.must("warn zwarnone", "WARNING flag set")
                self.assertEqual(saved(one, "Zwarnone"), (True, "1"))
                creator.must("warn zwarnone", "no longer has a WARNING")
                self.assertEqual(saved(one, "Zwarnone"), (False, "-"))
                creator.must("warn zwarnone", "WARNING flag set")
                creator.must("pardon zwarnone warned", "WARNED flag removed")
                self.assertEqual(saved(one, "Zwarnone"), (False, "-"))

                # A LOG staff set first outlives the warning.
                creator.must("log zwarntwo", "now being LOGGED")
                creator.must("warn zwarntwo", "WARNING flag set")
                self.assertEqual(saved(two, "Zwarntwo"), (True, "0"))
                creator.must("warn zwarntwo", "no longer has a WARNING")
                self.assertEqual(saved(two, "Zwarntwo"), (True, "-"))

                # And one set during the warning is staff's too.
                creator.must("log zwarntwo", "no longer being LOGGED")
                creator.must("warn zwarntwo", "WARNING flag set")
                creator.must("log zwarntwo", "no longer being LOGGED")
                creator.must("log zwarntwo", "now being LOGGED")
                creator.must("warn zwarntwo", "no longer has a WARNING")
                self.assertEqual(saved(two, "Zwarntwo"), (True, "-"))

if __name__ == "__main__":
    unittest.main()

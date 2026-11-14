"""Hyrule findings from the review of 2026-11-13, each played live.

- A mortal who struck a guardian but was not in the killer's group was
  handed its key (hyrule_guardian_slain) and never its boss achievement,
  and so never the chest's; and only whoever OPENed the chest closed got
  the chest's, so every keyholder after the first went without. Strikers
  in the room are credited as the key rule credits them, and a claim
  from the chest credits its claimer.
- CONSIDER said "You should win easily" of an unshrunk Digdogger, whose
  every blow bounces. It now says nothing can harm it yet.
- Playing the Recorder in Digdogger's den earned "Play It Again" (drain
  the lake). Only the lake's own puzzle does.
"""

from __future__ import annotations

import re
import unittest

from live_mud import (SPARRING_FLOOR, LiveMud, create_character, login,
                      patch_player_file, skip_reason)
from test_consider_guardian import DIGDOGGER, considered
from test_hyrule_guardian_keys import (LAIR, TEMPLE, connect, kill, make, obj,
                                       quit_all)

SKIP = skip_reason()
PW = "Zrcpass1"
DEN = 30489
RECORDER = 30413


def achv(mud: LiveMud, name: str) -> set[str]:
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    return {line.split()[1] for line in text.splitlines() if line.startswith("Achv ")}


@unittest.skipIf(SKIP is not None, SKIP or "")
class GuardianCreditTests(unittest.TestCase):
    def test_a_late_striker_and_every_keyholder_are_credited(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zrvstaff", Levl=70, Room=TEMPLE, AfBy=0)
            for name in ("Zrvlead", "Zrvlate", "Zrvmate"):
                make(mud, name, Levl=30, Room=TEMPLE)
            staff, lead, late, mate = connect(mud, "Zrvstaff", "Zrvlead", "Zrvlate", "Zrvmate")
            lead.name, late.name, mate.name = "Zrvlead", "Zrvlate", "Zrvmate"
            try:
                for name in ("zrvlead", "zrvlate", "zrvmate"):
                    staff.must(f"transfer {name} {LAIR}", "")
                mate.must("follow zrvlead", "You now follow")
                lead.must("group zrvmate", "")
                staff.must(f"at {LAIR} set char aquamentus hp 30000", "")
                staff.must(f"at {LAIR} restore aquamentus", "")
                late.sync("kill aquamentus", timeout=60)
                late.drain(3.0)
                staff.must(f"at {LAIR} peace", "")
                staff.must(f"at {LAIR} set char aquamentus hp 10", "")
                staff.must(f"at {LAIR} restore aquamentus", "")
                fought = kill(staff, lead, "aquamentus", LAIR)
                packs = {c.name: c.sync("inventory", timeout=60) for c in (lead, late, mate)}
                # The ungrouped striker unlocks and opens the chest with
                # their own key: "Unlock and open the treasure chest ...
                # after defeating its guardian".
                opened = "".join(late.sync(line, timeout=60) for line in (
                    "unlock east", "open east", "east", "unlock chest", "open chest",
                    "get all chest"))
                # The killer's group follow: the chest stands open.
                for client in (lead, mate):
                    client.sync("east", timeout=60)
                lead_got = lead.sync("get all chest", timeout=60)
                mate_got = mate.sync("get all chest", timeout=60)
                for client in (lead, late, mate):
                    client.sync("save", timeout=60)
                got = {name: achv(mud, name) for name in ("Zrvlead", "Zrvlate", "Zrvmate")}
            finally:
                quit_all(lead, late, mate, staff)

        for name, keys in got.items():
            print(name, sorted(k for k in keys if k.startswith("hyrule")))
        self.assertIn("is DEAD", fought, fought)
        self.assertIn("Eagle's key", packs["Zrvlate"])
        self.assertIn("first Triforce shard", opened, opened)
        self.assertIn("hyrule-eagle", got["Zrvlate"], "late striker: boss achievement")
        self.assertIn("hyrule-chest-1", got["Zrvlate"], "late striker opened the chest")
        self.assertIn("hyrule-chest-1", got["Zrvlead"], "keyholder in an opened chest")


@unittest.skipIf(SKIP is not None, SKIP or "")
class ConsiderUntouchableTests(unittest.TestCase):
    def test_consider_says_nothing_harms_an_unshrunk_digdogger(self) -> None:
        with LiveMud(fixtures=True) as mud:
            for name in ("Zrcstaff", "Zrcplay"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PW)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zrcstaff", Levl=70, Room=SPARRING_FLOOR)
            patch_player_file(mud, "Zrcplay", Levl=50, Room=SPARRING_FLOOR,
                              HMV="30000 30000 300 300 300 300", HMVP="30000 300 300")
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as player:
                login(staff, "Zrcstaff", PW)
                login(player, "Zrcplay", PW)
                for client in (staff, player):
                    client.sync("scroll 0")
                staff.must(f"load mob {DIGDOGGER}", "You create")
                staff.must("set char zrcplay hitroll 200", "")
                staff.must("set char zrcplay damroll 200", "")
                said = player.must("consider digdogger", "level")
                before = staff.sync("stat mob digdogger", timeout=60)
                fought = player.sync("kill digdogger", timeout=60) + player.drain(9.0)
                after = staff.sync("stat mob digdogger", timeout=60)
                staff.sync("peace")
                for client in (player, staff):
                    client.send("quit")
                    client.wait_closed()
            text = (mud.root / "log" / "progress.tsv").read_text(encoding="latin-1")
        hp = lambda s: re.search(r"Hp: (-?\d+)/(\d+)", s).group(0)
        rows = considered(text)
        self.assertIn("bounce", fought)
        self.assertEqual(hp(before), hp(after), "no blow lands on it")
        self.assertNotRegex(said, r"(?i)you should win|you would need", said)
        self.assertIn("too big to hurt", said)
        self.assertIn("untouchable", rows[0], rows)


@unittest.skipIf(SKIP is not None, SKIP or "")
class DenLakeTests(unittest.TestCase):
    def test_playing_in_the_den_is_not_draining_the_lake(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zrdstaff", Levl=70, Room=TEMPLE, AfBy=0)
            make(mud, "Zrdplay", Levl=40, Room=TEMPLE, objects=obj(RECORDER, 30))
            staff, player = connect(mud, "Zrdstaff", "Zrdplay")
            try:
                staff.must(f"transfer zrdplay {DEN}", "")
                played = player.sync("play recorder", timeout=60)
                player.sync("save", timeout=60)
                got = achv(mud, "Zrdplay")
            finally:
                quit_all(player, staff)
        self.assertIn("shrinks to a third", played, played)
        self.assertNotIn("hyrule-drain-lake", got,
                         "no lake was drained: this is Digdogger's den")


class InstantDeathSourceTests(unittest.TestCase):
    def test_what_nothing_harms_defies_instant_death_whole(self) -> None:
        """A backstab fatality or Farslay could kill an unshrunk Digdogger or
        a ringed patra, which the poison tick was already refused. The roll
        is random, so the rule is held here: the defiance asks
        hyrule_shrugs_off, and such a creature takes not even the hard
        blow."""
        from pathlib import Path
        fight = (Path(__file__).resolve().parents[1] / "src" / "fight.c").read_text(encoding="latin-1")
        defies = fight.split("bool hyrule_defies_instant_death(", 1)[1].split("\n}", 1)[0]
        self.assertIn("hyrule_shrugs_off(victim)", defies)
        resisted = fight.split("static bool hyrule_instant_kill_resisted(", 1)[1].split("\n}", 1)[0]
        self.assertLess(resisted.index("hyrule_shrugs_off(victim)"), resisted.index("share ="))


if __name__ == "__main__":
    unittest.main()

"""Starving and parched hurt, somewhat, and keep you awake (owner,
2026-11-12: "hunger and thirst should damage you somewhat as they get
extreme, and maybe prevent you from sleeping because you are too hungry or
thirsty to sleep").

Each tick a mortal spends with hunger (COND_FULL) or thirst at 0 takes a
share of their maximum hit points -- hunger 2% the first tick, a point more
each tick in a row to 8%; thirst 3% to 10% -- straight off the hit points,
never below one (hunger_thirst_tick in src/update.c). SLEEP is refused
while either is at 0, and a sleeper is woken by it.

One world, synthetic Z characters in the fixture gallery (joined to
nothing, so nothing wanders in), four ticks:

- Zstarve, 10,000 hit points, starving and parched from the file: the
  first tick takes exactly 5%, the second more; SLEEP is refused for
  hunger, then (fed) for thirst, then (watered) sleeps; a tick passes with
  nothing taken; set back to 0 while asleep, the next tick wakes it and
  takes 5% again, less its regeneration -- the count started over.
- Zfrail, two hit points of a hundred, starving and parched: held at one,
  never killed. Its line each tick is the test's clock.
- Zhero (level 51) and Zlinkdead (who lost the link) take nothing.
- Zbuilder (level 20 trusted to 60) starves like any mortal: staff are
  immortals by level (owner, 2026-11-12: "let trusted players act as
  mortals across the board").
"""
from __future__ import annotations

import re
import time
import unittest
from pathlib import Path

from live_mud import (LiveMud, SPARRING_GALLERY, create_character, login, patch_player_file,
                      skip_reason)

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zhungry1pass"
ROOM = SPARRING_GALLERY
BIG = "10000 10000 100 100 100 100"
HUNGER_LINE = re.compile(r"cramps with hunger|weak from hunger|You are starving, and")
HURT_LINE = re.compile(r"cramps with hunger|weak from hunger|You are starving, and"
                       r"|dry with thirst|parched and cracked|desperate for water")
HP = re.compile(r"Hp: (-?\d+)/(\d+)")
TICK = 100      # a tick is 40 to 80 seconds


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed(), name
    patch_player_file(mud, name, Room=ROOM, **fields)


def hit_points(staff, name: str) -> tuple[int, int]:
    match = HP.search(staff.must("stat char %s" % name, "Hp:"))
    assert match, name
    return int(match.group(1)), int(match.group(2))


def lines_of(text: str, pattern: re.Pattern) -> int:
    """How many lines say it: hunger and thirst share one line a tick."""
    return sum(1 for line in text.splitlines() if pattern.search(line))


def wait_lines(client, pattern: re.Pattern, count: int, timeout: float = TICK) -> None:
    """Pump the client until `count` of its lines say it -- not expect(),
    whose buffer a sync() replaces."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if lines_of(client.transcript, pattern) >= count:
            return
        client.drain(0.5)
    raise AssertionError("waited %ds for %d of %s; last output: %r"
                         % (timeout, count, pattern.pattern, client.transcript[-600:]))


@unittest.skipIf(SKIP is not None, SKIP or "")
class HungerAndThirstTests(unittest.TestCase):
    def test_starving_hurts_more_each_tick_never_kills_and_keeps_you_awake(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zwarden", Levl=70)
            make(mud, "Zstarve", Levl=20, HMV=BIG, HMVP="10000 100 100", Cond="0 0 0")
            make(mud, "Zfrail", Levl=20, HMV="2 100 100 100 100 100", HMVP="100 100 100",
                 Cond="0 0 0")
            make(mud, "Zhero", Levl=51, HMV=BIG, HMVP="10000 100 100", Cond="0 0 0")
            make(mud, "Zbuilder", Levl=20, Tru=60, HMV=BIG, HMVP="10000 100 100",
                 Cond="0 0 0")
            make(mud, "Zlinkdead", Levl=20, HMV=BIG, HMVP="10000 100 100", Cond="0 0 0")

            with mud.connect(timeout=120) as warden, \
                 mud.connect(timeout=120) as starve, \
                 mud.connect(timeout=120) as frail, \
                 mud.connect(timeout=120) as hero, \
                 mud.connect(timeout=120) as builder:
                login(warden, "Zwarden", PW)
                warden.sync("scroll 0")
                warden.sync("goto %d" % ROOM)
                with mud.connect(timeout=120) as linkdead:
                    login(linkdead, "Zlinkdead", PW)
                # The socket closed without QUIT: link-dead in the gallery.
                # A tick can fall between that login and the server reading
                # the closed socket, while Zlinkdead is still connected and
                # rightly hurt (CI, 2026-11-13: 9512 of 10000). Wait until the
                # game holds it link-dead, then put it back to full, so only
                # link-dead ticks are measured.
                for _ in range(40):
                    if "zlinkdead" not in warden.sync("sockets").lower():
                        break
                    warden.drain(0.25)
                warden.must("restore zlinkdead", "restored")
                for client, name in ((hero, "Zhero"), (builder, "Zbuilder"),
                                     (frail, "Zfrail"), (starve, "Zstarve")):
                    login(client, name, PW)

                # --- The first tick: exactly 5% of 10,000 at full health. ---
                wait_lines(starve, HURT_LINE, 1)
                self.assertIn("Your stomach cramps with hunger", starve.transcript)
                self.assertIn("Your mouth is dry with thirst", starve.transcript)
                self.assertEqual((9500, 10000), hit_points(warden, "zstarve"))

                # --- The second tick takes more (7%, less a little regen). ---
                wait_lines(starve, HURT_LINE, 2)
                hp2, _ = hit_points(warden, "zstarve")
                self.assertGreater(9500 - hp2, 500)
                self.assertLessEqual(9500 - hp2, 700)

                # Held at one hit point, never killed.
                wait_lines(frail, HUNGER_LINE, 2)
                self.assertEqual((1, 100), hit_points(warden, "zfrail"))
                self.assertNotIn("KILLED", frail.transcript)

                # --- SLEEP: refused for hunger, then thirst; then sleeps. ---
                self.assertIn("too hungry to sleep", starve.sync("sleep"))
                warden.must("load obj 20", "You create")         # a magic mushroom
                warden.must("give mushroom zstarve", "You give")
                starve.must("eat mushroom", "You eat")
                self.assertIn("too thirsty to sleep", starve.sync("sleep"))
                warden.must("load obj 22", "You create")         # a magical spring
                starve.must("drink spring", "You drink", "no longer thirsty")
                starve.must("sleep", "You go to sleep")

                # --- A tick fed and watered takes nothing, wakes nobody. ---
                frail_ticks = lines_of(frail.transcript, HUNGER_LINE)
                lines = lines_of(starve.transcript, HURT_LINE)
                wait_lines(frail, HUNGER_LINE, frail_ticks + 1)
                starve.drain(1.0)
                self.assertEqual(lines, lines_of(starve.transcript, HURT_LINE))
                self.assertNotIn("awake", starve.transcript)

                # --- Starving again, asleep: woken, and the count is new. ---
                warden.must("set char zstarve hunger 0", "Hunger value")
                warden.must("set char zstarve thirst 0", "Thirst value")
                before, _ = hit_points(warden, "zstarve")
                mark = len(starve.transcript)
                wait_lines(starve, HURT_LINE, lines + 1)
                starve.drain(1.0)
                self.assertIn("Hunger gnaws you awake", starve.transcript[mark:])
                after, _ = hit_points(warden, "zstarve")
                # 5% again, less the tick's regeneration first.
                self.assertGreater(before - after, 400)
                self.assertLessEqual(before - after, 500)
                # The first words again: the count started over.
                self.assertIn("Your stomach cramps with hunger", starve.transcript[mark:])
                self.assertIn("Your mouth is dry with thirst", starve.transcript[mark:])
                # Awake: asleep, SLEEP would answer "already sleeping".
                self.assertIn("too hungry to sleep", starve.sync("sleep"))

                # --- Exempt: a hero and the link-dead. ---
                hero.drain(0.5)
                self.assertEqual([], HURT_LINE.findall(hero.transcript), "zhero")
                self.assertEqual((10000, 10000), hit_points(warden, "zhero"))
                # --- Not exempt: a mortal given trust is a mortal. ---
                builder.drain(0.5)
                self.assertTrue(HURT_LINE.findall(builder.transcript),
                                builder.transcript[-600:])
                self.assertLess(hit_points(warden, "zbuilder")[0], 10000)
                self.assertEqual((10000, 10000), hit_points(warden, "zlinkdead"))
                self.assertNotIn("KILLED", frail.transcript)


class HungerSourceTests(unittest.TestCase):
    def test_hunger_is_never_a_blow_and_magic_sleep_holds(self) -> None:
        text = (ROOT / "src" / "update.c").read_text(encoding="latin-1")
        start = text.index("static void hunger_thirst_tick")
        body = text[start:text.index("\n}\n", start)]
        self.assertNotIn("damage(", body)              # no kill, no drain, no fight
        self.assertIn("pool_scale", body)
        self.assertIn("ch->hit - 1", body)            # never below one
        self.assertIn("AFF_SLEEP", body)              # the spell's sleep holds


if __name__ == "__main__":
    unittest.main()

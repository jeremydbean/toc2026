"""The jail paths that were traced but never played (owner, 2026-11-12:
a mortal must not escape an active sentence; "fix it all").

tests/test_jail_confinement.py plays walking, recall, scrolls, portals,
teleport, the pocket rooms, prayer, staff moves, remort, DELETE and three
kinds of death. This module plays the rest, each in a cell that has a
door -- the synthetic cell, room 3 given an exit north to the Temple and
one east to a death trap, and no flags at all -- so the sentence, never
the room, is what holds the prisoner:

- a mount: a prisoner riding in the cell, and one jailed in the saddle
  (the mount is led into the cell beside them, unridden);
- SUMMON of a prisoner, by a mortal and by staff (staff's summons is a
  portal in the cell, which the prisoner may not enter);
- GATE and the portal spell, cast at a prisoner -- the caster going in --
  and cast by the prisoner from the cell;
- RAISE DEAD cast on a prisoner's corpse carried out of the cell;
- a death trap: the door to it, a staff TRANSFER into it, and a saved
  room inside it at login;
- a death by poison, alone in the cell with nobody striking: the tick's
  own blow, and the death lands in the cell.

Starvation and thirst cannot kill: they take hit points each tick, but
never below one (hunger_thirst_tick in update.c; a cell is no shelter).
The poison test holds a starving, parched prisoner at one hit point
through the same tick to show it.

Synthetic Z characters in throwaway worlds only.
"""
from __future__ import annotations

import unittest

from live_mud import LiveMud, login, patch_player_file, room_of, skip_reason
from test_jail_confinement import (
    CELL,
    JAILED,
    PW,
    TEMPLE,
    file_field,
    give_skill,
    make,
)

SKIP = skip_reason()
DEATH_TRAP = 724          # The Yawning Depths, camelot.are: ROOM_DT
OAK_SQUARE = 2401
HORSE = 1109              # shire.are: a sentinel, mountable horse
SADDLE = 27
MANA = "900 900 9000 9000 900 900"


def synthetic_cell(mud: LiveMud) -> None:
    """Room 3 gets an exit north to the Temple and one east to a death
    trap, and loses every flag; the server is restarted to read it."""
    path = mud.root / "area" / "limbo.are"
    text = path.read_bytes().decode("latin-1")
    start = text.index("#3\nThe Jail~")
    flags = text.index("0 BNX 0\nS\n", start)
    text = (text[:flags]
            + "0 0 0\nD0\n~\n~\n0 -1 %d\nD1\n~\n~\n0 -1 %d\nS\n" % (TEMPLE, DEATH_TRAP)
            + text[flags + len("0 BNX 0\nS\n"):])
    path.write_bytes(text.encode("latin-1"))
    mud.restart()
    with mud.connect(timeout=120) as probe:
        probe.expect("by what name", "name:")


def cast(client, line: str, *outcomes: str, tries: int = 8) -> str:
    """Cast until the spell is really cast: a lost concentration is the
    caster's own roll, not what the test is about."""
    for _ in range(tries):
        reply = client.sync(line)
        if "lost your concentration" in reply:
            continue
        if any(text in reply for text in outcomes):
            return reply
        raise AssertionError("%r said %r, none of %r" % (line, reply, outcomes))
    raise AssertionError("%r: concentration lost %d times" % (line, tries))


def ride(client, mount: str = "horse") -> None:
    for _ in range(12):
        reply = client.sync("ride %s" % mount)
        if "You mount your steed" in reply:
            return
        if "bucked" not in reply:
            raise AssertionError("ride said %r" % reply)
    raise AssertionError("the horse bucked twelve times")


def deaths(mud: LiveMud, name: str) -> int:
    path = mud.root / "log" / "deaths.log"
    return path.read_text().count("DEATH: %s " % name) if path.exists() else 0


@unittest.skipIf(SKIP is not None, SKIP or "")
class JailPathTests(unittest.TestCase):
    def test_mounts_summons_travel_raise_dead_and_death_traps(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zwarden", 70)
            for spell in ("summon", "poison"):
                give_skill(mud, "Zwarden", spell, 100)
            # Both clerics: gate, portal and summon are theirs, and raise
            # dead the caller's.
            make(mud, "Zinmate", 50, Cla=1, HpManaMove=MANA)
            make(mud, "Zcaller", 50, Cla=1, HpManaMove=MANA)
            for name in ("Zinmate", "Zcaller"):
                for spell in ("gate", "portal", "summon", "raise dead"):
                    give_skill(mud, name, spell, 100)
            give_skill(mud, "Zinmate", "ride", 100)
            synthetic_cell(mud)

            with mud.connect(timeout=120) as warden, \
                 mud.connect(timeout=120) as inmate, \
                 mud.connect(timeout=120) as caller:
                login(warden, "Zwarden", PW)
                login(inmate, "Zinmate", PW)
                login(caller, "Zcaller", PW)
                for client in (warden, inmate, caller):
                    client.sync("scroll 0")
                inmate.must("nosummon", "no longer immune")
                caller.must("nosummon", "no longer immune")

                def held(what: str) -> None:
                    self.assertEqual(CELL, room_of(warden, "Zinmate"), what)
                    self.assertIn("is jailed", warden.sync("jail zinmate status"), what)

                # Control: gate reaches the inmate while free, so a refusal
                # later is the sentence and not the spell.
                warden.must("transfer zinmate %d" % OAK_SQUARE, "Ok", "arrives", "transfer")
                self.assertEqual(OAK_SQUARE, room_of(warden, "Zinmate"))
                cast(caller, "cast gate zinmate", "step through a gate")
                self.assertEqual(OAK_SQUARE, room_of(warden, "Zcaller"))
                warden.must("transfer zcaller %d" % TEMPLE, "Ok", "arrives", "transfer")
                warden.must("transfer zinmate %d" % TEMPLE, "Ok", "arrives", "transfer")

                # --- A prisoner on horseback in the cell. ---
                warden.must("jail zinmate 7", *JAILED)
                held("jailed")
                deadline = file_field(mud, "Zinmate", "Jw_Timer")
                warden.sync("goto %d" % CELL)
                warden.must("load mob %d" % HORSE, "You create")
                warden.must("load obj %d" % SADDLE, "You create")
                warden.must("give saddle zinmate", "You give")
                ride(inmate)
                for door in ("north", "east"):
                    self.assertIn("serving a jail sentence", inmate.sync(door), door)
                    held("mounted, " + door)
                self.assertNotIn("Your mount", inmate.sync("order horse north"))
                held("order the mount")
                inmate.must("dismount", "You dismount")

                # --- Jailed in the saddle: led in, mount and all. ---
                warden.must("jail zinmate release", "released")
                self.assertEqual(TEMPLE, room_of(warden, "Zinmate"))
                warden.sync("goto %d" % TEMPLE)
                warden.must("load mob %d" % HORSE, "You create")
                warden.must("load obj %d" % SADDLE, "You create")
                warden.must("give saddle zinmate", "You give")
                ride(inmate)
                warden.must("jail zinmate 7", *JAILED)
                held("jailed mounted")
                deadline = file_field(mud, "Zinmate", "Jw_Timer")
                # Taken out of the saddle; the horse came along.
                self.assertIn("aren't riding", inmate.sync("dismount"))
                warden.sync("goto %d" % CELL)
                self.assertGreaterEqual(warden.sync("look").lower().count("horse"), 2)
                for door in ("north", "east"):
                    self.assertIn("serving a jail sentence", inmate.sync(door), door)
                    held("led in, " + door)

                # --- Summons. ---
                warden.sync("goto %d" % TEMPLE)
                cast(caller, "cast summon zinmate", "You failed")
                held("a mortal's summon")
                # Staff summon by opening a portal at the target; the
                # prisoner may not take it.
                warden.must("cast summon zinmate", "aware of the summons")
                inmate.drain(0.5)
                self.assertIn("portal", inmate.sync("look").lower())
                self.assertIn("serving a jail sentence", inmate.sync("enter portal"))
                held("staff's summons portal")

                # --- Gate and portal: at the prisoner, and from the cell. ---
                cast(caller, "cast gate zinmate", "You failed")
                self.assertEqual(TEMPLE, room_of(warden, "Zcaller"),
                                 "a gate to a prisoner took the caster into the cell")
                cast(caller, "cast portal zinmate", "You failed")
                self.assertNotIn("portal", caller.sync("look").lower())
                cast(inmate, "cast gate zcaller", "You failed")
                held("gate from the cell")
                cast(inmate, "cast portal zcaller", "You failed")
                held("portal from the cell")

                # --- Raise dead on the prisoner's corpse, carried out. ---
                warden.sync("goto %d" % CELL)
                warden.sync("slay zinmate")
                inmate.drain(1.0)
                held("slain")
                self.assertEqual(1, deaths(mud, "Zinmate"))
                warden.must("get corpse", "You get")
                warden.sync("goto %d" % TEMPLE)
                warden.must("drop corpse", "You drop")
                cast(caller, "cast 'raise dead' corpse", "cannot find its way")
                held("raise dead")
                self.assertIn("corpse of Zinmate", caller.sync("look"))

                # --- Death traps. ---
                warden.must("transfer zinmate %d" % DEATH_TRAP, "JAIL Zinmate RELEASE")
                held("transfer into a death trap")
                inmate.send("quit")
                self.assertTrue(inmate.wait_closed())
                self.assertEqual(deadline, file_field(mud, "Zinmate", "Jw_Timer"))

            # A file saved with the prisoner in a death trap: the login
            # puts them in the cell, where the trap is not.
            patch_player_file(mud, "Zinmate", Room=DEATH_TRAP)
            with mud.connect(timeout=120) as warden, \
                 mud.connect(timeout=120) as inmate:
                login(warden, "Zwarden", PW)
                login(inmate, "Zinmate", PW)
                inmate.drain(5.0)   # two and a half death-trap pulses
                self.assertNotIn("KILLED", inmate.transcript)
                self.assertEqual(CELL, room_of(warden, "Zinmate"))
                self.assertIn("is jailed", warden.sync("jail zinmate status"))
                self.assertEqual(1, deaths(mud, "Zinmate"))

    def test_a_poisoned_prisoner_dies_in_the_cell_and_hunger_kills_nobody(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zwarden", 70)
            give_skill(mud, "Zwarden", "poison", 100)
            make(mud, "Zpoisoned", 30)
            make(mud, "Zstarving", 20)
            synthetic_cell(mud)
            with mud.connect(timeout=120) as warden, \
                 mud.connect(timeout=120) as poisoned, \
                 mud.connect(timeout=120) as starving:
                login(warden, "Zwarden", PW)
                login(poisoned, "Zpoisoned", PW)
                login(starving, "Zstarving", PW)
                for client in (warden, poisoned, starving):
                    client.sync("scroll 0")
                warden.must("jail zpoisoned 7", *JAILED)
                warden.must("jail zstarving 7", *JAILED)
                warden.sync("goto %d" % CELL)

                # Poisoned, then nobody fighting anybody, then the maximum
                # set below zero: the next tick's regeneration brings the
                # hit points down to it, and the poison's blow, its own,
                # kills.
                for _ in range(10):
                    warden.sync("cast poison zpoisoned")
                    if "You feel very sick" in poisoned.drain(0.5):
                        break
                else:
                    self.fail("the poison never took")
                warden.must("peace", "battle is ended", "All is peaceful")
                warden.sync("goto %d" % TEMPLE)
                warden.must("set char zpoisoned hp -10", "set to -10")

                # Starving and parched, at one hit point, through the same tick.
                warden.must("set char zstarving hp 1", "set to 1")
                warden.must("restore zstarving", "restored", "Ok")
                warden.must("set char zstarving hunger 0", "Ok", "set", "now")
                warden.must("set char zstarving thirst 0", "Ok", "set", "now")

                before = deaths(mud, "Zpoisoned")
                poisoned.expect("You shiver and suffer", timeout=150)
                poisoned.expect("KILLED", timeout=30)
                self.assertEqual(before + 1, deaths(mud, "Zpoisoned"))
                text = (mud.root / "log" / "deaths.log").read_text()
                self.assertRegex(text, r"DEATH: Zpoisoned \(level 30\) killed by themselves")
                self.assertEqual(CELL, room_of(warden, "Zpoisoned"))
                self.assertIn("is jailed", warden.sync("jail zpoisoned status"))

                starving.drain(1.0)
                self.assertNotIn("KILLED", starving.transcript)
                self.assertEqual(0, deaths(mud, "Zstarving"))
                self.assertEqual(CELL, room_of(warden, "Zstarving"))
                self.assertIn("is jailed", warden.sync("jail zstarving status"))


if __name__ == "__main__":
    unittest.main()

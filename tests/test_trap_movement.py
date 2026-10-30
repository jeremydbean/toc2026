"""A trap that kills a player on the way out ends the move.

Audit 2026-10-21: after room_affect, move_char asked whether in_room was
NULL -- but a slain player is not extracted, they are moved to the death
room, so the move went on: char_from_room took them out of the death room
and char_to_room put them through the exit, alive on 1 hit point at the
far end. Every trap check in movement now asks gone_after_blow() against
the room the character stood in.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from live_mud import (EAST_PADDOCK, GAS_HALL, LiveMud, WEST_PADDOCK, create_character, login,
                      patch_player_file, room_of, skip_reason)

SKIP = skip_reason()
ROOT = pathlib.Path(__file__).resolve().parents[1]
PASSWORD = "Ztrap1pass"
TEMPLE = 4207
DEATH_ROOM = 4216       # where a slain player is put; its only exit is down
GAS_EXIT_NAME = "Beyond The Gas Hall"   # the fixture room west of GAS_HALL


def run(client, command: str, settle: float = 1.2) -> str:
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class TrapMovementSourceTests(unittest.TestCase):
    def test_no_trap_check_in_movement_asks_for_null(self) -> None:
        move = (ROOT / "src" / "act_move.c").read_text(encoding="latin-1")
        calls = [m.start() for m in re.finditer(r"room_affect\(", move)]
        # How many there are is not the point (a rider's arrival used to
        # make two, which a pinned count of five held in place -- review,
        # 2026-10-22); that each one is guarded is.
        self.assertTrue(calls)
        for at in calls:
            after = move[at:at + 400]
            self.assertIn("gone_after_blow(", after, after)


# What interpret() says to a command typed below its position (WEST is
# POS_STANDING): the walker never tried the exit.
POSITION_REFUSALS = ("Lie still; you are DEAD", "You are hurt far too bad for that",
                     "You are too stunned to do that", "In your dreams, or what?",
                     "Better stand up first")


def departure_outcome(said: str) -> str:
    """What one WEST out of the gas hall did, read from the order of what
    it said. The stinking cloud also goes off on everybody in its room each
    tick, and its poison ticks too, with the same words -- so which death
    belongs to the move is a matter of order, not of text:

    * "arrived": the move finished (anything after the arrival, a poison
      tick's death included, happened in the far room);
    * "killed-leaving": gas, then KILLED, and no arrival -- the departure
      trap killed the walker, and the move must have ended there;
    * "walked-dead": KILLED and then the arrival -- the dead walked on
      through the exit, which is the bug this module exists for;
    * "before-move": a tick killed the walker in the hall before WEST ran,
      and WEST was then typed in the death room (resting, no west exit);
      that attempt tested nothing and is discarded, not counted;
    * "felled": the gas left the walker mortally wounded, incapacitated or
      stunned, short of dead, and the move stopped in the hall -- no death
      to test, so discarded as well. That includes a tick's gas that felled
      the walker before WEST ran, answered only by the position refusal
      (CI, 2026-10-27: "You are hurt far too bad for that." with no gas
      inside the reply was read as unclear);
    * "unclear": anything else."""
    arrival = said.find(GAS_EXIT_NAME)
    killed = said.find("You have been KILLED")
    gassed = said.find("Poison gas!")
    if killed < 0:
        if arrival >= 0:
            return "arrived"
        felled = ("mortally wounded", "incapacitated", "You are stunned")
        if 0 <= gassed and any(text in said[gassed:] for text in felled):
            return "felled"
        if any(text in said for text in POSITION_REFUSALS):
            return "felled"
        return "unclear"
    if arrival >= 0:
        return "arrived" if arrival < killed else "walked-dead"
    # A walker revived in the death room rests there, and its only exit is
    # down, so a WEST typed after a death from a tick is refused one way
    # or the other.
    if any(text in said[killed:] for text in ("Alas, you cannot go that way",
                                               "You feel too relaxed")
           + POSITION_REFUSALS):
        return "before-move"
    return "killed-leaving" if 0 <= gassed < killed else "unclear"


@unittest.skipIf(SKIP is not None, SKIP or "")
class TrapMovementLiveTests(unittest.TestCase):
    def test_a_lethal_departure_trap_ends_the_move(self) -> None:
        # The fixture world's gas hall: joined to nothing, so no wanderer,
        # player or second cloud can be in it.
        with LiveMud(fixtures=True) as mud:
            for name in ("Zwalker", "Ztrapper"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zwalker", Levl=10, Room=TEMPLE)
            patch_player_file(mud, "Ztrapper", Levl=70, Room=GAS_HALL)

            with mud.connect(timeout=120) as walker, mud.connect(timeout=120) as trapper:
                login(walker, "Zwalker", PASSWORD)
                login(trapper, "Ztrapper", PASSWORD)
                walker.sync("scroll 0")
                trapper.must("set skill ztrapper 'stinking cloud' 100", "skill is now 100")
                trapper.sync("set char ztrapper mana 30000")
                trapper.sync("set char zwalker hp 1")
                # SET CHAR HP sets the maximum; each RESTORE below brings
                # the walker to it.
                self.assertRegex(trapper.must("stat char zwalker", "Hp:"), r"Hp: -?\d+/1\b")

                # The cloud's 2d8 kills a player on 1 hit point about one
                # time in four (dead is -11); a survivor simply arrives,
                # which is correct. Every step is synced and confirmed: the
                # cloud is there, the walker stands restored in the hall,
                # and only then is WEST typed.
                outcomes = []
                for _ in range(40):
                    trapper.sync("restore ztrapper")
                    cast = trapper.sync("cast 'stinking cloud'", timeout=60)
                    # The first cast raises the cloud; later ones find it
                    # standing ("Nothing seems to happen" means the room
                    # already has its affect).
                    self.assertTrue("noxious fumes" in cast or "Nothing seems" in cast, cast)
                    trapper.must("restore zwalker", "restored")
                    trapper.sync("force zwalker stand")
                    trapper.must(f"transfer zwalker {GAS_HALL}", "Ok.")
                    # A tick's gas can kill the walker on 1 hit point in the
                    # moment between TRANSFER and this check (CI, 2026-10-30:
                    # 4216 != 32702). That attempt never reached WEST; try
                    # again.
                    where = room_of(trapper, "zwalker")
                    if where == DEATH_ROOM:
                        outcomes.append("before-move")
                        continue
                    self.assertEqual(where, GAS_HALL)
                    # TIME is the barrier: a walker the gas leaves mortally
                    # wounded may not type WORTH, which used to be.
                    said = walker.sync("west", timeout=60)
                    outcome = departure_outcome(said)
                    outcomes.append(outcome)
                    self.assertNotEqual(outcome, "walked-dead",
                                        "the dead walked through the exit:\n" + said)
                    self.assertNotEqual(outcome, "unclear", repr(said))
                    if outcome == "killed-leaving":
                        break
                else:
                    self.fail(f"the cloud never killed the walker on the way out: {outcomes}")

                self.assertEqual(room_of(trapper, "zwalker"), DEATH_ROOM, said)


PROMPT_RE = re.compile(r"<-?\d+hp")


def gas(text: str) -> int:
    """room_affect says exactly one of these each time a stinking cloud
    goes off on somebody."""
    return text.count("Poison gas!") + text.count("noxious fumes that fill the air")


def gas_in_move(text: str, arrival: str) -> int | None:
    """The cloud's fires that belong to the move itself: the burst of output
    from the prompt before the arrival's room name to the prompt after it.
    A stinking cloud also goes off on everybody in its room each tick
    (char_update), with the same words; a tick's fire comes with a prompt
    of its own, before or after, so it is never counted (CI, 2026-10-25:
    a tick in the two seconds after an arrival counted twice). None when
    the move did not arrive."""
    at = text.find(arrival)
    if at < 0:
        return None
    before = list(PROMPT_RE.finditer(text, 0, at))
    start = before[-1].end() if before else 0
    after = PROMPT_RE.search(text, at)
    return gas(text[start:after.start() if after else len(text)])


@unittest.skipIf(SKIP is not None, SKIP or "")
class MountedTrapTests(unittest.TestCase):
    def test_a_rider_sets_off_the_arrival_trap_once_as_a_walker_does(self) -> None:
        """Review 2026-10-22 (G3): do_riding ran the destination's trap
        before the arrival line with rev_dir[door] and again after the look
        with door, so a whole-room trap (exit 10) struck a rider twice.
        A walker and a rider each go east into a stinking cloud, and the
        rider back out through it."""
        horse, saddle = 740, 27      # a riding horse (ACT_MOUNTABLE); a saddle
        # Outdoors (no mount goes indoors) and not safe: the fixture world's
        # paddocks, joined to nothing, so nothing wanders in.
        start, gassed = WEST_PADDOCK, EAST_PADDOCK
        with LiveMud(fixtures=True) as mud:
            for name in ("Zgaswalker", "Zgasrider", "Zgasmaker"):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.drain(1.0)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
            hearty = dict(Levl=10, Room=start, HMV="5000 5000 500 500 500 500",
                          HMVP="5000 500 500")
            patch_player_file(mud, "Zgaswalker", **hearty)
            patch_player_file(mud, "Zgasrider", Sk="100 'ride'", **hearty)
            patch_player_file(mud, "Zgasmaker", Levl=70, Room=start)

            with mud.connect(timeout=120) as walker, mud.connect(timeout=120) as rider, \
                    mud.connect(timeout=120) as maker:
                login(walker, "Zgaswalker", PASSWORD)
                login(rider, "Zgasrider", PASSWORD)
                login(maker, "Zgasmaker", PASSWORD)
                for client in (walker, rider):
                    client.sync("scroll 0")
                maker.must(f"load obj {saddle}", "You create")
                maker.must("give saddle zgasrider", "You give")
                maker.must(f"load mob {horse}", "You create")
                # Ride is capped at 90%: a buck costs hit points, not the try.
                for _ in range(10):
                    mounted = rider.sync("ride horse", timeout=60)
                    if "You mount your steed" in mounted:
                        break
                    # A buck is the only other answer worth another try.
                    self.assertNotIn("aren't here", mounted, mounted)
                    self.assertNotIn("dismount your current", mounted, mounted)
                else:
                    self.fail("the rider never got on the horse")

                maker.must("set skill zgasmaker 'stinking cloud' 100", "skill is now 100")
                maker.sync("set char zgasmaker mana 30000")

                def cloud_stands() -> bool:
                    return "Affected by: stinking cloud" in maker.must(
                        f"stat room {gassed}", "Vnum:")

                def through_cloud(client, direction: str, back: str, arrival: str) -> str:
                    """One move through the cloud, with the cloud proven to
                    stand for the whole of it. It lasts one to three ticks
                    (spell_stinking_cloud's timer), so one raised just
                    before a move can blow away under it -- the CI failure
                    where a walker went east into clear air. A cloud still
                    standing after the move stood during it (nothing raises
                    one in between); one gone afterwards makes the try say
                    nothing, so the mover goes back and tries again under a
                    fresh cloud."""
                    for _ in range(6):
                        if not cloud_stands():
                            maker.sync(f"goto {gassed}")
                            self.assertIn("noxious fumes",
                                          maker.sync("cast 'stinking cloud'", timeout=60))
                            maker.sync(f"goto {start}")
                        said = client.sync(direction, timeout=60)
                        if cloud_stands():
                            return said
                        client.sync(back, timeout=60)
                    self.fail(f"no cloud stood through a {direction} move in six tries")

                walked_in = through_cloud(walker, "east", "west", "The East Paddock")
                # RIDE and the bucks before it lag the rider; sync waits that out.
                seen_from = len(walker.transcript)
                rode_in = through_cloud(rider, "east", "west", "The East Paddock")
                # The walker, already there, saw the rider arrive: the LOOK
                # pulls in everything sent before it; read across the ride.
                walker.sync("look")
                seen = walker.transcript[seen_from:]
                rode_out = through_cloud(rider, "west", "east", "The West Paddock")

                for name in ("zgaswalker", "zgasrider"):
                    maker.sync(f"restore {name}")
                for client in (walker, rider, maker):
                    client.send("quit")
                    client.wait_closed()

        self.assertEqual(gas_in_move(walked_in, "The East Paddock"), 1, walked_in)
        self.assertIn("rides in", seen, "the rider walked rather than rode:\n" + seen)
        self.assertEqual(gas_in_move(rode_in, "The East Paddock"), 1, rode_in)
        self.assertEqual(gas_in_move(rode_out, "The West Paddock"), 1, rode_out)


if __name__ == "__main__":
    unittest.main()

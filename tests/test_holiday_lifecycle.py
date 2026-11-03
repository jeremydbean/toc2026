"""The holiday fair's lifecycle, played live (review, 2026-11-02).

Every finding of the review has a behavioural test here, in a disposable
LiveMud world with synthetic Z characters:

* **The vendor and the event boss are known by identity, not address.**
  Both were checked by scanning the character list for the remembered
  pointer, and the pool hands a freed CHAR_DATA to the next mobile made:
  PURGE ROSALIND then LOAD MOB made the sparring guard "the vendor", and a
  purged boss's guard became "the boss" (SUMMONEVENT STATUS called it
  ALIVE, would not summon another, and its despawn took the guard away).
  extract_char now clears both (holiday_forget, event_boss_forget).
* **A boss's defeat is announced only when it is slain.** A purged boss
  used to be announced "defeated" at the next tick.
* **The boss's arrival and departure are seen in the room.** Both act()
  calls had no actor and sent nothing, so a player with shouts off saw
  neither.
* **The egg hunt's budget is the square's own area**, so eggs anywhere
  else cannot stop it; and **every egg on the ground is gathered when
  Noblegarden ends**, however many (the old gather stopped at 96), while
  carried and contained eggs stay.
* **The calendar runs in one process**: TOC_DATE_FILE is read at every
  look at the date, so one world is walked from holiday to holiday --
  active to active, active to none, none to active -- and repeated
  HOLIDAYS REFRESH never doubles the fair.
* **HOLIDAYS ON <date>** answers any day from the same code as today, and
  the matrix below holds every holiday's first and last day, the days
  either side, Winter Veil across the new year, Easter and Thanksgiving
  over several years and St. Patrick's Day before an early Noblegarden.
"""
from __future__ import annotations

import datetime
import re
import tempfile
import time
import unittest
from pathlib import Path

from live_mud import LiveMud, SPARRING_GUARD, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zholpass1"
SQUARE, TEMPLE, FLOOR = 2401, 4207, 32700
EGG, PIT = 29823, 3010

LOVE, STPATRICK, NOBLEGARDEN = "2027-02-10", "2027-03-15", "2027-03-25"
MIDSUMMER, NOTHING = "2027-06-25", "2027-08-01"

FAIR_RE = re.compile(
    r"\[staff\] fair: (?:vendor (?P<vendor>.+?) \(mob (?P<mob>\d+)\) in room \d+|no vendor); "
    r"decoration (?P<decor>\w+); eggs lying in the square's area (?P<local>\d+) of \d+, "
    r"anywhere (?P<anywhere>\d+)\.")


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def plain(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\x1b\[[0-9;]*m", "", text))


def fair(staff) -> dict:
    said = plain(staff.sync("holidays"))
    match = FAIR_RE.search(said)
    if match is None:
        raise AssertionError(f"no staff fair line in: {said[-600:]}")
    found = match.groupdict()
    found["local"] = int(found["local"])
    found["anywhere"] = int(found["anywhere"])
    return found


def set_date(path: Path, staff, date: str) -> str:
    path.write_text(date + "\n", encoding="ascii")
    staff.must("holidays refresh", "up to date")
    return plain(staff.sync("look"))


# ---------------------------------------------------------------- the calendar

FIXED = [  # in the order the game checks them: the first match wins
    ("Winter Veil", (12, 16), (1, 6)),
    ("the Lunar Festival", (1, 21), (2, 4)),
    ("Love is in the Air", (2, 7), (2, 20)),
    ("St. Patrick's Day", (3, 14), (3, 17)),
    ("Noblegarden", None, None),
    ("Children's Week", (4, 30), (5, 6)),
    ("the Midsummer Fire Festival", (6, 21), (7, 5)),
    ("Pirates' Day", (9, 19), (9, 19)),
    ("Brewfest", (9, 20), (10, 6)),
    ("Hallows End", (10, 18), (11, 1)),
    ("the Day of the Dead", (11, 2), (11, 3)),
    ("Pilgrim's Bounty", None, None),
]
EASTER = {2008: (3, 23), 2024: (3, 31), 2025: (4, 20), 2026: (4, 5), 2027: (3, 28),
          2028: (4, 16), 2038: (4, 25)}
THANKSGIVING = {2024: 28, 2025: 27, 2026: 26, 2027: 25, 2030: 28}


def window(name: str, day: datetime.date) -> tuple[datetime.date, datetime.date]:
    y = day.year
    if name == "Noblegarden":
        easter = datetime.date(y, *EASTER[y])
        return easter - datetime.timedelta(days=6), easter
    if name == "Pilgrim's Bounty":
        thanks = datetime.date(y, 11, THANKSGIVING[y])
        return thanks - datetime.timedelta(days=3), thanks + datetime.timedelta(days=3)
    (m1, d1), (m2, d2) = next((a, b) for n, a, b in FIXED if n == name)
    if (m1, d1) <= (m2, d2):
        return datetime.date(y, m1, d1), datetime.date(y, m2, d2)
    if day.month <= m2:
        return datetime.date(y - 1, m1, d1), datetime.date(y, m2, d2)
    return datetime.date(y, m1, d1), datetime.date(y + 1, m2, d2)


def expected_holiday(day: datetime.date) -> str | None:
    for name, _a, _b in FIXED:
        if name == "Noblegarden" and day.year not in EASTER:
            continue
        if name == "Pilgrim's Bounty" and day.year not in THANKSGIVING:
            continue
        first, last = window(name, day)
        if first <= day <= last:
            return name
    return None


def matrix_dates() -> list[datetime.date]:
    one = datetime.timedelta(days=1)
    days: set[datetime.date] = set()
    for name, _a, _b in FIXED:
        for year in (2027,) if name not in ("Noblegarden", "Pilgrim's Bounty") else ():
            first, last = window(name, datetime.date(year, 6, 1))
            days.update({first - one, first, last, last + one})
    for year in EASTER:
        first, last = window("Noblegarden", datetime.date(year, 4, 1))
        days.update({first - one, first, last, last + one})
    for year in THANKSGIVING:
        first, last = window("Pilgrim's Bounty", datetime.date(year, 11, 1))
        days.update({first - one, first, last, last + one})
    # Winter Veil both sides of two new years, and a leap day.
    days.update({datetime.date(2026, 12, 15), datetime.date(2026, 12, 16),
                 datetime.date(2026, 12, 31), datetime.date(2027, 1, 1),
                 datetime.date(2027, 1, 6), datetime.date(2027, 1, 7),
                 datetime.date(2027, 12, 16), datetime.date(2028, 1, 6),
                 datetime.date(2028, 2, 29)})
    # St. Patrick's Day before an early Noblegarden (Easter 2008, Mar 23).
    days.update({datetime.date(2008, 3, 14), datetime.date(2008, 3, 17),
                 datetime.date(2008, 3, 18)})
    return sorted(days)


class CalendarSpecTests(unittest.TestCase):
    """The test's own calendar agrees with the published dates."""

    def test_the_precedence_cases_are_real(self) -> None:
        self.assertEqual(window("Noblegarden", datetime.date(2008, 3, 20)),
                         (datetime.date(2008, 3, 17), datetime.date(2008, 3, 23)))
        self.assertEqual(expected_holiday(datetime.date(2008, 3, 17)), "St. Patrick's Day")
        self.assertEqual(expected_holiday(datetime.date(2008, 3, 18)), "Noblegarden")
        self.assertEqual(expected_holiday(datetime.date(2027, 1, 1)), "Winter Veil")
        self.assertIsNone(expected_holiday(datetime.date(2027, 1, 7)))
        self.assertGreater(len(matrix_dates()), 80)

    def test_janitors_and_scavengers_leave_the_hunt_alone(self) -> None:
        # Dresden's janitors take anything cheap every pulse, and its
        # thief, vagabond and servant scavenge; they took hidden eggs and
        # the hunt's count came up 11 of 12 in CI (2026-11-03).
        src = Path(__file__).resolve().parents[1] / "src"
        update = (src / "update.c").read_text(encoding="latin-1")
        scavenge = update[update.index("IS_SET(ch->act, ACT_SCAVENGER)"):]
        scavenge = scavenge[:scavenge.index("obj_to_char( obj_best, ch )")]
        self.assertIn("OBJ_VNUM_PAINTED_EGG", scavenge)
        special = (src / "special.c").read_text(encoding="latin-1")
        janitor = special[special.index("bool spec_janitor("):]
        janitor = janitor[:janitor.index("obj_to_char( trash, mob )")]
        self.assertIn("OBJ_VNUM_PAINTED_EGG", janitor)


@unittest.skipIf(SKIP is not None, SKIP or "")
class HolidayCalendarMatrixLiveTests(unittest.TestCase):
    def test_holidays_on_answers_every_boundary(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zholmatrix", Levl=20, Room=TEMPLE)
            with mud.connect(timeout=120) as client:
                login(client, "Zholmatrix", PW)
                client.sync("scroll 0")
                wrong = []
                for day in matrix_dates():
                    said = plain(client.sync(f"holidays on {day.isoformat()}"))
                    want = expected_holiday(day)
                    got = re.search(r"celebrates (.+?)\.(?: <|\s*$)", said)
                    got_name = got.group(1) if got else None
                    if got_name != want or (want is None and "No holiday falls on" not in said):
                        wrong.append(f"{day}: wanted {want}, got {said.strip()[:80]}")
                self.assertEqual(wrong, [])

                # Only a real, whole date is a date.
                for bad in ("2027-02-29", "2026-04-31", "2026-13-01", "2026-1-2",
                            "1899-12-31", "tomorrow", ""):
                    with self.subTest(bad=bad):
                        self.assertIn("Name a real day as YYYY-MM-DD",
                                      client.sync(f"holidays on {bad}"))
                self.assertIn("No holiday falls on 2028-02-29", client.sync("holidays on 2028-02-29"))
                self.assertIn("HOLIDAYS ON", client.sync("holidays sometime"))


# ------------------------------------------------- the vendor and the calendar

@unittest.skipIf(SKIP is not None, SKIP or "")
class HolidayVendorLifecycleLiveTests(unittest.TestCase):
    def test_vendor_identity_transitions_and_repeated_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            date_file = Path(tmp) / "today"
            date_file.write_text(LOVE + "\n", encoding="ascii")
            env = {"TOC_SEASON": None, "TOC_DATE_FILE": str(date_file)}
            with LiveMud(extra_env=env, fixtures=True) as mud:
                make(mud, "Zholstaff", Levl=70, Room=SQUARE)
                with mud.connect(timeout=120) as staff:
                    login(staff, "Zholstaff", PW)
                    staff.sync("scroll 0")
                    staff.must("holidays refresh", "up to date")
                    square = plain(staff.sync("look"))
                    self.assertEqual(square.count("Rosalind arranges red roses"), 1, square)
                    self.assertEqual(square.count("garland of paper hearts"), 1, square)
                    status = plain(staff.sync("holidays"))
                    self.assertIn("date 2027-02-10, from TOC_DATE_FILE", status)
                    self.assertIn("holiday: Love is in the Air, by the calendar", status)

                    # Refreshing again and again never doubles the fair.
                    staff.must(";".join(["holidays refresh"] * 5), "up to date")
                    square = plain(staff.sync("look"))
                    self.assertEqual(square.count("Rosalind arranges red roses"), 1, square)
                    self.assertEqual(square.count("garland of paper hearts"), 1, square)

                    # A purge of the whole room is put back, once each.
                    staff.sync("purge")
                    self.assertNotIn("Rosalind", plain(staff.sync("look")))
                    staff.must("holidays refresh", "up to date")
                    staff.must("holidays refresh", "up to date")
                    square = plain(staff.sync("look"))
                    self.assertEqual(square.count("Rosalind arranges red roses"), 1, square)
                    self.assertEqual(square.count("garland of paper hearts"), 1, square)

                    # The finding: PURGE ROSALIND, then a new mobile takes
                    # her freed CHAR_DATA. It is not the vendor.
                    staff.sync("purge rosalind")
                    staff.must(f"load mob {SPARRING_GUARD}", "You create a sparring guard")
                    self.assertIsNone(fair(staff)["vendor"], "the guard is not the vendor")
                    staff.must("holidays refresh", "up to date")
                    square = plain(staff.sync("look"))
                    self.assertIn("Rosalind arranges red roses", square, "the vendor came back")
                    self.assertIn("sparring guard", square)
                    found = fair(staff)
                    self.assertEqual(found["vendor"], "Rosalind the flower seller")
                    self.assertEqual(found["mob"], "29801")

                    # Active to active: the next holiday takes down only its
                    # own fair -- the guard stays.
                    square = set_date(date_file, staff, STPATRICK)
                    self.assertNotIn("Rosalind", square)
                    self.assertNotIn("garland of paper hearts", square)
                    self.assertIn("Finnegan the tinker sits", square)
                    self.assertIn("A rainbow painted on canvas", square)
                    self.assertIn("sparring guard", square)
                    self.assertIn("St. Patrick's Day", staff.sync("holidays"))

                    # Active to none.
                    square = set_date(date_file, staff, NOTHING)
                    self.assertNotIn("Finnegan", square)
                    self.assertNotIn("rainbow", square)
                    self.assertIn("sparring guard", square)
                    self.assertIn("No holiday is being celebrated", staff.sync("holidays"))
                    self.assertEqual(fair(staff)["vendor"], None)
                    self.assertEqual(fair(staff)["decor"], "none")

                    # None to active, without a reboot.
                    square = set_date(date_file, staff, MIDSUMMER)
                    self.assertIn("great midsummer bonfire", square)
                    self.assertIn("Keeper Ashby tends", square)
                    self.assertIn("sparring guard", square)

                    # A date that is not a date is said, and the clock is used.
                    date_file.write_text("2027-02-30\n", encoding="ascii")
                    status = plain(staff.sync("holidays"))
                    self.assertIn("from the host's clock, local time", status)
                    self.assertIn("seasonal areas loaded at boot: the ordinary ones", status)
                self.assertIn("holiday: test date '2027-02-30' is not a real YYYY-MM-DD",
                              mud.server_output())


# ------------------------------------------------------------- the event boss

@unittest.skipIf(SKIP is not None, SKIP or "")
class EventBossLifecycleLiveTests(unittest.TestCase):
    def test_boss_identity_removal_defeat_and_room_messages(self) -> None:
        with LiveMud(fixtures=True) as mud:
            make(mud, "Zholstaff", Levl=70, Room=SQUARE)
            make(mud, "Zholwatcher", Levl=20, Room=SQUARE)
            make(mud, "Zholherald", Levl=20, Room=TEMPLE)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as watcher, \
                    mud.connect(timeout=120) as herald:
                login(staff, "Zholstaff", PW)
                login(watcher, "Zholwatcher", PW)
                login(herald, "Zholherald", PW)
                for client in (staff, watcher, herald):
                    client.sync("scroll 0")
                self.assertIn("only hear", watcher.sync("quiet"), "shouts off")

                # Arrival: shouted to the world, and seen in the square by
                # somebody who hears no shouts.
                mark, herald_mark = len(watcher.transcript), len(herald.transcript)
                staff.must("summonevent horseman", "Event boss spawned: the Headless Horseman")
                watcher.sync("look")
                seen = plain(watcher.transcript[mark:])
                self.assertIn("arrives with a thunderous crash", seen)
                self.assertNotIn("[Event]", seen)
                herald.sync("look")
                self.assertIn("[Event] A CRACK of thunder", plain(herald.transcript[herald_mark:]))

                # Forced removal is not a defeat -- not now, not at the tick.
                purged_at = time.monotonic()
                herald_mark = len(herald.transcript)
                staff.sync("purge horseman")
                self.assertIn("Event boss : none", plain(staff.sync("summonevent status")))

                # A new mobile in the boss's freed CHAR_DATA is not the boss.
                staff.must(f"load mob {SPARRING_GUARD}", "You create a sparring guard")
                status = plain(staff.sync("summonevent status"))
                self.assertIn("Event boss : none", status)
                self.assertIn("Areas loaded : the ordinary ones", status)
                staff.must("summonevent horseman", "Event boss spawned: the Headless Horseman")

                # Departure is seen in the room, and takes only the boss.
                mark = len(watcher.transcript)
                staff.must("summonevent", "Despawning the event boss")
                watcher.sync("look")
                seen = plain(watcher.transcript[mark:])
                self.assertIn("lets out a final roar and fades from the world", seen)
                square = plain(staff.sync("look"))
                self.assertIn("sparring guard", square)
                self.assertNotIn("Headless Horseman", square)

                # Wait out a tick since the purge: still no defeat.
                time.sleep(max(0.0, 70 - (time.monotonic() - purged_at)))
                herald.sync("look")
                self.assertNotIn("defeated", plain(herald.transcript[herald_mark:]))

                # A real death is announced as a defeat.
                staff.must("summonevent horseman", "Event boss spawned")
                herald_mark = len(herald.transcript)
                staff.sync("slay horseman")
                herald.sync("look")
                self.assertIn("has been defeated! Dresden breathes again",
                              plain(herald.transcript[herald_mark:]))
                self.assertIn("Event boss : none", plain(staff.sync("summonevent status")))
            self.assertIn("left the world without being slain", mud.server_output())


# ------------------------------------------------------------------ the eggs

def drop_eggs(staff, count: int) -> None:
    """Load and drop `count` painted eggs where staff stands."""
    while count > 0:
        batch = min(count, 10)
        staff.sync(";".join([f"load obj {EGG}"] * batch + ["drop all.egg"]))
        count -= batch


@unittest.skipIf(SKIP is not None, SKIP or "")
class EggHuntLiveTests(unittest.TestCase):
    def test_remote_eggs_do_not_starve_the_hunt_and_pickup_replenishes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            date_file = Path(tmp) / "today"
            date_file.write_text(NOBLEGARDEN + "\n", encoding="ascii")
            env = {"TOC_SEASON": None, "TOC_DATE_FILE": str(date_file)}
            with LiveMud(extra_env=env, fixtures=True) as mud:
                make(mud, "Zholstaff", Levl=70, Room=FLOOR)
                with mud.connect(timeout=120) as staff:
                    login(staff, "Zholstaff", PW)
                    staff.sync("scroll 0")
                    before = fair(staff)
                    drop_eggs(staff, 20)          # far from Dresden
                    after = fair(staff)
                    self.assertEqual(after["anywhere"], before["anywhere"] + 20)
                    self.assertEqual(after["local"], before["local"])

                    # Twenty eggs elsewhere do not stop the hunt: each
                    # refresh hides one more in Dresden, up to twelve.
                    staff.sync(";".join(["holidays refresh"] * 14))
                    self.assertEqual(fair(staff)["local"], 12)
                    staff.sync(";".join(["holidays refresh"] * 3))
                    self.assertEqual(fair(staff)["local"], 12, "never past the ceiling")

                    # Picking one up makes room for another.
                    rows = re.findall(r"\[\s*\d+\]\s+a brightly painted egg \[29823\] in room \[\s*(\d+)\]",
                                      plain(staff.sync(f"owhere {EGG}")))
                    dresden = [int(r) for r in rows if int(r) != FLOOR]
                    self.assertTrue(dresden, rows)
                    staff.must(f"goto {dresden[0]}", "")
                    staff.must("get egg", "You get a brightly painted egg")
                    self.assertEqual(fair(staff)["local"], 11)
                    staff.must("holidays refresh", "up to date")
                    self.assertEqual(fair(staff)["local"], 12, "the hunt goes on")

    def test_every_egg_on_the_ground_is_gathered_when_it_ends(self) -> None:
        nook = FLOOR + 1
        with tempfile.TemporaryDirectory() as tmp:
            date_file = Path(tmp) / "today"
            date_file.write_text(NOTHING + "\n", encoding="ascii")
            env = {"TOC_SEASON": None, "TOC_DATE_FILE": str(date_file)}
            with LiveMud(extra_env=env, fixtures=True) as mud:
                make(mud, "Zholstaff", Levl=70, Room=FLOOR)
                make(mud, "Zholkeeper", Levl=20, Room=TEMPLE)
                with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as keeper:
                    login(staff, "Zholstaff", PW)
                    login(keeper, "Zholkeeper", PW)
                    staff.sync("scroll 0")
                    keeper.sync("scroll 0")
                    # One egg in a pit in another room, one carried by a
                    # player: neither lies on the ground, and both stay.
                    staff.must(f"goto {nook}", "")
                    staff.must(f"load obj {PIT}", "You create")
                    staff.must(f"load obj {EGG}", "You create")
                    staff.must("put egg pit", "You put")
                    staff.must(f"goto {TEMPLE}", "")
                    staff.must(f"load obj {EGG}", "You create")
                    staff.must("give egg zholkeeper", "You give")
                    staff.must(f"goto {FLOOR}", "")
                    for target in (1, 96, 97, 120):
                        with self.subTest(eggs=target):
                            # Noblegarden starts: the hunt hides its first egg.
                            set_date(date_file, staff, NOBLEGARDEN)
                            drop_eggs(staff, max(0, target - fair(staff)["anywhere"]))
                            ground = fair(staff)["anywhere"]
                            self.assertGreaterEqual(ground, target)
                            # It ends: every egg on the ground goes.
                            set_date(date_file, staff, NOTHING)
                            self.assertEqual(fair(staff)["anywhere"], 0,
                                             f"{ground} on the ground, all gathered")
                            staff.must("holidays refresh", "up to date")
                            self.assertEqual(fair(staff)["anywhere"], 0, "nothing left to gather")
                    self.assertIn("brightly painted egg", plain(keeper.sync("inventory")))
                    staff.must(f"goto {nook}", "")
                    self.assertIn("brightly painted egg", plain(staff.sync("look in pit")))
                    self.assertNotIn("brightly painted egg", plain(staff.sync("look")).split("pit")[0])

if __name__ == "__main__":
    unittest.main()

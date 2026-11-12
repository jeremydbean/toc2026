"""A prisoner's pet and mount at release, and SHIFT across a sentence
(owner's review, 2026-11-12; src/jail.c, src/magic2.c).

1. A release moved the prisoner from the cell to the Temple and left the
   pet standing beside them in the cell. save_char_obj writes a pet only
   from its owner's room, so the next save dropped it and a quit lost it
   for good -- after a staff release and after a term ran out alike. A
   horse the prisoner had mounted again in the cell (RIDE allows their
   own) stayed "ridden" in the cell under a rider "mounted" in the
   Temple. jail_release_move now takes the pet with them, a mount under
   its rider, as TRANSFER does.

2. SHIFT asked only the rooms' flags, so in a cell without them a free
   psionic shifting a prisoner paid the mana, was stunned and was told
   the rift had opened while char_to_room kept the prisoner in the cell.
   A sentence on either side is refused now, before any of it.

Both worlds use the synthetic cell -- room 3 with exits and no flags --
so the sentence, never the room, is what is being asked. A ridden mount
wears its saddle, and save_char_obj never writes a pet that carries
anything (the comment in comm.c: "A mount is never saved"), here or
anywhere else; the mount test therefore holds the rider and the horse
together through SAVE, and checks that a reconnect leaves nobody riding
a horse that is not there.

Synthetic Z characters in throwaway worlds only.
"""
from __future__ import annotations

import re
import time
import unittest

from live_mud import LiveMud, login, patch_player_file, room_of, skip_reason
from test_jail_confinement import CELL, JAILED, PW, TEMPLE, give_skill, make
from test_jail_paths import HORSE, SADDLE, ride, synthetic_cell

SKIP = skip_reason()
PONY = 2436               # dresden.are: the pet shop's pony
MANA = "900 900 9000 9000 900 900"


def plant_pet(mud: LiveMud, owner: str, keyword: str) -> None:
    """A #PET record of the pet shop's pony, named so STAT finds it alone."""
    path = mud.player_dir / owner
    text = path.read_text(encoding="latin-1")
    pet = ("#PET\nVnum %d\nName %s pony~\nSex  0\nLevl 1\n"
           "HMV  20 20 100 100 100 100\nEnd\n\n" % (PONY, keyword))
    path.write_text(text.replace("#END", pet + "#END", 1), encoding="latin-1",
                    newline="")


def saved_pet(mud: LiveMud, owner: str) -> str | None:
    text = (mud.player_dir / owner).read_text(encoding="latin-1")
    match = re.search(r"(?ms)^#PET\n.*?^End$", text)
    return match.group(0) if match else None


def quit_client(client) -> None:
    client.send("quit")
    assert client.wait_closed()


def stat_line(staff, name: str, pattern: str) -> re.Match:
    reply = staff.must("stat char %s" % name, "Room:")
    match = re.search(pattern, reply)
    assert match, reply
    return match


@unittest.skipIf(SKIP is not None, SKIP or "")
class ReleaseCompanionTests(unittest.TestCase):
    def test_a_pet_and_a_mount_leave_the_cell_with_their_owner(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zwarden", 70)
            make(mud, "Zpetkeep", 20)
            make(mud, "Zserved", 20)
            make(mud, "Zrider", 50)
            give_skill(mud, "Zrider", "ride", 100)
            plant_pet(mud, "Zpetkeep", "zkeeppony")
            plant_pet(mud, "Zserved", "zservedpony")
            synthetic_cell(mud)

            with mud.connect(timeout=120) as warden:
                login(warden, "Zwarden", PW)
                warden.sync("scroll 0")

                # --- (a) Released by staff. ---
                with mud.connect(timeout=120) as keeper:
                    login(keeper, "Zpetkeep", PW)
                    keeper.sync("scroll 0")
                    self.assertEqual(TEMPLE, room_of(warden, "zkeeppony"))
                    warden.must("jail zpetkeep 7", *JAILED)
                    self.assertEqual(CELL, room_of(warden, "Zpetkeep"))
                    self.assertEqual(CELL, room_of(warden, "zkeeppony"),
                                     "the pet is led in with them")
                    warden.must("jail zpetkeep release", "released from jail")
                    self.assertEqual(TEMPLE, room_of(warden, "Zpetkeep"))
                    self.assertEqual(TEMPLE, room_of(warden, "zkeeppony"),
                                     "the pet was left in the cell")
                    keeper.must("save", "Saving", "saved", "Ok")
                    self.assertIsNotNone(saved_pet(mud, "Zpetkeep"),
                                         "the save after the release dropped the pet")
                    quit_client(keeper)
                self.assertIn("zkeeppony", saved_pet(mud, "Zpetkeep") or "")
                with mud.connect(timeout=120) as keeper:
                    login(keeper, "Zpetkeep", PW)
                    self.assertEqual(TEMPLE, room_of(warden, "Zpetkeep"))
                    self.assertEqual(TEMPLE, room_of(warden, "zkeeppony"))
                    quit_client(keeper)

                # --- (b) A term that runs out online, nothing typed. ---
                self.assertIn("(offline; saved)", warden.sync("jail zserved 1d"))
                patch_player_file(mud, "Zserved", Jw_Timer=int(time.time()) + 15)
                with mud.connect(timeout=120) as served:
                    login(served, "Zserved", PW)
                    self.assertEqual(CELL, room_of(warden, "Zserved"))
                    self.assertEqual(CELL, room_of(warden, "zservedpony"))
                    served.expect("Your sentence has been served", timeout=40)
                    self.assertEqual(TEMPLE, room_of(warden, "Zserved"))
                    self.assertEqual(TEMPLE, room_of(warden, "zservedpony"),
                                     "the pet was left in the cell")
                    quit_client(served)
                self.assertIn("is not jailed", warden.sync("jail zserved status"))
                self.assertIn("zservedpony", saved_pet(mud, "Zserved") or "",
                              "the quit after the expiry dropped the pet")
                with mud.connect(timeout=120) as served:
                    login(served, "Zserved", PW)
                    self.assertEqual(TEMPLE, room_of(warden, "zservedpony"))
                    quit_client(served)

                # A term that ran out while they were away: the pet comes in
                # at the Temple beside them.
                self.assertIn("(offline; saved)", warden.sync("jail zserved 1d"))
                patch_player_file(mud, "Zserved", Jw_Timer=int(time.time()) - 60)
                with mud.connect(timeout=120) as served:
                    login(served, "Zserved", PW)
                    self.assertIn("Your sentence has been served", served.transcript)
                    self.assertEqual(TEMPLE, room_of(warden, "Zserved"))
                    self.assertEqual(TEMPLE, room_of(warden, "zservedpony"))
                    quit_client(served)
                self.assertIn("zservedpony", saved_pet(mud, "Zserved") or "")

                # --- (c) Mounted again in the cell, then released. ---
                with mud.connect(timeout=120) as rider:
                    login(rider, "Zrider", PW)
                    rider.sync("scroll 0")
                    warden.must("jail zrider 7", *JAILED)
                    warden.sync("goto %d" % CELL)
                    warden.must("load mob %d" % HORSE, "You create")
                    warden.must("load obj %d" % SADDLE, "You create")
                    warden.must("give saddle zrider", "You give")
                    ride(rider)
                    self.assertIn("serving a jail sentence", rider.sync("north"))
                    warden.sync("goto %d" % TEMPLE)
                    # The warden stands in the Temple, so STAT finds the
                    # horse there first if it is there at all.
                    self.assertNotEqual(TEMPLE, room_of(warden, "horse"))
                    warden.must("jail zrider release", "released from jail")
                    self.assertEqual(TEMPLE, room_of(warden, "Zrider"))
                    self.assertEqual(TEMPLE, room_of(warden, "horse"),
                                     "the horse was left in the cell under nobody")
                    self.assertIn("mounted on a steed", rider.sync("score"))
                    rider.must("save", "Saving", "saved", "Ok")
                    self.assertIn("mounted on a steed", rider.sync("score"))
                    self.assertEqual(TEMPLE, room_of(warden, "horse"))
                    # Down and up again: the horse is theirs, under them.
                    rider.must("dismount", "You dismount")
                    self.assertIn("horse", warden.sync("look").lower())
                    ride(rider)
                    self.assertIn("riding on the back of", warden.sync("look"))
                    quit_client(rider)
                # A saddled mount is never written (it carries the saddle),
                # so the reconnect must not leave them riding nothing.
                with mud.connect(timeout=120) as rider:
                    login(rider, "Zrider", PW)
                    self.assertEqual(TEMPLE, room_of(warden, "Zrider"))
                    self.assertNotIn("mounted on a steed", rider.sync("score"))
                    self.assertIn("aren't riding", rider.sync("dismount"))
                    quit_client(rider)


@unittest.skipIf(SKIP is not None, SKIP or "")
class ShiftTests(unittest.TestCase):
    def test_shift_refuses_a_sentence_on_either_side_before_any_cost(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zwarden", 70)
            make(mud, "Zpsion", 50, HpManaMove=MANA)
            make(mud, "Ztarget", 20)
            give_skill(mud, "Zpsion", "shift", 100)
            synthetic_cell(mud)

            with mud.connect(timeout=120) as warden, \
                 mud.connect(timeout=120) as psion, \
                 mud.connect(timeout=120) as target:
                login(warden, "Zwarden", PW)
                login(psion, "Zpsion", PW)
                login(target, "Ztarget", PW)
                for client in (warden, psion, target):
                    client.sync("scroll 0")
                target.must("nosummon", "no longer immune")
                psion.must("nosummon", "no longer immune")

                def mana(name: str) -> int:
                    return int(stat_line(warden, name, r"Mana: (-?\d+)/").group(1))

                def position(name: str) -> int:
                    return int(stat_line(warden, name, r"Position: (\d+)").group(1))

                # A free psionic, a prisoner in a cell with a door.
                warden.must("jail ztarget 7", *JAILED)
                self.assertEqual(CELL, room_of(warden, "Ztarget"))
                before = mana("Zpsion")
                said = psion.sync("shift ztarget")
                self.assertIn("serving a jail sentence", said)
                self.assertNotIn("rift", said)
                self.assertEqual(before, mana("Zpsion"), "mana spent on a refusal")
                self.assertEqual(8, position("Zpsion"), "stunned by a refusal")
                self.assertEqual(CELL, room_of(warden, "Ztarget"))
                self.assertNotIn("rift", target.drain(0.5))

                # A prisoner shifting a free target to the cell.
                warden.must("jail ztarget release", "released from jail")
                self.assertEqual(TEMPLE, room_of(warden, "Ztarget"))
                warden.must("jail zpsion 7", *JAILED)
                self.assertEqual(CELL, room_of(warden, "Zpsion"))
                before = mana("Zpsion")
                said = psion.sync("shift ztarget")
                self.assertIn("You are serving a jail sentence", said)
                self.assertEqual(before, mana("Zpsion"))
                self.assertEqual(8, position("Zpsion"))
                self.assertEqual(TEMPLE, room_of(warden, "Ztarget"))
                self.assertEqual(CELL, room_of(warden, "Zpsion"))

                # Control: released, the same shift really pulls them.
                warden.must("jail zpsion release", "released from jail")
                warden.must("transfer ztarget 2401", "Ok", "arrives", "transfer")
                self.assertIn("spatial rift", psion.sync("shift ztarget"))
                self.assertEqual(TEMPLE, room_of(warden, "Ztarget"))


if __name__ == "__main__":
    unittest.main()

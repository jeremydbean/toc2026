"""A saddled mount survives QUIT (2026-11-12; src/save.c).

RIDE puts the rider's saddle on the horse (WEAR_BODY) and makes the horse
their pet, and save_char_obj wrote a pet only when it carried nothing --
so a ridden mount was never written, and the quit's extraction took the
horse and the saddle with it. comm.c said so: "A mount is never saved".

fwrite_pet now writes a pet whose only possession is its own saddle, worn,
as `Saddle <vnum> <level>` in the #PET record; fread_pet makes the saddle
again and puts it on. The rider comes back dismounted, the horse saddled
beside them, and RIDE -- which lets anybody mount their own pet, and needs
no saddle in the pack when the horse wears one -- puts them back on it. A
pet carrying anything else is still not written, as before (a pet's carry
limit is 0, so only RIDE ever puts anything on one).

Synthetic Z characters in a throwaway world only.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, login, room_of, skip_reason
from test_jail_companions import quit_client, saved_pet
from test_jail_confinement import PW, TEMPLE, give_skill, make
from test_jail_paths import HORSE, SADDLE, ride

SKIP = skip_reason()


def saddles_in_world(staff) -> int:
    reply = staff.sync("owhere saddle")
    return len(re.findall(r"\[\s*%d\]" % SADDLE, reply))


def player_objects(mud: LiveMud, name: str) -> list[int]:
    """The vnums of the #O records before #PET/#STASH: what the player holds."""
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    own = re.split(r"(?m)^#(?:PET|STASH)$", text, maxsplit=1)[0]
    return [int(v) for v in re.findall(r"(?m)^Vnum (\d+)$", own)]


@unittest.skipIf(SKIP is not None, SKIP or "")
class MountPersistenceTests(unittest.TestCase):
    def test_a_saddled_mount_comes_back_after_quit(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zstable", 70)
            make(mud, "Zhorseman", 50)
            give_skill(mud, "Zhorseman", "ride", 100)

            with mud.connect(timeout=120) as staff:
                login(staff, "Zstable", PW)
                staff.sync("scroll 0")
                with mud.connect(timeout=120) as rider:
                    login(rider, "Zhorseman", PW)
                    rider.sync("scroll 0")
                    staff.must("load mob %d" % HORSE, "You create")
                    staff.must("load obj %d" % SADDLE, "You create")
                    staff.must("give saddle zhorseman", "You give")
                    ride(rider)
                    self.assertNotIn("saddle", rider.sync("inventory").lower(),
                                     "RIDE put the saddle on the horse")
                    saddles = saddles_in_world(staff)
                    self.assertGreaterEqual(saddles, 1)
                    rider.must("save", "Saving", "saved", "Ok")
                    pet = saved_pet(mud, "Zhorseman")
                    self.assertIsNotNone(pet, "a saddled mount was not written")
                    self.assertRegex(pet, r"(?m)^Saddle %d \d+$" % SADDLE)
                    self.assertNotIn(SADDLE, player_objects(mud, "Zhorseman"),
                                     "the saddle written twice: the rider holds it too")
                    quit_client(rider)
                self.assertEqual(saddles - 1, saddles_in_world(staff),
                                 "the quit left a saddle in the world")

                for round_trip in (1, 2):
                    with mud.connect(timeout=120) as rider:
                        login(rider, "Zhorseman", PW)
                        rider.sync("scroll 0")
                        self.assertEqual(TEMPLE, room_of(staff, "horse"),
                                         "round %d: the horse is not beside them" % round_trip)
                        self.assertEqual(saddles, saddles_in_world(staff),
                                         "round %d: one saddle, on the horse" % round_trip)
                        self.assertIn("saddle", staff.sync("look horse").lower())
                        self.assertNotIn("mounted on a steed", rider.sync("score"),
                                         "nobody comes back riding")
                        self.assertNotIn("saddle", rider.sync("inventory").lower())
                        # No saddle in the pack: the horse's own is what lets
                        # RIDE through, and the horse is theirs.
                        ride(rider)
                        self.assertIn("riding on the back of", staff.sync("look"))
                        self.assertIn("mounted on a steed", rider.sync("score"))
                        quit_client(rider)

                # Dismounted, the horse is nobody's (DISMOUNT lets it go):
                # it stays where it stands, saddled, and is not written, so
                # there is never a second one.
                with mud.connect(timeout=120) as rider:
                    login(rider, "Zhorseman", PW)
                    rider.sync("scroll 0")
                    ride(rider)
                    rider.must("dismount", "You dismount")
                    rider.must("save", "Saving", "saved", "Ok")
                    self.assertIsNone(saved_pet(mud, "Zhorseman"))
                    quit_client(rider)
                self.assertEqual(TEMPLE, room_of(staff, "horse"))
                self.assertEqual(saddles, saddles_in_world(staff))
                with mud.connect(timeout=120) as rider:
                    login(rider, "Zhorseman", PW)
                    self.assertNotIn("mounted on a steed", rider.sync("score"))
                    self.assertIn("aren't riding", rider.sync("dismount"))
                    quit_client(rider)
                self.assertEqual(saddles, saddles_in_world(staff))


PONY = 2436      # dresden.are: the pet shop's pony


def pet_record(*saddles: str) -> str:
    return ("#PET\nVnum %d\nName zfilepony pony~\nSex  0\nLevl 1\n"
            "HMV  20 20 100 100 100 100\n%sEnd\n\n"
            % (PONY, "".join("Saddle %s\n" % s for s in saddles)))


def add_pet(mud: LiveMud, name: str, record: str) -> bytes:
    path = mud.player_dir / name
    text = path.read_text(encoding="latin-1")
    path.write_text(text.replace("#END", record + "#END", 1), encoding="latin-1",
                    newline="")
    return path.read_bytes()


def try_name(mud: LiveMud, name: str) -> str:
    """A refused file closes at the name; one that loads asks the password."""
    with mud.connect(timeout=60) as client:
        client.expect("by what name", "name:")
        client.send(name)
        said = client.expect("could not be read", "assword")
        if said != "could not be read":
            return "loaded"
        client.wait_closed()
        return "refused"


@unittest.skipIf(SKIP is not None, SKIP or "")
class SaddleRecordTests(unittest.TestCase):
    """The Saddle key is read as the loader reads everything (AGENTS: a
    malformed value refuses the character, never the game)."""

    def test_saddle_keys_malformed_doubled_and_gone(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zsaddler", 70)
            for name in ("Zsadtwo", "Zsadbad", "Zsadnone", "Zsadbread", "Zsadgood"):
                make(mud, name, 20)
            refused = {
                "Zsadtwo": add_pet(mud, "Zsadtwo", pet_record("%d 2" % SADDLE, "%d 2" % SADDLE)),
                "Zsadbad": add_pet(mud, "Zsadbad", pet_record("%d zz" % SADDLE)),
            }
            add_pet(mud, "Zsadnone", pet_record("999999 5"))     # no such object
            add_pet(mud, "Zsadbread", pet_record("3011 5"))      # an object, not a saddle
            add_pet(mud, "Zsadgood", pet_record("%d 2" % SADDLE))

            for name, before in refused.items():
                self.assertEqual("refused", try_name(mud, name), name)
                self.assertEqual(before, (mud.player_dir / name).read_bytes(),
                                 "%s: a refused file was written over" % name)

            with mud.connect(timeout=120) as staff:
                login(staff, "Zsaddler", PW)
                staff.sync("scroll 0")
                before = saddles_in_world(staff)
                for name, saddled in (("Zsadnone", False), ("Zsadbread", False),
                                      ("Zsadgood", True)):
                    with mud.connect(timeout=120) as player:
                        login(player, name, PW)
                        player.sync("scroll 0")
                        self.assertEqual(TEMPLE, room_of(staff, "zfilepony"), name)
                        look = staff.sync("look zfilepony").lower()
                        self.assertEqual(saddled, "saddle" in look, "%s: %s" % (name, look))
                        self.assertEqual(before + (1 if saddled else 0),
                                         saddles_in_world(staff), name)
                        self.assertNotIn("bread", player.sync("inventory").lower())
                        quit_client(player)
                self.assertEqual(before, saddles_in_world(staff))


if __name__ == "__main__":
    unittest.main()

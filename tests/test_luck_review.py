"""Luck, as the review of 2026-11-20 asked it to behave.

- A lucky AQUEST GAMBLE is a second toss, not a win: a loss, when luck
  holds, is tossed once more, and that toss wins or loses as the first
  did. The offer shows those odds (57.5% at three points).
  TOC_GAMBLE_TOSSES plays the coin in a fixed order.
- A clover adds a point and never shortens luck held longer: a creator's
  hundred hours stay a hundred; a shorter time is raised to thirty. Points
  stop at three, luck wears off when its hours run out, it is saved, and
  FATE ... LUCK OFF ends it.
- A charmed pet's kill rolls its master's pot of gold, as its experience
  and clover_luck() are its master's; an unlucky kill spills none.

TOC_LUCK_ROLLS=always makes every luck roll land while any is held.
Synthetic characters in a throwaway world; the creator is a synthetic
Killuminati, as test_creator_rank's is.
"""
from __future__ import annotations

import re
import unittest

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
PW = "Zluckpass1"
QUESTMASTER = 2497
QUIET_ROOM = 32703          # fixture: not safe, nothing walks in
CLOVER = 29822
SPARRING_GUARD = 32700
RABBIT = 3709


def make(mud, name, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        assert client.wait_closed(), name
    patch_player_file(mud, name, **fields)


def give_clover(god, hero_name: str) -> None:
    god.must("load obj %d" % CLOVER, "")
    god.must("give clover %s" % hero_name, "You give")


@unittest.skipIf(SKIP is not None, SKIP or "")
class LuckReviewTests(unittest.TestCase):
    def test_a_lucky_gamble_is_a_second_toss(self) -> None:
        # Tosses in order: loss then win (a lucky save that wins), loss then
        # loss (a lucky save that loses), and a loss with no luck at all.
        env = {"TOC_LUCK_ROLLS": "always", "TOC_GAMBLE_TOSSES": "LWLLL"}
        with LiveMud(extra_env=env) as mud:
            make(mud, "Killuminati", Levl=70, Room=4207)
            make(mud, "Zgambler", Levl=30, Room=QUESTMASTER, QuestGmbl=10)
            with mud.connect(timeout=120) as god:
                login(god, "Killuminati", PW)
                god.must("fate zgambler luck 50 3", "lucky: 3 points")
                with mud.connect(timeout=120) as hero:
                    login(hero, "Zgambler", PW)
                    offer = hero.sync("aquest gamble")
                    self.assertIn("(57.5% chance, with your luck)", offer, offer)
                    self.assertIn("(42.5% chance)", offer, offer)
                    said = hero.sync("aquest gamble yes")
                    self.assertIn("Luck is with you: the questmaster's coin goes again!", said)
                    self.assertIn("You WIN 20 quest points", said, said)
                    hero.send("quit")
                    self.assertTrue(hero.wait_closed())

                patch_player_file(mud, "Zgambler", QuestGmbl=10)
                with mud.connect(timeout=120) as hero:
                    login(hero, "Zgambler", PW)
                    said = hero.sync("aquest gamble yes")
                    self.assertIn("Luck is with you: the questmaster's coin goes again!", said)
                    self.assertIn("The dice BETRAY you! Your 10 quest points are lost.", said, said)
                    hero.send("quit")
                    self.assertTrue(hero.wait_closed())

                god.must("fate zgambler luck off", "luck is ended")
                patch_player_file(mud, "Zgambler", QuestGmbl=10)
                with mud.connect(timeout=120) as hero:
                    login(hero, "Zgambler", PW)
                    offer = hero.sync("aquest gamble")
                    self.assertIn("(50.0% chance)", offer, offer)
                    said = hero.sync("aquest gamble yes")
                    self.assertNotIn("Luck is with you", said)
                    self.assertIn("BETRAY", said, said)

    def test_a_clover_never_shortens_luck_and_luck_runs_out(self) -> None:
        with LiveMud() as mud:
            make(mud, "Killuminati", Levl=70, Room=4207)
            make(mud, "Zclover", Levl=30, Room=4207)
            with mud.connect(timeout=120) as god:
                login(god, "Killuminati", PW)
                with mud.connect(timeout=120) as hero:
                    login(hero, "Zclover", PW)
                    # A creator's hundred hours at one point; a clover adds a
                    # point and leaves the hundred.
                    god.must("fate zclover luck 100 1", "lucky: 1 point for 100 hours")
                    give_clover(god, "zclover")
                    said = hero.sync("eat clover")
                    self.assertRegex(said, r"You have 2 points of luck \(at most 3\) for the next (99|100) hours")
                    give_clover(god, "zclover")
                    hero.sync("eat clover")
                    give_clover(god, "zclover")
                    hero.sync("eat clover")                       # past the cap
                    self.assertRegex(hero.sync("affects"),
                                     r"3 points of luck \(at most 3\), for (99|100) more hours")
                    hero.send("quit")
                    self.assertTrue(hero.wait_closed())

                text = (mud.player_dir / "Zclover").read_text(encoding="latin-1")
                self.assertRegex(text, r"(?m)^AffD 'luck' ")

                with mud.connect(timeout=120) as hero:
                    login(hero, "Zclover", PW)
                    # Saved and back: the same luck.
                    self.assertRegex(hero.sync("affects"),
                                     r"3 points of luck \(at most 3\), for (9[89]|100) more hours")
                    # A shorter time is raised to a clover's thirty.
                    god.must("fate zclover luck 5 1", "lucky: 1 point for 5 hours")
                    give_clover(god, "zclover")
                    self.assertIn("2 points of luck (at most 3) for the next 30 hours",
                                  hero.sync("eat clover"))
                    god.must("fate zclover luck off", "luck is ended")
                    self.assertNotIn("'luck'", hero.sync("affects"))

                    # One hour runs out within two ticks, and says so.
                    god.must("fate zclover luck 1 1", "lucky: 1 point for 1 hours")
                    hero.expect("Your luck runs out.", timeout=200)
                    self.assertNotIn("'luck'", hero.sync("affects"))

    def test_a_pets_kill_rolls_its_masters_pot_of_gold(self) -> None:
        env = {"TOC_LUCK_ROLLS": "always"}
        with LiveMud(extra_env=env, fixtures=True) as mud:
            make(mud, "Killuminati", Levl=70, Room=4207)
            make(mud, "Zpetmaster", Levl=30, Cla=0, Room=4207,
                 HMV="9000 9000 900 900 100 100", HMVP="9000 900 100")
            with mud.connect(timeout=120) as god, mud.connect(timeout=120) as hero:
                login(god, "Killuminati", PW)
                login(hero, "Zpetmaster", PW)
                for client in (god, hero):
                    client.sync("scroll 0")
                god.must("set skill zpetmaster charm 100", "skill set to 100")
                god.must("goto %d" % QUIET_ROOM, "")
                god.must("load mob %d" % SPARRING_GUARD, "sparring guard")
                god.must("set char sparring level 1", "")
                god.must("transfer zpetmaster %d" % QUIET_ROOM, "")
                hero.sync("look")
                for _ in range(40):
                    god.must("restore zpetmaster", "")
                    god.sync("peace")
                    hero.sync("cast 'charm person' sparring")
                    if "Master: Zpetmaster" in god.sync("stat sparring"):
                        break
                self.assertIn("Master: Zpetmaster", god.sync("stat sparring"))
                god.sync("peace")

                def wait_for(text: str, mark: int) -> str:
                    for _ in range(60):
                        if text in hero.transcript[mark:]:
                            break
                        hero.drain(1.0)
                    hero.drain(1.0)
                    return hero.transcript[mark:]

                def rabbit() -> None:
                    god.must("load mob %d" % RABBIT, "rabbit")
                    god.must("set char rabbit hp 1", "now set to 1")
                    god.sync("restore rabbit")

                # No luck: the pet's kill spills nothing.
                rabbit()
                mark = len(hero.transcript)
                hero.sync("order sparring kill rabbit")
                seen = wait_for("is DEAD", mark)
                self.assertIn("is DEAD", seen, seen[-600:])
                self.assertNotIn("pot of gold", seen)

                # Lucky: the pet's kill spills its master's pot of gold.
                god.must("fate zpetmaster luck 30 3", "lucky: 3 points")
                rabbit()
                mark = len(hero.transcript)
                hero.sync("order sparring kill rabbit")
                seen = wait_for("pot of gold", mark)
                self.assertIn("Luck is with you: a pot of gold tumbles out of the rabbit's things!",
                              seen, seen[-600:])

                # And the master's own kill, lucky, as before.
                rabbit()
                mark = len(hero.transcript)
                god.must("set char zpetmaster hitroll 300", "hitroll set to 300")
                hero.sync("kill rabbit")
                seen = wait_for("pot of gold", mark)
                self.assertIn("pot of gold tumbles out", seen, seen[-600:])


class LuckReviewSourceTests(unittest.TestCase):
    def test_gohma_names_a_command_and_the_silver_arrow_is_ganons(self) -> None:
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        fight = (root / "src" / "fight.c").read_text(encoding="latin-1")
        gohma = fight[fight.index("Only an arrow at the open eye finishes her"):]
        gohma = gohma[:gohma.index("HYRULE_GANON_VNUM")]
        self.assertNotIn("SHOOT $M", gohma)
        self.assertIn("SHOOT GOHMA", gohma)
        self.assertNotIn("OBJ_VNUM_HYRULE_SILVER_ARROW", gohma)
        prose = (root / "data" / "hyrule_mob_prose.json").read_text(encoding="utf-8")
        self.assertNotIn("or the Silver Arrow, to end it", prose)
        area = (root / "area" / "hyrule.are").read_text(encoding="latin-1")
        self.assertIn("wield Hyrule's short bow and SHOOT GOHMA.", area)
        # SHOOT with the Silver Arrow answers only at Ganon.
        self.assertIn("The Silver Arrow can only be shot at Ganon while he is here.", fight)
        self.assertTrue(re.search(r"is_silver_arrow_weapon\(obj\)\s*\)\s*\{", fight))


if __name__ == "__main__":
    unittest.main()

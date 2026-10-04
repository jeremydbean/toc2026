"""An object a generator retires is swapped for its replacement at login.

The Hyrule NES pass took the shops' satchel of bombs (30542) out of the
world, and the next time Alaric logged in the game dropped the four he
carried with a "Fread_obj: bad vnum" line each. retired_objects in
src/save.c maps a retired vnum to what replaced it, and the swapped item
takes the replacement's own stats rather than the saved ones.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason  # noqa: E402
from webadmin.area_parser import AreaParser  # noqa: E402

SKIP = skip_reason()
PASSWORD = "Zretire1"


def retired_table() -> dict[int, int]:
    save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
    table = save.split("} retired_objects[] =", 1)[1].split("};", 1)[0]
    return {int(a): int(b) for a, b in re.findall(r"\{\s*(\d+),\s*(\d+)\s*\}", table)}


class RetiredObjectTableTests(unittest.TestCase):
    def test_every_row_points_from_a_gone_vnum_to_a_live_one(self) -> None:
        parser = AreaParser(ROOT / "area")
        parser.parse_all()
        table = retired_table()
        self.assertIn(30542, table)
        for retired, replacement in table.items():
            self.assertNotIn(retired, parser.objects,
                             f"{retired} still exists, so its row never fires")
            self.assertIn(replacement, parser.objects,
                          f"{retired} would be swapped for a missing {replacement}")


class BoughtItemTests(unittest.TestCase):
    def test_a_bought_copy_is_not_shop_stock(self) -> None:
        """Hyrule's shop prototypes carry ITEM_INVENTORY, every copy sold
        kept it, and make_corpse destroys inventory items: a player who
        died lost everything they had bought, a 250-rupee Blue Ring
        included. do_buy clears it on the copy, and loading clears it
        from what a player already carries."""
        handler = (ROOT / "src" / "handler.c").read_text(encoding="latin-1").replace("\r\n", "\n")
        to_char = handler.split("void obj_to_char( OBJ_DATA *obj, CHAR_DATA *ch )", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("if ( !IS_NPC(ch) )\n\tREMOVE_BIT( obj->extra_flags, ITEM_INVENTORY );", to_char)
        # A bought item does not rot when its owner dies, either.
        obj_c = (ROOT / "src" / "act_obj.c").read_text(encoding="latin-1")
        buy = obj_c.split("obj = create_object( obj->pIndexData, -1 * obj->level );", 1)[1]
        self.assertLess(buy.index("REMOVE_BIT( obj->extra_flags, ITEM_ROT_DEATH );"),
                        buy.index("obj_to_char( obj, ch );"))
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        self.assertIn("if ( ch != NULL && !IS_NPC(ch) )\n\t\t\tREMOVE_BIT( obj->extra_flags, ITEM_INVENTORY );",
                      save.replace("\r\n", "\n"))

    def test_a_players_corpse_stamps_no_decay_timers(self) -> None:
        """Owner's Scroll of Farslay crumbled two days after a death: the
        corpse put a 200-500 tick timer on it and the timer stayed when he
        took it back. Only a mobile's corpse stamps potions, scrolls and
        scuba gear now, and loading clears the old stamp from a player's."""
        fight = (ROOT / "src" / "fight.c").read_text(encoding="latin-1").replace("\r\n", "\n")
        corpse = fight.split("void make_corpse( CHAR_DATA *ch )", 1)[1].split("\n}\n", 1)[0]
        guard = corpse.index("if ( IS_NPC(ch) )\n\t{")
        self.assertLess(guard, corpse.index("obj->timer = (sh_int)(number_range(200,500));"))
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        self.assertIn("|| obj->item_type == ITEM_SCROLL ) )\n\t\t\tobj->timer = 0;",
                      save.replace("\r\n", "\n"))

    def test_an_old_blue_ring_is_raised_to_its_level(self) -> None:
        """30551 was a level 24 ring with no ward; a copy saved then keeps
        its level, so loading raises it with the ward it gained."""
        save = (ROOT / "src" / "save.c").read_text(encoding="latin-1")
        self.assertIn("obj->pIndexData->vnum == OBJ_VNUM_HYRULE_BLUE_RING", save)


@unittest.skipIf(SKIP is not None, SKIP or "")
class RetiredObjectLiveTests(unittest.TestCase):
    def test_a_retired_satchel_comes_back_as_bombs(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zretiree", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zretiree", Room=4207)

            # Two satchels as an old save holds them: level and cost of
            # their own, which must not stick to the bombs.
            path = mud.player_dir / "Zretiree"
            text = path.read_text(encoding="latin-1")
            satchel = ("#O\nVnum 30542\nNest 0\nWear -1\nLev  5\nCost 20\n"
                       "Cond 100\nRepd 0\nEnd\n\n")
            text = text.replace("#END", satchel * 2 + "#END", 1)
            path.write_text(text, encoding="latin-1")

            with mud.connect(timeout=120) as client:
                login(client, "Zretiree", PASSWORD)
                client.drain(0.5)
                mark = len(client.transcript)
                client.send("inventory")
                client.drain(1.5)
                shown = client.transcript[mark:]
                self.assertIn("four bombs", shown, shown)
                self.assertNotIn("satchel", shown.lower(), shown)

            log = mud.root / "log" / "toc.log"
            self.assertTrue(log.is_file(), log)
            written = log.read_text(encoding="latin-1", errors="replace")
            self.assertIn("retired object 30542 swapped for 30695", written)
            self.assertNotIn("bad vnum 30542", written)

    def test_shop_stock_a_player_picks_up_survives_their_death(self) -> None:
        """The take-any caves' red 2nd Potion (30554) carries the shop's
        ITEM_INVENTORY on its prototype, and make_corpse destroys
        inventory items -- so a player who picked one up and died lost
        it. Anything that reaches a player is theirs now."""
        def run(client, command: str, settle: float = 1.5) -> str:
            client.drain(0.4)
            mark = len(client.transcript)
            client.send(command)
            client.drain(settle)
            return client.transcript[mark:]

        with LiveMud() as mud:
            for name, level in (("Zshopper", 20), ("Zshopgod", 70)):
                with mud.connect(timeout=120) as client:
                    create_character(client, name, PASSWORD)
                    client.send("quit")
                    self.assertTrue(client.wait_closed())
                patch_player_file(mud, name, Levl=level, Room=4207)

            with mud.connect(timeout=120) as hero, mud.connect(timeout=120) as god:
                login(hero, "Zshopper", PASSWORD)
                login(god, "Zshopgod", PASSWORD)
                run(god, "load obj 30554")
                run(god, "drop potion")
                self.assertIn("You get", run(hero, "get potion"))
                run(god, "slay zshopper", 2.5)
                inside = run(god, "look in corpse", 2.0)
                self.assertIn("red 2nd Potion", inside, inside)


if __name__ == "__main__":
    unittest.main()

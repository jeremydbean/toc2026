"""JOIN SWITCH: one change of guild in a first life (2026-11-15).

A warrior in the mages' guild, level 8, with a mage guild spell practised
to 60%, asks Melancholy for the warriors' guild: the preview changes
nothing, the confirmed switch takes the mage guild's training back and
returns the practices spent on it, gives the warrior guild's (and Hero's
Grip), keeps everything else as it was, is saved and refused a second time.
Too high a level, a remort and a monk are refused before anything changes.
Synthetic Z characters in a disposable world only.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zguildpass1"
CLERK_ROOM = 2498


def make(mud, name, **fields):
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    patch_player_file(mud, name, **fields)


def skills(mud, name) -> dict[str, int]:
    text = (mud.player_dir / name).read_text(encoding="latin-1")
    return {m.group(2): int(m.group(1)) for m in re.finditer(r"(?m)^Sk (\d+) '([^']+)'$", text)}


def field(mud, name, key) -> str:
    m = re.search(r"(?m)^%s (.+)$" % key, (mud.player_dir / name).read_text(encoding="latin-1"))
    return m.group(1).strip() if m else ""


@unittest.skipIf(SKIP is not None, SKIP or "")
class GuildSwitchTests(unittest.TestCase):
    def test_switch_once_with_everything_returned(self) -> None:
        with LiveMud() as mud:
            make(mud, "Zguildgod", Levl=70, Room=CLERK_ROOM)
            # A warrior in the mages' guild (Gui 0); the login repair gives
            # the mage guild's group.
            make(mud, "Zswitcher", Levl=8, Cla=3, Gui=0, Room=CLERK_ROOM, Prac=4, Trai=2)
            make(mud, "Zswitchold", Levl=16, Cla=3, Gui=0, Room=CLERK_ROOM)
            make(mud, "Zswitchmonk", Levl=8, Cla=4, Room=CLERK_ROOM)
            # A cleric in the warriors' guild who bought bash there.
            make(mud, "Zswitchcler", Levl=9, Cla=1, Gui=3, Room=CLERK_ROOM, Prac=0, Trai=1)
            with mud.connect(timeout=120) as staff, mud.connect(timeout=120) as hero:
                login(staff, "Zguildgod", PW)
                login(hero, "Zswitcher", PW)
                staff.must("set skill zswitcher 'magic missile' 60", "")
                staff.must("set skill zswitcher 'kick' 40", "")
                hero.must("save", "Saving")
                before = skills(mud, "Zswitcher")
                self.assertEqual(before.get("magic missile"), 60, before)
                self.assertNotIn("heroic grip", before)

                said = hero.sync("join switch")
                self.assertIn("JOIN SWITCH <mage|cleric|thief|warrior>", said, said)
                said = hero.sync("join switch warrior")
                self.assertIn("Leaving the mage guild for the warrior guild", said, said)
                m = re.search(r"Returned to you: (\d+) trains? and (\d+) practices?", said)
                self.assertIsNotNone(m, said)
                pracs = int(m.group(2))
                self.assertGreater(pracs, 0, said)
                # The preview changed nothing.
                hero.must("save", "Saving")
                self.assertEqual(skills(mud, "Zswitcher"), before)
                self.assertEqual(field(mud, "Zswitcher", "Gui"), "0")
                self.assertEqual(field(mud, "Zswitcher", "Prac"), "4")

                said = hero.sync("join switch warrior confirm", timeout=30)
                self.assertIn("member of the warrior guild", said, said)
                hero.must("save", "Saving")
                after = skills(mud, "Zswitcher")
                self.assertNotIn("magic missile", after, after)
                self.assertEqual(after.get("kick"), 40, after)          # not the guild's: kept
                self.assertIn("heroic grip", after, after)              # warrior/warrior
                self.assertEqual(field(mud, "Zswitcher", "Gui"), "3")
                self.assertEqual(int(field(mud, "Zswitcher", "Prac")), 4 + pracs)
                self.assertEqual(field(mud, "Zswitcher", "GuildSwitched"), "1")
                self.assertTrue(any(p.name.endswith(".guildswitch")
                                    for p in (mud.player_dir / "versions" / "Zswitcher").iterdir()))

                self.assertIn("once already", hero.sync("join switch cleric"))
                self.assertIn("once already", hero.sync("join switch cleric confirm"))

                # A skill bought from a guild-only trainer: its trains back.
                with mud.connect(timeout=120) as cler:
                    login(cler, "Zswitchcler", PW)
                    staff.must("set skill zswitchcler 'bash' 50", "")
                    said = cler.sync("join switch mage")
                    self.assertIn("bash (skill, 5 trains)", said, said)
                    said = cler.sync("join switch mage confirm", timeout=30)
                    self.assertIn("member of the mage guild", said, said)
                    cler.must("save", "Saving")
                    self.assertNotIn("bash", skills(mud, "Zswitchcler"))
                    self.assertEqual(int(field(mud, "Zswitchcler", "Trai")), 1 + 5)
                    self.assertGreater(int(field(mud, "Zswitchcler", "Prac")), 0)

                with mud.connect(timeout=120) as old, mud.connect(timeout=120) as monk:
                    login(old, "Zswitchold", PW)
                    login(monk, "Zswitchmonk", PW)
                    self.assertIn("level 15 or below", old.sync("join switch cleric confirm"))
                    self.assertEqual(field(mud, "Zswitchold", "Gui"), "0")
                    self.assertIn("level 15 or below", monk.sync("join switch cleric confirm"))


if __name__ == "__main__":
    unittest.main()

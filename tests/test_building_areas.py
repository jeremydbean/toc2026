"""In-game area building: ANEW makes a buildable area that survives a reboot.

Phase 1 of the in-game building subsystem (owner, 2026-10-06). ANEW declares
an area with its own vnum range, writes a stub .are with an #AREADATA header
in area/built/, lists it in built/built.lst (never area.lst, which is code),
and links it live. A room made with GOTO inside the
range belongs to the new area and is editable; RSAVE writes it into the file;
after a reboot the area reloads with its range and the room persists.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

SKIP = skip_reason()
ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "Zbuildpw1"
LO, HI = 21000, 21009
ROOMVNUM = 21001


def run(client, command: str, settle: float = 1.2) -> str:
    client.drain(0.3)
    mark = len(client.transcript)
    client.send(command)
    client.drain(settle)
    return client.transcript[mark:]


class BuiltAreaPersistenceTests(unittest.TestCase):
    """A built area reaches git and survives deploys (phase 7).

    It used to live on the host alone, and a code deploy -- which rebuilds
    area/ from git -- would have dropped it. Now ANEW writes into
    area/built/, which the state sync commits and deploys leave alone."""

    def test_the_state_sync_carries_area_built_to_git(self) -> None:
        sync = (ROOT / "deploy" / "windows-vm" / "toc-state-sync").read_text()
        self.assertIn('BUILT_DIR="area/built"', sync)
        self.assertRegex(sync, r"rsync -a --exclude '\*\.bak' --exclude '\*\.tmp'")
        self.assertIn('git add -f -A "$BUILT_DIR"', sync)
        # Never --delete: a missing built area is a fault, not a retirement.
        block = sync[sync.index('if [ -d "$TOC_ROOT/$BUILT_DIR" ]'):]
        block = block[:block.index("fi")]
        self.assertNotIn("--delete", block)

    def test_a_deploy_never_writes_over_the_live_built_areas(self) -> None:
        deploy = (ROOT / "deploy" / "windows-vm" / "toc-deploy").read_text()
        self.assertIn("--exclude 'area/built/'", deploy)
        self.assertIn('rsync -a --ignore-existing "$BUILD/area/built/"', deploy)

    def test_built_areas_are_ignored_by_git_ci_and_the_auto_deployer(self) -> None:
        self.assertIn("area/built/", (ROOT / ".gitignore").read_text())
        self.assertIn("'area/built/**'",
                      (ROOT / ".github" / "workflows" / "validate.yml").read_text())
        self.assertIn("':(exclude)area/built'",
                      (ROOT / "deploy" / "windows-vm" / "toc-auto-deploy").read_text())

    def test_the_game_loads_the_built_list_after_area_lst(self) -> None:
        db = (ROOT / "src" / "db.c").read_text(encoding="latin-1")
        boot = db[db.index("fpList = fopen( AREA_LIST,"):]
        self.assertLess(boot.index("fclose( fpList );"),
                        boot.index("fopen( BUILT_AREA_LIST"))


@unittest.skipIf(SKIP is not None, SKIP or "")
class AreaBuildingTests(unittest.TestCase):
    def test_anew_room_persists_across_reboot(self) -> None:
        with LiveMud() as mud:
            with mud.connect(timeout=120) as client:
                create_character(client, "Zbuilder", PASSWORD)
                client.send("quit")
                self.assertTrue(client.wait_closed())
            patch_player_file(mud, "Zbuilder", Levl=70, Room=4207)

            with mud.connect(timeout=120) as imm:
                login(imm, "Zbuilder", PASSWORD)
                run(imm, "scroll 0")

                made = run(imm, f"anew {LO} {HI} Zed Mossy Hollow")
                self.assertIn("Created area", made, made)

                # A busy or overlapping range is refused.
                self.assertIn("overlap", run(imm, f"anew {LO} {HI} Zed Again").lower())

                stat = run(imm, "astat Zed Mossy Hollow")
                self.assertIn(f"{LO}-{HI}", stat, stat)
                self.assertIn("Buildable: yes", stat, stat)

                self.assertIn(f"{LO}-{HI}", run(imm, "alist"))

                # GOTO into the range makes a room that belongs to the area.
                run(imm, f"goto {ROOMVNUM}", 1.5)
                run(imm, f"set room {ROOMVNUM} name A Mossy Hollow", 1.5)
                here = run(imm, "look", 1.5)
                self.assertIn("Mossy Hollow", here, here)

                # An ANEW area saves whole, rooms and all (phase 2).
                saved = run(imm, "rsave confirm", 2.0)
                self.assertIn("saved zed mossy hollow: 1 room", saved.lower(), saved)

                imm.send("quit")
                self.assertTrue(imm.wait_closed())

            # The stub file is in area/built/ and listed in the built list;
            # area.lst, which is code, is untouched.
            area_dir = mud.root / "area"
            files = [p.name for p in (area_dir / "built").glob("*.are")
                     if "mossy" in p.name.lower()]
            self.assertTrue(files, "no .are file written in area/built/")
            self.assertIn(f"built/{files[0]}",
                          (area_dir / "built" / "built.lst").read_text(encoding="latin-1"))
            self.assertNotIn(files[0],
                             (area_dir / "area.lst").read_text(encoding="latin-1"))

            # Reboot: the area reloads from its file with range and room.
            mud.restart()
            with mud.connect(timeout=120) as imm:
                login(imm, "Zbuilder", PASSWORD)
                run(imm, "scroll 0")
                stat = run(imm, "astat Zed Mossy Hollow")
                self.assertIn(f"{LO}-{HI}", stat, "range did not survive reboot: " + stat)
                back = run(imm, f"goto {ROOMVNUM}", 1.5) + run(imm, "look", 1.5)
                self.assertIn("Mossy Hollow", back, "room did not persist: " + back)


if __name__ == "__main__":
    unittest.main()

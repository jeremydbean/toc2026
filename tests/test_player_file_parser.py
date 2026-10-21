"""The dashboard's player-file parser keeps the sections apart.

Audit 2026-10-21: parse_player_file opened the player block at #PLAYER and
closed it only when an #O record happened to follow, so a character
carrying nothing read their pet's Name, HMV, Attr and Levl as their own --
the admin panel and the Oracle's grounding both showed a wolf. Stash
objects after #STASH were also filed as carried. The files here are
synthetic, in save.c's order.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import fastapi  # noqa: F401  -- webadmin.server will not import without it

    WEBADMIN_UNAVAILABLE_REASON = None
except Exception as exc:  # pragma: no cover - C-only environments skip this
    WEBADMIN_UNAVAILABLE_REASON = (
        f"webadmin dependencies unavailable ({type(exc).__name__}: {exc}). "
        "Install webadmin/requirements.txt."
    )

OWNER = """#PLAYER
Name Ztester~
Race human~
Sex  1
Cla 3
Levl 40
HMV  900 1000 50 60 70 80
Attr 20 13 13 13 13
End

"""
WORN = """#O
Vnum 3702
Wear 16
Lev 10
End

"""
CARRIED = """#O
Vnum 3355
Wear -1
Lev 1
End

"""
PET = """#PET
Vnum 3090
Name wolf~
Race wolf~
Sex  0
Levl 5
HMV  10 15 0 0 30 30
Attr 3 3 3 3 3
End

"""
STASH = """#STASH
#O
Vnum 3032
Wear -1
Lev 1
End

"""


@unittest.skipIf(WEBADMIN_UNAVAILABLE_REASON is not None, WEBADMIN_UNAVAILABLE_REASON or "")
class PlayerFileParserTests(unittest.TestCase):
    def parse(self, *sections: str) -> dict:
        from webadmin import server

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "Ztester").write_text("".join(sections) + "#END\n",
                                               encoding="latin-1")
            with patch.object(server, "PLAYER_PATH", Path(tmp)):
                return server.parse_player_file("Ztester")

    def owner_fields(self, data: dict) -> tuple:
        return (data["name"], data["race"], data["level"], data["hp_cur"],
                data["hp_max"], data["str_base"])

    def test_a_pet_never_becomes_its_owner(self) -> None:
        alone = self.owner_fields(self.parse(OWNER))
        self.assertEqual(alone, ("Ztester", "human", 40, 900, 1000, 20))
        for sections in ((OWNER, PET), (OWNER, WORN, PET), (OWNER, CARRIED, PET, STASH)):
            self.assertEqual(self.owner_fields(self.parse(*sections)), alone, sections)

    def test_worn_gear_is_still_read(self) -> None:
        data = self.parse(OWNER, WORN, CARRIED, PET, STASH)
        self.assertEqual([item["vnum"] for item in data["equipment"]], [3702])

    def test_the_stash_is_neither_worn_nor_exposed(self) -> None:
        # A stashed piece keeps the wear slot it was saved with; it is not
        # on the character, and the API does not list the stash.
        data = self.parse(OWNER, PET, STASH.replace("Wear -1", "Wear 16"))
        self.assertEqual(data["equipment"], [])
        self.assertNotIn("stash", data)
        self.assertNotIn("inventory", data)


if __name__ == "__main__":
    unittest.main()

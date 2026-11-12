#!/usr/bin/env python3
"""Make the player-file seed corpus in a disposable world.

Every seed is a character this script creates in a throwaway world
(tests/live_mud.LiveMud) and the game itself saves -- never a real
player's file. Run from the repository root after `make`:

    python3 fuzz/make_seeds.py            # rewrites fuzz/corpus/player/

The seeds:
  new       a level 1 warrior straight out of creation
  kit       the same character made staff and given things: a container
            holding a weapon (Nest), worn armour and light, a wand,
            an alias, a title
  pet       kit with a #PET record and a #STASH holding a container with
            something in it, both in the writer's own shape (fwrite_pet,
            fwrite_obj), spliced in before #END -- buying a pet and
            standing at the altar need trips this script does not make
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import live_mud  # noqa: E402
from live_mud import LiveMud, create_character, login, patch_player_file  # noqa: E402

NAME = "Zfuzz"
PASSWORD = "fuzzseed1"
OUT = ROOT / "fuzz" / "corpus" / "player"

# A container (a black robe, htower.are), a weapon, armour, a light, a wand
# and a trinket -- ordinary shipped prototypes.
KIT = [1387, 630, 101, 3365, 28024, 607]

PET = """#PET
Vnum 2404
Name mercenary pet~
Sex  1
HMV  30 30 100 100 100 100
Pos  8
ACs  95 95 95 95
Attr 13 13 13 13 13
AMod 0 0 0 0 0
AffD 'armor'  10  12 -20  17          0          0
End

"""

STASH = """#STASH
#O
Vnum 1387
Nest 0
Wear -1
Cost 0
Cond 100
End

#O
Vnum 607
Nest 1
Wear -1
Cost 0
Cond 100
End

"""


def quit_and_wait(client) -> None:
    client.send("quit")
    if not client.wait_closed():
        raise SystemExit("the seed character did not leave the world")


def main() -> int:
    if live_mud.skip_reason():
        raise SystemExit(live_mud.skip_reason())
    OUT.mkdir(parents=True, exist_ok=True)
    with LiveMud() as mud:
        with mud.connect(timeout=120) as client:
            create_character(client, NAME, PASSWORD)
            quit_and_wait(client)
        new = (mud.player_dir / NAME).read_bytes()
        (OUT / "new").write_bytes(new)

        patch_player_file(mud, NAME, Levl=70)
        with mud.connect(timeout=120) as client:
            login(client, NAME, PASSWORD)
            for vnum in KIT:
                client.sync("load obj %d" % vnum)
            client.sync("put claymore robe")
            client.sync("wear glasses")
            client.sync("hold banner")
            client.sync("alias zz look")
            client.sync("title the fuzzed")
            client.sync("save")
            quit_and_wait(client)
        kit = (mud.player_dir / NAME).read_bytes()
        (OUT / "kit").write_bytes(kit)

        text = kit.decode("latin-1")
        at = text.find("#STASH")
        if at < 0:
            at = text.find("#END")
            text = text[:at] + PET + STASH + text[at:]
        else:
            text = text[:at] + PET + text[at:]
        (OUT / "pet").write_bytes(text.encode("latin-1"))
    for path in sorted(OUT.iterdir()):
        print(path.relative_to(ROOT), path.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

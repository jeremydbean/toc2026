#!/usr/bin/env python3
"""
Pass 4 help file improvements: typos and grammar fixes in masters.are,
arena.are, horde.are, istari.are, and toc.are.
"""
import os
import tempfile

AREA_DIR = "area"


def fix_file(filename, replacements):
    """Apply a list of (old, new) replacements to a file."""
    path = os.path.join(AREA_DIR, filename)
    with open(path, encoding="latin-1") as f:
        content = f.read()

    original = content
    errors = []
    for old, new, label in replacements:
        count = content.count(old)
        if count == 0:
            errors.append(f"  ERROR: '{label}' — old string not found")
        elif count > 1:
            errors.append(f"  ERROR: '{label}' — old string found {count} times (expected 1)")
        else:
            content = content.replace(old, new, 1)
            print(f"  OK: {label}")

    if errors:
        for e in errors:
            print(e)

    if content != original:
        fd, tmp = tempfile.mkstemp(dir=AREA_DIR)
        try:
            with os.fdopen(fd, "w", encoding="latin-1") as f:
                f.write(content)
            os.replace(tmp, path)
            print(f"  Written: {filename}")
        except Exception:
            os.unlink(tmp)
            raise
    return not errors


# ---------------------------------------------------------------------------
# masters.are — 8 fixes
# ---------------------------------------------------------------------------
masters_fixes = [
    # 1. Typo: "Weaponsmaser" in RAKAR entry title
    (
        "Rakar the Weaponsmaser is skilled",
        "Rakar the Weaponsmaster is skilled",
        "RAKAR: 'Weaponsmaser' → 'Weaponsmaster'",
    ),
    # 2. Typo: "formost" in MORGUE Necro Guild Master line
    (
        "Necro Guild Master - The formost authority",
        "Necro Guild Master - The foremost authority",
        "MORGUE: 'formost' → 'foremost'",
    ),
    # 3. Grammar: "who with to pursue" in MONK entry
    (
        "adventurers who with to pursue this",
        "adventurers who wish to pursue this",
        "MONK: 'who with to pursue' → 'who wish to pursue'",
    ),
    # 4. Grammar: "guild study matriculate" in MAGE entry (garbled phrase)
    (
        "guild study matriculate at the University of \n\nMagic.",
        "guild matriculate at the University of \n\nMagic.",
        "MAGE: 'guild study matriculate' → 'guild matriculate'",
    ),
    # 5. Typo: "haven chosen" in MAGE entry
    (
        "born mages, who\n\nhaven chosen other guilds.",
        "born mages, who\n\nhave chosen other guilds.",
        "MAGE: 'haven chosen' → 'have chosen'",
    ),
    # 6. Typo: "Galdiator" in CITADEL entry
    (
        "Geko the Galdiator (?/W)",
        "Geko the Gladiator (?/W)",
        "CITADEL: 'Galdiator' → 'Gladiator'",
    ),
    # 7. Double word: "different different assortment" in CLERICS entry
    (
        "slightly different \n\ndifferent assortment of spells. ",
        "slightly different assortment of spells. ",
        "CLERICS: doubled 'different different'",
    ),
    # 8. Fix double space in SERALOI keyword line
    (
        'SERALOI  "LOST MAGE"~',
        'SERALOI "LOST MAGE"~',
        "SERALOI: double space in keyword",
    ),
]

# ---------------------------------------------------------------------------
# horde.are — 1 fix
# ---------------------------------------------------------------------------
horde_fixes = [
    (
        "inbreeding, cannibolism, \nand evil rites",
        "inbreeding, cannibalism, \nand evil rites",
        "HORDE: 'cannibolism' → 'cannibalism'",
    ),
]

# ---------------------------------------------------------------------------
# istari.are — 1 fix
# ---------------------------------------------------------------------------
istari_fixes = [
    (
        "of it's inevitability.",
        "of its inevitability.",
        "ISTARI: 'it's' → 'its' (possessive)",
    ),
]

# ---------------------------------------------------------------------------
# arena.are — 1 fix
# ---------------------------------------------------------------------------
arena_fixes = [
    (
        "allowed among plyers who join a CASTLE.",
        "allowed among players who join a CASTLE.",
        "ARENA/PKILLING: 'plyers' → 'players'",
    ),
]

# ---------------------------------------------------------------------------
# toc.are — remove obsolete DTD glossary entry
# ---------------------------------------------------------------------------
toc_fixes = [
    (
        "DTD  - Some software programs allow the person to 'drop to dos'\n",
        "",
        "BEGINNERS: remove obsolete 'DTD' glossary entry",
    ),
]

# ---------------------------------------------------------------------------
# Run all fixes
# ---------------------------------------------------------------------------
all_ok = True
for fname, fixes in [
    ("masters.are", masters_fixes),
    ("horde.are", horde_fixes),
    ("istari.are", istari_fixes),
    ("arena.are", arena_fixes),
    ("toc.are", toc_fixes),
]:
    print(f"\n{fname}:")
    result = fix_file(fname, fixes)
    all_ok = all_ok and result

print("\nDone." if all_ok else "\nCompleted with errors — check output above.")

#!/usr/bin/env python3
"""
Pass 6 help file improvements:
- toc.are: HEROQUEST typo, DOORBASH typo, NEWS possessive
- toc.are: Add See Also to DYING, GUILDS, RACES, EXPERIENCE
- commands.are: PETRIFY affect/effect noun confusion
"""
import os
import tempfile

AREA_DIR = "area"


def fix_file(filename, replacements):
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
            errors.append(f"  ERROR: '{label}' — found {count} times (expected 1)")
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
# toc.are — 7 fixes
# ---------------------------------------------------------------------------
toc_fixes = [
    # 1. HEROQUEST: "This wil start" -> "This will start"
    (
        "heroquest: This wil start the quest.",
        "heroquest: This will start the quest.",
        "HEROQUEST: 'This wil start' -> 'This will start'",
    ),
    # 2. DOORBASH: "mimimum" -> "minimum"
    (
        "The mimimum level to use this skill is 10.",
        "The minimum level to use this skill is 10.",
        "DOORBASH: 'mimimum' -> 'minimum'",
    ),
    # 3. NEWS: "set it's durability" -> "set its durability"
    (
        "and set it's durability to 1.",
        "and set its durability to 1.",
        "NEWS: 'set it\\'s durability' -> 'set its durability' (possessive)",
    ),
    # 4. DYING: add See Also
    (
        "KILLER, THIEF or TRAITOR flag may be looted by anyone.\n~",
        "KILLER, THIEF or TRAITOR flag may be looted by anyone.\n\nSee also: NOLOOT, KILLER, THIEF, TRAITOR\n~",
        "DYING: add See Also",
    ),
    # 5. GUILDS: add See Also
    (
        "can then also type teachlist where you\ncan learn your new skills/spells.\n\n~",
        "can then also type teachlist where you\ncan learn your new skills/spells.\n\nSee also: GAINLIST, TEACHLIST, SKILLS, SPELLS, MULTICLASS\n~",
        "GUILDS: add See Also",
    ),
    # 6. RACES: add See Also
    (
        "Necromancer: Human and elf only\n~",
        "Necromancer: Human and elf only\n\nSee also: CLASS, REMORT, STATS\n~",
        "RACES: add See Also",
    ),
    # 7. EXPERIENCE: add See Also
    (
        "your age in hours; and some random variation.\n~",
        "your age in hours; and some random variation.\n\nSee also: SCORE, LEVEL, DYING\n~",
        "EXPERIENCE: add See Also",
    ),
]

# ---------------------------------------------------------------------------
# commands.are — 1 fix
# ---------------------------------------------------------------------------
commands_fixes = [
    # PETRIFY: "The affect is saved" -> "The effect is saved" (noun use)
    (
        "removes the effect immediately.  The affect is saved across logins.",
        "removes the effect immediately.  The effect is saved across logins.",
        "PETRIFY: 'The affect is saved' -> 'The effect is saved' (noun)",
    ),
]

# ---------------------------------------------------------------------------
# Run all fixes
# ---------------------------------------------------------------------------
all_ok = True
for fname, fixes in [
    ("toc.are", toc_fixes),
    ("commands.are", commands_fixes),
]:
    print(f"\n{fname}:")
    result = fix_file(fname, fixes)
    all_ok = all_ok and result

print("\nDone." if all_ok else "\nCompleted with errors — check output above.")

#!/usr/bin/env python3
"""
Pass 7 help file improvements: See Also additions to commands.are
and targeted cross-references in spells.are (detect/cure/enchant groups).
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
# commands.are — 8 See Also additions
# ---------------------------------------------------------------------------
commands_fixes = [
    # RECALL
    (
        "curse may not recall at all.\n~",
        "curse may not recall at all.\n\nSee also: WORD OF RECALL, PORTAL, MOVEMENT\n~",
        "RECALL: add See Also",
    ),
    # HELP
    (
        "for an alphabetical listing of all keywords.\n~",
        "for an alphabetical listing of all keywords.\n\nSee also: KEYWORDS, COMMANDS, SOCIALS\n~",
        "HELP: add See Also",
    ),
    # DELETE
    (
        "You will not be restored for deleting yourself.\n~",
        "You will not be restored for deleting yourself.\n\nSee also: QUIT, SAVE\n~",
        "DELETE: add See Also",
    ),
    # QUESTION channel
    (
        "to everyone listening on that channel so other players can help.\n~",
        "to everyone listening on that channel so other players can help.\n\nSee also: GOSSIP, TELL, CHANNELS\n~",
        "QUESTION: add See Also",
    ),
    # FREEZE
    (
        "troublemaker is usually a better option than they deny command.\n~",
        "troublemaker is usually a better option than the deny command.\n\nSee also: DENY, PETRIFY, STASIS, MUTE\n~",
        "FREEZE: fix 'they deny' -> 'the deny' + add See Also",
    ),
    # OUTFIT
    (
        "Only empty equipment slots are affected.\n~",
        "Only empty equipment slots are affected.\n\nSee also: EQUIPMENT, WEAR, SUBISSUE\n~",
        "OUTFIT: add See Also",
    ),
    # HERO channel
    (
        "Immortals may also use the hero channel.\n~",
        "Immortals may also use the hero channel.\n\nSee also: GOSSIP, CHANNELS, HEROQUEST\n~",
        "HERO: add See Also",
    ),
]

# ---------------------------------------------------------------------------
# spells.are — 5 See Also additions (cross-reference related spell groups)
# ---------------------------------------------------------------------------
spells_fixes = [
    # DETECT group: detect magic -> cross-ref others
    (
        "Mage:2  Cleric:2  Thief:5  Warrior:5  Monk: N/A   Necromancer:62\n~",
        "Mage:2  Cleric:2  Thief:5  Warrior:5  Monk: N/A   Necromancer:62\n\nSee also: DETECT EVIL, DETECT HIDDEN, DETECT INVIS, IDENTIFY\n~",
        "DETECT MAGIC: add See Also",
    ),
    # ENCHANT WEAPON -> cross-ref enchant armor / identify
    (
        "Enchant weapon is for M/M only and minimum level is 18.\n~",
        "Enchant weapon is for M/M only and minimum level is 18.\n\nSee also: ENCHANT ARMOR, IDENTIFY\n~",
        "ENCHANT WEAPON: add See Also",
    ),
    # ENCHANT ARMOR -> cross-ref enchant weapon / identify
    (
        "Enchant armor is for M/M only and minimum level is 16.\n~",
        "Enchant armor is for M/M only and minimum level is 16.\n\nSee also: ENCHANT WEAPON, IDENTIFY\n~",
        "ENCHANT ARMOR: add See Also",
    ),
    # IDENTIFY -> cross-ref enchant
    (
        "Mage:15  Cleric:16   Thief:18   Warrior:20   Monk: N/A   Necromancer:N/A\n~",
        "Mage:15  Cleric:16   Thief:18   Warrior:20   Monk: N/A   Necromancer:N/A\n\nSee also: ENCHANT WEAPON, ENCHANT ARMOR, LORE\n~",
        "IDENTIFY: add See Also",
    ),
    # TELEPORT -> cross-ref recall
    (
        "Mage:13  Cleric:22   Thief:25   Warrior:36   Monk: N/A   Necromancer:N/A\n~",
        "Mage:13  Cleric:22   Thief:25   Warrior:36   Monk: N/A   Necromancer:N/A\n\nSee also: WORD OF RECALL, RECALL, PORTAL\n~",
        "TELEPORT: add See Also",
    ),
]

# ---------------------------------------------------------------------------
# Run all fixes
# ---------------------------------------------------------------------------
all_ok = True
for fname, fixes in [
    ("commands.are", commands_fixes),
    ("spells.are", spells_fixes),
]:
    print(f"\n{fname}:")
    result = fix_file(fname, fixes)
    all_ok = all_ok and result

print("\nDone." if all_ok else "\nCompleted with errors — check output above.")

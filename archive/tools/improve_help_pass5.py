#!/usr/bin/env python3
"""
Pass 5 help file improvements:
- toc.are: LYCANTHROPY typos + TAX apostrophe + BEGINNERS Dresden services section
- commands.are: EXPLODE possessive + IGNORE See Also
- spells.are: BLIZZARD area effect + RESTORE MANA expanded + CHANGE SEX expanded
- skills.are: MINDBAR possessive
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
# toc.are — 5 fixes
# ---------------------------------------------------------------------------
toc_fixes = [
    # 1. LYCANTHROPY: "know known" -> "no known"
    (
        "There is currently know known cure for this\ndisease.",
        "There is currently no known cure for this\ndisease.",
        "LYCANTHROPY: 'know known' -> 'no known'",
    ),
    # 2. LYCANTHROPY: "into it's current form" -> "into its current form"
    (
        "has mutated into it's current form.",
        "has mutated into its current form.",
        "LYCANTHROPY: 'into it\\'s' -> 'into its' (possessive)",
    ),
    # 3. LYCANTHROPY: "depending on there size" -> "depending on their size"
    (
        "carry 1-4 items, depending on there size,",
        "carry 1-4 items, depending on their size,",
        "LYCANTHROPY: 'on there size' -> 'on their size'",
    ),
    # 4. TAX: "mayors office" -> "mayor's office"
    (
        "and furnishing the mayors office\nin high style",
        "and furnishing the mayor's office\nin high style",
        "TAX: 'mayors office' -> 'mayor\\'s office'",
    ),
    # 5. BEGINNERS: add a "Dresden Services" section before "General MUD Terms"
    (
        "There's a Newbie Train, up from the Entrance to Mud School, which can\n"
        "take you to these places and more.\n"
        "\n"
        "\n"
        "General MUD Terms",
        "There's a Newbie Train, up from the Entrance to Mud School, which can\n"
        "take you to these places and more.\n"
        "\n"
        "\n"
        "Dresden Services\n"
        "================\n"
        "\n"
        "The starting city of Dresden has several useful services:\n"
        "\n"
        "Bank        - Deposit and withdraw gold.  Your balance earns 1% interest\n"
        "              per real day and survives death and remort.  See help BANK.\n"
        "\n"
        "Casino      - The Lucky Dragon Casino in Market Plaza offers slots and\n"
        "              card games for those feeling lucky.  See help CASINO.\n"
        "\n"
        "Psionics    - Some characters can develop psionic abilities.  The PSIONIC\n"
        "              channel alerts you to nearby mental activity.  See help PSIONICS.\n"
        "\n"
        "\n"
        "General MUD Terms",
        "BEGINNERS: add Dresden Services section (bank/casino/psionics)",
    ),
]

# ---------------------------------------------------------------------------
# commands.are — 2 fixes
# ---------------------------------------------------------------------------
commands_fixes = [
    # 1. EXPLODE: "It's main use" -> "Its main use" (possessive, not contraction)
    (
        "inventory all over the MUD. It's main use is to simplify",
        "inventory all over the MUD. Its main use is to simplify",
        "EXPLODE: 'It\\'s main use' -> 'Its main use' (possessive)",
    ),
    # 2. IGNORE: add See Also line
    (
        "ignore nobody will clear your ignore list.\n\n~",
        "ignore nobody will clear your ignore list.\n\nSee also: TELL, CHANNELS\n~",
        "IGNORE: add 'See also: TELL, CHANNELS'",
    ),
]

# ---------------------------------------------------------------------------
# spells.are — 3 fixes
# ---------------------------------------------------------------------------
spells_fixes = [
    # 1. BLIZZARD: "area affect spell" -> "area-effect spell"
    (
        "Blizzard is an area affect\nspell that hits all attackable characters in the room",
        "Blizzard is an area-effect\nspell that hits all attackable characters in the room",
        "BLIZZARD: 'area affect spell' -> 'area-effect spell'",
    ),
    # 2. RESTORE MANA: expand stub description
    (
        "Syntax: c 'restore mana'\n\nThis spell restores the mana of the spellcaster.\n~",
        "Syntax: c 'restore mana'\n       c 'restore mana' <target>\n\n"
        "Restore mana replenishes a small amount of mana (5 to 50 points) for the\n"
        "caster or a chosen target.  It can be cast at any time while standing and\n"
        "is useful for topping off mana between fights.\n~",
        "RESTORE MANA: expand stub with actual effect and range",
    ),
    # 3. CHANGE SEX: expand stub description
    (
        "Syntax: cast 'change sex' <victim>\n\nThis spell changes the sex of the victim (temporarily).\n~",
        "Syntax: cast 'change sex' <victim>\n\n"
        "Change sex alters the gender of the victim for a duration based on the\n"
        "caster's level (approximately 2 ticks per level).  The victim may resist\n"
        "the spell with a saving throw.  The effect is purely cosmetic and wears\n"
        "off naturally.  A second application has no effect while the first is\n"
        "still active.\n~",
        "CHANGE SEX: expand stub with duration and save info",
    ),
]

# ---------------------------------------------------------------------------
# skills.are — 1 fix
# ---------------------------------------------------------------------------
skills_fixes = [
    # MINDBAR: "It's strength is similar" -> "Its strength is similar"
    (
        "psionicist can have. It's\nstrength is similar to the spell sanctuary",
        "psionicist can have. Its\nstrength is similar to the spell sanctuary",
        "MINDBAR: 'It\\'s strength' -> 'Its strength' (possessive)",
    ),
]

# ---------------------------------------------------------------------------
# Run all fixes
# ---------------------------------------------------------------------------
all_ok = True
for fname, fixes in [
    ("toc.are", toc_fixes),
    ("commands.are", commands_fixes),
    ("spells.are", spells_fixes),
    ("skills.are", skills_fixes),
]:
    print(f"\n{fname}:")
    result = fix_file(fname, fixes)
    all_ok = all_ok and result

print("\nDone." if all_ok else "\nCompleted with errors — check output above.")

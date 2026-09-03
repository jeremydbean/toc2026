#!/usr/bin/env python3
"""
Pass 13 — Add See Also to masters.are (18 guild/trainer entries),
help.are (4 entries), and small area help files.
"""

import os, sys

AREA_DIR = "area"

def read_file(fname):
    with open(os.path.join(AREA_DIR, fname), encoding='latin-1') as f:
        return f.read()

def write_file(fname, content):
    path = os.path.join(AREA_DIR, fname)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='latin-1') as f:
        f.write(content)
    os.replace(tmp, path)

def replace_once(content, old, new, label):
    count = content.count(old)
    if count == 0:
        print(f"  ERROR – not found:  {label!r}")
        return content, False
    if count > 1:
        print(f"  ERROR – {count} occurrences: {label!r}")
        return content, False
    print(f"  OK  {label}")
    return content.replace(old, new, 1), True

errors = 0

# ─────────────────────────────────────────────────────────────────────────────
# masters.are — 18 guild/trainer entries
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== masters.are ===")
ma = read_file('masters.are')
ok_ma = 0

masters_changes = [
    (
        "MUDSCHOOL ADEPT overview",
        "high level for him to consider you as a potential student.\n\n~",
        "high level for him to consider you as a potential student.\n\nSee also: BEGINNERS, SKILLS, GAIN\n\n~",
    ),
    (
        "JAZAIR general trainer",
        "tricks if you approach him nicely.\n\n~",
        "tricks if you approach him nicely.\n\nSee also: SHOVE, ARCHERY, SKILLS\n\n~",
    ),
    (
        "FINGERS recall trainer",
        "he just may share it with you.\n\n~",
        "he just may share it with you.\n\nSee also: RECALL, SKILLS\n\n~",
    ),
    (
        "SALIR psionic trainer",
        "rare gift from the gods.\n\n~",
        "rare gift from the gods.\n\nSee also: PSIONICS, GAIN\n\n~",
    ),
    (
        "TEMPLE OF BREAS cleric guild",
        "she is also\n\nskilled at teaching elemental magics.\n\n~",
        "she is also\n\nskilled at teaching elemental magics.\n\nSee also: GUILDS, GAIN, BENEDICTIONS\n\n~",
    ),
    (
        "CLERICS DAVID cleric trainer",
        "cleric spells to aid them on their adventures.\n\n~",
        "cleric spells to aid them on their adventures.\n\nSee also: GUILDS, GAIN, SPELLS\n\n~",
    ),
    (
        "CITADEL OF WAR warrior guild",
        "only full warriors may\n\nbecome his students.\n\n~",
        "only full warriors may\n\nbecome his students.\n\nSee also: GUILDS, GAIN, SKILLS\n\n~",
    ),
    (
        "RAKAR weaponsmaster",
        "and Conquer and Conquer and Conquer.\"\n\n~",
        "and Conquer and Conquer and Conquer.\"\n\nSee also: ARCHERY, SHOVE, SKILLS\n\n~",
    ),
    (
        "WARRIOR KALAK blacksmith",
        "fighting skills that will help an \n\nadventurer survive.\n\n~",
        "fighting skills that will help an \n\nadventurer survive.\n\nSee also: GUILDS, GAIN, SKILLS\n\n~",
    ),
    (
        "HOUSE OF THIEVES guild",
        "him to detect what is on the other side of closed doors.  \n\n~",
        "him to detect what is on the other side of closed doors.  \n\nSee also: GUILDS, GAIN, STEALTH\n\n~",
    ),
    (
        "THIEF TIA trainer",
        "Look near River Road, as that is his\n\nfavorite hangout.\n\n~",
        "Look near River Road, as that is his\n\nfavorite hangout.\n\nSee also: GUILDS, GAIN, STEALTH\n\n~",
    ),
    (
        "UNIVERSITY OF MAGIC mage guild",
        "the rigors of adventure.\n\n~",
        "the rigors of adventure.\n\nSee also: GUILDS, GAIN, SPELLS\n\n~",
    ),
    (
        "MAGE GIOLI trainer",
        "skills that your guildmasters may not know.\n\n~",
        "skills that your guildmasters may not know.\n\nSee also: GUILDS, GAIN, SPELLS\n\n~",
    ),
    (
        "SERALOI riding trainer",
        "he fills in time by giving riding lessons.\n\n~",
        "he fills in time by giving riding lessons.\n\nSee also: RIDE, SKILLS\n\n~",
    ),
    (
        "PALMS OF THE CREATOR monk guild",
        "weapons and beat them to the ground.\n\n~",
        "weapons and beat them to the ground.\n\nSee also: GUILDS, GAIN, SKILLS\n\n~",
    ),
    (
        "MONK guild",
        "classes may not join the monks' guild.\n\n~",
        "classes may not join the monks' guild.\n\nSee also: GUILDS, GAIN, PSIONICS\n\n~",
    ),
    (
        "MORGUE OF DRESDEN necro guild",
        "is said to mix a pretty mean potion for the master's before dinner\n\npleasure.\n\n~",
        "is said to mix a pretty mean potion for the master's before dinner\n\npleasure.\n\nSee also: GUILDS, GAIN, LIFE-UNDEATH\n\n~",
    ),
    (
        "NECROMANCER guild",
        "may not join the necromancers' guild.\n\n~",
        "may not join the necromancers' guild.\n\nSee also: GUILDS, GAIN, LIFE-UNDEATH\n\n~",
    ),
]

for label, old, new in masters_changes:
    ma, ok = replace_once(ma, old, new, label)
    if ok: ok_ma += 1
    else: errors += 1

write_file('masters.are', ma)
print(f"  → masters.are: {ok_ma}/{len(masters_changes)} applied")

# ─────────────────────────────────────────────────────────────────────────────
# help.are — 4 entries
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== help.are ===")
ha = read_file('help.are')
ok_ha = 0

help_changes = [
    (
        "DIKU credits",
        "DIKU -- The Department of Computer Science\n                      at the University of Copenhagen.\n\n~",
        "DIKU -- The Department of Computer Science\n                      at the University of Copenhagen.\n\nSee also: MERC, ROM\n\n~",
    ),
    (
        "MERC credits",
        "hours of enjoyment.\n\nShare and enjoy.\n~",
        "hours of enjoyment.\n\nShare and enjoy.\n\nSee also: DIKU, ROM\n~",
    ),
    (
        "SUMMARY help list",
        "If you are new here, we recommend that you read BEGINNERS.\n~",
        "If you are new here, we recommend that you read BEGINNERS.\n\nSee also: COMMANDS, WIZHELP, BEGINNERS\n~",
    ),
    (
        "DAMAGE table",
        "At the far reaches of damaging power: \"do UNSPEAKABLE things to\"\n~",
        "At the far reaches of damaging power: \"do UNSPEAKABLE things to\"\n\nSee also: COMBAT, SKILLS, SPELLS\n~",
    ),
]

for label, old, new in help_changes:
    ha, ok = replace_once(ha, old, new, label)
    if ok: ok_ha += 1
    else: errors += 1

write_file('help.are', ha)
print(f"  → help.are: {ok_ha}/{len(help_changes)} applied")

# ─────────────────────────────────────────────────────────────────────────────
# Small area help files
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== small area files ===")

small_changes = {
    'arena.are': [
        (
            "arena pkilling rules",
            "buy/sell stuff.\n\n~",
            "buy/sell stuff.\n\nSee also: PKILL, GUILDS\n\n~",
        ),
    ],
    'camelot.are': [
        (
            "camelot area help",
            "For more information\nabout ARENA areas, type HELP ARENA.\n~",
            "For more information\nabout ARENA areas, type HELP ARENA.\n\nSee also: ARENA, PKILL\n~",
        ),
    ],
    'consortium.are': [
        (
            "CONSORTIUM guild",
            "a vast degree of knowledge about\nSembia.\n~",
            "a vast degree of knowledge about\nSembia.\n\nSee also: GUILDS, GAIN, NOTE\n~",
        ),
    ],
    'dominion.are': [
        (
            "DOMINION guild",
            "member and post a note to us.\n~",
            "member and post a note to us.\n\nSee also: GUILDS, GAIN, NOTE\n~",
        ),
    ],
    'horde.are': [
        (
            "HORDE guild",
            "Wanna join up?\n~",
            "Wanna join up?\n\nSee also: GUILDS, GAIN, NOTE\n~",
        ),
    ],
    'istari.are': [
        (
            "ISTARI guild",
            "information about joining.\n~",
            "information about joining.\n\nSee also: GUILDS, GAIN, NOTE\n~",
        ),
    ],
    'mountain.are': [
        (
            "AQUEST area quest",
            "enjoy this new feature on TOC.\n~",
            "enjoy this new feature on TOC.\n\nSee also: HEROQUEST, QUEST\n~",
        ),
    ],
    'valley.are': [
        (
            "VALLEY ELF race",
            "gnomekind, whom they tolerate.\n\n~",
            "gnomekind, whom they tolerate.\n\nSee also: RACES, ELF\n\n~",
        ),
    ],
}

ok_small = 0; total_small = 0
for fname, changes in small_changes.items():
    total_small += len(changes)
    content = read_file(fname)
    file_ok = 0
    for label, old, new in changes:
        content, ok = replace_once(content, old, new, f"{fname}: {label}")
        if ok:
            ok_small += 1; file_ok += 1
        else:
            errors += 1
    if file_ok > 0:
        write_file(fname, content)

print(f"  → small files: {ok_small}/{total_small} applied")

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
total_ok = ok_ma + ok_ha + ok_small
total = len(masters_changes) + len(help_changes) + total_small
print(f"\nTotal: {total_ok}/{total} OK, {errors} errors")
if errors:
    sys.exit(1)

#!/usr/bin/env python3
"""Help pass 8:
- camelot.are: Arturian -> Arthurian
- valley.are: it's anger -> its anger (mob desc possessive)
- skills.are: BERSERK bug fix (bash -> berserk) + 21 See Also additions
- toc.are: 6 See Also additions (SPELLGROUP, KEYWORDS, PROMPT, TICK, DAMAGE, HEROQUEST)
- spells.are: 15 See Also additions (detect group, dispel group, bless/curse, armor, cure/cause, etc.)
"""

import os
import tempfile

AREA_DIR = 'area'


def replace_once(content, old, new, label):
    count = content.count(old)
    if count == 0:
        print(f'  ERROR (not found): {label}')
        return content, False
    if count > 1:
        print(f'  ERROR (found {count} times): {label}')
        return content, False
    print(f'  OK: {label}')
    return content.replace(old, new, 1), True


def write_file(path, content):
    dirpath = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=dirpath)
    try:
        with os.fdopen(fd, 'w', encoding='latin-1') as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# =============================================================
# camelot.are: typo Arturian -> Arthurian
# =============================================================
print('=== camelot.are ===')
path = f'{AREA_DIR}/camelot.are'
with open(path, encoding='latin-1') as f:
    content = f.read()

content, _ = replace_once(
    content,
    'traditional\nArturian legends in content.',
    'traditional\nArthurian legends in content.',
    'Arturian -> Arthurian'
)

write_file(path, content)

# =============================================================
# valley.are: it's anger -> its anger (mob description)
# =============================================================
print('\n=== valley.are ===')
path = f'{AREA_DIR}/valley.are'
with open(path, encoding='latin-1') as f:
    content = f.read()

content, _ = replace_once(
    content,
    "willing to take out it's\n\nanger at you!",
    "willing to take out its\n\nanger at you!",
    "take out it's anger -> its anger (possessive)"
)

write_file(path, content)

# =============================================================
# skills.are: BERSERK bug fix + 21 See Also additions
# =============================================================
print('\n=== skills.are ===')
path = f'{AREA_DIR}/skills.are'
with open(path, encoding='latin-1') as f:
    content = f.read()

fixes = [
    # Bug: BERSERK says "bash" instead of "berserk" + add See Also
    (
        'Monks and necromancers may not learn bash since they cannot join the\n'
        'warrior guild.\n\n'
        'Trainer: Geko (?/W)\n~',
        'Monks and necromancers may not learn berserk since they cannot join the\n'
        'warrior guild.\n\n'
        'Trainer: Geko (?/W)\n\n'
        'See also: ENHANCED DAMAGE, BASH\n~',
        'BERSERK: fix bash->berserk + See Also'
    ),
    # HIDE SNEAK
    (
        'Monks and Necromancers cannot learn to hide or sneak.\n~',
        'Monks and Necromancers cannot learn to hide or sneak.\n\n'
        'See also: BACKSTAB, STEAL, PEEK, STEALTH\n~',
        'HIDE SNEAK: See Also'
    ),
    # BACKSTAB
    (
        'Trainer:  Ni Hi the Ninja Master (?/T), Tia (T/?)\n'
        '           and mud school adept (practice only, no gain)\n~',
        'Trainer:  Ni Hi the Ninja Master (?/T), Tia (T/?)\n'
        '           and mud school adept (practice only, no gain)\n\n'
        'See also: HIDE SNEAK, STEALTH, FATALITY\n~',
        'BACKSTAB: See Also'
    ),
    # BASH
    (
        'Trainer: Geko (?/W), Jazair (any with skill but no gain),\n'
        '         Master of Movement (Monk)\n~',
        'Trainer: Geko (?/W), Jazair (any with skill but no gain),\n'
        '         Master of Movement (Monk)\n\n'
        'See also: KICK, TRIP, SHOVE\n~',
        'BASH: See Also'
    ),
    # KICK (has trailing comma after 'no gain)')
    (
        'Trainer: Breark (*/W), Kalak (W/?), Silent Master (Monk),\n'
        '         mud school adept (practice only, no gain),\n~',
        'Trainer: Breark (*/W), Kalak (W/?), Silent Master (Monk),\n'
        '         mud school adept (practice only, no gain),\n\n'
        'See also: BASH, TRIP, DIRT KICKING\n~',
        'KICK: See Also'
    ),
    # TRIP
    (
        'Trainer: Ni Hi (?/T), Silent Master (Monk), mud school adept (practice only,\n'
        '         no gain)\n~',
        'Trainer: Ni Hi (?/T), Silent Master (Monk), mud school adept (practice only,\n'
        '         no gain)\n\n'
        'See also: BASH, KICK\n~',
        'TRIP: See Also'
    ),
    # DODGE (has blank line before tilde)
    (
        'mud school adept (practice only, no gain), Silent Master (monk)\n'
        '          Necromantic Knight (necro),\n\n~',
        'mud school adept (practice only, no gain), Silent Master (monk)\n'
        '          Necromantic Knight (necro),\n\n'
        'See also: PARRY, SHIELD BLOCK\n~',
        'DODGE: See Also'
    ),
    # PARRY
    (
        'Trainer: Dolonar (?/W), Stout(?/T), Kalak (W/?), Silent Master (Monk),\n'
        '         mud school adept (practice only, no gain)\n~',
        'Trainer: Dolonar (?/W), Stout(?/T), Kalak (W/?), Silent Master (Monk),\n'
        '         mud school adept (practice only, no gain)\n\n'
        'See also: DODGE, SHIELD BLOCK\n~',
        'PARRY: See Also'
    ),
    # SHIELD BLOCK
    (
        'Trainer: Kalak (W/?), Geko (?/W), mud school adept (practice only, no gain)\n~',
        'Trainer: Kalak (W/?), Geko (?/W), mud school adept (practice only, no gain)\n\n'
        'See also: PARRY, DODGE\n~',
        'SHIELD BLOCK: See Also'
    ),
    # DUAL WIELD
    (
        'dual wield is 17.\n\n'
        'Number of trains: 3\n'
        'Trainer: Mizry (T/T)\n~',
        'dual wield is 17.\n\n'
        'Number of trains: 3\n'
        'Trainer: Mizry (T/T)\n\n'
        'See also: SECOND ATTACK, THIRD ATTACK\n~',
        'DUAL WIELD: See Also'
    ),
    # SECOND ATTACK
    (
        'Kilar (?/M), Master of Movement (Monk), Flame the fire\n'
        '         Mage (M/M)\n~',
        'Kilar (?/M), Master of Movement (Monk), Flame the fire\n'
        '         Mage (M/M)\n\n'
        'See also: THIRD ATTACK, DUAL WIELD\n~',
        'SECOND ATTACK: See Also'
    ),
    # THIRD ATTACK
    (
        'they may use it at level 15 and above.\n\n'
        'Number of trains: 4\n'
        'Trainer: Vladamir (W/W)\n~',
        'they may use it at level 15 and above.\n\n'
        'Number of trains: 4\n'
        'Trainer: Vladamir (W/W)\n\n'
        'See also: SECOND ATTACK, DUAL WIELD\n~',
        'THIRD ATTACK: See Also'
    ),
    # FAST HEALING
    (
        'Necromancers and Clerics cannot learn fast healing.\n\n'
        'Trainer: Breark (?/W), Silent Master (Monk)\n~',
        'Necromancers and Clerics cannot learn fast healing.\n\n'
        'Trainer: Breark (?/W), Silent Master (Monk)\n\n'
        'See also: MEDITATION\n~',
        'FAST HEALING: See Also'
    ),
    # MEDITATION
    (
        'Trainer: Silius (?/C), Diemos (?/M), Necromantic Knight (necro),\n'
        '         Master of Movement (Monk)\n~',
        'Trainer: Silius (?/C), Diemos (?/M), Necromantic Knight (necro),\n'
        '         Master of Movement (Monk)\n\n'
        'See also: FAST HEALING\n~',
        'MEDITATION: See Also'
    ),
    # DIRT KICKING
    (
        'Necromancers cannot use dirt kicking.\n\n'
        'Trainer: Geko (?/W), Ni Hi (?/T), Silent Master (monk)\n~',
        'Necromancers cannot use dirt kicking.\n\n'
        'Trainer: Geko (?/W), Ni Hi (?/T), Silent Master (monk)\n\n'
        'See also: BASH, KICK\n~',
        'DIRT KICKING: See Also'
    ),
    # TRACK
    (
        'Number of trains required: 1\n'
        'Trainer: Mizry, the Assassin\n~',
        'Number of trains required: 1\n'
        'Trainer: Mizry, the Assassin\n\n'
        'See also: DANGER SENSE, SEARCH\n~',
        'TRACK: See Also'
    ),
    # LORE
    (
        "thieves' guild.\n\n"
        'Trainer: Stout (?/T)\n~',
        "thieves' guild.\n\n"
        'Trainer: Stout (?/T)\n\n'
        'See also: IDENTIFY, DETECT MAGIC\n~',
        'LORE: See Also'
    ),
    # STEAL (use more context to avoid collision with SEARCH)
    (
        'therefore, cannot\n'
        'learn to steal.\n\n'
        'Trainer: Quickfingers (?/T), Tia (T/?), mud school adept (practice only,\n'
        '         no gain)\n~',
        'therefore, cannot\n'
        'learn to steal.\n\n'
        'Trainer: Quickfingers (?/T), Tia (T/?), mud school adept (practice only,\n'
        '         no gain)\n\n'
        'See also: PEEK, HIDE SNEAK, SLEIGHT OF HAND\n~',
        'STEAL: See Also'
    ),
    # PEEK
    (
        "thieves' guild.\n\n"
        'Trainer: Quickfingers (?/T)\n~',
        "thieves' guild.\n\n"
        'Trainer: Quickfingers (?/T)\n\n'
        'See also: STEAL, HIDE SNEAK, SEARCH\n~',
        'PEEK: See Also'
    ),
    # SEARCH (distinct from STEAL by preceding context)
    (
        "not join the thieves' guild.\n\n"
        'Trainer: Quickfingers (?/T), Tia (T/?), mud school adept (practice only,\n'
        '         no gain)\n~',
        "not join the thieves' guild.\n\n"
        'Trainer: Quickfingers (?/T), Tia (T/?), mud school adept (practice only,\n'
        '         no gain)\n\n'
        'See also: PEEK, DETECT HIDDEN\n~',
        'SEARCH: See Also'
    ),
    # STEALTH
    (
        'Number of trains required: 5\n'
        'Trainer: Mizry (T/T)\n~',
        'Number of trains required: 5\n'
        'Trainer: Mizry (T/T)\n\n'
        'See also: HIDE SNEAK, BACKSTAB\n~',
        'STEALTH: See Also'
    ),
    # DISARM
    (
        'Necromancers cannot learn to disarm.\n\n'
        'Trainer: Kalak (W/?), Dolonar (?/W), Master of Movement (Monk)\n~',
        'Necromancers cannot learn to disarm.\n\n'
        'Trainer: Kalak (W/?), Dolonar (?/W), Master of Movement (Monk)\n\n'
        'See also: BASH, SHOVE\n~',
        'DISARM: See Also'
    ),
    # FATALITY
    (
        'Number of trains: 5\n'
        'Trainer: Mizry (T/T)\n~',
        'Number of trains: 5\n'
        'Trainer: Mizry (T/T)\n\n'
        'See also: BACKSTAB, DESTRUCTION\n~',
        'FATALITY: See Also'
    ),
]

for old, new, label in fixes:
    content, _ = replace_once(content, old, new, label)

write_file(path, content)

# =============================================================
# toc.are: 6 See Also additions
# =============================================================
print('\n=== toc.are ===')
path = f'{AREA_DIR}/toc.are'
with open(path, encoding='latin-1') as f:
    content = f.read()

toc_fixes = [
    # SPELLGROUP
    (
        'mortals, it is listed as N/A.\n~',
        'mortals, it is listed as N/A.\n\n'
        'See also: GAIN, GAINLIST, GROUPS\n~',
        'SPELLGROUP: See Also'
    ),
    # KEYWORDS
    (
        'animate parts    shield block         track\n~',
        'animate parts    shield block         track\n\n'
        'See also: HELP, COMMANDS\n~',
        'KEYWORDS: See Also'
    ),
    # PROMPT (has blank line before tilde)
    (
        'Will set your prompt to "<10hp 100m 100mv>"\n\n~',
        'Will set your prompt to "<10hp 100m 100mv>"\n\n'
        'See also: SCORE, AFFECTS\n~',
        'PROMPT: See Also'
    ),
    # TICK
    (
        'will not be regenerated if anyone is in the area when it resets.\n~',
        'will not be regenerated if anyone is in the area when it resets.\n\n'
        'See also: FAST HEALING, MEDITATION, RESTING\n~',
        'TICK: See Also'
    ),
    # DAMAGE
    (
        'At the far reaches of damaging power: "do UNSPEAKABLE things to"\n~',
        'At the far reaches of damaging power: "do UNSPEAKABLE things to"\n\n'
        'See also: COMBAT, ATTACK, WIMPY\n~',
        'DAMAGE: See Also'
    ),
    # HEROQUEST
    (
        'that PC and your Hero will SUFFER SEVERE PENALTIES, NO EXCEPTIONS!!!\n~',
        'that PC and your Hero will SUFFER SEVERE PENALTIES, NO EXCEPTIONS!!!\n\n'
        'See also: HERO, HEROLEVELS, QUESTS\n~',
        'HEROQUEST: See Also'
    ),
]

for old, new, label in toc_fixes:
    content, _ = replace_once(content, old, new, label)

write_file(path, content)

# =============================================================
# spells.are: 15 See Also additions
# =============================================================
print('\n=== spells.are ===')
path = f'{AREA_DIR}/spells.are'
with open(path, encoding='latin-1') as f:
    content = f.read()

spell_fixes = [
    # BLESS
    (
        'Mage:9  Cleric:6  Thief:12   Warrior:11   Monk: N/A   Necromancer:N/A\n~',
        'Mage:9  Cleric:6  Thief:12   Warrior:11   Monk: N/A   Necromancer:N/A\n\n'
        'See also: CURSE, KNOW ALIGNMENT, BENEDICTIONS\n~',
        'BLESS: See Also'
    ),
    # CURSE
    (
        'Mage:21  Cleric:19  Thief:25  Warrior:23  Monk: N/A  Necromancer:N/A\n~',
        'Mage:21  Cleric:19  Thief:25  Warrior:23  Monk: N/A  Necromancer:N/A\n\n'
        'See also: BLESS, DISPEL MAGIC, MALADICTIONS\n~',
        'CURSE: See Also'
    ),
    # ARMOR / STONE SKIN group
    (
        'Mage:30   Cleric:30   Thief:35   Warrior:40   Monk: N/A   Necromancer:32\n~',
        'Mage:30   Cleric:30   Thief:35   Warrior:40   Monk: N/A   Necromancer:32\n\n'
        'See also: PROTECTION EVIL, ENCHANT ARMOR, PROTECTIVE\n~',
        'ARMOR/STONE SKIN group: See Also'
    ),
    # CAUSE LIGHT/SERIOUS/CRITICAL/HARM
    (
        'Mage:25  Cleric:24  Thief:32  Warrior:28  Monk: N/A   Necromancer:N/A\n~',
        'Mage:25  Cleric:24  Thief:32  Warrior:28  Monk: N/A   Necromancer:N/A\n\n'
        'See also: CURE LIGHT, CURE CRITICAL, HARMFUL\n~',
        'CAUSE LIGHT/CRITICAL: See Also'
    ),
    # CURE LIGHT/SERIOUS/CRITICAL/HEALSPELL/MASS HEALING
    (
        'Mass healing is for C/C only with a minimum level of 38.\n~',
        'Mass healing is for C/C only with a minimum level of 38.\n\n'
        'See also: AID, CAUSE LIGHT, HEALING\n~',
        'CURE LIGHT/MASS HEALING: See Also'
    ),
    # DETECT EVIL
    (
        'Mage:10   Cleric:10  Thief:13   Warrior:13   Monk: N/A   Necromancer:N/A\n~',
        'Mage:10   Cleric:10  Thief:13   Warrior:13   Monk: N/A   Necromancer:N/A\n\n'
        'See also: DETECT GOOD, DETECT MAGIC, KNOW ALIGNMENT\n~',
        'DETECT EVIL: See Also'
    ),
    # DETECT GOOD (slightly different spacing)
    (
        'Mage:10  Cleric:10  Thief:13   Warrior:13   Monk: N/A   Necromancer:N/A\n~',
        'Mage:10  Cleric:10  Thief:13   Warrior:13   Monk: N/A   Necromancer:N/A\n\n'
        'See also: DETECT EVIL, DETECT MAGIC, KNOW ALIGNMENT\n~',
        'DETECT GOOD: See Also'
    ),
    # DETECT STEALTH
    (
        'detect stealthy creatures.\n\n'
        'Minimum level depends on your primary class and is:\n'
        'Mage:9  Cleric:9  Thief:14   Warrior:14   Monk: N/A   Necromancer:N/A\n~',
        'detect stealthy creatures.\n\n'
        'Minimum level depends on your primary class and is:\n'
        'Mage:9  Cleric:9  Thief:14   Warrior:14   Monk: N/A   Necromancer:N/A\n\n'
        'See also: DETECT HIDDEN, DETECT INVIS, DETECTION\n~',
        'DETECT STEALTH: See Also'
    ),
    # DETECT HIDDEN
    (
        'detect hidden creatures.\n\n'
        'Minimum level depends on your primary class and is:\n'
        'Mage:9  Cleric:9  Thief:14   Warrior:14   Monk: N/A   Necromancer:N/A\n~',
        'detect hidden creatures.\n\n'
        'Minimum level depends on your primary class and is:\n'
        'Mage:9  Cleric:9  Thief:14   Warrior:14   Monk: N/A   Necromancer:N/A\n\n'
        'See also: DETECT STEALTH, DETECT INVIS, DETECTION\n~',
        'DETECT HIDDEN: See Also'
    ),
    # DETECT INVIS
    (
        'Mage:8  Cleric:7  Thief:11   Warrior:11   Monk: N/A   Necromancer:N/A\n~',
        'Mage:8  Cleric:7  Thief:11   Warrior:11   Monk: N/A   Necromancer:N/A\n\n'
        'See also: DETECT HIDDEN, DETECT STEALTH, INVIS\n~',
        'DETECT INVIS: See Also'
    ),
    # DETECT POISON
    (
        'Mage:12   Cleric:7   Thief:9   Warrior:15   Monk: N/A   Necromancer:N/A\n~',
        'Mage:12   Cleric:7   Thief:9   Warrior:15   Monk: N/A   Necromancer:N/A\n\n'
        'See also: CURE POISON, DETECT MAGIC\n~',
        'DETECT POISON: See Also'
    ),
    # DETECT TRAPS
    (
        'This spell is available only to mages and clerics.  Minimum level is 11.\n~',
        'This spell is available only to mages and clerics.  Minimum level is 11.\n\n'
        'See also: DETECT HIDDEN, DETECT MAGIC, DETECTION\n~',
        'DETECT TRAPS: See Also'
    ),
    # DISPEL EVIL
    (
        'Mage:23   Cleric:23   Thief:29   Warrior:29   Monk: N/A   Necromancer:N/A\n~',
        'Mage:23   Cleric:23   Thief:29   Warrior:29   Monk: N/A   Necromancer:N/A\n\n'
        'See also: DISPEL GOOD, DISPEL MAGIC, ALIGNMENT\n~',
        'DISPEL EVIL: See Also'
    ),
    # DISPEL GOOD (different tail: Necromancer: with no N/A)
    (
        'Mage:23   Cleric:23   Thief:29   Warrior:29   Monk: N/A   Necromancer:\n~',
        'Mage:23   Cleric:23   Thief:29   Warrior:29   Monk: N/A   Necromancer:\n\n'
        'See also: DISPEL EVIL, DISPEL MAGIC, ALIGNMENT\n~',
        'DISPEL GOOD: See Also'
    ),
    # DISPEL MAGIC / CANCELLATION / NEUTRALITY FIELD
    (
        'Neutrality field is only available to Necromancer at level 40 and higher.\n~',
        'Neutrality field is only available to Necromancer at level 40 and higher.\n\n'
        'See also: DISPEL EVIL, DISPEL GOOD, REMOVE CURSE\n~',
        'DISPEL MAGIC: See Also'
    ),
]

for old, new, label in spell_fixes:
    content, _ = replace_once(content, old, new, label)

write_file(path, content)

print('\nPass 8 complete.')

#!/usr/bin/env python3
"""Help pass 9:
- spells.are: 36 See Also additions (aid, haste, fly, frenzy, enhancement group,
  invisibility group, poison/plague/cure group, charm/gate/portal, energy spells,
  elemental damage groups, misc)
- commands.are: 6 See Also additions (REMORT, WHO, COMMANDS, movement, CGOS, GATHER)
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
# spells.are
# =============================================================
print('=== spells.are ===')
path = f'{AREA_DIR}/spells.are'
with open(path, encoding='latin-1') as f:
    content = f.read()

fixes = [
    # AID
    (
        'Mage:15  Cleric:13  Thief:18  Warrior:20  Monk: N/A   Necromancer:N/A\n~',
        'Mage:15  Cleric:13  Thief:18  Warrior:20  Monk: N/A   Necromancer:N/A\n\n'
        'See also: CURE LIGHT, CURE CRITICAL, HEALING\n~',
        'AID: See Also'
    ),
    # HASTE
    (
        'Mage:21  Cleric:25  Thief:27  Warrior:29  Monk: N/A   Necromancer:N/A\n~',
        'Mage:21  Cleric:25  Thief:27  Warrior:29  Monk: N/A   Necromancer:N/A\n\n'
        'See also: SLOW, FRENZY, ENHANCEMENT\n~',
        'HASTE: See Also'
    ),
    # FLY
    (
        'Mage:10  Cleric:11  Thief:12   Warrior:13   Monk: N/A   Necromancer:13\n~',
        'Mage:10  Cleric:11  Thief:12   Warrior:13   Monk: N/A   Necromancer:13\n\n'
        'See also: LEVITATE, PASS DOOR, TRANSPORT\n~',
        'FLY: See Also'
    ),
    # FRENZY
    (
        'Mage:N/A  Cleric:27   Thief:N/A   Warrior:N/A   Monk: N/A   Necromancer:N/A\n~',
        'Mage:N/A  Cleric:27   Thief:N/A   Warrior:N/A   Monk: N/A   Necromancer:N/A\n\n'
        'See also: HASTE, BERSERK, ENHANCEMENT\n~',
        'FRENZY: See Also'
    ),
    # GIANT STRENGTH
    (
        'Mage:11   Cleric:13   Thief:14   Warrior:15   Monk: N/A   Necromancer:N/A\n~',
        'Mage:11   Cleric:13   Thief:14   Warrior:15   Monk: N/A   Necromancer:N/A\n\n'
        'See also: WEAKEN, HASTE, ENHANCEMENT\n~',
        'GIANT STRENGTH: See Also'
    ),
    # WEAKEN
    (
        'Mage:11   Cleric:14   Thief:16   Warrior:17   Monk: N/A   Necromancer:N/A\n~',
        'Mage:11   Cleric:14   Thief:16   Warrior:17   Monk: N/A   Necromancer:N/A\n\n'
        'See also: GIANT STRENGTH, CURSE, MALADICTIONS\n~',
        'WEAKEN: See Also'
    ),
    # INVIS / MASS INVIS
    (
        'Mass invis is for M/M only, with a minimum level of 22.\n~',
        'Mass invis is for M/M only, with a minimum level of 22.\n\n'
        'See also: DETECT INVIS, FAERIE FOG, FAERIE FIRE\n~',
        'INVIS/MASS INVIS: See Also'
    ),
    # FAERIE FIRE
    (
        'Mage:5  Cleric:6  Thief:8  Warrior:8  Monk: N/A   Necromancer:N/A\n~',
        'Mage:5  Cleric:6  Thief:8  Warrior:8  Monk: N/A   Necromancer:N/A\n\n'
        'See also: FAERIE FOG, DETECT INVIS, INVIS\n~',
        'FAERIE FIRE: See Also'
    ),
    # FAERIE FOG
    (
        'Mage:14   Cleric:16   Thief:20   Warrior:18  Monk: N/A   Necromancer:N/A\n~',
        'Mage:14   Cleric:16   Thief:20   Warrior:18  Monk: N/A   Necromancer:N/A\n\n'
        'See also: FAERIE FIRE, DETECT STEALTH, DETECT HIDDEN\n~',
        'FAERIE FOG: See Also'
    ),
    # POISON
    (
        'Mage:17   Cleric:12   Thief:13  Warrior:21   Monk: N/A   Necromancer:N/A\n~',
        'Mage:17   Cleric:12   Thief:13  Warrior:21   Monk: N/A   Necromancer:N/A\n\n'
        'See also: CURE POISON, DETECT POISON, PLAGUE\n~',
        'POISON: See Also'
    ),
    # PLAGUE
    (
        'Mage:23   Cleric:17   Thief:29   Warrior:26   Monk: N/A   Necromancer:N/A\n~',
        'Mage:23   Cleric:17   Thief:29   Warrior:26   Monk: N/A   Necromancer:N/A\n\n'
        'See also: CURE DISEASE, POISON, MALADICTIONS\n~',
        'PLAGUE: See Also'
    ),
    # CURE POISON (has double period in body - unique anchor)
    (
        'as to have been poisoned..\n\n'
        'Minimum level depends on your primary class and is:\n'
        'Mage:15  Cleric:14  Thief:17  Warrior:16  Monk: N/A   Necromancer:N/A\n~',
        'as to have been poisoned..\n\n'
        'Minimum level depends on your primary class and is:\n'
        'Mage:15  Cleric:14  Thief:17  Warrior:16  Monk: N/A   Necromancer:N/A\n\n'
        'See also: POISON, CURE DISEASE, CURATIVE\n~',
        'CURE POISON: See Also'
    ),
    # CURE DISEASE
    (
        'Mage:15  Cleric:13  Thief:18   Warrior:16  Monk: N/A  Necromancer:N/A\n~',
        'Mage:15  Cleric:13  Thief:18   Warrior:16  Monk: N/A  Necromancer:N/A\n\n'
        'See also: PLAGUE, CURE POISON, CURATIVE\n~',
        'CURE DISEASE: See Also'
    ),
    # CURE BLINDNESS
    (
        'Mage:8  Cleric:6  Thief:12  Warrior:10  Monk: N/A   Necromancer:N/A\n~',
        'Mage:8  Cleric:6  Thief:12  Warrior:10  Monk: N/A   Necromancer:N/A\n\n'
        'See also: BLINDNESS, DETECT MAGIC, CURATIVE\n~',
        'CURE BLINDNESS: See Also'
    ),
    # CURE NIGHTMARE
    (
        "gain the curative spellgroup.\n~",
        "gain the curative spellgroup.\n\n"
        'See also: NIGHTMARE, CURATIVE\n~',
        'CURE NIGHTMARE: See Also'
    ),
    # CHARM PERSON
    (
        'Mage:20  Cleric:22  Thief:24  Warrior:26  Monk: N/A   Necromancer:N/A\n~',
        'Mage:20  Cleric:22  Thief:24  Warrior:26  Monk: N/A   Necromancer:N/A\n\n'
        'See also: SUMMON, GATE, BEWITCH\n~',
        'CHARM PERSON: See Also'
    ),
    # GATE / EARTH TRAVEL
    (
        'Earth travel is for necromancers only, with a minimum level of 25.\n~',
        'Earth travel is for necromancers only, with a minimum level of 25.\n\n'
        'See also: PORTAL, SUMMON, TRANSPORT\n~',
        'GATE/EARTH TRAVEL: See Also'
    ),
    # PORTAL
    (
        'Portal is limited to M/M (minimum level 29) and C/C (minimum level 30).\n~',
        'Portal is limited to M/M (minimum level 29) and C/C (minimum level 30).\n\n'
        'See also: GATE, TELEPORT, RECALL, TRANSPORT\n~',
        'PORTAL: See Also'
    ),
    # WORD OF RECALL (has blank line before tilde)
    (
        'useful since the recall skill is free and costs no mana.\n\n~',
        'useful since the recall skill is free and costs no mana.\n\n'
        'See also: RECALL, TELEPORT, PORTAL, TRANSPORT\n~',
        'WORD OF RECALL: See Also'
    ),
    # SUMMON
    (
        'Mage:24   Cleric:12   Thief:29   Warrior:26   Monk: N/A   Necromancer:N/A\n~',
        'Mage:24   Cleric:12   Thief:29   Warrior:26   Monk: N/A   Necromancer:N/A\n\n'
        'See also: GATE, CHARM PERSON, TRANSPORT\n~',
        'SUMMON: See Also'
    ),
    # EARTHQUAKE
    (
        'Mage:14   Cleric:14   Thief:17   Warrior:17   Monk: N/A   Necromancer:N/A\n~',
        'Mage:14   Cleric:14   Thief:17   Warrior:17   Monk: N/A   Necromancer:N/A\n\n'
        'See also: MALADICTIONS, ELEMENTAL, HARMFUL\n~',
        'EARTHQUAKE: See Also'
    ),
    # PROTECTION EVIL / SANCTUARY / MASS SANCTUARY
    (
        'Mass sanctuary is for C/C only with a minimum level of 35.\n~',
        'Mass sanctuary is for C/C only with a minimum level of 35.\n\n'
        'See also: ARMOR, BLESS, PROTECTIVE\n~',
        'PROTECTION EVIL/SANCTUARY: See Also'
    ),
    # REMOVE CURSE
    (
        'Monk: N/A   Necromancer:20\n~',
        'Monk: N/A   Necromancer:20\n\n'
        'See also: CURSE, DISPEL MAGIC, CURATIVE\n~',
        'REMOVE CURSE: See Also'
    ),
    # KNOW ALIGNMENT
    (
        'Mage:12  Cleric:9  Thief:20   Warrior:15   Monk: N/A   Necromancer:N/A\n~',
        'Mage:12  Cleric:9  Thief:20   Warrior:15   Monk: N/A   Necromancer:N/A\n\n'
        'See also: DETECT EVIL, DETECT GOOD, BLESS, CURSE\n~',
        'KNOW ALIGNMENT: See Also'
    ),
    # LOCATE OBJECT
    (
        'Mage:9  Cleric:13  Thief:15   Warrior:18   Monk: N/A   Necromancer:N/A\n~',
        'Mage:9  Cleric:13  Thief:15   Warrior:18   Monk: N/A   Necromancer:N/A\n\n'
        'See also: IDENTIFY, DETECT MAGIC, DETECTION\n~',
        'LOCATE OBJECT: See Also'
    ),
    # INFRAVISION
    (
        'Mage:8  Cleric:10   Thief:13   Warrior:16   Monk: N/A   Necromancer:9\n~',
        'Mage:8  Cleric:10   Thief:13   Warrior:16   Monk: N/A   Necromancer:9\n\n'
        'See also: DETECT HIDDEN, CONTINUAL LIGHT, DETECTION\n~',
        'INFRAVISION: See Also'
    ),
    # ENERGY DRAIN / VAMPIRIC TOUCH
    (
        'Vampiric touch is limited to necromancers, with a minimum level of 15.\n~',
        'Vampiric touch is limited to necromancers, with a minimum level of 15.\n\n'
        'See also: MALADICTIONS, LIFE-UNDEATH\n~',
        'ENERGY DRAIN/VAMPIRIC TOUCH: See Also'
    ),
    # COLD SPELLS group (ends with \n\n~ - blank line before tilde)
    (
        'Mage:24  Cleric:16  Thief:27  Warrior:27  Monk: N/A   Necromancer:21\n\n~',
        'Mage:24  Cleric:16  Thief:27  Warrior:27  Monk: N/A   Necromancer:21\n\n'
        'See also: FIRE SPELLS, ELECTRIC SPELLS, ELEMENTAL\n~',
        'COLD SPELLS group: See Also'
    ),
    # FIRE SPELLS group
    (
        'Mage:23  Cleric:20  Thief:27  Warrior:25   Monk: N/A   Necromancer:N/A\n~',
        'Mage:23  Cleric:20  Thief:27  Warrior:25   Monk: N/A   Necromancer:N/A\n\n'
        'See also: COLD SPELLS, ELECTRIC SPELLS, ELEMENTAL\n~',
        'FIRE SPELLS group: See Also'
    ),
    # ELECTRIC SPELLS group
    (
        'Mage:26  Cleric:26  Thief:30  Warrior:30   Monk: N/A   Necromancer:N/A\n~',
        'Mage:26  Cleric:26  Thief:30  Warrior:30   Monk: N/A   Necromancer:N/A\n\n'
        'See also: FIRE SPELLS, COLD SPELLS, ELEMENTAL\n~',
        'ELECTRIC SPELLS group: See Also'
    ),
    # FIRESHIELD FROSTSHIELD DEATHSHROUD
    (
        'Death shroud is for necromancers only and has a minimum level of 22.\n~',
        'Death shroud is for necromancers only and has a minimum level of 22.\n\n'
        'See also: ARMOR, PROTECTIVE, ENHANCEMENT\n~',
        'FIRESHIELD/FROSTSHIELD: See Also'
    ),
    # LIGHT SPELLS
    (
        'Mage:31   Cleric:31   Thief:46   Warrior:49   Monk: N/A   Necromancer:N/A\n~',
        'Mage:31   Cleric:31   Thief:46   Warrior:49   Monk: N/A   Necromancer:N/A\n\n'
        'See also: CONTINUAL LIGHT, ELEMENTAL, HARMFUL\n~',
        'LIGHT SPELLS: See Also'
    ),
    # WATER SPELLS
    (
        'Geyser is only available to M/M and C/C, with a minimum level of 43.\n~',
        'Geyser is only available to M/M and C/C, with a minimum level of 43.\n\n'
        'See also: FIRE SPELLS, COLD SPELLS, ELEMENTAL\n~',
        'WATER SPELLS: See Also'
    ),
    # WIND SPELLS
    (
        'Mage:40   Cleric:42   Thief:48   Warrior:48   Monk: N/A   Necromancer:44\n~',
        'Mage:40   Cleric:42   Thief:48   Warrior:48   Monk: N/A   Necromancer:44\n\n'
        'See also: ELECTRIC SPELLS, ELEMENTAL, HARMFUL\n~',
        'WIND SPELLS: See Also'
    ),
    # DRACONIAN SPELLS
    (
        'lightning breath - 36\n~',
        'lightning breath - 36\n\n'
        'See also: FIRE SPELLS, COLD SPELLS, ELEMENTAL\n~',
        'DRACONIAN SPELLS: See Also'
    ),
    # ACID BLAST / COLOR SPRAY / MAGIC MISSILE group
    (
        'Mage:1  Cleric:3  Thief:4  Warrior:5  Monk: N/A   Necromancer:N/A\n~',
        'Mage:1  Cleric:3  Thief:4  Warrior:5  Monk: N/A   Necromancer:N/A\n\n'
        'See also: FIRE SPELLS, COLD SPELLS, HARMFUL\n~',
        'ACID BLAST/MAGIC MISSILE group: See Also'
    ),
]

for old, new, label in fixes:
    content, _ = replace_once(content, old, new, label)

write_file(path, content)

# =============================================================
# commands.are: 6 See Also additions
# =============================================================
print('\n=== commands.are ===')
path = f'{AREA_DIR}/commands.are'
with open(path, encoding='latin-1') as f:
    content = f.read()

cmd_fixes = [
    # REMORT
    (
        'Remort history is saved; HELP SCORE shows your remort count.\n~',
        'Remort history is saved; HELP SCORE shows your remort count.\n\n'
        'See also: HERO, HEROLEVELS, GAIN, GROUPS\n~',
        'REMORT: See Also'
    ),
    # WHO WHOIS
    (
        'Classes and races may be abbreviated.\n~',
        'Classes and races may be abbreviated.\n\n'
        'See also: WHERE, FINGER, SCORE\n~',
        'WHO WHOIS: See Also'
    ),
    # COMMANDS (its own syntax entry: short body "shows all commands")
    (
        'COMMANDS shows you all the commands in the game.\n~',
        'COMMANDS shows you all the commands in the game.\n\n'
        'See also: KEYWORDS, HELP, SOCIALS\n~',
        'COMMANDS: See Also'
    ),
    # Directions / Movement
    (
        'abbreviated directions.\n~',
        'abbreviated directions.\n\n'
        'See also: EXITS, OPEN, MOVEMENT\n~',
        'MOVEMENT directions: See Also'
    ),
    # CGOS / CASTLECHAT / CC
    (
        "Type a channel name without a message to turn that channel off.\n~",
        "Type a channel name without a message to turn that channel off.\n\n"
        'See also: CHANNELS, GOSSIP, TELL\n~',
        'CGOS/CC: See Also'
    ),
    # GATHER
    (
        'The third version will gather all objects that have a corresponding\nvnum.\n~',
        'The third version will gather all objects that have a corresponding\nvnum.\n\n'
        'See also: SPLIT, GIVE, GET\n~',
        'GATHER: See Also'
    ),
]

for old, new, label in cmd_fixes:
    content, _ = replace_once(content, old, new, label)

write_file(path, content)

print('\nPass 9 complete.')

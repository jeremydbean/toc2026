#!/usr/bin/env python3
"""
Pass 10 — Add See Also to remaining spells.are entries and toc.are
spell-group/race/misc entries.
"""

import os, sys, tempfile

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
# spells.are — 28 See Also additions
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== spells.are ===")
sp = read_file('spells.are')
ok_count = 0

changes_sp = [
    # ------------------------------------------------------------------
    # Necromancer utility spells
    # ------------------------------------------------------------------
    (
        "GHOSTLY PRESENCE",
        "Ghostly presence is only available to necromancers at level 25 and higher.\n~",
        "Ghostly presence is only available to necromancers at level 25 and higher.\n\nSee also: ANIMATE PARTS, LIFE-UNDEATH, PASS DOOR\n~",
    ),
    (
        "ANIMATE PARTS",
        "This spell is necro only, minimum level 5.\n~",
        "This spell is necro only, minimum level 5.\n\nSee also: BUTCHER, EMBALM, LIFE-UNDEATH\n~",
    ),
    (
        "BEWITCH",
        "Bewitch Weapon is a necromancer only spell and is gainable at level 25.\n~",
        "Bewitch Weapon is a necromancer only spell and is gainable at level 25.\n\nSee also: CURSE, MALADICTIONS, ENCHANTMENT\n~",
    ),
    (
        "BUTCHER",
        "Butcher is a necromancer only spell, useable at Level 10.\n~",
        "Butcher is a necromancer only spell, useable at Level 10.\n\nSee also: ANIMATE PARTS, EMBALM, LIFE-UNDEATH\n~",
    ),
    (
        "EMBALM",
        "Embalm is for necromancers only, with a minimum level of 7.\n~",
        "Embalm is for necromancers only, with a minimum level of 7.\n\nSee also: ANIMATE PARTS, BUTCHER, LIFE-UNDEATH\n~",
    ),
    (
        "CREATE SKELETON/WRAITH/VAMPIRE group",
        "create skeleton - 15\ncreate wraith - 30\ncreate vampire - 45\n~",
        "create skeleton - 15\ncreate wraith - 30\ncreate vampire - 45\n\nSee also: ANIMATE PARTS, BUTCHER, LIFE-UNDEATH\n~",
    ),
    (
        "SKELETAL HANDS",
        "Only Necromancers may use skeletal hands, at a minimum level of 13.\n~",
        "Only Necromancers may use skeletal hands, at a minimum level of 13.\n\nSee also: ANIMATE PARTS, LIFE-UNDEATH, HARMFUL\n~",
    ),
    (
        "TENTACLES",
        "Only necromancers can use tentacles, at a minimum level of 42.\n~",
        "Only necromancers can use tentacles, at a minimum level of 42.\n\nSee also: ANIMATE PARTS, LIFE-UNDEATH, HARMFUL\n~",
    ),
    (
        "TRAP THE SOUL",
        "Only necromancers who have attained hero level may use this spell.\n~",
        "Only necromancers who have attained hero level may use this spell.\n\nSee also: MAZE, ANIMATE PARTS, LIFE-UNDEATH\n~",
    ),
    (
        "EVIL EYE",
        "Evil eye is for necromancers only and has a minimum level of 19.\n~",
        "Evil eye is for necromancers only and has a minimum level of 19.\n\nSee also: BLINDNESS, ENERGY DRAIN, MALADICTIONS\n~",
    ),
    # ------------------------------------------------------------------
    # Mage / Cleric combat spells
    # ------------------------------------------------------------------
    (
        "FORCE SWORD",
        "necromancers with a minimum level of 34.\n~",
        "necromancers with a minimum level of 34.\n\nSee also: POWER GLOVES, ENCHANTMENT, ENHANCEMENT\n~",
    ),
    (
        "POWER GLOVES",
        "The power gloves spell is limited to M/M with a minimum level of 25.\n~",
        "The power gloves spell is limited to M/M with a minimum level of 25.\n\nSee also: FORCE SWORD, GIANT STRENGTH, ENCHANTMENT\n~",
    ),
    (
        "HEAT METAL",
        "Heat metal is only for M/M at level 17 or up and C/C at level 19 and up.\n~",
        "Heat metal is only for M/M at level 17 or up and C/C at level 19 and up.\n\nSee also: FIRE SPELLS, ELEMENTAL, HARMFUL\n~",
    ),
    (
        "SPIRITUAL HAMMER",
        "Mage:21   Cleric:15   Thief:26   Warrior:29   Monk: N/A   Necromancer:N/A\n~",
        "Mage:21   Cleric:15   Thief:26   Warrior:29   Monk: N/A   Necromancer:N/A\n\nSee also: FORCE SWORD, BENEFICIAL, HARMFUL\n~",
    ),
    (
        "HOLY WORD",
        "Mage:35   Cleric:32   Thief:37   Warrior:39   Monk: N/A   Necromancer:N/A\n~",
        "Mage:35   Cleric:32   Thief:37   Warrior:39   Monk: N/A   Necromancer:N/A\n\nSee also: DISPEL EVIL, DIVINE INTERVENTION, BENEDICTIONS\n~",
    ),
    (
        "DIVINE INTERVENTION",
        "This spell is only available to C/C at level 43 and higher.\n~",
        "This spell is only available to C/C at level 43 and higher.\n\nSee also: AID, HOLY WORD, BENEDICTIONS\n~",
    ),
    # ------------------------------------------------------------------
    # Utility / support spells
    # ------------------------------------------------------------------
    (
        "CONTINUAL LIGHT",
        "Mage:5  Cleric:4  Thief:7  Warrior:6  Monk: N/A   Necromancer:N/A\n~",
        "Mage:5  Cleric:4  Thief:7  Warrior:6  Monk: N/A   Necromancer:N/A\n\nSee also: INFRAVISION, LIGHT SPELLS, CREATION\n~",
    ),
    (
        "CONTROL WEATHER",
        "Mage:27  Cleric:28  Thief:32  Warrior:32  Monk: N/A   Necromancer:N/A\n~",
        "Mage:27  Cleric:28  Thief:32  Warrior:32  Monk: N/A   Necromancer:N/A\n\nSee also: WEATHERSPELLS, ELEMENTAL\n~",
    ),
    (
        "CREATE FOOD",
        "Mage:10  Cleric:5  Thief:12  Warrior:11  Monk: N/A   Necromancer:N/A\n~",
        "Mage:10  Cleric:5  Thief:12  Warrior:11  Monk: N/A   Necromancer:N/A\n\nSee also: CREATE WATER, CREATE SPRING, CREATION\n~",
    ),
    (
        "CREATE SPRING",
        "Mage:16  Cleric:14  Thief:20   Warrior:18  Monk: N/A   Necromancer:N/A\n~",
        "Mage:16  Cleric:14  Thief:20   Warrior:18  Monk: N/A   Necromancer:N/A\n\nSee also: CREATE FOOD, CREATE WATER, CREATION\n~",
    ),
    (
        "CREATE WATER",
        "Mage:8  Cleric:3  Thief:11  Warrior:12  Monk: N/A   Necromancer:N/A\n~",
        "Mage:8  Cleric:3  Thief:11  Warrior:12  Monk: N/A   Necromancer:N/A\n\nSee also: CREATE FOOD, CREATE SPRING, CREATION\n~",
    ),
    (
        "MANA CONVERT",
        "Mage:13   Cleric:12   Thief:16   Warrior:16   Monk: N/A   Necromancer:14\n~",
        "Mage:13   Cleric:12   Thief:16   Warrior:16   Monk: N/A   Necromancer:14\n\nSee also: REFRESH, MEDITATION, CREATION\n~",
    ),
    (
        "REFRESH",
        "Mage:6  Cleric:4  Thief:8  Warrior:7  Monk: N/A   Necromancer:N/A\n~",
        "Mage:6  Cleric:4  Thief:8  Warrior:7  Monk: N/A   Necromancer:N/A\n\nSee also: MANA CONVERT, AID, CREATION\n~",
    ),
    (
        "RAISE DEAD",
        "Only C/C of level 31 or higher and necromancers of level 29 or higher can\nraise the dead.\n~",
        "Only C/C of level 31 or higher and necromancers of level 29 or higher can\nraise the dead.\n\nSee also: ANIMATE PARTS, LIFE-UNDEATH, HEALING\n~",
    ),
    (
        "HAVEN/ROPE TRICK",
        "Haven is only available for M/M and C/C with a minimum level of 44.\n~",
        "Haven is only available for M/M and C/C with a minimum level of 44.\n\nSee also: MAZE, PROTECTIVE, TRANSPORT\n~",
    ),
    (
        "MAZE",
        "This spell is available to M/M and C/C with a minimum level of 38.\n~",
        "This spell is available to M/M and C/C with a minimum level of 38.\n\nSee also: HAVEN, TRAP THE SOUL, TRANSPORT\n~",
    ),
    (
        "PASS DOOR",
        "Mage:24   Cleric:22   Thief:28   Warrior:26   Monk: N/A   Necromancer:24\n~",
        "Mage:24   Cleric:22   Thief:28   Warrior:26   Monk: N/A   Necromancer:24\n\nSee also: FLY, TRANSPORT, GHOSTLY PRESENCE\n~",
    ),
    (
        "SLEEPSPELL",
        "Mage:12   Cleric:11   Thief:12   Warrior:14   Monk: N/A   Necromancer:N/A\n~",
        "Mage:12   Cleric:11   Thief:12   Warrior:14   Monk: N/A   Necromancer:N/A\n\nSee also: CHARM PERSON, BEWITCH, MALADICTIONS\n~",
    ),
    # ------------------------------------------------------------------
    # Immortal-only spells (add See Also for context)
    # ------------------------------------------------------------------
    (
        "CHANGE SEX",
        "still active.\n~",
        "still active.\n\nSee also: BENEDICTIONS\n~",
    ),
    (
        "RESTORE MANA",
        "is useful for topping off mana between fights.\n~",
        "is useful for topping off mana between fights.\n\nSee also: MANA CONVERT, MEDITATION\n~",
    ),
    (
        "REMOVE ALIGN",
        "you may blow the object up.\n~",
        "you may blow the object up.\n\nSee also: REMOVE CURSE, ENCHANTMENT\n~",
    ),
]

for label, old, new in changes_sp:
    sp, ok = replace_once(sp, old, new, label)
    if ok:
        ok_count += 1
    else:
        errors += 1

write_file('spells.are', sp)
print(f"  → spells.are: {ok_count}/{len(changes_sp)} applied")

# ─────────────────────────────────────────────────────────────────────────────
# toc.are — spell group entries + race entries + misc
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== toc.are ===")
tc = read_file('toc.are')
ok_count_tc = 0

changes_tc = [
    # ------------------------------------------------------------------
    # Spell group entries — add SPELLGROUP + GAIN cross-refs
    # ------------------------------------------------------------------
    (
        "BEGUILING",
        "Trainer for M/M is Danko. Trainer for ?/M is Creole\n~",
        "Trainer for M/M is Danko. Trainer for ?/M is Creole\n\nSee also: SPELLGROUP, GAIN, MALADICTIONS\n~",
    ),
    (
        "BENEDICTIONS",
        "Trainer for C/C is Tempora.  Trainer for ?/C is Grill.\n~",
        "Trainer for C/C is Tempora.  Trainer for ?/C is Grill.\n\nSee also: SPELLGROUP, GAIN, HEALING\n~",
    ),
    (
        "COMBAT",
        "Trainer for M/M is Flame.  Trainer for ?/M is Kilar.\n~",
        "Trainer for M/M is Flame.  Trainer for ?/M is Kilar.\n\nSee also: SPELLGROUP, GAIN, HARMFUL\n~",
    ),
    (
        "CREATION",
        "members of the cleric guild can gain this.\n\nTrainer is Silius.\n~",
        "members of the cleric guild can gain this.\n\nTrainer is Silius.\n\nSee also: SPELLGROUP, GAIN\n~",
    ),
    (
        "CURATIVE",
        "or mages, and 6 for warriors and thieves.\n\nTrainer is Qualo.\n~",
        "or mages, and 6 for warriors and thieves.\n\nTrainer is Qualo.\n\nSee also: SPELLGROUP, GAIN, HEALING\n~",
    ),
    (
        "DETECTION",
        "Detect Stealth.\n\nCost is 4 for mage, 4 for cleric, 5 for warrior and thief.\n\nTrainers are Silius for ?/C (including C/C)\n\t and Diemos for ?/M (including M/M)\n~",
        "Detect Stealth.\n\nCost is 4 for mage, 4 for cleric, 5 for warrior and thief.\n\nTrainers are Silius for ?/C (including C/C)\n\t and Diemos for ?/M (including M/M)\n\nSee also: SPELLGROUP, GAIN\n~",
    ),
    (
        "DRACONIAN",
        "st level spell in this group is level 34.\n\nTrainer is Drixt.\n~",
        "st level spell in this group is level 34.\n\nTrainer is Drixt.\n\nSee also: SPELLGROUP, GAIN, ELEMENTAL\n~",
    ),
    (
        "ELEMENTAL",
        "ixt for M/M\n\t       Kilar for ?/M\n\t and   Marilith for Necro\n~",
        "ixt for M/M\n\t       Kilar for ?/M\n\t and   Marilith for Necro\n\nSee also: SPELLGROUP, GAIN, DRACONIAN\n~",
    ),
    (
        "ENCHANTMENT",
        "Enchant Armor, Enchant Weapon.\nCost is 5 trains.\n\nTrainer is Danko.\n~",
        "Enchant Armor, Enchant Weapon.\nCost is 5 trains.\n\nTrainer is Danko.\n\nSee also: SPELLGROUP, GAIN\n~",
    ),
    (
        "ENHANCEMENT",
        "Marilith for Necro\n\n~",
        "Marilith for Necro\n\nSee also: SPELLGROUP, GAIN\n\n~",
    ),
    (
        "HARMFUL",
        "Trainer for C/C is Eriak.  Trainer for ?/C is Lunk.\n~",
        "Trainer for C/C is Eriak.  Trainer for ?/C is Lunk.\n\nSee also: SPELLGROUP, GAIN, COMBAT\n~",
    ),
    (
        "HEALING",
        "Trainer for C/C is Dominic.  Trainer for ?/C is Grill.\n~",
        "Trainer for C/C is Dominic.  Trainer for ?/C is Grill.\n\nSee also: SPELLGROUP, GAIN, CURATIVE\n~",
    ),
    (
        "LIFE-UNDEATH",
        "Cost: 7 trains\n\nTrainer is the Soul Trapper.\n~",
        "Cost: 7 trains\n\nTrainer is the Soul Trapper.\n\nSee also: SPELLGROUP, GAIN, ANIMATE PARTS\n~",
    ),
    (
        "MALADICTIONS",
        "Necro Guild Master for Necro\n~",
        "Necro Guild Master for Necro\n\nSee also: SPELLGROUP, GAIN, BEGUILING\n~",
    ),
    (
        "PROTECTIVE",
        "Soul Trapper for Necro\n\n~",
        "Soul Trapper for Necro\n\nSee also: SPELLGROUP, GAIN\n\n~",
    ),
    (
        "TRANSPORT",
        "Undead Spirit for Necro\n~",
        "Undead Spirit for Necro\n\nSee also: SPELLGROUP, GAIN\n~",
    ),
    (
        "WEATHERSPELLS",
        "Mage:14  Cleric:6  Thief:8  Warrior:8\n\nTrainers are Silius for ?/C (including C/C)\n\t and Diemos for ?/M (including M/M)\n~",
        "Mage:14  Cleric:6  Thief:8  Warrior:8\n\nTrainers are Silius for ?/C (including C/C)\n\t and Diemos for ?/M (including M/M)\n\nSee also: SPELLGROUP, GAIN, ELEMENTAL\n~",
    ),
    (
        "ATTACK",
        "Trainer for C/C is Dominic. Trainer for ?/C, Fredar.\n~",
        "Trainer for C/C is Dominic. Trainer for ?/C, Fredar.\n\nSee also: SPELLGROUP, GAIN, COMBAT\n~",
    ),
    # ------------------------------------------------------------------
    # Race entries — link to RACES overview
    # ------------------------------------------------------------------
    (
        "DWARF exp table",
        "Mage:2200  Cleric:2150  Thief:2150  Warrior:2125  Monk:2400\n~",
        "Mage:2200  Cleric:2150  Thief:2150  Warrior:2125  Monk:2400\n\nSee also: RACES, ELF, HUMAN, HOBBIT\n~",
    ),
    (
        "ELF exp table",
        "Mage:2100  Cleric:2125  Thief:2150  Warrior:2200  Necro:2300\n~",
        "Mage:2100  Cleric:2125  Thief:2150  Warrior:2200  Necro:2300\n\nSee also: RACES, DWARF, HUMAN, HOBBIT\n~",
    ),
    (
        "HUMAN exp table",
        "Cleric:2000  Thief:2000  Warrior:2000  Monk:2300  Necro:2000\n~",
        "Cleric:2000  Thief:2000  Warrior:2000  Monk:2300  Necro:2000\n\nSee also: RACES, DWARF, ELF, HOBBIT\n~",
    ),
    (
        "HOBBIT exp table",
        "Mage:2200  Cleric:2150  Thief:2125  Warrior:2150\n~",
        "Mage:2200  Cleric:2150  Thief:2125  Warrior:2150\n\nSee also: RACES, DWARF, ELF, HUMAN\n~",
    ),
    (
        "SAURIAN exp table",
        "Mage:2200  Cleric:2150  Thief:2250  Warrior:2200\n~",
        "Mage:2200  Cleric:2150  Thief:2250  Warrior:2200\n\nSee also: RACES, DWARF, ELF, HUMAN\n~",
    ),
    # ------------------------------------------------------------------
    # Misc important entries
    # ------------------------------------------------------------------
    (
        "COMMANDMENTS intro reference",
        "and your immortal disassociated from one another.\n\n~",
        "and your immortal disassociated from one another.\n\nSee also: IMMORTAL, RULES, WIZLIST\n\n~",
    ),
    (
        "RULES for players",
        "looked on particularly strongly.\n\n\n\n~",
        "looked on particularly strongly.\n\nSee also: COMMANDMENTS, PUNISHED, PKILL\n\n\n\n~",
    ),
    (
        "TAX gold cap",
        "all gold above 1 million coins, each and every time you log on.\n~",
        "all gold above 1 million coins, each and every time you log on.\n\nSee also: BANK, GUILDS\n~",
    ),
    (
        "NEWS entry",
        "nding on their base stat and possible magical\n  enhancement.\n~",
        "nding on their base stat and possible magical\n  enhancement.\n\nSee also: CHANGES, MOTD\n~",
    ),
]

for label, old, new in changes_tc:
    tc, ok = replace_once(tc, old, new, label)
    if ok:
        ok_count_tc += 1
    else:
        errors += 1

write_file('toc.are', tc)
print(f"  → toc.are: {ok_count_tc}/{len(changes_tc)} applied")

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
total_ok = ok_count + ok_count_tc
total_changes = len(changes_sp) + len(changes_tc)
print(f"\nTotal: {total_ok}/{total_changes} OK, {errors} errors")
if errors:
    sys.exit(1)

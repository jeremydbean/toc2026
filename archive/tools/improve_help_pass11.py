#!/usr/bin/env python3
"""
Pass 11 — Add See Also to remaining skills.are entries (psionics + combat/misc)
and remaining toc.are entries (immortal ranks, newbie, credits, misc).
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
# skills.are — 16 psionic entries
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== skills.are (psionics) ===")
sk = read_file('skills.are')
ok_sk = 0

psionics_changes = [
    (
        "PSIONICS overview",
        "TORMENT, and TRANSFUSION.\n~",
        "TORMENT, and TRANSFUSION.\n\nSee also: GAIN, SALIR\n~",
    ),
    (
        "ASTRAL WALK",
        "fewer restrictions are applied to its use.\n\nMinimum level: 25\n~",
        "fewer restrictions are applied to its use.\n\nMinimum level: 25\n\nSee also: PSIONICS, GATE, SHIFT\n~",
    ),
    (
        "CLAIRVOYANCE",
        "the world, what is in the room, and what the room looks\nlike.\n\nMinimum level: 18\n~",
        "the world, what is in the room, and what the room looks\nlike.\n\nMinimum level: 18\n\nSee also: PSIONICS, TORMENT\n~",
    ),
    (
        "CONFUSE",
        "only defend themselves while they try to figure out\nwhy they are being attacked.\n\nMinimum level: 21\n~",
        "only defend themselves while they try to figure out\nwhy they are being attacked.\n\nMinimum level: 21\n\nSee also: PSIONICS, EGO WHIP, TORMENT\n~",
    ),
    (
        "EGO WHIP",
        "makes victims feel less confident about themselves and damages\nblood vessels and synapses in the brain.\n\nMinimum level: 19\n~",
        "makes victims feel less confident about themselves and damages\nblood vessels and synapses in the brain.\n\nMinimum level: 19\n\nSee also: PSIONICS, MINDBLAST, TORMENT\n~",
    ),
    (
        "MINDBAR",
        "he nature of this skill, it is usable only on the\npsionicist.\n\nMinimum level: 22\n~",
        "he nature of this skill, it is usable only on the\npsionicist.\n\nMinimum level: 22\n\nSee also: PSIONICS, PSIONIC ARMOR, PSYCHIC SHIELD\n~",
    ),
    (
        "MINDBLAST",
        "be overwhelmed by mental\nenergies, causing brain hemorrhages.\n\nMinimum level: 23\n~",
        "be overwhelmed by mental\nenergies, causing brain hemorrhages.\n\nMinimum level: 23\n\nSee also: PSIONICS, EGO WHIP, TORMENT\n~",
    ),
    (
        "NIGHTMARE",
        "victims horrifying visions, preventing them from\nsleeping.  It also has adverse affects on magical abilities.\n\nMinimum level: 21\n~",
        "victims horrifying visions, preventing them from\nsleeping.  It also has adverse affects on magical abilities.\n\nMinimum level: 21\n\nSee also: PSIONICS, TORMENT, CONFUSE\n~",
    ),
    (
        "PROJECT",
        "obstructions, such as doors, and are immune to attack.\n\nMinimum level: 19\n~",
        "obstructions, such as doors, and are immune to attack.\n\nMinimum level: 19\n\nSee also: PSIONICS, ASTRAL WALK, SHIFT\n~",
    ),
    (
        "PSIONIC ARMOR",
        "the PROTECTION EVIL spell.  This spell can be cast on\nothers.\n\nMinimum level: 17\n~",
        "the PROTECTION EVIL spell.  This spell can be cast on\nothers.\n\nMinimum level: 17\n\nSee also: PSIONICS, MINDBAR, PSYCHIC SHIELD\n~",
    ),
    (
        "PSYCHIC SHIELD",
        "Psionic Armor,\nbut it affects everyone who is grouped with the user.\n\nMinimum level: 19\n~",
        "Psionic Armor,\nbut it affects everyone who is grouped with the user.\n\nMinimum level: 19\n\nSee also: PSIONICS, PSIONIC ARMOR, MINDBAR\n~",
    ),
    (
        "PYROTECHNICS",
        "the light source, the\nmore damage is inflicted on the victim.\n\nMinimum level: 20\n~",
        "the light source, the\nmore damage is inflicted on the victim.\n\nMinimum level: 20\n\nSee also: PSIONICS, FIRE SPELLS, HARMFUL\n~",
    ),
    (
        "SHIFT",
        "nosummon on, he or she cannot be\nshifted.\n\nMinimum level: 25\n~",
        "nosummon on, he or she cannot be\nshifted.\n\nMinimum level: 25\n\nSee also: PSIONICS, ASTRAL WALK, SUMMON\n~",
    ),
    (
        "TELEKINESIS TK",
        "items scattered about the world to his or her possession.\n\nMinimum level: 21\n~",
        "items scattered about the world to his or her possession.\n\nMinimum level: 21\n\nSee also: PSIONICS, DISARM, STEAL\n~",
    ),
    (
        "TORMENT",
        "experiences from the past,\ncausing real damage to the victim.\n\nMinimum level: 18\n~",
        "experiences from the past,\ncausing real damage to the victim.\n\nMinimum level: 18\n\nSee also: PSIONICS, EGO WHIP, CONFUSE\n~",
    ),
    (
        "TRANSFUSION",
        "sfers physical stamina from the user to the target character.\n\nMinimum level: 28\n~",
        "sfers physical stamina from the user to the target character.\n\nMinimum level: 28\n\nSee also: PSIONICS, AID, FAST HEALING\n~",
    ),
]

for label, old, new in psionics_changes:
    sk, ok = replace_once(sk, old, new, label)
    if ok: ok_sk += 1
    else: errors += 1

# ─────────────────────────────────────────────────────────────────────────────
# skills.are — 28 other entries
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== skills.are (other skills) ===")

other_changes = [
    (
        "AGGROSTAB",
        "necromancers cannot learn aggrostab, since they cannot join the\nthieves' guild.\n~",
        "necromancers cannot learn aggrostab, since they cannot join the\nthieves' guild.\n\nSee also: BACKSTAB, HIDE, STEALTH\n~",
    ),
    (
        "ARCHERY BOW SHOOT",
        "Necromancers cannot learn archery.\n\nTrainer: Rakar (all)\n~",
        "Necromancers cannot learn archery.\n\nTrainer: Rakar (all)\n\nSee also: DUAL WIELD, SECOND ATTACK, FATALITY\n~",
    ),
    (
        "BLINDING FISTS",
        "to use this martial art.\n\nNumber of trains: 3\nTrainer: Master of Movement (Monk)\n~",
        "to use this martial art.\n\nNumber of trains: 3\nTrainer: Master of Movement (Monk)\n\nSee also: FISTS OF FURY, CRANE DANCE, IRON SKIN\n~",
    ),
    (
        "BREW HERBAL BREWING",
        "y have reached level 12.\n\nNumber of trains: 3\nTrainer: Master of Movement (Monk)\n~",
        "y have reached level 12.\n\nNumber of trains: 3\nTrainer: Master of Movement (Monk)\n\nSee also: CONCOCT, SCRIBE, LORE\n~",
    ),
    (
        "CONCOCT",
        "ancers require\n5 trains.\n\nTrainer:  Flame (M/M), Tempora (C/C), Marilith (Necro)\n~",
        "ancers require\n5 trains.\n\nTrainer:  Flame (M/M), Tempora (C/C), Marilith (Necro)\n\nSee also: BREW, SCRIBE, LORE\n~",
    ),
    (
        "CRANE DANCE",
        "nks of level 35 and up.\n\nNumber of trains: 5\nTrainer: Master of Movement (Monk)\n\n~",
        "nks of level 35 and up.\n\nNumber of trains: 5\nTrainer: Master of Movement (Monk)\n\nSee also: BLINDING FISTS, FISTS OF FURY, IRON SKIN\n\n~",
    ),
    (
        "DANGER SENSE",
        "in this skill, since they may not join\nthe warrior guild.\n\nTrainer: Breark (?/W)\n~",
        "in this skill, since they may not join\nthe warrior guild.\n\nTrainer: Breark (?/W)\n\nSee also: DODGE, PARRY, FAST HEALING\n~",
    ),
    (
        "DESPAIR",
        "combat or pursuit.\n\nNumber of trains: 1  (available to all classes at level 25)\n~",
        "combat or pursuit.\n\nNumber of trains: 1  (available to all classes at level 25)\n\nSee also: BERSERK, FATALITY, SECOND ATTACK\n~",
    ),
    (
        "DESTRUCTION",
        "level 25.\n\nNumber of trains needed: 4\nTrainer: Vladamir (W/W)\n~",
        "level 25.\n\nNumber of trains needed: 4\nTrainer: Vladamir (W/W)\n\nSee also: BASH, SMITE, DISARM\n~",
    ),
    (
        "ENHANCED DAMAGE",
        "rs may not learn enhanced damage.\n\nTrainer:  Dolonar (?/W), Silent Master (monk)\n~",
        "rs may not learn enhanced damage.\n\nTrainer:  Dolonar (?/W), Silent Master (monk)\n\nSee also: SECOND ATTACK, THIRD ATTACK, FATALITY\n~",
    ),
    (
        "FISTS OF FURY",
        "s of level 30 and above.\n\nNumber of trains: 4\nTrainer: Master of Movement (Monk)\n~",
        "s of level 30 and above.\n\nNumber of trains: 4\nTrainer: Master of Movement (Monk)\n\nSee also: BLINDING FISTS, CRANE DANCE, STUNNING BLOW\n~",
    ),
    (
        "HAND TO HAND",
        "Silent Master (monk), mud school adept (practice\n         only, no gain)\n~",
        "Silent Master (monk), mud school adept (practice\n         only, no gain)\n\nSee also: DUAL WIELD, SECOND ATTACK, BASH\n~",
    ),
    (
        "IRON SKIN",
        "order to use iron skin.\n\nNumber of trains: 2\nTrainer: Master of Movement (monk)\n~",
        "order to use iron skin.\n\nNumber of trains: 2\nTrainer: Master of Movement (monk)\n\nSee also: BLINDING FISTS, FISTS OF FURY, CRANE DANCE\n~",
    ),
    (
        "LEVITATE",
        "tion needed to levitate.\n\nNumber of trains: 2\nTrainer: Master of Movement (Monk)\n~",
        "tion needed to levitate.\n\nNumber of trains: 2\nTrainer: Master of Movement (Monk)\n\nSee also: FLY, TRANSPORT\n~",
    ),
    (
        "NERVE DAMAGE",
        "must study until level 15\nbefore they can use it.\n\nTrainer: Silent Master (Monk)\n~",
        "must study until level 15\nbefore they can use it.\n\nTrainer: Silent Master (Monk)\n\nSee also: STUNNING BLOW, BLINDING FISTS\n~",
    ),
    (
        "RESCUE",
        "Trainer: Dolonar (?/W), Kalak (W/?), mud school adept (practice only, no gain)\n~",
        "Trainer: Dolonar (?/W), Kalak (W/?), mud school adept (practice only, no gain)\n\nSee also: BASH, SHIELD BLOCK\n~",
    ),
    (
        "SLEIGHT OF HAND",
        "cannot join the\nthief guild.\n\nTrainer: Suma (?/T)\n~",
        "cannot join the\nthief guild.\n\nTrainer: Suma (?/T)\n\nSee also: STEAL, PEEK, PICK LOCK\n~",
    ),
    (
        "STEEL FIST",
        "be used starting at level 25.\n\nNumber of trains: 3\nTrainer: Silent Master (Monk)\n~",
        "be used starting at level 25.\n\nNumber of trains: 3\nTrainer: Silent Master (Monk)\n\nSee also: BLINDING FISTS, FISTS OF FURY, IRON SKIN\n~",
    ),
    (
        "STUNNING BLOW",
        "monks of level 21 or\nabove.\n\nNumber of trains: 3\nTrainer: Silent Master (Monk)\n~",
        "monks of level 21 or\nabove.\n\nNumber of trains: 3\nTrainer: Silent Master (Monk)\n\nSee also: NERVE DAMAGE, BASH, KICK\n~",
    ),
    (
        "HAGGLE HAGGLING",
        "cannot learn haggle, since they cannot join the\nmonk guild.\n\nTrainer: Suma (?/T)\n~",
        "cannot learn haggle, since they cannot join the\nmonk guild.\n\nTrainer: Suma (?/T)\n\nSee also: SLEIGHT OF HAND, SKILLS\n~",
    ),
    (
        "LISTEN AT DOOR",
        "not gain this skill, as they cannot join the\nthief guild.\n\nTrainer: Warder (?/T)\n~",
        "not gain this skill, as they cannot join the\nthief guild.\n\nTrainer: Warder (?/T)\n\nSee also: PEEK, SEARCH, STEALTH\n~",
    ),
    (
        "PICK LOCK",
        "Picky (?/T), Tia (T/?), mud school adept (practice only, no gain)\n~",
        "Picky (?/T), Tia (T/?), mud school adept (practice only, no gain)\n\nSee also: SLEIGHT OF HAND, STEAL, SNEAK\n~",
    ),
    (
        "RIDE RIDING MOUNT DISMOUNT",
        "Number of trains required is 3 for all classes.\nTrainer: Seraloi (any)\n~",
        "Number of trains required is 3 for all classes.\nTrainer: Seraloi (any)\n\nSee also: LEVITATE, FLY\n~",
    ),
    (
        "SCRIBE",
        "ges above level 20 may use this skill.\n\nNumber of trains: 4\nTrainer: Drixt (M/M)\n~",
        "ges above level 20 may use this skill.\n\nNumber of trains: 4\nTrainer: Drixt (M/M)\n\nSee also: BREW, CONCOCT, LORE\n~",
    ),
    (
        "SHOVE",
        "is 1 for W/* and Monk and 2 for all others.\n\nTrainer: Rakar (any), Jazair (any)\n~",
        "is 1 for W/* and Monk and 2 for all others.\n\nTrainer: Rakar (any), Jazair (any)\n\nSee also: BASH, TRIP, KICK\n~",
    ),
    (
        "SMITE",
        "in the process.\n\nNumber of trains needed: 2\nTrainer: Vladamir (W/W)\n~",
        "in the process.\n\nNumber of trains needed: 2\nTrainer: Vladamir (W/W)\n\nSee also: BASH, DESTRUCTION, DISARM\n~",
    ),
    (
        "WANDS STAVES SCROLLS",
        "Soul Trapper (necro), mud school adept (practice\n         only, no gain)\n~",
        "Soul Trapper (necro), mud school adept (practice\n         only, no gain)\n\nSee also: LORE, BREW, CONCOCT\n~",
    ),
    (
        "RECALL /",
        "curse may not recall at all.\n\nTrainer: mud school adept, Fingers (any)\n~",
        "curse may not recall at all.\n\nTrainer: mud school adept, Fingers (any)\n\nSee also: WORD OF RECALL, SUMMON, TRANSPORT\n~",
    ),
]

for label, old, new in other_changes:
    sk, ok = replace_once(sk, old, new, label)
    if ok: ok_sk += 1
    else: errors += 1

write_file('skills.are', sk)
print(f"  → skills.are: {ok_sk}/{len(psionics_changes) + len(other_changes)} applied")

# ─────────────────────────────────────────────────────────────────────────────
# toc.are — 24 remaining entries
# ─────────────────────────────────────────────────────────────────────────────
print("\n=== toc.are ===")
tc = read_file('toc.are')
ok_tc = 0

toc_changes = [
    # ------------------------------------------------------------------
    # Newbie / introduction entries
    # ------------------------------------------------------------------
    (
        "WIZLIST art",
        "d|_|b_T     Killuminati  T_d|_|b\n                       *------------------*\n~",
        "d|_|b_T     Killuminati  T_d|_|b\n                       *------------------*\n\nSee also: GODS, DEMIGODS, IMMORTAL\n~",
    ),
    (
        "NEWBIE INFO blob",
        "n't try to kill the blob in mudschool.\n\nTo see a lot more useful information, type: help beginners\n~",
        "n't try to kill the blob in mudschool.\n\nTo see a lot more useful information, type: help beginners\n\nSee also: BEGINNERS, RULES, GREETING\n~",
    ),
    (
        "BEGINNERS npcs",
        "And that's it. Remember, this is only a game and we are all here to have FUN!\n\nEnjoy...\n~",
        "And that's it. Remember, this is only a game and we are all here to have FUN!\n\nEnjoy...\n\nSee also: NEWBIE INFO, HELP, RULES\n~",
    ),
    (
        "MOTD imps sign-off",
        "enjoy the game!\n\n- The Imps -\n\nPlease type HELP RULES, ignorance of the rules is not an excuse.\n\n\n\n~",
        "enjoy the game!\n\n- The Imps -\n\nPlease type HELP RULES, ignorance of the rules is not an excuse.\n\nSee also: NEWS, IMOTD, CHANGES\n\n\n\n~",
    ),
    # ------------------------------------------------------------------
    # Immortal-only entries
    # ------------------------------------------------------------------
    (
        "IMOTD continue prompt",
        "Do not use immortal powers to benefit your own mortal characters.\n\n[Hit Return to continue]\n~",
        "Do not use immortal powers to benefit your own mortal characters.\n\n[Hit Return to continue]\n\nSee also: MOTD, JOBS, COMMANDMENTS\n~",
    ),
    (
        "JOBS commandments ref",
        "to be read by all immortals is: help commandments.\n~",
        "to be read by all immortals is: help commandments.\n\nSee also: IMOTD, COMMANDMENTS, MARTYR\n~",
    ),
    (
        "MARTYR special status",
        "the game in the past, and the above does not entirely apply to them.\n~",
        "the game in the past, and the above does not entirely apply to them.\n\nSee also: JOBS, IMMORTAL, COMMANDMENTS\n~",
    ),
    (
        "IMMORTAL quests info",
        "Read the help file 'Quests' for more information.\n~",
        "Read the help file 'Quests' for more information.\n\nSee also: AVATAR, COMMANDMENTS, JOBS\n~",
    ),
    (
        "AVATAR game interesting",
        "Having quests livens up the game and is a very important\npart of making the game interesting.\n~",
        "Having quests livens up the game and is a very important\npart of making the game interesting.\n\nSee also: IMMORTAL, ANGEL, COMMANDMENTS\n~",
    ),
    (
        "ANGEL assist quests",
        "are obligated to assist other immortals running them.  Read the help on\nquests.\n~",
        "are obligated to assist other immortals running them.  Read the help on\nquests.\n\nSee also: AVATAR, ARCHANGEL, COMMANDMENTS\n~",
    ),
    (
        "ARCHANGEL mobs check",
        "Check stats on mobs to see if they are correct, in your opinion, or if\nsomething needs changing.\n~",
        "Check stats on mobs to see if they are correct, in your opinion, or if\nsomething needs changing.\n\nSee also: ANGEL, DEMIGODS, COMMANDMENTS\n~",
    ),
    (
        "DEMIGODS jailed note",
        "Make sure you leave a note concerning the incident.\n~",
        "Make sure you leave a note concerning the incident.\n\nSee also: ARCHANGEL, DEITY, COMMANDMENTS\n~",
    ),
    (
        "DEITY level range",
        "object is known to be in that level range.\n~",
        "object is known to be in that level range.\n\nSee also: DEMIGODS, GODS, COMMANDMENTS\n~",
    ),
    (
        "GODS performance ideas",
        "To come up with new ideas for the game, or ideas to help speed up game\nperformance I guess.\n~",
        "To come up with new ideas for the game, or ideas to help speed up game\nperformance I guess.\n\nSee also: DEITY, WIZLIST, COMMANDMENTS\n~",
    ),
    (
        "HERBIE ANGEL rely",
        "He's not something to be relied on though.\n~",
        "He's not something to be relied on though.\n\nSee also: HEAL, GODS\n~",
    ),
    (
        "PUNISHED dashes",
        "        Punishment\n==============================================================================\n\n~",
        "        Punishment\n==============================================================================\n\nSee also: COMMANDMENTS, RULES\n\n~",
    ),
    # ------------------------------------------------------------------
    # Informational / credits entries
    # ------------------------------------------------------------------
    (
        "LYCANTHROPY no cure",
        "have no worries about death. There is currently no known cure for this\ndisease.\n~",
        "have no worries about death. There is currently no known cure for this\ndisease.\n\nSee also: RACES, DEATH\n~",
    ),
    (
        "WEB connection info",
        "Connect with any MUD client, or via telnet:\n  telnet toc.jeremybean.com 9000\n~",
        "Connect with any MUD client, or via telnet:\n  telnet toc.jeremybean.com 9000\n\nSee also: HELP, NEWS\n~",
    ),
    (
        "CHANGES check news",
        "\nCheck help news.\n~",
        "\nCheck help news.\n\nSee also: NEWS, MOTD\n~",
    ),
    (
        "DIKU University",
        "Developed at: DIKU -- The Department of Computer Science\n\t\t      at the University of Copenhagen.\n\n~",
        "Developed at: DIKU -- The Department of Computer Science\n\t\t      at the University of Copenhagen.\n\nSee also: MERC, ROM\n\n~",
    ),
    (
        "MERC share and enjoy",
        "hours of enjoyment.\n\nShare and enjoy.\n~",
        "hours of enjoyment.\n\nShare and enjoy.\n\nSee also: DIKU, ROM\n~",
    ),
    (
        "ROM hair-pulling",
        "hair-pulling. Hope you enjoy it.\n\n(my apologies if anyone was forgotten in this list)\n~",
        "hair-pulling. Hope you enjoy it.\n\n(my apologies if anyone was forgotten in this list)\n\nSee also: DIKU, MERC\n~",
    ),
    (
        "DOORBASH minimum level",
        "The minimum level to use this skill is 10.\n\nNumber of trains needed: 1\nTrainer: Vladamir (W/W)\n\n~",
        "The minimum level to use this skill is 10.\n\nNumber of trains needed: 1\nTrainer: Vladamir (W/W)\n\nSee also: BASH, TRIP, SKILLS\n\n~",
    ),
]

for label, old, new in toc_changes:
    tc, ok = replace_once(tc, old, new, label)
    if ok: ok_tc += 1
    else: errors += 1

write_file('toc.are', tc)
print(f"  → toc.are: {ok_tc}/{len(toc_changes)} applied")

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
total_ok = ok_sk + ok_tc
total = len(psionics_changes) + len(other_changes) + len(toc_changes)
print(f"\nTotal: {total_ok}/{total} OK, {errors} errors")
if errors:
    sys.exit(1)

#!/usr/bin/env python3
"""
Help improvement pass 3: expand thin entries, fix stubs, correct the damage
table, and improve spells/skills descriptions across toc.are, spells.are, and
skills.are.

Run from the repo root:  python3 improve_help_pass3.py
"""

import os
import sys
import tempfile

AREA_DIR = "area"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load(path):
    with open(path, encoding="latin-1") as f:
        return f.read()

def save(path, text):
    """Write atomically via a temp file then rename."""
    dir_ = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=dir_ or ".", prefix=".helptmp_")
    try:
        with os.fdopen(fd, "w", encoding="latin-1") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise

def replace_once(text, old, new, label):
    """Replace exactly one occurrence of old with new; die loudly if ambiguous."""
    count = text.count(old)
    if count == 0:
        print(f"  ERROR [{label}]: pattern not found - skipping")
        return text, False
    if count > 1:
        print(f"  ERROR [{label}]: pattern found {count} times - skipping")
        return text, False
    print(f"  OK    [{label}]")
    return text.replace(old, new, 1), True


# ---------------------------------------------------------------------------
# toc.are changes
# ---------------------------------------------------------------------------

def fix_toc(content):
    changes = 0

    # 1 ── DAMAGE table: add correct verb decorations matching fight.c
    old, new = (
        "0 DAMAGE~\n"
        "When one character attacks another, the severity of the damage is shown in the\n"
        "verb used in the damage message.  Here are all the damage verbs listed from\n"
        "least damage to most damage:\n"
        "\n"
        "    miss        wound           MUTILATE        DEMOLISH\n"
        "    scratch     maul            DISEMBOWEL      DEVASTATE\n"
        "    graze       decimate        DISMEMBER       DESTROY\n"
        "    hit         devastate       MASSACRE        OBLITERATE\n"
        "    injure      maim            MANGLE          ERADICATE\n"
        "\t\t\t\t\tANNIHILATE\n"
        "\n"
        "And, at the far reaches of damaging power, you can do UNSPEAKABLE things.\n"
        "~",

        "0 DAMAGE~\n"
        "When one character attacks another, the severity of the damage is shown in the\n"
        "verb used in the damage message.  Listed from least damage to most damage:\n"
        "\n"
        "    miss          wound          MUTILATE       *** DEMOLISH ***\n"
        "    scratch       maul           DISEMBOWEL     *** DEVASTATE ***\n"
        "    graze         decimate       DISMEMBER      ^^^ DESTROY ^^^\n"
        "    hit           devastate      MASSACRE       === OBLITERATE ===\n"
        "    injure        maim           MANGLE         <<< ERADICATE >>>\n"
        "                                                >>> ANNIHILATE <<<\n"
        "\n"
        "    At the far reaches of damaging power: \"do UNSPEAKABLE things to\"\n"
        "~"
    )
    content, ok = replace_once(content, old, new, "toc DAMAGE table")
    changes += ok

    # 2 ── IMOTD: expand from near-empty to useful immortal orientation
    old, new = (
        "62 IMOTD~\n"
        "Welcome Immortal!\n"
        "\n"
        "\n"
        "\n"
        "~",

        "62 IMOTD~\n"
        "Welcome Immortal!\n"
        "\n"
        "Essential reading for new immortals:\n"
        "  help COMMANDMENTS  - rules governing all immortal conduct\n"
        "  help JOBS          - duties and responsibilities by immortal level\n"
        "  help QUESTS        - guidelines for running player quests\n"
        "\n"
        "Communication:\n"
        "  wiznet             - immortal broadcast channel (on by default)\n"
        "  wizinfo            - send a message to all immortals\n"
        "\n"
        "Remember: your duty is to serve and improve gameplay for mortals.\n"
        "Do not use immortal powers to benefit your own mortal characters.\n"
        "\n"
        "[Hit Return to continue]\n"
        "~"
    )
    content, ok = replace_once(content, old, new, "toc IMOTD expand")
    changes += ok

    # 3 ── QUESTS (level 62): replace useless stub with quest guidelines
    old, new = (
        "62 QUESTS~\n"
        "Sorry not in yet.\n"
        "~",

        "62 QUESTS~\n"
        "The following guidelines apply to all quests run by immortals on ToC:\n"
        "\n"
        "  - Quests should be fun and accessible to the target audience.\n"
        "  - Prize items must not be dramatically overpowered for their level.\n"
        "    Do not load an item more than 4 levels below its normal level\n"
        "    (e.g. level 5 ogre gauntlets are prohibited).\n"
        "  - Larger prizes require greater group effort or problem-solving.\n"
        "  - Announce quest start on the INFO channel so all players may attend.\n"
        "  - Have at least 10 interested players before beginning a quest.\n"
        "  - Do not use reboot as a reset mechanism mid-quest.\n"
        "  - Leave a note summarising the quest and prizes awarded.\n"
        "\n"
        "See also: HEROQUEST, COMMANDMENTS, JOBS\n"
        "~"
    )
    content, ok = replace_once(content, old, new, "toc QUESTS expand")
    changes += ok

    # 4 ── HEROLEVELS (level 51): replace dead stub with actual info
    old, new = (
        "51 HEROLEVELS~\n"
        "See help on exchange. More help on herolevels will be added later.\n"
        "~",

        "51 HEROLEVELS~\n"
        "Hero status is reached when a character attains level 51.  At that point\n"
        "normal experience leveling stops; experience is accumulated for other uses.\n"
        "\n"
        "The primary use of accumulated hero experience is exchanging it for\n"
        "additional practice sessions.  Each exchange costs 5,000 experience points\n"
        "and grants between 4 and 6 practices at random.  Exchanges must be made\n"
        "with the guru located in Hero Hall.\n"
        "\n"
        "Heroes may also embark on special quests through the Questmaster to earn\n"
        "additional rewards.  See HELP HEROQUEST for full details.\n"
        "\n"
        "See also: EXCHANGE, PRACTICE, HEROQUEST, GAIN\n"
        "~"
    )
    content, ok = replace_once(content, old, new, "toc HEROLEVELS expand")
    changes += ok

    # 5 ── WEB: replace "REMOVED" with useful server address
    old, new = (
        "-1 WEB~\n"
        "REMOVED\n"
        "~",

        "-1 WEB~\n"
        "Times of Chaos is hosted at toc.jeremybean.com on port 9000.\n"
        "\n"
        "Connect with any MUD client, or via telnet:\n"
        "  telnet toc.jeremybean.com 9000\n"
        "~"
    )
    content, ok = replace_once(content, old, new, "toc WEB update")
    changes += ok

    # 6 ── STORY: remove dead web-page reference
    old, new = (
        "-1 STORY~\n"
        "The story of ToC is told in the diaries of Judicandus Bramsheer.  See\n"
        "the Aaron's Time of Chaos Web page (see help WEB for address) to read them.\n"
        "~",

        "-1 STORY~\n"
        "The story of ToC revolves around the diaries of Judicandus Bramsheer,\n"
        "a scholar who chronicled the tumultuous Times of Chaos that shaped this\n"
        "world's history.  Read room descriptions carefully as you explore -- many\n"
        "areas contain fragments of this history woven into their descriptions.\n"
        "\n"
        "See also: WEB, DIKU, MERC, ROM\n"
        "~"
    )
    content, ok = replace_once(content, old, new, "toc STORY update")
    changes += ok

    print(f"  toc.are: {changes} change(s) applied")
    return content


# ---------------------------------------------------------------------------
# spells.are changes
# ---------------------------------------------------------------------------

def fix_spells(content):
    changes = 0

    # 7 ── BLINDNESS: describe what blindness actually does to the victim
    old, new = (
        "0 BLINDNESS~\n"
        "Syntax: cast blindness <victim>\n"
        "\n"
        "This spell renders the target character blind.\n"
        "\n"
        "Minimum level depends on your primary class and is:\n"
        "Mage:10  Cleric:8  Thief:15  Warrior:13  Monk: N/A   Necromancer:N/A\n"
        "~",

        "0 BLINDNESS~\n"
        "Syntax: cast blindness <victim>\n"
        "\n"
        "This spell renders the target blind.  A blinded character cannot read room\n"
        "descriptions, see the contents of containers, or clearly make out other\n"
        "characters and objects.  Combat accuracy is significantly penalised.\n"
        "The effect wears off naturally after a short time, or can be removed\n"
        "immediately with the CURE BLINDNESS spell.\n"
        "\n"
        "Minimum level depends on your primary class and is:\n"
        "Mage:10  Cleric:8  Thief:15  Warrior:13  Monk: N/A   Necromancer:N/A\n"
        "\n"
        "See also: CURE BLINDNESS, DIRT KICKING\n"
        "~"
    )
    content, ok = replace_once(content, old, new, "spells BLINDNESS expand")
    changes += ok

    # 8 ── DEMONFIRE: add damage type and attack context
    old, new = (
        "0 'DEMONFIRE'~\n"
        "Syntax: cast demonfire <target>\n"
        "\n"
        "This spell calls the fires of hell to strike down your opponent. This\n"
        "spell is very very evil and should be used sparingly.\n"
        "\n"
        "Minimum level depends on your primary class and is:\n"
        "Mage:36   Cleric:34   Thief:39   Warrior:37   Monk: N/A   Necromancer:N/A\n"
        "~",

        "0 'DEMONFIRE'~\n"
        "Syntax: cast 'demonfire' <target>\n"
        "\n"
        "This spell calls the fires of hell to strike down a single opponent.\n"
        "Demonfire inflicts unholy (negative-energy) damage, making it especially\n"
        "potent against good-aligned creatures.  It is one of the primary offensive\n"
        "spells available to full clerics through the ATTACK spell group.\n"
        "\n"
        "Minimum level depends on your primary class and is:\n"
        "Mage:36   Cleric:34   Thief:39   Warrior:37   Monk: N/A   Necromancer:N/A\n"
        "\n"
        "See also: DISPEL EVIL, DISPEL GOOD, ATTACK, HARMFUL\n"
        "~"
    )
    content, ok = replace_once(content, old, new, "spells DEMONFIRE expand")
    changes += ok

    # 9 ── CALM: add note about uses and PvP implications
    old, new = (
        "0 CALM~\n"
        "Syntax: cast calm\n"
        "\n"
        "This is a powerful spell, which can be used to stop all fighting in the\n"
        "room.\n"
        "\n"
        "Minimum level depends on your primary class and is:\n"
        "Mage:22  Cleric:20  Thief:28  Warrior:30  Monk: N/A   Necromancer:N/A\n"
        "~",

        "0 CALM~\n"
        "Syntax: cast calm\n"
        "\n"
        "This powerful spell arrests all combat in the room, forcing every fighting\n"
        "character to cease attacking.  It is useful for breaking up dangerous mob\n"
        "battles or preventing accidental group-wide aggression.  Characters may\n"
        "resume fighting after the effect wears off.  Calm does not prevent\n"
        "characters from re-initiating combat immediately.\n"
        "\n"
        "Minimum level depends on your primary class and is:\n"
        "Mage:22  Cleric:20  Thief:28  Warrior:30  Monk: N/A   Necromancer:N/A\n"
        "\n"
        "See also: BENEDICTIONS, BLESS, FRENZY\n"
        "~"
    )
    content, ok = replace_once(content, old, new, "spells CALM expand")
    changes += ok

    # 10 ── DISPEL MAGIC: fix grammar ("is considering" -> "is considered")
    #        and fix capitalisation of "Notable" mid-sentence
    old, new = (
        "has a reduced chance of working and is considering an attack spell.  Neutrality\n",
        "has a reduced chance of working and is considered an attack spell.  Neutrality\n"
    )
    content, ok = replace_once(content, old, new, "spells DISPEL MAGIC grammar fix")
    changes += ok

    old, new = (
        "be dispelled, Notable examples are poison and plague.\n",
        "be dispelled; notable examples are poison and plague.\n"
    )
    content, ok = replace_once(content, old, new, "spells DISPEL MAGIC punctuation fix")
    changes += ok

    # 11 ── SLEEPSPELL: fix confusing "see REST" note
    old, new = (
        "This spell puts its victim to sleep.\n"
        "\n"
        "For help on the sleep command, see REST.\n",
        "This spell puts its victim to sleep.  A sleeping character cannot act\n"
        "and will not wake until disturbed or until the spell expires.\n"
        "\n"
        "Note: typing 'sleep' without casting puts your own character to sleep.\n"
        "For help on the rest/sleep/stand commands, see HELP REST or HELP SLEEP.\n"
    )
    content, ok = replace_once(content, old, new, "spells SLEEPSPELL clarify")
    changes += ok

    # 12 ── TELEPORT: fix syntax line (missing quotes around teleport)
    old, new = (
        "Syntax: cast <teleport>\n",
        "Syntax: cast teleport\n"
    )
    content, ok = replace_once(content, old, new, "spells TELEPORT syntax fix")
    changes += ok

    # 13 ── STINKING CLOUD: replace placeholder with real description
    old, new = (
        "62 'STINKING CLOUD'~\n"
        "\n"
        "This is a placeholder for help on stinking cloud.\n"
        "~",

        "62 'STINKING CLOUD'~\n"
        "Syntax: cast 'stinking cloud'\n"
        "\n"
        "This earth magic calls forth noxious fumes from the ground, filling the\n"
        "entire room with a poisonous cloud.  All other characters in the room\n"
        "suffer continuous damage and a reduction to their hit rolls for as long\n"
        "as they remain.  The cloud lingers for a short time before dissipating.\n"
        "\n"
        "Stinking cloud is currently restricted to immortal use (level 62 minimum).\n"
        "~"
    )
    content, ok = replace_once(content, old, new, "spells STINKING CLOUD expand")
    changes += ok

    # 14 ── SLOW: expand thin description
    old, new = (
        "0 SLOW~\n"
        "Syntax: cast 'slow' <victim>\n"
        "\n"
        "This spell will slow down the targeted victim.\n"
        "\n"
        "Minimum level depends on your primary class and is:\n"
        "Mage:21   Cleric:29   Thief:26   Warrior:29   Monk: N/A   Necromancer:N/A\n"
        "~",

        "0 SLOW~\n"
        "Syntax: cast 'slow' <victim>\n"
        "\n"
        "This spell reduces the movement and attack speed of the targeted victim.\n"
        "Slowed characters attack less frequently and lose some of their natural\n"
        "dodging ability.  Slow is the direct counter to the HASTE spell; casting\n"
        "slow on a hasted target will cancel the haste effect.\n"
        "\n"
        "Minimum level depends on your primary class and is:\n"
        "Mage:21   Cleric:29   Thief:26   Warrior:29   Monk: N/A   Necromancer:N/A\n"
        "\n"
        "See also: HASTE, ENHANCEMENT, MALADICTIONS\n"
        "~"
    )
    content, ok = replace_once(content, old, new, "spells SLOW expand")
    changes += ok

    print(f"  spells.are: {changes} change(s) applied")
    return content


# ---------------------------------------------------------------------------
# skills.are changes
# ---------------------------------------------------------------------------

def fix_skills(content):
    changes = 0

    # 15 ── DESPAIR: replace stub with real description (passive combat skill)
    old, new = (
        "25 DESPAIR~\n"
        "\n"
        "no help available yet\n"
        "~",

        "25 DESPAIR~\n"
        "Despair is a passive combat skill available at level 25.  When a character\n"
        "with this skill is actively hunting or fighting an opponent, there is a\n"
        "chance that the opponent will be overcome by a wave of hopelessness and\n"
        "flee the battle involuntarily.  The trigger chance scales with skill level.\n"
        "\n"
        "This skill cannot be activated manually; it fires automatically during\n"
        "combat or pursuit.\n"
        "\n"
        "Number of trains: 1  (available to all classes at level 25)\n"
        "~"
    )
    content, ok = replace_once(content, old, new, "skills DESPAIR expand")
    changes += ok

    # 16 ── PHASE: replace stub with real description (passive stealth-on-move)
    old, new = (
        "25 PHASE~\n"
        "\n"
        "no help available yet\n"
        "~",

        "25 PHASE~\n"
        "Phase is a passive movement skill available at level 25.  When moving from\n"
        "room to room, a character with the phase skill has a chance to automatically\n"
        "enter stealth upon arrival, vanishing from sight in the new room.  The\n"
        "chance of phasing successfully improves with skill level.\n"
        "\n"
        "This skill triggers automatically on movement; no command is required.\n"
        "\n"
        "Number of trains: 1  (available to all classes at level 25)\n"
        "\n"
        "See also: STEALTH, SNEAK, HIDE\n"
        "~"
    )
    content, ok = replace_once(content, old, new, "skills PHASE expand")
    changes += ok

    print(f"  skills.are: {changes} change(s) applied")
    return content


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    files = [
        ("toc.are",    fix_toc),
        ("spells.are", fix_spells),
        ("skills.are", fix_skills),
    ]

    for fname, fixer in files:
        path = os.path.join(AREA_DIR, fname)
        print(f"\nProcessing {fname} ...")
        content = load(path)
        new_content = fixer(content)
        if new_content != content:
            save(path, new_content)
            print(f"  Saved.")
        else:
            print(f"  No changes written (all edits may have been skipped).")

    print("\nDone.")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()

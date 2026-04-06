#!/usr/bin/env python3
"""Fix in-game help files:
 - Remove duplicates from help.are (CAST, PROMPT, NORTH/SOUTH, ! entries)
 - Split combined multi-command entries in commands.are
 - Add See Also cross-references to entries that are missing them
"""

import os
import re

AREA_DIR = "/Users/jeremybean/toc2026-1/area"
HELP_FILE = os.path.join(AREA_DIR, "help.are")
CMD_FILE  = os.path.join(AREA_DIR, "commands.are")

warnings = []
applied  = []

def read_file(path):
    with open(path, encoding='latin-1') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w', encoding='latin-1', newline='\n') as f:
        f.write(content)

def rep(content, old, new, label, path):
    """Replace old with new exactly once; log warnings if not found."""
    if old not in content:
        warnings.append(f"NOT FOUND in {os.path.basename(path)}: {label}")
        return content
    count = content.count(old)
    if count > 1:
        warnings.append(f"FOUND {count}x in {os.path.basename(path)}: {label} — replacing first only")
    applied.append(label)
    return content.replace(old, new, 1)

# ============================================================
# help.are — remove entries that duplicate commands.are
# ============================================================
h = read_file(HELP_FILE)

# 1. Remove ! entry (identical copy in commands.are)
h = rep(h,
"""0 !~
Syntax: !

! repeats the last command you typed.
~""",
"", "! duplicate in help.are", HELP_FILE)

# 2. Remove NORTH SOUTH EAST WEST UP DOWN entry (superseded by commands.are)
h = rep(h,
"""0 NORTH SOUTH EAST WEST UP DOWN~
Syntax: north
Syntax: south
Syntax: east
Syntax: west
Syntax: up
Syntax: down

Use these commands to walk in a particular direction.
~""",
"", "NORTH SOUTH direction duplicate in help.are", HELP_FILE)

# 3. Remove CAST entry (same text exists in commands.are)
h = rep(h,
"""0 CAST~
Syntax: cast <spell> <target>

Before you can cast a spell, you have to practice it.  The more you practice,
the higher chance you have of success when casting.  Casting spells costs mana.
The mana cost decreases as your level increases.

The <target> is optional.  Many spells which need targets will use an
appropriate default target, especially during combat.

If the spell name is more than one word, then you must quote the spell name.
Example: cast 'cure critic' frag.  Quoting is optional for single-word spells.
You can abbreviate the spell name.

When you cast an offensive spell, the victim usually gets a saving throw.
The effect of the spell is reduced or eliminated if the victim makes the
saving throw successfully.

See also the help sections for individual spells.
~""",
"", "CAST duplicate in help.are", HELP_FILE)

# 4. Remove old PROMPT entry — commands.are has a better one
h = rep(h,
"""-1 PROMPT~
Syntax: prompt
Syntax: prompt all
Syntax: prompt <%*>

PROMPT with out an argument will turn your prompt on or off.

PROMPT ALL will give you the standard "<hits mana moves>" prompt.

PROMPT <%*> where the %* are the various variables you may set yourself.

        %h :  Display your current hits
        %H :  Display your maximum hits
        %m :  Display your current mana
        %M :  Display your maximum mana
        %v :  Display your current moves
        %V :  Display your maximum moves
        %x :  Display your current experience
        %X :  Display experience to level
        %g :  Display your gold held
        %a :  Display your alignment
        %R :  Display the vnum you are in (IMMORTAL ONLY)
        %z :  Display the area name you are in (IMMORTAL ONLY)

Example:  PROMPT <%hhp %mm %vmv>
        Will set your prompt to "<10hp 100m 100mv>"
~""",
"", "PROMPT duplicate in help.are", HELP_FILE)

write_file(HELP_FILE, h)
print("help.are written.")

# ============================================================
# commands.are — all splits + See Also additions
# ============================================================
c = read_file(CMD_FILE)

# -------------------------------------------------------
# 1. ENTER RIDE MOUNT  →  ENTER  +  RIDE MOUNT
# -------------------------------------------------------
c = rep(c,
"""0 ENTER RIDE MOUNT~
Syntax: enter
Syntax: ride <mount> / mount <mount>

ENTER uses a room's default portal or structure entrance when no explicit
exit keyword is given.  It is often used for doors, wagons, boats, or other
special entries that do not map cleanly to the six main directions.

RIDE and MOUNT allow you to climb onto a valid mountable creature or
vehicle.  While mounted you move with your mount and benefit from its speed;
use DISMOUNT to climb off.  Some areas restrict mounted travel.
~""",
"""0 ENTER~
Syntax: enter

ENTER steps into a portal, vehicle, or structure that does not map to a
standard directional exit.  Use it for magic gates, wagons, boats, and any
special entry point described in the room.  Look for keywords such as
"portal", "gate", "boat", or "door" to identify what you can enter.

See also: RIDE, MOUNT, RECALL
~

0 RIDE MOUNT~
Syntax: ride <mount>
Syntax: mount <mount>

RIDE and MOUNT climb onto a mountable creature or vehicle.  Only mobs with
the MOUNTABLE flag can be ridden.  While mounted you move with your mount
and benefit from reduced movement costs.  Some areas restrict mounted
travel.  Use DISMOUNT to climb off.

See also: ENTER, DISMOUNT
~""",
"ENTER RIDE MOUNT split", CMD_FILE)

# -------------------------------------------------------
# 2. TELEKINESIS TK CLAIRVOYANCE DANGER PROJECT SHIFT  →  5 entries
# -------------------------------------------------------
c = rep(c,
"""0 TELEKINESIS TK CLAIRVOYANCE DANGER PROJECT SHIFT~
Syntax: telekinesis <target>
Syntax: tk <target>
Syntax: clairvoyance
Syntax: danger
Syntax: project <direction>
Syntax: shift <player>

Psionic utility commands:
- TELEKINESIS/TK attempts to move or lift a target with mental force.  It
  requires psionic training and enough mana to succeed.
- CLAIRVOYANCE briefly lets you scry your surroundings for concealed exits or
  threats without moving.
- DANGER (Danger Sense) gives you a quick pulse of awareness about nearby
  threats, warning you if a room or foe is particularly perilous.
- PROJECT sends your spirit one room at a time in the chosen direction,
  letting you scout ahead while your body stays behind.  Running out of
  control or mana will snap you back to your body.
- SHIFT teleports you directly to another player if the destination and your
  current room permit travel; many safe or special rooms block shifting.
~""",
"""0 TELEKINESIS TK~
Syntax: telekinesis <target>
Syntax: tk <target>

TELEKINESIS (TK) attempts to move or lift a distant target using pure
mental force.  It can retrieve objects in adjacent rooms, push enemies
back, or interact with distant levers and switches.  Requires psionic
training and sufficient mana.  Difficulty scales with the weight and
distance of the target.

See also: CLAIRVOYANCE, PROJECT, PSIONICS
~

0 CLAIRVOYANCE~
Syntax: clairvoyance

CLAIRVOYANCE briefly lets you scry your immediate surroundings for
concealed exits or threats without moving.  You receive a momentary
mental impression of nearby rooms and any significant dangers within
them.  Range and clarity improve with your psionic skill level.

See also: TELEKINESIS, DANGER, PROJECT, PSIONICS
~

0 DANGER~
Syntax: danger

DANGER SENSE gives you a quick pulse of psionic awareness about nearby
threats.  It warns you if the current room or an adjacent area contains
a particularly perilous mob, active trap, or other significant hazard.
Useful for scouting before stepping into an unknown area.

See also: CLAIRVOYANCE, SEARCH, PSIONICS
~

0 PROJECT~
Syntax: project <direction>

PROJECT sends your spirit one room at a time in the chosen direction,
letting you scout ahead while your body remains in place.  You can look
around the projected location and step further.  Running out of mana or
losing concentration snaps you back to your body immediately.

See also: ASTRAL WALK, CLAIRVOYANCE, PSIONICS
~

0 SHIFT~
Syntax: shift <player>

SHIFT teleports you directly to another player's location if the
destination and your current room permit travel.  Many safe, private,
or magically warded rooms block shifting.  The target receives no
warning of your arrival.

See also: ASTRAL WALK, PROJECT, PSIONICS
~""",
"TELEKINESIS TK CLAIRVOYANCE DANGER PROJECT SHIFT split", CMD_FILE)

# -------------------------------------------------------
# 3. BANK BALANCE DEPOSIT WITHDRAW CONVERT  →  5 entries
# -------------------------------------------------------
c = rep(c,
"""0 BANK BALANCE DEPOSIT WITHDRAW CONVERT~
Syntax: balance
Syntax: deposit <amount> [platinum|gold|silver|copper]
Syntax: withdraw <amount> [platinum|gold|silver|copper]
Syntax: convert

Banking commands let you store wealth safely.  All four commands require you
to be inside a bank room (look for the flag or ask a banker).

  BALANCE   -- Shows your current account balance in all denominations.

  DEPOSIT   -- Moves coins from your inventory into your bank account.
               Specify an amount and an optional coin type.  Examples:
                 deposit 100 gold
                 deposit 500 platinum
               If no coin type is given, gold is assumed.

  WITHDRAW  -- Retrieves coins from your bank account into your inventory.
               Same syntax as deposit.  You must have room in your inventory
               to carry the coins.

  CONVERT   -- Exchanges all your carried coins upward to the highest
               denomination possible (copper -> silver -> gold -> platinum).
               Handy before depositing to keep your inventory tidy.

Notes:
  - The bank earns 1% interest per real day on your balance.  Interest is
    applied automatically while you are logged in (once every 24 real hours,
    catching up to 7 days if you were offline).  Accounts below 1 platinum
    do not earn interest.
  - No fees are charged on deposits or withdrawals.
  - Pkiller characters cannot access banking services.
  - Your bank balance is retained across deaths and remorts.
~""",
"""0 BANK~
All banking commands require you to be inside a bank room.  Available
operations: BALANCE, DEPOSIT, WITHDRAW, and CONVERT.

Notes:
  - The bank earns 1% interest per real day on your balance.  Interest is
    applied automatically while you are logged in (catching up for up to
    7 days of offline time).  Accounts below 1 platinum do not earn interest.
  - No fees are charged on deposits or withdrawals.
  - Pkiller characters cannot access banking services.
  - Your bank balance is retained across deaths and remorts.

See also: BALANCE, DEPOSIT, WITHDRAW, CONVERT, WORTH
~

0 BALANCE~
Syntax: balance

Shows your current bank account balance in all denominations: platinum,
gold, silver, and copper.  You must be inside a bank room.

See also: BANK, DEPOSIT, WITHDRAW, WORTH
~

0 DEPOSIT~
Syntax: deposit <amount> [platinum|gold|silver|copper]

Moves coins from your inventory into your bank account.  An optional coin
type may be specified; if omitted, gold is assumed.  You must be inside
a bank room.

Examples:
  deposit 100 gold
  deposit 500 platinum

See also: BANK, WITHDRAW, BALANCE, CONVERT
~

0 WITHDRAW~
Syntax: withdraw <amount> [platinum|gold|silver|copper]

Retrieves coins from your bank account into your inventory.  Same syntax
as DEPOSIT.  You must have room in your inventory to carry the coins and
must be inside a bank room.

See also: BANK, DEPOSIT, BALANCE
~

0 CONVERT~
Syntax: convert

Exchanges all your carried coins upward to the highest denomination
possible (copper -> silver -> gold -> platinum).  Handy before depositing
to keep your inventory tidy.  Must be inside a bank room.

See also: BANK, DEPOSIT, BALANCE
~""",
"BANK BALANCE DEPOSIT WITHDRAW CONVERT split", CMD_FILE)

# -------------------------------------------------------
# 4. BREW CONCOCT SCRIBE SHOOT PICK JUNK  →  5 entries
# -------------------------------------------------------
c = rep(c,
"""0 BREW CONCOCT SCRIBE SHOOT PICK JUNK~
Syntax: brew <potion recipe>
Syntax: concoct <component list>
Syntax: scribe <scroll recipe>
Syntax: shoot <target>
Syntax: pick <direction/lock>
Syntax: junk <object>

Crafting and utility commands:
- BREW/CONCOCT create magical potions from components you carry.
- SCRIBE copies a spell into a blank scroll if you know the spell and have a
  quill.
- SHOOT uses a loaded projectile weapon to fire at your current target.
- PICK attempts to pick the lock on a door or container using your lockpicks
  and the PICK LOCK skill.
- JUNK destroys an unwanted object, clearing inventory space without leaving
  a corpse behind.
~""",
"""0 BREW CONCOCT~
Syntax: brew <potion recipe>
Syntax: concoct <component list>

BREW creates a magical potion from a recipe if you have the required
components in your inventory.  CONCOCT is a related command that combines
a specific list of components into a potion using your alchemical knowledge
directly.  Both require alchemical skill and the right materials.

See also: SCRIBE, QUAFF
~

0 SCRIBE~
Syntax: scribe <scroll recipe>

SCRIBE copies a spell you know onto a blank scroll, creating a single-use
magical item.  You must have a blank scroll, a quill, and sufficient
knowledge of the target spell.  The spell is inscribed at your current
level of mastery.

See also: BREW, RECITE
~

0 SHOOT~
Syntax: shoot <target>

SHOOT fires a loaded projectile weapon (bow, crossbow, etc.) at a target.
You must have ammunition loaded or available.  Missile weapons deal ranged
damage; effectiveness depends on your SHOOT skill and the weapon's stats.

See also: WIELD, KICK, BACKSTAB
~

0 PICK~
Syntax: pick <direction>
Syntax: pick <container>

PICK attempts to open a lock on a door or container using lockpicks and
the PICK LOCK skill.  Success opens the lock without a key.  Difficulty
depends on the lock's strength and your skill level.  A failed attempt
may alert nearby mobs.

See also: OPEN, LOCK, UNLOCK, STEAL
~

0 JUNK~
Syntax: junk <object>

JUNK destroys an unwanted object from your inventory, permanently removing
it from the game.  Once junked, an item cannot be recovered.  Use JUNK to
clear inventory space without dropping items on the ground.

See also: SACRIFICE, DROP, DONATE
~""",
"BREW CONCOCT SCRIBE SHOOT PICK JUNK split", CMD_FILE)

# -------------------------------------------------------
# 5. CRANE FISTS  →  CRANE  +  FISTS
# -------------------------------------------------------
c = rep(c,
"""0 CRANE FISTS~
Syntax: crane
Syntax: fists

Toggle unarmed fighting stances.

CRANE adopts the crane style: balanced, evasive, with a slight defensive
edge.  The stance improves your dodge and parry while sacrificing some raw
damage output.  Suitable for characters who prefer to outlast their foes.

FISTS adopts the iron-fist style: aggressive, forward-pressing, with
emphasis on raw hand-to-hand damage.  You deal more damage unarmed but
take more hits in return.  Best used when you intend to end the fight
quickly.

Both stances require training in the appropriate hand-to-hand skill.
Entering combat or exceeding your movement limit will break the stance.

See also: KICK, BERSERK
~""",
"""0 CRANE~
Syntax: crane

Toggle the crane fighting stance.  CRANE adopts a balanced, evasive style
that improves your dodge and parry while sacrificing some raw damage output.
Suitable for characters who prefer to outlast their foes rather than
overwhelm them quickly.  Requires the crane skill.  Entering combat at full
speed or running out of movement breaks the stance.

See also: FISTS, IRON, ROLL, KICK
~

0 FISTS~
Syntax: fists

Toggle the iron-fist fighting stance.  FISTS adopts an aggressive,
forward-pressing style with emphasis on raw hand-to-hand damage.  You deal
more damage unarmed but take more hits in return.  Best used when you intend
to end the fight quickly.  Requires the fists skill.

See also: CRANE, BERSERK, KICK
~""",
"CRANE FISTS split", CMD_FILE)

# -------------------------------------------------------
# 6. HIT MURDER MURDE  →  HIT  +  MURDER MURDE
# -------------------------------------------------------
c = rep(c,
"""0 HIT MURDER MURDE~
Syntax: hit <victim>
Syntax: murder <victim>
Syntax: murde <victim>

Direct physical attack commands.

HIT works identically to the KILL command: it starts or continues combat
against the chosen target.  Use it when you prefer not to type "kill".

MURDER (and its abbreviation MURDE) explicitly flags your action as a
hostile assault regardless of the target's criminal status or alignment.
Unlike HIT, MURDER is always logged and counts as a pk-flagged attack if
the target is a player.  Use with care in populated areas.

See also: KILL, BACKSTAB, BASH
~""",
"""0 HIT~
Syntax: hit <victim>

HIT is an alias for the KILL command and starts or continues combat
against the chosen target.  Use it when you prefer not to type "kill".
HIT does not carry the additional PK logging that MURDER does.

See also: KILL, MURDER, BACKSTAB
~

0 MURDER MURDE~
Syntax: murder <victim>
Syntax: murde <victim>

MURDER (and its abbreviation MURDE) explicitly flags your action as a
hostile assault against a player character.  Unlike HIT or KILL, MURDER
is always logged and counts as a pk-flagged attack.  Against mobs it
functions identically to KILL.  Use with care in populated areas.

See also: HIT, KILL, PKILL
~""",
"HIT MURDER MURDE split", CMD_FILE)

# -------------------------------------------------------
# 6b. Remove the short ENERVATE duplicate (keep the detailed psionic one)
#     The short one is in the combat section; the full one is in the psionic section
# -------------------------------------------------------
c = rep(c,
"""0 ENERVATE~
Syntax: enervate <victim>

Drain vital energy from your target, weakening their physical or mental
reserves.  On a failed save the victim suffers reduced stats or combat
effectiveness for the duration.  The precise debuff depends on your level
and spellcasting ability.  Particularly effective against high-endurance
fighters who rely on long attrition.

See also: CONFUSE, TORMENT, NIGHTMARE
~""",
"", "short ENERVATE duplicate removed", CMD_FILE)

# -------------------------------------------------------
# 7. ARRIVE DEPART  →  ARRIVE  +  DEPART
# -------------------------------------------------------
c = rep(c,
"""0 ARRIVE DEPART~
Syntax: arrive <string>
        depart <string>

Sets the message that others see when you enter and leave rooms.

All messages must contain a $n where your name is to be placed and a
$t(or $T) where the direction is to be placed.

The difference between $t and $T is the directions that are defaulted.
$t (arrive/depart)= north, south, east, west, up, down
$T (arrive) = the north, the south, the east, the west, above, below
$T (depart) = the north, the south, the east, the west, up, down
~""",
"""0 ARRIVE~
Syntax: arrive <string>

Sets the message that others see when you enter a room.  The message must
include $n (your name) and $T (the direction you arrived from).

  $T (arrive) = the north, the south, the east, the west, above, below

Example:  arrive $n strides in from $T.

See also: DEPART
~

0 DEPART~
Syntax: depart <string>

Sets the message that others see when you leave a room.  The message must
include $n (your name) and $t (the direction you are heading).

  $t (depart) = north, south, east, west, up, down

Example:  depart $n slips away to the $t.

See also: ARRIVE
~""",
"ARRIVE DEPART split", CMD_FILE)

# -------------------------------------------------------
# 8. AUTO AUTOLIST + 7 flags  →  AUTO AUTOLIST  +  7 individual entries
# -------------------------------------------------------
c = rep(c,
"""0 AUTO AUTOLIST AUTOLOOT AUTOGOLD AUTOSAC AUTOEXIT AUTOASSIST AUTOSPLIT~
Syntax: autolist
        autoloot
        autogold
        autosac
        autoexit
        autosplit
        autoassist

ToC uses varies automatic actions, to ease the boredom of always splitting
gold and sacrificing corpses.  The actions are as follows:

autolist   : list all automatic actions
autogold   : take all gold from dead mobiles
autoloot   : take all equipment from dead mobiles
autosac    : sacrifice dead monsters (if autoloot is on, only empty corpses)
autoexit   : display room exits upon entering a room
autosplit  : split up spoils from combat among your group members
autoassist : makes you help group members in combat

Typing a command sets the action (except for autolist); typing it again removes
it.  When you create a new character, the default is for all of the automatic
actions to be on.

AUTO is equivalent to autolist and also shows the status of the PROMPT,
COMBINE ITEMS, NOFOLLOW, NOSUMMON, and NOLOOT flags..
~""",
"""0 AUTO AUTOLIST~
Syntax: auto
Syntax: autolist

AUTO (or AUTOLIST) displays the current status of all automatic feature
flags: AUTOLOOT, AUTOGOLD, AUTOSAC, AUTOEXIT, AUTOASSIST, AUTOSPLIT, as
well as PROMPT, COMBINE, NOFOLLOW, NOSUMMON, and NOLOOT.  When you create
a new character all automatic actions are on by default.

See also: AUTOLOOT, AUTOGOLD, AUTOSAC, AUTOEXIT, AUTOASSIST, AUTOSPLIT
~

0 AUTOLOOT~
Syntax: autoloot

Toggle automatic looting.  When on, you automatically pick up all equipment
from mobiles you kill.  When AUTOLOOT is on, AUTOSAC will only sacrifice
corpses that have already been fully looted.

See also: AUTO, AUTOGOLD, AUTOSAC
~

0 AUTOGOLD~
Syntax: autogold

Toggle automatic gold collection.  When on, all gold is automatically
taken from mobiles you kill.

See also: AUTO, AUTOLOOT, AUTOSPLIT
~

0 AUTOSAC~
Syntax: autosac

Toggle automatic corpse sacrifice.  When on, dead monster corpses are
automatically sacrificed after looting.  If AUTOLOOT is also on, only
empty corpses are sacrificed.

See also: AUTO, AUTOLOOT, SACRIFICE
~

0 AUTOEXIT~
Syntax: autoexit

Toggle automatic exit display.  When on, visible room exits are shown
every time you enter a room, alongside the room description.

See also: AUTO, EXITS, BRIEF
~

0 AUTOASSIST~
Syntax: autoassist

Toggle automatic group assist.  When on, you automatically join combat
if another member of your group is attacked.

See also: AUTO, GROUP, RESCUE
~

0 AUTOSPLIT~
Syntax: autosplit

Toggle automatic gold splitting.  When on, gold looted from kills is
automatically split among all group members in the same room.

See also: AUTO, SPLIT, AUTOGOLD
~""",
"AUTO AUTOLIST + flags split", CMD_FILE)

# -------------------------------------------------------
# 9. BRANDISH QUAFF RECITE ZAP  →  4 entries
# -------------------------------------------------------
c = rep(c,
"""0 BRANDISH QUAFF RECITE ZAP~
Syntax: brandish
Syntax: quaff    <potion>
Syntax: recite   <scroll> <target>
Syntax: zap      <target>
Syntax: zap

BRANDISH brandishes a magical staff.  QUAFF quaffs a magical potion (as opposed
to DRINK, which drinks mundane liquids).  RECITE recites a magical scroll; the
<target> is optional, depending on the nature of the scroll.  ZAP zaps a
magical wand at a target.  If the target is not specified, and you are fighting
someone, then that character is used for a target.

You must HOLD a wand or a staff before using BRANDISH or ZAP.

All of these commands use up their objects.  Potions and scrolls have a single
charge.  Wands and staves have multiple charges.  When a magical object has no
more charges, it will be consumed.

These commands may require an item skill to be successful, see the help entries
on the SCROLLS, STAVES, and WANDS skills for more information.  No skill is
required to quaff a potion.
~""",
"""0 BRANDISH~
Syntax: brandish

BRANDISH activates a magical staff you are holding.  You must HOLD the
staff first.  Staves have multiple charges; each brandish uses one.  When
all charges are exhausted the staff is consumed.  May require the STAVES
skill.

See also: ZAP, HOLD, RECITE, QUAFF
~

0 QUAFF~
Syntax: quaff <potion>

QUAFF drinks a magical potion, triggering its effects immediately.  This
is distinct from DRINK, which consumes mundane beverages.  Potions have a
single charge and are consumed on use.  No skill is required to quaff.

See also: BRANDISH, RECITE, ZAP, DRINK
~

0 RECITE~
Syntax: recite <scroll> [target]

RECITE reads from a magical scroll, casting the inscribed spell.  The
target argument is optional and depends on the nature of the scroll.
Scrolls have a single charge and are consumed on use.  May require the
SCROLLS skill.

See also: BRANDISH, QUAFF, ZAP
~

0 ZAP~
Syntax: zap <target>
Syntax: zap

ZAP fires a magical wand at a target.  You must HOLD the wand first.  If
no target is given and you are in combat, the current opponent is targeted
automatically.  Wands have multiple charges; each zap uses one.  When all
charges are exhausted the wand is consumed.  May require the WANDS skill.

See also: BRANDISH, RECITE, HOLD
~""",
"BRANDISH QUAFF RECITE ZAP split", CMD_FILE)

# -------------------------------------------------------
# 10. BUY LIST SELL VALUE  →  4 entries
# -------------------------------------------------------
c = rep(c,
"""0 BUY LIST SELL VALUE~
Syntax: buy   <object>
Syntax: list
Syntax: sell  <object>
Syntax: value <object>

BUY buys an object from a shop keeper.
When multiple items of the same name are listed, type 'buy n.item', where n
is the position of the item in a list of that name.  So if there are two
swords, buy 2.sword will buy the second.

LIST lists the objects the shop keeper will sell you.
List <name> shows you only objects of that name.

SELL sells an object to a shop keeper.

VALUE asks the shop keeper how much he, she, or it will buy the item for.
~""",
"""0 BUY~
Syntax: buy <object>
Syntax: buy <n>.<object>

BUY purchases an object from a shopkeeper.  When multiple items of the
same name are available, prepend the position index: 'buy 2.sword' buys
the second sword in the list.

See also: LIST, SELL, VALUE
~

0 LIST~
Syntax: list
Syntax: list <name>

LIST shows the items a shopkeeper will sell you.  With a name argument,
only items matching that name are displayed.

See also: BUY, SELL, VALUE
~

0 SELL~
Syntax: sell <object>

SELL offers an object to a shopkeeper in exchange for gold.  The price is
shown before the transaction completes.  The shopkeeper may refuse items
they do not buy; use VALUE to check first.

See also: BUY, VALUE, LIST
~

0 VALUE~
Syntax: value <object>

VALUE asks a shopkeeper how much they will pay for an item.  Use this
before SELL to confirm the item is wanted and check the offered price.

See also: SELL, BUY, LIST
~""",
"BUY LIST SELL VALUE split", CMD_FILE)

# -------------------------------------------------------
# 11. OPEN CLOSE LOCK UNLOCK  →  OPEN CLOSE  +  LOCK UNLOCK
# -------------------------------------------------------
c = rep(c,
"""0 OPEN CLOSE LOCK UNLOCK~
Syntax: open   <object|direction>
Syntax: close  <object|direction>
Syntax: lock   <object|direction>
Syntax: unlock <object|direction>

OPEN and CLOSE open and close an object or a door.

LOCK and UNLOCK lock and unlock a closed object or door.  You must have
the requisite key to LOCK or UNLOCK.

Those with the appropriate skill can PICK locks, enabling them to open
locked doors or objects without having the key.  See help on PICK for more
information.
~""",
"""0 OPEN CLOSE~
Syntax: open  <object|direction>
Syntax: close <object|direction>

OPEN opens a door or container.  CLOSE shuts it again.  Both commands
accept either a direction (to act on that exit's door) or an object name
(to open a container in the room or your inventory).

See also: LOCK, UNLOCK, PICK, DOORBASH
~

0 LOCK UNLOCK~
Syntax: lock   <object|direction>
Syntax: unlock <object|direction>

LOCK secures a closed door or container.  UNLOCK removes the lock.  Both
require the appropriate key in your inventory.  Without a key, characters
with the PICK LOCK skill can bypass the lock with the PICK command.

See also: OPEN, CLOSE, PICK, DOORBASH
~""",
"OPEN CLOSE LOCK UNLOCK split", CMD_FILE)

# -------------------------------------------------------
# 12. DRINK EAT FILL  →  3 entries
# -------------------------------------------------------
c = rep(c,
"""0 DRINK EAT FILL~
Syntax: drink <object>
Syntax: eat   <object>
Syntax: fill  <object>

When you are thirsty, DRINK something.

When you are hungry, EAT something.

FILL fills a drink container with water from a fountain or pool.
~""",
"""0 DRINK~
Syntax: drink <object>

DRINK consumes a liquid from a drink container to quench your thirst.
Characters who become dehydrated suffer regeneration penalties.  Use
FILL to refill empty drink containers from a fountain or pool.

See also: EAT, FILL, QUAFF
~

0 EAT~
Syntax: eat <object>

EAT consumes a food item to satisfy your hunger.  Characters who become
hungry suffer regeneration penalties.  Some foods apply temporary magical
or status effects when eaten.

See also: DRINK, FILL
~

0 FILL~
Syntax: fill <object>

FILL refills a drink container with fresh water from a nearby fountain
or pool.  You must be in a room with an accessible water source.

See also: DRINK, EAT
~""",
"DRINK EAT FILL split", CMD_FILE)

# -------------------------------------------------------
# 13. DROP GET GIVE PUT TAKE  →  4 entries
# -------------------------------------------------------
c = rep(c,
"""0 DROP GET GIVE PUT TAKE~
Syntax: drop <object>
Syntax: drop <amount> coins
Syntax: get  <object>
Syntax: get  <object> <container>
Syntax: give <object> <character>
Syntax: give <amount> coins <character>
Syntax: put  <object> <container>

DROP drops an object, or some coins, on the ground.

GET gets an object, either lying on the ground, or from a container, or even
from a corpse.  TAKE is a synonym for get.

GIVE gives an object, or some coins, to another character.

PUT puts an object into a container.

DROP, GET and PUT understand the object names 'ALL' for all objects and
'ALL.object' for all objects with the same name.
~""",
"""0 DROP~
Syntax: drop <object>
Syntax: drop <amount> coins
Syntax: drop all
Syntax: drop all.<keyword>

DROP places an object or coins on the ground in the current room.  'drop
all' drops everything; 'drop all.sword' drops all items named "sword".

See also: GET, PUT, GIVE, DONATE
~

0 GET TAKE~
Syntax: get <object>
Syntax: get <object> <container>
Syntax: take <object>
Syntax: get all
Syntax: get all.<keyword>

GET (or TAKE) picks up an object from the ground, from a container, or
from a corpse.  'get all' picks up everything available; 'get all.sword'
takes all items named "sword".

See also: DROP, PUT, INVENTORY
~

0 GIVE~
Syntax: give <object> <character>
Syntax: give <amount> coins <character>

GIVE hands an object or a quantity of coins to another character in the
same room.  The recipient must be present and able to receive it.

See also: DROP, SPLIT, DONATE
~

0 PUT~
Syntax: put <object> <container>

PUT places an object into a container.  The container must be in your
inventory or the room.  The object must fit within the container's weight
and size limits.

See also: GET, DROP, INVENTORY
~""",
"DROP GET GIVE PUT TAKE split", CMD_FILE)

# -------------------------------------------------------
# 14. EMOTE , POSE SOCIAL SOCIALS  →  3 entries
# -------------------------------------------------------
c = rep(c,
"""0 EMOTE , POSE SOCIAL SOCIALS~
Syntax: emote <action>
Syntax: , <action>
Syntax: pose

Socials are a large set of specialized commands that let you do such things
as smile, wave, etc. to yourself, others or nobody in particular.  For a
complete list of the available actions, type SOCIAL.

EMOTE is used to express emotions or actions.  A shortcut for emote is ,.
EMOTE allows you to perform actions that are not built in.

POSE is a variant of EMOTE.  POSE selects a pose at random.  The poses are
dependent on your class.

The following is a (not necessarily complete) list of the socials which
exist in ToC:
gack        kiss        eve         bounce      smile       dance
cackle      laugh       giggle      shake       puke        growl
scream      comfort     sigh        sulk        hug         snuggle
cuddle      nuzzle      cry         poke        accuse      grin
bow         applaud     blush       burp        chuckle     clap
cough       curtsey     fart        flip        fondle      frown
gasp        glare       groan       grope       hiccup      lick
love        moan        nibble      pout        ruffle      shiver
shrug       sing        slap        smirk       snap        sneeze
snicker     sniff       snore       squeeze     stare       strut
thank       twiddle     wave        whistle     wiggle      wink
yawn        snowball    french      comb        massage     tickle
pat         curse       pray        beg         cringe      daydream
fume        grovel      hop         nudge       ponder      punch
snarl       spank       hand        yodel       faint       pinch
stroke      apologize   caress      stagger     snort       slobber
blink       tease       knee        flirt       tip         lust
flutter     bark        howl        babble      ramble      hush
threaten    roll        swoon       bird        eyebrow     serenade
grimace     boggle      beckon      wonder      worry       drool
nod         purr        point       rub         bleed       highfive
propose     peer        worship     bearhug     innocent    collapse
stretch     spam        boast       squirm      moo         moon
goose       wince       type        brb         mutter      rofl
sob         pant        whine       flex        embrace     duck
bonk        squeal      tackle      spit        life        mosh
flinch      air         tweak       peck        explode     raspberry
flash       strip       undress     tongue      view        grumble
cheer       plead       charge      criticize   run         judge
insane      cover       flare       head        pie         cower
noogie      yeehaw      pissed      passout     adjust      scratch
meditate    bkiss       beer        bcatch      claw        rose
laces       tag         tank        starve      aargh       homework
puff        differ      yae         lightbulb   voodoo      awkward
dab         derp        facepalm    micdrop     panic       slowclap
~""",
"""0 EMOTE ,~
Syntax: emote <action>
Syntax: , <action>

EMOTE broadcasts a custom action to everyone in your current room.  The
comma (,) is a shortcut for EMOTE.  Unlike fixed socials, EMOTE lets you
type any free-form action.

Example:  emote grins wickedly.    or    ,grins wickedly.

See also: POSE, SOCIAL, SAY
~

0 POSE~
Syntax: pose

POSE displays a random, class-appropriate emote selected automatically by
the game.  Each class has its own set of poses.  Use POSE for quick flavor
text without typing a full EMOTE message.

See also: EMOTE, SOCIAL
~

0 SOCIAL SOCIALS~
Syntax: social
Syntax: socials

SOCIAL (or SOCIALS) lists all built-in social commands available in the
game.  Each social is a named action you can direct at yourself, another
player, or no target (e.g. smile, wave, bow, laugh).  Type the social's
name alone or with a target name.

The following is a (not necessarily complete) list of available socials:
gack        kiss        eve         bounce      smile       dance
cackle      laugh       giggle      shake       puke        growl
scream      comfort     sigh        sulk        hug         snuggle
cuddle      nuzzle      cry         poke        accuse      grin
bow         applaud     blush       burp        chuckle     clap
cough       curtsey     fart        flip        fondle      frown
gasp        glare       groan       grope       hiccup      lick
love        moan        nibble      pout        ruffle      shiver
shrug       sing        slap        smirk       snap        sneeze
snicker     sniff       snore       squeeze     stare       strut
thank       twiddle     wave        whistle     wiggle      wink
yawn        snowball    french      comb        massage     tickle
pat         curse       pray        beg         cringe      daydream
fume        grovel      hop         nudge       ponder      punch
snarl       spank       hand        yodel       faint       pinch
stroke      apologize   caress      stagger     snort       slobber
blink       tease       knee        flirt       tip         lust
flutter     bark        howl        babble      ramble      hush
threaten    roll        swoon       bird        eyebrow     serenade
grimace     boggle      beckon      wonder      worry       drool
nod         purr        point       rub         bleed       highfive
propose     peer        worship     bearhug     innocent    collapse
stretch     spam        boast       squirm      moo         moon
goose       wince       type        brb         mutter      rofl
sob         pant        whine       flex        embrace     duck
bonk        squeal      tackle      spit        life        mosh
flinch      air         tweak       peck        explode     raspberry
flash       strip       undress     tongue      view        grumble
cheer       plead       charge      criticize   run         judge
insane      cover       flare       head        pie         cower
noogie      yeehaw      pissed      passout     adjust      scratch
meditate    bkiss       beer        bcatch      claw        rose
laces       tag         tank        starve      aargh       homework
puff        differ      yae         lightbulb   voodoo      awkward
dab         derp        facepalm    micdrop     panic       slowclap

See also: EMOTE, POSE
~""",
"EMOTE , POSE SOCIAL SOCIALS split", CMD_FILE)

# -------------------------------------------------------
# 15. HOLD REMOVE WEAR WIELD  →  4 entries
# -------------------------------------------------------
c = rep(c,
"""0 HOLD REMOVE WEAR WIELD~
Syntax: hold   <object>
Syntax: remove <object>
Syntax: wear   <object>
Syntax: wear   all
Syntax: wield  <object>

Three of these commands will take an object from your inventory and start using
it as equipment.  HOLD is for light sources, wands, and staves.  WEAR is for
armor.  WIELD is for weapons.

WEAR ALL will attempt to HOLD, WEAR, or WIELD each suitable item in your
inventory.

You may not be able to HOLD, WEAR, or WIELD an item if its alignment does not
match yours, if it is too heavy for you, or if you are not experienced enough
to use it properly.

REMOVE will take any object from your equipment and put it back into your
inventory.  REMOVE ALL will remove all of your equipment, except for cursed
items.

Those with the appropriate skill may wield a second weapon.  For more
information on this, read help for DUAL WIELD.
~""",
"""0 WEAR~
Syntax: wear <object>
Syntax: wear all

WEAR equips a piece of armor or clothing at its appropriate body slot.
You may not be able to wear an item if its alignment does not match yours,
it is too heavy for you, or you are not experienced enough.  WEAR ALL
attempts to equip every suitable item in your inventory at once.

See also: WIELD, HOLD, REMOVE, EQUIPMENT
~

0 WIELD~
Syntax: wield <object>

WIELD equips a weapon in your main hand.  Characters with the SECONDARY
skill can equip a second weapon in the off hand using the SECONDARY
command.

See also: WEAR, HOLD, REMOVE, SECONDARY, DUAL WIELD
~

0 HOLD~
Syntax: hold <object>

HOLD equips a light source, wand, or staff in the held-item slot.  Only
items designated for holding can be used this way.

See also: WEAR, WIELD, ZAP, BRANDISH, REMOVE
~

0 REMOVE~
Syntax: remove <object>
Syntax: remove all

REMOVE takes an equipped item and puts it back into your inventory.
REMOVE ALL strips all your gear except for cursed items, which cannot
be removed until the curse is lifted.

See also: WEAR, WIELD, HOLD, EQUIPMENT
~""",
"HOLD REMOVE WEAR WIELD split", CMD_FILE)

# -------------------------------------------------------
# 16. KILL PKILL MURDER  →  KILL  +  PKILL  (MURDER has its own entry now)
# -------------------------------------------------------
c = rep(c,
"""0 KILL PKILL MURDER~
Syntax: kill <name of mob>
        murder <character>

The KILL command is used to start a fight with a mobile.  You need to type
kill only once per fight.

PKILL is permanent setting. Once you become level 15, you may choose to
participate in pKilling, and once you have passed level 30, the option is
no longer available.

To do this, you type PKILL and your password.  Once you set yourself to PKILL,
it is permanent, and under no circumstances will it be set back.  You will only
be able to see who pKillers are by physically walking up to them and CONSIDERing
them.

To kill other players, use MURDER.  Player killing is only permitted
for those who have selected this option (SEE ABOVE)  and there are
restrictions on the relative levels of the pkiller and victim.
Non-pKILL players may pkill or be pkilled only in the arena (SEE HELP
ARENA).

MURDER also works to kill mobiles.
~""",
"""0 KILL~
Syntax: kill <name of mob>

The KILL command starts a fight with a mobile (non-player character).  You
need to type kill only once per fight.  Attacking player characters
requires MURDER instead.

See also: MURDER, HIT, FLEE, WIMPY
~

0 PKILL~
Syntax: pkill <password>

PKILL is a permanent, irreversible setting.  Between level 15 and 30, you
may choose to participate in player killing by typing PKILL followed by
your password.  After level 30 the option is no longer available.  Once
set, pkill status cannot be revoked under any circumstances.

You can identify other pkillers only by walking up to them and using
CONSIDER.  Non-pkillers may only engage in player combat inside the arena.

See also: MURDER, ARENA, KILL
~""",
"KILL PKILL MURDER split", CMD_FILE)

# -------------------------------------------------------
# 17. GOSSIP . INFO LEVELING MUSIC Q/A SHOUT YELL  →  6 entries
#     (Q/A already has a QUESTION entry; just split the rest)
# -------------------------------------------------------
c = rep(c,
"""0 GOSSIP . INFO LEVELING MUSIC Q/A SHOUT YELL~
Syntax: gossip <message>
Syntax: gossip
Syntax: info
Syntax: music <message>
Syntax: music
Syntax: question <message>
Syntax: question
Syntax: shout <message>
Syntax: yell <message>

ToC supplies a number of public communication channels.  Type the name of
a channel with a message to use on of these channels.  Typing the name of
the channel alone turns that channel off.

SHOUT sends a message to all awake players in the world.  To curb excessive
shouting, SHOUT imposes a three-second delay on the shouter.  In addition,
players must be at least level 3 in order to shout.

GOSSIP is a variant of SHOUT (without the delay).  '.' is a synonym
for GOSSIP.  GOSSIP is the most frequently used public channel on ToC.

YELL sends a message to all awake players within your area.

In general, most public communication between players will be on the gossip
channel.  The Q/A  (Syntax: question) channel is used for asking questions
about items.  Use the MUSIC channel when you wish to sing.
If what you have to say is primarily of interest only to one other player,
you might want to use a private channel (e.g. TELL) instead.
Note that you must be at least level 2 to use the public channels.

The INFO channel displays automatic messages when a player attains a new
level.  The LEVELING channel is intended for congratulatory messages to
those who level.

Typing a channel name without a message turns that channel off.

See also helps on CHANNELS, CC CGOS GTELL DEAF QUIET REPLY SAY and TELL.
~""",
"""0 GOSSIP .~
Syntax: gossip <message>
Syntax: gossip
Syntax: . <message>

GOSSIP broadcasts a message to all players in the world who have the channel
enabled.  The period (.) is a shortcut for GOSSIP.  This is the most
frequently used public channel on ToC.  Typing GOSSIP without a message
toggles the channel off; type it again to restore it.

You must be at least level 2 to use the gossip channel.

See also: SHOUT, YELL, CHANNELS, DEAF, QUIET, TELL
~

0 SHOUT~
Syntax: shout <message>

SHOUT sends a message to all awake players in the world.  To curb excessive
shouting, SHOUT imposes a three-second delay on the shouter.  Players must
be at least level 3 to shout.  Use DEAF to block incoming shouts, or QUIET
to silence all public channels at once.

See also: GOSSIP, YELL, DEAF, CHANNELS
~

0 YELL~
Syntax: yell <message>

YELL broadcasts a message to all awake players within your current area
only.  It is narrower than SHOUT (world-wide) and more broadly heard
than SAY (room only).

See also: SHOUT, GOSSIP, SAY, CHANNELS
~

0 INFO~
Syntax: info

INFO is a broadcast channel that displays automatic notifications when a
player attains a new level.  Typing INFO alone toggles the channel off or
on; you cannot send messages on the info channel directly.

See also: LEVELING, CHANNELS
~

0 LEVELING~
Syntax: leveling <message>
Syntax: leveling

The LEVELING channel is for congratulatory messages to players who just
leveled up.  INFO displays the automatic level notification; LEVELING is
where other players respond with congratulations.  Typing LEVELING alone
toggles the channel.

See also: INFO, GOSSIP, CHANNELS
~

0 MUSIC~
Syntax: music <message>
Syntax: music

The MUSIC channel is used for singing and sharing music-related content
with all players.  Send a message or type MUSIC alone to toggle it off or
on.

See also: GOSSIP, CHANNELS
~""",
"GOSSIP . INFO LEVELING MUSIC Q/A SHOUT YELL split", CMD_FILE)

# -------------------------------------------------------
# 18. GTELL REPLY SAY TELL  →  TELL  +  REPLY
#     (SAY already has '  SAY~ entry; GTELL already has ;  GTELL~ entry)
# -------------------------------------------------------
# Use a partial match that skips the problematic ''' sequence
old_gtell_start = "0 GTELL REPLY SAY TELL~"
old_gtell_end   = "This is handy for talking to invisible or switched immortal players.\n~"
if old_gtell_start in c and old_gtell_end in c:
    idx_start = c.index(old_gtell_start)
    idx_end   = c.index(old_gtell_end, idx_start) + len(old_gtell_end)
    old_block = c[idx_start:idx_end]
    new_block = """0 TELL~
Syntax: tell <character> <message>

TELL sends a private message to one awake player anywhere in the world.
Only the target sees your message.  Use REPLY to respond to the last tell
you received.

See also: REPLY, SAY, GTELL, CHANNELS
~

0 REPLY~
Syntax: reply <message>

REPLY sends a message to the last player who sent you a TELL.  REPLY
works even if you cannot see the player and without revealing their
identity.  This is handy for talking to invisible or switched immortal
players.

See also: TELL, SAY, GTELL
~"""
    c = c[:idx_start] + new_block + c[idx_end:]
    applied.append("GTELL REPLY SAY TELL split")
else:
    warnings.append("GTELL REPLY SAY TELL block NOT FOUND by boundary search")

# -------------------------------------------------------
# 19. REST SLEEP STAND WAKE SIT  →  SLEEP  +  REST STAND WAKE SIT
# -------------------------------------------------------
c = rep(c,
"""0 REST SLEEP STAND WAKE SIT~
Syntax: rest
Syntax: sleep
Syntax: stand
Syntax: wake
Syntax: sit

These commands change your position.  When you REST or SLEEP, you
regenerate hit points, mana points, and movement points faster.
However, you are more vulnerable to attack, and if you SLEEP,
you won't hear many things happen.

Use STAND or WAKE to come back to a standing position.  You can
also WAKE other sleeping characters.

For information on the sleep spell, see help SLEEPSPELL.
~""",
"""0 SLEEP~
Syntax: sleep

SLEEP puts your character into a deep slumber.  While asleep you
regenerate hit points, mana, and movement at the fastest possible rate,
but you are more vulnerable to attack and will not hear most events in
the room.  Use WAKE or STAND to get up.

For information on the sleep spell, see SLEEPSPELL.

See also: REST, STAND, WAKE, WIMPY
~

0 REST STAND WAKE SIT~
Syntax: rest
Syntax: stand
Syntax: wake
Syntax: sit

These commands change your position.  When you REST or SIT, you regenerate
hit points, mana, and movement faster than while standing, while remaining
aware of your surroundings.

STAND or WAKE returns you to a standing position.  You can also use WAKE
to rouse a sleeping character.

See also: SLEEP, FLEE, WIMPY
~""",
"REST SLEEP STAND WAKE SIT split", CMD_FILE)

# -------------------------------------------------------
# 20. EXAMINE LOOK READ  →  LOOK READ  +  EXAMINE
# -------------------------------------------------------
c = rep(c,
"""0 EXAMINE LOOK READ~
Syntax: look
Syntax: look room
Syntax: look <object>
Syntax: look <character>
Syntax: look <direction>
Syntax: look <keyword>
Syntax: look in <container>
Syntax: look in <corpse>
Syntax: examine <container>
Syntax: examine <corpse>

LOOK looks at something and sees what you can see.  For example, if you look
at a character, you will see that character's description and equipment.

LOOK alone, without an argument, describes the room you are in; if BRIEF is
on, you will see only the short description of the room.  Use Look room to
see the full ("unbriefed") description of the room.

EXAMINE is short for 'LOOK container' followed by 'LOOK IN container'.

READ is a synonym for LOOK.
~""",
"""0 LOOK READ~
Syntax: look
Syntax: look room
Syntax: look <object>
Syntax: look <character>
Syntax: look <direction>
Syntax: look <keyword>
Syntax: look in <container>
Syntax: look in <corpse>

LOOK examines whatever you specify.  Looking at a character shows their
description and equipment.  LOOK alone describes the room you are in;
with BRIEF on, only the short description is shown.  Use 'look room' to
see the full, unbriefed room description.

READ is a synonym for LOOK.

See also: EXAMINE, SEARCH, INVENTORY
~

0 EXAMINE~
Syntax: examine <container>
Syntax: examine <corpse>

EXAMINE is shorthand for 'LOOK <container>' followed by 'LOOK IN
<container>'.  It shows the container itself and then lists all of its
contents in one step.  Particularly useful for inspecting corpses and packs.

See also: LOOK, INVENTORY, GET
~""",
"EXAMINE LOOK READ split", CMD_FILE)

# -------------------------------------------------------
# Add See Also to entries currently missing them
# -------------------------------------------------------

# COMPACT
c = rep(c,
"The default is for compact to be off.\n~\n\n0 COMPARE~",
"The default is for compact to be off.\n\nSee also: BRIEF, COLOR, COMBINE\n~\n\n0 COMPARE~",
"COMPACT add See Also", CMD_FILE)

# COMPARE
c = rep(c,
"by using the IDENTIFY spell or the LORE skill..\n~\n\n0 CONSIDER~",
"by using the IDENTIFY spell or the LORE skill.\n\nSee also: LORE, INVENTORY, EQUIPMENT\n~\n\n0 CONSIDER~",
"COMPARE add See Also", CMD_FILE)

# CONSIDER
c = rep(c,
"rough idea of whether or not it is worth attempting the fight.\n~\n\n0 COUNT~",
"rough idea of whether or not it is worth attempting the fight.\n\nSee also: SCORE, WIMPY, FLEE\n~\n\n0 COUNT~",
"CONSIDER add See Also", CMD_FILE)

# DESCRIPTION DESC
c = rep(c,
"so that you can make multi-line descriptions.\n~\n\n0 DONATE~",
"so that you can make multi-line descriptions.\n\nSee also: TITLE, WHO, SCORE\n~\n\n0 DONATE~",
"DESCRIPTION add See Also", CMD_FILE)

# DONATE
c = rep(c,
"either in the Temple of Devota or in one of the guild halls in Dresden.\n~\n\n0 DRINK~",
"either in the Temple of Devota or in one of the guild halls in Dresden.\n\nSee also: DROP, SACRIFICE, JUNK\n~\n\n0 DRINK~",
"DONATE add See Also", CMD_FILE)

# EXITS
c = rep(c,
"provide some clues as to the existence of hidden exits and their names.\n~\n\n0 FLEE~",
"provide some clues as to the existence of hidden exits and their names.\n\nSee also: AUTOEXIT, SEARCH, LOOK\n~\n\n0 FLEE~",
"EXITS add See Also", CMD_FILE)

# FLEE — update old cross-ref
c = rep(c,
"See also helps on RESCUE, RECALL and WIMPY.\n~",
"See also: RESCUE, RECALL, WIMPY\n~",
"FLEE update See Also", CMD_FILE)

# FLIP MOVE PULL PUSH TURN
c = rep(c,
"Read room descriptions carefully in order to find\nobjects that you can manipulate.\n~\n\n0 FOLLOW GROUP ~",
"Read room descriptions carefully in order to find\nobjects that you can manipulate.\n\nSee also: LOOK, SEARCH, OPEN, CLIMB\n~\n\n0 FOLLOW GROUP ~",
"FLIP/MOVE/PULL add See Also", CMD_FILE)

# FOLLOW GROUP
c = rep(c,
"GROUP with no argument shows statistics for each character in your group.\n\nYou may FOLLOW anyone but you may only GROUP with characters within 8 levels\nof yourself.\n~",
"GROUP with no argument shows statistics for each character in your group.\n\nYou may FOLLOW anyone but you may only GROUP with characters within 8 levels\nof yourself.\n\nSee also: GTELL, SPLIT, NOFOLLOW, AUTOASSIST\n~",
"FOLLOW GROUP add See Also", CMD_FILE)

# GAIN
c = rep(c,
"to use a skill or the lowest level spell in a spellgroup.\n~\n\n0 GROUPS~",
"to use a skill or the lowest level spell in a spellgroup.\n\nSee also: TRAIN, PRACTICE, GROUPS, TEACHLIST, GAINLIST\n~\n\n0 GROUPS~",
"GAIN add See Also", CMD_FILE)

# GROUPS
c = rep(c,
"The GROUPS command shows which spell groups you have (both default and\ngroups that you have gained).\n~\n\n0 HEAL~",
"The GROUPS command shows which spell groups you have (both default and\ngroups that you have gained).\n\nSee also: GAIN, SKILLS, SPELLS\n~\n\n0 HEAL~",
"GROUPS add See Also", CMD_FILE)

# HEAL
c = rep(c,
"members of the cleric's guild), read help for HEALSPELL.\n~\n\n0 HELP~",
"members of the cleric's guild), read help for HEALSPELL.\n\nSee also: SCORE, AFFECT, RESTORE\n~\n\n0 HELP~",
"HEAL add See Also", CMD_FILE)

# JOIN
c = rep(c,
"See also help on GUILDS.\n~\n\n0 KILL~",
"See also: GUILDS, GAIN, GROUPS\n~\n\n0 KILL~",
"JOIN fix See Also", CMD_FILE)

# LORE
c = rep(c,
"better chance to identify cursed or hidden attributes.\n~\n\n0 AFK~",
"better chance to identify cursed or hidden attributes.\n\nSee also: COMPARE, IDENTIFY, INVENTORY\n~\n\n0 AFK~",
"LORE add See Also", CMD_FILE)

# NOFOLLOW
c = rep(c,
"check the status of the NOFOL flag with the AUTO command.\n~\n\n0 NOLOOT~",
"check the status of the NOFOL flag with the AUTO command.\n\nSee also: GROUP, FOLLOW, AUTO\n~\n\n0 NOLOOT~",
"NOFOLLOW add See Also", CMD_FILE)

# NOLOOT
c = rep(c,
"check the status of this flag with the AUTO command.\n~\n\n0 NOSUMMON~",
"check the status of this flag with the AUTO command.\n\nSee also: AUTO, NOSUMMON, NOFOLLOW\n~\n\n0 NOSUMMON~",
"NOLOOT add See Also", CMD_FILE)

# NOSUMMON
c = rep(c,
"The status of this flag can be checked with the AUTO command.\n~\n\n0 NOTE NOTES~",
"The status of this flag can be checked with the AUTO command.\n\nSee also: AUTO, NOLOOT, NOFOLLOW\n~\n\n0 NOTE NOTES~",
"NOSUMMON add See Also", CMD_FILE)

# NOTE NOTES
c = rep(c,
"You must be at least level 2 to use the note system.\n~\n\n0 ORDER~",
"You must be at least level 2 to use the note system.\n\nSee also: BUG, IDEA, TYPO, CHANNELS\n~\n\n0 ORDER~",
"NOTE add See Also", CMD_FILE)

# ORDER
c = rep(c,
"charmed aggressive mobs should not be brought outside the areas they are\nnormally found in.\n~\n\n0 OUTFIT~",
"charmed aggressive mobs should not be brought outside the areas they are\nnormally found in.\n\nSee also: GROUP, FOLLOW, CHARM PERSON\n~\n\n0 OUTFIT~",
"ORDER add See Also", CMD_FILE)

# PRACTICE
c = rep(c,
"each time you gain a level.  Unused sessions are saved until you do use them.\n~\n\n0 SAVE~",
"each time you gain a level.  Unused sessions are saved until you do use them.\n\nSee also: TRAIN, GAIN, SKILLS, SPELLS\n~\n\n0 SAVE~",
"PRACTICE add See Also", CMD_FILE)

# RUN
c = rep(c,
"Direction must be specified.\n~\n\n0 SACRIFICE~",
"Direction must be specified.\n\nSee also: RECALL, AUTOEXIT, EXITS\n~\n\n0 SACRIFICE~",
"RUN add See Also", CMD_FILE)

# SACRIFICE
c = rep(c,
"The nature of the reward depends upon the type of object.\n~\n\n0 SCAN~",
"The nature of the reward depends upon the type of object.\n\nSee also: JUNK, DONATE, AUTOSAC\n~\n\n0 SCAN~",
"SACRIFICE add See Also", CMD_FILE)

# SCAN
c = rep(c,
"You cannot scan through a closed door.\n~\n\n0 SCROLL~",
"You cannot scan through a closed door.\n\nSee also: SEARCH, TRACK, EXITS\n~\n\n0 SCROLL~",
"SCAN add See Also", CMD_FILE)

# SPLIT
c = rep(c,
"the AUTOSPLIT option.\n~\n\n0 TIME~",
"the AUTOSPLIT option.\n\nSee also: AUTOSPLIT, GROUP, GIVE\n~\n\n0 TIME~",
"SPLIT add See Also", CMD_FILE)

# TITLE
c = rep(c,
"advance a level.  You can use TITLE to set your title to something else.\n~\n\n0 TRAIN~",
"advance a level.  You can use TITLE to set your title to something else.\n\nSee also: DESCRIPTION, SCORE, WHO\n~\n\n0 TRAIN~",
"TITLE add See Also", CMD_FILE)

# TRAIN
c = rep(c,
"before training anything else.\n~\n\n0 VISIBLE~",
"before training anything else.\n\nSee also: PRACTICE, GAIN, SCORE, ATTRIBUTE\n~\n\n0 VISIBLE~",
"TRAIN add See Also", CMD_FILE)

# VISIBLE
c = rep(c,
"VISIBLE cancels your hiding and sneaking, as well as any invisibility,\nmaking you visible again.\n~\n\n0 WHERE~",
"VISIBLE cancels your hiding and sneaking, as well as any invisibility,\nmaking you visible again.\n\nSee also: HIDE, SNEAK, STEALTH\n~\n\n0 WHERE~",
"VISIBLE add See Also", CMD_FILE)

# SKILLS SPELLS
c = rep(c,
"listed where applicable.\n\nSee also help for GAIN and GROUPS.\n~\n\n0 SPLIT~",
"listed where applicable.\n\nSee also: GAIN, GROUPS, PRACTICE\n~\n\n0 SPLIT~",
"SKILLS SPELLS fix See Also", CMD_FILE)

# BRIEF
c = rep(c,
"The default is for brief to be off.\n~\n\n0 BUY~",
"The default is for brief to be off.\n\nSee also: COMPACT, COMBINE, PROMPT\n~\n\n0 BUY~",
"BRIEF add See Also", CMD_FILE)

# CLIMB
c = rep(c,
"In order to get between certain rooms, you must CLIMB a rope, ladder or\nother object.  Read room descriptions carefully to find the object you need\nto climb.\n~\n\n0 COLOR~",
"In order to get between certain rooms, you must CLIMB a rope, ladder or\nother object.  Read room descriptions carefully to find the object you need\nto climb.\n\nSee also: JUMP, CRAWL, EXITS\n~\n\n0 COLOR~",
"CLIMB add See Also", CMD_FILE)

# COLOR
c = rep(c,
"COLOR gossips 7\n~\n\n0 COMBINE~",
"COLOR gossips 7\n\nSee also: PROMPT, COMPACT, BRIEF\n~\n\n0 COMBINE~",
"COLOR add See Also", CMD_FILE)

# COMBINE
c = rep(c,
"inventory again.  The default is for combine to be on.\n~\n\n0 COMMANDS~",
"inventory again.  The default is for combine to be on.\n\nSee also: INVENTORY, COMPACT, BRIEF\n~\n\n0 COMMANDS~",
"COMBINE add See Also", CMD_FILE)

# ALIAS ALIASES
c = rep(c,
"There is a max of 20 aliases per character.\n~\n\n0 AREAS~",
"There is a max of 20 aliases per character.\n\nSee also: COMMANDS, HELP\n~\n\n0 AREAS~",
"ALIAS add See Also", CMD_FILE)

# AREAS
c = rep(c,
"somewhere that may be particularly dangerous.\n~\n\n0 ARRIVE~",
"somewhere that may be particularly dangerous.\n\nSee also: WHERE, RECALL\n~\n\n0 ARRIVE~",
"AREAS add See Also", CMD_FILE)

# CHANNELS
c = rep(c,
"To toggle the on/off status of a channel, type the name of that channel.\n~",
"To toggle the on/off status of a channel, type the name of that channel.\n\nSee also: GOSSIP, SHOUT, TELL, SAY, DEAF, QUIET\n~",
"CHANNELS add See Also", CMD_FILE)

# PASSWORD
c = rep(c,
"The PASSWORD command is protected against being snooped or logged.\n~\n\n0 PRACTICE~",
"The PASSWORD command is protected against being snooped or logged.\n\nSee also: DELETE, QUIT, SAVE\n~\n\n0 PRACTICE~",
"PASSWORD add See Also", CMD_FILE)

# WIMPY
c = rep(c,
"Some monsters are wimpy.\n~\n\n0 !\n~",
"Some monsters are wimpy.\n\nSee also: FLEE, RECALL, SCORE\n~\n\n0 !\n~",
"WIMPY add See Also", CMD_FILE)

# BUG IDEA TYPO
c = rep(c,
"it is preferable to use the bug and idea note forums.  See help NOTE for\nmore information.\n~\n\n0 DEAF~",
"it is preferable to use the bug and idea note forums.  See help NOTE for\nmore information.\n\nSee also: NOTE\n~\n\n0 DEAF~",
"BUG IDEA TYPO add See Also", CMD_FILE)

# CRAWL
c = rep(c,
"Type STAND\nor CRAWL again to return to a normal posture.\n\nSee also: JUMP, STAND, SNEAK\n~",
"Type STAND\nor CRAWL again to return to a normal posture.\n\nSee also: JUMP, STAND, SNEAK\n~",
"CRAWL See Also (no-op if already present)", CMD_FILE)

# COUNT — add See Also
c = rep(c,
"into the mud.  It also displays the highest number observed that day, if\nit is higher.\n~\n\n0 DELETE~",
"into the mud.  It also displays the highest number observed that day, if\nit is higher.\n\nSee also: WHO, WHERE\n~\n\n0 DELETE~",
"COUNT add See Also", CMD_FILE)

write_file(CMD_FILE, c)
print("commands.are written.")

# -------------------------------------------------------
# Verification report
# -------------------------------------------------------
print(f"\n=== Applied ({len(applied)}) ===")
for a in applied:
    print(f"  + {a}")

if warnings:
    print(f"\n=== Warnings ({len(warnings)}) ===")
    for w in warnings:
        print(f"  ! {w}")
else:
    print("\nNo warnings. All replacements succeeded.")

# Quick sanity: look for stray combined entries
final_cmd = read_file(CMD_FILE)
combined_markers = [
    "0 ENTER RIDE MOUNT~",
    "0 TELEKINESIS TK CLAIRVOYANCE DANGER PROJECT SHIFT~",
    "0 BANK BALANCE DEPOSIT WITHDRAW CONVERT~",
    "0 BREW CONCOCT SCRIBE SHOOT PICK JUNK~",
    "0 CRANE FISTS~",
    "0 HIT MURDER MURDE~",
    "0 ARRIVE DEPART~",
    "0 AUTO AUTOLIST AUTOLOOT AUTOGOLD AUTOSAC AUTOEXIT AUTOASSIST AUTOSPLIT~",
    "0 BRANDISH QUAFF RECITE ZAP~",
    "0 BUY LIST SELL VALUE~",
    "0 OPEN CLOSE LOCK UNLOCK~",
    "0 DRINK EAT FILL~",
    "0 DROP GET GIVE PUT TAKE~",
    "0 EMOTE , POSE SOCIAL SOCIALS~",
    "0 HOLD REMOVE WEAR WIELD~",
    "0 KILL PKILL MURDER~",
    "0 GOSSIP . INFO LEVELING MUSIC Q/A SHOUT YELL~",
    "0 GTELL REPLY SAY TELL~",
    "0 REST SLEEP STAND WAKE SIT~",
    "0 EXAMINE LOOK READ~",
]
print("\n=== Combined-entry sanity check ===")
for marker in combined_markers:
    if marker in final_cmd:
        print(f"  STILL PRESENT: {marker}")
    else:
        print(f"  removed OK:    {marker}")

# Check for duplicate help.are entries
final_help = read_file(HELP_FILE)
help_dupes = ["0 CAST~", "0 !~", "0 NORTH SOUTH EAST WEST UP DOWN~", "-1 PROMPT~"]
print("\n=== help.are duplicate check ===")
for d in help_dupes:
    if d in final_help:
        print(f"  STILL PRESENT: {d}")
    else:
        print(f"  removed OK:    {d}")

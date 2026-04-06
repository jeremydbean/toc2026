#!/usr/bin/env python3
"""
Second-pass help file quality improvements:
- Fix help.are: DAMAGE table (remove duplicate), update SUMMARY, add See Also to dragon breaths
- Improve commands.are: thin entries, missing See Also, add PSIONICS and DUAL WIELD entries
"""
import re

COMMANDS = "area/commands.are"
HELP     = "area/help.are"

def read_file(path):
    with open(path, encoding="latin-1") as f:
        return f.read()

def write_file(path, content):
    import tempfile, shutil
    try:
        content.encode("latin-1")
    except UnicodeEncodeError as e:
        print(f"  ERROR: non-latin-1 char in content for {path}: {e}")
        return
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="latin-1", newline="\n") as f:
        f.write(content)
    shutil.move(tmp, path)

def replace_once(content, old, new, label):
    count = content.count(old)
    if count == 0:
        print(f"  WARNING: '{label}' -- pattern NOT FOUND")
        return content
    if count > 1:
        print(f"  WARNING: '{label}' -- {count} matches; replacing first only")
    return content.replace(old, new, 1)

# ─────────────────────────────────────────────────────────────────────────────
# HELP.ARE CHANGES
# ─────────────────────────────────────────────────────────────────────────────

help_content = read_file(HELP)

# 1. Update the old -1 SUMMARY to match current commands.are content
OLD_SUMMARY = """-1 SUMMARY~
MOVEMENT                            GROUP
north south east west up down       follow group gtell split
exits recall
sleep wake rest stand

OBJECTS                             INFORMATION / COMMUNICATION
get put drop give sacrifice         help credits commands areas
wear wield hold                     report score time weather where who
recite quaff zap brandish           description password title
lock unlock open close pick         bug idea typo
inventory equipment look compare    auction gossip say shout tell yell
eat drink fill                      emote pose
list buy sell value                 note

COMBAT                              OTHER
kill flee kick rescue disarm        ! save quit
backstab cast wimpy                 practice train


For more help, type 'help <topic>' for any command, skill, or spell.
Also help on: DAMAGE DEATH EXPERIENCE NEWS STORY TICK WIZLIST
~"""

NEW_SUMMARY = """-1 SUMMARY~
MOVEMENT                            GROUP
north south east west up down       follow group gtell split
northeast ne northwest nw
southeast se southwest sw
run exits recall
sleep wake rest stand

OBJECTS                             INFORMATION
get put drop give sacrifice         help credits commands areas socials
wear wield hold                     report score time weather where who
recite quaff zap brandish           color description password title
lock unlock open close pick         gainlist teachlist
inventory equipment look compare
eat drink fill
list buy sell value
move climb flip push pull turn

COMMUNICATION
gossip leveling music q/a
shout quiet info yell
say tell gtell reply
emote pose note channels

COMBAT                              OTHER
kill flee kick rescue disarm        ! save quit
dirt-kick backstab cast wimpy       practice train
bash

For more help, type 'help <topic>' for any command, skill, or spell.
Type 'help KEYWORD' to see a list of all of the available topics.
Also help on: DAMAGE DYING EXPERIENCE NEWS STORY TICK WIZLIST GUILDS
If you are new here, we recommend that you read BEGINNERS.
~"""

help_content = replace_once(help_content, OLD_SUMMARY, NEW_SUMMARY, "help.are SUMMARY")

# 2. Fix DAMAGE table -- replace incorrect/duplicate table with accurate one from source
OLD_DAMAGE = """0 DAMAGE~
When one character attacks another, the severity of the damage is shown in the
verb used in the damage message.  Here are all the damage verbs listed from
least damage to most damage:

    miss        wound           MUTILATE        DEMOLISH
    scratch     maul            DISEMBOWEL      DEVASTATE
    graze       decimate        DISMEMBER\tOBLITERATE
    hit         devastate       MASSACRE\tANNIHILATE
    injure      maim  \t\tMANGLE\t\tERADICATE

    And, at the far reaches of damaging power, you can do unspeakable things.
~"""

NEW_DAMAGE = """0 DAMAGE~
When one character attacks another, the severity of the damage is shown in the
verb used in the damage message.  Listed from least damage to most damage:

    miss          wound          MUTILATE       *** DEMOLISH ***
    scratch       maul           DISEMBOWEL     *** DEVASTATE ***
    graze         decimate       DISMEMBER      ^^^ DESTROY ^^^
    hit           devastate      MASSACRE       === OBLITERATE ===
    injure        maim           MANGLE         <<< ERADICATE >>>
                                                >>> ANNIHILATE <<<

    At the far reaches of damaging power: "do UNSPEAKABLE things to"
~"""

help_content = replace_once(help_content, OLD_DAMAGE, NEW_DAMAGE, "help.are DAMAGE table")

# 3. Add See Also to dragon breath spells entry
OLD_DRAGONBREATH = """0 'ACID BREATH' 'FIRE BREATH' 'FROST BREATH' 'GAS BREATH' 'LIGHTNING BREATH'~
Syntax: cast 'acid breath'      <victim>
Syntax: cast 'fire breath'      <victim>
Syntax: cast 'frost breath'     <victim>
Syntax: cast 'gas breath'
Syntax: cast 'lightning breath' <victim>

These spells are for the use of dragons.  Acid, fire, frost, and lightning
damage one victim, whereas gas damages every PC in the room.  Fire and
frost can break objects, and acid can damage armor.

High level mages may learn and cast these spells as well.
~"""

NEW_DRAGONBREATH = """0 'ACID BREATH' 'FIRE BREATH' 'FROST BREATH' 'GAS BREATH' 'LIGHTNING BREATH'~
Syntax: cast 'acid breath'      <victim>
Syntax: cast 'fire breath'      <victim>
Syntax: cast 'frost breath'     <victim>
Syntax: cast 'gas breath'
Syntax: cast 'lightning breath' <victim>

These spells are for the use of dragons.  Acid, fire, frost, and lightning
damage one victim, whereas gas damages every PC in the room.  Fire and
frost can break objects, and acid can damage armor.

High level mages may learn and cast these spells as well.

See also: CAST, SPELLS, PRACTICE
~"""

help_content = replace_once(help_content, OLD_DRAGONBREATH, NEW_DRAGONBREATH, "help.are dragon breaths See Also")

write_file(HELP, help_content)
print("help.are written.")

# ─────────────────────────────────────────────────────────────────────────────
# COMMANDS.ARE CHANGES
# ─────────────────────────────────────────────────────────────────────────────

cmd_content = read_file(COMMANDS)

# 1. NE entry -- add See also
OLD_NE = """0 NE NORTHEAST NW NORTHWEST SE SOUTHEAST SW SOUTHWEST~
Syntax: <direction>

These are shorthand movement commands for the diagonal exits in a room.
Each direction functions the same way as typing the full diagonal, for
example "ne" moves northeast and "sw" moves southwest.  If the exit exists
and is open, you will step through it; otherwise you will be told the way
is closed or blocked.
~"""

NEW_NE = """0 NE NORTHEAST NW NORTHWEST SE SOUTHEAST SW SOUTHWEST~
Syntax: <direction>

These are shorthand movement commands for the diagonal exits in a room.
Each direction functions the same way as typing the full diagonal, for
example "ne" moves northeast and "sw" moves southwest.  If the exit exists
and is open, you will step through it; otherwise you will be told the way
is closed or blocked.

See also: NORTH, EXITS, RUN
~"""

cmd_content = replace_once(cmd_content, OLD_NE, NEW_NE, "NE See also")

# 2. CASTLE -- add See also
OLD_CASTLE = """0 CASTLE~
Syntax: castle
Syntax: castle <message>

Castle chat is the private channel for members of your castle.  Typing
castle with no arguments toggles whether you hear castle chat.  Supplying a
message sends it to every logged-in member of your castle.  Synonyms: CC and
"-".
~"""

NEW_CASTLE = """0 CASTLE~
Syntax: castle
Syntax: castle <message>

Castle chat is the private channel for members of your castle.  Typing
castle with no arguments toggles whether you hear castle chat.  Supplying a
message sends it to every logged-in member of your castle.  Synonyms: CC and
"-".

See also: CHANNELS, CGOS, CC
~"""

cmd_content = replace_once(cmd_content, OLD_CASTLE, NEW_CASTLE, "CASTLE See also")

# 3. IGNORE -- add See also
OLD_IGNORE = """0 IGNORE~
Syntax: ignore <name>
        ignore none
        ignore list

Adds or removes players from a personal ignore list.  Characters on your
ignore list cannot contact you via tells or channels.  The LIST option shows
who you are currently ignoring; NONE clears the entire list.
~"""

NEW_IGNORE = """0 IGNORE~
Syntax: ignore <name>
        ignore none
        ignore list

Adds or removes players from a personal ignore list.  Characters on your
ignore list cannot contact you via tells or channels.  The LIST option shows
who you are currently ignoring; NONE clears the entire list.

See also: TELL, REPLY, AFK
~"""

cmd_content = replace_once(cmd_content, OLD_IGNORE, NEW_IGNORE, "IGNORE See also")

# 4. LISTEN -- expand description
OLD_LISTEN = """0 LISTEN~
Syntax: listen

Listen provides a short ambient description of the sounds around you in your
current room.  It is helpful for spotting nearby activity without moving.
~"""

NEW_LISTEN = """0 LISTEN~
Syntax: listen

LISTEN receives a brief ambient sound description of your current room:
wind through cracks, distant dripping water, faint movement in the
shadows, and other atmospheric details that add flavor to the environment.
The description varies by room type and current conditions.

LISTEN is a flavor command, not a tactical warning.  It does not reveal
hidden characters or notify you of nearby enemies.  Use SEARCH to
uncover hidden exits or traps, and SCAN to see what mobs are in
adjacent rooms.

See also: SEARCH, SCAN, LOOK
~"""

cmd_content = replace_once(cmd_content, OLD_LISTEN, NEW_LISTEN, "LISTEN expand")

# 5. REPAIR -- expand + See also
OLD_REPAIR = """0 REPAIR~
Syntax: repair <object>

Requests repairs from an NPC repair vendor on worn equipment.  The shopkeeper
will quote and charge a gold cost based on condition and item type before
restoring durability.  If the item cannot be repaired, you will be told why.
~"""

NEW_REPAIR = """0 REPAIR~
Syntax: repair <object>

Requests repairs from an NPC repair vendor on worn equipment.  The shopkeeper
quotes and charges a gold cost based on the item's current condition and type
before restoring it to full durability.  If the item cannot be repaired you
will be told why.

Repair vendors are found in some guild halls, market districts, and weapon or
armor shops throughout the world.  Not all shopkeepers offer repair services;
look for vendors who mention repairs in their room description or greeting.

See also: VALUE, BUY, LIST
~"""

cmd_content = replace_once(cmd_content, OLD_REPAIR, NEW_REPAIR, "REPAIR expand + See also")

# 6. SECONDARY -- add See also
OLD_SECONDARY = """0 SECONDARY~
Syntax: secondary <weapon>

Equips the specified weapon in your off-hand if you have trained the
SECONDARY weapon skill.  This toggles dual wielding; to return to a single
weapon, wield your main-hand weapon normally.
~"""

NEW_SECONDARY = """0 SECONDARY~
Syntax: secondary <weapon>

Equips the specified weapon in your off-hand if you have trained the
SECONDARY weapon skill.  This toggles dual wielding; to return to a single
weapon, wield your main-hand weapon normally.

Dual wielding with low skill imposes accuracy penalties to both weapons.
As your SECONDARY skill improves, the off-hand penalty diminishes.  Smaller
or lighter weapons are generally better choices for the off hand.

See also: WIELD, DISARM, DUAL WIELD
~"""

cmd_content = replace_once(cmd_content, OLD_SECONDARY, NEW_SECONDARY, "SECONDARY See also + expand")

# 7. DELET DELETE -- improve (add password note + See also)
OLD_DELET = """0 DELET DELETE~
Syntax: delet
Syntax: delete

DELET is a safety guard that prepares you for character deletion.  Typing
DELETE after using DELET fully confirms removal of your character file.  Use
with caution; deleted characters cannot be recovered without immortal aid.
~"""

NEW_DELET = """0 DELET DELETE~
Syntax: delet
Syntax: delete <password>

DELET is a safety guard for character deletion.  First type DELET alone to
arm the command, then confirm with DELETE <yourpassword>.  Both steps must be
done in sequence to complete the deletion.

Deletion is permanent.  The character's name becomes available for other
players and will not be restored by immortals.  All equipment and bank gold
are permanently lost.

See also: PASSWORD, QUIT, SAVE
~"""

cmd_content = replace_once(cmd_content, OLD_DELET, NEW_DELET, "DELET DELETE improve")

# 8. PROMPT -- add See also
OLD_PROMPT = """0 PROMPT~
Syntax: prompt
Syntax: prompt <format string>
Syntax: prompt all

Customizes the prompt shown at the bottom of your screen.  PROMPT with no
arguments shows your current setting; PROMPT ALL sets a detailed default.
Placeholders such as %h for hit points, %m for mana, %v for movement, %g for
gold, and %r for room name may be used to build your own display.
~"""

NEW_PROMPT = """0 PROMPT~
Syntax: prompt
Syntax: prompt <format string>
Syntax: prompt all

Customizes the prompt shown at the bottom of your screen.  PROMPT with no
arguments shows your current setting; PROMPT ALL sets a detailed default.
Placeholders such as %h for hit points, %m for mana, %v for movement, %g for
gold, and %r for room name may be used to build your own display.

See also: COLOR, COMPACT, BRIEF
~"""

cmd_content = replace_once(cmd_content, OLD_PROMPT, NEW_PROMPT, "PROMPT See also")

# 9. COUNT -- add See also
OLD_COUNT = """0 COUNT~
The count command displays the number of people (that you can see) logged
into the mud.  It also displays the highest number observed that day, if
it is higher.

See also: WHO, WHERE
~"""
# Already has See also -- check if we need to update it
# Actually looking at my reads, COUNT currently says "See also: WHO, WHERE"... 
# Let me check exact content
if "0 COUNT~" in cmd_content:
    # Only replace if it doesn't already have See also
    old_count_no_sa = """0 COUNT~
The count command displays the number of people (that you can see) logged
into the mud.  It also displays the highest number observed that day, if
it is higher.
~"""
    new_count_with_sa = """0 COUNT~
The count command displays the number of people (that you can see) logged
into the mud.  It also displays the highest number observed that day, if
it is higher.

See also: WHO, WHERE
~"""
    if old_count_no_sa in cmd_content:
        cmd_content = replace_once(cmd_content, old_count_no_sa, new_count_with_sa, "COUNT See also")
    else:
        print("  INFO: COUNT already has See also, skipping.")

# 10. SCROLL (page length) -- add See also
OLD_SCROLL = """0 SCROLL~
Syntax: scroll
Syntax: scroll <number>

This command changes the number of lines the mud sends you in a page (the
default is 24 lines).  Change this to a higher number for larger screen
sizes, or to 0 to disabling paging.
~"""

NEW_SCROLL = """0 SCROLL~
Syntax: scroll
Syntax: scroll <number>

This command changes the number of lines the mud sends you in a page (the
default is 24 lines).  Change this to a higher number for larger screen
sizes, or to 0 to disable paging.

See also: BRIEF, COMPACT, PROMPT
~"""

cmd_content = replace_once(cmd_content, OLD_SCROLL, NEW_SCROLL, "SCROLL See also + fix typo")

# 11. WHERE -- add See also
OLD_WHERE = """0 WHERE~
Syntax: where
Syntax: where <character>

WHERE without an argument tells you the location of visible players in the same
area as you are.

WHERE with an argument tells you the location of one character with that name
within your area, including monsters.
~"""

NEW_WHERE = """0 WHERE~
Syntax: where
Syntax: where <character>

WHERE without an argument tells you the location of visible players in the same
area as you are.

WHERE with an argument tells you the location of one character with that name
within your area, including monsters.

See also: WHO, SCAN, AREAS
~"""

cmd_content = replace_once(cmd_content, OLD_WHERE, NEW_WHERE, "WHERE See also")

# 12. EXCHANGE -- add See also
OLD_EXCHANGE = """51 EXCHANGE~

Syntax: exchange

If you are a hero, you may exchange experience for more practices.  The cost
is 5000 experience points.  This means that if you would rather get more
practices rather than another level, exchange the experience before leveling.
Otherwise you'll have to get 5000 more experience up and above your new level.
Exchanging experience for practices gives you 4-6 more; the exact number of
practices you get is random.  You may exchange only at the guru in Hero Hall.
~"""

NEW_EXCHANGE = """51 EXCHANGE~
Syntax: exchange

If you are a hero, you may exchange experience for more practices.  The cost
is 5000 experience points.  This means that if you would rather get more
practices rather than another level, exchange the experience before leveling.
Otherwise you'll have to get 5000 more experience up and above your new level.
Exchanging experience for practices gives you 4-6 more; the exact number of
practices you get is random.  You may exchange only at the guru in Hero Hall.

See also: PRACTICE, GAIN, TRAIN, WORTH
~"""

cmd_content = replace_once(cmd_content, OLD_EXCHANGE, NEW_EXCHANGE, "EXCHANGE See also")

# 13. TEACHLIST -- improve + See also
OLD_TEACHLIST = """5 TEACHLIST~
Syntax: teachlist

This will show you a list of guildmasters and what they can teach you for skills/
spells. Some spells/skills will require that you learn the group they are in.
So also check out the gainlist command.
~"""

NEW_TEACHLIST = """5 TEACHLIST~
Syntax: teachlist

TEACHLIST shows a list of guildmasters and what they can teach you for
skills and spells.  Each entry shows the trainer, their location, and the
skill or spell they offer.  Some skills require that you first gain the
group they belong to before you can practice them.

Use GAINLIST to see which skill groups are available for purchase, and
PRACTICE to improve skills once you have learned them.

See also: GAINLIST, GAIN, PRACTICE, TRAIN
~"""

cmd_content = replace_once(cmd_content, OLD_TEACHLIST, NEW_TEACHLIST, "TEACHLIST improve")

# 14. GAINLIST -- improve + See also
OLD_GAINLIST = """5 GAINLIST~
Syntax: gainlist

This will show you a list of guildmasters and what they will allow you to gain
for skills/spells. For information on every group you can consult the help.
The command teachlist will show you where you can learn which spell. So also
check out the teachlist command.
~"""

NEW_GAINLIST = """5 GAINLIST~
Syntax: gainlist

GAINLIST shows a list of guildmasters and the skill groups or individual
skills they will allow you to GAIN.  Gaining a skill or group costs training
sessions (not practice sessions).  For a description of each group, consult
HELP GROUPS.  For a list of who teaches individual skills once you have
gained them, see TEACHLIST.

See also: TEACHLIST, GAIN, GROUPS, TRAIN
~"""

cmd_content = replace_once(cmd_content, OLD_GAINLIST, NEW_GAINLIST, "GAINLIST improve")

# 15. EDIT -- expand (currently nearly empty, level 65)
OLD_EDIT = """65 EDIT~
Syntax: edit <field> <arguments>
Where field is exit
~"""

NEW_EDIT = """65 EDIT~
Syntax: edit exit <direction> <field> <value>

EDIT modifies live room exit data without requiring a full area reload.
The only currently supported field is 'exit', which lets you adjust exit
flags, door states, or key vnums on the fly for testing or event purposes.

Use STAT ROOM to inspect current exit values before editing.  Changes made
with EDIT persist only until the next area reset or reboot; they are not
written to the area file.

See also: STAT, GOTO, REPOP
~"""

cmd_content = replace_once(cmd_content, OLD_EDIT, NEW_EDIT, "EDIT expand")

# 16. SHOWHUNT -- expand
OLD_SHOWHUNT = """62 SHOWHUNT~
Syntax: showhunt

Shows the number of hunting mobs in the game.
~"""

NEW_SHOWHUNT = """62 SHOWHUNT~
Syntax: showhunt

SHOWHUNT reports how many mobile NPCs currently have an active hunt target
set.  Hunting mobs pursue their targets across rooms until the quarry is
killed, escapes too far, or the hunt expires.  High hunt counts can affect
server performance; this command helps staff identify if hunting behavior
is running out of control.

See also: HPARDON, MWHERE
~"""

cmd_content = replace_once(cmd_content, OLD_SHOWHUNT, NEW_SHOWHUNT, "SHOWHUNT expand")

# 17. HPARDON -- expand
OLD_HPARDON = """62 HPARDON~
Syntax: hpardon <character>
        hpardon all

Stops a hunt.
~"""

NEW_HPARDON = """62 HPARDON~
Syntax: hpardon <character>
        hpardon all

HPARDON cancels any active hunts targeting the specified character, causing
all mobs currently pursuing them to abandon the chase.  HPARDON ALL clears
every active hunt in the game simultaneously.

Use this when a hunt becomes stuck, when a player is being griefed by
relentless hunting mobs after a crash or bug, or to clean up testing.

See also: SHOWHUNT
~"""

cmd_content = replace_once(cmd_content, OLD_HPARDON, NEW_HPARDON, "HPARDON expand")

# 18. WIZINFO -- expand
OLD_WIZINFO = """63 WIZINFO~
Syntax: wizinfo

WIZINFO toggles whether or not you see WIZINFO messages, telling you who
has logged in, logged out, lost link, etc..
~"""

NEW_WIZINFO = """63 WIZINFO~
Syntax: wizinfo
Syntax: wizinfo <message>

WIZINFO with no argument toggles whether you receive the stream of automatic
staff notifications: logins, logouts, link-death events, level-ups, and other
significant game events flagged with LOG_ALWAYS.  Most immortals keep this
enabled.

WIZINFO with a message broadcasts that message to all immortals who have
WIZINFO enabled, similar to an immortal-only announcement channel.  Use it
to coordinate with staff, warn about reboots, or share important information.

See also: IMMTALK, GODTALK, ANNOUNCE
~"""

cmd_content = replace_once(cmd_content, OLD_WIZINFO, NEW_WIZINFO, "WIZINFO expand")

# 19. ECHO -- fix See also (remove RECHO which is not a user-visible command)
OLD_ECHO_SA = """See also: GECHO, PECHO, RECHO
~"""
NEW_ECHO_SA = """See also: GECHO, PECHO
~"""
# Only replace the one inside the ECHO entry -- there's only one RECHO reference
cmd_content = replace_once(cmd_content, OLD_ECHO_SA, NEW_ECHO_SA, "ECHO remove RECHO from See also")

# 20. Add PSIONICS overview entry (insert before the QUIT entry)
# We'll insert it near the other psionic commands (after PSYCHIC entry)
OLD_PSYCHIC_END = """0 PSYCHIC~
Syntax: psychic

Toggle psychic resonance mode.  An advanced psionic state that enhances
all active mental abilities: MINDBAR becomes stronger, psionic attack
spells deal more damage, and your saves against mental effects improve.
PSYCHIC mode requires substantial psionic training and drains mana
steadily while active.  It cannot be combined with IRON or ROLL stances.

See also: PSIONIC, MINDBAR, PSIONICS
~"""

NEW_PSYCHIC_WITH_PSIONICS = """0 PSYCHIC~
Syntax: psychic

Toggle psychic resonance mode.  An advanced psionic state that enhances
all active mental abilities: MINDBAR becomes stronger, psionic attack
spells deal more damage, and your saves against mental effects improve.
PSYCHIC mode requires substantial psionic training and drains mana
steadily while active.  It cannot be combined with IRON or ROLL stances.

See also: PSIONIC, MINDBAR, PSIONICS
~

0 PSIONICS~
Psionics are mental disciplines available to characters who have remorted at
least twice (remort 2+).  Upon qualifying, you automatically receive 4
randomly chosen skills from each of 4 psionic disciplines (16 total possible
skills spread across the disciplines).  At remort 5 (final) all 16 psionic
skills are granted.

PSIONIC DISCIPLINES

  Telepathy:   clairvoyance, danger (sense), project (astral scout),
               astral walk, shift (teleport to player)

  Kinesis:     telekinesis (TK), levitate, mindblast, ego whip,
               mind leech

  Control:     confuse, nightmare, torment, enervate, transfusion

  Defense:     mindbar, psionic armor, psychic shield, psionic (awareness),
               psychic (resonance mode)

PASSIVE BENEFITS
  Remort 2+: access to psionic skills; immune to hunger and thirst.
  Remort 4+: recall always succeeds (no skill check).
  Remort 5:  all 16 psionic skills granted; unlimited carry capacity.

RESOURCE COST
  Most psionic skills draw from your mana pool.  Some toggles (MINDBAR,
  PSIONIC, PSYCHIC, STEALTH, etc.) maintain a small per-tick mana drain while
  active.

See also: REMORT, MINDBAR, PSIONIC, PSYCHIC, TELEKINESIS, CLAIRVOYANCE,
          MINDBLAST, CONFUSE, NIGHTMARE, TORMENT, ENERVATE, TRANSFUSION,
          ASTRAL WALK, EGO WHIP
~"""

cmd_content = replace_once(cmd_content, OLD_PSYCHIC_END, NEW_PSYCHIC_WITH_PSIONICS, "Add PSIONICS entry after PSYCHIC")

# 21. Add DUAL WIELD entry (insert after SECONDARY entry)
OLD_SECONDARY_END = """0 SECONDARY~
Syntax: secondary <weapon>

Equips the specified weapon in your off-hand if you have trained the
SECONDARY weapon skill.  This toggles dual wielding; to return to a single
weapon, wield your main-hand weapon normally.

Dual wielding with low skill imposes accuracy penalties to both weapons.
As your SECONDARY skill improves, the off-hand penalty diminishes.  Smaller
or lighter weapons are generally better choices for the off hand.

See also: WIELD, DISARM, DUAL WIELD
~"""

NEW_SECONDARY_WITH_DUAL = """0 SECONDARY~
Syntax: secondary <weapon>

Equips the specified weapon in your off-hand if you have trained the
SECONDARY weapon skill.  This toggles dual wielding; to return to a single
weapon, wield your main-hand weapon normally.

Dual wielding with low skill imposes accuracy penalties to both weapons.
As your SECONDARY skill improves, the off-hand penalty diminishes.  Smaller
or lighter weapons are generally better choices for the off hand.

See also: WIELD, DISARM, DUAL WIELD
~

0 DUAL WIELD~
Dual wielding is the act of fighting with a weapon in each hand
simultaneously.  To dual wield you must:
  1. Have the SECONDARY skill (gain it from a trainer).
  2. WIELD your main weapon normally.
  3. Use SECONDARY <weapon> to equip the off-hand weapon.

Off-hand accuracy starts lower than the main hand and improves as your
SECONDARY skill increases.  Lighter weapons work better in the off hand;
very heavy or two-handed weapons cannot be used this way.

To return to single-weapon combat, WIELD your main weapon again -- this
replaces the off-hand weapon.  You can also use REMOVE on the off-hand
item, but WIELD is faster.

See also: SECONDARY, WIELD, DISARM
~"""

cmd_content = replace_once(cmd_content, OLD_SECONDARY_END, NEW_SECONDARY_WITH_DUAL, "Add DUAL WIELD entry after SECONDARY")

write_file(COMMANDS, cmd_content)
print("commands.are written.")
print("Done.")

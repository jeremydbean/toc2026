#!/usr/bin/env python3
"""
Pass 12 — Add See Also to remaining commands.are entries (mostly immortal
commands plus a few player-accessible entries).
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

print("\n=== commands.are ===")
cm = read_file('commands.are')
ok_cm = 0

changes = [
    # ──────────────────────────────────────────
    # Player-accessible commands
    # ──────────────────────────────────────────
    (
        "SUMMARY",
        "ly commands are documented under WIZHELP and will not appear to\nnon-immortals.\n~",
        "ly commands are documented under WIZHELP and will not appear to\nnon-immortals.\n\nSee also: COMMANDS, WIZHELP\n~",
    ),
    (
        "CAST — replace informal see-also with formal",
        "See also the help sections for individual spells.\n~",
        "See also: SPELLGROUP, SPELLS, GAIN\n~",
    ),
    (
        "CREDITS",
        "This command shows the list of the original Diku Mud implementors.\n~",
        "This command shows the list of the original Diku Mud implementors.\n\nSee also: DIKU, MERC, ROM\n~",
    ),
    (
        "! repeat command",
        "! repeats the last command you typed.\n~",
        "! repeats the last command you typed.\n\nSee also: COMMANDS\n~",
    ),
    (
        "' SAY channel",
        "Use TELL for private messages to individuals, or GOSSIP\nfor world-wide chat.\n~",
        "Use TELL for private messages to individuals, or GOSSIP\nfor world-wide chat.\n\nSee also: TELL, GOSSIP, YELL\n~",
    ),
    (
        "; GTELL group-tell",
        "Note that you must have no space between the semicolon and your\nmessage.\n~",
        "Note that you must have no space between the semicolon and your\nmessage.\n\nSee also: TELL, GOSSIP, GROUP\n~",
    ),
    # ──────────────────────────────────────────
    # Low immortal commands (62–63)
    # ──────────────────────────────────────────
    (
        "GOTO room nav",
        "Some other rooms are barred to players below a certain\ngod level.\n~",
        "Some other rooms are barred to players below a certain\ngod level.\n\nSee also: TRANSFER, AT, STAT\n~",
    ),
    (
        "CLOAK visibility",
        "higher level than the level you set your cloak at can see you anywhere though.\n~",
        "higher level than the level you set your cloak at can see you anywhere though.\n\nSee also: WIZHELP, IMMORTAL\n~",
    ),
    (
        "QFLAG flag removal",
        "The flag will automatically be removed when\nthe player quits otherwise.\n\n~",
        "The flag will automatically be removed when\nthe player quits otherwise.\n\nSee also: WIZHELP, IMMORTAL\n\n~",
    ),
    (
        "WIZHELP list",
        "Wizhelp provides a list of all the immortal commands available to you.\n~",
        "Wizhelp provides a list of all the immortal commands available to you.\n\nSee also: COMMANDS, SUMMARY\n~",
    ),
    (
        "RENAME player file",
        "the old player file is deleted and replaced with a new\none under the new name immediately.\n~",
        "the old player file is deleted and replaced with a new\none under the new name immediately.\n\nSee also: STAT, PURGE\n~",
    ),
    (
        "AREAVNUMS vnum list",
        "300 abbeyrd   301 abbeyrd      302 finalj       303 finalj\n~",
        "300 abbeyrd   301 abbeyrd      302 finalj       303 finalj\n\nSee also: VNUM, MEMORY\n~",
    ),
    (
        "CLONE object copy",
        "Strung extended descriptions on objects are not kept, however.\n~",
        "Strung extended descriptions on objects are not kept, however.\n\nSee also: LOAD, VNUM, STRING\n~",
    ),
    (
        "FORCE execute command",
        "This is typically used for 'force all save'.\n~",
        "This is typically used for 'force all save'.\n\nSee also: TRANSFER, AT, SOCKETS\n~",
    ),
    (
        "SOCKETS player list",
        "Example:  socket ip nowhere.com\n\n~",
        "Example:  socket ip nowhere.com\n\nSee also: TRANSFER, STAT, MEMORY\n\n~",
    ),
    (
        "TRANSFER TELEPORT",
        "Teleport is a synonym for transfer.\n~",
        "Teleport is a synonym for transfer.\n\nSee also: GOTO, AT, FORCE\n~",
    ),
    (
        "AT perform at room",
        "command, and then moving you back (if the command didn't change your\nlocation).\n~",
        "command, and then moving you back (if the command didn't change your\nlocation).\n\nSee also: GOTO, TRANSFER, FORCE\n~",
    ),
    (
        "EXPLODE quest item",
        "s a generic item with a no_locate\nflag on it that can be used as a quest item.\n~",
        "s a generic item with a no_locate\nflag on it that can be used as a quest item.\n\nSee also: PURGE, LOAD, VNUM\n~",
    ),
    (
        "STAT inspect",
        "Stat can be used to find room vnums for goto.\n(see also goto, transfer)\n~",
        "Stat can be used to find room vnums for goto.\n\nSee also: GOTO, TRANSFER, VNUM\n~",
    ),
    (
        "REPOP area reset",
        "Useful for testing area resets or quickly restocking a cleared zone.\n~",
        "Useful for testing area resets or quickly restocking a cleared zone.\n\nSee also: LOAD, VNUM\n~",
    ),
    # ──────────────────────────────────────────
    # Mid immortal commands (64–67)
    # ──────────────────────────────────────────
    (
        "STRING variables warning",
        "DO NOT USE ANY OTHER VARIABLES, DOING SO WILL CAUSE THE MUD TO CRASH.\n~",
        "DO NOT USE ANY OTHER VARIABLES, DOING SO WILL CAUSE THE MUD TO CRASH.\n\nSee also: STAT, LOAD, CLONE\n~",
    ),
    (
        "PEACE stop fighting",
        "It also strips the\nAGGRESSIVE bit from mobiles.\n~",
        "It also strips the\nAGGRESSIVE bit from mobiles.\n\nSee also: SLAY, RESTORE, FORCE\n~",
    ),
    (
        "IPORTAL use responsibly",
        "Note: This is a powerful tool; use responsibly.\n~",
        "Note: This is a powerful tool; use responsibly.\n\nSee also: PORTAL, GOTO, TRANSFER\n~",
    ),
    (
        "LOAD mob/obj",
        "preset level that cannot be changed without set.\n(see also clone, vnum, stat)\n~",
        "preset level that cannot be changed without set.\n\nSee also: CLONE, VNUM, STAT\n~",
    ),
    (
        "MEMORY stats",
        "There is no limit\non the number and size of these blocks.\n~",
        "There is no limit\non the number and size of these blocks.\n\nSee also: SOCKETS, STAT\n~",
    ),
    (
        "VNUM slot number",
        "the slot number (for making new zones) of a skill name.\n(see also load)\n~",
        "the slot number (for making new zones) of a skill name.\n\nSee also: LOAD, STAT, AREAVNUMS\n~",
    ),
    (
        "PURGE clear room",
        "Mobiles may be\npurged if they are called directly by name.\n~",
        "Mobiles may be\npurged if they are called directly by name.\n\nSee also: SLAY, RESTORE, LOAD\n~",
    ),
    (
        "RESTORE heal all",
        "Restore should be used sparingly\nor not at all.\n~",
        "Restore should be used sparingly\nor not at all.\n\nSee also: PURGE, SLAY\n~",
    ),
    (
        "SLAY god kill",
        "command on players if you enjoy being a god.\n~",
        "command on players if you enjoy being a god.\n\nSee also: PURGE, RESTORE, KILL\n~",
    ),
    (
        "SLOOKUP spell/skill number",
        "a potion or scroll, and various other items.\n~",
        "a potion or scroll, and various other items.\n\nSee also: LOAD, BREW, SCRIBE\n~",
    ),
    (
        "FSAVE force save",
        "This command is also invoked on reboots and shutdowns.\n\n~",
        "This command is also invoked on reboots and shutdowns.\n\nSee also: SOCKETS, RESTORECHAR\n\n~",
    ),
    (
        "ALLOW BAN clear on reboot",
        "every time the server is rebooted, the site\nban list is cleared.\n~",
        "every time the server is rebooted, the site\nban list is cleared.\n\nSee also: BAN, DNS\n~",
    ),
    (
        "RESTORECHAR bad pfile",
        "not those who have deleted themselves.\n~",
        "not those who have deleted themselves.\n\nSee also: RESTORE, PURGE\n~",
    ),
    (
        "SWEDISH accent",
        "Remember to remove it from the player\nbefore you or they leave.\n~",
        "Remember to remove it from the player\nbefore you or they leave.\n\nSee also: WIZHELP\n~",
    ),
    # ──────────────────────────────────────────
    # High immortal commands (68–70)
    # ──────────────────────────────────────────
    (
        "MAXLOAD spawn limit",
        "LESS as the maxload value specified. Which can take a while....\n~",
        "LESS as the maxload value specified. Which can take a while....\n\nSee also: MEMORY, VNUM\n~",
    ),
    (
        "WHINE cityguard taunt",
        "causes cityguards to taunt them incessantly. This\ncommand is NOT to be abused!\n~",
        "causes cityguards to taunt them incessantly. This\ncommand is NOT to be abused!\n\nSee also: WIZHELP, PUNISHED\n~",
    ),
    (
        "NONOTE last resort",
        "consistently abused their note privilege.\n~",
        "consistently abused their note privilege.\n\nSee also: NOTE, WIZHELP\n~",
    ),
    (
        "ADVANCE level set",
        "ADVANCE\nmay also be used to demote characters.\n~",
        "ADVANCE\nmay also be used to demote characters.\n\nSee also: TRUST, WIZLIST\n~",
    ),
    (
        "TRUST level override",
        "A trust of 0 means to use the character's natural level again.\n~",
        "A trust of 0 means to use the character's natural level again.\n\nSee also: ADVANCE, WIZLIST\n~",
    ),
    (
        "BACKUP scheduled",
        "will show when the next scheduled backup will take place.\n\n~",
        "will show when the next scheduled backup will take place.\n\nSee also: MEMORY, SOCKETS\n\n~",
    ),
    (
        "PSTAT player stats",
        "Pstat shows you various statistics of all the players connected to the mud.\n~",
        "Pstat shows you various statistics of all the players connected to the mud.\n\nSee also: SOCKETS, MEMORY\n~",
    ),
    (
        "DNS site ban lookups",
        "sitebans on name hosts will be ignored.\n\n~",
        "sitebans on name hosts will be ignored.\n\nSee also: BAN, ALLOW BAN\n\n~",
    ),
    (
        "GRANTPSI psionic list",
        "telekinesis, transfusion, nightmare, mind leech, and confuse.\n\n~",
        "telekinesis, transfusion, nightmare, mind leech, and confuse.\n\nSee also: PSIONICS, ADVANCE\n\n~",
    ),
    (
        "COMPONENT world items",
        "(do 'owhere component' to see the current components in the world.)\n~",
        "(do 'owhere component' to see the current components in the world.)\n\nSee also: LOAD, VNUM\n~",
    ),
    (
        "DUMP_EXITS area exits",
        "for every exit defined in the loaded areas.\n~",
        "for every exit defined in the loaded areas.\n\nSee also: AREAVNUMS, STAT, VNUM\n~",
    ),
    # ──────────────────────────────────────────
    # IMOTD (level 60)
    # ──────────────────────────────────────────
    (
        "IMOTD immortal message",
        "This message is shown\nautomatically when an immortal logs in.\n~",
        "This message is shown\nautomatically when an immortal logs in.\n\nSee also: MOTD, NEWS, JOBS\n~",
    ),
]

for label, old, new in changes:
    cm, ok = replace_once(cm, old, new, label)
    if ok: ok_cm += 1
    else: errors += 1

write_file('commands.are', cm)
print(f"\n  → commands.are: {ok_cm}/{len(changes)} applied")
print(f"\nTotal: {ok_cm}/{len(changes)} OK, {errors} errors")
if errors:
    sys.exit(1)

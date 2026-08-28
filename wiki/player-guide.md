# Times of Chaos Player Guide

This guide is for a player arriving in Times of Chaos for the first time. It
explains the normal progression loop and the systems that are easy to miss in a
classic text MUD. The live game remains authoritative: use `help <topic>` for
exact syntax and `commands`, `skills`, `spells`, `groups`, `gainlist`, and
`teachlist` for options available to the character currently logged in.

## Before You Connect

ToC uses plain Telnet. Your login name, password, commands, and game output are
not encrypted between your client and the server. The server also uses
traditional DES password hashes, for which only the first eight password bytes
are significant.

- Use a unique password that you have never used for email, banking, work, or
  another game.
- Treat the first eight characters as the effective password. Use a random mix
  rather than a word or reused phrase.
- Do not enter a sensitive password into aliases, triggers, logs, screenshots,
  or support messages.
- Ask the host whether they provide a TLS-wrapped connection, VPN, or secure web
  client if network privacy matters.

## Connecting

A dedicated MUD client provides better color, scrollback, aliases, triggers,
and reconnect handling than a raw Telnet program. Common choices include
Mudlet, TinTin++, MUSHclient, and CMUD. Configure:

| Setting | Value |
|---|---|
| Host | The address supplied by the ToC host; `localhost` for your own server |
| Port | `9000` unless the host changed it |
| Protocol | Telnet/MUD |
| Character set | Latin-1 or automatic |
| Local echo | Off unless the client requires it |

Raw `telnet <host> 9000` is useful for a connectivity check, but many current
Windows installations do not enable the Telnet client by default.

## Creating A Character

Follow the login prompts to choose a new name, password, sex, race, and class.
Names and passwords are stored in a character file, so choose a stable name and
the unique password described above.

### Classes

| Class | Primary attribute | Starting weapon | General identity |
|---|---|---|---|
| Mage | Intelligence | Dagger | Broad arcane spellcasting and mana use |
| Cleric | Wisdom | Mace | Divine magic, healing, support, and durability |
| Thief | Dexterity | Dagger | Stealth, backstab, utility, and opportunistic damage |
| Warrior | Strength | Sword | Weapon damage, armor, attacks, and front-line control |
| Monk | Constitution | Dagger | Unarmed techniques, mobility, and mixed physical/mystic play |
| Necromancer | Intelligence | Dagger | Death-oriented spellcasting and specialized magic |

Monks may be Human or Dwarf. Necromancers may be Human or Elf. Other classes
can use any playable race.

### Races

Stats below are ordered `STR / INT / WIS / DEX / CON` and show base values,
then racial maximums. Equipment, training, spells, and other systems can modify
the effective value.

| Race | Base stats | Maximums | Innate traits |
|---|---|---|---|
| Human | 13 / 13 / 13 / 13 / 13 | 18 / 18 / 18 / 18 / 18 | Balanced baseline |
| Elf | 12 / 15 / 13 / 14 / 11 | 17 / 19 / 18 / 18 / 18 | Sneak, infrared, magic/poison resistance, iron vulnerability |
| Dwarf | 14 / 13 / 12 / 12 / 15 | 20 / 16 / 18 / 16 / 19 | Bash, infrared, magic/disease resistance, drowning vulnerability |
| Hobbit | 10 / 13 / 14 / 16 / 12 | 16 / 18 / 18 / 19 / 17 | Hide, poison/disease resistance, wind vulnerability, small size |
| Saurian | 14 / 12 / 12 / 13 / 13 | 17 / 18 / 18 / 17 / 18 | Infrared, poison immunity, fire resistance, cold vulnerability |

Race also affects advancement costs for some class and guild combinations. Use
the creation screens and in-game help when optimizing a particular build.

## Your First Session

After entering the world, run this short orientation sequence:

```text
look
score
equipment
inventory
achievements
autoexit
autogold
autoloot
commands
skills
spells
areas
save
```

Then:

1. Read room descriptions and signs. Builders often place directions and
   mechanics in prose rather than a separate quest tracker.
2. Find opponents near your level and use `consider <target>` before attacking.
3. Return to a trainer or guildmaster when you have practices, trains, or new
   skills available.
4. Choose a guild before advancing beyond level 5.
5. Use `save` after meaningful progress and before disconnecting.

`score`, `attribute`, `affect`, `worth`, `equipment`, and `compare profile`
together provide the clearest picture of the character.

## Reading The World

Core observation commands:

| Command | Purpose |
|---|---|
| `look` | Redisplay the room |
| `look <target>` | Inspect a character, object, feature, or direction |
| `examine <object>` | Inspect an object and, where relevant, its contents |
| `exits` | Show obvious exits |
| `scan` | Look for nearby characters |
| `where` | Find visible nearby players or landmarks supported by the area |
| `areas` | Show level ranges and area names |
| `consider <target>` | Estimate how dangerous an opponent is |
| `lore <object>` | Use lore knowledge to inspect equipment |
| `read <thing>` | Read notes, signs, boards, and readable objects |
| `search` | Search the current room for supported hidden features |

Descriptions matter. A room can support `climb`, `crawl`, `jump`, `enter`,
`push`, `pull`, `move`, `turn`, `flip`, `burn`, or another contextual action
without presenting it as a normal compass exit.

## Movement

ToC supports ten directions:

```text
north east south west up down northeast northwest southeast southwest
n     e    s     w    u  d    ne        nw        se        sw
```

Useful movement commands:

```text
run <direction> [distance]
speedwalk <route>
enter <target>
climb <target>
crawl <target>
jump <target>
track <target>
recall
```

`run` moves up to 30 rooms in one direction; the default distance is 30.
`speedwalk` accepts compact lowercase direction tokens, for example:

```text
speedwalk 3n2e1s
speedwalk 2ne4w1d
```

Each count is capped at 30, and movement stops when ordinary movement fails,
combat starts, or the character can no longer continue. Use short routes in
unfamiliar areas because traps, aggressive mobiles, closed doors, and movement
costs still apply.

Door and container commands include `open`, `close`, `lock`, `unlock`, `pick`,
and `doorbash`. Most accept a direction or object name. Hidden doors may need to
be discovered before the normal door commands can target them.

### Recall

Recall is intentionally unpredictable in this game: it may send you to any room
eligible for recall rather than one fixed hometown. Protected and no-recall
rooms are excluded. Some areas, including Hyrule, disable recall completely and
provide their own exit path. Do not enter a dangerous one-way area assuming
`recall` will always rescue you.

## Combat

Start with `consider <target>`, then use `kill <target>` for a normal NPC fight.
Class and guild abilities appear in `skills` and `spells`; read each relevant
help topic before spending practices.

Common combat controls:

| Command | Purpose |
|---|---|
| `kill <target>` | Begin ordinary combat |
| `cast '<spell>' [target]` | Cast a known spell |
| `flee` | Attempt to leave combat |
| `wimpy <hp>` | Automatically attempt to flee below a hit-point threshold |
| `rescue <ally>` | Attempt to take over an ally's opponent |
| `report` | Report current resources to the group |
| `autoassist` | Toggle automatic entry into supported allied combat |
| `shoot <target>` | Fire a wielded bow at a visible target in an adjacent room |

Current bow combat requires a bow and the archery skill. It does **not** consume
or require a separate ammunition object. On a successful hostile shot, an NPC
may move toward the archer and retaliate.

`murder` is the explicit player-hostile form of attack and can carry PK
consequences. Read `help pkill`, `help murder`, and the server rules before
using it.

### Rest And Recovery

Use `rest`, `sit`, `sleep`, `stand`, and `wake` to control position and recovery.
Food, drink, healers, potions, spells, regeneration, and equipment can affect
recovery. After the first remort, hunger and thirst conditions are disabled by
the remort system.

### Death And Corpses

Death behavior can vary with character state, area, and PK context. Read the
messages shown at death, use `where` and room descriptions to navigate, and ask
another player for retrieval help when needed. Avoid quitting in the middle of
recovery unless the game explicitly says it is safe. Saving protects persistent
character state but is not a substitute for recovering carried equipment.

## Advancement

Experience advances the character through mortal levels. `leveling` summarizes
the progression state; `score` shows experience and level information.

### Practices, Trains, Groups, And Gain

- `practice` lists or improves individual abilities where a trainer supports
  them.
- `train` improves supported attributes or resources.
- `groups` lists skill groups known or available to the character.
- `gain`, `gainlist`, and `teachlist` expose guildmaster and trainer options.
- `skills` and `spells` reflect the character's current class, guild, level,
  and learned percentages.

Do not spend every resource immediately. A future skill group, stat increase,
or guild choice may be more valuable than a marginal early improvement.

### Guild Choice

The primary class and guild are separate build dimensions for most characters.
A guild grants a different advancement path and cross-class access. Mage,
Cleric, Thief, and Warrior are valid optional guild choices. Monk and
Necromancer use their class-specific path and do not select one of those four
guilds.

The game warns at level 5. If the character still has no guild upon reaching
level 6, the game assigns the guild matching the primary class and may take up
to 50 gold. Use `join`, `gainlist`, `teachlist`, and the relevant in-game guild
help before that point.

### Heroes, Remorts, And The Mortal Cap

Hero status begins at level 51. Mortal progression is intentionally staged by
remorts:

| Life | Required level to remort | Result |
|---:|---:|---|
| Original | 54 | First remort, return to level 3 |
| Remort 1 | 55 | Second remort, return to level 3 |
| Remort 2 | 56 | Third remort, return to level 3 |
| Remort 3 | 57 | Fourth remort, return to level 3 |
| Remort 4 | 58 | Final remort, return to level 3 |
| Remort 5 | 59 | Absolute mortal maximum; no further remort |

Levels 60-70 are immortal/staff trust levels.

The command syntax is:

```text
remort <password> <class> <guild> <race>
```

Use `none` for the guild when choosing Monk or Necromancer. The class, guild,
and race arguments require at least two characters. Necromancer and Monk race
restrictions still apply. Before the final remort, the new class/guild choices
normally must differ from earlier lives; the game explains currently valid
choices when it rejects a duplicate.

Remorting is a major rebuild: level returns to 3, base permanent stats reset,
skills and groups are rebuilt for the new path, resources and progression
bonuses change, and status effects are cleared. Current code keeps items on the
final remort path, but always read `help remort`, save, and confirm the host has
a recent backup before committing. The password entered in the command crosses
the same unencrypted Telnet connection as every other command.

### Psionics

Beginning at remort 2, a character receives one random power from each of four
psionic disciplines. The final remort grants all 17 powers. These abilities use
mana and include mental attacks, temporary defenses, healing, scouting,
teleportation, and item retrieval. See the [Psionics Guide](psionics.md) for the
complete power list, costs, defensive interactions, and protected-room rules.

## Achievements

Achievements provide permanent, noncombat progression for a character. They
award points, an earned date, and a nearby-player announcement, but no stats or
equipment power. Start with:

```text
achievements
achievements character
achievements incomplete
achievements encounters
achievements collection
achievements hyrule
```

The 111-entry catalog covers character levels and remorts, play time, mobile
and player kills, named world bosses, rare relics, crafting, unusual deaths,
quest completions and streaks, exploration, and the full Hyrule campaign.
Hidden achievements show neither title nor requirement until earned. Credit
for every listed boss is shared with grouped players present in the boss room,
so healers and support characters do not need the final hit.

The default summary pairs categories in two columns and shows the five newest
unlocks without normally interrupting the overview with a paging prompt.
Category, earned, incomplete, all, and search views remain scrollable.

Existing characters receive credit for facts the old save format already
knows: level, remorts, play time, qualifying player kills, current quest
streak, and qualifying rare or Hyrule items still carried, including items
inside containers. Lifetime mobile-kill, quest-completion, and all-cause death
totals start when the new system begins recording them; old saves did not
preserve those totals.
`score` shows a compact total, while `achievements` shows dates and progress.
See [Achievement System](achievements.md) for the full behavior.

## Equipment And Items

Basic inventory commands:

```text
inventory
equipment
get <object> [container]
put <object> <container>
drop <object>
give <object> <person>
wear <object>
wield <object>
hold <object>
remove <object>
examine <object>
value <object>
repair <object>
```

Magic and consumable object commands include `quaff`, `recite`, `brandish`,
`zap`, `eat`, `drink`, `fill`, `brew`, `scribe`, and `concoct`. The item type,
class skills, charges, and room rules determine whether each command works.

### Advanced Compare

```text
compare <item>
compare <item-a> <item-b>
compare <focus> <item> [item]
compare profile
```

Valid focuses are `overall`, `damage`, `spells`, `defense`, `leveling`, and
`utility`. The comparison models projected full loadouts rather than adding a
few raw attributes. It accounts for class, guild, race gates, level, learned
abilities, weapon proficiency, attacks, spell resources, survival, recovery,
equipment conflicts, and the selected focus.

The displayed percentage is an estimate against a standard equal-level combat
benchmark, not a universal promise. Enemy resistances, vulnerabilities, fight
length, special attacks, and group role can change the practical winner. See
[Advanced Gear Comparison](gear-comparison.md) for the complete model.

## Shops, Currency, And Banking

Shop commands include `list`, `buy`, `sell`, `value`, and `repair`. Healers use
`heal` to list or purchase services. Currency can exist in multiple
denominations; `worth` summarizes carried money.

Banks support:

```text
balance
deposit <amount>
withdraw <amount>
exchange ...
convert ...
```

The exact accepted amount syntax is shown by each command's help and local NPC
messages. The game also contains gambling commands such as `gamble`, `slots`,
`bet`, `roulette`, and `poker`; use them only where the relevant game operator
is present.

## Groups And Social Play

Use `follow <leader>`, `group <name>`, `gtell <message>`, `report`, `rescue`,
`split`, `autosplit`, and `autoassist` to coordinate. `nofollow` prevents
unwanted followers, and `noloot` controls whether group members may loot your
corpse under supported rules.

Group before the fight, confirm who is leading, decide whether autoloot and
autosac are appropriate, and keep enough movement to retreat. Experience,
currency splitting, assists, rescues, and kill ownership depend on group state.

## Communication

Common communication commands include:

```text
say <message>
' <message>
tell <player> <message>
reply <message>
gossip <message>
question <message>
yell <message>
gtell <message>
emote <action>
note ...
```

Use `channels` to review channel state, `quiet` to suppress channels, `deaf` for
shouts, `ignore <name>` for a player, and `afk` when stepping away. Read `rules`
and `help rules` before using public channels or PK systems. Report content
problems with `bug`, `typo`, and `idea`.

## Quests And Player Killing

`aquest` is the main quest command family; invoke it without arguments and read
`help aquest` for the current subcommands and eligibility. Quest points and
rewards are distinct from ordinary shop progression.

`pkill` controls or reports player-killing state according to the live rules.
PK commands, theft, hostile spells, charm, grouping, and corpse handling may
have consequences that differ from NPC combat. Read `rules`, `help pkill`, and
the host's local policy before opting in or attacking another player.

## Hyrule: First Quest

Hyrule is a generated 443-room campaign modeled after the first quest of the
original Legend of Zelda. It contains a 128-room overworld, nine dungeons and
cellars, level-scaled progression, canonical bosses and enemies, hidden
interactions, dungeon maps and compasses, boss keys, the Triforce route, and
return portals.

- Enter through the arcade cabinet portal; the campaign begins at its intended
  Zelda 1 entrance rather than through a normal world road.
- Recall is disabled. Leave through the secret-tree return or the post-Ganon
  portal.
- A dungeon map reveals layout information.
- A dungeon compass gives the general direction toward that dungeon's boss.
- Candles, bombs, arrows, keys, rafts, ladders, recorders, and room actions are
  part of progression. Read descriptions and inspect inventory carefully.
- Other weapons and spells can wound Ganon, but only a direct normal strike
  from the Silver Arrow can kill him. Use `wield silver` in your primary
  weapon slot and attack normally. There is no separate Silver Arrow `use` or
  `fire` command, and casting a spell while merely holding it does not count.
  The Silver Arrow requires level 59, the highest attainable mortal level; it
  does not require immortal status.
  Against Ganon, every landed Silver Arrow strike uses full weapon mastery and
  deals at least 10% of his maximum health after defenses. At one hit point he
  turns bright red, all combat with him stops, and he remains stunned until the
  Silver Arrow lands the final blow. `Look ganon` repeats the instruction in
  this vulnerable phase.

The full level bands, dungeon order, commands, generated-data workflow, and
spoiler-conscious mechanics are in [Hyrule: First Quest](hyrule-area.md).

## Character Settings

Useful preference commands include:

- `autolist` to review automatic behavior.
- `autoexit`, `autogold`, `autoloot`, `autosac`, `autosplit`, and `autoassist`.
- `brief`, `compact`, and `scroll` for output density.
- `color` for color settings.
- `damagenumbers` for numeric combat output.
- `prompt` for prompt formatting.
- `description` and `title` for character presentation where allowed.
- `nosummon`, `nofollow`, `noloot`, and `wimpy` for safety preferences.

Avoid aliases or triggers that spam movement or combat without checking game
state. A compact route still passes through every room and can trigger every
normal hazard.

## Saving, Quitting, And Passwords

Use `save` after leveling, changing equipment, training, receiving important
items, or completing a difficult objective. Use the full `quit` command when
leaving; the abbreviated `qui` exists to prevent accidental quits.

Change a password with the documented `password` command, using a unique value.
Traditional DES ignores bytes after the eighth, so changing only later
characters does not change the effective credential. Do not share character
files: they contain the password hash and persistent game state.

## Troubleshooting

### I Cannot Connect

Confirm the host, port, and protocol. The first-party browser client is normally
`http://127.0.0.1:9001/client`; a traditional MUD client normally uses game port
9000. Test whether the server is online and check local firewall or VPN rules.
Do not enter the web-client URL as the host in a traditional MUD client.

### My Password Is Rejected

Check capitalization and character name first. Ask an operator for account
recovery; do not send the password or player file in a public channel. Remember
that only the first eight password bytes affect the legacy hash.

### A Command Is Missing

Use `commands` and `help <command>`. Some commands require a minimum level,
class, guild, skill, position, room feature, NPC, or held object. `skills`,
`spells`, `gainlist`, and `teachlist` show character-specific access.

### I Am Lost

Use `look`, `exits`, `where`, `areas`, `scan`, and room descriptions. Backtrack
one move at a time. Recall is random among eligible rooms and can be disabled,
so it should not be the only plan. Ask on a suitable help channel when stuck.

### My Equipment Looks Worse After A Swap

Run `compare profile`, then compare the two items with the relevant focus. Check
level, race/alignment restrictions, weapon proficiency, two-handed conflicts,
no-remove items, heated/damaged state, and the complete projected loadout.

### The Client Shows Odd Characters

Select Latin-1 or automatic encoding and enable ANSI color support. If prompts
double or typed characters echo twice, disable local echo in the client.

## Quick Reference

```text
help <topic>              exact live help
commands                  commands available at your level
skills / spells           current learned abilities
score / attribute         character progression and stats
equipment / inventory     worn and carried objects
look / exits / scan       immediate surroundings
areas / where             world orientation
consider <target>         danger estimate
compare profile           inferred equipment priorities
save                       persist progress
rules                      local conduct and PK rules
bug / typo / idea          send feedback to staff
```

See [Player Command Reference](player-command-reference.md) for commands grouped
by purpose and [Wiki Home](Home.md) for every guide.

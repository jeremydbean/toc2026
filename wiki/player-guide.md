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

Mudlet is the recommended desktop client when you want gauges and automatic
mapping. Enable GMCP and server-installed packages in the profile; the server
then supplies the interface and the full-world map. In game, use `help
mudlet`, `help map`, and `help gmcp` for current behavior and limitations.

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

`recall`, or `/`, prays for transport to your recall point. It costs half your
movement, it can fail on a skill check, and on a rare bad roll it drops you in
a random eligible room instead - so it is a good escape, not a guaranteed one.
Recalling out of combat also costs experience. From the fourth remort on it
always succeeds and never misfires.

Your recall point starts at the Temple of Devota in Dresden, and you can move
it:

| Command | Effect |
| --- | --- |
| `recall set` | Make the room you are standing in your recall point |
| `recall default` | Send it back to the Temple |
| `recall where` | Where it is now, and whether you may move it yet |

Pick somewhere you keep going back to: a hunting ground you are working
through, a questmaster, the shop you live out of. A room has to be one recall
works in, so no-recall rooms, jails, death traps and private rooms are all
refused.

You may move your recall point once every 30 minutes, and not while you are
fighting or while the blood is still up from a fight. `recall default` is
exempt from all of that - you can always send it back to the Temple, so a
choice you regret can never strand you.

`word of recall` is a different journey, and the differences are the reason
to carry it. It always goes to the Temple whatever you have set, so between
the spell and the skill you have two places to reach in a hurry. It also
works while you are cursed, where `recall` does not: a curse silences your
own prayer but has no hold over somebody else's magic. A scroll or potion of
recall carries the same spell and behaves the same way. The Recall Ring, and
being pulled to safety while link-dead, also go to the Temple.

Some areas disable recall and provide their own exit path. In Hyrule that is
the nine dungeons: inside a `Level N` dungeon, recall will not take you out,
and you leave the way you came. The Hyrule overworld, its sword caves, shops,
repair rooms, money games, warp halls and the Lost Woods all allow recall, and
recalling is the intended way out of the Lost Woods loop. Do not enter a
dangerous one-way area assuming `recall` will always rescue you.

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
| `shoot <target>` | Fire a wielded bow at a visible mobile through an open adjacent exit |

Current bow combat requires a bow and the archery skill. It does **not** consume
or require a separate ammunition object, and normal ranged attacks cannot
target players. Successful and missed shots can improve Archery. On a
successful hostile shot, an NPC may move toward the archer and retaliate.

`murder` is the explicit player-hostile form of attack and can carry PK
consequences. Read `help pkill`, `help murder`, and the server rules before
using it.

### The Training Yard

A dummy that cannot be killed, for finding out what your gear and spells
actually do. From the centre of the Oak Tree Square go `down`, then
`south`; `north` walks back out, and in Mudlet `walk dummy` takes you
there. The yard takes one fighter at a time.

`kill dummy` starts the standard fight: twenty-five rounds against a dummy
at your level that dodges, parries, blocks and hits back. Neither of you
can die there, nothing is learned there, and when the run ends you are put
back the way you were when it began rather than healed. The report breaks
the fight down attack by attack, both ways, and the standard fight is
ranked on `dummy leaderboard`. `dummy` alone shows every setting; change
any of them and the run is not ranked. See `help dummy`.

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
restrictions still apply. Before the final remort, the new class must differ
from every earlier life's class; the game explains currently valid choices when
it rejects a duplicate.

Remorting is a major rebuild: level returns to 3, base permanent stats reset,
skills and groups are rebuilt for the new path, resources and progression
bonuses change, and status effects are cleared. Every item you own is kept,
worn gear included -- though most of it will out-level you until you climb
back up. Always read `help remort`, save, and confirm the host has a recent
backup before committing. The password entered in the command crosses
the same unencrypted Telnet connection as every other command.

Each remort also leaves a permanent gift. Gifts accumulate: every later life
keeps everything earlier ones gave.

| Remorts taken | Gift |
|---:|---|
| 1 | Hunger and thirst no longer affect you: you never get hungry or thirsty again |
| 2 | Psionics: one power from each of the four disciplines |
| 3 | Two powers per discipline; you may stay idle or link-dead twice as long before being dropped; you can carry twice the items and twice the weight; recall always succeeds and never throws you to a random room |
| 4 | Three powers per discipline; the Shadowmeld skill at 50% |
| 5 | All 17 psionic powers; no carrying limits; the fifth remort may pick any class, even one you have already lived as |

The guild is never restricted, only the class.

### Necromancers And The Undead

A necromancer raises servants that fight alongside them. `create skeleton`
from level 15, `create wraith` from 30, and `create vampire` from 45.

None of the three needs a corpse. Cast with nothing to hand and the spirit
arrives thin. Cast where a mobile's corpse is lying and the servant is half
again as strong, lasts twice as long, and carries part of what the dead
thing was worth into its own level, so raising something formidable beats
raising a rat. Name a corpse to pick one, or name nothing and any corpse in
the room is used.

Servant strength follows your level, not the corpse's. You may have five
skeletons, two wraiths, or one vampire standing; they share one count.

`animate parts` (level 5) throws something dead at whoever you are fighting.
A dismembered part in the room - the kind `butcher` leaves - is what gets
thrown and does the most damage; a heart hurts worst, then an arm or leg,
then guts, then a head. Without one, gore is pulled out of the air instead:
weaker, but it always works.

`butcher` and `raise dead` still need a corpse, because cutting up a body
and resurrecting a dead player are what those spells do.

### Psionics

Beginning at remort 2, a character receives one random power from each of four
psionic disciplines. Powers stack and are never taken away: the third remort
brings each discipline to two, the fourth to three, and the final remort grants
all 17. These abilities use
mana and include mental attacks, temporary defenses, healing, scouting,
teleportation, and item retrieval. Practice them with Salir the Monk in the
Study of the Sage, in the Astral Plane. See the [Psionics Guide](psionics.md)
for the complete power list, costs, defensive interactions, and protected-room
rules.

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
achievements economy
achievements hyrule
```

The 127-entry catalog covers character levels and remorts, play time, mobile
and player kills, named world bosses, rare relics, crafting, unusual deaths,
quest completions and streaks, exploration, banking and casino feats, and the
full Hyrule campaign.
Hidden achievements show neither title nor requirement until earned. Credit
for every listed boss is shared with grouped players present in the boss room,
so healers and support characters do not need the final hit.

The default summary pairs categories in two columns and shows the five newest
unlocks without normally interrupting the overview with a paging prompt.
Category, earned, incomplete, all, and search views remain scrollable.

Existing characters receive credit for facts the old save format already
knows: level, remorts, play time, qualifying player kills, current quest
streak, bank balance, carried money, casino totals, and qualifying rare or
Hyrule items still carried, including items inside containers. Lifetime
mobile-kill, quest-completion, and all-cause death totals start when the new
system begins recording them; old saves did not preserve those totals.
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

### Compare

```text
compare <item>            against what you wear there, or the empty slot
compare <item-a> <item-b> two items against each other
compare upgrades [slot]   the best gear you could wear today, and where it is
compare profile           how your damage is made
compare defense ...       rank by toughness instead of damage
```

`compare` ranks gear by how much harder it makes you hit -- weapon damage per
round for fighters, mana to cast with for casters -- and uses toughness to
settle close calls. It works from your own level, skills, stats and what you
already wear, and says plainly when you cannot use something yet.
`compare upgrades` searches every piece of gear a mob in the world carries or
sells. See [Gear Comparison](gear-comparison.md) for the complete model.

## Shops, Currency, And Banking

Shop commands include `list`, `buy`, `sell`, `value`, and `repair`. Healers use
`heal` to list or purchase services. Currency can exist in multiple
denominations; `worth` summarizes carried money.

`list` shows each price in the denominations it will actually cost, written
short: `1c`, `5g 20s`, `3p`. Prices are counted in copper, so a shop can
charge as little as a single copper coin - the bread in Mud School does.

Shops are priced for the people who use them. A shelf in a starting area is
counted in coppers and silvers, because the mobiles around it carry coppers
and silvers; the same shelf one bracket up is counted in gold. As a rough
measure, an ordinary piece of gear costs about as much as thirty or forty
kills of something your own level, and a meal costs a few. If a shop looks
unreachable, it is probably not meant for you yet.

`repair` works on gear you are wearing as well as gear in your pack, so you do
not have to take a dented breastplate off to have it seen to. The smith quotes
a price from how worn the item is and how high a level it is, in the same
denominations the shops use, and restores the item to full condition -- armour
values and worth included, both of which a heavy blow can file down. An item
remembers how often it has been mended; after about two dozen repairs the next
attempt breaks it for good, and the running count is printed every time so you
can see it coming.

Banks support:

```text
balance
deposit <amount> [platinum|gold|silver|copper]
withdraw <amount> [platinum|gold|silver|copper]
convert
```

If the denomination is omitted, `deposit` and `withdraw` use platinum. The bank
stores exact copper value, charges no transaction fee, and saves successful
deposits and withdrawals immediately. Balances of at least 1 platinum earn 1%
per real day while the character is in the game, with at most seven elapsed
days paid in one catch-up. `convert` exchanges carried value upward into the
fewest practical coins.

The game also contains `gamble`, `slots`, `bet`, `roulette`, and `poker`; use
them only where the relevant game operator is present. Hi/Lo and roulette bets
range from 1 to 100,000 gold and require confirmation above 500 gold. Video
poker accepts 5 to 200 gold.

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
`help aquest` for the current subcommands and eligibility. `info`, `points`,
`time` and `gamble` answer wherever you are standing; requesting, turning in,
aborting and shopping are business with a questmaster and need one present.
Every subcommand abbreviates to its first letter. Quest points and rewards are
distinct from ordinary shop progression.

The questmaster never sends you into Hyrule -- it is too large and too new to
be fair as a quest target, and its dungeons do not let you recall -- nor to the
Training Dummy Yard, whose dummy cannot die. Every other area can come up.

`pkill` controls or reports player-killing state according to the live rules.
PK commands, theft, hostile spells, charm, grouping, and corpse handling may
have consequences that differ from NPC combat. Read `rules`, `help pkill`, and
the host's local policy before opting in or attacking another player.

## Hyrule: First Quest

Hyrule is a generated 447-room campaign modeled after the first quest of the
original Legend of Zelda. It contains a 128-room overworld, nine dungeons and
cellars, level-scaled progression, canonical bosses and enemies, hidden
interactions, dungeon maps and compasses, boss keys, the Triforce route, and
return portals.

- Enter through the arcade cabinet portal; the campaign begins at its intended
  Zelda 1 entrance rather than through a normal world road.
- Recall works everywhere in Hyrule except inside the nine `Level N`
  dungeons; walk out of a dungeon the way you came in. The secret-tree return
  and the post-Ganon portal are the other ways home.
- The dungeons climb from Level 1 (character levels 2-8) to Death Mountain
  (53-59), and the land around each dungeon matches it. What you find in a
  place -- chest gear, a boss's Heart Guard and weapon, a shop's wares -- is
  usable at that place's level. The first eight guardians also leave a Heart
  Container, and ordinary enemies sometimes drop rupees, a heart, a bottled
  fairy or a clock-flask (quaff the last three).
- The dungeons are done in order. Each needs the previous dungeon's Triforce
  piece to enter and its treasure to reach the guardian; the guardian drops a
  key to the locked room behind it, where a locked chest holds this dungeon's
  piece and treasure. `help hyrule` has the whole chain. Every guardian is
  sized to beat a lone character at the top of its band: go well above it,
  or go with friends.
- Ganon is a fight for a group, ideally with two Silver Arrows: he blinks
  about the dark throwing fireballs no parry stops, and heals if left alone.
  His Golden Key opens Zelda's chamber and the great chest there, which holds
  the ninth piece and the Master Sword, level 58, the finest blade a mortal
  can wield, which hastens its wielder.
- The Red Ring of Hyrule lies in Death Mountain's deepest cellar; worn, it
  gives sanctuary and takes a fifth off all damage. `combine triforce` joins
  the nine pieces into The Triforce, worn in the light slot, which
  shows you what a level 59 hero with holy light would see. `help ganon` has
  the details.
- A dungeon map, looked at or read, draws its floor plan: where you stand, the
  guardian's chamber, the locked Triforce chest, and what the guardian's door
  needs. Its compass, inside its own dungeon, names the first step toward the
  Triforce chest and how many rooms away it and the guardian are.
- Hidden ways open only to the NES's act with its tool: BOMB a cracked wall
  (each blast uses a bomb), BURN a bush with a lit candle, PUSH an Armos or a
  gravestone, PLAY the Recorder at Level 7's lake. OPEN will not shift them.
- Every Hyrule item does something: bombs, the bow and arrows (a rupee a
  shot), boomerangs, candles, bait, the Recorder, the Magical Rod and Book,
  potions, keys, rings and the Magical Shield. `help hyrule items` lists them.
- The caves keep the NES's rules, once per character: the money caves pay as
  you walk in, the take-any caves give a Heart Container or a red potion, and
  the White and Magical Swords want 5 and 12 hearts (`hearts`). `help hyrule
  secrets` has them all.
- Every guardian also drops two pieces of a five-piece armour table, each a
  little better than anything else a character of its band can find.
- Other weapons and spells can wound Ganon, but no normal attack can kill him.
  Normal strikes with the wielded Silver Arrow still use full weapon mastery
  and deal at least 10% of his maximum health after defenses.
- The Silver Arrow requires level 54. It does not require immortal status.
- At one hit point Ganon turns bright red, all combat with him stops, and he
  remains stunned. Keep the Silver Arrow wielded and type `shoot ganon` in his
  room to deliver the final blow. This special shot always lands, requires no
  Archery skill, and does not consume the Arrow. `Look ganon` repeats the
  instruction during this vulnerable phase.
- Ganon's corpse always contains the Golden Key and one random mortal relic:
  the Hero's Tunic, Mirror Shield, or Pegasus Boots. Their levels range from
  54 through 56, and each has a real defensive, recovery, or travel passive
  described by `examine` and modeled by `compare`. The Red Ring of Hyrule is
  found in Death Mountain's cellar, and the Blue Ring of Hyrule is bought
  from the ring shop.
- The Blue Ring of Hyrule (level 45) and the Red Ring stack -- 28 percent
  less damage worn together -- but only one of each may be worn. The Mirror
  Shield's nonphysical ward stacks with both.

The full level bands, dungeon order, commands, generated-data workflow, and
spoiler-conscious mechanics are in [Hyrule: First Quest](hyrule-area.md).

## The Oracle

`pray` draws you out of the world into the sanctum of the Oracle, a seer who
answers questions about the game. Everything you `say` there is said to her
(`ask <question>` works too). `say done`, or stepping `down` through the bead
curtain, returns you to where you prayed. She attends one seeker at a time.

- She knows commands, classes, races, remorts, skills, areas, leveling, and
  what gear to seek for your class and level, and she has read the game's own
  help. She can see what players and creatures are wearing, where an item or
  creature is right now, and where an item drops -- but only what you could
  see yourself. She never reveals staff, anyone stealthed, shadowmelded or
  hidden from you, or what is in another player's pack.
- She remembers what you asked earlier in the same audience, so a follow-up
  ("and for a mage?") works.
- If an answer is wrong, `say wrong`. The exchange is filed as a bug report
  for the staff, and she stops giving that answer.
- She answers only questions about Times of Chaos and keeps them brief.
- An audience lasts at most five minutes, less if you fall silent. However it
  ends -- done, silence, time, or her walking out on off-topic questions --
  you return to where you prayed, dazed for a moment.
- It is never an escape: you cannot pray in battle, while your blood is still
  up after a fight or a flight, while something hunts you, or from a death
  trap.

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

`AUTOGOLD` collects currency even when `AUTOLOOT` is off. `AUTOSAC` only
sacrifices empty corpses, so boss drops and anything you cannot carry remain in
the room instead of being destroyed.

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

The live server is `toc.jeremybean.com`: play in a browser at
`http://toc.jeremybean.com:9001/client`, or point any traditional MUD
client at `toc.jeremybean.com` port `9000`. The `:9001` is required for
the browser client; there is no listener on browser port 80.

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
one move at a time. Recall takes you to your recall point, but it can fail and
some areas disable it, so it should not be the only plan. In Mudlet, the official mapper records rooms
as you explore, but it intentionally omits undiscovered secrets and may not draw
special scripted routes. Ask on a suitable help channel when stuck.

### My Equipment Looks Worse After A Swap

Run `compare <item>` before swapping: it shows what changes on the score
sheet and whether you hit harder. Its verdict names anything that stops you
using the item (level, race, alignment, weight, two-handed conflicts).

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
compare upgrades          best gear you can get today
save                       persist progress
rules                      local conduct and PK rules
bug / typo / idea          send feedback to staff
```

See [Player Command Reference](player-command-reference.md) for commands grouped
by purpose and [Wiki Home](Home.md) for every guide.

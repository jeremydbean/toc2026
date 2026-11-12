# Player Command Reference

This page groups the player-facing command surface by purpose. It is a map, not
a replacement for live help. Commands can depend on level, class, guild, race,
learned skill, position, equipment, room, NPC, or server rules.

Use these discovery commands first:

```text
commands
help <topic>
skills
spells
groups
gainlist
teachlist
socials
autolist
```

The interpreter usually accepts unambiguous prefixes, but full command names
are safer for `quit`, `delete`, `password`, `remort`, PK actions, purchases, and
staff-assisted recovery. Multiword spell names need no quotes - `cast` takes
the longest run of leading words that names a spell and treats the rest as
the target - though quoting still works:

```text
cast cure light self
cast 'cure light' self
```

Many character and object lookups support a numbered keyword such as
`2.guard` or `3.sword` when several visible targets share a name.

## Direction And Travel

| Commands | Use |
|---|---|
| `north`, `east`, `south`, `west`, `up`, `down` | Cardinal and vertical movement |
| `northeast`, `northwest`, `southeast`, `southwest` | Diagonal movement |
| `n`, `e`, `s`, `w`, `u`, `d`, `ne`, `nw`, `se`, `sw` | Direction abbreviations |
| `exits`, `look <direction>` | Inspect known routes |
| `run <direction> [distance]` | Move repeatedly in one direction, default/max 30 |
| `speedwalk <route>` | Follow compact lowercase routes such as `3n2e1s` |
| `walkto <place>` | Walk to an area, a guild hall, a guildmaster or trainer, the guild clerk, or the Temple from wherever you stand, a room every half second; any other command stops you |
| `walkto`, `walkto guilds`, `walkto trainers`, `walkto areas` | List the places `walkto` knows |
| `walkto stop` | Stop walking |
| `enter <portal>` | Step into a portal in the room (`enter portal`); some charge or need an item |
| `climb`, `crawl`, `jump` | Use area-defined movement features |
| `ride`, `mount`, `dismount` | Control supported mounts |
| `track <target>` | Use tracking skill where available |
| `search <container\|direction>` | Check a closed, locked container or door for traps and disarm one (search skill); not a room search for hidden exits |
| `recall`, `/` | Pray for transport to your recall point; a curse blocks it |
| `recall set` | Make this room your recall point (once per 30 minutes) |
| `recall default` | Send your recall point back to the Temple |
| `recall where` | Show your recall point and when you may move it |
| `where`, `areas`, `scan` | Orient within the world |
| `astral walk`, `project`, `shift`, `telekinesis`, `tk` | Specialized psionic travel, scouting, and retrieval when learned |

Contextual movement may also be attached to `push`, `pull`, `move`, `turn`,
`flip`, `burn`, or a specific noun described in the room.

## Observation And Character Information

| Commands | Use |
|---|---|
| `look`, `examine`, `read` | Inspect the room, targets, or text; `read` a Hyrule compass points toward the Triforce chest |
| `listen <direction>` | Listen through a closed, non-secret door for anyone beyond it (Listen at Door skill) |
| `score`, `attribute`, `affect` | Level, stats, resources, and active effects |
| `maps [all]`, `read <map>` | The maps you hold and how much of each area you have walked; `read` an area's map to learn it (the Mudlet map shows only what you know) |
| `alignment`, `devote light/dark/balance` | Your alignment tier, its perks and how to move it; `devote` works at the Temple |
| `achievements [view]` | Points and progress for levels, bosses, relics, crafting, economy, unusual deaths, quests, exploration, and Hyrule |
| `diary [yesterday \| yyyy-mm-dd \| list]` | Your day written down: time played, levels, kills, deaths, quests, achievements, skills, areas, things gained, coin in and out (the last 30 days) |
| `equipment`, `inventory`, `worth` | Worn items, carried items, and carried coin with experience to level (`balance` shows the bank) |
| `consider <target>` | Size up a fight before starting it |
| `danger` | Danger Sense: the other players in your area, roughly how far, and how many are stealthed |
| `compare <item> [item]`, `compare upgrades [slot]`, `compare profile` | Which gear makes you hit harder; the best gear you can get today |
| `lore <object>` | Inspect an item with lore knowledge |
| `count` | Show population/count information supported by the game |
| `time`, `weather` | World time and environmental state |
| `who`, `whois`, `wizlist` | Connected players and staff information |
| `info`, `news`, `changes`, `motd`, `story` | Server and world notices |
| `credits`, `rules` | Attribution and conduct rules |

## Inventory And Equipment

| Commands | Use |
|---|---|
| `get`, `take` | Pick up an object or retrieve it from a container |
| `pick` | Pick a lock on a door or container; a lock that cannot be picked says so at once |
| `put` | Place an object in a container |
| `drop` | Drop an object, or coins: `drop 20 gold` |
| `give` | Give an object or coins: `give 5 silver guard` |
| `wear`, `wield`, `hold` | Equip an object; `hold` takes wands, staves and other held items (a light goes in the light slot) |
| `secondary` | Equip or manage a secondary weapon where allowed |
| `remove` | Unequip an object |
| `sacrifice`, `junk` | Destroy an object lying on the ground for a little copper (`junk` is `sacrifice`) |
| `open`, `close`, `lock`, `unlock`, `pick`, `doorbash` | Operate doors and containers |
| `fill`, `drink`, `eat`, `feed` | Food, drink, and containers |
| `quaff`, `recite`, `brandish`, `zap` | Activate potions, scrolls, staves, and wands |
| `brew`, `concoct`, `scribe` | Create class-supported consumables |
| `shoot` | Fire a bow at an adjacent target; in Hyrule, its bow (with a quiver, a gold coin a shot) or a boomerang at an enemy in the room; or the Silver Arrow finisher |
| `bomb`, `burn`, `flip`, `play`, `pull`, `push`, `move`, `turn` | Item or area-specific interactions; in Hyrule `bomb` and `burn` also strike an enemy |
| `hearts` | Your Hyrule heart count, which the White and Magical Swords ask for |

Normal bow shooting requires Archery, targets visible mobiles through open
adjacent exits, and does not use a separate ammunition item. Shots can improve
Archery, and normal ranged attacks cannot target players. In Hyrule, a level 54
or higher character wielding the Silver Arrow can use `shoot ganon` in the same
room after Ganon flashes red. That special shot requires no Archery skill and
does not consume the Arrow.

## Shops, Services, Money, And Games

| Commands | Use |
|---|---|
| `list` | List a shop, healer, or context-specific service |
| `buy`, `sell`, `value` | Trade with a shopkeeper; `sell` is immediate, so `value` first |
| `repair` | Repair a worn or carried item at a smith; price in coins |
| `heal` | List or buy healer services |
| `donate` | Send an eligible object to donation handling |
| `balance`, `deposit`, `withdraw` | Use a bank |
| `exchange`, `convert` | Convert supported currency or resources |
| `gamble`, `slots`, `bet`, `roulette`, `poker` | Use supported gambling NPCs or rooms |

Invoke a command without enough arguments to see its local syntax. Shop and
bank commands require the appropriate NPC or room.

## Combat

| Commands | Use |
|---|---|
| `kill`, `hit` | Start a fight with a creature; both refuse players |
| `murder` | Attack a player; the victim yells and it is logged. `mur`/`murde` only say to type it in full |
| `cast` | Cast a known spell |
| `flee` | Attempt to escape combat |
| `wimpy` | Set automatic flee threshold |
| `rescue` | Attempt to redirect an ally's opponent |
| `backstab`, `bs` | Thief-style opening attack when available |
| `bash`, `trip`, `dirt`, `disarm`, `kick` | Common physical control and attacks |
| `berserk`, `smite`, `shove` | Specialized physical abilities |
| `blinding`, `fists`, `stunning`, `nerve`, `steel`, `crane`, `iron` | Monk martial arts, unarmed: Blinding Fists is a flurry of four to six blows, Stunning Blow stuns, Nerve Damage lowers dexterity and stops natural recovery |
| `confuse`, `ego whip`, `mindblast`, `nightmare`, `pyrotechnics`, `torment` | Specialized magical or psionic combat |
| `mindbar`, `mindleech`, `enervate`, `psionic`, `psychic`, `transfusion` | Specialized psionic defense, draining, and healing abilities |
| `topten` | The leading player killers |
| `dummy`, `dummy report`, `dummy leaderboard` | The training yard: set up the dummy, read a run, see the benchmark board (down then south from the Oak Tree Square) |

This is not a skill list. `skills` and `spells` are authoritative for the
character because learned commands and level gates vary by build.
See the [Psionics Guide](psionics.md) for all 17 powers and their costs.

## Rest, Visibility, And Position

| Commands | Use |
|---|---|
| `stand`, `sit`, `rest`, `sleep`, `wake` | Change position and recovery state |
| `hide`, `sneak`, `stealth`, `visible` | Control learned visibility states |
| `levitate` | Use learned levitation |
| `arrive`, `depart` | Customize supported arrival/departure behavior |

Many commands require standing, resting, or fighting. If a valid command is
rejected, check position and active effects with `score` and `affect`.

## Advancement, Guilds, And Remorts

| Commands | Use |
|---|---|
| `leveling` | Review advancement state |
| `practice` | List or improve abilities with a trainer |
| `train` | Improve supported attributes/resources |
| `groups` | Review skill groups |
| `gain`, `gainlist`, `teachlist` | Buy skills; list what you can learn and where; list who can practise what you know |
| `join` | Join a guild at Melancholy the guild clerk, levels 3 to 6, one gold; a castle head adds castle members |
| `remort` | Begin a new life at level 3 from levels 54-58 (`help remort`, `help 'remort gifts'`, `help 'remort classes'`) |
| `outfit` | Request supported starter equipment |
| `roll` | Use character-roll behavior where allowed |

Choose a guild before level 6. See [Player Guide](player-guide.md) for the exact
remort thresholds and class/race restrictions.

## Groups And Followers

| Commands | Use |
|---|---|
| `follow` | Follow another character or stop following self |
| `group` | Review or change group membership |
| `gtell` | Send a group message |
| `report` | Say your current and maximum hit points, mana and endurance, and your experience, to the room |
| `order` | Command supported charmed followers |
| `split` | Split coins with the group: `split 30 silver` (gold if no kind is named) |
| `autoassist`, `autosplit` | Toggle automatic group behavior |
| `nofollow`, `noloot` | Set follower and corpse-loot preferences |
| `nosummon` | Refuse supported summon effects |

## Communication And Notes

| Commands | Use |
|---|---|
| `say`, `'` | Speak in the current room |
| `tell`, `reply` | Private conversation |
| `gossip`, `question`, `shout`, `yell`, `music` | Public or regional channels |
| `gtell` | Group channel |
| `emote`, `pose` | Role-play actions |
| `note` | Use the in-game note system |
| `channels` | Review channel settings |
| `quiet`, `deaf` | `quiet`: only says and emotes; `deaf`: no tells. `shout` alone toggles hearing shouts |
| `ignore` | Ignore a named player |
| `beep` | Staff-level or context-limited alert command |
| `afk [message]` | Mark yourself away; tellers see your message; sending a tell or reply clears it |

Some channel commands are level-gated or may be disabled by local rules.

## Quests And PK

| Commands | Use |
|---|---|
| `aquest` | Main automated quest command family |
| `pkill <password>` | Become a player killer for good, from level 15 (staff can lift it; a remort clears it) |
| `steal` | Attempt theft; rules and consequences apply. A fumble is bad luck; "too wary" means the target is beyond your level |
| `murder` | Explicit player-hostile attack |

Use `rules`, `help pkill`, `help aquest`, and local staff guidance before taking
an irreversible action.

## Preferences And Output

| Commands | Use |
|---|---|
| `autolist` | Show automatic settings |
| `autoexit`, `autogold`, `autoloot`, `autosac`, `autosplit`, `autoassist` | Toggle automatic actions |
| `brief`, `compact`, `scroll` | Control output density and paging |
| `color` | Configure color |
| `damagenumbers` | Toggle numeric damage display |
| `prompt` | Configure the command prompt |
| `alias` | Manage server-side aliases; one may run up to ten commands separated by `;` |
| `description`, `title` | Customize character presentation; a title you set stays through levels until `title default` |
| `afk [message]` | Toggle away status |

`AUTOGOLD` takes currency directly from a defeated mobile's corpse when
`AUTOLOOT` is off. `AUTOSAC` sacrifices only empty corpses; anything that was
not selected or could not be carried remains safely in the corpse.

## Client Features

`map`, `mudlet`, `gmcp`, and `webclient` are help topics rather than game
commands. The official Mudlet package provides gauges and an automatic mapper;
its local `tocgui status`, `tocgui off`, and `tocgui on` aliases inspect or
toggle that interface. The first-party browser client provides aliases,
semicolon command chains, quick actions, reconnect support, and transcript
download, but does not currently include Mudlet's automatic mapper. See the
[Game Client Guide](game-client-guide.md) and the corresponding live help.

## Character And Session Management

| Commands | Use |
|---|---|
| `save` | Save now (the game also saves about every five minutes); keys other than Hyrule's small keys, blank maps and quest recovery items are never saved |
| `quit` | Leave the game normally |
| `qui` | Only a reminder: `quit` must be typed in full (`quie` is `quiet`) |
| `password` | Change the character password |
| `delete` | Begin permanent character deletion; read every confirmation |

Use a unique password. Passwords are stored as SHA-512 crypt hashes and a new
one counts every byte; a password carried over from the old DES format counts
only its first eight until it is changed. The password travels over unencrypted
Telnet.

## Feedback And Help

| Commands | Use |
|---|---|
| `help <topic>` | Search in-game help |
| `commands` | Show currently available commands |
| `socials` | List social actions |
| `bug` | Report incorrect behavior |
| `typo` | Report text or spelling problems |
| `idea` | Submit a suggestion |
| `rules` | Read conduct rules |
| `credits` | Read codebase attribution |

When reporting a problem, include the room name/vnum if visible, the command,
the exact response, the expected result, and whether it is repeatable. Never
include a password or raw player file.

## The Oracle

An in-game seer who answers questions about the game.

| Commands | Use |
|---|---|
| `pray` | Go to the Oracle's sanctum (one seeker at a time) |
| `say <anything>` | In her sanctum, everything you say is said to her |
| `ask <question>` | The same, as a command |
| `say done` | Return to where you prayed (or go `down` through the beads) |
| `say wrong` | Report her last answer as wrong (filed for staff; she stops giving it) |

- She knows commands, classes, races, remorts, skills, areas, leveling, and
  what gear to seek for your class and level, and she has read the game's
  help. She can see what players and creatures wear, where things are right
  now, and where items drop. Follow-up questions in one audience work.
- She answers only questions about Times of Chaos, and keeps answers short.
- An audience lasts at most five minutes, less if you fall silent. However it
  ends, you return to where you prayed, dazed for a moment.
- You cannot pray in battle, while your blood is still up, while something
  hunts you, or from a death trap.
- Repeated off-topic questions make her leave; the gods may bar a troublemaker.

## Related Guides

- [Player Guide](player-guide.md)
- [Advanced Gear Comparison](gear-comparison.md)
- [Hyrule: First Quest](hyrule-area.md)
- [Wiki Home](Home.md)

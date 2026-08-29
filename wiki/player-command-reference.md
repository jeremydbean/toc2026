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
staff-assisted recovery. Multiword spell names normally use quotes:

```text
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
| `enter <target>` | Enter a supported object, portal, or feature |
| `climb`, `crawl`, `jump` | Use area-defined movement features |
| `ride`, `mount`, `dismount` | Control supported mounts |
| `track <target>` | Use tracking skill where available |
| `search` | Search the current room |
| `recall`, `/` | Attempt random recall to an eligible room |
| `where`, `areas`, `scan` | Orient within the world |
| `astral walk`, `project`, `shift`, `telekinesis`, `tk` | Specialized psionic travel, scouting, and retrieval when learned |

Contextual movement may also be attached to `push`, `pull`, `move`, `turn`,
`flip`, `burn`, or a specific noun described in the room.

## Observation And Character Information

| Commands | Use |
|---|---|
| `look`, `examine`, `read`, `listen` | Inspect the room, targets, text, or sound |
| `score`, `attribute`, `affect` | Level, stats, resources, and active effects |
| `achievements [view]` | Points and progress for levels, bosses, relics, crafting, unusual deaths, quests, exploration, and Hyrule |
| `equipment`, `inventory`, `worth` | Worn items, carried items, and money |
| `consider <target>`, `danger` | Estimate nearby danger |
| `compare ...`, `compare profile` | Analyze equipment and inferred playstyle |
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
| `put` | Place an object in a container |
| `drop` | Drop an object |
| `give` | Give an object or currency to another character |
| `wear`, `wield`, `hold` | Equip an object in a compatible slot |
| `secondary` | Equip or manage a secondary weapon where allowed |
| `remove` | Unequip an object |
| `sacrifice`, `junk` | Dispose of a supported object |
| `open`, `close`, `lock`, `unlock`, `pick`, `doorbash` | Operate doors and containers |
| `fill`, `drink`, `eat`, `feed` | Food, drink, and containers |
| `quaff`, `recite`, `brandish`, `zap` | Activate potions, scrolls, staves, and wands |
| `brew`, `concoct`, `scribe` | Create class-supported consumables |
| `shoot` | Fire a bow at an adjacent target, or use Hyrule's Silver Arrow finisher |
| `bomb`, `burn`, `flip`, `play`, `pull`, `push`, `move`, `turn` | Item or area-specific interactions |

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
| `buy`, `sell`, `value` | Trade with a shopkeeper |
| `repair` | Request repair from a compatible NPC |
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
| `kill`, `hit` | Start ordinary combat against an NPC target |
| `murder` | Explicit hostile player attack; read PK rules first |
| `cast` | Cast a known spell |
| `flee` | Attempt to escape combat |
| `wimpy` | Set automatic flee threshold |
| `rescue` | Attempt to redirect an ally's opponent |
| `backstab`, `bs` | Thief-style opening attack when available |
| `bash`, `trip`, `dirt`, `disarm`, `kick` | Common physical control and attacks |
| `berserk`, `smite`, `shove`, `stunning`, `nerve` | Specialized physical abilities |
| `blinding`, `fists`, `steel`, `crane`, `iron` | Monk and martial abilities |
| `confuse`, `ego whip`, `mindblast`, `nightmare`, `pyrotechnics`, `torment` | Specialized magical or psionic combat |
| `mindbar`, `mindleech`, `enervate`, `psionic`, `psychic`, `transfusion` | Specialized psionic defense, draining, and healing abilities |
| `topten` | Show supported combat or PK ranking information |

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
| `gain`, `gainlist`, `teachlist` | Review or purchase guildmaster options |
| `join` | Join a supported guild |
| `remort` | Begin a remort after reaching the current life cap |
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
| `report` | Report current resources |
| `order` | Command supported charmed followers |
| `split` | Split currency with the group |
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
| `quiet`, `deaf` | Suppress channel categories |
| `ignore` | Ignore a named player |
| `beep` | Staff-level or context-limited alert command |
| `afk` | Mark yourself away from keyboard |

Some channel commands are level-gated or may be disabled by local rules.

## Quests And PK

| Commands | Use |
|---|---|
| `aquest` | Main automated quest command family |
| `pkill` | Review or control supported PK state |
| `steal` | Attempt theft; rules and consequences apply |
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
| `alias` | Manage server-side aliases |
| `description`, `title` | Customize character presentation |
| `afk` | Toggle away status |

`AUTOGOLD` takes currency directly from a defeated mobile's corpse when
`AUTOLOOT` is off. `AUTOSAC` sacrifices only empty corpses; anything that was
not selected or could not be carried remains safely in the corpse.

## Character And Session Management

| Commands | Use |
|---|---|
| `save` | Persist the character |
| `quit` | Leave the game normally |
| `qui` | Deliberately incomplete guard against accidental abbreviation |
| `password` | Change the character password |
| `delete` | Begin permanent character deletion; read every confirmation |

Use a unique password. Only the first eight bytes affect the current DES hash,
and the password travels over unencrypted Telnet.

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

## Related Guides

- [Player Guide](player-guide.md)
- [Advanced Gear Comparison](gear-comparison.md)
- [Hyrule: First Quest](hyrule-area.md)
- [Wiki Home](Home.md)

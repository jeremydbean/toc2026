# Achievement System

Times of Chaos has a permanent, character-based achievement system inspired by
the progression and collection model used by modern MMORPGs. Achievements are
recognition and long-term goals: they award points, dates, and announcements,
but never combat stats or economic rewards.

The catalog holds **378** achievements: 203 from before 2026-10-25 and the
175 of the 2026-10-25 expansion (rare encounters, more named bosses,
combat and teamwork, skills and crafting, quests and exploration, Hyrule's
actions and secrets, collection, services and world events). Every point
earned is also a **mark** that can be spent at `REDEEM` on cosmetic and
convenience perks; spending marks never lowers points.

## Player Commands

| Command | Result |
|---|---|
| `achievements` | Compact two-column category totals, points, and five newest unlocks |
| `achievements <category>` | One category with requirements and live progress |
| `achievements earned` | Every earned achievement and date |
| `achievements incomplete` | Remaining visible goals and hidden entries |
| `achievements all` | Entire catalog, in parts: `achievements all 2` is the second |
| `achievements <words>` | Search keys, titles, and descriptions (hidden ones never match) |
| `redeem` | Marks held and what they buy |

Categories are `character`, `combat`, `encounters`, `quests`, `exploration`,
`collection`, `crafting`, `misadventure`, `economy`, and `hyrule`. The command
accepts normal unambiguous command prefixes, but full category names are
clearest. `score` also shows earned count and achievement points.

The normal summary is sized to fit the default page length. Longer category,
filter, and search results use the standard game pager and honor each player's
color and scroll settings. A list view is cut into parts of at most 12,000
bytes of raw text (`ACHIEVEMENT_PART_BYTES`), each ending at an entry, so a
part always fits the pager's 32,000-byte block with colour on; the footer
names the part, how many there are, and the command for the next. Any view
takes a trailing part number: `achievements combat 2`, `achievements dragon 2`.

An unlock displays its title, description, points, and new total. Other players
in the room see a short announcement. Hidden achievements display a generic
placeholder until earned, match no search, and are never sent over GMCP until
earned (the GMCP feed is the unlock toast alone). A visible meta never names
its hidden members: Tools of the Hero says "the secret ones included".

## What Is Tracked

| Category | Milestones |
|---|---|
| Character | Levels 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 58, and 59; every remort from the first to the fifth; 24 hours, seven days, and thirty days played; Well Rested, for coming back with rested experience |
| Combat | 1, 100, 500, 1,000, 2,500, 5,000, 10,000, 25,000 and 50,000 mobile kills; 1, 10, 25, 50, 100, 250 and 500 qualifying player kills; a hidden Farslay feat; Top of the Board, for posting the best standard benchmark in the training yard |
| Encounters | Seventeen named endgame bosses plus five-boss and full-catalog metas (frozen); seven more bosses and three regional metas (2026-10-25); treasure goblins, the Great Black Dragon, Herbie's visit |
| Quests | 1, 10, 50, 100, 250, 500, and 1,000 completions; streaks of 5, 10, 25, 50, and 100; rush, emergency, final-minute, gamble-win, and keepsake feats; daily quests: a first daily, a full day of three, daily streaks of 7, 30 and 100 days, and a train bought with daily points |
| Exploration | Thirty-nine landmarks across the world, from the Pet Shop and Mud School six rooms out to Valhalla at ninety-four, plus arrival in Hyrule and discovery of all nine dungeon entrances. Every one is the destination of a published route in `webadmin/directions.json`, so all of them are reachable on foot |
| Collection | Seventeen rare or special-source relics plus 5, 10, and 17-relic metas |
| Crafting | Brewing, concocting, scribing, the hidden Farslay-scroll recipe, and a crafting meta |
| Misadventure | 1, 10, 25, 50, 100, and 500 deaths; six unusual death causes; a hidden death meta |
| Economy | Bank deposits and balances to 1,000 platinum, interest, carried wealth to 1,000 platinum, all four denominations at once, casino lifetime totals won and lost to a million gold, and hidden slots, roulette, and poker feats |
| Hyrule | Signature items, shards, maps, compasses, nine bosses, Ganon, Zelda, and meta completion |

The world-boss list is the Tarrasque, the Borg, Korzath, the Master Guardian,
the brilliant white light, Smaug, the minotaur god, Zeus, Odin, Ra, Dagahze,
Lolth, Eilistraee, the Dracolich, the Ashen Herald, Lord British, and Lanatir.
Hyrule's boss achievements correspond to the principal encounter in each First
Quest dungeon. Any listed boss kill awards every non-NPC group member present
in the boss room, not only the character delivering the final blow. Ordinary
lifetime kill progress still belongs to the credited killer.

The rare-relic list includes the Power of the world, Lifetaker, Starlight
Sword, minotaur-god claws, the Aegis and Thunder Bolt, Ra's amulet and Sword of
the Sun, Elfbane, Lanatir's sphere and Hammer of Wrath, an Angel's Heart, Lord
British's crown/sceptre/amulet, Farslayer, and the quest-master Scroll of
Farslay. Acquiring one is enough; the achievement remains after the object is
used, lost, stored, or destroyed.

Automatic-quest achievements also recognize completing a rush contract,
surviving an emergency contract (the hidden five-minute, five-times-reward
one), turning in a quest during its final minute, winning double-or-nothing,
and acquiring the questmaster's keepsake. Kill objectives award progress to
eligible group members present for the kill, including when a controlled pet
lands the final blow.

Unusual-death achievements distinguish a flagged room death trap, a room-wide
puzzle trap, a lethal action item, another player's Farslay, a self-inflicted
Farslay backlash, and a death ray. Arena knockouts and divine-protection saves
are not true deaths and do not advance the lifetime death counter.

Maps, compasses, and Triforce shards are remembered when acquired, even if the
item is later spent, dropped, or stored. On migration, currently carried items
are scanned recursively, so items inside bags also count. The Master Sword,
Silver Arrow, and Triforce (COMBINE) achievements require possession when the
state is evaluated.

Economy balance milestones use exact copper value across all denominations.
Bank deposits and interest, emptying an account, a three-seven slots jackpot,
a straight-up roulette win, and a royal flush are event achievements. Lifetime
casino totals record net winnings and actual losses and saturate safely at the
save format's maximum value.

## Marks And REDEEM

Marks are points earned less marks spent, so a character who earned points
before REDEEM existed has every one of them to spend; nothing migrated. The
spend is saved as `AchSpent <spent> 0` and rolls back with the earned set in a
PRESTORE, so a rollback takes back a purchase and its marks together. What
marks buy changes how a character looks or saves time, never stats, coin,
trains or gear power:

| Command | Marks | Effect |
|---|---|---|
| `redeem recall` | 10 | Clears the recall-point cooldown, so `recall set` works now |
| `redeem trophy <achievement>` | 25 | A keepsake trophy (object 95, limbo.are) naming one you earned |
| `redeem stash` | 40 | 25 more stash slots, never past the 500 ceiling |
| `redeem restring <weapon> <name>` | 100 | A new name for a weapon you carry: 4-45 plain characters, no colour, keeping one of its keywords |

Every purchase is written to `log/toc.log` (`Redeem: <name> spent <n> marks`).

## The 2026-10-25 Expansion

### Rules every new achievement keeps

- **Awarded at the successful event, never at the command.** Each hook sits
  after the refusals and the roll: the blow that collapsed the portal, the
  disarm that took the weapon, the heal that restored hit points, the
  craft that produced the potion.
- **Staff earn none of them.** `ACH_STAFF` is `IS_TRUSTED(ch, LEVEL_IMMORTAL)`,
  the rule every command gate uses: a staff kill, purchase or walk is not
  play. A staff-started disaster or dragon, and HERBIE summoned by staff,
  award nothing.
- **Deduplicated by real identity.** Rooms by vnum, areas by a hash of the
  area file name (`achievement_area_id`), Vesh stock visits by the stock's
  id, Vesh purchases by object prototype, recipes by method plus signature
  spell, the dragon and a disaster by the encounter in progress, quest
  areas by the target's room at assignment.
- **The original metas are frozen.** Boss Hunter, Conqueror of Chaos, the
  three relic metas, Artisan of Chaos, Death Becomes You and Hero of Hyrule
  count explicit lists (`cohort_*_v1` in `achievements.c`) exactly as they
  stood on 2026-10-24. Adding a boss, a relic, a crafting feat or a death
  never changes what they ask. The new metas count their own lists.
- **Points are cosmetic**: about 5 for an introduction, 10-25 for
  milestones, 30-60 for hard feats and 75-100 for major metas.

### Group, pet and challenge credit

- **Bosses** keep the existing rule: everyone in the killer's group standing
  in the boss's room. A pet's or a raised servant's kill is its master's.
  Prince Starfire is WIMPY, so his row counts a death anywhere in the
  Glitter Palace (a negative room in the table means "this room's area").
- **Goblin and dragon kills** go to the credited player and their group in
  the room (`achievement_party_count`), real goblin only (a copy staff
  loaded runs and spills, but counts for nothing).
- **The Chase Is On** counts the goblin's flights since he last escaped by
  portal, drifted or was born (`gob_chase_flights`), not his whole life.
- **You Picked the Wrong Passenger** wants the carried-off player to have
  struck the dragon (any blow, landed or not) and to be in at the kill,
  as killer or group member. **Discretion Is an Option** wants them alive,
  with no death since they were taken, out of the dragon's room when it
  takes off, and never to have struck it.
- **Faithful Servant** counts a kill whose blow was a charmed or pet NPC's,
  credited to its player master. **By a Thread** counts a kill credited to a
  player standing in the room at 5% of maximum hit points or less, against
  a monster no more than five levels below them. Neither counts charmed,
  pet or raised-undead victims.
- **A Fair Fight** (Hyrule's nine band challenges): at the guardian's death
  every player in the room, group or not, must be at or below the top of
  the dungeon's band (8, 14, 20, 27, 33, 40, 46, 52, 59, from
  `LEVEL_BANDS` in `scripts/build_hyrule_manifest.py`), no staff may be
  there, and no charmed or pet NPC above the band. Anyone overleveled
  spoils it for everybody.
- **Field Medic** counts a heal on another player who is fighting an NPC
  (not the training dummy) and only when hit points actually rose.
  **Clear Eyes, Clean Blood** counts blindness, poison or disease really
  dispelled from another player.
- **Disasters** mark each player a strike reaches (`disaster_area`,
  `disaster_kind`, the death count then); the disaster's own end awards
  everyone it marked who is alive with no death since. A flood or tornado
  that swept someone out of the area still counts. The dragon is not a
  disaster for this purpose and disasters cannot kill, so there are no
  disaster-death feats.

### Persistence

New state is saved by name, never by position, so the lists may grow:

- `AchCount <name> <value>` for each counter above zero (goblins, dragons,
  vesh-visits, rescues, disarms, heals, cures, narrow-wins, servant-kills,
  brews, concoctions, scrolls, training-foods, rush-quests,
  emergency-quests, daily-quests, repairs).
- `AchSet <name> <id or a-b> ... ~` for each identity set (vesh-items,
  recipes, quest-areas, areas, rooms, daily-kinds, psi-disciplines),
  sorted, with runs of consecutive ids written `a-b`. An unknown name is
  read through and dropped. Each set has a hard bound (rooms 16,384).
- `AchSpent <spent> 0` for REDEEM.

All of it is under case 'A' of `fread_char`, lives in `PC_DATA`, is freed
with the character (`achievement_free`), and is untouched by a remort.

### Migration

Only facts the save proves are backfilled, at the first login: abilities and
weapon proficiencies at 100%, psionic powers held, Hyrule secret bits
(money caves, bomb bags, take-any choices), a stash already at 500, relics
held now, and metas whose members are already earned. Every counter starts
at zero and every set empty: nothing is inferred from wealth, possessions or
logs. Event feats (stash use, crafting, Hyrule actions, kills) begin when
the hooks are installed.

### Catalog

| Key | Title | Criterion | Pts | Hidden | Hook | Migration |
|---|---|---|---|---|---|---|
| `goblin-kills-1` | Follow the Money I | Be in at the kill of a treasure goblin. | 10 |  | goblin.c treasure_goblin_slain -> achievement_party_count | starts at 0 |
| `goblin-kills-10` | Follow the Money II | Be in at the kill of 10 treasure goblins. | 25 |  | goblin.c treasure_goblin_slain -> achievement_party_count | starts at 0 |
| `goblin-kills-50` | Follow the Money III | Be in at the kill of 50 treasure goblins. | 50 |  | goblin.c treasure_goblin_slain -> achievement_party_count | starts at 0 |
| `goblin-portal-denied` | Portal Denied | Land a blow on a treasure goblin while his escape portal opens, and collapse it. | 15 | yes | goblin.c treasure_goblin_struck (portal collapses) | from now |
| `goblin-long-chase` | The Chase Is On | Be in at a treasure goblin's kill after he has fled twelve times in that chase. | 25 |  | goblin.c treasure_goblin_slain (12+ flights this chase) | from now |
| `dragon-kills-1` | Dragon Trouble I | Be in at the kill of a Great Black Dragon. | 20 |  | disaster.c disaster_dragon_slain -> achievement_party_count | starts at 0 |
| `dragon-kills-5` | Dragon Trouble II | Be in at the kill of 5 Great Black Dragons. | 35 |  | disaster.c disaster_dragon_slain -> achievement_party_count | starts at 0 |
| `dragon-kills-25` | Dragon Trouble III | Be in at the kill of 25 Great Black Dragons. | 50 |  | disaster.c disaster_dragon_slain -> achievement_party_count | starts at 0 |
| `dragon-passenger` | You Picked the Wrong Passenger | Be carried off by the black dragon, then help kill that same dragon. | 30 | yes | disaster.c disaster_dragon_slain | from now |
| `dragon-discretion` | Discretion Is an Option | Walk away alive from the black dragon that carried you off, without striking it. | 15 | yes | disaster.c dragon_update (takes off) | from now |
| `vesh-visits-1` | Under the Counter I | Buy from Vesh the Smuggler on one of his visits. | 10 |  | blackmarket.c black_market_record (first buy from a new stock) | starts at 0 |
| `vesh-visits-10` | Under the Counter II | Buy from Vesh the Smuggler on 10 different visits. | 25 |  | blackmarket.c black_market_record (first buy from a new stock) | starts at 0 |
| `vesh-visits-25` | Under the Counter III | Buy from Vesh the Smuggler on 25 different visits. | 40 |  | blackmarket.c black_market_record (first buy from a new stock) | starts at 0 |
| `vesh-sold-out` | Sold Out | Buy all five things from one of Vesh's full five-item stocks. | 30 | yes | blackmarket.c black_market_record | from now |
| `vesh-items-5` | Unusual Inventory I | Buy 5 different kinds of item from Vesh. | 10 |  | blackmarket.c black_market_record | starts empty |
| `vesh-items-15` | Unusual Inventory II | Buy 15 different kinds of item from Vesh. | 25 |  | blackmarket.c black_market_record | starts empty |
| `vesh-items-30` | Unusual Inventory III | Buy 30 different kinds of item from Vesh. | 40 |  | blackmarket.c black_market_record | starts empty |
| `boss-moon-guardian` | By the Light of the Moon | Defeat the Guardian of the Moon in Valhalla's moonlit courtyard. | 50 |  | fight.c raw_kill_internal -> achievement_record_kill (group in room) | from now |
| `boss-archangel` | Beyond the Pearly Gates | Defeat the archangel at the pearly white gates of the Crypt. | 50 |  | fight.c raw_kill_internal -> achievement_record_kill (group in room) | from now |
| `boss-blaine` | Blaine Is a Pain | Defeat Blaine the Mono in its control room in Lud. | 60 |  | fight.c raw_kill_internal -> achievement_record_kill (group in room) | from now |
| `boss-roland` | The Gunslinger Falls | Defeat Roland in his private cabin. | 55 |  | fight.c raw_kill_internal -> achievement_record_kill (group in room) | from now |
| `boss-starfire` | The Prince Abdicates | Defeat Crown Prince Augustus Starfire in the Glitter Palace. | 45 |  | fight.c raw_kill_internal -> achievement_record_kill (group in room) | from now |
| `boss-headless-horseman` | Heads Will Roll | Defeat the Headless Horseman when he rides into the Oak Tree Square. | 40 |  | fight.c raw_kill_internal -> achievement_record_kill (group in room) | from now |
| `boss-father-winter` | The Thaw | Defeat Father Winter when he comes to the Oak Tree Square. | 40 |  | fight.c raw_kill_internal -> achievement_record_kill (group in room) | from now |
| `region-dark-tower` | All Things Serve the Beam | Defeat the Borg, Korzath, the Master Guardian, Blaine and Roland. | 100 |  | meta: dark tower | from the members |
| `region-pantheon` | Twilight of the Gods | Defeat Zeus, Odin, Ra and the Guardian of the Moon. | 90 |  | meta: pantheon | from the members |
| `region-heavens-gate` | Storming Heaven | Defeat the white light, the archangel, Prince Starfire and Dagahze. | 90 |  | meta: heavens gate | from the members |
| `rescue-1` | Not Today I | Rescue a groupmate from a monster once. | 5 |  | fight.c do_rescue (attacker is an NPC) | starts at 0 |
| `rescue-25` | Not Today II | Rescue a groupmate from a monster 25 times. | 15 |  | fight.c do_rescue (attacker is an NPC) | starts at 0 |
| `rescue-100` | Not Today III | Rescue a groupmate from a monster 100 times. | 30 |  | fight.c do_rescue (attacker is an NPC) | starts at 0 |
| `disarm-1` | Empty Hands I | Knock the weapon out of a monster's hands once. | 5 |  | fight.c disarm (NPC weapon leaves hand) | starts at 0 |
| `disarm-25` | Empty Hands II | Knock the weapon out of a monster's hands 25 times. | 15 |  | fight.c disarm (NPC weapon leaves hand) | starts at 0 |
| `disarm-100` | Empty Hands III | Knock the weapon out of a monster's hands 100 times. | 30 |  | fight.c disarm (NPC weapon leaves hand) | starts at 0 |
| `heals-10` | Field Medic I | Heal another player fighting a monster 10 times; overhealing does not count. | 10 |  | magic.c cure light/serious/critical, heal -> achievement_record_heal | starts at 0 |
| `heals-100` | Field Medic II | Heal another player fighting a monster 100 times; overhealing does not count. | 20 |  | magic.c cure light/serious/critical, heal -> achievement_record_heal | starts at 0 |
| `heals-500` | Field Medic III | Heal another player fighting a monster 500 times; overhealing does not count. | 40 |  | magic.c cure light/serious/critical, heal -> achievement_record_heal | starts at 0 |
| `cures-1` | Clear Eyes, Clean Blood I | Cure another player of blindness, poison or disease once. | 5 |  | magic.c cure blindness/poison/disease -> achievement_record_cure | starts at 0 |
| `cures-25` | Clear Eyes, Clean Blood II | Cure another player of blindness, poison or disease 25 times. | 15 |  | magic.c cure blindness/poison/disease -> achievement_record_cure | starts at 0 |
| `cures-100` | Clear Eyes, Clean Blood III | Cure another player of blindness, poison or disease 100 times. | 30 |  | magic.c cure blindness/poison/disease -> achievement_record_cure | starts at 0 |
| `narrow-win-1` | By a Thread I | Win a fight against a worthy monster on 5% of your hit points or less. | 10 |  | achievements.c achievement_record_kill | starts at 0 |
| `narrow-win-10` | By a Thread II | Win 10 fights against a worthy monster on 5% of your hit points or less. | 25 |  | achievements.c achievement_record_kill | starts at 0 |
| `narrow-win-50` | By a Thread III | Win 50 fights against a worthy monster on 5% of your hit points or less. | 45 |  | achievements.c achievement_record_kill | starts at 0 |
| `servant-kills-1` | Faithful Servant I | Have your pet or raised servant kill a monster. | 5 |  | achievements.c achievement_record_kill | starts at 0 |
| `servant-kills-100` | Faithful Servant II | Have your pet or raised servant kill 100 monsters. | 20 |  | achievements.c achievement_record_kill | starts at 0 |
| `servant-kills-1000` | Faithful Servant III | Have your pet or raised servant kill 1,000 monsters. | 40 |  | achievements.c achievement_record_kill | starts at 0 |
| `raise-skeleton` | Bare Bones | Raise a skeleton to serve you. | 10 |  | magic2.c spell_create_skeleton | from now |
| `raise-wraith` | A Chill in the Air | Raise a wraith to serve you. | 15 |  | magic2.c spell_create_wraith | from now |
| `raise-vampire` | Blood Pact | Raise a vampire to serve you. | 20 |  | magic2.c spell_create_vampire | from now |
| `necromancy-all` | Night of the Living Dead | Raise a skeleton, a wraith and a vampire. | 30 |  | meta: necromancy | from the members |
| `guardian-angel` | Guardian Angel | Earn Not Today III, Field Medic III and Clear Eyes, Clean Blood III. | 75 |  | meta: guardian angel | from the members |
| `mastered-1` | Practice Makes Permanent I | Bring an ability to 100%. | 10 |  | learned[] at 100 (check_improve, login) | from the save |
| `mastered-5` | Practice Makes Permanent II | Bring 5 different abilities to 100%. | 25 |  | learned[] at 100 (check_improve, login) | from the save |
| `mastered-15` | Practice Makes Permanent III | Bring 15 different abilities to 100%. | 45 |  | learned[] at 100 (check_improve, login) | from the save |
| `weapons-1` | Weapons Scholar I | Bring a weapon proficiency to 100%. | 10 |  | learned[] at 100 (check_improve, login) | from the save |
| `weapons-3` | Weapons Scholar II | Bring 3 weapon proficiencies to 100%. | 25 |  | learned[] at 100 (check_improve, login) | from the save |
| `weapons-5` | Weapons Scholar III | Bring 5 weapon proficiencies to 100%. | 40 |  | learned[] at 100 (check_improve, login) | from the save |
| `psi-four-disciplines` | Four Corners of the Mind | Use a psionic power from each of the four disciplines. | 30 |  | skills.c check_improve (success) -> achievement_record_psionic | from now |
| `psi-all-powers` | An Open Mind | Hold all seventeen psionic powers. | 50 |  | learned[] of the 17 powers (login, remort) | from the save |
| `brew-25` | Kettle's On I | Brew 25 herbal teas successfully. | 15 |  | magic2.c craft_succeeded | starts at 0 |
| `brew-100` | Kettle's On II | Brew 100 herbal teas successfully. | 30 |  | magic2.c craft_succeeded | starts at 0 |
| `brew-500` | Kettle's On III | Brew 500 herbal teas successfully. | 50 |  | magic2.c craft_succeeded | starts at 0 |
| `concoct-25` | Cauldron Keeper I | Concoct 25 potions successfully. | 15 |  | magic2.c craft_succeeded | starts at 0 |
| `concoct-100` | Cauldron Keeper II | Concoct 100 potions successfully. | 30 |  | magic2.c craft_succeeded | starts at 0 |
| `concoct-500` | Cauldron Keeper III | Concoct 500 potions successfully. | 50 |  | magic2.c craft_succeeded | starts at 0 |
| `scribe-25` | Scriptorium I | Scribe 25 scrolls successfully. | 15 |  | magic2.c craft_succeeded | starts at 0 |
| `scribe-100` | Scriptorium II | Scribe 100 scrolls successfully. | 30 |  | magic2.c craft_succeeded | starts at 0 |
| `scribe-500` | Scriptorium III | Scribe 500 scrolls successfully. | 50 |  | magic2.c craft_succeeded | starts at 0 |
| `recipes-5` | A Varied Recipe Book I | Successfully craft 5 different recipes. | 15 |  | magic2.c craft_succeeded (method + signature spell) | starts empty |
| `recipes-10` | A Varied Recipe Book II | Successfully craft 10 different recipes. | 30 |  | magic2.c craft_succeeded (method + signature spell) | starts empty |
| `recipes-20` | A Varied Recipe Book III | Successfully craft 20 different recipes. | 50 |  | magic2.c craft_succeeded (method + signature spell) | starts empty |
| `craft-triple` | Jack of All Trades | Earn Kettle's On I, Cauldron Keeper I and Scriptorium I. | 30 |  | meta: triple craft | from the members |
| `wedding-cake` | A Slice of Progress | Eat the Valhalla wedding cake and gain its train. | 25 |  | act_obj.c do_eat (ITEM_CAKE 9955) | from now |
| `training-food-1` | Seasoned Appetite I | Gain a train from a training cake. | 5 |  | act_obj.c do_eat (ITEM_CAKE) | starts at 0 |
| `training-food-5` | Seasoned Appetite II | Gain a train from 5 training cakes. | 20 |  | act_obj.c do_eat (ITEM_CAKE) | starts at 0 |
| `training-food-25` | Seasoned Appetite III | Gain a train from 25 training cakes. | 40 |  | act_obj.c do_eat (ITEM_CAKE) | starts at 0 |
| `rush-10` | Express Courier I | Complete 10 rush contracts in time. | 15 |  | quest.c complete_automatic_quest_body | starts at 0 |
| `rush-50` | Express Courier II | Complete 50 rush contracts in time. | 30 |  | quest.c complete_automatic_quest_body | starts at 0 |
| `rush-100` | Express Courier III | Complete 100 rush contracts in time. | 50 |  | quest.c complete_automatic_quest_body | starts at 0 |
| `emergency-5` | First Responder I | Complete 5 emergency contracts in time. | 20 |  | quest.c complete_automatic_quest_body | starts at 0 |
| `emergency-25` | First Responder II | Complete 25 emergency contracts in time. | 40 |  | quest.c complete_automatic_quest_body | starts at 0 |
| `emergency-50` | First Responder III | Complete 50 emergency contracts in time. | 60 |  | quest.c complete_automatic_quest_body | starts at 0 |
| `daily-10` | Daily Grind I | Complete 10 daily quests. | 10 |  | quest.c complete_daily_quest | starts at 0 |
| `daily-50` | Daily Grind II | Complete 50 daily quests. | 25 |  | quest.c complete_daily_quest | starts at 0 |
| `daily-100` | Daily Grind III | Complete 100 daily quests. | 45 |  | quest.c complete_daily_quest | starts at 0 |
| `quest-areas-5` | Work Takes Me Places I | Complete quests whose target was in 5 different areas. | 10 |  | quest.c quest_note_area | starts empty |
| `quest-areas-15` | Work Takes Me Places II | Complete quests whose target was in 15 different areas. | 25 |  | quest.c quest_note_area | starts empty |
| `quest-areas-30` | Work Takes Me Places III | Complete quests whose target was in 30 different areas. | 45 |  | quest.c quest_note_area | starts empty |
| `daily-every-kind` | A Complete Assignment | Finish a daily of every kind: a hunt and a recovery. | 10 |  | quest.c complete_daily_quest | starts empty |
| `areas-10` | Off the Beaten Path I | Set foot in 10 different areas of the world. | 10 |  | handler.c char_to_room -> achievement_record_room_visit | starts empty |
| `areas-25` | Off the Beaten Path II | Set foot in 25 different areas of the world. | 25 |  | handler.c char_to_room -> achievement_record_room_visit | starts empty |
| `areas-50` | Off the Beaten Path III | Set foot in 50 different areas of the world. | 50 |  | handler.c char_to_room -> achievement_record_room_visit | starts empty |
| `rooms-500` | Every Nook and Cranny I | Walk into 500 different rooms of the world. | 10 |  | handler.c char_to_room -> achievement_record_room_visit | starts empty |
| `rooms-1500` | Every Nook and Cranny II | Walk into 1,500 different rooms of the world. | 30 |  | handler.c char_to_room -> achievement_record_room_visit | starts empty |
| `rooms-3000` | Every Nook and Cranny III | Walk into 3,000 different rooms of the world. | 60 |  | handler.c char_to_room -> achievement_record_room_visit | starts empty |
| `landmarks-10` | Sightseer | Reach ten of the realm's landmarks. | 20 |  | meta: landmarks v1 | from the members |
| `landmarks-25` | Tour Guide | Reach twenty-five of the realm's landmarks. | 40 |  | meta: landmarks v1 | from the members |
| `landmarks-all` | Seen It All | Reach every one of the realm's landmarks. | 75 |  | meta: landmarks v1 | from the members |
| `hyrule-bomb-wall` | Blast Through | Bomb open a cracked wall in Hyrule. | 10 |  | act_obj.c do_bomb | from now |
| `hyrule-burn-bush` | Burning Bush | Burn away a bush hiding a secret in Hyrule. | 10 | yes | act_obj.c do_burn | from now |
| `hyrule-push-block` | Push Comes to Shove | Push a block aside to find the stairs beneath it. | 10 |  | act_obj.c do_manipulate (30513) | from now |
| `hyrule-move-armos` | Statue of Limitations | Move a sleeping Armos statue. | 10 | yes | act_obj.c do_manipulate (30514) | from now |
| `hyrule-drain-lake` | Play It Again | Drain the lake with the Recorder. | 15 | yes | act_obj.c do_play | from now |
| `hyrule-feed-goriya` | Grumble, Grumble | Feed the hungry Goriya. | 15 | yes | act_obj.c do_feed | from now |
| `hyrule-money-caves-1` | Everybody's Secret I | Claim the gold of a hidden money cave. | 5 |  | pcdata->hyrule_secrets bits (saved since 2026-10) | from the save |
| `hyrule-money-caves-7` | Everybody's Secret II | Claim the gold of seven hidden money caves. | 20 |  | pcdata->hyrule_secrets bits (saved since 2026-10) | from the save |
| `hyrule-money-caves-all` | Everybody's Secret III | Claim the gold of all fourteen hidden money caves. | 40 |  | pcdata->hyrule_secrets bits (saved since 2026-10) | from the save |
| `hyrule-bomb-bag-5` | Room for More | Buy the bigger bomb bag in Level 5. | 10 |  | pcdata->hyrule_secrets bits (saved since 2026-10) | from the save |
| `hyrule-bomb-bag-7` | Even More Room | Buy the bigger bomb bag in Level 7. | 10 |  | pcdata->hyrule_secrets bits (saved since 2026-10) | from the save |
| `hyrule-bomb-bags` | Sixteen Bombs | Own both bigger bomb bags. | 20 |  | pcdata->hyrule_secrets bits (saved since 2026-10) | from the save |
| `hyrule-take-any-all` | Take Any One You Want | Make your choice in all four take-any caves. | 25 |  | pcdata->hyrule_secrets bits (saved since 2026-10) | from the save |
| `hyrule-white-sword` | Master Using It | Be given the White Sword for your hearts. | 20 |  | hyrule.c hyrule_claim | from now |
| `hyrule-magical-sword` | Worthy of the Magical Sword | Be given the Magical Sword for your hearts. | 30 |  | hyrule.c hyrule_claim | from now |
| `hyrule-hint` | Pay Me and I'll Talk | Pay an old woman for a real hint. | 10 | yes | hyrule.c hyrule_paid_to_talk (right sum) | from now |
| `hyrule-pols-arrow` | An Arrow Through the Ear | Kill a Pols Voice with an arrow. | 15 | yes | hyrule.c hyrule_shoot (arrow kills) | from now |
| `hyrule-boomerang-stun` | It Comes Back | Stun an enemy with a boomerang and leave it standing. | 10 |  | hyrule.c hyrule_shoot (stun, survives) | from now |
| `hyrule-digdogger-recorder` | Cut Down to Size | Shrink a Digdogger with the Recorder. | 15 | yes | hyrule.c hyrule_play_recorder | from now |
| `hyrule-dodongo-bomb` | Dodongo Dislikes Smoke | Feed Dodongo a bomb. | 15 |  | hyrule.c hyrule_bomb_creature | from now |
| `hyrule-rod-fire` | Burn After Reading | Loose the Book of Magic's fire with the Magical Rod. | 15 | yes | hyrule.c hyrule_after_zap | from now |
| `hyrule-bait-calm` | Something to Chew On | Calm Hyrule's enemies with bait. | 10 |  | act_obj.c do_feed bait -> hyrule_set_bait | from now |
| `hyrule-tenth-bomb` | Untouchable Ten | Earn a bomb by killing ten enemies in a row without a wound. | 15 | yes | hyrule.c hyrule_note_kill | from now |
| `hyrule-chest-1` | Eagle's Hoard | Unlock and open the treasure chest of Level 1: The Eagle after defeating its guardian. | 10 |  | act_move.c do_open -> achievement_record_hyrule_chest (guardian beaten) | from now |
| `hyrule-chest-2` | Under the Moon | Unlock and open the treasure chest of Level 2: The Moon after defeating its guardian. | 13 |  | act_move.c do_open -> achievement_record_hyrule_chest (guardian beaten) | from now |
| `hyrule-chest-3` | Spoils of the Manji | Unlock and open the treasure chest of Level 3: The Manji after defeating its guardian. | 16 |  | act_move.c do_open -> achievement_record_hyrule_chest (guardian beaten) | from now |
| `hyrule-chest-4` | The Snake's Coil | Unlock and open the treasure chest of Level 4: The Snake after defeating its guardian. | 19 |  | act_move.c do_open -> achievement_record_hyrule_chest (guardian beaten) | from now |
| `hyrule-chest-5` | The Lizard's Cache | Unlock and open the treasure chest of Level 5: The Lizard after defeating its guardian. | 22 |  | act_move.c do_open -> achievement_record_hyrule_chest (guardian beaten) | from now |
| `hyrule-chest-6` | The Dragon's Treasury | Unlock and open the treasure chest of Level 6: The Dragon after defeating its guardian. | 25 |  | act_move.c do_open -> achievement_record_hyrule_chest (guardian beaten) | from now |
| `hyrule-chest-7` | The Demon's Vault | Unlock and open the treasure chest of Level 7: The Demon after defeating its guardian. | 28 |  | act_move.c do_open -> achievement_record_hyrule_chest (guardian beaten) | from now |
| `hyrule-chest-8` | The Lion's Share | Unlock and open the treasure chest of Level 8: The Lion after defeating its guardian. | 31 |  | act_move.c do_open -> achievement_record_hyrule_chest (guardian beaten) | from now |
| `hyrule-chest-9` | Ganon's Great Chest | Unlock and open the treasure chest of Level 9: Death Mountain after defeating its guardian. | 35 |  | act_move.c do_open -> achievement_record_hyrule_chest (guardian beaten) | from now |
| `hyrule-band-1` | Fair Fight: The Eagle | Defeat Aquamentus with nobody present above level 8. | 20 |  | achievements.c achievement_hyrule_fair_fight (guardian kill) | from now |
| `hyrule-band-2` | Fair Fight: The Moon | Defeat Dodongo with nobody present above level 14. | 24 |  | achievements.c achievement_hyrule_fair_fight (guardian kill) | from now |
| `hyrule-band-3` | Fair Fight: The Manji | Defeat Manhandla with nobody present above level 20. | 28 |  | achievements.c achievement_hyrule_fair_fight (guardian kill) | from now |
| `hyrule-band-4` | Fair Fight: The Snake | Defeat Gleeok with nobody present above level 27. | 32 |  | achievements.c achievement_hyrule_fair_fight (guardian kill) | from now |
| `hyrule-band-5` | Fair Fight: The Lizard | Defeat Digdogger with nobody present above level 33. | 36 |  | achievements.c achievement_hyrule_fair_fight (guardian kill) | from now |
| `hyrule-band-6` | Fair Fight: The Dragon | Defeat Gohma with nobody present above level 40. | 40 |  | achievements.c achievement_hyrule_fair_fight (guardian kill) | from now |
| `hyrule-band-7` | Fair Fight: The Demon | Defeat ancient Aquamentus with nobody present above level 46. | 44 |  | achievements.c achievement_hyrule_fair_fight (guardian kill) | from now |
| `hyrule-band-8` | Fair Fight: The Lion | Defeat ashen Gleeok with nobody present above level 52. | 48 |  | achievements.c achievement_hyrule_fair_fight (guardian kill) | from now |
| `hyrule-band-9` | Fair Fight: Death Mountain | Defeat Ganon with nobody present above level 59. | 60 |  | achievements.c achievement_hyrule_fair_fight (guardian kill) | from now |
| `hyrule-tools` | Tools of the Hero | Master all ten of Hyrule's tool and puzzle feats, the secret ones included. | 50 |  | meta: hyrule tools | from the members |
| `hyrule-all-chests` | Every Chest in Hyrule | Open the treasure chest of all nine dungeons. | 60 |  | meta: hyrule chests | from the members |
| `hyrule-all-bands` | By the Book | Win every Fair Fight in Hyrule. | 100 |  | meta: hyrule bands | from the members |
| `relic-horseman-reaper` | Grim Harvest | Acquire the Headless Horseman's Reaper. | 25 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `relic-horseman-helm` | Keep Your Head | Acquire the Horseman's cursed helm. | 20 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `relic-frostbite` | Frostbitten | Acquire Frostbite, Father Winter's blade. | 25 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `relic-winter-mantle` | Wrapped for Winter | Acquire the Winter Veil mantle. | 20 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `relic-pumpkin-charm` | Jack of the Lantern | Acquire a pumpkin-lantern charm. | 10 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `relic-snowflake-pendant` | No Two Alike | Acquire a snowflake pendant. | 10 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `relic-clover-small` | Luck of the Draw | Acquire the smaller lucky clover. | 15 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `relic-clover-large` | Four Leaves | Acquire the larger lucky clover. | 20 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `relic-moonray` | Moonstruck | Acquire the moonray sword. | 30 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `relic-celestial-dagger` | Fallen Star | Acquire the celestial dagger. | 30 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `relic-flamberge` | A Wavy Edge | Acquire the Flamberge from the Castellan of Valhalla. | 30 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `crystalline-sceptre` | The Sceptre of Commanding | Acquire the Crystalline Sceptre of Commanding. | 20 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `crystalline-sword` | The Sword of Justice | Acquire the Crystalline Sword of Justice. | 20 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `crystalline-robe` | The Robe of Shielding | Acquire the Crystalline Robe of Shielding. | 20 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `crystalline-cloak` | The Royal Cloak | Acquire the Crystalline Royal Cloak. | 20 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `crystalline-crown` | The Crown of Perception | Acquire the Crystalline Crown of Perception. | 20 |  | handler.c obj_to_char -> achievement_check_state (held) | held now |
| `crystalline-set` | Crown Jewels of Glitter | Acquire all five crystalline pieces Prince Starfire wears. | 50 |  | meta: crystalline | from the members |
| `stash-deposit` | Put It Somewhere Safe | Put something in your stash. | 5 |  | act_obj.c do_stash put | from now |
| `stash-withdraw` | Right Where I Left It | Take something back out of your stash. | 5 |  | act_obj.c do_stash get | from now |
| `stash-expand` | More Shelf Space | Buy more room in your stash. | 10 |  | act_obj.c do_stash buy; REDEEM STASH | from now |
| `stash-ceiling` | A Warehouse of One's Own | Grow your stash to its full five hundred slots. | 40 |  | pcdata->stash_max (saved) | from the save |
| `repairs-1` | Good as New I | Pay to have a damaged item repaired. | 5 |  | act_obj.c repair_mend (paid) | starts at 0 |
| `repairs-25` | Good as New II | Pay to have 25 damaged items repaired. | 15 |  | act_obj.c repair_mend (paid) | starts at 0 |
| `repairs-100` | Good as New III | Pay to have 100 damaged items repaired. | 30 |  | act_obj.c repair_mend (paid) | starts at 0 |
| `wings-of-mercy` | Wings of Mercy | Be found, badly hurt, by Herbie the angel and healed. | 15 | yes | special.c spec_paramedic (natural visit only) | from now |
| `disaster-flood` | High Water | Live through a flood to its end. | 10 |  | disaster.c disaster_end (struck, alive, no death since) | from now |
| `disaster-lightning` | Lightning Rod | Live through a lightning storm to its end. | 10 |  | disaster.c disaster_end (struck, alive, no death since) | from now |
| `disaster-earthquake` | All Shook Up | Live through an earthquake to its end. | 10 |  | disaster.c disaster_end (struck, alive, no death since) | from now |
| `disaster-tornado` | Not in Kansas Anymore | Live through a tornado to its end. | 10 |  | disaster.c disaster_end (struck, alive, no death since) | from now |
| `disaster-sandstorm` | Sand in Everything | Live through a sandstorm to its end. | 10 |  | disaster.c disaster_end (struck, alive, no death since) | from now |
| `disaster-fire` | Through the Fire | Live through a wildfire. | 10 |  | disaster.c disaster_end (struck, alive, no death since) | from now |
| `disaster-tidal` | Riding the Wave | Live through a tidal wave. | 10 |  | disaster.c disaster_end (struck, alive, no death since) | from now |
| `disaster-all` | Act of the Gods | Live through every kind of disaster but the dragon. | 50 |  | meta: disasters | from the members |
| `rare-sightings` | Rare Sightings | Earn Follow the Money I, Dragon Trouble I and Under the Counter I. | 30 |  | meta: rare sightings | from the members |

### Deferred candidates

- **The Witch King (9901)** has a `#SHOPS` row, so he is a shopkeeper:
  `is_safe` and `is_protected_npc` refuse every attack.
- **Khamul (9905)** is one of six identical castle-gate Nazgul (9905-9910)
  with no gear; nothing makes him one encounter.
- **The Castellan (9913)** is Valhalla's butler, alignment 1000, who casts
  helpful spells; his Flamberge is a relic achievement instead.
- **Zoltan (9919)** is ACT_PET in a safe room and cannot be attacked.
- **Overlord Hatchet's manifestation (3815)** is a level 60 tribute NPC with
  1,260 hit points sitting in a level 2-10 area.
- **The Crystalline Diadem and Dagger** are carried by Princess Semele, not
  Prince Starfire; the set meta is the five pieces he wears.
- **Disaster deaths** do not exist: disasters never kill.
- **A heal or cure on oneself** is not teamwork and does not count.

## Existing Characters

The first login after upgrading checks facts already present in an old player
file. Existing characters can immediately receive level, remort, play-time,
qualifying player-kill, current quest-streak, bank-balance, carried-money,
casino-total, and currently owned collection or Hyrule-item achievements. Their
current Hyrule room can also record a matching discovery.

Old player files did not retain lifetime mobile-kill or completed-quest totals.
They also did not retain a reliable all-cause death total. Those three counters
therefore begin when this system first records them. They are not estimated
from session snapshots or the older PK-only death field, because an estimate
could award progress a character did not earn.

Event-only economy feats are not inferred. An existing high bank balance can
award its balance milestones, but first deposit, first interest, seven-day
interest, empty-account, jackpot, straight-up roulette, and royal-flush credit
must occur after the corresponding hooks are installed.

## Persistence And Compatibility

Achievement data is stored in the normal player file:

- `Achv <stable-key> <timestamp>` records each unlock by key, not table index.
- `AchKills`, `AchQuests`, and `AchDeaths` store lifetime counters introduced
  by the system.
- `AchExplore`, `AchMaps`, `AchCompass`, and `AchTriforce` store compact Hyrule
  discovery and collection masks.

Missing fields default to zero, so old player files remain valid. Stable string
keys allow catalog entries to move without changing the meaning of saved data.
Unknown retired keys are ignored safely. Achievement state follows ordinary
character save, quit, autosave, snapshot, backup, and restore behavior.

## Developer Notes

The catalog and command live in `src/achievements.c`. `PC_DATA` reserves 512
timestamp slots through `MAX_ACHIEVEMENTS`, checked at compile time by
`achievement_table_must_fit`; the current catalog uses 378. Add a new entry
only with a unique key that will never be repurposed, at the end of the
table, and never move an old row.

Achievement views use canonical `{HH}` game-color tokens and
`page_to_char()`. The pager converts those tokens to the recipient's ANSI
sequences, or removes them when color is disabled, before retaining the text
between pages. Do not bypass that path with raw `write_to_buffer()` calls.

Event hooks are intentionally central:

- `fight.c` records NPC deaths, true player deaths, named bosses, and qualifying
  player-kill milestones.
- `quest.c` records successful quest completions after streak advancement,
  plus rush, final-minute, gamble-win, and keepsake-related progress.
- `handler.c` records room entry, item acquisition, and lethal action items.
- `magic2.c` records crafting, Farslay outcomes, and death rays; `act_obj.c` and
  `update.c` distinguish puzzle traps and flagged death-trap rooms.
- `act_obj.c` records bank transactions, carried-value state, casino totals,
  slots jackpots, roulette straight wins, and poker royal flushes; `update.c`
  records daily and seven-day interest payouts.
- `update.c`, `act_info.c`, `comm.c`, and `save.c` evaluate state milestones at
  level-up, remort, login, score display, and save.

`achievement_check_state()` is idempotent. Event-only room, boss, crafting, and
death-cause criteria unlock only from their event hook; state criteria can be
checked repeatedly.
The save writer serializes earned entries by key. The loader resolves each key
back to the current runtime index.

Run the normal native build, CMake build, area validation, and
`scripts/test-parallel.sh test_achievements test_achievement_expansion
test_money_safety test_bank_interest` after changing the catalog, economy,
or hooks. `test_achievement_expansion` holds the counts, the frozen
cohorts, a hook for every new event and counter, this page's catalog
against the source, and plays an old save, REDEEM, paging, a remort, the
stash, a Fair Fight and a WIMPY boss live.
These tests verify key uniqueness, catalog capacity, persistence wiring,
currency transaction safety, the generated Hyrule boss-to-room contract,
compact summary layout, and paged color conversion.

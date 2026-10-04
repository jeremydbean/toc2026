# Changelog — Times of Chaos (ToC)

All notable changes to this project are documented in this file.

Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Fixed

- **Ganon no longer collapses to one hit point from a punch.** Hit points,
  mana and moves were `sh_int`, so Ganon's 36,000 wrapped negative when he
  spawned and the first blow counted as fatal. The ashen Gleeok and the
  Undead Cleric (up to 45,000) were broken the same way. The fields are
  `int` now, and the area loader stopped clamping a mobile's hit dice at
  32,767. `tests/test_big_hit_points.py`.
- **Hyrule uses regular money.** Shops, the money caves, the door-repair
  charge, the gambling game, the hint caves, arrows and every line of
  prose say gold instead of rupees. A rupee was a gold coin underneath all
  along, so no price or reward changed: the Blue Ring is 250 gold, a door
  repair 20, a moblin's gift 10, 30 or 100.
- **Several commands on one typed line, in any client.** "n;kill orc"
  from Mudlet or plain telnet used to answer "Huh?"; only the browser split
  on semicolons. The server splits now, on the browser's rules (quotes and
  \; keep a semicolon), runs them one at a time with lag between, and
  never splits a line that sets an alias or carries a password.
- **A quest is told to the one who asked for it.** The questmaster SAID
  every assignment -- target and where to find it -- so everyone in the
  room heard another player's quest and went after it. Alaric: "the mud
  just forces the quest on the whole room". It is a tell now.
- **Cross-class spells can be taught.** ARCANE STUDIES, from Dawn the
  Wand Maker in any guild, holds earthquake, plague, harm, major globe and
  vortex -- spells the class sheet gives mages, thieves and warriors a
  level for that no group of theirs held. Spells HELP keeps to one class
  stay that class's. Despair is taught by Rakar the weaponsmaster; phase
  is deliberately not taught.
- **Major globe will not form over armor, shield or stone skin**, as HELP
  always said; it refused only shroud, so cast last it stacked.
- **Earth travel and gate keep the room rules walking keeps**: another
  class's guild rooms, rooms behind a guild guard, Hyrule's order.
- **WALKTO** routes around Hyrule dungeons you have not earned instead of
  stopping at the door, and uses the 500-gold Hall of Heroes windows when
  you can pay and nothing free goes there.
- **Rope trick and haven take a ridden mount along**; the rider used to go
  alone, still flagged as riding. A maze turned back on an already-mazed
  caster fizzles instead of stacking.
- **A remort keeps on what the new life can wear** and stashes the rest --
  now including gear made for the old race, which stayed worn.
- **Unspent practices and trains survive a remort.** The new life's
  starting amounts are added to them instead of replacing them; HELP
  REMORT says so, and that handed-back psionics return at 1%.
- **A flaming or frost aura no longer burns its own wearer.** Poison,
  plague and drowning are damage a character deals themselves, and the
  aura reflected 60% of each tick back at them -- every tick hit twice.
- **Remort and psionics, triple-checked.** Loading an offline character
  -- GRANTPSI, UNDENY, or a player's STASH LINK -- ran the psionic login
  top-up, which wrote to a blank connection and could crash the server;
  it also announced a character's powers to whoever typed their name at
  the login prompt. It runs on entering the game now. A guildless
  character's remort read past the end of the class table into the log.
  Offline loads drove an area's player count below zero, so Hyrule could
  reset and reseal its walls around players inside. A remort now ends in
  the Temple (it could be taken inside a no-recall dungeon) and is
  refused in jail; charmed followers other than a pet or mount are
  released. GRANTPSI says when it added nothing, and a pending GRANTPSI
  list is no longer spent by the login top-up.
- **Trainers, checked for every class and guild.** Dawn the Wand Maker
  teaches scribe to anyone who can reach it (clerics at 25 had nobody);
  HELP MALADICTIONS names Grill for ?/C instead of "<TBD>". HELP PHASE and
  HELP DESPAIR say what they do: phase can stealth you as you fall asleep,
  and despair can turn your FLEE into your opponent's. Two fighters who
  both held despair could bounce FLEE back and forth inside each other;
  an answer to despair no longer answers back.
- **Every multi-hit spell, trap and flood stopped at its first blow.**
  `damage()` says whether a blow landed, and a 2025 pass read it as "the
  victim died" at more than twenty places. So: one magic missile, one
  skeletal hand and one tentacle per target; chain lightning that never
  chained; heat metal on one item; dirt kicking that never blinded;
  stunning blow, stun traps and earthquakes that never stunned (and a
  landed stunning blow, blinding fists or fists of fury that cost no
  lag); dart traps with one dart and no poison; floods that carried you
  one room; enervate that never healed; the geyser knocking you down only
  when it missed; a cauldron explosion that never used up its
  ingredients; and a poisoned or drowning character skipping the rest of
  their tick. `gone_after_blow()` is the test now, and
  `tests/test_damage_result.py` fails on any branch on `damage()`'s
  result.
- **Followers of someone who quit kept following a freed character.**
  `die_follower()` had been an empty stub since November 2025; the next
  character allocated from the pool inherited them. It is stock ROM's
  again, and raised undead crumble when their necromancer quits, refuses
  followers or remorts rather than stand about as a free mobile.
- **Necromancer exploits closed.** MURDER on your own vampire broke its
  charm with the first blow and paid full experience; raised undead now
  pay none to anyone, and MURDER refuses NOKILL mobiles as KILL does. A
  raise dead that left belongings in the corpse could be cast again and
  again to pull its owner anywhere; the leftovers now fall to the floor
  and the corpse is used up. Rope trick and haven kept their origin in
  the idle void's return pointer and never cleared it.
- **Two necromancer spells had no trainer.** Cause serious (level 18)
  sat in no necromancer group, and GAIN sells spells only inside a group;
  it is in NECRO MALADICTIONS now, so everyone who already holds that
  group has it from their next login. Scribe (level 30) was taught only by
  the mages' trainer; the Undead Spirit, who teaches scrolls, teaches it
  too. `tests/test_necro_trainers.py` fails if a necromancer skill is ever
  left without one again. Despair and phase are untaught for every class.
- **No remort, and no levelling, past your cap.** A character staff
  advanced beyond 54 plus their remorts went on gaining levels toward 60
  and was told to "advance till" a level below their own. Experience now
  stops at the cap however far past it they are, remort refuses them
  with an honest reason (owner: remort does not work past the point you
  could level to), and an immortal can never remort.
- **The backup alarm cried wolf, to everyone.** The state-sync check
  read a sync that was still running as "last success 99999 minutes ago"
  -- a deploy restarts the 5- and 15-minute timers together, so they meet
  every quarter hour -- and announced it to the whole game. It waits for
  a running sync now, and a real failure goes to staff on WIZINFO.
- **Remort psionics, end to end.** Every power starts at 1% and is
  trained with Salir, one handed back from an earlier life included. (The
  first cut restored them at 75% -- and did it at every login, so a power
  granted at 1% read 75% after a relog; that is gone.) A character
  with two or more remorts who holds fewer powers than the remorts give
  (Bongaboy: three remorts, none) is topped up at login. The big awakening
  message shows only when something new is given; powers handed back are
  named one by one.
- **A rotting corpse in someone's hands kept nothing.** Its contents went
  to the carrier and were then destroyed in the same pass, because the
  three destinations were not chained with else (stock ROM's are).
- **More of what a watched player does is logged:** buying and selling
  (item, vnum, price, shopkeeper), giving an item (both sides), the
  stash (in, out, and across linked characters), a finished quest's
  reward, and a remort's old and new class, race and guild. TAKE from a
  linked character's stash ignores carry limits, as withdraw does.
- **A staff GRANTPSI pays on the next level gained, at any level.** It used to
  wait on the 18-21 band's one-in-four rolls (Alaric missed three). The
  player is no longer told a grant was made; the awakening itself is the
  original framed message again, naming Salir and WALKTO SALIR. Powers
  restored at login are announced one by one.
- **Colour tokens that printed.** A token is `{` and two hex digits; the
  Ganon collapse lines, the Silver Arrow shot, the heat spell and the
  psionic messages wrote `{0C}`, `{x}` and `{R`, which showed as stray
  braces and letters.
- **COMPARE judges gear you cannot wear yet.** The verdict says which is
  better either way, then why you cannot use it yet.
- **Hermie stands at the pit for six hours after every boot.**
- **Necromancer review.** Fixed: major globe stacked without limit (it
  tested the skill number as affect bits); the undead-servant cap vanished
  once the necro joined a group, and a servant could be killed for its
  experience; RECITE had no lag; trap the soul could bottle the training
  dummy, a quest master or a shopkeeper, and Farslay could kill them
  anywhere; raising or butchering a corpse destroyed the loot inside;
  recasting a short buff kept a servant alive for ever; rope trick and
  haven were a way out of jail and no-recall dungeons; raise dead ignored
  summoning rules; vampiric touch and energy drain healed off the undead;
  an iron skin sweep stripped innate immunities whenever any affect ended;
  creation allowed necromancer and monk races that remort refused; the
  Halloween undead template could be killed; help for DEATH SHROUD and
  CREATE SKELETON.
- **What you take back from your own corpse no longer rots.** A corpse put
  a decay timer on every potion and scroll in it (and scuba gear), and the
  timer stayed when you took them back -- the owner's Scroll of Farslay
  crumbled two days after a death. Only a mobile's corpse stamps them now,
  and the stamp comes off a player's potions and scrolls at login.
- **Mudlet 1.5.4: routes load by default.** The last route list downloaded
  is read from disk as the package starts, a fresh one is fetched two
  seconds later (and again on reconnect if there is none), a failed
  download retries, and a WALK typed before the list arrives sets off when
  it does. WALK also finds trainers and guild halls once the list carries
  them.
- **A copy of the character before anything big happens.** Before a remort,
  a death, a staff ADVANCE or SET, a GRANTPSI, a COMBINE, a deletion or a
  login repair, the character is saved and copied to
  `player/versions/<Name>/<Name>.<timestamp>.<reason>`. PRESTORE lists those
  with "before remort" and the like, and the 30-copy rotation never prunes
  them; the newest 20 of each reason are kept.
- **Remort, from a full review.** Wimpy is cut to a fifth of the new hit
  points (a 54's 800 against 200 fled every blow). The stash hands back the
  outgrown-gear pack however heavy (owner) -- a level 3 could never lift a
  level 54 kit, so it stayed there. NODROP and timed items stay carried
  instead of going in the pack (a pack can be TAKEn by a linked alt). A
  remorted character's hunger and thirst stay gone through fountains and
  RESTORE. Powers from an awakening or a grant come back on the first
  remort, and at login for anyone remorted before. Hero's grip is granted
  at once; a recall point a new level 3 may not enter is set aside; the
  login repair also catches maxima below 200 per remort; OUTFIT floors
  recall even when it hands out nothing; the character is saved before the
  backup. HELP REMORT says all of it.
- **Every player is watched by default while the changes settle.** LOG ALL
  is on from boot, and it now means the full watch log for everyone --
  commands with the room, every move, coin change, level and death -- not
  bare commands. A tell is recorded by name only unless the character was
  flagged with LOG <name>, because log/ is published. LOG ALL turns it off;
  turning it either way is logged. Level lines say "earned" or "staff
  advance"; an ordinary level read "(restore)", which looked like staff
  intervention on a watched character.
- **Remorting under a big spell no longer wrecks the character.** Alaric
  remorted while empowered and titanic and came out at -5515 hit points,
  -6945 mana and -1385 moves: the remort reset the maxima and only then
  stripped the spells, and stripping a spell takes its bonus back off the
  maxima. The spells now come off with the gear, before the reset. The
  login that follows a remort rebuilds the permanent stats from the maxima,
  which wrote the wreck in for good; it now never derives a non-positive
  maximum, keeps a sane stored one, and fills a rebuilt pool. A remort also
  ends dressed -- OUTFIT fills the empty light, body, shield and weapon
  slots, as for a new character. The level 54 note says "max level".
- **Nothing a player owns is shop stock.** The Hyrule fix covered buying;
  the same flag sat on the Azeroth dwarf's Vial of Immortal's Blood and on
  the free red potions in Hyrule's take-any caves, which were lost on death
  once picked up. The flag now comes off whatever reaches a player, by any
  route, and a bought item no longer rots when its owner dies (the prison
  weaponmaster's short sword did).
- **Things bought in Hyrule survive their owner's death.** Hyrule's shop
  items carry the shop-stock flag on the item itself, every copy sold kept
  it, and a corpse destroys shop stock -- so dying lost everything a player
  had bought there, the 250-rupee Blue Ring included. A bought copy is the
  player's now, and the flag comes off anything a player already carries
  at login. A Blue Ring of Hyrule bought when it was level 24 is raised to
  45 with the ward it gained.
- **Hyrule's text caught up.** Ganon's description no longer has the
  Master Sword at his hip (it is in the great chest behind him); the Mirror
  Shield and Pegasus Boots no longer answer to "ganon", like the Tunic and
  Red Ring; the grave's Magical Sword is no longer "the finest blade anyone
  may carry"; help and the guides name the Blue Ring's ward with the
  others and list everything Ganon's corpse holds.
- **A retired item is swapped for its replacement at login, not dropped.**
  The Hyrule NES pass took the shops' satchel of bombs (30542) out of the
  world, and Alaric's four were dropped the next time he logged in, with a
  "bad vnum" line each. `retired_objects` in `src/save.c` maps a retired
  vnum to what replaced it -- the satchel to four bombs, Ganon's old Blue
  Ring to the Blue Ring of Hyrule -- and the swapped item takes the
  replacement's own stats. Add a row whenever an item players can hold is
  removed. `tests/test_retired_objects.py`.
- **The report backlog is archived, and stays archived.** Every bug and
  typo report on file has been worked through, so the old hosts' files
  are kept as `area/bugs.txt.20260929-151146` and
  `area/typos.txt.20260929-151146` and the live copies are gone. The
  state sync now backs up what REPORTS CLEAR sets aside -- those
  archives used to live on the host alone -- and drops a cleared report
  file from git, where it had sat for ever and a restore would have put
  the cleared reports back.
- **The typo archive, second pass.** The first pass fixed every report
  where the player named the place; the same misspellings were still
  elsewhere in the world: "desperatly", "brige", "jewlery", "what use to
  be" (eight rooms of ruined Midgaard and beyond), "shiney" (and a shiny
  sword that only answered to "sword"), "it's known uses", "a bleeding
  heart fly's up", "the moss ... give off" and "comes to life and
  ATTACK!". `tests/test_reported_typos.py` now holds every reported slip
  and fails if one comes back.
- **The old bug reports, second pass.** Every report in the archive the
  first pass did not fix was checked against today's code; most were
  fixed long since. These were still live (`tests/test_old_bug_reports.py`):
  - TELL or REPLY to a Mud School monster could crash the game: their race
    sets the bit PLR_AFK shares, and the AFK branch read the mobile's
    player data, which it has none of.
  - A curse or sleep cast on a player already fighting something flagged
    nobody, so their first blow back made *them* WANTED. The caster
    answers for it now, from a wand or a spell alike.
  - FLEE and wimpy never chose southeast or southwest -- a room whose only
    ways out were those said PANIC every time. Flee gets eight tries now,
    keeping its old odds.
  - Moving up or down announced "has arrived from the down"; it says
    "from below" and "from above", for runners, riders, the shoved and
    arrows too.
  - The mahogany door in the chess house locked only on the inside, so
    the vase's silver key was never needed; it locks from both sides.
  - The Halloween elite vampire guards were neutral; they are evil.
  - HELP GET explains `get 2.potion bag`; "some dark metal bracers"; the
    hunter's "Ye shall DIE!" closes its quote; despair's grammar.
- **Heroes are never too full to eat.** Hunger stands still from level 51,
  and stood still wherever it was: a hero who levelled sated, or was
  RESTOREd (which sets it to 100), could never eat food, a pill or a
  training cake again. Hunger and thirst now sit at a middling value for a
  hero, and EAT never refuses one for fullness. (Alaric's report.)
- **No "No help on that word" at login.** Heroes were shown the immortal
  MOTD, whose topics are all staff-only; it is for immortals by trust now.
  And every login printed the MOTD command's own help ("Syntax: motd")
  instead of the message of the day, because that entry loaded first and
  hid the real one; the MOTD and IMOTD command entries are gone, and the
  real IMOTD is level 60 so every immortal sees it. (Alaric's report.)
- **One Blue Ring of Hyrule, and it stacks with the Red.** The ring shop's
  Blue Ring is the Blue Ring of Hyrule, level 45, taking a tenth off every
  blow; Ganon no longer rolls a second one. Worn together the Red and Blue
  wards stack to 28 percent, and only one of each may be worn.
- **Ganon is a hard fight, not an execution.** With his hit points finally
  holding, his fireballs (1,400-1,900, two every four seconds, no parry)
  out-damaged a level 59's whole health in one pulse through sanctuary,
  and a level 70 was shown UNSPEAKABLE on every blow. They are 300-420 now
  and his blow averages 200 instead of 350; a lone 59 still loses, a
  group of three wins.
- **Gear that grants a spell shows it.** AFFECTS and the Mudlet buffs pane
  list the Red Ring's sanctuary and the Master Sword's haste -- any spell
  worn gear gives -- with the item giving it, for as long as it is worn.
- **No Hyrule reward is barred by alignment.** The Master Sword was
  anti-evil; nothing a Hyrule boss drops is now.
- **"The final Triforce piece"** is the ninth piece's name, in place of
  the Triforce of Power. The Red Ring of Hyrule and the Hero's Tunic no
  longer answer to "ganon", and the old plain red ring nobody placed or
  held is gone, so VNUM RED RING shows one.
- **Mudlet 1.5.3: HP, mana, endurance and EXP are back across the top.**
  1.5.2 took the first three away on a misreading -- the owner wanted
  vitals kept out of the sidebar, not off the screen. They are one row on
  top again, as they were, with moves labelled END as the game calls them.
- **Death traps are off the Mudlet starter map.** You find one yourself;
  the mapper learns it from GMCP when you walk in, and no exit on the
  shipped map leads to one.

### Changed

- **Hyrule's NES pass: people of their own, maps that help, the caves'
  rules, and items that do things.** The plan is "The NES Pass: Plan" in
  `wiki/hyrule-area.md`; the new code is `src/hyrule.c`.
  - **Every room, enemy and person is written on its own.** Duplicate room
    names and the caves' shared text are gone: each of the 60-odd caves,
    shops and halls has its own entry. Every enemy kind has its own text in
    each band (127 entries), and the old men, old women, merchants, potion
    sellers, door-repair men, gamblers, moblins, fairies and Zelda are 78
    records of their own instead of seven shared ones; an old man says his
    NES hint. Hints now stand in the rooms the sources give (Level 2's old
    man added; Levels 6, 7, 8 and 9 corrected).
  - **Maps and compasses tell you something.** LOOK or READ a dungeon map
    for its floor plan, with you, the guardian's chamber, the locked
    Triforce chest and what the guardian's door needs; a compass names the
    first step of the shortest path to the chest and how many rooms away
    it and the guardian are. All nine sets were checked against the NES.
  - **Boss drop tables.** Every guardian drops two of five armour pieces at
    random, each a little better than the best piece a character of its
    band can find anywhere else, measured with the Gear Finder.
  - **The caves follow the NES and cannot be farmed.** Money caves pay once
    per character as you walk in (a new saved field, `HyruleSecrets`); the
    money-making game is the NES's, with nothing to gain on average and no
    casino credit; four plain heart caves are the NES's "take any one you
    want"; the White Sword wants 5 hearts and the graveyard's Magical Sword
    (new, level 38) 12, counted the NES way (HEARTS); two old women sell
    hints for rupees (GIVE) and two old men give theirs; the Level 5 and 7
    old men sell bigger bomb bags.
  - **Hidden ways open only to their tool.** Bomb walls, bushes, Armos,
    blocks and the lake were plain closed doors anyone could OPEN; they are
    secret now until the NES's act opens them, and OPEN, PICK, DOORBASH and
    UNLOCK refuse with a hint. Shutters stay shut while enemies remain. A
    bomb is used up by every blast; the Recorder must be the Recorder.
    `tools/build_directions.py` writes these as the act and its need.
  - **Every item does something.** Bombs are bought four at a time and
    thrown at walls or enemies; the bow SHOOTs with a quiver at a rupee a
    shot, killing pols voices outright; boomerangs stun; candles burn
    enemies; bait calms a room; the Recorder shrinks Digdogger and calls the
    whirlwind; the Rod never runs dry and burns with the Book; the red
    potion turns blue; shop keys keep through a quit; the shop Blue Ring and
    Magical Shield carry wards; fountain fairies restore you; the tenth
    enemy in a row without a wound leaves a bomb.
  - The Silver Arrow was checked against the NES and is already where it
    belongs: Level 9's item cellar under the far-west wizzrobe room.
  - The item COMBINE TRIFORCE makes is named just "The Triforce" everywhere
    it is shown: its short description, COMBINE's messages, its achievement,
    HELP and the pieces' lore. Same vnum, same powers.

- **Hyrule's dungeons are done in order, and every guardian keeps a key.**
  - Each guardian drops its dungeon's key. The key opens the magical door
    into the room behind the guardian and the locked chest in it; the chest
    holds the dungeon's Triforce piece and its treasure. Ganon's Golden Key
    opens Zelda's chamber and his great chest, which holds the ninth piece,
    the Triforce of Power, and the Master Sword -- no longer in his corpse.
  - Entering a dungeon needs the previous dungeon's piece, and reaching its
    guardian needs the previous dungeon's treasure: boomerang, Magical
    Boomerang, raft, stepladder, bow, Recorder, Red Candle, Magical Key. The
    bow moves from Level 1 to Level 5 and the Recorder from Level 5 to Level
    6, so each arrives just before the dungeon the NES uses it in. Both gates
    are asked of the character moving (`hyrule_progress_gate` in
    `act_move.c`, by walking and by portal); staff pass by trust.
  - `COMBINE TRIFORCE` joins the nine pieces into the complete Triforce,
    which is no longer lying in Zelda's chamber. COMBINE alone still toggles
    the inventory display.
  - The Triforce pieces and the Magical Key were keys in the item tables,
    and keys are not saved when you quit; they are treasure now. Pieces
    cannot be dropped, given or sold. A guardian's key does not crumble in
    its corpse.
  - Hyrule's chests relock and refill at every area reset, players or not,
    and every container standing in a room is relocked when a reset refills
    it, as ROM 2.4 did.
  - Every guardian is resized by simulation against a player model fitted
    to the live player files, and has its NES attack: Aquamentus's fan of
    fireballs, Dodongo's charge, Manhandla's heads, Gleeok's heads,
    Digdogger's split, Gohma's eye. Patras lash with their orbiting eyes.
    Alone at the top of the band a character loses; six levels above, or
    three together, they win. Ganon's fireballs come down to 1,400-1,900
    and his hit points go up to 36,000: a group wants two Silver Arrows.
  - HELP HYRULE has the order as a table, every refusal says what is
    needed and where it comes from, and the old man's cave says it too.
  - **Every locked door in Hyrule was a trap.** The generator wrote keyed
    doors as exit type 5, which `load_resets` turns into a trapped door at
    every reset, so unlocking one with its key went off four times in five
    -- a needle, a teleport, sleep. Keyed doors are type 2 now (pickproof).
    `wiki/area-building-guide.md`'s door tables listed values the code does
    not have, and are corrected.

- **Hyrule's endgame: the Master Sword is Ganon's, Ganon needs a group,
  and the Red Ring and Triforce have their powers.**
  - The **Master Sword** (level 58) no longer lies in the B6 graveyard;
    Ganon carries it, so it lands in his corpse. At 13d9 +5/+5 it scores
    70.0 (average damage plus damroll) against 63.5 for Ganon's trident,
    the best weapon a mortal could otherwise get anywhere, and 54.0 for the
    best outside Hyrule. It hastens whoever wields it.
  - **Ganon** is level 64 with 30,000 hit points and armour -400, and
    `spec_ganon` replaces his necromancer's spells: every four seconds he
    blinks to another spot and throws two 1,600-2,200 fireballs at random
    members of the fight, which no parry stops, and out of a fight he heals
    a tenth a pulse. Simulated against a level 59 with every defence,
    sanctuary, the Red Ring and 4,000 hit points, a solo hero wins about one
    fight in twenty and a group of three or four nine in ten or better. The
    Silver Arrow rule, the relics and the achievements are unchanged.
  - The **Red Ring of Hyrule** lies in Death Mountain's Red Ring Cellar, in
    place of the catalog's plain red ring, instead of being one of Ganon's
    five random relics (four now). Worn, it gives sanctuary as well as its
    20% ward.
  - The **complete Triforce** is a light. Worn in the light slot it gives
    the sight of a level 59 character with HOLYLIGHT on -- through
    darkness, blindness, invisibility, hiding and shadowmeld, and through
    wizinvis or incognito up to 59 and no higher. `triforce_sight()` and
    `sight_trust()` in `handler.c` are asked wherever holylight grants
    sight.
  - **Worn powers use ROM 2.4 `F` records**, which `load_objects` reads
    now. Slow and dispel magic leave a worn haste or sanctuary alone, and
    IDENTIFY says "Grants haste while worn."
  - **Drops.** The first eight bosses leave a Heart Container at the top of
    their band; ordinary enemies sometimes leave rupees, a recovery heart, a
    bottled fairy or a clock-flask (a potion of haste), one of each per band.
  - **Every room, enemy and boss description** was rewritten from the NES
    game; the old men's hints are carved into their rooms. Enemy and boss
    text lives in the new `data/hyrule_mob_prose.json`. Level 1's guardian
    is plain "Aquamentus", the one-horned dragon. The B6 grave is "The
    Hero's Grave", and the Mudlet map is rebuilt for it.

- **COMPARE, rebuilt: which gear makes you hit harder.** The old command
  blended five indexes (damage, spells, survival, leveling, utility) under
  a weighted "profile" and printed twenty-odd lines; it is now two numbers.
  Damage -- weapon damage per round walked through `multi_hit` and
  `one_hit`, or for a caster the mana there is to cast with, since every
  spell is cast at the caster's level and gear only changes how many casts
  there are -- and toughness, effective hp against an equal-level foe,
  counted a quarter as much. The output is the two items, a three-row
  table, every number that moves on the score sheet, and a one-line
  verdict.
  - `compare <item>` measures against the weaker of a pair (it used to take
    whichever ring was on the left) and against an empty slot rather than
    refusing.
  - `compare upgrades [slot]` is the gear finder in game: every piece a mob
    carries, wears or sells, through the same measurement against what the
    character wears, limited to what they could put on today, with where
    to get it.
  - `compare profile` says how your damage is made: swings, hit chance,
    damage a hit, mana and casts.
  - An item goes only to the slot WEAR puts it in (a held light is a light),
    race flags name everyone an item suits, as `wear` reads them (a kraken
    shell flagged for three races was refused to all three), and a saurian's tail swing
    counts.
- **The website Gear Finder** applies the same rules: one slot per item,
  level -1 gear at the level its carrier gives it (518 obtainable pieces
  were scored as level -1, usable by anyone, with no dice), no rot-death or
  corpse-destroyed gear, nothing from staff rooms or Mud School past
  newbie level, and each pick names the mob that drops or sells it.
- **Aliases can run several commands.** `alias prep wear all;get all
  corpse` runs both, in order, up to ten per alias. The first runs at once
  and the rest wait at the front of the input buffer, so each pays its own
  lag exactly as typed input does, and each is logged under its own name,
  so `password`, `delete` and `remort` inside an alias still never write
  their arguments to a watched player's log. `\;` is a literal semicolon.
  Whatever is typed after the alias goes on its last command. An alias's
  commands are never expanded as aliases again, which is the whole
  recursion limit; they are not counted as input spam, and `!` repeats the
  alias rather than its last command. Defining one now refuses a name with
  a space in it (it would have loaded back as a different alias) and drops
  any tilde, which would have cut the player file short.
- **Portal and astral walk may leave a no-recall room but never enter one;
  jail stops both.** Portal already worked that way. Astral walk refused
  its own starting room too, so a psionic in a no-recall room could not
  walk out though a mage beside them could open a portal. Gate, summon,
  teleport, shift, earth travel and word of recall are unchanged. One
  HELP ASTRAL WALK gave the syntax as `astral walk <target>`, which takes
  "walk" for the target and always fails; it is `astral <target>`.

### Fixed

- **Mudlet 1.5.2: one failing part no longer hides the whole interface.**
  The owner saw only the top bars and Mudlet's own map: `buildUI` stopped
  at the first part that failed, and `install()` registered the GMCP
  handlers after it, so the sidebar, chat, tabs and exits were never drawn
  or fed. Each part is built on its own now, a failure is printed in red
  with its error, and the handlers are registered whatever happened. The
  HP, mana and move bars are gone, at the owner's request -- the prompt
  shows them; the EXP bar and the lag bar stay.
- **Stealth and shadowmeld are invisible without holylight.** No roll on
  each look, so nothing blinks in and out; only holylight and the worn
  Triforce see either. A stealthed mobile that is fighting shows itself.

- **Repairs cost a few kills, not a few hundred.** Reported in game: a
  level 46 shield broken past use quoted 265 platinum, which is about 377
  kills at that level, for one piece. REPAIR charged (100 - condition) x
  level x 5 gold, blind to how coin is earned. It now charges four kills'
  worth of the coin an equal-level mob carries (the expected value of
  `load_mobiles`' roll) for a full repair, in proportion to the damage, so
  the same shield costs about three platinum. Paid through the copper
  helpers. HELP REPAIR no longer says items break after two dozen repairs;
  nothing has broken that way for a while.
- **"isarm".** Reported in game: HEROIC GRIP's message, and the
  won't-budge message for a cursed weapon, printed "isarm". A C hex escape
  takes every hex digit after it, so the colour code `\x0C` swallowed the
  "d" of "disarm" into one byte. `tests/test_hex_escapes.py` now fails on
  any escape that runs into a hex letter, in every source file.

- **COMPARE UPGRADES and the website's Gear Finder count chest loot.** The
  Master Sword now waits in Ganon's great chest, and both only counted gear
  a mobile carries. A chest counts where it stands in a room (the website
  also requires the room to be reachable on foot) and any key a locked one
  needs can itself be had. When the piece you wear is cursed, COMPARE
  UPGRADES now says it will not come off instead of claiming nothing in
  the world is better.

- **A failed reopen of the spare file handle could crash the next save.**
  `fpReserve` is closed before every file write and reopened after; if a
  reopen ever failed it stayed NULL, and the next `fclose(NULL)` crashed,
  and a path that returned between the close and the reopen left a closed
  handle to be closed again. All eighteen closes go through
  `reserve_release()`, which closes only an open handle and clears it.
  Found by GCC's `-fanalyzer`, which also found COMPARE reading
  `skill_table[-1]` on one path; fixed.
- **Staff 4513, which always works, failed one brandish in a hundred**:
  the same `>= chance` roll as shadowmeld's.
- `tests/test_fread_key_cases.py` checks that every one of the 226 keys
  in `fread_char`, `fread_pet` and `fread_obj` is read in its own letter's
  case -- the mistake that once hung logins. All pass today.
- **Infravision can be learned outside the mage guild.** It sat only in
  "enhancement" and "guild enhancement", both sold by mage-guild trainers,
  and "necro enhancement", so a mage in any other guild -- and a cleric,
  thief or warrior outside the mage guild -- reached the spell's level
  with nobody to sell it. A one-spell group, NIGHT VISION (1 train for
  mages and clerics, 2 for thieves and warriors), is sold and practised by
  the four class guildmasters in Dresden, who take any guild. Which
  classes have the spell, and when, is unchanged. The other class spells
  locked behind a guild were left alone: that is the guild system's
  design, not the same one-line gap.
- **A title you set survives a level-up.** `advance_level` put the class
  title back every level. A chosen title is now remembered (`TitleSet`,
  read under case 'T'), kept through levels and remorts, and `title
  default` returns to the class title; `title` alone shows which you have.
  Old player files load as automatic, as they behaved before. Jail and
  hero-quest titles stay replaceable by the next level, as they were.
- **The elixir vendor is back in Elemental Canyon.** Mob 9238 kept his
  shop but lost his reset in April, which also handed his anti-cyclops
  elixirs to a mountain climber. He stands in the Mountainside Tombs
  (9203) again, where the original reset put him, the last stop before
  the cyclops, with the elixir as his stock; the climber keeps his.
- **Quest Zone room 20306 is a jail room again,** like the other nine
  riddle rooms (`BDKN`). The zone itself still has no entrance.
- Two format-truncation warnings in STASH's listing: the "Shared with"
  line is appended in pieces rather than through a 512-byte line buffer
  that could cut it, and the upgrade price buffer is sized to what
  `format_price` writes.

- **Five signature relics have their powers back.** The winged boots and
  the black feathered wings fly again, the robe of invisibility is worn
  about the body and turns you invisible, and Eversight and Virtual Vision
  grant detect invisible. A change on 2026-08-28 "repaired" their flag
  lines by reading them through the dashboard parser, which had extra2 and
  the wear flags the wrong way round -- so it turned correct lines into
  broken ones, and wrote a test that pinned the broken reading. The
  original lines are restored, and the test passes against the corrected
  parser unchanged. Eversight is halfling-only, as it always was.
- **The dashboard had elf-only and halfling-only the wrong way round**
  (`ITEM2_ELF_ONLY` is B and `ITEM2_HALFLING_ONLY` is D in `merc.h`), so the
  Gear Finder offered elves the halflings' gear and the reverse.
- **A shadowmeld skill of 100 failed one time in a hundred.**
  `number_percent()` runs 1 to 100, and the miss was `>= chance`.
- **CI no longer stops at the first failed check.** `scripts/validate.sh`
  runs every check after the build and lists the failures together, each
  with the command that fixes it, also in the GitHub job summary. A stale
  Mudlet map had stopped every push for a day before any test ran. Two
  tests that failed now and then are fixed at the cause: the recall-point
  fixture was a level 40 with 20 hit points, killed by whatever wandered
  through the Oak Tree Square; and the psionics help test failed on a line
  break inside the phrase it looked for.

- **Typo reports from the archive, worked through.** Every line ever
  filed to `area/typos.txt` was checked against the current world, and
  the 33 reports whose slip was still there are fixed across 18 area
  files and 5 source files (Mob Factory, A Shrine to a Forgotten God,
  "The Gods appreciate", "You're in too much pain", race arrival lines
  that read "The beautiful a toy soldier", and the like).
- **Old player bug reports, triaged against today's code.** Each was
  checked; these were still live. `tests/test_old_bug_reports.py`.
  - OPEN, CLOSE, LOCK, UNLOCK, PICK, DOORBASH and SEARCH take a
    direction after the door's name. OPEN DOOR EAST read only "door"
    and opened the first door in the room, so a second door could be
    reached only as OPEN EAST or OPEN 2.DOOR.
  - TELEPORT can be cast on yourself again, which is what the spell is
    for: it is offensive against others, and offensive spells refused
    "yourself".
  - A wand, staff or scroll user is the aggressor. With a spell that did
    no damage the victim's return blow reached `check_killer` first, so
    the player who was attacked was the one flagged WANTED.
  - RUN EAST -1 ran until a wall stopped it: `is_number` accepts a sign
    and the loop counted down to zero. A non-direction no longer runs
    north, and SPEEDWALK's count cannot overflow.
  - Running past an aggressive mobile follows the rules `aggr_update`
    does: a wimpy, calmed, charmed or sleeping mobile, or one in a safe
    room, no longer attacks. Fidos and bruisers jumped runners.
  - The quest master no longer names an unbought pet in a pet shop's
    storage (the copy carries ACT_PET, not the index) or a mobile inside
    a guild hall whose guard would turn the player away.
  - A hunter beside an invisible quarry growled every second; it now
    waits between growls, and the message lost a stray quote.
  - SET SEX lifts CHANGE SEX first, and an expiring APPLY_SEX affect
    that lands out of range falls back to the true sex, so an
    immortal's fix no longer flips back when the spell wears off.
  - FLIP with no argument, or at a person, is the social. The command
    of the same name hid it.
  - A monk is not outfitted with a dagger; hand to hand gets the
    starting skill floor instead.
  - The pet shop prints prices in coin ("40g") rather than a bare number
    of gold pieces that read as copper.
  - EXITS names a closed exit by its keyword ("Closed gate").
  - BALANCE stated 1% daily interest; the bank pays 0.25%.
  - Drow mages on the mushroom tower wielded their wand, which hit as
    10d10 from its charges; they hold it now. The duergar mercenary's
    axe chops instead of pecking. Marilyn stays in the Solace bird shop.
    The Mud School storage jar can be picked up, as its room says, and
    the gate there answers to "door". Missing keywords on the newbie
    robes, the dark metal bracers and the seasonal Salir. Room text for
    Gang Land 2160, the fox hole valley (5267), the Midgaard Woods trail
    (5946) and the river under the rope (25230) matches the exits and
    objects. Help for BANK, CRAWL, JUMP, ALIAS, TITLE, OPEN and
    TELEPORT describes what the commands do.

- **The gear finder hid race-restricted gear from the race it was for.**
  Reported in game by Alaric: Starlight compared better than the blue
  war banner in game but never appeared on the website. The game reads
  an object's flag line as `type extra [extra2] wear`, with extra2
  present only when the extra flags carry `Z`; the dashboard parser
  read the fourth token as extra2, swapping the two on all 55 such
  objects. Starlight, dwarf-only and held, read as human-only and worn
  on the neck. It now tops the light slot for a level 52 dwarf
  warrior. `tests/test_area_parser_flags2.py`.

- **Mudlet 1.0.8: no more "Prompt not auto-detected" from the mapper.**
  Mudlet's own mapper assumes nothing is handling the map unless a
  script says so, and then tries to auto-detect a prompt to track
  movement itself. This package maps from GMCP `Room.Info` and never
  reads the prompt, so the warning never applied to it; setting
  `mudlet.mapper_script` is the documented way to say so.

- **Mudlet 1.0.7: the identity panel capitalises race and class.**
  Reported in game by Alaric. `Char.Status` carries them the way the
  game stores them, lower case, because GMCP is data and not
  presentation -- so the panel title-cases them on the way to the
  screen rather than the protocol changing for every client that reads
  it. A hyphen starts a word, so "half-elf" reads "Half-Elf".

### Added

- **A training yard, through the practice ring in the southwestern
  corner of Oak Tree Square.** A dummy that cannot be killed and
  cannot kill you -- its blows floor you at one hit point and stop --
  so you can measure gear instead of forming an impression of it over
  an evening. `DUMMY` opens a menu: set its level (it starts at
  yours), its shape (soft, armored, evasive, brutal) and what it hits
  you with (nine damage schools, for testing resistances and saves).
  `KILL DUMMY` to start, `DUMMY REPORT` to stop. The report gives your
  damage per second and its damage per second, hit rate, best and
  average blow, how long it would take you from full, and how long you
  would need to kill a mobile of that level.

  That last figure is measured, not invented: the dummy is always
  worth what a mobile of its level really averages, across every
  mobile in the world at that level. A benchmark nobody can check is
  the one thing a training yard must not report.

- **`GRANTPSI` stopped saying the target was offline, and told a
  level 1 they were "inside the awakening band".** Restructuring the
  immediate path dropped the first and got the second wrong -- a
  level 1 is below the band, not in it. It now names where the band
  is rather than where they are, and says on its own line when the
  flag went to a player file instead of a person. Caught by CI.

- **Immortals can quest.** `automatic_quest_target_is_suitable()`
  opened with a flat `ch->level > 59`, so anybody above the mortal cap
  was told "there are no suitable quests at the moment" -- which was
  not true, and not something the message could have explained,
  because the pool was never searched. Nothing about questing needs a
  mortal, and being unable to try the feature is a poor position to
  judge it from. No special case replaces the bar: the per-target
  ceiling, a mobile no higher than your own level, simply stops
  binding above the cap.

- **`HELP WALKTO` lists every area you can walk to**, alphabetically,
  with how many rooms out each one is -- 89 of them. It is generated by
  `tools/build_directions.py` from the same routes the website
  publishes, because a hand-kept list of 89 areas is wrong the first
  time somebody adds one, and a help file that lies about where you
  can go is worse than no list. A test asserts the generator
  reproduces it, so a hand edit fails rather than drifting. `HELP
  AREAS`, `HELP MAP` and `HELP ROUTES` point at it.

- **Mudlet 1.2.1: clicking a Hyrule room on the map now walks there.**
  It answered "Cannot find a path from 2401 to 30239 using known exits",
  and it was right: Hyrule is entered with `enter cabinet`, and a mapper
  builds its graph from directional exits alone, so those rooms sat on
  the map with nothing joining them to the world. `directions.json`
  gained a `links` array -- 131 ways through that are not compass
  directions, which the route walker has known about for years and
  never published -- and the package installs them as Mudlet special
  exits. The walker already sent whatever it was handed, so that was
  the only missing piece. The route list is now fetched quietly a few
  seconds after connecting rather than waiting for `walk routes`.

- **Mudlet 1.2.0: quest and target strips, room and item tabs,
  clickable exits, achievement notices.** The quest strip counts an
  emergency contract's five minutes down, amber at three and red at
  one. The target strip draws your opponent's condition as a bar,
  which the game otherwise says in prose. Below the map, four tabs:
  Chat, Tells (their own, so they are not lost among gossip), Here
  (who is in the room, aggressives marked) and Items. Exits are
  buttons on the bottom bar. An achievement is shown over the map for
  a few seconds when it is earned, and only the ones the game
  announces, so a login's silent catch-up awards do not arrive as a
  stack. `HELP MUDLET` describes all of it.

- **Five more GMCP feeds**, for the panels that read them:
  `Char.Quest` (objective, contract kind, countdown, streak),
  `Char.Target` (who you are fighting and their condition),
  `Room.Chars` (who and what is in the room), `Char.Items` (carried
  and worn), and `Char.Achievement`, sent at the moment one is earned.
  `Char.Items` hashes a cheap integer signature over vnums and wear
  slots rather than its own payload, because it runs off the main loop
  and an inventory is long. `Char.Achievement` is emitted inside the
  announce branch, so the dozen silent catch-up awards a login can
  hand out do not arrive as a dozen notifications. `HELP GMCP` lists
  them all.

- **`HELP ROUTES`.** The realms publish a walking route to 89 of the
  92 areas that have rooms, and until now the only way to meet them
  was to already know `walk routes` existed. The new topic says where
  to see them in Mudlet, the browser client and the dashboard, warns
  that a route is a walk and not a safe passage, and explains why
  three areas have none. `HELP MAP` now points at it under "Where can
  I go?".

- **In-game help for the whole Mudlet interface.** `HELP MUDLET` lists
  every alias and what each panel shows; a new `HELP WALK` covers
  click-to-walk, named destinations and how the walk paces itself;
  `HELP MAP` explains what the room symbols mean and says plainly that
  they are drawn inside the room boxes, so they only appear once the
  map is zoomed in far enough; and `HELP GMCP` now lists `Char.Affects`
  and `Comm.Channel` alongside the fields `Room.Info` gained. All four
  say that these are Mudlet aliases rather than game commands.

- **Mudlet 1.1.1: the chat pane printed its colour tags.** `decho`
  takes decimal `<R,G,B>` and `hecho` takes `#RRGGBB` with no
  brackets; the pane had the brackets of one and the hex of the other,
  so every tag arrived as literal text. `decho` is the right one here
  because its escape character is `<`, which the message body already
  has neutralised, where `hecho`'s is `#` and players type `#`.

- **Mudlet 1.1.0: chat pane, affects line, doors and room labels, and
  named walks.** The chat pane shows exactly what the character heard,
  because the game emits each line where it delivers it rather than
  guessing at the audience. The map draws doors and marks what a room
  is for, and the walker opens a door it already knows is shut instead
  of bumping into it. `walk routes` loads the published route list and
  `walk <name>` walks to one.

- **Mudlet 1.0.9: click-to-walk.** Click a room on the map, or type
  `walk <vnum>`, and the character walks there. Mudlet plots the route
  and hands it over; the package walks it one room at a time, sending
  each step only when GMCP confirms arrival in the room the route
  expected. That paces it to the server, respects movement lag, and
  stops the walk the moment something diverts you rather than marching
  the rest of the path into a wall. A shut door is opened and the step
  retried once. `walk stop` breaks off.

- **Emergency contracts.** About one quest request in twenty now comes
  back as an emergency: five minutes flat, and five times the base point
  reward. It is rolled ahead of the rush contract and replaces it, so a
  quest is one or the other and never pays both multipliers; the streak
  bonus still applies on top. A hidden achievement, "When It Could Not
  Wait", goes with it.

### Changed

- **CI is faster and cheaper.** Superseded runs are cancelled, so
  three commits in ten minutes no longer mean three ninety-minute runs
  and one useful answer. The tests run across the runner's cores
  through `scripts/test-parallel.sh` rather than one at a time. The C
  tree is built once with the strict warnings instead of twice, since
  the strict set is the default set plus more and neither uses
  `-Werror`. ccache and pip are cached, which is what keeps
  `validate.sh`'s deliberate `make clean` from costing a full rebuild
  -- the Makefile's `CC` had to become `?=` for that to work at all.

- **`validate.sh` could fail on its own output.** It runs
  `--check-area`, which appends to `log/toc.log` -- tracked since the
  state sync started -- and merc's banner ends in a space, so the
  `git diff --check` at the end of the same script failed on
  whitespace the script had just caused. It skips `log/` now. Nothing
  had hit it only because the unit tests were failing earlier in the
  run.

- **Says are recorded.** A say now reaches the staff journal and the
  chat window of everybody who was in the room to hear it. It is
  deliberately **not** in the shared HISTORY: those rings are handed to
  whoever asks, including somebody who was nowhere near at the time,
  and nothing remembers who was standing where. A room conversation
  replayed to the whole mud is a leak rather than a feature. The
  position gate matches the one `act()` uses, so a sleeper who was not
  shown the line does not receive it either. `HELP CHANNELS` and
  `HELP HISTORY` now say what is recorded and what is not.

- **Nobody is voided for idling in under a quarter of an hour.** The
  idle timer was three minutes, which is not long enough to answer a
  door, and players were losing sessions to it. It is fifteen minutes
  now for a level 1, plus a minute per five levels, so the rope grows
  with the character: 19 at level 20, 25 at level 50. The third
  remort's named gift still doubles the result. Both branches -- link
  dead and connected but idle -- read it from `idle_purge_ticks()`,
  which remains the only place the answer is worked out.

### Fixed

- **A promised psionic grant never arrived.** `GRANTPSI` set
  `psionic_grant_pending`, saved it as `PsiGrant`, told the immortal it
  would land on the next level check and the player that their mind
  tingled with unfamiliar potential -- and nothing ever read the flag
  back. A level 50 character carried it for days. The flag is read now,
  and a grant to somebody already past the 18-21 awakening band lands at
  once rather than waiting on a roll that cannot come round again.

- **A login re-rolled the psionic awakening.** The
  `number_range(18, 21)` roll sat open-coded at two call sites, and the
  player loader calls the same check, so a character inside the band
  could relog until it landed. The roll lives in `do_check_psi` now and
  only a gained level takes one.

- **Psionic grants are written down.** Which power, from which set,
  against which roll, and why that one rather than another -- none of it
  was recorded anywhere but the player's own skill list, so "did I miss
  the roll or did it never fire?" could not be answered. Every roll,
  hit or miss, and every power granted now logs its arithmetic.

- **`GRANTPSI` on an offline character could lose the grant and leak the
  character.** The offline branch works on a loaded copy that has to be
  saved and extracted; there is one immediate path now so no branch can
  skip it.

- **A chance of 100 missed one time in a hundred.**
  `number_percent() >= chance` in `grant_psionics`, where
  `number_percent()` returns 1..100.

- **Every step a watched player took logged "(arguments withheld)".**
  `LOG_NEVER` means "too noisy for the global log" for the ten
  directions and "never write the arguments" for `password`, `resetpwd`
  and `remort`, and one flag was being read for both -- 800-odd lines in
  one session claiming something was hidden where there was nothing to
  hide, burying the few where something was. The secrecy list is
  explicit now.

### Added

- **Channel history reaches the dashboard.** The game now appends every
  line that goes to a shared channel to `log/channels.tsv`, and the new
  admin-only Chat view reads it through `/api/channels`, filterable by
  channel and by text. The in-game HISTORY rings are still memory-only
  and still go on a reboot; this is what survives one. **Tells are not
  in that file**: they never pass through the shared register, and that
  is deliberate, because `log/` is published.

- **A questing streak keeps paying past five.** The bonus stopped dead
  at `min(streak, 5) * 10`, so the sixth quest in a row was worth
  exactly what the fifth was and a run of fifty was worth no more than a
  run of five. It now climbs in shallower steps -- +10% each to five,
  +5% to fifteen, +3% to thirty, +2% to fifty, +1% after that -- capped
  at 300%. The first tier is unchanged, so no existing streak is worth
  less than it was.

- **Forty-two more achievements**, 152 to 194. Deeper ladders for
  levels, remorts, playtime, kills, player kills, quests, quest streaks,
  deaths, bank and purse totals and casino wins and losses; and twenty
  more places to find, every one of them the destination of a published
  route, so all of them can be walked to. No new hook and no new saved
  field: the earned set is written by key, so nobody's player file
  changes.

- **`scripts/test-parallel.sh` runs the test modules across every core.**
  The suite took about 87 minutes because `unittest discover` is serial
  and 50 of the 75 modules boot a real server that parses all 7,781
  rooms -- eleven cores idle for an hour and a half. Nothing in the
  fixtures had to change to allow it: each `LiveMud` already picks a free
  port and its own throwaway copy of `area/`, they were simply never run
  at the same time. The full suite is now **10m 28s, all passing**, and
  failures are reprinted together at the end instead of buried in the
  interleaving.

- **Live player state reaches GitHub every five minutes.** `player/`,
  `gods/`, `log/` and the `area/` runtime files are committed to `main`
  in plaintext by `toc-state-sync` on whichever host is running the
  game, so an outage costs minutes rather than everything since the
  last time somebody thought to copy them. `toc-state-sync-check`
  complains -- to the journal, to a marker file, and into the game
  where staff will see it -- if that stops working, because the way
  backups fail is quietly. `deploy/toc-restore` rebuilds a working
  game from the public repository and nothing else, and has been
  rehearsed rather than only written.

- **Characters are written to disk every five minutes instead of
  every thirty.** Stock ROM staggers autosaves over a 30-tick cycle,
  so syncing every five minutes was copying files that could be half
  an hour stale. `AUTOSAVE_CYCLE_TICKS` closes that.

### Fixed

- **Hermie's menu ran to three screens and ate the command after it.**
  `page_to_char` stops at "[Hit Return to continue]" and takes
  whatever arrives next as that return, so asking her for a buff
  straight after reading her list did nothing at all -- no refusal, no
  message, nothing. Three columns of keywords with the groups on one
  line brings forty-odd rows down to twelve, and a test now asserts it
  does not page.

- **A player-state sync no longer starts a CI run.** Every one used to:
  an hour and a half of runner time to be told no code had changed,
  three times an hour, burying the real failures underneath. Guarded
  twice, by `paths-ignore` on the workflow and `[skip ci]` in the
  commit.

- **The dashboard's host panel worked on the Pi and nowhere else.** It
  was disabled by default and its service, timer and journal unit
  names were hard-coded to the appliance's, so on the VM both host
  endpoints answered 503 and every table came back empty. The names
  come from the environment now. Game uptime moved onto the host
  payload as well, so the Host tab stops showing "Locked" beside a
  host uptime that is working, and the tile next to it no longer calls
  the machine a Pi.

- **The endless water jug is back in the newbie pack.** Only the
  ordinary one was meant to come out.

- Mudlet package 1.0.6 explicitly shows and raises its mapper on refresh,
  resize, atlas load, and `tocgui on`, without overriding `tocgui off`.
- Staff `set char <name> mana` and `end` accept 0 through 30,000, matching
  the existing HP/movement ceiling instead of rejecting values above 15,000.

### Added

- **Shadowmeld is a real skill.** It is for two things: going AFK
  without being killed for it, and laying in wait in a room somebody has
  to walk through so that you strike first. The fourth remort teaches it at 50%
  and it improves from there with use and with failure like anything
  else; an immortal can grant it to anybody with `SET SKILL`, and no
  later remort takes it away. It sits in the table at level 3 for every
  class, because a remort restarts at 3 and a skill priced any higher
  could not be improved until the character had climbed all the way
  back. Nothing teaches it and no guildmaster sells it, so those two
  routes are the only ones.

  It behaves as STEALTH against other players now rather than as hide:
  the same roll against the same weather, so looking for the hidden no
  longer finds you. Holylight still does, and faerie fog still reveals
  you. VIS steps you out of it, WHO shows `[SHADOW]`, WHERE omits you
  and DANGER SENSE counts you -- everything stealth already did.

- **The third remort now carries four gifts.** Twice the carrying room,
  in slots and in weight alike; twice as long before the idle void; a
  second psionic power from each of the four disciplines; and the recall
  that never fails, moved down from the fourth remort to make room for
  shadowmeld.

- **Psionic powers stack across remorts.** They never did: a remort wipes
  the skill table, and the grant simply redealt one power per discipline,
  so a player could lose a discipline they had spent a whole life with.
  What has been awarded is remembered by name in `PsiKnown` now, put back
  before anything new is given, and the per-discipline target grows with
  the remort count -- one each at the second remort, two at the third,
  three at the fourth. The fifth hands over all seventeen, ahead of any
  immortal grant list, because there is no later life to award the rest
  in. Characters who earned powers before the field existed have it
  seeded from what they already know when their file loads.

- **Two new remort gifts.** The remort taken at level 56 doubles how
  long a character may idle before the void takes them. The one taken
  at level 57 gives SHADOWMELD: draw the shadows around yourself and
  stay in them until you move, sleeping if you like, with no creature
  in the world able to see you. It is meant for stepping away from the
  keyboard, and nothing else in the game is safe to do that in.

  Only two things end a meld: leaving the room, however you leave it,
  and swinging at somebody. Against other players it behaves like
  hide, so detect hidden and holylight still find you. It is the
  world's creatures you are hidden from.

  The check in `can_see` sits deliberately above the shortcut that
  hands every mobile of immortal level perfect sight. Below it, an
  aggressive high-level mobile would still have walked in and killed
  somebody who had stepped away, which is the one thing the gift
  exists to prevent.

  `idle_purge_ticks()` is now the only thing that decides an idle
  character's rope, and both branches of `char_update` use it.

### Fixed

- **HISTORY marks where you were away.** Type it and a
  `--- while you were away ---` line is drawn at the moment you last
  logged out, with everything said since below it, so the lines you
  would have seen had you been here are one command away. Nothing is
  pushed at you on arrival. The moment is recorded both on a clean quit
  and on losing link, so a dropped player's marker sits at the drop
  rather than at their last proper goodbye.

- **A social was logged as a refusal.** The watched-player log wrote its
  line from the command-table lookup, and socials are looked up after
  that, so every NOD, GRIN and BOW a watched character used was recorded
  as `(refused)`. A log that reports working commands as failures is
  worse than no log, since the whole value of it is being able to trust
  what it says. It is written after the lookup now and says which
  happened.

- **Hermie ignored a named item in silence.** A watched session showed
  somebody type `heal uncurse shieldb` eight times, try to drop the
  thing, and try again. Remove curse cannot be aimed -- it frees
  whichever cursed item fails its save first -- and the healer at the
  pit says so, but she was dropping the name without a word. She says
  it too now.

- **The Mudlet map did not appear until you clicked in the window.**
  Reported by Alaric. The mapper is built at load, before the profile
  window has settled, so it ended up the right shape but unpainted.
  Package 1.0.5 re-applies its geometry and calls `updateMap()` when the
  first room arrives, shortly after load, and on any window resize.

- **HISTORY reads back what was said.** A player's Mudlet chat capture
  stopped part way through a session and there was no way to recover
  the lines, so the game keeps them now. `HISTORY` on its own shows the
  last twenty across every channel the character can hear, oldest
  first, with the time against each; `HISTORY 50` shows more, `HISTORY
  GOSSIP` one channel, `HISTORY GOSSIP 5` the last five of it, and
  `HISTORY LIST` what is held. `REPLAY`, which had been a stub saying
  nothing was available and was never even registered in the command
  table, is now a synonym.

  A channel you may not hear is a channel you may not read back, and
  tells never go into the shared rings -- each character keeps their
  own copy of the tells they sent and received, and nobody else can
  read them. It is all held in memory and is lost on a reboot, which is
  the point: a way to catch up, not a transcript.

- **You could not set a recall point at the quest giver.** The room is
  ROOM_PRIVATE and the questmaster stands in it, so the questmaster and
  the player already made two and the gods "would not answer a prayer
  raised in this place". A recall point is refused by flags now, never
  by an occupancy count -- which was also stricter than recall itself,
  and unstable, since the stored room is rechecked on every use and
  would have reverted to the Temple the moment somebody else walked in.
  Jail, death traps and the rest still refuse it.

- **A mobile that lives in a room filled it.** The same count behind
  both of the above: a resident questmaster or shopkeeper took a
  privacy slot permanently, and a solitary room with a mobile in it
  admitted nobody at all.

- **An idle immortal filled a one-person room.** Standing in the quest
  room was enough to shut questing down for everybody: `ROOM_SOLITARY`
  counts occupants and counted staff among them. Staff are skipped now.
  They can also walk into such a room rather than being turned away --
  every caller had asked for level 69 rather than immortal rank, and
  asked it of the raw level rather than trust, so an ordinary immortal
  was refused and a trusted builder was refused everywhere.
  Implementor-only rooms keep the bar they had.

- **The quest master no longer sends anybody into Hyrule.** It is 443
  rooms, most of them generated, and its dungeons refuse recall, so a
  quest aimed at a mobile seven floors down was a half-hour march for a
  quest reward.

- **STASH LINK had no help at all.** HELP STASHLINK now covers the
  two-sided handshake, denying, blocking and sharing; HELP STASH lists
  every subcommand rather than four of them, PUT ALL included.

- **BOMB dealt damage and handed the turn straight back.** It takes
  half a target's maximum hit points with no roll and nothing consumed,
  and paid no lag either, so it could be typed as fast as the player
  could type it. It pays now.

  The sweep behind that checked every ability in the game: no damaging
  spell or skill has a `beats` of 0, and every other path that calls
  `damage()` either pays or is exempt for a stated reason.
  `tests/test_damage_lag.py` keeps it that way. A monk's *missed* NERVE
  DAMAGE still deals four dice and returns free, which is deliberate --
  a monk carries no weapon and that is part of what pays for it.
  ENERVATE, which prompted the check, was innocent: every path of it
  that deals damage pays 12 beats, and the log showing it spammed was
  an immortal, who bypasses lag by design.

- **A player could remort themselves into a corner they could never get
  out of.** Every life is meant to be a new one, so REMORT refuses a class
  or a guild you have already been. It read both out of one flat list, and
  because a guild is stored as its matching class index the two were
  conflated -- having been in the mage guild barred you from ever living
  as a mage. Each non-monk life burned two of only six values, so a mage
  of the cleric guild who went thief/warrior, then monk, then necro
  arrived at their fourth remort with nothing legal left to choose, was
  shown an empty list, and was stuck at level 57 with 59 out of reach for
  good.

  The class is the whole of the restriction now, because the class is
  what decides how a life plays. A class you have lived bars that class;
  the guild is free, so join any of them as often as you like. With six
  classes and at most five restricted lives there is always something
  left to pick. A refusal lists every class still open to you. The saved
  `ListRemorts` format is unchanged and is read back the way it was
  written, one life at a time. HELP REMORT described the old rule as a
  class-and-guild *combination*, which it never was.

- **All three staff channels were half-broken, and seven commands with
  them.** `channel_say()` decided who could hear by `victim->level`
  while the command table decides who may speak by `get_trust()`, so a
  builder trusted to immortal rank could talk on immtalk, godtalk or
  hero and never hear a word of the reply.

  Sweeping the 111 commands WIZHELP lists turned up the same fault in
  `switch`, `ksock`, `fsave`, `hpardon`, `maxloads`, `finger` and staff
  mail. `switch` was the worst: `IS_IMMORTAL(ch)` picked which message
  to print, and the branch below it is the werewolf shapeshift, so a
  trusted builder who switched was moved to room 9 with a `were_shape`
  copied onto the mobile they were possessing.

  The rank immtalk and godtalk print is now the trust that let the
  speaker on the channel rather than their level.

### Added

- **The note board answers back.** `note reply <n>` starts a note to
  whoever wrote that one, with the subject already set to `Re:` theirs
  and no second `Re:` if it was a reply already. `note forward <n>
  <player>` passes one on with the original text carried across and
  fenced as somebody else's words. `note search <text>` matches the
  sender, the subject or the body; `note unread` shows only what is
  waiting; `note catchup` marks the lot read without opening it.

  Answering a note used to mean reading it, remembering who sent it and
  what it was called, then typing `note to`, `note subject Re: ...` and
  hoping the name was right.

  One lister backs list, unread and search, and the number it prints is
  always the note's place in the full list. Search, see `2)`, read 2 --
  and it is the note you were looking at.

- **Twenty-five more achievements**, weighted to the categories that
  had almost nothing. Exploration goes from 3 to 22 and combat from 9
  to 15; the catalog is 152 of a reserved 192.

  Every exploration room is the destination of a published route, so
  the route walker has already proved you can get there on foot from
  the Oak Tree Square, and the points follow that walk rather than
  taste: Mud School is six rooms out and worth 5, Valhalla is
  ninety-four and worth 50. A test holds them to it.

  The combat ladder had gaps that covered most of a character's
  fighting life -- 100 straight to 1,000 to 10,000 kills, and 1 to 25
  to 100 player kills -- so it gains 500, 2,500 and 5,000 kills and 10,
  50 and 250 player kills.

  Nothing new was needed in the C: every one uses a requirement kind
  that already existed. Achievements persist by key rather than by
  index, so inserting these mid-table leaves earned ones alone.

- **Hermie takes a command, and has more to give.** `buff` reads out
  her list, `buff <name>` asks for one thing, `buff <group>` for a
  handful -- DEFENSE, DETECTS, TRAVEL, CURES, RESTORE, COMBAT -- and
  `buff all` for everything. It is shaped like `heal` at the pit
  because that is the shape players already know, except that she
  charges nothing, so the command sits at level 0. Speech still works
  and runs through the same code.

  Ten more spells on the list, and `refresh`, `heal` and `mana` now
  fill the pool rather than handing out a slice, with `vitals` for all
  three. Reading one watched session showed why that mattered: a player
  topping up said `22` nine times in three seconds and `23` nine times
  in two, and every one of them worked.

### Fixed

- **The healer at the pit no longer takes 250 gold in silence.**
  `spell_remove_curse` frees the first cursed item that fails its save
  and ended there with no else branch, so a player whose curse held was
  told nothing at all. One of them paid three times in eleven seconds
  and then sacrificed the item. It now says whether the curse held or
  whether nothing was cursed, and `heal uncurse <item>` answers that it
  cannot be aimed rather than discarding the word.

- **Watching a player records more than their typing.** `watch_log()`
  adds the things a command log cannot see: every room they end up in
  (a portal or a teleport moves them with no command to show for it),
  level changes, every change of coin, and both halves of a death. It
  costs one bit test for anybody not being watched. `REPORTS CLEAR`
  now also reaches the log rather than only telling whoever happened to
  be online.

- **Watching a player records what they did.** `log <name>` wrote a
  blank line for every step, because all ten directions are
  `LOG_NEVER` -- 82 of the 296 lines in the first captured session --
  and never recorded a command the game refused. It now logs every
  command with the room vnum, refusals included. Commands that carry a
  secret are logged by name with their arguments dropped, so a password
  is still never written down.

- **The game says when something is waiting for you.** Unread notes are
  announced at login, for everyone, instead of sitting unmentioned until
  somebody thought to type NOTE. Staff additionally get a count of the
  bug, typo and idea reports filed since they last looked, and a
  `REPORTS` command to read them: `reports` for a summary, `reports
  bugs|typos|ideas [n]` for the most recent, `reports clear <kind>` to
  set a file aside.

  `bug`, `typo` and `idea` have always appended one line to a flat file
  and done nothing else -- nothing announced a report and nothing read
  one back -- so on the live server they had reached 135, 106 and 500
  lines, unread. Most of it is not a report at all: typing `bug` and
  your next command on one line files the command, which is why those
  files are full of `wear all` and `short sword`. Clearing is part of
  the feature for that reason, and it renames the file with a timestamp
  rather than deleting it, because what a player told us is worth
  keeping even when the file is mostly noise.

  The read position lives in `pcdata->reports_seen[]` and saves as one
  `ReportsSeen` line under case `'R'`, which is the letter `fread_char`
  dispatches on. The staff half is gated on
  `IS_TRUSTED(ch, LEVEL_IMMORTAL)` rather than the raw level.

### Changed

- **The player report files and the note board are no longer tracked in
  git.** `area/bugs.txt`, `typos.txt`, `ideas.txt` and `notes.txt` held
  739 lines of player-written text, including player names and the
  in-game note board, and the running game rewrites all four. Runtime
  state does not belong in the repository. They are gitignored now;
  history still holds what was committed before.

  Untracking one of these is delicate. The updater advances the Pi with
  `git merge --ff-only`, and these paths are permanently dirty there, so
  a commit that touches one makes the merge refuse and blocks every
  later deploy until the tree is fixed by hand. The live copies were
  backed up and restored around this change.

- **Two monster wards that had never worked now do.** `dshield` and
  `baura` have sat in the skill table since before this repository's
  history as `spell_null`: no cast function, and in no class's skill
  group, so nothing in the game could produce either affect. The only
  other mention of them was a pair of blocks in `update.c` that swept up
  immunities the affect never granted -- and swept them while the ward
  was still standing rather than after it fell, so they were wrong as
  well as unreachable. They surfaced only through
  `set skill <char> all`, which walks the whole table and put two skills
  in a player's list that nothing in the game explained.

  They are monster abilities now. A **bloody aura** turns magic aside; a
  **dominion shield** turns aside weapon and spell alike, is only raised
  below half health, and lasts a single tick, so it reads as the last
  stretch of a hard fight rather than a wall. The aura rolls one in
  sixty-four every four seconds and only while it is down, which puts it
  up about a quarter of a fight -- at the one in eight it was first
  written with, the downtime was shorter than the affect and it would
  have been a permanent immunity to magic on four end-game mobiles. Both announce themselves
  going up and fading. The immunity rides on the affect through
  `APPLY_IMMUNITY`, the way iron skin's does, so it lifts exactly when
  the ward does and needs no sweeping.

  No class can reach either: both are level 72 across the board, above
  MAX_LEVEL. `spec_dominion_ward` is registered for builders, and four
  end-game mobiles that had no special of their own now carry it -- the
  Lord General and the Fade in the Battleground, Zoltan and the second
  succubus in Valhalla.

- **MIRROR, an immortal command that wears somebody else's kit.** It
  takes off what the immortal has on -- into their inventory, not
  destroyed -- and puts on what the named character is wearing, so a
  build can be looked at from the inside without asking anyone to hand
  anything over. It works whether or not they are logged in: an online
  character is read from the game, an offline one from the `Wear` lines
  of their last save, and the reply says which. Each piece is a fresh
  object from its prototype rather than their copy, so an enchantment
  they added is not reproduced. `mirror clear` takes it all off again.
  ITEM_ACTION is never put on, because `equip_char` fires those and one
  of them kills you, and MIRROR says so rather than passing over it
  silently. Nothing else can refuse a piece: the three `ITEM_ANTI_*`
  flags are cleared on the copy, so an item that would zap itself off
  someone of the immortal's alignment goes on anyway, and the kit is
  equipped from the last slot backwards so a two-handed weapon does not
  knock the shield off again.

  `mirror restore` undoes the whole thing: the borrowed kit goes into a
  pack named "<player>'s gear" in the immortal's inventory, and what
  they were wearing when they started goes back on. The slots are
  remembered as vnums rather than pointers -- an object can be dropped
  or destroyed between the two commands, and a stale pointer to one is a
  crash where a stale vnum is merely a piece that does not come back.
  Logged.

- **INVULN, an immortal toggle that stops anything hurting you.** No
  mobile, no player, no spell, and worn equipment stops taking damage
  too. `invuln damage` (the default) lets attacks connect and be
  described exactly as they would be, numbers and all, so a fight being
  watched still looks like a fight; `invuln absorb` makes every blow
  read the way one does against something immune to the weapon being
  used -- "Zog is unaffected by your slash!" -- borrowing the voice the
  game already has for this rather than inventing a second one, and
  naming the attack that failed. Unlike WIZINVIS and CLOAK it shows nowhere -- not
  on the score sheet, not to the room. Use of it is logged.

  It answers to **trust, not level**. `interp.c` gates every command on
  `get_trust()`, so as first written -- with the effect asking
  `IS_IMMORTAL()`, which reads the raw level -- a character trusted to
  immortal rank could run INVULN, was told it was on, and went on taking
  damage. Both ends now ask the same question. It still lapses on its
  own when trust is revoked, because `get_trust()` falls back to the
  level.

- **RECALL can be moved.** It was a one-way trip to the Temple for
  everybody; it now goes wherever the character last set it.

  - `RECALL SET` makes the room you are standing in your recall point.
  - `RECALL DEFAULT` puts it back to the Temple.
  - `RECALL WHERE` says where it is and whether you may move it yet.

  The wait is on *moving* the point, not on using it: recall stays free
  and repeatable, because a standing shortcut to one favourite room -- a
  hunting ground, a questmaster, the shop you live out of -- is the whole
  feature. What 30 minutes stops is changing where recall lands in the
  middle of something, which is the version that would matter in a fight.
  Setting is also refused while fighting and while battleticks are still
  running, so it cannot be used to reposition during a hunt.

  `RECALL DEFAULT` is exempt from the wait by design. It is the way back
  from a choice that turned out badly, and a character who cannot reach
  their own recall point has no other way to reset it.

  A room must be one recall works in: no `ROOM_NO_RECALL`, no jail, no
  death trap, nothing private or staff-only. The stored vnum is rechecked
  on every use rather than trusted from the player file, so an area edit
  that removes the room or makes it no-recall quietly falls back to the
  Temple instead of stranding anyone.

- **WORD OF RECALL is worth casting.** Its help said it "is not generally
  considered useful since the recall skill is free and costs no mana",
  which was fair when both went to the same room. Now only the skill uses
  the point a character chose: the spell, a scroll or potion of it, the
  Recall Ring and the rescue of a link-dead player all go to the Temple.
  A cleric therefore has two places to reach in a hurry instead of one.

  The spell also works through a curse, where the skill does not. A curse
  silences your own prayer; it has no hold over somebody else's magic, and
  that is the other half of why a scroll of recall is worth carrying.
  `ROOM_NO_RECALL` still blocks everything -- that flag is how an area
  keeps you inside.

- **HELP CHANGES lists changes.** It promised "a log of recent game
  updates, balance changes, new features, and bug fixes" and then had
  none of them. It now carries the player-visible changes of the last
  month, newest first.

### Changed

- **The bottom of the economy is priced for the people standing in it.**
  `obj->cost` is copper, and `load_mobiles` rolls a mobile's coin from its
  level in six steps with cliffs between them: a level 4 mobile carries one
  to eight copper, a level 5 one about five silver, a level 10 one about
  five gold. Measured against that, prices from level 10 up were already
  about right -- the median object cost forty kills of a mobile its own
  level. Below it they were not:

  | item level | median price | kills to afford it |
  |---|---|---|
  | 1-4   | 20g - 1p75g | 1,000,000 |
  | 5-9   | 1p - 2p50g  | 2,801 |
  | 10-14 | 3p          | 59 |
  | 20-24 | 5p          | 43 |
  | 40-44 | 10p75g      | 23 |

  A turkey burger in Mud School cost ten gold. A level 1 mobile carries one
  or two copper, every character in the game starts in Mud School, and they
  start with nothing. `tools/reprice_by_level.py` rescaled 688 prices across
  70 files to the target the rest of the world already keeps -- one factor
  per level, so every ratio a builder chose survives exactly, and no price
  was raised. Nothing at level 10 or above was touched.

  Mud School now reads 1c for a loaf, 16c for a turkey burger, 48c for a
  lantern. Dresden's leather worker sells a leather cap for 56s and the
  jerkin for 1g 65s, about eleven and thirty-two kills at level 5; the
  weaponsmith's dagger is 2g 60s. Verified in a running game: a character
  created with an empty purse and sixty copper -- four kills' worth -- buys
  a meal and has forty-four left.

  What it does not do is the other end, where the same measurement says the
  median level 50 object costs three kills. That is the income table's last
  step, not the prices, and changing it moves every high-level character's
  earnings.

### Fixed

- **Herbs and spell components almost never landed.** `component_update()`
  chose where to put something by guessing a vnum between 0 and 65535 and
  asking whether a room lived there. With 7,781 rooms in play that finds
  *a* room about one try in eight; a room inside an area already chosen,
  about one try in eight hundred. The inner loop gave up after a hundred
  tries, which it did roughly nine times in ten, so most of what the
  function meant to scatter was never placed -- and the herb branch did
  not even check the area before dropping, so what did land often landed
  somewhere else. `COMPONENT` answered "New Components Scattered!" either
  way, so there was nothing to go on.

  `random_scatter_room()` walks the room hash once and samples, which
  always answers, and skips death traps, jails, private rooms and
  staff-only rooms. `COMPONENT` now counts before and after and prints
  both numbers.

  With the picker working the old rate would have buried the world, so it
  is much lower than it was on paper: the ceilings are 40 herbs and 25
  components rather than 250 and 200, one area and one or two herbs per
  round rather than up to twelve, and **nothing is scattered at all while
  nobody is logged in**. The world drains through the quiet hours instead
  of carpeting itself for whoever logs in first.

- **You could only spend the loose change in your pocket.** A price is
  quoted in copper and was charged with
  `can_adjust_coin_balance(ch, -cost, TYPE_COPPER)`, which reads exactly
  one field: `ch->new_copper`. A character carrying two and a half million
  platinum was told they could not afford a twenty-two silver loaf of
  bread, because they had a hundred and seventy-five loose coppers on them
  and the baker would not break anything larger. Nobody could buy anything
  they were not already carrying exact change for.

  Selling had the mirror of it. `cost > keeper->new_gold` compared a copper
  price against a count of gold coins, so a shopkeeper with 265 gold
  refused to pay more than 265 copper; the deduction from the keeper then
  failed silently, and the payment reached the seller as one undivided
  pile of copper -- thirteen gold arriving as a hundred and thirty thousand
  coins, which the carry-weight check then refused. Buying and selling now
  go through `has_enough_copper`, `spend_copper` and `gain_copper`, which
  work on the whole purse and break coins the way `add_money` always has.

- **The converter that moved every price to copper stopped 85 objects
  short, and nobody noticed for the length of the world.** Its docstring
  is right that an area file must be read as a stream of tokens; its loop
  then found the next record by scanning for the next `\n#`, which is not
  a record boundary. A Hyrule dungeon map carries an ASCII floor plan in an
  extra description and several of its rows begin with a hash. The scan
  landed inside one, found no vnum after it and gave up -- so the last 85
  objects in the world kept gold-scale prices after everything else had
  moved to copper. A Magical Shield whose description reads "displayed for
  130 rupees" sold for one silver and thirty copper. Both readers now walk
  the trailing `A`/`E`/`T` records the way `load_objects` does, and
  `scripts/build_hyrule_area.py` writes its rupee prices out in copper.

- **`scripts/build_hyrule_area.py` had drifted behind the area file it
  generates, and a regeneration would have undone a month of work.** 197
  rooms in `area/hyrule.are` had been given their recall and always-lit
  flags by hand: only the dungeons keep `ROOM_NO_RECALL`, and the overworld
  carries `ROOM2_ALWAYS_LIT` because its sectors go dark at sunset. The
  generator still wrote `ROOM_NO_RECALL` on all 443. Running
  `make hyrule-area` would have reverted both and failed fourteen
  assertions in `tests/test_hyrule_progression.py`. The rule lives in
  `room_flag_word()` now, and the generator reproduces the committed file
  exactly.

- **Remorting quietly took five armour classes off you, every time.**
  `do_remort` rebuilds the character as a bare level-3 body: armour back
  to 100, maxima back to the remort baseline, immunities and affect flags
  cleared. It does that with the character still wearing everything, and
  worn gear had already added itself to all three when it went on --
  `equip_char` writes into `ch->armor`, `ch->max_hit` and the flag words
  directly, not into `ch->affected`. Writing over the top of that threw
  the contribution away, and the player's next REMOVE then subtracted a
  bonus that was no longer there. Measured on a plain new character: 95
  armour before the remort, 95 after, 105 once the gear came off, against
  a bare baseline of 100. Repeatable on all five remorts, and the drift
  went the other way for anything the gear added rather than subtracted.
  The gear now comes off before the rebuild and goes back on after it, so
  `unequip_char` unwinds what `equip_char` did. Level checks are not
  re-applied -- the character was wearing it a second ago -- but
  ITEM_ACTION stays in the pack, because equipping one of those recalls or
  kills you.

- **A character whose password had a capital letter in it could not
  remort at all.** `one_argument` lowercases what it copies, which is
  right for a keyword and wrong for a password, and `crypt(3)` is case
  sensitive. `do_password` and `do_pkill` had each stolen a private copy
  of `one_argument` to dodge this -- the comment in `do_password` says so
  -- and `do_remort` simply did not notice. There is now one
  `one_argument_case()` and all three use it.

- **A remort was priced against the life it was leaving.**
  `exp_per_level` reads class, race and guild, and the starting
  experience was computed several lines before any of the three had been
  replaced.

- **A character below level 4 could never be given a quest.** The target
  filter rejected anything under level 3 absolutely and anything at or
  above the player's own level, so at levels 1 to 3 the two bounds
  crossed and nothing in the world qualified. Each attempt then spent a
  five-minute cooldown to say so. The floor is now relative for anyone
  who has not left Mud School, the ceiling includes the player's own
  level, and a failed request costs one minute rather than five.

- **AQUEST would not tell you how to use AQUEST unless you were already
  standing at a questmaster.** The command list, and every mistyped
  subcommand, fell through to the questmaster check and got "You can't do
  that here." Checking your own points, timer, streak or pending gamble
  already worked anywhere; printing the syntax now does too. Subcommands
  also accept abbreviations -- all nine start with a different letter --
  where before `aquest req` was a typo.

- **Three more things the questmaster got visibly wrong.** The shop
  listing is a literal handed to `send_to_char`, which does not collapse
  `%%`, so the bonus lines read "+10%%". Quest directions printed the raw
  `#AREA` line, sending players to "the {1 70} Killum Hyrule region"
  instead of the Valley of the Elves. And the short post-quest cooldown
  for someone with nothing left to level tested `ch->level == 50` in four
  places -- 50 stopped being the ceiling when remorts raised it to 59, so
  no hero it was written for ever matched it.

- **Recovery quest tokens were potions.** Vnums 25038-25042 are
  `ITEM_POTION` with every spell slot zero, so quaffing your own quest
  item destroyed it and left the quest unfinishable. They are ITEM_TRASH
  now, which is what they always were in everything but the number.

- **`area/commands.are` is Latin-1 and held 36 UTF-8 em-dashes**, which
  reach the player as three garbage characters each -- including in the
  REMORT and quest-shop help. Rewritten as ASCII hyphens. The REMORT help
  also still claimed gear was only kept on the fifth remort; stripping was
  removed for every remort some time ago.

- **The dashboard's mob flag map had no entry for ACT_QUESTM**, so none
  of the world's 16 questmasters showed as one. `ACT_B_BOY` was missing
  the same way.

- **The maintained guides had drifted behind the code.** AGENTS.md still
  said Hyrule disables recall everywhere, which stopped being true when
  the arcade cabinet made the area escapable, and so did the player
  guide. Neither the guides nor the README mentioned the travel
  directions at all, though they are generated, published and shown on
  two surfaces. Now recorded: how `.are` files actually parse and the
  five line shapes a reader has to accept; that prices are copper and go
  through `format_price`; what the route builder models and the two rules
  that keep its output honest; the `?v=` cache-busting requirement for
  anything under `webadmin/static/`; that `online.count` comes from the
  game over MSSP and when it does not; where the admin token lives and
  how to rotate it without it leaving the host; and that a large failure
  count can be one wrong expectation inside a subTest.

- **The Admin and Game lights in the top bar only ever updated on the
  Overview page.** They sit in the bar, which every view shares, but
  `loadRuntimeStatus()` was called from `loadOverview()` alone. Open the
  dashboard on Directions, World database or Gear finder and both dots
  kept the amber "pending" the markup gives them and never moved, so a
  healthy server read as one still being checked -- indefinitely. They
  also went stale on a page left open, since nothing refreshed them.

  They now refresh on every view change and on a fifteen-second timer.
  `/api/health` is public and the loopback probe behind it is cached for
  two seconds, so the poll costs nothing.

- **The dashboard's top bar ran off the right of the screen, taking the
  Refresh button and the service pills with it.** `app.css` pins the bar
  with `position: fixed; inset: 0 0 auto var(--sidebar-width)`, but
  `theme-dragon.css` loads after it and set `position: relative` on the
  same element, to anchor the gold rule it draws underneath. That won.
  A relatively positioned bar keeps its parent's full width and `left`
  merely shifts it, so the bar was the width of the page *plus* the
  sidebar: 1493px inside a 1280px window, with the last 213px off-screen
  and the document scrolling sideways to match.

  `position: fixed` already establishes the containing block that the
  `::after` needs, so the theme no longer sets position on the top bar;
  the player client's own bar is a plain flex item and keeps it. The bar
  now ends exactly at the viewport edge with no horizontal overflow, at
  desktop and at phone width, and the gold rule still draws.

  The theme stylesheet's cache-busting version is bumped too -- without
  it browsers keep the copy that carries the bug.

- **The published route to Wyvern's Tower was "crawl hole", which walks
  you into a prank.** Six decoy objects sit in the Center of Oak Tree
  Square -- a hole, a crevice, an air shaft, a chasm, a rock and a
  platform -- and every one drops you into room 1607, the House of
  Pancakes. That room says the ceiling has crushed you, prints a fake
  `<1hp 0m 0mv>` prompt, and a tick later teleports you to the Temple
  altar. You are not hurt; it is a joke on the curious.

  The router could not tell a joke from a door. 1607 belongs to
  wyvern.are, so arriving there counted as arriving in Wyvern's Tower,
  and the whole route to that area was published as one command that
  fake-kills the reader and leaves them at the Temple. A room whose
  teleport destination is the recall point is an ejector, not a passage;
  six of them exist and none is now walked into or counted as an
  entrance. Wyvern's Tower routes by an actual ten-step walk to the Main
  Eastern Road.

- **The Routes filter defaulted to hiding half the directions.** Both
  the client panel and the dashboard opened on the worked-out routes,
  leaving the eighty-one handed down by players a click away, which most
  people never made. With 170 routes and a search box already narrowing
  them, the filter earned nothing. It is gone from both surfaces: every
  route is listed, and each card carries a tag saying whether it was
  worked out of the world as it stands or handed down, beside the badge
  saying how well it still holds up.

- **Eight handed-down routes aimed at a thing rather than an area, so
  when they drifted nothing could offer a way there.** `match_area`
  pairs a broken route with the area it was heading for, but "Pitch
  Black Opal", "Hobgoblins" and "Bright White Light" name an object, a
  mob and a light, not a destination on the area list -- they were
  published as broken with no replacement, though all three targets are
  still in the world and still reachable. The builder now also looks for
  the thing a route is named after: a room by its name, or the room a
  mob or object is reset into, nearest to the Oak Tree Square.

  Repaired routes go from 7 to 9 of the 10 that drifted. Hobgoblins
  lands in the Hobgoblin Barracks, in the same area its old directions
  were heading for, and Pitch Black Opal (path 2) lands in An ancient
  tomb -- which is exactly where its path 1, still verified, arrives.

  Bright White Light is left unrepaired on purpose. Its name matches
  four different reachable things -- a chamber in the High Tower, a
  brilliant white light in the crypt, and two other lights -- with no
  way to tell from the name which was meant, and a confidently wrong
  route is worse than a note saying where the old one stops.

- **The validation workflow had been red on every commit since
  2026-09-20, reporting 203 test failures.** It was five, and none of them
  a product bug. One asserts inside a `subTest` that loops over all 443
  Hyrule rooms, so a single wrong expectation printed itself 197 times and
  buried the other four.

  Four guarded code that had been deliberately refactored into shared
  helpers, and went on asserting at the old address: the charm binding
  that three create-undead spells now share through `raise_undead`,
  Herbie's return to his own room now shared through `herbie_visit`, and
  the lore appraisal that prints through `format_price` since prices moved
  to copper. Each is repointed at where the behaviour now lives, and the
  behaviour was checked to still be there first -- these fail again if it
  goes away.

  The fifth asserted that every Hyrule room carries `ROOM_NO_RECALL`. That
  stopped being the design when the arcade cabinet was built: the area
  used to be one nobody could leave, and 197 rooms gave the flag up so
  players can recall out. `no_recall` is now exactly the dungeon range,
  30400 to 30645, and the test says so -- as one set comparison rather
  than 443 subtests, so the next mismatch prints one readable failure
  instead of nearly two hundred. A companion test covers the other half of
  that change, that the overworld carries `ROOM2_ALWAYS_LIT` and no longer
  goes dark at sunset; nothing guarded it before.

- **The dashboard's area parser still called room flag2 `B` "unused".**
  `src/merc.h` renamed it `ROOM2_ALWAYS_LIT` when the Hyrule overworld
  stopped blacking out at night, so the dashboard displayed nothing for a
  flag that is now load-bearing.

- **`tests/test_players_online.py` errored instead of skipping** where
  fastapi is not installed. It now reports the same reason the other
  webadmin tests do.

### Added

- **Directions on the dashboard, and an end to serving the old client
  script.** The routes went into the player client at `/client` but never
  into the dashboard at `/`, which is where an operator actually looks --
  `index.html` and `app.js` had no reference to them at all. There is now
  a Directions item in the left nav, among the public views, reading the
  same `/api/directions` feed as the client so the two cannot drift.

  The client's own panel was also invisible to anyone who had opened it
  before: `client.html` still asked for `client.js?v=4`, the same URL it
  used before the panel was rewritten, so browsers kept the cached script.
  The client and dashboard asset versions are bumped.

- **The dashboard's "players online" count was the login journal, which
  only ever over-reports.** `players_online()` promised in its own
  docstring that the names were "bounded by real connections", with "the
  socket count ... the authority on how many". No such bound existed: it
  read `log/logins.tsv` and counted names whose last event was a
  `connect`. A session that ends without a recorded close leaves one of
  those behind for good, so the number drifts upward and never comes back
  -- and the Pi deploy gate, which holds a game restart while players are
  on, was reading it.

  The game already knows. `telnet_count_players()` walks the descriptor
  list counting `CON_PLAYING` with a character, and answers `DO MSSP` with
  the total. The dashboard now asks down the same short loopback probe the
  health check already opens, caches it for two seconds so a five-second
  poll does not double the connections, and reports that as
  `online.count`. The journal is used only to put names to it, and where
  it holds more names than there are players the older sessions are
  dropped as the stale ones. A new `online.source` field says `"game"` or
  `"journal"`, so a caller can tell a reading from an upper bound instead
  of guessing.

  `tests/test_players_online.py` stands a fake MSSP listener up and covers
  the count overriding a stale journal, an empty game reporting nobody,
  more players than names, an unreachable game falling back with
  `source == "journal"`, and the health flag still tracking reachability.

- **You could not repair the armour you were wearing.** The help for
  REPAIR says it works "on worn equipment", and that is where damaged gear
  normally is -- `damage_eq` only strips a piece off once its condition
  drops below zero, so anything merely dented stays on your body. But
  `do_repair` looked the item up with `get_obj_carry`, which skips
  anything whose `wear_loc` is set, and then said **"You aren't carrying
  that!"** about a sword the character was holding. It now looks in the
  pack and then at what you have on. Breaking a worn item on the last
  repair is safe: `obj_from_char` unequips before it unlinks.

- **A repaired shield stayed permanently worse than the one you bought.**
  When `check_shield_block` dents a shield it takes a point off each of
  the item's four armour values and cuts its cost to a third. Nothing ever
  put either back, so the damage was permanent and compounding: ten dents
  cost ten points of armour class and left the shield worth a fifty-nine
  thousandth of its price, however many times it had been paid to repair.
  REPAIR now restores both from the object's prototype -- never above it,
  so an immortal's tuning and an enchanter's affects are untouched -- and
  re-seats a worn piece so the wearer's armour is recomputed.

- **Dented armour left the wearer a duplicate armour bonus for good.** The
  same code did `victim->armor[i] -= apply_ac(...)` before filing the
  values down, and never re-applied. `equip_char` already subtracts and
  `unequip_char` adds, so that second subtraction was a free armour-class
  gift each time a shield was hit, and taking the shield off gave back
  only the reduced amount -- leaving the character permanently better
  armoured than their equipment. It now removes the bonus at the old
  values and re-applies it at the new ones.

- **A repair quote was a bare number after prices moved to copper.** The
  cost is charged in gold through `has_enough_gold`/`add_money`, but it
  printed as a naked integer, so "It will cost you 250" sat next to shop
  prices reading `5g 20s`. Quotes now go through `format_price` and read
  in denominations. The formula is unchanged. The cost is also computed
  and clamped as a `long` before being multiplied up into copper, so an
  immortal-set condition or level cannot overflow the quote.

- **Two smaller things in the same command.** Refusing a repair for want
  of money printed the price without ever saying you could not afford it;
  it says so now. And the smith's line when an item finally breaks was
  passed to `do_say` with `\n\r` inside it, which put a line break in
  the middle of a speech.

- **REPAIR's help was wrong twice over.** It said the price depends on the
  item's "condition and type" -- it is condition and level -- and it never
  mentioned that an item breaks for good after about two dozen repairs,
  which is a poor thing to discover by losing something. Both corrected,
  along with the note that the item may be worn or carried.

  `tests/test_repair_gear.py` covers repairing worn and packed gear, the
  restoration of filed-down armour values and price, the denominated
  quote, an undamaged item, a missing item and standing nowhere near a
  smith.

- **The route finder sent everyone to New Thalos by Newbie Train.**
  Teleport rooms became graph edges when the router learned to read them,
  and breadth-first search prices every edge at one step -- so eleven
  stops of standing still on a train that moves every five ticks looked
  cheaper than walking. 29 of the 89 routes went that way, 191 wait-steps
  in all. Routing is now Dijkstra: a door, a portal, a rope or a jump
  still costs one, and a room that carries you costs eight, because you
  wait on its timer and cannot steer. No route uses a carried room any
  more, and nothing became unreachable -- the Assassins Guild's
  transportation chamber is still the only way to its upper floor, and a
  costly edge is still used where it is the only edge.

### Added

- **The Routes panel in the browser client now shows what it has.** It
  was reading `counts.verified`, which the file does not contain, so the
  intro read "0 walk cleanly today"; and its badge logic only knew
  `verified`, so all 89 worked-out routes rendered as "needs checking".
  The 81 routes handed down by players were fetched and then ignored
  entirely, replacements included.

  There is now a Worked out / Handed down / All filter, honest badges
  (checks out, still walks, repaired, has drifted), and the distance in
  rooms. Where a handed-down route no longer arrives and the builder
  worked out a replacement, the card shows the note, the replacement
  destination and a second one-click route -- 7 of the 10 drifted routes
  have one.

- **The button in Haze's private study is armed.** Object 29422 in
  `world.are` loads into room 29498, reached by climbing the colossal oak
  at the Edge of the Woods and opening the glowing circle in the
  Treehouse ceiling. Pushing it kills everyone in the room except whoever
  pushed it, which is what `value[4] == 3` has always meant; the room
  description has warned about it all along.

- **Whole areas looked unreachable because the route finder could not
  read them, and 175 resets had been deleted on the strength of that.**
  `.are` files are a token stream: `fread_letter`, `fread_number` and
  `fread_string` all skip whitespace, so the game does not care where a
  builder broke a line. `tools/build_directions.py` cared, in four
  separate places, and each one silently dropped content:

  - a record header written `#114 ` with a trailing space was skipped.
    Object 114 is the portal from the Eye of the Storm into Mega-City One,
    so a 28-room area looked cut off; 22 records are written that way.
  - a record whose name starts on the same line as its vnum
    (`#24377 The White Queen's Chamber~`) was skipped entirely.
  - an exit whose description starts on the same line as its `D3` was
    dropped -- 2,275 of the world's 19,971 exits, including the west door
    out of the Assassins Guild's three-way intersection.
  - `ITEM_MANIPULATION` objects and rooms flagged `ROOM_TELEPORT` or
    `ROOM_RIVER` were not treated as edges at all, though they are how you
    reach Dylan's front gate, the top of the Lonely Mountain, the Treehouse
    in Mid-World, the Mud School chute and the Assassins Guild's upper
    floor. 95 objects and 103 rooms carry you somewhere.

  Reachable rooms go from 7,399 to 7,568 and the router now agrees with
  `check_exits.py` that no exit in the world is dangling. 78 of the 81
  handed-down routes walk, up from 64.

  The same misreading had already been acted on in the world data. 175
  resets across `chess.are`, `korzath1.are` and `world.are` were commented
  out with `(removed: room does not exist)` or `(removed: obj does not
  exist)`; every room, mob and object they named is present. The 38 rooms
  affected are all reachable and every one of them was standing empty --
  Korzath's Engineering Department, the Metalworks, The Joker's Throne.
  All are restored except the button in Haze's private study, object
  29422, whose `value[4] == 3` kills everyone in the room except whoever
  pushes it; arming that is a gameplay decision, not a parsing repair, and
  its comment now says so. Native validation reports 5,703 active mobs
  before and 5,762 after.

  `tests/test_directions_router.py` pins the router against the
  dashboard's independent parser and against each record shape that was
  being missed.

- **One player quitting disconnected every other player online.** `do_quit`
  ends with a loop meant to close a duplicate login of the same character,
  comparing `CHAR_DATA.id`. Nothing in the codebase ever assigns that field
  -- the only line touching it was the comparison -- so every character's
  id was 0, the test was `0 == 0`, and the loop extracted and closed every
  connected descriptor. `delete` routes through `do_quit`, so it behaved
  the same way. It was reported as "snooping someone who deletes
  disconnects the immortal", which was simply the case where somebody was
  watching closely enough to notice. The loop now matches on name, copied
  out before `extract_char` frees `ch`.

- **The Makefile never rebuilt anything when a header changed.** Its
  pattern rules depended only on the `.c` file, so editing `merc.h`
  recompiled nothing -- not a stale build but a silently corrupt one.
  `MAX_INPUT_LENGTH` sizes three arrays inside `DESCRIPTOR_DATA`, so
  changing it rebuilt only the touched translation units with the new
  struct layout while the rest kept the old; the linker joins that without
  complaint and the program then reads and writes past the fields it thinks
  it is addressing. It surfaced as a long paste wedging a connection under
  `make` while the identical source handled it correctly under CMake, which
  tracks headers properly. Fixed with `-MMD -MP` and `-include`: touching
  `merc.h` now schedules 35 recompiles where it scheduled none. Production
  was never affected -- `deploy/toc2026-update` runs `make clean` first.
  **When Make and CMake disagree on behaviour, suspect the build.**

- Nine permission gates read `ch->trust` directly instead of calling
  `get_trust()`. `trust` is 0 unless somebody explicitly assigns one, which
  is the normal state, so each gate compared 0 against its threshold and
  refused everybody including implementors: `stat room`, `gather` from the
  world and by name, `advance`, `mset qp` above 100, `oset` on portals and
  on item types, switched-immortal visibility in `who`/`whois`, and `order`
  against a charmed immortal (which compared two raw trusts, so `0 >= 0`
  refused every such order). The three gated at exactly 70 widen access
  rather than restore it, which is what the comparison was written to mean.

- Twenty-two immortal commands refused when `get_trust(victim) >=
  get_trust(ch)`. At MAX_LEVEL that reads `70 >= 70`, so an implementor
  could not point any of them at another implementor -- the people those
  commands mostly exist for. `rank_protects()` in `handler.c` now states
  the exemption once. Below MAX_LEVEL nothing changes, and `victim == ch`
  guards are untouched: rank is not what those are about.

- `say` truncated itself at `MAX_INPUT_LENGTH - 100`, or 156 characters,
  silently, and no other channel did. The limit is 510 now, and overrunning
  it trims the line, delivers it, and says how much was used. Overflowing
  the accumulation buffer used to return FALSE from `read_from_descriptor`,
  which the caller treats as a hangup -- so pasting something long cost you
  the connection and everything you had typed.

- A multi-word alias lost its argument. The expansion joins the alias body
  to whatever follows as `"%s %s"`, so used bare it produced `"goto 4108 "`
  with a trailing space; `do_goto` hands its whole argument to
  `find_location` without tokenising, `is_number("4108 ")` is false because
  of the space, and it stops treating the argument as a vnum. Single-word
  aliases were unaffected. The composed line is trimmed now.

- `prompt` with no argument turned prompts *off*, so the obvious way to ask
  what your prompt was set to was also the way to lose it. The help file
  has described the opposite for years; the code now matches it.

- `WIZINFO` opened a colour and never closed it, so cyan ran on into
  whatever printed next. It was the only coloured channel in the codebase
  missing its `{00`, and it fires on every login.

- Both strings of berries in the newbie pack are `ITEM_NODROP`, so a newbie
  given the pack could not put them down. Cleared on the copies the pack
  makes rather than on vnums 5776 and 5780, which exist elsewhere in the
  world where the flag is deliberate.

- New characters got recall at 1%. `group_add()` grants every starting
  skill at 1%, which is fine for skills you practise up and wrong for the
  one that gets a level one character out of trouble. Two other places
  already set it (50 on a legacy file upgrade, 100 on reroll) and neither
  covered creation, which is why it went unnoticed.

- Hyrule's hand-written mobs did not answer to the words describing them:
  `look old` and `look man` both missed "a gambling old man", whose
  keywords were `hyrule money game elder`. The generator now folds the
  short description into the keywords, so the rule holds for future mobs
  rather than for the eleven that were wrong.

- `Sock.sinaddr` and `EOF encountered on read` fired for every connection
  including the healthcheck's loopback probe every two minutes -- roughly
  1,400 lines a day burying everything else. Both are now skipped for
  loopback only.

- The dashboard displayed `127.0.0.1:9000` as the game endpoint. That is
  where the web service dials, not anywhere a player can reach.

- `parse_login_journal`'s docstring claimed newest-first while the function
  returns file order, oldest first.

### Changed

- **Prices are counted in copper.** `obj->cost` was denominated in gold, so
  the cheapest anything in the world could be was one gold piece -- ten
  thousand copper. The loaf of bread in Mud School showed "1" on the shop
  list and took a gold coin, which is not a price a newbie can meet. It
  costs one copper now.

  Every price in every loaded area was multiplied by `COPPER_PER_GOLD`, so
  nothing is worth more or less than it was; only the unit changed.
  `tools/costs_to_copper.py` did it and is kept, because it had to learn
  four things about the format that a simpler tool gets wrong: several
  areas are written double-spaced, one object runs its flag and value lines
  together, weapons carry letters rather than numbers in their value
  fields, and `ITEM_FLAGS2` adds a flag word that shifts everything after
  it. It also reproduces a genuine loader quirk -- `fread_flag` does not
  handle a minus sign, so on a negative value field it returns zero
  *without consuming the character*, and the whole rest of that object's
  header shifts along by one.

  `obj->cost` is a `long` now: four objects were already dear enough that
  ten thousand times their price overflows an int.

  Player files carry a price per carried object, so they gain a version.
  A file written before version 4 has its object costs scaled on load;
  without that every item anybody was carrying would come back worth a ten
  thousandth of what they put it down with.

  Everything that compared a price against a fixed number moved with it:
  the pawnbroker's divisor and his ceiling, the junk collector's threshold,
  and the three trust gates that cap what an immortal may load. `do_repair`,
  the healer and the casino keep their own gold formulas, because none of
  them derives from `obj->cost` and converting them would be a balance
  change rather than a unit change.

  Every price a player is shown now carries its denomination -- `1c`,
  `5g 20s`, `3p` -- on `list`, `value`, `sell`, haggling, `lore` and
  `identify`. They were bare numbers before, which is how a gold price came
  to look like a copper one.

  One bug fixed on the way: sacrifice computed its reward in copper and then
  capped it with `UMIN(copper, obj->cost)` in gold, so sacrificing a
  one-gold item paid you one copper.

### Added

- **The necromancer's undead line works.** `create skeleton`, `create
  wraith`, `create vampire` and `animate parts` were all `TAR_OBJ_HERE`,
  so each needed a corpse or a dismembered body part lying in the room --
  and corpses decay, and only `butcher` makes parts. A class whose
  signature ability only fires in the seconds after a kill does not have
  one. All four now cast anywhere, and the component makes them stronger
  instead of being the price of entry: a servant raised over a corpse has
  half again the hit points, twice the duration, and part of the corpse's
  level added to its own; `animate parts` throws a real part for full
  damage and a fistful of carrion otherwise.

  The three create spells also scaled off the *corpse* rather than the
  caster, so a level 40 necromancer who killed a rat got a level 3
  skeleton with ten hitroll. The vampire already scaled off the caster,
  which is why it was the only one anyone used. All three follow the
  caster now. `butcher` and `raise dead` keep their corpse requirements,
  because cutting up a body and resurrecting a dead player are what those
  spells are.

- **`cast` no longer needs quotes.** `one_argument` stops at a space, so
  every multi-word spell needed `cast 'create wraith' corpse`, and
  forgetting the quotes answered "You don't know any spells of that name"
  -- which reads as the spell being missing rather than the syntax being
  wrong. It now takes the longest leading run of words that names a spell,
  so `cast cure light dwarf` finds cure light and leaves the dwarf.
  Quoting and abbreviating both still work.


- **Rooms built in game now survive a reboot.** `goto <unused vnum>` has
  always made a room and `set room` has always been able to name, describe
  and flag it, but nothing ever wrote any of it down, so the whole feature
  was unusable -- and there was no way to connect two rooms together
  anyway. `AREA_DATA` now records the file it was read from, `rlink` digs
  exits (both ways, with doors, locks, keys and secret keywords), and
  `rsave` writes the standing area's rooms back to its `.are`.

  Rooms made in game belong to `area/custom.are`, which is now in
  `area.lst`, so a saved room is loaded at the next boot and built on
  rather than overwritten -- `new_area` adopts the loaded area instead of
  allocating a fresh one.

  Two limits. A room that came out of a shipped area file may only be
  changed by an implementor; `set room` and `rlink` both refuse below
  `MAX_LEVEL`, because building in your own rooms and editing Hyrule are
  not the same act. And saving over an existing `.are` takes a confirmation
  naming the file (`rsave confirm hyrule.are`), so a stray `rsave` in a
  room you happened to be standing in cannot rewrite it. The previous file
  is kept as a dated `.bak`, and the new one is written to a temp name and
  renamed, so an interrupted save leaves the original intact.

  The writer refuses rooms it cannot round-trip -- a second flag word, a
  river or teleport destination, a room affect -- and names the room rather
  than writing a file that has quietly dropped them. Those fields live in
  lists outside the room and the loader reads them only when the matching
  flag is set, so writing the flag without the data would make it read the
  next room's fields as this one's. Help: `BUILDING`, `RLINK`, `RSAVE`.

- **Hero's grip**, a warrior/warrior skill from level 35: a passive chance
  to keep hold of your weapon when somebody disarms you, reaching certainty
  at 100%. It is the warrior's own answer to `bewitch weapon`, and
  deliberately not the same thing -- bewitch curses the weapon so nobody
  can remove it, including its owner, while the grip does nothing to the
  weapon at all. `remove` and `wield` keep working, and it cannot be put on
  a weapon, a follower or anyone else.

  Practice takes it to 75% ten points at a time; the last quarter comes
  only from having disarms thrown at you, at `confuse`'s rating, so it is a
  slow finish. Every disarm attempt is a chance to improve whether or not
  you keep the weapon. Vladamir the veteran teaches it; Dolonar the
  blacksmith and Breark the troll will practice it. Every W/W already
  playing has it at 1% from their next login, granted in `load_char_obj`
  and on joining the guild. `skill_table` can gate by class but has no
  column for guild, so `is_warrior_warrior()` carries that half of the
  rule.


- **Hermie**, a standing spellup desk and Herbie's girlfriend (mob vnum 98).
  `spellup` plants her; she casts on whoever talks to her from a menu she
  reads out, every spell pinned to 30 ticks and logged. `spellpurge` clears
  every copy in the world; she deliberately carries no `ACT_NOPURGE` so an
  ordinary `purge` clears the one in front of you. There is no speech hook
  in this codebase -- spec_funs run on a pulse and never see what a player
  said -- so `do_say` calls her directly. She answers only when addressed,
  or she would paste her menu over every conversation in her room.

- `DNS` is implemented; it was a stub answering "not available". It
  reports and toggles hostname resolution, lists what the resolver made of
  everyone connected beside their numeric address, and looks up one
  address. The toggle matters: `getnameinfo` runs in a single-threaded loop
  on every connection, so a slow resolver stalls the game mid-login.

- `GRANTPSI` works on a character who is not logged in, using the same
  load / modify / save / extract shape as `do_undeny`. An offline grant is
  always deferred -- "now" would apply to a copy about to be discarded.

- `SET` reaches the fields it could not: `hitroll damroll armor wimpy move
  maxmove exp` on characters, `name short long condition material` on
  objects, `name description` on rooms. The room text fields sit *before*
  the numeric check, which would otherwise reject them. Its help is
  rewritten and now lists every room flag, object extra flag, wear flag,
  item type and sector number -- they previously existed only in `merc.h`.

- `wizhelp` lists every command the character can use, sorted. The table
  hoists a few entries to the front for prefix matching, so the listing
  opened with `at`, `goto`, `iportal`, `sockets` and nothing was where you
  would look for it -- `smash` and `iportal` both read as missing when they
  had been there all along.

- `purge <object>` works, on portals or anything else, and says when the
  thing it removed was flagged nopurge. Purging a *player* now severs their
  link and leaves them linkdead rather than extracting the character.

- `holylight` carries the room vnum, and `prompt room on|off` adds or
  removes it for staff. `%R` is staff-only: `do_exits` already hid vnums
  from mortals and the prompt was the one place they leaked.

- `HELP NEW` lists everything a player can change about how the game reads,
  linked from the text shown at character creation. `damagenumbers` is
  documented and now **off** by default -- it was on with no help entry at
  all.

- The player web client has a searchable **Help** tab needing no login. It
  reads the area files rather than keeping a copy, so the site cannot drift
  from what the game serves to `HELP`. Only level 0 and below is exposed,
  filtered at parse time, since that is the whole security model for an
  unauthenticated endpoint.

- Server activity, the log terminal and login history page 50 at a time
  with arrows. Activity pages client-side deliberately -- its filters run
  over the whole history, so paging the fetch would filter within a page.
  `/api/logs/page` and `/api/events?paged=1` are new.

- The admin panel reports players online by name, and game uptime beside
  the host's: a deploy restarts the game and not the hardware.

- `WIZINFO` now reports empower, titanic, spellup, spellpurge, grantpsi and
  trust, saying whether a grant is permanent. Trust also tells the player
  being trusted. A mob catching lycanthropy from a dice roll no longer
  reports anything.

- `~/bin/toc-deploy` (developer machine, not in the repo) holds a deploy
  when a player other than Killuminati is connected. The updater restarts
  the game; before this existed a real player was disconnected twice in one
  afternoon.

### Changed

- Bank interest is 0.25% a day, down from 1% -- which compounds to roughly
  3700% a year and made a balance a better income than playing. `score`
  shows a lifetime interest total, since the payment arrives while you are
  offline and the notice scrolls past on login.

- Carry weight is half again the base for every player. It was briefly a
  newbie-only bonus, which just moved the wall further along.

- The newbie pack carries an endless snack pack and endless water jug in
  place of ten pot pies and a water jug, everything in it is level 1
  including the pack, and it holds 100 platinum.

- Every class starts its issued weapon at 40% instead of 1%.

- Announcements are upper-cased regardless of how they were typed, with a
  blank line and an indent so the text reads as the message rather than as
  part of the frame.

- `MAX_INPUT_LENGTH` is 512, giving 510 usable characters -- about six
  lines at 80 columns.

- The dashboard's local-admin unlock no longer trusts the `Host` header. It
  gated on `request.url.hostname`, which the caller writes, so a request from
  anywhere carrying `Host: 127.0.0.1` was issued an admin session cookie that
  opens every protected endpoint. It now gates on the peer address, the one
  part of a request a remote caller cannot choose. The unlock's other guard
  read `WEB_ADMIN_BIND` while uvicorn bound whatever `--host` said, and the
  production unit passes `--host 0.0.0.0` with no such variable set, so the
  guard believed it was loopback-bound; the bound address is now recorded at
  startup. Not exploitable in production, where the unlock is off, but one
  environment variable away from being so.

- Fixed the Python area parser losing a line on the seven shipped area files
  written with a blank line between every record line (hood, haven, wyvern,
  arena, firenewt, valley, trollden). It skipped blanks before the
  area/flags/sector line but not before the room name, so the blank became
  the name and the first line of the description was then read as the flags
  line. Around 300 rooms had an empty name and a word of prose stored as
  their sector type, which the dashboard displayed and which would have made
  the new world map unreadable. The C loader was always fine, so only
  Python-side consumers were affected. Blank room names go from ~300 to zero;
  world totals and every area-health baseline are unchanged.
- The Mudlet mapper now spirals outwards for a free square when the room it
  would place is already occupied. Placing each new room one step from the
  room walked in from assumes a grid, and one-way exits, up/down loops and
  teleports routinely put two rooms on the same square, where Mudlet drew
  them on top of each other.
- Fixed a blank line at the name prompt silently closing the connection.
  Stock ROM hangs up there without a word, which drops any player who simply
  presses Enter and any client that probes the login prompt with an empty
  line -- the reason a clean Mudlet profile could install the interface and
  then lose its first connection to the bundled generic mapper. The prompt is
  now reissued instead. The behaviour that made the hangup defensible is
  kept: a connection that sends nothing but blank lines is still dropped,
  after `MAX_BLANK_LOGIN_LINES` of them.
- Fixed three ragged rows in the `score` sheet, which is a fixed 62-column
  box built from independent format strings. The bank shared the Constitution
  row, where its four denominations needed nine more columns than the
  carried-coin cell beside them even at minimum field widths, and a balance
  past 999 platinum widened it further -- a real account holding 1,078,289
  platinum pushed that border thirteen columns past every other row. The bank
  now has a full-width row of its own, which keeps all four denominations and
  cannot be widened out of the box by any balance a long can hold. The
  achievements row was one column short and the Pkiller flag row two. A live
  test now asserts every row closes at exactly 62 columns, using the same
  balance that exposed the misalignment.
- Preserve link-dead characters and switched immortals during SIGTERM/SIGINT
  shutdown by saving all live player characters, not only connected descriptors.
- Preserve streaming ANSI colors and Telnet password state in the admin console;
  bound scrollback and render server text without interpreting it as HTML.
- Keep extensionless Unix deployment scripts LF-only on Windows checkouts.
- Make Mudlet package 1.0.2 reproducible across operating systems and zlib
  versions using LF source assets and deterministic stored ZIP entries.

- Allowed the sandboxed Pi updater to write only the system script and unit
  directories used by its checked-in self-refresh step. `ProtectSystem=full`
  previously blocked `/usr/local/sbin` before the validated update could
  restart either live service.

- The official Mudlet mapper now reconciles every standard direction against
  the latest `Room.Info`: removed exits are deleted, retargeted exits are
  replaced, and obsolete stubs are cleared when a room is revisited. The game
  also detects changed room data while a character remains in the same room,
  and package version 1.0.1 triggers automatic delivery of the fix.

- Fixed password input becoming visible in Telnet and browser clients. The
  modern option parser rejected the client's acknowledgement of the server's
  echo-suppression request, immediately cancelling it; the acknowledgement is
  now accepted and normal echo resumes only after password entry finishes.
- Fixed native macOS startup failing at `SO_LINGER` with "Numerical argument
  out of domain" by using a portable, bounded 30-second linger interval, and
  stopped the validator from requesting unsupported LeakSanitizer behavior on
  Darwin.
- Fixed `compare` overvaluing damroll and Strength by applying enhanced damage
  after damroll and by multiplying damroll into the backstab estimate; `one_hit`
  adds damroll last, after both. This could invert weapon recommendations,
  most sharply for thieves.
- Fixed projected equipment removal in `compare` erasing flight, invisibility,
  and detect-invisibility even when a spell still supplied the effect, where
  `unequip_char` preserves it.
- Fixed `compare` reporting weapons as usable by a monk under `steel fist`,
  which `wear` refuses.
- Fixed `bomb` accepting any object whose keyword merely began with "bomb",
  and `burn` accepting a candle carried unlit in inventory rather than the lit
  candle the help text documents.
- Hoisted a NULL check in `spell_cause_madness()` that sat after three
  dereferences of the pointer it guarded, so it could never have fired.
  `TAR_CHAR_DEFENSIVE` targeting means the pointer is the caster when no
  target is named, so NULL was not reachable, but a guard placed after the
  dereferences it protects is worse than no guard. Found by `-fanalyzer`.
- `coins_to_copper()` now saturates instead of overflowing. The obvious
  formulation multiplies the platinum count by 1,000,000 unguarded, which is
  undefined behaviour above roughly 9.2 trillion platinum. Normal play cannot
  reach that because `copper_to_breakdown()` only distributes totals that
  already fit, but a hand-edited or corrupted player file can, and pfile
  numbers are exactly what AGENTS.md requires validating before multiplying.
- Strengthened Telekinesis, which was capped at a 50% success rate even at
  100% skill because it rolled against `chance / 2`; no other psionic power
  halves its own learned percentage. It now rolls against the full skill.
  It also charged its whole 50-mana cost before searching, so a mistyped
  item name cost a full casting: the full cost is now paid only when an item
  is actually retrieved, and a fruitless search costs only the effort. A
  match that is merely too heavy to carry is now reported as such instead of
  being folded into "you couldn't find it".
- Astral Walk no longer uses the generic `saves_spell()` curve against
  mobiles, which pinned its resist roll at the 95 ceiling for the
  high-level targets the power exists to reach. It now uses the shared
  psionic ward check: an immune mind cannot be fixed upon, a resistant mind
  may shrug off the pull, and an ordinary mind cannot resist.
- Astral Walk and Shift now tell the caster that the crossing leaves them
  stunned. The stun itself is deliberate balance -- it denies a free opening
  turn so neither power can be used to jump a player and act first -- but it
  previously happened silently, with nothing explaining why the character
  could not act. Documented in help and the psionics guide, and pinned by a
  test so it is not softened by mistake.
- Fixed a use-after-free in the character/object list iterator that could
  corrupt memory or crash the server whenever something died inside a
  world-list loop. `extract_char()` removes the very element a
  `FOR_EACH_CHARACTER` loop is standing on, but `list_remove()` freed the
  node immediately while the iterator cursor still aliased that node's
  `next` field. Sixteen loops were exposed, including `violence_update()`,
  `aggr_update()`, `char_update()`, `mobile_update()`, `do_mindblast()`,
  `spell_earthquake()`, `spell_blizzard()` and `spell_call_lightning()`.
  Because `next` is the last field of `LIST_NODE`, a freed chunk usually
  still held a readable pointer, so the defect surfaced as rare
  unreproducible corruption rather than a dependable crash - which is why it
  survived a previous iterator fix. Removal now tombstones the node and
  defers the free until `flush_container_lists()` runs at the top of the game
  loop, where no iteration is in progress, and the iterator skips tombstones
  so an already extracted element is never handed back to a caller.
  AddressSanitizer confirms the old code faulted and the new code is clean;
  `tests/test_list_iterator.c` reproduces all four removal orderings and now
  runs under ASan/UBSan as part of both validation suites.
- Fixed Mind Leech and Enervate being silently halved against most targets.
  The same psionics pass that broke Confuse added the generic `saves_spell()`
  curve to both drains, and because that curve is driven by the target's
  (usually negative) saving throw rather than by any psionic defense, a
  mastered drain gave up half its effect on nearly every use. Both now share
  the Confuse ward model through a single `psionic_ward_check()` helper:
  mental immunity blocks the drain outright, mental resistance halves it on a
  bounded roll, and an ordinary mind cannot resist. Mindbar, Psionic Armor,
  and Psychic Shield still apply on top through
  `psionic_reduce_mental_drain()`, so real psionic defenses keep working.
  Confuse was refactored onto the same helper, so the resist band is tuned in
  one place (`PSI_RESIST_BASE`/`MIN`/`MAX`).
- Fixed Confuse failing almost every attempt. The psionics pass added the
  generic `saves_spell()` curve as a second gate, and that curve clamps to a
  95% resist rate against the negative saving throws most mobiles carry, so a
  100%-skill power was blocked nearly every cast. Confuse now gates only on
  the caster's concentration roll and the target's mental ward: a mind immune
  to mental damage is never confused, a mentally resistant mind gets one
  bounded resist roll (25% base, shifted by level difference, clamped to
  5-50%), and a normal or vulnerable mind cannot resist at all.
- Hardened carried-money conversion, bank deposits and withdrawals, shop and
  sacrifice payouts, group splits, gifts, theft, dropped piles, NPC corpse
  coins, and casino accounting against signed overflow, narrowing, partial
  mutation, and silent currency loss.
- Fixed partial money pickups leaving stale pile descriptions and values,
  loose piles being treated as 50 times heavier than carried coins,
  future-dated interest timestamps blocking accrual, consumed no-payout days
  not being saved, and 64-bit casino totals being truncated while loading.
- Fixed malformed or unterminated PK leaderboard data making every server boot
  and native area validation spin forever at end-of-file; valid records now
  load through a bounded line parser and malformed records are skipped.
- Corrected bank help to document the actual default platinum denomination and
  casino help to document the real 100,000-gold Hi/Lo and roulette limits.
- Fixed Hyrule mobile resets using a population cap of 1,000, which could
  duplicate Ganon and every other surviving NPC whenever an empty area reset
  ran after a player disconnected. Generated limits now match each mobile's
  intended population.

### Added

- The Mudlet package now ships a full-world map: all 7,781 rooms across 92
  areas, each area laid out offline with no two rooms sharing a square, and
  every exit resolved. It replaces the 25-room Mud School starter map.
  Mud School keeps area id 1 so an existing profile is not reshuffled, and
  area names are generated to match exactly what `Room.Info` sends, since the
  package looks areas up by name and a mismatch would silently duplicate
  every one of them. Package version 1.0.3 delivers it automatically.
- `tocgui atlas` pulls that world map into a profile on demand (package
  version 1.0.4). Mudlet only downloads the server's map into a profile
  that does not already have one, so every profile that connected before
  the atlas shipped would otherwise keep its old partial map forever. The
  command replaces the profile's saved map, so it is never automatic.
- Added boot-time local discovery for the Raspberry Pi appliance. Every
  NetworkManager Ethernet and Wi-Fi profile now explicitly sends `toc` as its
  IPv4 and IPv6 DHCP hostname, while Avahi publishes `toc.local` over mDNS.
  The configuration never cycles an active connection, so applying an update
  cannot interrupt SSH.

- Added in-game `MAP`, `MUDLET`, `GMCP`, and `WEBCLIENT` help covering automatic
  mapping, package controls, protocol data, browser capabilities, update
  behavior, persistence, troubleshooting, and intentional mapping limits.

- Added a native, low-memory Raspberry Pi appliance deployment with headless
  systemd boot, game/dashboard crash recovery, graceful SIGTERM player saves,
  capped journald storage, encrypted six-hour GitHub player snapshots, and an
  weekly guarded `origin/main` updater. The protected dashboard now includes
  **Update ToC**, which requests the same backup, fast-forward, one-job build,
  native area validation, restart, and health-check workflow. A private-LAN
  profile publishes the browser client and dashboard on port 9001 while keeping
  operational routes behind the persistent admin token.

- Added a sandboxed, timer-driven Namecheap Dynamic DNS updater for the Pi
  appliance. It detects and validates the public IPv4 address, keeps the
  `toc.jeremybean.com` A record current approximately every ten minutes, stores
  its domain-specific credential outside Git, and runs without a resident
  daemon.

- Added a low-duty-cycle Raspberry Pi ACT LED status indicator. It flashes
  briefly every two seconds while the MUD service is running, turns off when
  the game stops, and follows systemd boot and crash recovery automatically.

- Added first-class Mudlet support: `IAC GA` prompt framing, `Char.Vitals`,
  `Char.Status`, and `Room.Info` GMCP messages, automatic `Client.Map` and
  `Client.GUI` delivery, a 25-room Mud School MMP map, and a self-updating
  Mudlet package with gauges and an embedded mapper.
- Added deterministic Mudlet asset generation and tests plus a live handshake
  probe that verifies negotiation, package/map advertisement, ping handling,
  prompt framing, and isolation of GMCP data from login names.
- Added combat effects for the `flaming`, `frost`, `vampiric`, `sharp`, and
  `vorpal` weapon flags, which 135 of 623 weapons carried with no mechanical
  effect. Elemental flags add damage and convert the damage school so immunity
  and resistance apply; vampiric drains to the wielder; sharp and vorpal are
  damage procs scaled by weapon skill. Effects are folded into the single
  `damage()` call rather than added as a second call, and `compare` credits
  them. See `notes/weapon_flags_plan.md` for the balance notes.
- Added money-conservation and persistence tests to the live suite. Currency
  is four denominations backed by a single copper total plus a bank balance,
  so every operation is a conversion and a chance to lose or duplicate value;
  the tests assert that convert, deposit, withdraw, and drop/get all conserve
  it exactly, and that hostile amounts (zero, negative, overflowing, and
  non-numeric) move nothing. Persistence is checked by round trip rather than
  by reading the save code: every autolist toggle is flipped, saved, and
  re-read after a reconnect.
- Added `patch_player_file()` and `make_funded_character()` test helpers for
  state a fresh character cannot reach (coins, a bank balance, a starting
  room). They edit a character's own saved file, so no host `crypt(3)`
  binding is needed -- Python removed the `crypt` module in 3.13.
- Added MCCP2 output compression, negotiated per client and off by default.
  Compression is applied in `write_to_descriptor()`, the single choke point
  for descriptor output, so every existing caller benefits without knowing
  about it; GMCP and other protocol writes go through the same path and are
  compressed too. The handshake is sent uncompressed and the deflate stream
  armed only afterwards, since everything following the acknowledgement is
  deflate output. A failed deflate falls back to plain output rather than
  dropping the session, and the stream is released when the descriptor
  closes. Builds now link `libz`: `zlib1g-dev` to build, `zlib1g` at runtime
  (the Docker runtime stage previously shipped neither).
- Added telnet option handling. The input path had no IAC handling at all,
  so any client that negotiated options fed protocol bytes to the command
  interpreter as garbage, which is why none of the modern MUD options were
  supported. A single state machine in `src/telnet_proto.c` now consumes
  negotiation and subnegotiation, and three options are built on it:
  - **MSSP** reports name, player count, uptime, and codebase to crawlers, so
    the game can be indexed and kept current on MUD listing sites. Only
    already-public facts are exposed; nothing operational.
  - **NAWS** records the client's window size. It deliberately does not
    change the page length on its own, because `lines == 0` means the player
    turned paging off on purpose; `scroll` now reports the detected size and
    `scroll auto` opts in to it.
  - **GMCP** sends `Char.Vitals` alongside the prompt for clients that ask
    for it, so Mudlet-style gauges track without scraping prompt text.
  A plain Telnet client that negotiates nothing is unaffected, which is
  covered by its own test.
- Added per-address login throttling. Nothing counted failed password
  attempts before: a wrong password closed the socket, which cost an attacker
  only a reconnect, against hashes where just the first eight password bytes
  are effective. Five failures now refuse the address at accept() time with an
  escalating backoff from 30 seconds to a 15-minute cap; a success clears it
  and old history decays. The table is a fixed 64 entries so it cannot be used
  to exhaust memory. Loopback is exempt by default because the browser client
  bridges through the dashboard and every web player shares 127.0.0.1;
  `TOC_THROTTLE_LOOPBACK=1` opts it in.
- Added end-to-end gameplay tests that boot a real server, connect over
  Telnet, create a character, play, save, and reconnect. Every other test in
  the suite asserts on source text, so this is the first layer that can catch
  a change which compiles and reads correctly but does not actually work.
  Data is fully isolated: the game resolves its mutable paths relative to the
  working directory, so the harness runs each server from a throwaway `area/`
  copy and real `player/`, `gods/`, and `heroes/` data is never touched.
  Skipped automatically where there is no built binary or on Windows.
- Added an AddressSanitizer/UndefinedBehaviorSanitizer CI job that boots the
  full world, runs the list-iterator regression test, and performs a live
  startup smoke run. The normal suite cannot see memory errors, which is how
  the iterator use-after-free survived a previous fix.
- Added an authenticated dashboard operations snapshot with game reachability,
  queue depth, backup freshness, recent player saves, runtime-file activity,
  searchable Server Info/WizInfo history, and a compact expandable backup list.
- Added a guaranteed random Ganon relic drop alongside his fixed progression
  loot: the level 54-58 Hero's Tunic, Blue Ring, Red Ring, Mirror Shield, and
  Pegasus Boots. Their unique kill-healing, damage-ward, magic-ward, and travel
  effects are implemented in gameplay and modeled explicitly by `compare`.
- Added bounded semicolon command chaining to both browser game consoles, with
  ordered sends, quote and escape handling, single-entry history, and password
  protection.
- Added a WoW-style permanent character achievement system with 127 cataloged
  accomplishments, points, earned dates, ten categories, hidden discoveries,
  progress views, nearby unlock announcements, retroactive state checks, and
  save-compatible stable keys.
- Added sixteen Economy achievements for banking, interest, carried wealth,
  denominations, lifetime casino results, jackpots, straight-up roulette wins,
  and royal flushes.
- Added verified world-boss, rare-relic, crafting, unusual-death, Farslay, and
  expanded level achievements, including group boss credit and collection,
  crafting, encounter, and misadventure meta achievements.
- Fixed the player-scribed deadly black Farslay scroll recipe so it contains
  the Vengence spell instead of an invalid legacy skill name.
- Added complete Hyrule achievement tracking for dungeon discovery, maps,
  compasses, Triforce shards, signature items, all nine bosses, grouped boss
  credit, Ganon, Princess Zelda, and campaign-wide meta achievements.
- Added idempotent one-command installers and fresh-machine bootstraps for
  Windows, macOS, Debian/Ubuntu, and Raspberry Pi OS; installers now obtain
  prerequisites, generate private configuration, start Docker, build, launch,
  health-check, and preserve completed work across required OS restarts.
- Added PowerShell/Bash lifecycle launchers with start, build, stop, restart,
  status, logs, doctor, update, and dashboard-open actions, plus double-click
  Windows and macOS install/start entry points.
- Added an advanced in-game `compare` command with player-specific gear
  profiles, focus modes for damage, spells, defense, leveling, and utility,
  full-loadout projections, usability warnings, and percentage recommendations.
- Added a generated Hyrule First Quest area (`30200-30799`) with a teleport-only
  Campus entry, the 128-screen overworld, all nine source-derived dungeon
  layouts, a complete level 1-70 gear curve, and two return routes.
- Added data-driven `burn`, `bomb`, `play`, and `feed` puzzle commands for
  candle bushes, cracked walls, Recorder interactions, and the hungry Goriya.
- Added Hyrule progression tests for every gear level, dungeon entrances,
  boss drops, shard sources, canonical items, puzzles, and room reachability.
- Added a unique readable map and functional boss compass to each Hyrule
  dungeon, including route guidance through legacy portal and stair links.
- Added all First Quest regular, deluxe, and Letter-gated potion shops; 14
  rupee secrets; nine one-time door-repair charges; five money-making games;
  and the four-location Power Bracelet warp network.
- Added the Hyrule `gamble` command, bomb combat against Dodongo, reusable
  Magical Key behavior, consumable dungeon keys, automatic shutters, and
  signature Like Like, Bubble, Wallmaster, Gohma, and Ganon mechanics.
- Added `merc --check-area` / `merc --validate` startup mode for loading the full area database and exiting without opening a listening socket.
- Added reusable area-health linting in `webadmin/area_health.py`, the `scripts/area_lint.py` CLI, a web admin Area Health view, and the `/api/area_health` endpoint.
- Added cross-platform validation runners: `scripts/validate.ps1` for Windows/WSL and `scripts/validate.sh` for Linux, macOS, WSL, and CI.
- Added GitHub Actions validation in `.github/workflows/validate.yml`.
- Added Python unit tests for area-health summaries and key web-admin API behavior.
- Added the immortal `diagnostics` command for boot time, world totals, descriptor/list counts, active mobs, and backup schedule visibility.

### Changed

- Moved 25 unreferenced one-off scripts out of the repository root into
  `archive/tools/` with a README explaining each group. They were retired
  help-rewriting passes, bulk area fixers, typo sweeps, and abandoned
  dashboard prototypes that nothing in the runtime, build, validation suite,
  or CI referenced, and they sat beside the four checkers validation does
  run. Several perform the unbounded global `.are` replacement the area
  guide warns against, so they should not be mistaken for current tooling.
- Added ignore rules for CMake/build output (`bin/`, `build/`,
  `build-sanitize/`) and Python virtual environments (`.venv/`, `venv/`), so
  a documented `python3 -m venv .venv` no longer shows up as untracked work.
- Web-admin API tests now report why the test client is unavailable instead
  of always blaming a missing `fastapi`. starlette raises a `RuntimeError`
  when `httpx2` is absent, and these tests need both
  `webadmin/requirements.txt` and `scripts/requirements.txt`.
- Psionic travel, scouting, retrieval, control, draining, healing, and defense
  powers now share consistent room protection, saving throw, mana, lag, skill
  improvement, and combat-start behavior.
- Replaced contradictory psionics help with an accurate 17-power player guide,
  real remort selection rules, command costs, defense values, and restrictions.
- Docker Compose now binds both ports to loopback by default, supports explicit
  host bind/port variables, persists god/hero/corpse state, and reports game
  readiness through a container health check. Public install mode exposes only
  the game port.
- Docker image builds now exclude private runtime state, logs, backups, and
  `.env` from their context and create empty runtime mount points instead.
- Container startup now maps its unprivileged `toc` account to configured host
  UID/GID values before dropping privileges, allowing fresh Linux bind mounts
  to remain writable without running the game or dashboard as root.
- Area-health source tracking now follows `P` reset chains back to a real room
  or mobile source, without hiding objects inside unreachable containers.
- Expanded web admin configuration with `AREA_PATH`, `BACKUP_PATH`, `--area-path`, and `--backup-path`.
- Web admin reloads now validate a complete replacement parser, reject critical issues with HTTP 422, preserve the last known-good data on failure, and list recent backup archives.
- Operational web-admin endpoints are disabled until `WEB_ADMIN_TOKEN` is configured; queue payloads are bounded and restricted to one protocol-safe line.
- Player-save snapshots now use bounded native path construction and directory creation instead of shell-built `mkdir` commands.
- Backup archive creation now verifies shell command return codes, creates the backup directory when needed, and logs success only after archive creation succeeds.
- Rebuilt the repository documentation around dedicated player, command,
  hosting, operator, developer, contributing, and security guides; the README
  is now an accurate project front door instead of a mixed-audience manual.
- Corrected documented build paths, player/immortal level boundaries, remort
  thresholds, current world totals, web API routes, Docker restart behavior,
  dashboard exposure, legacy DES/Telnet limitations, and bow/run/speedwalk help.
- Replaced obsolete install/startup/cleanup/refresh instructions that used
  hard-coded paths, permissive modes, binary copies, and broad process kills
  with current prerequisite helpers and safe compatibility wrappers.
- Added `.env` Git/Docker exclusions, a safe `.env.example`, and ignore rules
  that prevent newly created player/god/hero files from being staged by
  accident; documented that already tracked legacy hashes remain exposed.
- Hyrule documentation now records source provenance, coordinate conversion,
  generated vnum ranges, progression, secrets, runtime rules, fidelity limits,
  regeneration, and regression coverage.

### Fixed

- Invalid portals no longer consume gold or charges, crystal-ball entry now
  replies to the player, successful Riding improves correctly, saddles use
  normal equipment hooks, and stale or invisible mount state no longer crashes
  or broadcasts uninitialized text.
- Monk buffs no longer consume mana when already active, ghost-blocked attacks
  no longer consume mana or movement, and a failed Crane Dance now uses its
  documented 30 mana while recording a failed skill attempt.
- Bulk `put` now rolls concealment independently for every item and reports an
  empty match; lycanthropy checks every weather tick, avoids reinfecting tagged
  mobiles, bounds restored were-form inventory, and skips stale object vnums.
- Immortal were-form editing now rejects negative indexes instead of reading
  before the form table.
- Dashboard view changes now return to the top instead of carrying a long
  Operations-page scroll offset into Overview or another section.
- Fixed `AUTOGOLD` searching the room instead of the defeated mobile's corpse,
  and made `AUTOSAC` preserve every corpse that still contains money, boss
  drops, or loot the player could not carry.
- Repaired normal bow shooting through closed or secret exits, silent immunity
  on `NOPURGE` mobiles, unsupported player targeting, missing Archery skill
  improvement, unsafe pursuit through one-way/transport exits, and potentially
  lethal anti-cheese backlash.
- Restored city guards' unreachable innocent-protection behavior, prevented an
  NPC cleric using Mana Convert from dereferencing player-only data, and fixed
  shield reflection leaving a one-hit-point attacker marked dead.
- Applied the Red Ring, Blue Ring, and Mirror Shield wards to reflected fire and
  frost damage so those effects match their player-facing descriptions.
- Made Ganon's Silver Arrow finale an explicit `shoot ganon` action, available
  at level 54 without Archery skill, while preserving the Arrow's boosted
  normal damage and preventing normal attacks from delivering the final blow.
- Ganon's one-hit-point phase now ends combat for every attacker, turns his
  room appearance bright red, announces the Silver Arrow opening, and repeats
  that instruction when players look at him.
- Lowered Hyrule's required Silver Arrow from the immortal-only level 68 range
  to the maximum mortal level 59, restoring a mortal path to defeating Ganon.
- Fixed paged commands exposing raw `{0D` color tokens instead of terminal
  colors, and compacted the achievement summary into paired category columns
  so its normal overview fits within the default page length.
- Fixed Telekinesis bypassing take, corpse-looting, bound quest-item, and
  no-teleport rules; Confuse requiring 139 mana instead of its actual cost;
  Clairvoyance counting remote views as physical exploration; astral travel
  charging before target validation; and Project possessing the wrong ghost.
- Fixed Enervate healing from resisted damage, empty or duplicate defensive
  casts consuming full mana, Transfusion allowing ineffective casts without
  lag or skill improvement, and invalid `grantpsi` lists unlocking no powers.
- Fixed psionic special mobiles overwhelmingly selecting Torment, restored
  reliable self-defense casting, and added fair use of newer combat powers.
- Reworked automatic quests to choose suitable live targets, credit nearby
  group members and pet-assisted kills, accept turn-ins at any questmaster,
  bind and clean up recovery tokens, find tokens inside containers, and save
  cooldown and timeout transitions immediately. Protected service mobiles,
  explicitly unkillable targets, and ghosts are no longer selected.
- Fixed active-quest logout preserving streaks, heroes being unable to abort,
  object quests having a different cooldown, practice rewards disagreeing with
  their advertised range, malformed gamble percentages, reward additions
  overflowing the quest-point balance, and remort preserving a high-level
  quest after returning the player to level 3.
- Replaced the quest shop's mislabeled translucent-key "trophy" with a real
  questmaster keepsake, hardened missing reward prototypes, and added quest
  achievements for 250 completions, a 25-win streak, rushes, final-minute
  turn-ins, gamble wins, and acquiring the keepsake.
- Fixed `lore` allowing negative research fees to pay repeatable gold, omitting
  its value estimate, hiding later spells, and miscalculating negative affects
  and weapon averages.
- Fixed Raise Dead destroying belongings the revived player could not carry,
  ambiguous player matching, and unsaved recoveries; heavy items now remain in
  the corpse and the spell requires the exact online owner.
- Fixed soul trapping overlooking later empty bottles, unsaved soul capture and
  release, Water Burst wasting all water, Geyser destroying its container, and
  Transfusion allowing its user to remain standing at zero hit points.
- Kept skeletons, wraiths, and vampires charmed for their full summoned lives,
  rather than allowing them to roam uncontrolled after an early charm expiry.
- Fixed multi-race equipment being wearable by no race, repaired the slots and
  advertised powers of five signature relics, and preserved invisibility,
  detect-invisibility, and flight when another worn, racial, or spell source
  still grants the effect.
- Prevented pending automatic-quest gamble rewards from being overwritten,
  bounded practice and quest-streak rewards, persisted quest state promptly,
  cleared rush state on abort, and allowed the hero experience exchange at the
  exact required experience threshold.
- Fixed fire, frost, and death-shroud shield state checks so mutually exclusive
  shields cannot stack, and capped energy-drain healing at maximum hit points.
- Made `concoct` and `scribe` recipes ingredient-order independent, removed
  failed-craft object leaks, preserved ingredients for unknown recipes, saved
  consumed rare components immediately, and corrected their player help.
- Fixed stale seasonal-vendor pointers that could crash timed despawns, restored
  event-boss defeat announcements, moved holiday rewards into corpses, and
  guaranteed each event boss awards at least one primary rare item.
- Bounded Hero Quest item lookups, saved each recovered relic, removed temporary
  magic immunity and no-follow state on every exit, and safely floored abandon
  penalties while keeping current and maximum health consistent.
- Fixed death ray falsely announcing Ganon's death before his protected reform,
  and documented the permanent training reward on the two rare holiday foods.
- Fixed the advertised quest-shop Potion of Power, Potion of the Giant, and
  Scroll of Farslay never appearing in `AQUEST LIST` or being purchasable.
- Fixed Farslay scrolls consuming themselves without a target, leaking or
  removing the reader's holy-light setting, and resolving duplicate Farslay
  slots as repeated deaths and permanent penalties.
- Bounded Farslay's permanent resource and attribute costs, protected NPC
  casters from player-data access, and stopped protected Ganon attempts from
  falsely announcing and logging his death.
- Fixed Herbie's automatic rescue choosing an arbitrary wounded player due to
  integer division, being blocked by invalid or link-dead candidates, moving
  away while fighting, flooding recipients with hundreds of heal messages,
  and returning to a hard-coded room instead of his actual origin.
- Fixed ordinary seasonal candy corn and spiced cider using the rare training-
  food type, which let inexpensive vendor snacks grant permanent trains.
- Prevented training-food rewards from overflowing the 16-bit train counter,
  saved them immediately after consumption, corrected their displayed type,
  and exposed the type accurately in the web area browser.
- Fixed `remort <password> ...` and `resetpwd <player> <newpassword>` being
  registered as `LOG_ALWAYS`, which wrote plaintext password arguments to game
  logs and snoop output; added a regression test for all credential commands.
- Fixed off-hand attacks using main-hand proficiency, secondary wield bypassing
  item restrictions, and failed weapon swaps removing the equipped weapon.
- Fixed comparison estimates for off-hand proficiency, low-skill unarmed damage,
  two-handed no-remove conflicts, and engine-applied experience bonuses.
- Fixed Hyrule's inactive Raft gate, two nonlethal dead ends, mismatched armor
  slots, held Recorder use, and Recorder effects weakening unrelated NPCs.
- Fixed incorrect overworld locations for Levels 8 and 9, the White and Master
  Swords, Princess Zelda's Letter, and the Power Bracelet.
- Fixed legacy Hyrule shopkeeper vnums being shared with dungeon elders and
  combat mobiles; generated vendors now use dedicated prototypes and stock.
- Fixed dungeon maps and compasses remaining readable while blind or in darkness.
- Fixed inferred dungeon wall links by deriving all 56 First Quest bomb walls
  from the paired NESMaps room markers, including Death Mountain's 19 pairs.
- Fixed single-item gear comparisons matching unrelated worn objects through
  the universal `ITEM_TAKE` flag instead of an actual shared equipment slot.
- Fixed the CMake/C17 build using unavailable BSD `strlcpy`/`strlcat` calls
  instead of the repository's portable bounded string helpers.
- Fixed the PowerShell startup smoke test treating a healthy timeout-driven
  server shutdown as a validation failure.
- Fixed Unix game-loop web-admin queue processing so queued dashboard actions are handled on Linux/Docker builds.
- Fixed a web-admin queue race that could lose actions appended while the game loop read and deleted the queue file.
- Fixed player saves reporting success and creating snapshots after failed writes or failed atomic replacement.
- Fixed player restore overwriting the live file before its snapshot copy completed; restores now force a pre-change snapshot and atomically replace from a temporary file.
- Fixed null-stream crashes in corpse history and `areasave` failure paths, and bounded corpse-history item counts read from disk.
- Fixed shared text readers hanging or mishandling EOF when a data file ends without a newline.
- Fixed repeated area-parser and wizlist loads retaining stale state or using an invalid list tail.
- Fixed stale review/documentation notes for the previously resolved `areaload` double-close and flood movement checks.

---

## [2026.04 (April 2026)] — Area Content & Stability

### Fixed — Spelling & Grammar in World Files (Rounds 1–30)

A comprehensive audit of all 132 `.are` files was performed, correcting over 400 spelling, grammar, and article errors. Areas modified across all 30 rounds:

**Rounds 1–10** (various .are files):
- `alot` → `a lot` across many files
- there/their/they're errors
- `immediatly` → `immediately` (multiple areas)
- `strangly` → `strangely`
- Apostrophe errors in contractions and possessives
- Double-word errors (`the the`, `in in`, etc.)
- `erradicate` → `eradicate`
- `heros` → `heroes`

**Rounds 11–20**:
- Continued systematic scan across remaining areas
- Corrected verb agreement and pluralization errors
- Various jumbled/transposed word fixes

**Rounds 21–30** (specific, documented):
- `Round 21` — `kerofk.are`: Removed redundant `potatoe` keyword; fixed `potatoe^H` (literal backspace control character artifact)
- `Round 22` — 14 files: `forboding`→`foreboding` (nether, despair, scult, prison, abyss); `amazment`→`amazement` (gcult); `unconsious`→`unconscious` (glitter); `preperation`→`preparation` (nethril1); `beneith`→`beneath`, `pedistal`→`pedestal` (tarin); `pedastal`→`pedestal` (mountain ×2); `stalagtites`→`stalactites` (horde); `Persistant`→`Persistent` (camelot); `apparant`→`apparent` (newthalo); `boundries`→`boundaries` (world)
- `Round 23` — 9 files: `Calender`→`Calendar` (korzath2); `unfamilar`→`unfamiliar` (dresden, dresden_halloween, dresden_xmas); `equipement`→`equipment` (highland); `nonexistance`→`nonexistence` (crypt); `harrasing`→`harassing` ×4 each (limbo, limbo_xmas, limbo_halloween)
- `Round 24` — 11 files: `headress`→`headdress` ×5 (northsea), ×2 (arac); `a animal`→`an animal` (horde); `a ever/emerald/even/orderly/even/orange/object/alchemy` → `an` article fixes (valhalla, mountain, ultima, solace, commands, dresden×3)
- `Round 25` — 6 files: `a elder`→`an elder` (nether); `a iron handle`→`an iron handle` (camelot); `a oak door`→`an oak door` ×2 (solace); `a east-north`→`an east-north` (moria); `a incessant`→`an incessant` ×2 (canyon); `a everlasting`→`an everlasting` (sewer)
- `Round 26` — 7 files: `terrrifying`→`terrifying` (valhalla); `apperance`→`appearance` (ag); `Sacraficial`→`Sacrificial` ×2 (abyss); `decend`→`descend` ×4 (sea), ×1 each (nether, horde, connect)
- `Round 27` — 3 files: `parliment`→`parliament` (connect); `throught`→`through` ×6, `wich`→`which` (mid_ruin); `throught`→`through` (astral)
- `Round 28` — 4 files: `crouds`→`crowds` ×3 (limbo, limbo_xmas, limbo_halloween); `maintenence`→`maintenance` ×2 (lud)
- `Round 29` — 4 files: `inscripted`→`inscribed` ×2 (ofcol), ×1 (plains); `Dispite`→`Despite` (solace); `indiscernable`→`indiscernible` (istari); `infititely`→`infinitely` (istari)
- `Round 30` — `mid_ruin.are`: `remains fo the southern` → `remains of the southern`

---

### Added — New Content

- **`area/ashen_wastes.are`** — New grinding zone "The Ashen Wastes" (vnums 26700–26799): scorched post-apocalyptic landscape with progressive difficulty mobs and rare material drops

- **Quest shop items** — Three new items purchasable with quest points:
  - Potion of Power (+str/dex/con temporarily)
  - Potion of the Giant (+str/size)
  - Scroll of Farslay (ranged damage spell)

- **Seasonal area system** — Framework for holiday events, weather-tied spawns, and seasonal bosses:
  - `dresden_halloween.are`, `limbo_halloween.are` — Halloween variants
  - `dresden_xmas.are`, `limbo_xmas.are`, `midennir_halloween.are` — Christmas/holiday variants
  - Wandering seasonal vendors appear during events
  - Holiday area portals open/close based on in-game date

- **Pyrotechnics overhaul** — `spell_pyrotechnics` fully rewritten as a psi-class area attack with proper scaling and status effects

- **Heated gear mechanic** — Objects can gain a `heated` flag (from fire magic, traps, environment); wearing heated gear deals passive burn damage; cooling happens over time via `update.c`

### Added — Immortal Commands (11 new)

Implemented in `src/act_wiz.c`:

| Command | Level | Description |
|---------|-------|-------------|
| `mute` | L65 | Toggle all speech: sets COMM_MUTE + NOCHANNELS/NOTELL/NOSHOUT/NOEMOTE |
| `drag` | L66 | Pull any online PC to your current room |
| `duel` | L64 | Force two online PCs into PK combat (transports p2 to p1's room) |
| `weather` | L65 | Set global weather: sunny/cloudy/rain/storm |
| `lights` | L65 | Toggle ROOM_DARK flag on current room |
| `seal` | L65 | Toggle EX_WIZLOCKED on a room exit by direction |
| `finger` | L65 | Player info lookup (online: live stats; offline: saved file scan) |
| `trail` | L67 | Show last `TRAIL_LEN` rooms visited (ring buffer in `pc_data`) |
| `petrify` | L65 | Apply timed 'stone' affect blocking ALL commands |
| `empower` | L64 | Apply sanctuary + haste + fly + passdr + protect + regen + divprot + stat boosts |
| `colossus` | L64 | Apply 500% HP/mana/move boost, heal to full (`gsn_titanic` affect) |

Infrastructure changes for new commands:
- `MAX_SKILL` bumped 228 → 231
- `COMM_MUTE` added to comm flags
- `TRAIL_LEN 10` constant; `int trail[TRAIL_LEN]` + `sh_int trail_head` in `pc_data`
- `gsn_empower`, `gsn_titanic`, `gsn_petrify` globals added
- `petrify` affect blocks ALL commands in interpreter (`interp.c`)

---

### Fixed — Crash & Stability Bugs

A systematic use-after-free (UAF) and NULL-dereference audit was performed across the entire C source tree:

- **`src/fight.c`** — Fixed UAF in `damage()` autoloot block after `raw_kill`; fixed UAF in `fatality()` autoloot block
- **`src/magic.c` / `src/magic2.c`** — Fixed 7 spell bugs; chain lightning UAF (death-check each arc target); missile/skeletal_hands loop UAF
- **`src/update.c`** — Fixed `component_update()` infinite loops (random-vnum `for(;;)` loops now bounded to 200 attempts); fixed misindented `component_update()` calls in `weather_update()` causing stack corruption; fixed UAF in river room sweep; `char_update`, `dtrap_update`, `hit_gain`, `mana_gain` NULL guards
- **`src/skills.c`** — Fixed out-of-bounds and UAF in skill loops
- **`src/special.c`** — Fixed `spec_black_dragon` character scan NULL deref; fixed `spec_whine` NULL deref; fixed `spec_healer` NULL deref (`most_hurt` in-room check)
- **`src/save.c`** — Fixed NULL deref crashes in player save/load
- **`src/act_wiz.c`** — Fixed NULL deref crashes
- **`src/quest.c`** — Added `in_room` NULL guard before questmaster search in `do_quest`
- **`src/trap.c`** (via fight/update) — Fixed guardian trap UAF; fixed `do_manipulate` trap case 3 send-after-free
- **`src/magic.c`** — Restored `spell_rope_trick` which was accidentally disabled; fixed `spell_haven` infinite loop
- Fixed 5 bugs flagged by GCC static analysis (`-Wduplicated-cond`, `-Wlogical-op`, `-Wnull-dereference`)
- Fixed 3 bugs in arena/death/fight code (arena exit, death inventory handling)
- All `for(;;)` random-vnum loops bounded to max 200 attempts (prevents game freeze)

---

### Changed — Build System & Infrastructure

- **`src/act_wiz.c`**: `fgets()` magic number `80` replaced with `sizeof(arg)` for maintainability
- **`webadmin/server.py`**: Added `WEB_ADMIN_TOKEN` environment variable; mutating API endpoints now require `X-Admin-Token` header when token is set
- **`area/resolve.c`**: Moved to `archive/resolve.c` — dead code (legacy ident resolver, not compiled)
- **`webadmin/server.py`**: Removed duplicate import block (lines 13–24 were identical to lines 1–12)
- **`src/act_info.c`**: Two remaining `strcat()` calls converted to `strlcat()` with `sizeof(buf)` bounds

---

## [2025.11 (November 2025)] — String Safety & Infrastructure Overhaul

### Added — String Safety Infrastructure (PRs #11–27)

A comprehensive string safety refactor replacing all unbounded string functions (`strcpy`, `strcat`, `sprintf`) with bounded equivalents throughout the codebase:

- **`src/string_safe.c`**: New module providing OpenBSD-style `strlcpy()` and `strlcat()` implementations with guaranteed null-termination
- **`src/merc.h`**: Added `strlcpy`/`strlcat` prototypes; `UNUSED_PARAM(x)` macro for clean unused-parameter suppression; `#ifndef __APPLE__` guards for `<crypt.h>` include; modernized `bool` and integer types

**Modules converted (PR by PR):**
- `src/act_comm.c` — All `sprintf`/`strcpy`/`strcat` → `safe_strcpy`/`safe_strcat` wrappers
- `src/act_wiz.c` — Fully converted to `snprintf`/`strlcpy`/`strlcat`; `clamp_sh_int` helper for wizard-set commands
- `src/comm.c` — `safe_strcpy`/`safe_strcat` throughout; port validation before `htons`; widened descriptor handles to `int`
- `src/handler.c` — Flag/bit-name builders from repeated `strcat` → bounded `strlcat`
- `src/wizlist.c` — Formatting converted to `snprintf`
- `src/magic.c` — Fully converted; cleaned signed/unsigned comparisons; `spell_heat_metal` reorganized
- `src/act_obj.c` — `snprintf` for all formatted messages
- `src/db.c` — Area file names, socials, default room text, bug logging bounded; `fread_sh_int`/clamp helpers added
- `src/save.c` — No unsafe functions detected in audit
- `src/hunt.c` — Bounded buffer for secret-door door commands
- `src/magic2.c` — `do_lore` flow tidied; trap direction/keyword formatting capped; damage table bounds aligned
- `src/skills.c`, `src/special.c`, `src/update.c`, `src/quest.c`, `src/pkill.c` — All converted

### Added — Modern Build Systems

- **`CMakeLists.txt`** (PR #4–7): CMake build system targeting C17 standard with:
  - Explicit source file list (reproducible builds)
  - Optional AddressSanitizer + UBSanitizer via `-DENABLE_SANITIZERS=ON`
  - Output to `bin/rom` (separate from Makefile's `merc`)
  - clang-format configuration (`.clang-format`)

- **`Dockerfile`** (PR #8): Multi-stage Docker build:
  - Build stage: `debian:bookworm-slim` + build-essential + cmake
  - Runtime stage: minimal with only `libcrypt1` + Python 3 + FastAPI/uvicorn
  - Non-root `toc` user for container security
  - `EXPOSE 9000`

- **`docker-compose.yml`** (PR #3): Multi-service orchestration:
  - `game` service: MUD server on 9000/9001
  - `middleware` service: Python bridge on 8000
  - Volume mounts for `player/`, `log/`, `area/`

### Added — Network & Socket Modernization (PR #10)

- Socket handling in `src/comm.c` modernized to use POSIX-standard APIs
- `O_NONBLOCK` set via `fcntl` (replacing deprecated flags)
- `socklen_t` used consistently for address length parameters

### Added — Web Admin

- **`webadmin/server.py`**: FastAPI web administration panel:
  - `QueueWriter` class for IPC to game via `area/webadmin.queue`
  - Dashboard HTML (self-contained, no external CDN dependencies)
  - WebSocket `/ws/logs` for real-time log streaming
  - `/api/health` — checks merc and uvicorn process status
  - Player browser, area browser (mobs/objects/rooms), best gear finder
  - `docker-entrypoint.sh` starts uvicorn automatically

### Added — Setup Scripts

- `scripts/setup_windows.ps1` — Chocolatey-based Git + Docker Desktop installer
- `scripts/setup_mac.sh` — Homebrew-based installer (Intel + Apple Silicon aware)
- `scripts/setup_linux.sh` — apt-based Docker + git installer

### Fixed — Compiler Warnings

Extended warning set (`-Wall -Wextra -Wshadow -Wsign-compare -Wformat-overflow=2 -Wunused-parameter -Wstrict-prototypes -Wold-style-definition -Wmissing-prototypes -Wcast-qual`) builds cleanly:

- `UNUSED_PARAM` macro applied across all command/spell stubs
- Renamed shadowing locals in `act_wiz.c`, `comm.c`, `db.c`, `magic.c`, `save.c`, `special.c`, `update.c`
- `int_app` fixed: both `learn` and `mana_gain` fields now initialized
- `race_type` sentinel fills every field
- `hunt_victim` uses bounded buffer
- `act_new`/`act_public` const-correct; `is_name` works on local copies
- `-Wconversion` hotspots: `sh_int` clamping in `act_comm.c`, `act_info.c`, `act_move.c`, `act_obj.c`, `act_wiz.c`, `comm.c`, `db.c`, `fight.c`, `handler.c`

---

## [Initial] — 2025-11-18 (Initial Commit)

- Initial repository created from legacy ToC codebase
- 132 area files loaded and compiling
- Basic Makefile with gnu89 build flags
- Existing MUD engine code (Merc/ROM derivative with ToC customizations)

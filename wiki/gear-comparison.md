# Gear Comparison

The in-game `compare` command answers one question: which gear makes this
character hit harder? It never equips, removes or changes anything.

## Player commands

```text
compare <item>            against what you wear there, or the empty slot
compare <item-a> <item-b> two items against each other
compare upgrades [slot]   the best gear you could wear today, and where it is
compare profile           how your damage is made
compare defense ...       rank by toughness instead of damage
```

With one item, `compare` measures it against what it would replace. For a
ring, an amulet or a bracer that is the weaker of the two you wear -- the one
you would take off. If nothing is worn there it measures against the empty
slot.

## How it ranks

Every comparison puts the item on in place of what is in the slot, keeps the
rest of the character exactly as they stand, and measures two numbers.

- **Damage.** For weapons: damage per round, walked through `multi_hit` and
  `one_hit` -- two swings, haste, second and third attack, dual wield, a
  saurian's tail, the d20 hit roll against an equal-level mobile's armour,
  weapon dice, enhanced damage, weapon flags, damroll and strength. Backstab,
  smite and fists of fury count for a fifth, as openers and occasional
  bursts. For spells: mana to cast with, the pool plus four ticks of
  `mana_gain` regeneration, because every spell is cast at the caster's level
  and gear only changes how many casts there are. A character's damage is
  split between the two by class (mage and necromancer 85% spells, cleric
  50%, monk 15%, thief and warrior none), leaning 30% toward the guild, and
  is all weapons for anyone who knows no attack spell.
- **Toughness.** Effective hit points against an equal-level opponent: hp,
  armour turning blows aside and softening the rest, dodge, parry, shield
  block, sanctuary, divine protection, saves against the half of the damage
  that is magic, and the Hyrule relic wards.

The score is the damage change plus a quarter of the toughness change. A big
hp bump can still beat a marginal damage gain; an ordinary one cannot. Under
half a percent is a tie. `compare defense` ranks by toughness alone.

Hitroll helps only until you land 95% of your swings, which is the most the
d20 allows; past that it shows as a change on the score sheet and nothing in
the damage row. That is the model being honest, not a bug.

## Reading a result

```text
A) Starlight (level 45)
B) the blue war banner of Persante of Inde (level 35), worn
Slot: light.  Your damage comes from weapons.
                           A         B
  Weapon dmg/round     246.7     244.3   A +1.0%
  Toughness            14713     14300   A +2.9%
A instead of B: hit +1, dam +1, mana -20, move -40, save -2.
Verdict: A, Starlight -- 1.0% more damage, 2.9% tougher.
```

The "instead" line lists every number on the score sheet that moves, so the
verdict can be checked against `identify`. Items you cannot use yet are still
measured, and the verdict says why you cannot (level, alignment, race,
weight, dual wield, two-handed conflicts, a cursed item that will not come
off).

## Upgrades

`compare upgrades` walks every reset in the world for gear a mobile carries,
wears or sells, or a chest holds, puts each piece through the same
measurement in place of what you wear, and keeps the ones that win. Only
what you could put on today counts:

- Your level, race (the race flags name everyone an item suits, as WEAR reads
  them), alignment, strength for a weapon, and the off-hand rules.
- An item goes only to the slot WEAR would put it in: the first of its wear
  flags in `wear_obj`'s order, and a light is always a light.
- A level -1 prototype comes out at its carrier's level less two (a
  shopkeeper's by item type), capped at 52, with weapon dice and armour to
  match, exactly as `reset_area` and `create_object` make it.
- A `P` reset counts too: an object put into a chest that lies in a room
  you may enter, when the chest is unlocked or its key can itself be had.
  A level -1 object in a chest is left out, since its level comes from
  whatever loads the chest.
- Not listed: rot-death gear, which crumbles after the kill; inventory-flagged
  gear on anyone but a shopkeeper, which goes with the corpse; anything in a
  gods-only or implementor-only room; and Mud School past newbie level.
- A Hyrule guardian's drop table and Ganon's relics are listed too, though no
  reset places them: three pieces of a guardian's table fall each kill, and
  one of Ganon's three relics. The source line says so: "dropped by
  Aquamentus in Level 1: Hall of Threefold Scorches, Hyrule: about 3 kills in
  11". COMPARE does not say what the way to the guardian needs.

The website's Gear Finder (`get_best_gear` in `webadmin/server.py`) applies
the same rules to the parsed world -- carriers, shopkeepers and chests whose
key can be had -- and also counts a chest a mobile carries, and leaves out a
locked, keyless, pickproof chest nobody can open. It lists more of what a
death makes, from `webadmin/gear_drops.py`, which mirrors the C that makes
it (held to it by `tests/test_gear_drop_sources.py`): each guardian drop
with what the way to the guardian needs (the previous Triforce piece, the
tool for its chamber, the Silver Arrow for Ganon), the boomerangs a cleared
Hyrule room lays out, the holiday bosses' drops and Midsummer's firework
while their holiday is on, and the black market's rarities with their odds.
It weighs gear with fixed weights per class and level, where `compare
upgrades` knows the character -- skills, stats and current kit -- so the
two agree on what counts as gear, not always on which piece is best.

## Limits

The benchmark is an equal-level standard opponent. A particular enemy's
damage type, resistances, armour, special attacks or fight length can change
the practical winner. `dummy` in the training yard measures what you actually
do.

The implementation lives in `src/gear_compare.c`; the website finder is
`get_best_gear` in `webadmin/server.py`.

## Related Documentation

- [Player Guide](player-guide.md)
- [Player Command Reference](player-command-reference.md)
- [Developer Guide](developer-guide.md)

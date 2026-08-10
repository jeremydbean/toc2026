# Advanced Gear Comparison

The in-game `compare` command evaluates gear as part of the player's complete
loadout. It does not equip, remove, identify, or otherwise change either item.

## Player commands

```text
compare <item>
compare <item-a> <item-b>
compare <focus> <item> [item]
compare profile
```

With one item, the game finds the currently equipped item in the same exact
slot. Two explicitly named items must compete for a common slot. Valid focuses
are `overall`, `damage`, `spells`, `defense`, `leveling`, and `utility`.

`compare profile` displays the inferred playstyle and percentage priority mix.
The profile is rebuilt on every command, so it follows changes to the player's
level, primary class, guild, learned spells, weapon proficiencies, and trained
skills.

## What the categories mean

- **Weapon damage** estimates damage per combat round against the standard
  armor class for an equal-level opponent. It includes weapon dice, hitroll,
  damroll, strength, proficiency, haste, second and third attacks, dual wield,
  enhanced damage, backstab, smite, and fists of fury where usable.
- **Spellcasting** is a readiness estimate, not a promise of spell damage. It
  combines maximum mana, mana recovery, intelligence learning, wisdom
  practices, and the importance of spells in the inferred profile.
- **Survivability** estimates effective hit points using maximum hp, armor hit
  avoidance, armor damage reduction, saves, regeneration, immunities, parry,
  dodge, shield block, sanctuary, and divine protection.
- **Leveling** combines combat pace, survival, recovery, movement, skill
  learning, and the positive `APPLY_EXP` bonus the engine applies to gains.
- **Utility** values movement capacity and recovery, dexterity, constitution,
  immunities, flight, invisibility, and detect invisibility.

The overall recommendation normalizes each category against the loadout with
the compared slot empty, then combines them using the displayed player-profile
priorities. A focused comparison uses the selected category for its final
recommendation and still reports overall fit.

## Reading a result

`A +12.4%` means loadout A's estimate for that row is 12.4 percent higher than
loadout B's estimate. The projected loadouts also show hitroll, damroll, hp,
mana, movement, average armor class, saving throw, XP bonus, weapon skill, and
all five current stats so the reason is inspectable.

Items above the player's level are still modeled, but are marked theoretical.
The command also checks heated or damaged gear, alignment and race gates,
weapon weight, no-remove conflicts, two-handed conflicts, and the game's
special restrictions on secondary weapons.

## Limits of the estimate

The combat benchmark is an equal-level standard opponent and a five-round
fight. A particular enemy's damage type, resistances, vulnerabilities, armor,
special attacks, or fight length can change the practical winner. The command
therefore presents category estimates and underlying loadout facts instead of
hiding the decision behind one universal item score.

The implementation lives in `src/gear_compare.c`; the command registration and
public function declaration remain in `src/interp.c` and `src/interp.h`.

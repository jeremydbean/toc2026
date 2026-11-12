# Weapon type flags — findings and implementation

Status: **implemented.** See `one_hit` in `src/fight.c` and
`gear_weapon_flag_multiplier` in `src/gear_compare.c`.

Raised by a review as "flaming and frost weapon flags have no combat effect."
That was correct, and the scope turned out to be wider than flaming and frost.

## What was broken

`merc.h` defines six weapon type flags in `value[4]`. Before this change, five
of the six were referenced in exactly two places: their `merc.h` defines and
the flag-to-string list in `weapon_bit_name` (`handler.c:3169`). `one_hit`
derived its damage type solely from `wield->value[3]` via `attack_table`
(`fight.c:694-712`) and never looked at `value[4]`.

Measured across `area/*.are` (623 `ITEM_WEAPON` objects):

```
flaming      30 weapons     frost        14 weapons
vampiric     20 weapons     sharp        79 weapons
vorpal       34 weapons     two_hands    67 weapons  (already worked)

135 of 623 weapons (22%) carried at least one inert flag, across 34 area files.
```

Examples: the Master Sword (`hyrule.are` #30200, `AD` = flaming + sharp), the
Flamberge (#9921, `ACE`), Frostbite (#29922), the Sword of Winter (#4502).

## Framing: content gap, not player deception

Worth recording, because it set the priority. The flags were never visible to
ordinary players:

- `weapon_bit_name` has exactly one caller: `do_ostat` (`act_wiz.c:1836`), an
  immortal command.
- `spell_identify`'s `ITEM_WEAPON` branch (`magic.c:3278`) prints weapon class
  and damage dice only — it never prints `value[4]`.
- `gear_compare` read `value[4]` only for `WEAPON_TWO_HANDS`, so `compare` was
  *consistent* with combat here. Unlike the damroll ordering bug fixed in the
  same pass, there was no compare-vs-combat mismatch.

So nobody was being shown a "flaming" label that did nothing. The real cost was
that builders had been authoring flags with design intent across 135 weapons and
getting nothing, while item names and descriptions ("Frostbite", "the
Flamberge", the Master Sword's golden light) promised behavior the code did not
deliver.

## Approach

Everything needed already existed. `damage()` routes `dam_type` through
`check_immune` (`fight.c:1077`) for immune/resistant/vulnerable, and already
honors the `AFF2_FLAMING_HOT` / `AFF2_FLAMING_COLD` shields at `fight.c:1066`.
`DAM_FIRE`, `DAM_COLD`, and `DAM_NEGATIVE` were all defined.

**Stock ROM's structure was deliberately not copied.** Stock applies weapon
effects as *secondary* `damage()` calls after the primary one. That is unsafe
here:

- `damage()` does not return a clean "victim is still alive" signal — it
  returns `true` on the divine-protection save path (`fight.c:1277`) and
  `false` on several non-death paths.
- `raw_kill` can free the victim struct; `fight.c:1383` already carries the
  comment *"pre-save before raw_kill may free the victim struct"*, and recent
  history (`ab87c73`, `21d5c1d`) is segfault fixes in exactly this area.

A second `damage()` call on a possibly-extracted victim would reintroduce that
bug class. Instead each flag's contribution is **folded into `dam` before the
single existing `damage()` call**, with the elemental flags also rewriting
`dam_type`. One damage path, immunity and resistance handling for free, and no
way to touch a freed victim.

Insertion point: after the smite block and before
`dam += GET_DAMROLL(ch)`, guarded on `wield != NULL`. Placing it before damroll
means an enchantment scales with the weapon's own dice rather than with the
wielder's damroll gear — deliberate, so high-damroll characters don't extract
extra value from every flagged weapon.

## What each flag now does

| Flag | Effect |
|---|---|
| `WEAPON_FLAMING` | `dam += dam/10`; converts a physical damage school to `DAM_FIRE` |
| `WEAPON_FROST` | `dam += dam/10`; converts a physical damage school to `DAM_COLD` |
| `WEAPON_VAMPIRIC` | `dam += dam/10`; heals wielder `dam/20` capped at `max_hit`; PCs lose 1 alignment per hit |
| `WEAPON_SHARP` | `number_percent() <= skill/8` (≤12% at 100 skill) doubles `dam`, with a message |
| `WEAPON_VORPAL` | `number_percent() <= skill/20` (≤5% at 100 skill) triples `dam`, with a message |

Notes on the choices:

- **Elemental exclusivity.** Both elemental flags add damage, but each only
  converts a *physical* school, so on a weapon flagged both ways (#25022 A
  Dwarven Hammer, #29250 Starlight Sword) flaming wins the school and frost
  still contributes its damage. Deterministic, no ordering surprise.
- **Vampiric does not change the damage school.** Draining via `DAM_NEGATIVE`
  would let negative-energy immunity defeat the weapon entirely. The drain and
  the alignment drift are the mechanic; the damage stays whatever the weapon
  normally deals.
- **Vorpal.** This flag has no stock ROM meaning and no precedent here, so the
  design was a judgment call: it is a rare, spiky damage multiplier, **not** an
  instant kill or decapitation. An instant-kill proc on 34 weapons is a PK
  balance event that should not arrive as a side effect of a bug fix. Sharp is
  frequent-and-modest, vorpal is rare-and-large; expected contributions are
  comparable (~12% vs ~10% at 100 skill) but vorpal has much higher variance.
  Revisit if you want it to be genuinely lethal.
- **Message volume.** Only the sharp and vorpal procs emit `act()` text. The
  three continuous effects fire on every hit and would flood combat scroll; they
  show up in damage numbers and damage type instead.

## `compare` was updated in the same pass

`gear_weapon_flag_multiplier` in `gear_compare.c` mirrors the expected value of
the block above, applied inside `gear_weapon_base_damage`. Without it `compare`
would have started *under*valuing 22% of weapons — the mirror image of the
damroll bug fixed alongside this.

Because enhanced damage and the flag bonuses are both multiplicative, folding
the flags into the dice term is equivalent to combat's ordering and keeps
damroll outside both. The integer proc thresholds (`skill/8`, `skill/20`) are
reproduced deliberately so the estimator tracks the real thresholds rather than
a rounded approximation.

Not modelled: vampiric's self-heal is not credited to the survival metric. It is
worth `dam/20` per landed hit and arguably belongs there; left out to keep this
change scoped to damage.

## Balance risk — read before deploying

This is a live power increase for 22% of weapons at once, concentrated in the
high-end areas (`valhalla`, `limbo`, `astral`, `emerald`). Stacked flags
compound: the Flamberge is `ACE` (flaming + vampiric + vorpal), so roughly
+21% continuous plus a 5% triple-damage proc.

If that is too much to land in one step, the flags are independent `if` blocks
and can be commented out individually; flaming and frost alone are the smallest
blast radius (44 weapons) and the most clearly intended.

## Test coverage caveat

The existing suite (`tests/*.py`, 21 tests) parses area files in Python and
cannot exercise C combat code. This change is verified by compilation and
inspection only. It needs in-game testing — a flagged weapon of each type
against a target with matching immunity and without.

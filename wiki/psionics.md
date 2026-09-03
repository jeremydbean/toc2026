# Psionics Guide

Psionics are remort powers that use mana rather than spell slots. Characters
unlock them beginning at remort 2. Remorts 2 through 4 grant one random power
from each discipline, for four powers total. The final remort grants all 17.
Use `skills` to see which powers the current character knows and `help
<power>` for live syntax.

## Disciplines

| Discipline | Powers |
|---|---|
| Assault | Ego Whip, Torment, Nightmare, Mindblast |
| Astral | Astral Walk, Shift, Project, Telekinesis |
| Defense | Mindbar, Psionic Armor, Psychic Shield, Transfusion |
| Control | Clairvoyance, Confuse, Mind Leech, Enervate, Pyrotechnics |

## Power Reference

| Power | Level | Cost | What it does |
|---|---:|---:|---|
| Psionic Armor (`psionic`) | 17 | 20 mana | Gives one room target 25% mental-damage reduction. |
| Clairvoyance | 18 | 25 mana | Shows a remote character's room without moving the user. |
| Torment | 18 | 20 mana | Deals single-target mental damage. |
| Ego Whip (`ego`) | 19 | 20 mana | Deals mental damage and may temporarily reduce one physical or mental stat. |
| Project | 19 | 25 mana | Sends an astral scout through several rooms in one direction. |
| Psychic Shield (`psychic`) | 19 | 50 mana | Gives eligible group members in the room 25% mental-damage reduction. |
| Pyrotechnics | 20 | 20 mana | Deals vitality-scaled fire damage and may temporarily heat worn gear. |
| Confuse | 21 | level + 50 mana | Makes a target intermittently lose combat actions. Lands whenever the caster keeps concentration, unless the target is immune or resistant to mental damage. |
| Nightmare | 21 | 20 mana | Reduces maximum mana and prevents normal recovery until cured or expired. |
| Enervate | 21 | 35 mana | Drains health and movement and returns part of the actual drain to the user. Blocked by mental immunity, halved by mental resistance. |
| Telekinesis (`tk`) | 21 | 50 mana | Retrieves an eligible ground item from elsewhere in the world. Gated on full skill; the full cost is charged only on a successful retrieval. |
| Mindbar | 22 | 50 mana | Gives the user 50% mental-damage reduction. |
| Mind Leech (`mindleech`) | 22 | 30 mana | Drains mana and restores half; deals mental damage to a target with no mana. Blocked by mental immunity, halved by mental resistance. |
| Mindblast | 23 | 50 mana | Deals mental damage to every attackable target in the room. |
| Astral Walk (`astral`) | 25 | 70 mana | Moves the user and a present pet to another character. Blocked by a target's mental immunity; leaves the caster stunned on arrival. |
| Shift | 25 | 70 mana | Pulls a non-fighting character to the user. Leaves the caster stunned. |
| Transfusion | 28 | 20 mana and 50 health | Gives up to 50 health to another injured character. |

## Defense Rules

Mindbar, Psionic Armor, and Psychic Shield are mutually exclusive. Armor and
Shield reduce mental damage by one quarter; Mindbar reduces it by one half.
They do not reduce physical or elemental damage. Mental saves can separately
reduce or prevent powers such as Nightmare, Mind Leech, Enervate, Torment,
and Ego Whip.

Confuse, Mind Leech, and Enervate deliberately do not use the generic
saving-throw curve. Their only caster-side gate is the skill roll, so a psion
at 100% never loses concentration. Target-side, they consult mental immunity
and resistance (`DAM_MENTAL`) through the shared `psionic_ward_check()`
helper instead:

| Target ward | Confuse | Mind Leech / Enervate |
|---|---|---|
| Immune to mental damage (`IMM_MENTAL`, or `IMM_MAGIC`) | Never confused | Nothing drained |
| Resistant to mental damage (`RES_MENTAL`, or `RES_MAGIC`) | One bounded resist roll: 25% base, shifted by the level difference, clamped to 5-50%; on a success the power is blocked | Same roll; on a success the drain is halved |
| Normal or vulnerable | Always confused | Full drain |

Astral Walk uses the same ward check when the target is a mobile: an
immune mind cannot be fixed upon, a resistant one may shrug off the pull,
and an ordinary one cannot resist. It previously used `saves_spell()`,
which meant a mastered Astral Walk could not reach the high-level targets
it exists to reach.

Mindbar, Psionic Armor, and Psychic Shield still apply on top of a drain
through `psionic_reduce_mental_drain()`, so a warded and shielded target
benefits from both.

The generic `saves_spell()` curve clamps to a 95% resist rate against the
negative saving throws most mobiles carry, which is why these powers do not
use it. Tune the shared resist band with `PSI_RESIST_BASE`,
`PSI_RESIST_MIN`, and `PSI_RESIST_MAX` in `src/magic2.c`.

## Travel And Retrieval Safety

Astral Walk and Shift deliberately leave the caster `POS_STUNNED`, cleared
on the next `char_update()` tick. This is balance, not an oversight: it
denies the caster a free opening turn so neither power can be used to jump
a player and act first. Do not soften it without solving that abuse.

Telekinesis is gated on the caster's full learned percentage. It used to
roll against `chance / 2`, which capped it at a 50% success rate even at
100% skill. It also charged its full 50 mana before searching, so a
mistyped name cost a full casting; the full cost is now charged only when
an item is actually retrieved.

Astral Walk, Shift, Project, Clairvoyance, and Telekinesis respect private,
staff-only, death-trap, jail, and no-teleport rooms as appropriate. Teleporting
and item retrieval also respect no-recall rooms. Telekinesis can retrieve only
visible, takeable ground objects and preserves normal carry, corpse-looting,
quest ownership, NOLOCATE, and NO_TPORT restrictions.

## Immortal Granting

Level 70 administrators can use:

```text
grantpsi <player> [now] [skill1,skill2,...]
```

Without a list, normal remort selection rules apply. With a list, names must
be valid and comma-separated; invalid or empty selections are rejected. The
`now` option grants immediately instead of waiting for the next level check.

See also: [Player Guide](player-guide.md), [Player Command Reference](player-command-reference.md)

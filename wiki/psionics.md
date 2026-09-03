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
| Enervate | 21 | 35 mana | Drains health and movement and returns part of the actual drain to the user. |
| Telekinesis (`tk`) | 21 | 50 mana | Retrieves an eligible ground item from elsewhere in the world. |
| Mindbar | 22 | 50 mana | Gives the user 50% mental-damage reduction. |
| Mind Leech (`mindleech`) | 22 | 30 mana | Drains mana and restores half; deals mental damage to a target with no mana. |
| Mindblast | 23 | 50 mana | Deals mental damage to every attackable target in the room. |
| Astral Walk (`astral`) | 25 | 70 mana | Moves the user and a present pet to another character. |
| Shift | 25 | 70 mana | Pulls a non-fighting character to the user. |
| Transfusion | 28 | 20 mana and 50 health | Gives up to 50 health to another injured character. |

## Defense Rules

Mindbar, Psionic Armor, and Psychic Shield are mutually exclusive. Armor and
Shield reduce mental damage by one quarter; Mindbar reduces it by one half.
They do not reduce physical or elemental damage. Mental saves can separately
reduce or prevent powers such as Nightmare, Mind Leech, Enervate, Torment,
and Ego Whip.

Confuse deliberately does not use the generic saving-throw curve. Its only
caster-side gate is the skill roll, so a psion at 100% Confuse never loses
concentration. Target-side, the power consults mental immunity and
resistance (`DAM_MENTAL`) instead:

| Target ward | Result |
|---|---|
| Immune to mental damage (`IMM_MENTAL`, or `IMM_MAGIC`) | Never confused |
| Resistant to mental damage (`RES_MENTAL`, or `RES_MAGIC`) | One bounded resist roll: 25% base, shifted by the level difference, clamped to 5-50% |
| Normal or vulnerable | Always confused |

The generic `saves_spell()` curve clamps to a 95% resist rate against the
negative saving throws most mobiles carry, which is why it is not used for
this power. Tune the resist band with `CONFUSE_RESIST_BASE`,
`CONFUSE_RESIST_MIN`, and `CONFUSE_RESIST_MAX` in `src/magic2.c`.

## Travel And Retrieval Safety

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

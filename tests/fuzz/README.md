# Fuzzing the file readers

Every serious bug of late was in a reader: duplicate `#PET` and `Trap`
records, numbers past their type, a second `Nest`. These are libFuzzer
targets, built with AddressSanitizer and UndefinedBehaviorSanitizer, that
feed the game's own readers arbitrary bytes.

| target | what it reads | oracle beyond ASan/UBSan |
| --- | --- | --- |
| `fuzz_numparse` | `src/numparse.c`: `parse_int`, `parse_long`, `digit_append`, the checked sums | an independent 128-bit reference must agree exactly |
| `fuzz_player` | a player file through `offline_player_load` -> `load_char_obj` (`fread_char`, `fread_obj`, `fread_pet`, `#STASH`, the Nest and container checks, `revive_at_load`, `unwear_illegal_at_load`), in a booted copy of the world | `exit()` while reading is a crash (a player file refuses that character, never the game); after `extract_char` no player is left in the character list; a file the loader accepted, saved by the game's writer, must load again (`TOC_FUZZ_ROUNDTRIP=0` turns that off); LeakSanitizer -- per input until the game's own global state grows (journals, indexes), when libFuzzer turns that off and the run's end still checks |
| `fuzz_area` | one extra area file at boot: `load_area_file` and every section loader (`#AREA`, `#AREADATA`, `#HELPS`, `#MOBILES`, `#OBJECTS`, `#RESETS`, `#ROOMS`, `#SHOPS`, `#SOCIALS`, `#SPECIALS`), then `fix_exits` and `fix_reset_room_limits` | a malformed file must stop the boot cleanly (`exit`), never crash, read out of bounds or hang (`-timeout=10`) |

## Running

From the repository root (Linux; clang with libFuzzer -- on Ubuntu
`apt-get install clang libclang-rt-18-dev`):

```bash
tests/fuzz/build.sh                  # build-fuzz/fuzz_{numparse,player,area}
tests/fuzz/run.sh player 900         # fuzz for 15 minutes
tests/fuzz/run.sh area 900
tests/fuzz/run.sh numparse 300
```

`run.sh` keeps its working corpus in `build-fuzz/work/<target>/corpus`
(started from `tests/fuzz/corpus/<target>`) and puts any finding in
`build-fuzz/work/<target>/artifacts/`, then replays it with the report
showing. To replay one input yourself, pass it to the binary by an
**absolute** path (the harness changes directory into its world):

```bash
build-fuzz/fuzz_player "$PWD/build-fuzz/work/player/artifacts/crash-..."
build-fuzz/fuzz_area -detect_leaks=0 "$PWD/tests/fuzz/regressions/area/hang-cut-mid-string.are"
TOC_FUZZ_VERBOSE=1 build-fuzz/fuzz_area -detect_leaks=0 "$PWD/tests/fuzz/corpus/area/synthetic.are"
```

`TOC_FUZZ_VERBOSE=1` makes the area target say whether each input loaded
whole or would stop the boot -- the check that a seed is a good one.
`TOC_FUZZ_KEEP=1` leaves the disposable world (`/dev/shm/tocfuzz-<pid>`,
or under `TOC_FUZZ_DIR`) behind to look at.

`tests/test_fuzz_smoke.py` builds the targets, replays everything in
`tests/fuzz/regressions/`, and fuzzes each target for a fixed number of inputs
from a fixed seed (`-seed=1 -runs=N`; `TOC_FUZZ_SMOKE_SCALE` multiplies
them), so CI cannot fail on luck -- the real search is `run.sh`'s. CI
installs the toolchain on the shard that runs it. `tests/test_fuzz_findings.py` holds each finding to the real game
(`--check-area` and live logins), with no fuzzer needed.

## How the harness works

- **A fuzz build of the game.** `build.sh` compiles every `src/*.c` again
  with clang, `-fsanitize=address,undefined,fuzzer-no-link
  -fno-sanitize-recover=undefined` and `-DTOC_FUZZ`, renames `comm.c`'s
  `main` for libFuzzer's, and links with `-Wl,--wrap=exit`. `TOC_FUZZ` adds
  only `fuzz_world_mark`/`fuzz_world_rewind` to `db.c`; neither the Makefile
  nor CMake defines it, so the game is unchanged.
- **A disposable world** (`fuzz_world.c`): `/dev/shm/tocfuzz-<pid>` with a
  copy of the repository's area files (code -- never `player/`, `gods/`,
  `heroes/` or `log/`), booted once per process with `boot_db`. The player
  target boots the whole world, so object and pet vnums mean what they do
  in play; the area target boots an empty `area.lst`.
- **exit() is wrapped.** The area loaders exit on a malformed file -- the
  boot fails fast, by design -- so the area target's `__wrap_exit` longjmps
  back to the harness. The player target's turns any exit into `abort()`:
  in play it would have stopped the game. `fread_player_trap`, armed by
  `load_char_obj` itself, is what catches a malformed value in a player
  file, exactly as in the game.
- **The area target takes each input back out.** Every loader adds by
  prepending to a hash chain or appending to a list, so `fuzz_world_mark`
  saves the heads and tails after boot and `fuzz_world_rewind` puts them
  back after every input, zeroing and reusing the permanent memory and
  string space the input used. A new global a loader writes must be added
  there, or inputs start meeting each other's records. Leak detection is
  off for this target: boot strings are never freed, on purpose.

## Seeds and dictionaries

Synthetic only. `tests/fuzz/corpus/player/` is made by `python3
tests/fuzz/make_seeds.py` (after `make`): a character created and saved by the
game in a throwaway world, then given things, plus a `#PET` and `#STASH`
record in the writer's shape. `tests/fuzz/corpus/area/` is the test fixture area
and `synthetic.are`, which has every section and record kind (an M-style
mobile, F/A/E/T object records, teleport, river and affected rooms, doors,
every reset letter, a shop, a special, helps, socials, `#AREADATA`).
`python3 tests/fuzz/make_dict.py` writes `tests/fuzz/dict/`, the player dictionary
straight from the keys `src/save.c` matches.

## What it found (2026-11-12)

About an hour of the player target (some 2.2 million inputs, at 100 to
700 a second: every input loads, extracts, saves and reloads a character
in the whole world), 45 minutes of the area target (about 17 million, at
7,000 a second) and five of the number parser (155 million), restarted
after each fix; the last runs of each -- ten minutes of the player target,
ten and fifteen of the area target -- found nothing more. Each finding is fixed and has a test that fails
on the old code (`tests/test_fuzz_findings.py`; the input is in
`tests/fuzz/regressions/`):

| input | what happened | fix |
| --- | --- | --- |
| an area file cut off mid-string, no final newline | **the boot hung**: `bug()` counts lines with `while (getc(fp) != '\n')`, which never ends at EOF | `bug()` stops counting at EOF |
| a potion, scroll, pill, wand or staff naming a spell slot no spell has | `slot_lookup` `abort()`ed the boot -- a core dump, not the clean stop every other malformed record gets | `exit(1)` after the bug line |
| a room affect type outside 0-3 | `room_aff_type[type]` read before or past the table | `load_rooms` refuses it |
| a door (`D`) reset naming a negative room | **the boot crashed**: `get_room_index` answers NULL for a negative vnum without stopping the boot, and the exit was read through it | refused like any other bad door reset |
| a `#SOCIALS` section of more than `MAX_SOCIALS` (512) | wrote past `social_table[]` (seen while writing the rewind, then confirmed by the target under ASan) | `social_add` refuses the 513th |
| a player file key this build does not know (a rollback to an older build leaves exactly that) | **the game crashed at that player's login**: `bug()` was handed the word's pointer cut to an `int`, printed with `%s`; and once that was fixed, a key holding `%n` crashed it too, since `bug()` takes its text as a format | the line is formatted first, its `%`s made `?` |
| a player file with no `Room` line, loaded offline (GRANTPSI, UNDENY, the stash) | `extract_char` refused the roomless copy, which stayed in the character list; the player's next login "reconnected" into it | `offline_player_load` places a roomless copy where a login would |
| a refused player file with a pet and no `Room` | **the game crashed** in `free_char` -> `nuke_pets` -> `stop_follower`, which asked `can_see` of a master with no room | rooms are checked before `can_see` |
| a player file whose `Act` carries bit A (`ACT_IS_NPC`); a pet's without it | the player read as a mobile with no prototype (`extract_char` read `pIndexData` through NULL; the old binary crashed at that login); the pet as a player with no `pcdata` | `fread_char` clears the bit, `fread_pet` sets it |
| a player file whose class, race or guild is outside the tables (`Cla 14`, `Race dragon`, `Gui 9`) | read past the end of `class_table` and `pc_race_table` from the first stat asked for, freeing the copy included | the character is refused (the file left as it is), and the discarded copy given values the tables hold so it can be freed |
| a `NumRemorts` of millions (or below zero) | `reset_char`'s 200 hit points a remort overflowed an `int` | refused like a bad class: no character has more remorts than there are levels |
| an alias with no name, or (in play) `ALIAS "'ZQ" LOOK` -- a name starting with a quote | the roundtrip oracle: the game saved a line (`Alias 'zq look~`, `Alias  ~`) its own reader takes out of step, so **the next login refused the character** -- a player could lock themselves out | ALIAS refuses such a name, the writer skips one, the reader drops a nameless one |
| a refused file with no `Room` whose character's strength rests on worn gear and who wields a weapon | **crashed** freeing the copy: taking off the strength item made `affect_modify` drop the weapon into no room. In play the same drop at a **quit** left a copy of the weapon -- still in the saved file -- on the floor: an item duplication | a player's things leaving the game (`extract_obj_player`) never trigger the drop, nor does a roomless character |
| an object `Cost` past `LONG_MAX / 10000` in a file from before version 4 (gold) | the multiply into copper overflowed a `long` | refused (held to the limit by a reader with no trap) |
| two `#PLAYER` records in one file | the second was read over the first; its aliases took the first's slots without freeing them | refused, like two pets |
| every load | leaked the name `load_char_obj` starts with, the first of any repeated string key, every `Race` name read, and every `capitalize()` (a fresh `str_dup` nobody freed, at every save, file path and display) | `KEYS` frees what it replaces; `capitalize` uses a ring of static buffers |
| a character's or pet's `AffD` cut short by a malformed number | the affect, not yet linked, was lost when the trap jumped | linked as soon as it is made, as an object's already was |

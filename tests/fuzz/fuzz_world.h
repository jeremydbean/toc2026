/*
 * The fuzz targets' shared harness (tests/fuzz/README.md). Not part of the game:
 * tests/fuzz/build.sh links it with the game's objects, the game's main()
 * renamed away, under libFuzzer.
 */
#ifndef FUZZ_WORLD_H
#define FUZZ_WORLD_H

#include <setjmp.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* What exit() does while an input is being read. The game's own area
   loaders exit on a malformed file -- the boot fails fast, by design --
   so the area target catches that and moves on (FUZZ_EXIT_CATCH). A
   player file must never stop the game (AGENTS.md: "A player file with a
   malformed number refuses that character, never the game"), so the
   player target treats any exit as the crash it would be (FUZZ_EXIT_ABORT). */
enum fuzz_exit_mode { FUZZ_EXIT_REAL, FUZZ_EXIT_CATCH, FUZZ_EXIT_ABORT };

extern enum fuzz_exit_mode fuzz_exit_mode;
extern jmp_buf            *fuzz_exit_trap;

/* A disposable world under /dev/shm (or $TOC_FUZZ_DIR), its area/ a copy
   of the repository's area files -- code, never player data -- and the
   working directory set to it, as the game runs. With full false the
   area.lst names nothing, and boot makes only the builder's area. Boots it. */
void fuzz_world_boot( bool full );

/* The world's root directory (holds area/, player/, log/). */
const char *fuzz_world_root( void );

/* Write bytes to a file, whole. False on failure. */
bool fuzz_write_file( const char *path, const uint8_t *data, size_t size );

#endif

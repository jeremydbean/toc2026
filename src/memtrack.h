/*
 * memtrack.h -- which addresses hold a live or quarantined character,
 * object or descriptor, answered without reading the address.
 *
 * memguard.c asks of tens of thousands of stored pointers a second whether
 * each still names something. It used to read the target's mem_magic tag,
 * which is safe only while the target is alive or held whole in
 * recycle.c's quarantine; once a block is freed (its window over, or the
 * quarantine past its cap) the read is itself a use after free (review,
 * 2026-11-12). This set is keyed by address and updated at every
 * allocation, release and free, so a check looks the address up and never
 * touches the memory it names:
 *
 *   MEMTRACK_LIVE     registered by char_data_new/obj_data_new/
 *                     descriptor_data_new, not yet released;
 *   MEMTRACK_DEAD     released to the quarantine: freed later, still whole,
 *                     its own fields safe to read until then;
 *   MEMTRACK_OTHER    registered, but as another kind -- the address was
 *                     freed and handed to something new of a different type;
 *   MEMTRACK_UNKNOWN  nothing here: freed, never ours, or a stand-in on the
 *                     stack or a static. Never to be read.
 *
 * What it cannot see: an address freed and handed to a new block of the
 * same kind reads MEMTRACK_LIVE, and a stale pointer to it is
 * indistinguishable from a fresh one by address alone. The quarantine
 * makes that unlikely inside its window, not impossible after it.
 *
 * Open addressing with linear probing and backward-shift deletion: O(1) a
 * lookup, no tombstones. No merc.h, so tests/test_memtrack.c compiles
 * exactly this file.
 */
#ifndef MEMTRACK_H
#define MEMTRACK_H

#include <stdbool.h>
#include <stddef.h>

#define MEMTRACK_UNKNOWN    0
#define MEMTRACK_LIVE       1
#define MEMTRACK_DEAD       2
#define MEMTRACK_OTHER      3

/* Kinds: any small positive numbers; recycle.c uses its Q_CHAR etc. */

/* Registers `p' as live, replacing whatever the address held before (an
   address the allocator reuses is live again). False if out of memory. */
bool    memtrack_alive      ( const void *p, int kind );
/* Marks a registered address released; false if it was not registered. */
bool    memtrack_dead       ( const void *p );
/* Forgets an address, as its block is freed. */
void    memtrack_forget     ( const void *p );
/* MEMTRACK_*, for `p' expected to be of `kind'. NULL is MEMTRACK_UNKNOWN. */
int     memtrack_state      ( const void *p, int kind );
/* Counts, for MEMCHECK. */
void    memtrack_counts     ( size_t *live, size_t *dead, size_t *capacity );

#endif

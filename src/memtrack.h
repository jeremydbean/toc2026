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
 *                     stack or a static that is not in use. Never to be read.
 *
 * Every registration gets a serial, unique for the life of the process and
 * never 0 (2026-11-12). An address freed and handed to a new block of the
 * same kind reads MEMTRACK_LIVE again, but under a new serial: a holder
 * that kept the serial beside its pointer (MEM_REF in merc.h) sees the
 * difference without reading the block. A holder that kept none cannot.
 *
 * A stand-in -- a character, object or descriptor on the stack or in a
 * static, never allocated -- is registered for as long as it is in use
 * (memtrack_standin, then memtrack_forget): it reads MEMTRACK_LIVE, but
 * memtrack_dead refuses it, so nothing ever releases or frees it.
 *
 * Open addressing with linear probing and backward-shift deletion: O(1) a
 * lookup, no tombstones. No merc.h, so tests/test_memtrack.c compiles
 * exactly this file.
 */
#ifndef MEMTRACK_H
#define MEMTRACK_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define MEMTRACK_UNKNOWN    0
#define MEMTRACK_LIVE       1
#define MEMTRACK_DEAD       2
#define MEMTRACK_OTHER      3

/* Kinds: any small positive numbers; recycle.c uses these. */
#define MEMTRACK_KIND_CHAR  1
#define MEMTRACK_KIND_OBJ   2
#define MEMTRACK_KIND_DESC  3

/* Registers `p' as live under a new serial, replacing whatever the address
   held before (an address the allocator reuses is live again, and new).
   False if out of memory. */
bool    memtrack_alive      ( const void *p, int kind );
/* Registers a stand-in as live under a new serial, marked so that
   memtrack_dead refuses it; memtrack_forget ends it. */
bool    memtrack_standin    ( const void *p, int kind );
/* Marks a registered address released; false if it was not registered,
   or is a stand-in. */
bool    memtrack_dead       ( const void *p );
/* Forgets an address, as its block is freed or its stand-in's use ends. */
void    memtrack_forget     ( const void *p );
/* MEMTRACK_*, for `p' expected to be of `kind'. NULL is MEMTRACK_UNKNOWN. */
int     memtrack_state      ( const void *p, int kind );
/* The same, with the registration's serial in *serial when the state is
   MEMTRACK_LIVE or MEMTRACK_DEAD (0 otherwise). One probe. */
int     memtrack_lookup     ( const void *p, int kind, uint64_t *serial );
/* The serial of a live registration of `kind' at `p', or 0. */
uint64_t memtrack_serial    ( const void *p, int kind );
/* True for a stand-in registered and not yet forgotten. */
bool    memtrack_is_standin ( const void *p );
/* Counts, for MEMCHECK. */
void    memtrack_counts     ( size_t *live, size_t *dead, size_t *capacity );
/* Stand-ins registered now, and ever. */
void    memtrack_standin_counts ( size_t *now, uint64_t *ever );

#endif

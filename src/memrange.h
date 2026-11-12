/*
 * memrange.h -- "is this pointer inside that block?" without comparing
 * pointers from different allocations.
 *
 * C defines <, <=, > and >= only between pointers into the same object (or
 * one past its end). free_mem asked whether a pointer lay inside one of
 * alloc_perm's blocks, and free_string/str_dup/str_perm whether a string lay
 * inside the boot string space, by comparing the pointer with the block's
 * bounds -- and the pointer is usually an ordinary heap allocation, so the
 * comparison was undefined (ASan's pointer-compare check reports it as an
 * invalid pointer pair; review, 2026-11-12). Every such question goes
 * through here: addresses are converted to uintptr_t once and compared as
 * integers, and membership is `addr - base < size` in unsigned arithmetic,
 * which cannot overflow and is false below the base.
 *
 * No merc.h, so tests/test_memrange.c compiles exactly this file under
 * -fsanitize=address,pointer-compare.
 */
#ifndef MEMRANGE_H
#define MEMRANGE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/* True when `p' lies in [base, base + size). Never compares pointers. */
bool    mem_addr_in         ( const void *p, const void *base, size_t size );

/*
 * A set of equal-sized blocks (alloc_perm's), kept sorted by address as
 * integers so membership is a binary search. Interior pointers count; a
 * pointer one past a block's end does not.
 */
typedef struct mem_block_set
{
    uintptr_t * base;       /* sorted ascending */
    int         count;
    int         size;
    size_t      block;      /* every block's length in bytes */
} MEM_BLOCK_SET;

/* Adds a block; false (and nothing changed) when memory for the index runs out. */
bool    mem_block_set_add   ( MEM_BLOCK_SET *set, const void *block );
bool    mem_block_set_has   ( const MEM_BLOCK_SET *set, const void *p );

#endif

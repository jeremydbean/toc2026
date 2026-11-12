/*
 * memrange.c -- pointer-in-block questions answered on integers; see
 * memrange.h for why. No merc.h.
 */
#include <stdlib.h>
#include "memrange.h"

bool mem_addr_in( const void *p, const void *base, size_t size )
{
    uintptr_t addr = (uintptr_t) p;
    uintptr_t from = (uintptr_t) base;

    /* Below the base wraps to a huge offset, so one test covers both ends. */
    return p != NULL && base != NULL && addr - from < (uintptr_t) size;
}

bool mem_block_set_add( MEM_BLOCK_SET *set, const void *block )
{
    uintptr_t addr = (uintptr_t) block;
    int i;

    if ( set->count == set->size )
    {
        int size = set->size > 0 ? 2 * set->size : 64;
        uintptr_t *grown = realloc( set->base, (size_t) size * sizeof(*grown) );

        if ( grown == NULL )
            return false;
        set->base = grown;
        set->size = size;
    }

    for ( i = set->count; i > 0 && set->base[i - 1] > addr; i-- )
        set->base[i] = set->base[i - 1];
    set->base[i] = addr;
    set->count++;
    return true;
}

bool mem_block_set_has( const MEM_BLOCK_SET *set, const void *p )
{
    uintptr_t addr = (uintptr_t) p;
    int lo = 0;
    int hi = set->count - 1;

    if ( p == NULL )
        return false;
    while ( lo <= hi )
    {
        int mid = lo + ( hi - lo ) / 2;
        uintptr_t base = set->base[mid];

        if ( addr < base )
            hi = mid - 1;
        else if ( addr - base >= (uintptr_t) set->block )
            lo = mid + 1;
        else
            return true;
    }
    return false;
}

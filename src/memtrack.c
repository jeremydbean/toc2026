/*
 * memtrack.c -- the address set behind char_is_live and its kin; see
 * memtrack.h. No merc.h.
 */
#include <stdint.h>
#include <stdlib.h>
#include "memtrack.h"

typedef struct
{
    uintptr_t       addr;       /* 0: empty */
    unsigned char   kind;
    unsigned char   state;      /* MEMTRACK_LIVE or MEMTRACK_DEAD */
} MT_SLOT;

static MT_SLOT *mt_table;
static size_t   mt_capacity;    /* a power of two, or 0 */
static size_t   mt_used;
static size_t   mt_dead;

static size_t mt_hash( uintptr_t addr )
{
    /* Allocations are at least 16-byte aligned: the low bits say nothing. */
    uint64_t h = (uint64_t) ( addr >> 4 ) * UINT64_C(0x9E3779B97F4A7C15);

    return (size_t) ( h >> 17 );
}

static size_t mt_find( uintptr_t addr )
{
    size_t mask = mt_capacity - 1;
    size_t i = mt_hash( addr ) & mask;

    while ( mt_table[i].addr != 0 && mt_table[i].addr != addr )
        i = ( i + 1 ) & mask;
    return i;
}

static bool mt_grow( void )
{
    size_t capacity = mt_capacity > 0 ? 2 * mt_capacity : 4096;
    MT_SLOT *old = mt_table;
    size_t old_capacity = mt_capacity;
    MT_SLOT *grown = calloc( capacity, sizeof(*grown) );
    size_t i;

    if ( grown == NULL )
        return false;
    mt_table    = grown;
    mt_capacity = capacity;
    for ( i = 0; i < old_capacity; i++ )
        if ( old[i].addr != 0 )
            mt_table[mt_find( old[i].addr )] = old[i];
    free( old );
    return true;
}

bool memtrack_alive( const void *p, int kind )
{
    uintptr_t addr = (uintptr_t) p;
    size_t i;

    if ( p == NULL )
        return false;
    /* Kept at most half full, so a probe is short. */
    if ( ( mt_used + 1 ) * 2 > mt_capacity && !mt_grow( ) )
        return false;
    i = mt_find( addr );
    if ( mt_table[i].addr == 0 )
    {
        mt_table[i].addr = addr;
        mt_used++;
    }
    else if ( mt_table[i].state == MEMTRACK_DEAD )
        mt_dead--;
    mt_table[i].kind  = (unsigned char) kind;
    mt_table[i].state = MEMTRACK_LIVE;
    return true;
}

bool memtrack_dead( const void *p )
{
    size_t i;

    if ( p == NULL || mt_capacity == 0 )
        return false;
    i = mt_find( (uintptr_t) p );
    if ( mt_table[i].addr == 0 )
        return false;
    if ( mt_table[i].state != MEMTRACK_DEAD )
        mt_dead++;
    mt_table[i].state = MEMTRACK_DEAD;
    return true;
}

void memtrack_forget( const void *p )
{
    size_t mask;
    size_t i;
    size_t j;

    if ( p == NULL || mt_capacity == 0 )
        return;
    mask = mt_capacity - 1;
    i = mt_find( (uintptr_t) p );
    if ( mt_table[i].addr == 0 )
        return;
    if ( mt_table[i].state == MEMTRACK_DEAD )
        mt_dead--;
    mt_table[i].addr = 0;
    mt_used--;

    /* Backward shift: pull later members of the run into the hole, so a
       lookup never stops early at it. */
    for ( j = ( i + 1 ) & mask; mt_table[j].addr != 0; j = ( j + 1 ) & mask )
    {
        size_t home = mt_hash( mt_table[j].addr ) & mask;

        /* j stays if its home lies cyclically in (i, j]. */
        if ( ( j > i && ( home <= i || home > j ) )
        ||   ( j < i && ( home <= i && home > j ) ) )
        {
            mt_table[i] = mt_table[j];
            mt_table[j].addr = 0;
            i = j;
        }
    }
}

int memtrack_state( const void *p, int kind )
{
    size_t i;

    if ( p == NULL || mt_capacity == 0 )
        return MEMTRACK_UNKNOWN;
    i = mt_find( (uintptr_t) p );
    if ( mt_table[i].addr == 0 )
        return MEMTRACK_UNKNOWN;
    if ( mt_table[i].kind != kind )
        return MEMTRACK_OTHER;
    return mt_table[i].state;
}

void memtrack_counts( size_t *live, size_t *dead, size_t *capacity )
{
    *live     = mt_used - mt_dead;
    *dead     = mt_dead;
    *capacity = mt_capacity;
}

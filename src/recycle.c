/***************************************************************************
 * recycle.c -- characters, objects, descriptors and extra descriptions   *
 * come from the system allocator and go back to it.                      *
 *                                                                         *
 * ROM kept a free list of each and handed a released block to the next   *
 * thing created, so AddressSanitizer never saw a use after free or a     *
 * double free in any of them: the block was still "in use", by the pool. *
 * Every allocation is calloc now and every release is free.              *
 *                                                                         *
 * Characters, objects and descriptors are not freed on the spot. The     *
 * game reads one it has just extracted -- gone_after_blow() asks a slain *
 * mobile's in_room after damage(), a loop finishes with a descriptor     *
 * close_socket() has closed, the web queue's stand-in asks whether it is *
 * still listed -- and under the pool that read was safe until something   *
 * new was created. Released ones wait on a list and are freed at the top *
 * of the next pass of the game loop (recycle_flush, beside               *
 * flush_container_lists), where no command, update or iteration is under *
 * way. A read later than that is a real use after free, and ASan says so. *
 ***************************************************************************/

#include "merc.h"

/*
 * The lists end at a sentinel rather than NULL, so `next_free' is NULL
 * exactly when a character or object is live: released twice, it is
 * refused with a bug line instead of being freed twice -- which, after a
 * flush, is a free of memory the allocator has already reused.
 */
static CHAR_DATA        char_released_end;
static OBJ_DATA         obj_released_end;
static CHAR_DATA *      char_released   = &char_released_end;
static OBJ_DATA *       obj_released    = &obj_released_end;

static DESCRIPTOR_DATA **desc_released;
static int              desc_released_count;
static int              desc_released_size;


static void *recycle_calloc( size_t size, const char *what )
{
    void *mem = calloc( 1, size );

    if ( mem == NULL )
    {
        perror( what );
        exit( 1 );
    }
    return mem;
}


CHAR_DATA *char_data_new( void )
{
    return recycle_calloc( sizeof(CHAR_DATA), "char_data_new" );
}

bool char_data_released( const CHAR_DATA *ch )
{
    return ch != NULL && ch->next_free != NULL;
}

/* The character's own pcdata goes with it. */
void char_data_release( CHAR_DATA *ch )
{
    if ( ch == NULL || ch == &char_released_end )
        return;
    if ( char_data_released( ch ) )
    {
        bug( "Char_data_release: released twice.", 0 );
        return;
    }
    ch->next_free = char_released;
    char_released = ch;
}


OBJ_DATA *obj_data_new( void )
{
    return recycle_calloc( sizeof(OBJ_DATA), "obj_data_new" );
}

bool obj_data_released( const OBJ_DATA *obj )
{
    return obj != NULL && obj->next_free != NULL;
}

void obj_data_release( OBJ_DATA *obj )
{
    if ( obj == NULL || obj == &obj_released_end )
        return;
    if ( obj_data_released( obj ) )
    {
        bug( "Obj_data_release: released twice.", 0 );
        return;
    }
    obj->next_free = obj_released;
    obj_released   = obj;
}


DESCRIPTOR_DATA *descriptor_data_new( void )
{
    return recycle_calloc( sizeof(DESCRIPTOR_DATA), "descriptor_data_new" );
}

void descriptor_data_release( DESCRIPTOR_DATA *d )
{
    int i;

    if ( d == NULL )
        return;
    for ( i = 0; i < desc_released_count; i++ )
    {
        if ( desc_released[i] == d )
        {
            bug( "Descriptor_data_release: released twice.", 0 );
            return;
        }
    }
    if ( desc_released_count == desc_released_size )
    {
        int size = desc_released_size > 0 ? 2 * desc_released_size : 16;
        DESCRIPTOR_DATA **grown =
            realloc( desc_released, (size_t) size * sizeof(*grown) );

        if ( grown == NULL )
        {
            /* Kept for good rather than freed under a reader. */
            bug( "Descriptor_data_release: out of memory.", 0 );
            return;
        }
        desc_released      = grown;
        desc_released_size = size;
    }
    desc_released[desc_released_count++] = d;
}


/* Extra descriptions are freed at once: nothing reads one after it goes. */
EXTRA_DESCR_DATA *extra_descr_new( void )
{
    return alloc_mem( sizeof(EXTRA_DESCR_DATA) );
}

void extra_descr_release( EXTRA_DESCR_DATA *ed )
{
    if ( ed == NULL )
        return;
    free_string( ed->description );
    free_string( ed->keyword );
    ed->description = NULL;
    ed->keyword     = NULL;
    free_mem( ed, sizeof(*ed) );
}


/*
 * Free everything released since the last call. Only where nothing can
 * still be holding a pointer taken during the pass: the top of the game
 * loop. A block that came from permanent memory -- nothing does now, but a
 * prototype's never did -- is left where it is.
 */
void recycle_flush( void )
{
    CHAR_DATA *ch;
    CHAR_DATA *ch_next;
    OBJ_DATA *obj;
    OBJ_DATA *obj_next;
    int i;

    for ( ch = char_released; ch != &char_released_end; ch = ch_next )
    {
        ch_next = ch->next_free;
        if ( ch->pcdata != NULL && !is_perm_memory( ch->pcdata ) )
            free( ch->pcdata );
        if ( !is_perm_memory( ch ) )
            free( ch );
    }
    char_released = &char_released_end;

    for ( obj = obj_released; obj != &obj_released_end; obj = obj_next )
    {
        obj_next = obj->next_free;
        if ( !is_perm_memory( obj ) )
            free( obj );
    }
    obj_released = &obj_released_end;

    for ( i = 0; i < desc_released_count; i++ )
        if ( !is_perm_memory( desc_released[i] ) )
            free( desc_released[i] );
    desc_released_count = 0;
}

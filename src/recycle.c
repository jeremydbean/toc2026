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
 * new was created. Released ones wait and are freed at the top of a later *
 * pass of the game loop (recycle_flush, beside flush_container_lists),    *
 * where no command, update or iteration is under way.                    *
 *                                                                         *
 * Quarantine (2026-11-11, "Memory Safeguards" in AGENTS.md). In an       *
 * ordinary build a released block is not freed at the next pass but kept *
 * whole, tagged MEM_DEAD_*, for MEM_QUARANTINE_SECS (the environment's    *
 * TOC_MEM_QUARANTINE_SECS overrides) and at most MEM_QUARANTINE_MAX      *
 * blocks. A stale pointer read inside that window reads what the old pool *
 * would have given it -- the game survives it -- and memguard.c's sweep  *
 * sees the dead tag, logs it and repairs the pointer. Under               *
 * AddressSanitizer the window is 0 unless the environment asks for one,   *
 * so ASan still reports a use after free itself.                         *
 ***************************************************************************/

#include "merc.h"

/*
 * A released character or object keeps `next_free' non-NULL (the
 * sentinel), and every released block carries its MEM_DEAD_* tag, so a
 * second release is refused with a bug line instead of being freed twice.
 */
static CHAR_DATA        char_released_end;
static OBJ_DATA         obj_released_end;

#define Q_CHAR  1
#define Q_OBJ   2
#define Q_DESC  3
#define Q_LABEL 64

/*
 * One released block, oldest first: freed when its window is over or the
 * quarantine is past its cap. The label is written at release from what is
 * still safe to read then -- a player's name before free_char frees it, an
 * object's prototype -- so a stale pointer can be named later without
 * reading a freed string.
 */
typedef struct quarantine_entry
{
    void *      ptr;
    time_t      when;
    int         kind;
    char        label[Q_LABEL];
    int         level;      /* the trust that may read the label (a wizinvis name) */
} QUARANTINE_ENTRY;

static QUARANTINE_ENTRY *quarantine;
static int              q_head;
static int              q_count;
static int              q_size;
static long             q_freed;
static int              q_window = -1;   /* read from the environment once */

/* The label free_char hands over before it frees the strings. */
static const CHAR_DATA *pending_label_ch;
static char             pending_label[Q_LABEL];
static int              pending_label_level;


static int quarantine_window( void )
{
    const char *env;

    if ( q_window >= 0 )
        return q_window;
    q_window = MEM_QUARANTINE_SECS;
#if defined(__SANITIZE_ADDRESS__)
    q_window = 0;
#elif defined(__has_feature)
#if __has_feature(address_sanitizer)
    q_window = 0;
#endif
#endif
    if ( ( env = getenv( "TOC_MEM_QUARANTINE_SECS" ) ) != NULL && env[0] != '\0' )
    {
        char *end;
        long secs = strtol( env, &end, 10 );

        if ( *end == '\0' && secs >= 0 && secs <= 3600 )
            q_window = (int) secs;
    }
    return q_window;
}


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


static void quarantine_free_block( QUARANTINE_ENTRY *e )
{
    if ( e->kind == Q_CHAR )
    {
        CHAR_DATA *ch = e->ptr;

        if ( ch->pcdata != NULL && !is_perm_memory( ch->pcdata ) )
            free( ch->pcdata );
    }
    if ( !is_perm_memory( e->ptr ) )
        free( e->ptr );
    e->ptr = NULL;
    q_freed++;
}


/*
 * Kept even past the cap: a block released in this pass may still be read
 * in this pass, so only recycle_flush ever frees, and it trims to the cap.
 */
static void quarantine_push( void *ptr, int kind, const char *label, int level )
{
    QUARANTINE_ENTRY *e;

    if ( q_count == q_size )
    {
        int size = q_size > 0 ? 2 * q_size : 256;
        QUARANTINE_ENTRY *grown = malloc( (size_t) size * sizeof(*grown) );
        int i;

        if ( grown == NULL )
        {
            /* Kept for good rather than freed under a reader. */
            bug( "Recycle: out of memory for the quarantine.", 0 );
            return;
        }
        for ( i = 0; i < q_count; i++ )
            grown[i] = quarantine[( q_head + i ) % q_size];
        free( quarantine );
        quarantine = grown;
        q_head     = 0;
        q_size     = size;
    }
    e = &quarantine[( q_head + q_count ) % q_size];
    e->ptr  = ptr;
    e->when = current_time;
    e->kind = kind;
    toc_strlcpy( e->label, label != NULL ? label : "?", sizeof(e->label) );
    e->level = level;
    q_count++;
}


CHAR_DATA *char_data_new( void )
{
    CHAR_DATA *ch = recycle_calloc( sizeof(CHAR_DATA), "char_data_new" );

    ch->mem_magic = MEM_ALIVE_CHAR;
    return ch;
}

bool char_data_released( const CHAR_DATA *ch )
{
    return ch != NULL
        && ( ch->next_free != NULL || ch->mem_magic == MEM_DEAD_CHAR );
}

/* NULL and untagged stand-ins count as live: only a dead tag is stale. */
bool char_is_live( const CHAR_DATA *ch )
{
    return ch == NULL || ch->mem_magic != MEM_DEAD_CHAR;
}

/*
 * free_char calls this before it frees the character's strings, so the
 * quarantine can name a player whose name is about to go: a mobile's
 * prototype strings are permanent, a player's name is not.
 */
void recycle_label_char( const CHAR_DATA *ch )
{
    pending_label_ch = ch;
    pending_label_level = LEVEL_IMMORTAL;
    if ( ch == NULL )
        return;
    /* A wizinvis player's name is for those who could see them. */
    if ( ch->pcdata != NULL )
        pending_label_level = staff_notice_level( ch, LEVEL_IMMORTAL );
    if ( ch->pcdata == NULL && ch->pIndexData != NULL )
        snprintf( pending_label, sizeof(pending_label), "mob %d %s",
                  ch->pIndexData->vnum,
                  ch->pIndexData->short_descr != NULL
                      ? ch->pIndexData->short_descr : "?" );
    else
        snprintf( pending_label, sizeof(pending_label), "player %s",
                  ch->name != NULL ? ch->name : "?" );
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
    ch->next_free = &char_released_end;
    ch->mem_magic = MEM_DEAD_CHAR;
    if ( pending_label_ch != ch )
    {
        /* Not labelled by free_char: only the prototype is safe to read. */
        if ( ch->pIndexData != NULL )
            snprintf( pending_label, sizeof(pending_label), "mob %d",
                      ch->pIndexData->vnum );
        else
            toc_strlcpy( pending_label, "character", sizeof(pending_label) );
        pending_label_level = LEVEL_IMMORTAL;
    }
    quarantine_push( ch, Q_CHAR, pending_label, pending_label_level );
    pending_label_ch = NULL;
}


OBJ_DATA *obj_data_new( void )
{
    OBJ_DATA *obj = recycle_calloc( sizeof(OBJ_DATA), "obj_data_new" );

    obj->mem_magic = MEM_ALIVE_OBJ;
    return obj;
}

bool obj_data_released( const OBJ_DATA *obj )
{
    return obj != NULL
        && ( obj->next_free != NULL || obj->mem_magic == MEM_DEAD_OBJ );
}

bool obj_is_live( const OBJ_DATA *obj )
{
    return obj == NULL || obj->mem_magic != MEM_DEAD_OBJ;
}

void obj_data_release( OBJ_DATA *obj )
{
    char label[Q_LABEL];

    if ( obj == NULL || obj == &obj_released_end )
        return;
    if ( obj_data_released( obj ) )
    {
        bug( "Obj_data_release: released twice.", 0 );
        return;
    }
    obj->next_free = &obj_released_end;
    obj->mem_magic = MEM_DEAD_OBJ;
    /* The prototype is permanent; the object's own strings are freed. */
    if ( obj->pIndexData != NULL )
        snprintf( label, sizeof(label), "obj %d %s", obj->pIndexData->vnum,
                  obj->pIndexData->short_descr != NULL
                      ? obj->pIndexData->short_descr : "?" );
    else
        toc_strlcpy( label, "object", sizeof(label) );
    quarantine_push( obj, Q_OBJ, label, LEVEL_IMMORTAL );
}


DESCRIPTOR_DATA *descriptor_data_new( void )
{
    DESCRIPTOR_DATA *d = recycle_calloc( sizeof(DESCRIPTOR_DATA),
                                         "descriptor_data_new" );

    d->mem_magic = MEM_ALIVE_DESC;
    return d;
}

bool desc_is_live( const DESCRIPTOR_DATA *d )
{
    return d == NULL || d->mem_magic != MEM_DEAD_DESC;
}

void descriptor_data_release( DESCRIPTOR_DATA *d )
{
    char label[Q_LABEL];

    if ( d == NULL )
        return;
    if ( d->mem_magic == MEM_DEAD_DESC )
    {
        bug( "Descriptor_data_release: released twice.", 0 );
        return;
    }
    d->mem_magic = MEM_DEAD_DESC;
    /* The socket number only: never an address. */
    snprintf( label, sizeof(label), "descriptor %d", d->descriptor );
    quarantine_push( d, Q_DESC, label, LEVEL_IMMORTAL );
}


/*
 * What a dead block was, for memguard.c's MEMORY lines: true, and the
 * label written at its release, when `ptr' is in quarantine. Linear, and
 * only asked when a stale pointer has been found.
 */
bool recycle_dead_label( const void *ptr, char *out, size_t size, int *level )
{
    int i;

    for ( i = q_count - 1; i >= 0; i-- )
    {
        const QUARANTINE_ENTRY *e = &quarantine[( q_head + i ) % q_size];

        if ( e->ptr == ptr )
        {
            toc_strlcpy( out, e->label, size );
            if ( level != NULL )
                *level = e->level;
            return TRUE;
        }
    }
    toc_strlcpy( out, "?", size );
    if ( level != NULL )
        *level = LEVEL_IMMORTAL;
    return FALSE;
}

void recycle_stats( int *held, long *oldest_secs, long *freed,
                    int *window_secs, int *cap )
{
    *held        = q_count;
    *oldest_secs = q_count > 0
        ? (long) ( current_time - quarantine[q_head].when ) : 0;
    *freed       = q_freed;
    *window_secs = quarantine_window( );
    *cap         = MEM_QUARANTINE_MAX;
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
 * Free what has served its quarantine. Only where nothing can still be
 * holding a pointer taken during the pass: the top of the game loop. With
 * a window of 0 (a sanitizer build) that is everything released before
 * this call, exactly as before the quarantine. Past the cap the oldest go
 * whatever their age. A block from permanent memory -- nothing does now,
 * but a prototype's never did -- is left where it is.
 */
void recycle_flush( void )
{
    int window = quarantine_window( );

    while ( q_count > 0 )
    {
        QUARANTINE_ENTRY *e = &quarantine[q_head];

        if ( q_count <= MEM_QUARANTINE_MAX && window > 0
        &&   e->when + window > current_time )
            break;
        quarantine_free_block( e );
        q_head = ( q_head + 1 ) % q_size;
        q_count--;
    }
}

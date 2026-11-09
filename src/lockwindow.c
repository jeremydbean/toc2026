/*
 * The wrong-password window: see lockwindow.h. No merc.h, no game state.
 */
#include <ctype.h>
#include <string.h>
#include "lockwindow.h"

static int name_equal( const char *a, const char *b )
{
    for ( ; *a != '\0' && *b != '\0'; a++, b++ )
        if ( tolower( (unsigned char) *a ) != tolower( (unsigned char) *b ) )
            return 0;
    return *a == *b;
}

static void drop( LOCK_WINDOW *w, int i )
{
    for ( ; i + 1 < w->n; i++ )
    {
        w->at[i] = w->at[i + 1];
        memcpy( w->name[i], w->name[i + 1], LOCK_WINDOW_NAME );
    }
    w->n--;
}

void lock_window_expire( LOCK_WINDOW *w, long now, long window )
{
    int i = 0;

    while ( i < w->n )
    {
        /* A failure from the future (a clock stepped back) is not kept
           counting for ever either. */
        if ( now - w->at[i] >= window || w->at[i] > now + window )
            drop( w, i );
        else
            i++;
    }
}

int lock_window_add( LOCK_WINDOW *w, long now, long window, const char *name )
{
    lock_window_expire( w, now, window );
    if ( w->n == LOCK_WINDOW_SLOTS )
        drop( w, 0 );
    w->at[w->n] = now;
    strncpy( w->name[w->n], name != NULL ? name : "", LOCK_WINDOW_NAME - 1 );
    w->name[w->n][LOCK_WINDOW_NAME - 1] = '\0';
    w->n++;
    return w->n;
}

int lock_window_count( LOCK_WINDOW *w, long now, long window )
{
    lock_window_expire( w, now, window );
    return w->n;
}

void lock_window_forget_name( LOCK_WINDOW *w, const char *name )
{
    int i = 0;

    if ( name == NULL )
        return;
    while ( i < w->n )
    {
        if ( name_equal( w->name[i], name ) )
            drop( w, i );
        else
            i++;
    }
}

void lock_window_clear( LOCK_WINDOW *w )
{
    memset( w, 0, sizeof(*w) );
}

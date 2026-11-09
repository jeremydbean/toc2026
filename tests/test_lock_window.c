/*
 * The wrong-password window (src/lockwindow.c) against a synthetic clock
 * (review, 2026-11-09). Prints "ok" or FAIL lines.
 */
#include <stdio.h>
#include <string.h>
#include "lockwindow.h"

#define WINDOW 900L
#define MIN 60L

static int failures = 0;

static void expect( int got, int want, const char *what )
{
    if ( got != want )
    {
        printf( "FAIL %s: got %d, want %d\n", what, got, want );
        failures++;
    }
}

/* The review's sequence: one failure every fourteen minutes. No fifteen
   minutes ever hold more than two of them. */
static void spaced_failures( void )
{
    LOCK_WINDOW w;
    long t[] = { 0, 14 * MIN, 28 * MIN, 42 * MIN, 56 * MIN };
    int i, most = 0, n;

    lock_window_clear( &w );
    for ( i = 0; i < 5; i++ )
    {
        n = lock_window_add( &w, 1000000L + t[i], WINDOW, "Zvictim" );
        if ( n > most )
            most = n;
    }
    expect( most, 2, "failures at 0, 14, 28, 42, 56 minutes never count five" );
}

static void five_inside( void )
{
    LOCK_WINDOW w;
    int i, n = 0;

    lock_window_clear( &w );
    for ( i = 0; i < 5; i++ )
        n = lock_window_add( &w, 1000000L + i * 3 * MIN, WINDOW, "Zvictim" );
    expect( n, 5, "five failures within twelve minutes count five" );
}

static void boundaries( void )
{
    LOCK_WINDOW w;
    long base = 2000000L;
    int i, n;

    /* The fifth a second inside the first's fifteen minutes: five. */
    lock_window_clear( &w );
    for ( i = 0; i < 4; i++ )
        lock_window_add( &w, base + i * MIN, WINDOW, "Zvictim" );
    n = lock_window_add( &w, base + WINDOW - 1, WINDOW, "Zvictim" );
    expect( n, 5, "the fifth at 899 seconds" );

    /* At exactly fifteen minutes the first has left: four. */
    lock_window_clear( &w );
    for ( i = 0; i < 4; i++ )
        lock_window_add( &w, base + i * MIN, WINDOW, "Zvictim" );
    n = lock_window_add( &w, base + WINDOW, WINDOW, "Zvictim" );
    expect( n, 4, "the fifth at 900 seconds" );

    /* Everything has left fifteen minutes after the last. */
    expect( lock_window_count( &w, base + WINDOW + WINDOW, WINDOW ), 0,
            "all gone fifteen minutes after the last" );
}

/* Logging into one's own character forgives one's own slips only. */
static void names( void )
{
    LOCK_WINDOW w;
    long base = 3000000L;
    int n;

    lock_window_clear( &w );
    lock_window_add( &w, base, WINDOW, "Zvictim" );
    lock_window_add( &w, base + 10, WINDOW, "Zowner" );
    lock_window_add( &w, base + 20, WINDOW, "Zvictim" );
    lock_window_add( &w, base + 30, WINDOW, "Zvictim" );
    lock_window_add( &w, base + 40, WINDOW, "ZOWNER" );
    lock_window_forget_name( &w, "zowner" );
    expect( lock_window_count( &w, base + 50, WINDOW ), 3,
            "the owner's login forgets the owner's two, keeps three at another" );
    n = lock_window_add( &w, base + 60, WINDOW, "Zvictim" );
    expect( n, 4, "guesses at another go on counting" );
    n = lock_window_add( &w, base + 70, WINDOW, "Zvictim" );
    expect( n, 5, "and reach five" );

    /* A player who only mistyped their own: all forgiven. */
    lock_window_clear( &w );
    lock_window_add( &w, base, WINDOW, "Zowner" );
    lock_window_add( &w, base + 5, WINDOW, "Zowner" );
    lock_window_forget_name( &w, "Zowner" );
    expect( lock_window_count( &w, base + 6, WINDOW ), 0, "own slips forgiven" );

    /* A failure's name leaves with it: an old guess at another expires,
       and nothing about it outlasts the window. */
    lock_window_clear( &w );
    lock_window_add( &w, base, WINDOW, "Zvictim" );
    lock_window_add( &w, base + 600, WINDOW, "Zowner" );
    expect( lock_window_count( &w, base + WINDOW, WINDOW ), 1, "the old guess expired" );
    expect( strcmp( w.name[0], "Zowner" ), 0, "with its name" );
    lock_window_forget_name( &w, "Zowner" );
    expect( lock_window_count( &w, base + WINDOW, WINDOW ), 0,
            "the owner then clears what is left" );
}

static void bounds( void )
{
    LOCK_WINDOW w;
    long base = 4000000L;
    int i, n = 0;
    char longname[64];

    lock_window_clear( &w );
    for ( i = 0; i < 3 * LOCK_WINDOW_SLOTS; i++ )
        n = lock_window_add( &w, base + i, WINDOW, "Zvictim" );
    expect( n, LOCK_WINDOW_SLOTS, "never more than the slots" );
    expect( w.at[0] == base + 2 * LOCK_WINDOW_SLOTS, 1, "the oldest gave way" );

    /* A clock stepped back: failures from far ahead are not believed. */
    lock_window_clear( &w );
    lock_window_add( &w, base + 10 * WINDOW, WINDOW, "Zvictim" );
    expect( lock_window_count( &w, base, WINDOW ), 0, "a failure from the future" );

    memset( longname, 'Z', sizeof(longname) - 1 );
    longname[sizeof(longname) - 1] = '\0';
    lock_window_clear( &w );
    lock_window_add( &w, base, WINDOW, longname );
    expect( (int) strlen( w.name[0] ), LOCK_WINDOW_NAME - 1, "a long name is cut, terminated" );
    lock_window_add( &w, base + 1, WINDOW, NULL );
    expect( lock_window_count( &w, base + 2, WINDOW ), 2, "a missing name counts" );
}

int main( void )
{
    spaced_failures();
    five_inside();
    boundaries();
    names();
    bounds();
    if ( failures == 0 )
        printf( "ok\n" );
    return failures == 0 ? 0 : 1;
}

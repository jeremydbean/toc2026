/*
 * src/dstring.c: the growable string listings are built in (growable
 * output buffers, 2026-11-12). Run by tests/test_dstring.py under
 * AddressSanitizer and UndefinedBehaviorSanitizer where the compiler has
 * them. Prints "ok" and exits 0, or a FAIL line per broken check.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "dstring.h"

static int failures;

#define CHECK( cond ) \
    do { if ( !( cond ) ) { printf( "FAIL %s:%d %s\n", __FILE__, __LINE__, #cond ); failures++; } } while ( 0 )

static void unbounded_grows_past_any_fixed_array( void )
{
    DString s;
    char line[64];
    int i;

    dstring_init( &s );
    CHECK( s.limit == 0 && !s.truncated );
    for ( i = 1; i <= 20000; i++ )
    {
        snprintf( line, sizeof(line), "%5d) silver plate\n\r", i );
        CHECK( dstring_append_cstr( &s, line ) );
    }
    CHECK( dstring_length( &s ) == 20000u * strlen( "    1) silver plate\n\r" ) );
    CHECK( strstr( dstring_cstr( &s ), "20000) silver plate" ) != NULL );
    CHECK( !s.truncated );
    dstring_free( &s );
    CHECK( strcmp( dstring_cstr( &s ), "" ) == 0 );
}

static void printf_appends_whole( void )
{
    DString s;

    dstring_init( &s );
    CHECK( dstring_printf( &s, "%s %d", "abc", 42 ) );
    CHECK( dstring_printf( &s, "|%05d|", 7 ) );
    CHECK( strcmp( dstring_cstr( &s ), "abc 42|00007|" ) == 0 );
    CHECK( dstring_length( &s ) == strlen( "abc 42|00007|" ) );
    /* Longer than the initial capacity in one go. */
    CHECK( dstring_printf( &s, "%300s", "x" ) );
    CHECK( dstring_length( &s ) == strlen( "abc 42|00007|" ) + 300 );
    CHECK( dstring_cstr( &s )[dstring_length( &s ) - 1] == 'x' );
    dstring_free( &s );
}

static void the_limit_refuses_whole_appends( void )
{
    DString s;

    dstring_init_limit( &s, 10 );
    CHECK( dstring_fits( &s, 10 ) );
    CHECK( !dstring_fits( &s, 11 ) );
    CHECK( dstring_append_cstr( &s, "12345" ) );
    CHECK( !s.truncated );
    /* Six more would pass ten: nothing of it goes in. */
    CHECK( !dstring_append_cstr( &s, "abcdef" ) );
    CHECK( s.truncated );
    CHECK( strcmp( dstring_cstr( &s ), "12345" ) == 0 );
    /* Exactly to the limit is allowed. */
    CHECK( dstring_printf( &s, "%s", "ABCDE" ) );
    CHECK( strcmp( dstring_cstr( &s ), "12345ABCDE" ) == 0 );
    CHECK( !dstring_printf( &s, "%c", 'z' ) );
    CHECK( !dstring_append_char( &s, 'z' ) );
    CHECK( dstring_length( &s ) == 10 );
    CHECK( !dstring_fits( &s, 1 ) && dstring_fits( &s, 0 ) );
    /* A huge request cannot wrap the arithmetic into "fits". */
    CHECK( !dstring_fits( &s, (size_t) -1 ) );
    dstring_clear( &s );
    CHECK( !s.truncated && dstring_length( &s ) == 0 && s.limit == 10 );
    dstring_free( &s );
}

static void the_output_limit_holds_a_full_stash( void )
{
    DString s;
    char line[64];
    int i;

    /* 500 slots, at a far longer line than a stash's: well inside it. */
    dstring_init_limit( &s, DSTRING_OUTPUT_MAX );
    for ( i = 1; i <= 500; i++ )
    {
        snprintf( line, sizeof(line), "  %3d) %-50s\n\r", i, "a very long name" );
        CHECK( dstring_append_cstr( &s, line ) );
    }
    CHECK( !s.truncated );
    CHECK( dstring_length( &s ) > 4 * 4096 );
    dstring_free( &s );
}

int main( void )
{
    unbounded_grows_past_any_fixed_array();
    printf_appends_whole();
    the_limit_refuses_whole_appends();
    the_output_limit_holds_a_full_stash();
    if ( failures == 0 )
        printf( "ok\n" );
    return failures == 0 ? 0 : 1;
}

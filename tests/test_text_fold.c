/*
 * Boundary checks for src/text_fold.c, built by tests/test_text_fold.py,
 * under AddressSanitizer when the compiler has it. The help loader's first
 * fold wrote its terminator one past a 4096-byte buffer for a header of
 * 4094 letters, a tab and one more letter (review, 2026-10-30).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "text_fold.h"

#define SIZE 4096

static int failures;

static void check( int ok, const char *what )
{
    printf( "%s %s\n", ok ? "ok" : "FAIL", what );
    if ( !ok )
        failures++;
}

/* A heap buffer exactly `size` long, so ASan sees one byte past it. */
static int fold( const char *in, size_t size, char **out, int *changed )
{
    *out = malloc( size );
    return fold_whitespace( in, *out, size, changed );
}

static char *letters( size_t count, const char *tail )
{
    char *s = malloc( count + strlen( tail ) + 1 );

    memset( s, 'A', count );
    strcpy( s + count, tail );
    return s;
}

int main( void )
{
    char *in, *out;
    int changed, n;

    /* The review's case: 4094 letters, a tab, a letter -- 4096 folded. */
    in = letters( SIZE - 2, "\tB" );
    n = fold( in, SIZE, &out, &changed );
    check( n == -1 && out[0] == '\0', "separator and letter past the end: refused, empty" );
    free( in ); free( out );

    /* One shorter fits exactly: 4095 characters and the terminator. */
    in = letters( SIZE - 3, "\tB" );
    n = fold( in, SIZE, &out, &changed );
    check( n == SIZE - 1 && changed && out[SIZE - 3] == ' ' && out[SIZE - 2] == 'B'
           && out[SIZE - 1] == '\0', "folded to the last byte" );
    free( in ); free( out );

    in = letters( SIZE - 1, "" );
    n = fold( in, SIZE, &out, &changed );
    check( n == SIZE - 1 && !changed, "4095 letters fit, unchanged" );
    free( in ); free( out );

    in = letters( SIZE, "" );
    n = fold( in, SIZE, &out, &changed );
    check( n == -1, "4096 letters do not fit" );
    free( in ); free( out );

    /* Whitespace near the limit costs nothing unless a letter follows. */
    in = letters( SIZE - 1, " \t\n\r  " );
    n = fold( in, SIZE, &out, &changed );
    check( n == SIZE - 1 && changed, "trailing whitespace at the limit dropped" );
    free( in ); free( out );

    in = letters( SIZE - 2, "\n\r\n\rB" );
    n = fold( in, SIZE, &out, &changed );
    check( n == -1, "a long run of whitespace still costs one separator" );
    free( in ); free( out );

    n = fold( "  ELECTRIC\n\rCALL   LIGHTNING\t", 64, &out, &changed );
    check( n == 23 && changed && !strcmp( out, "ELECTRIC CALL LIGHTNING" ),
           "leading, trailing and inner runs folded" );
    free( out );

    n = fold( "'DIVINE INTERVENTION' DIVINE", 64, &out, &changed );
    check( n == 28 && !changed, "a clean header is unchanged" );
    free( out );

    n = fold( "", 1, &out, &changed );
    check( n == 0 && out[0] == '\0', "empty into one byte" );
    free( out );

    n = fold( "a", 1, &out, &changed );
    check( n == -1 && out[0] == '\0', "one letter needs two bytes" );
    free( out );

    {
        char one[1];
        check( fold_whitespace( "x", one, 0, NULL ) == -1, "no room at all" );
    }

    printf( "%d failure(s)\n", failures );
    return failures != 0;
}

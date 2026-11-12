/*
 * The bounded text helpers of the format-truncation review (2026-11-12),
 * src/string_safe.c: format_tenths (a number to one decimal place, held to
 * a limit, never longer than FORMAT_TENTHS_MAX) and toc_path_join (a path
 * joined only when all of it fits). Built and run by
 * tests/test_format_bounds.py; prints "ok" or FAIL lines.
 */
#include <float.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "merc.h"

static int failures;

static void expect_text( const char *what, const char *got, const char *want )
{
    if ( strcmp( got, want ) != 0 )
    {
        printf( "FAIL %s: got \"%s\", want \"%s\"\n", what, got, want );
        failures++;
    }
}

static void expect_true( const char *what, bool cond )
{
    if ( !cond )
    {
        printf( "FAIL %s\n", what );
        failures++;
    }
}

int main( void )
{
    char buf[FORMAT_TENTHS_MAX], path[16];
    static const double extremes[] = { DBL_MAX, -DBL_MAX, HUGE_VAL, -HUGE_VAL, 1e300,
                                       -1e300, 1e15, -1e15, 0.0, -0.0 };
    size_t i;

    expect_text( "zero", format_tenths( buf, sizeof(buf), 0.0, 999.9 ), "0.0" );
    expect_text( "a tenth", format_tenths( buf, sizeof(buf), 12.34, 999.9 ), "12.3" );
    expect_text( "rounds up", format_tenths( buf, sizeof(buf), 12.36, 999.9 ), "12.4" );
    expect_text( "negative", format_tenths( buf, sizeof(buf), -0.5, 999.9 ), "-0.5" );
    expect_text( "a nearly zero negative", format_tenths( buf, sizeof(buf), -0.04, 999.9 ),
                 "0.0" );
    expect_text( "held to the limit", format_tenths( buf, sizeof(buf), 5000.0, 999.9 ),
                 "999.9" );
    expect_text( "held to minus the limit", format_tenths( buf, sizeof(buf), -5000.0, 999.9 ),
                 "-999.9" );
    expect_text( "NaN reads 0", format_tenths( buf, sizeof(buf), NAN, 999.9 ), "0.0" );
    expect_text( "a big round number", format_tenths( buf, sizeof(buf), 1e10, 1e12 ),
                 "10000000000.0" );
    /* Any value, any limit: never longer than FORMAT_TENTHS_MAX - 1. */
    for ( i = 0; i < sizeof(extremes) / sizeof(extremes[0]); i++ )
    {
        char wide[64];

        format_tenths( wide, sizeof(wide), extremes[i], DBL_MAX );
        expect_true( "an extreme fits FORMAT_TENTHS_MAX", strlen( wide ) < FORMAT_TENTHS_MAX );
    }
    expect_text( "the biggest", format_tenths( buf, sizeof(buf), -DBL_MAX, DBL_MAX ),
                 "-1000000000000000.0" );
    /* A short buffer is cut, as toc_strlcpy cuts, never overrun. */
    {
        char tiny[4];

        format_tenths( tiny, sizeof(tiny), 123.4, 999.9 );
        expect_text( "a short buffer", tiny, "123" );
    }

    expect_true( "a join that fits", toc_path_join( path, sizeof(path), "../dir/", "", "Name" ) );
    expect_text( "the joined path", path, "../dir/Name" );
    expect_true( "a join with a separator", toc_path_join( path, sizeof(path), "a", "/", "b" ) );
    expect_text( "the separated path", path, "a/b" );
    /* Exactly full: 15 characters and the nul. */
    expect_true( "a join of exactly the size",
                 toc_path_join( path, sizeof(path), "0123456789", "", "abcde" ) );
    expect_text( "the full path", path, "0123456789abcde" );
    expect_true( "one too long is refused",
                 !toc_path_join( path, sizeof(path), "0123456789", "", "abcdef" ) );
    expect_text( "and leaves nothing", path, "" );
    expect_true( "a directory alone too long",
                 !toc_path_join( path, sizeof(path), "0123456789abcdefgh", "", "" ) );
    expect_true( "nothing fits nothing", !toc_path_join( path, 0, "a", "", "b" ) );

    expect_true( "snprintf_fits: fits", snprintf_fits( 15, 16 ) );
    expect_true( "snprintf_fits: cut", !snprintf_fits( 16, 16 ) );
    expect_true( "snprintf_fits: an error", !snprintf_fits( -1, 16 ) );

    if ( failures == 0 )
        printf( "ok\n" );
    return failures == 0 ? 0 : 1;
}

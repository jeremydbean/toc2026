/*
 * tests/test_numparse.c -- src/numparse.c checked exactly: whole numbers
 * only, signs, surrounding space, the edges of int and long, and ranges
 * (modernization project 2, 2026-11-11). Prints "FAIL ..." for each
 * failure and "ok" when there are none. Built and run by
 * tests/test_numparse.py.
 */
#include <limits.h>
#include <stdio.h>
#include "numparse.h"

static int failures = 0;

#define CHECK(cond, ...) do { if ( !(cond) ) { failures++; \
    printf( "FAIL " ); printf( __VA_ARGS__ ); printf( "\n" ); } } while ( 0 )

static void int_ok( const char *text, int min, int max, int want )
{
    int got = -12345;

    CHECK( parse_int( text, min, max, &got ) && got == want,
           "parse_int(\"%s\", %d, %d) should give %d, gave %d", text, min, max, want, got );
}

static void int_refused( const char *text, int min, int max )
{
    int got = -12345;

    CHECK( !parse_int( text, min, max, &got ) && got == -12345,
           "parse_int(\"%s\", %d, %d) should be refused and leave the output, gave %d",
           text ? text : "(null)", min, max, got );
}

static void long_ok( const char *text, long min, long max, long want )
{
    long got = -12345;

    CHECK( parse_long( text, min, max, &got ) && got == want,
           "parse_long(\"%s\") should give %ld, gave %ld", text, want, got );
}

static void long_refused( const char *text, long min, long max )
{
    long got = -12345;

    CHECK( !parse_long( text, min, max, &got ) && got == -12345,
           "parse_long(\"%s\") should be refused, gave %ld", text, got );
}

int main( void )
{
    char buf[64];

    /* What atoi took and these refuse. */
    int_refused( "", INT_MIN, INT_MAX );
    int_refused( NULL, INT_MIN, INT_MAX );
    int_refused( "abc", INT_MIN, INT_MAX );
    int_refused( "5abc", INT_MIN, INT_MAX );
    int_refused( "5 abc", INT_MIN, INT_MAX );
    int_refused( "-", INT_MIN, INT_MAX );
    int_refused( "+", INT_MIN, INT_MAX );
    int_refused( "- 5", INT_MIN, INT_MAX );
    int_refused( "--5", INT_MIN, INT_MAX );
    int_refused( "+-5", INT_MIN, INT_MAX );
    int_refused( "0x10", INT_MIN, INT_MAX );
    int_refused( "1.5", INT_MIN, INT_MAX );
    int_refused( "1e3", INT_MIN, INT_MAX );
    int_refused( "   ", INT_MIN, INT_MAX );
    int_refused( "12,000", INT_MIN, INT_MAX );

    /* Whole numbers. */
    int_ok( "0", INT_MIN, INT_MAX, 0 );
    int_ok( "5", INT_MIN, INT_MAX, 5 );
    int_ok( "+5", INT_MIN, INT_MAX, 5 );
    int_ok( "-5", INT_MIN, INT_MAX, -5 );
    int_ok( "-0", INT_MIN, INT_MAX, 0 );
    int_ok( "007", INT_MIN, INT_MAX, 7 );
    int_ok( " 42", INT_MIN, INT_MAX, 42 );
    int_ok( "42 ", INT_MIN, INT_MAX, 42 );
    int_ok( "\t42\n", INT_MIN, INT_MAX, 42 );

    /* The edges of int. */
    snprintf( buf, sizeof( buf ), "%d", INT_MAX );
    int_ok( buf, INT_MIN, INT_MAX, INT_MAX );
    snprintf( buf, sizeof( buf ), "%d", INT_MIN );
    int_ok( buf, INT_MIN, INT_MAX, INT_MIN );
    snprintf( buf, sizeof( buf ), "%ld", (long) INT_MAX + 1 );
    int_refused( buf, INT_MIN, INT_MAX );
    snprintf( buf, sizeof( buf ), "%ld", (long) INT_MIN - 1 );
    int_refused( buf, INT_MIN, INT_MAX );
    int_refused( "99999999999999999999999999", INT_MIN, INT_MAX );
    int_refused( "-99999999999999999999999999", INT_MIN, INT_MAX );

    /* Ranges: both ends included, one past refused. */
    int_ok( "1", 1, 59, 1 );
    int_ok( "59", 1, 59, 59 );
    int_refused( "0", 1, 59 );
    int_refused( "60", 1, 59 );
    int_refused( "-1", 0, INT_MAX );
    int_ok( "-10000", -10000, 10000, -10000 );
    int_refused( "-10001", -10000, 10000 );
    int_refused( "5", 6, 5 );   /* an empty range refuses everything */

    /* long. */
    snprintf( buf, sizeof( buf ), "%ld", LONG_MAX );
    long_ok( buf, LONG_MIN, LONG_MAX, LONG_MAX );
    snprintf( buf, sizeof( buf ), "%ld", LONG_MIN );
    long_ok( buf, LONG_MIN, LONG_MAX, LONG_MIN );
    long_refused( "99999999999999999999999999", LONG_MIN, LONG_MAX );
    long_refused( "-99999999999999999999999999", LONG_MIN, LONG_MAX );
    long_refused( "12x", LONG_MIN, LONG_MAX );
    long_refused( "", LONG_MIN, LONG_MAX );
    long_ok( "100", 1, 100, 100 );
    long_refused( "101", 1, 100 );

    if ( failures == 0 )
        printf( "ok\n" );
    return failures == 0 ? 0 : 1;
}

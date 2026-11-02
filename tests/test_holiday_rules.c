/*
 * tests/test_holiday_rules.c -- src/holiday_rules.c checked exactly:
 * the day arithmetic over every day from 1900 to 9999, date validation
 * and parsing, Easter and Thanksgiving against published dates, and the
 * firework cooldown table at its boundaries (review, 2026-11-02).
 * Prints "FAIL ..." for each failure and "ok" when there are none.
 * Built and run by tests/test_holiday_rules.py.
 */
#include <stdio.h>
#include <string.h>
#include "holiday_rules.h"

static int failures = 0;

#define CHECK(cond, ...) do { if ( !(cond) ) { failures++; \
    printf( "FAIL " ); printf( __VA_ARGS__ ); printf( "\n" ); } } while ( 0 )

static void test_round_trip( void )
{
    long first = holiday_days_from_civil( 1900, 1, 1 );
    long last  = holiday_days_from_civil( 9999, 12, 31 );
    long day;
    int y = 1900, m = 1, d = 1;

    CHECK( holiday_days_from_civil( 1970, 1, 1 ) == 0, "epoch is day 0" );
    CHECK( holiday_days_from_civil( 2000, 3, 1 ) - holiday_days_from_civil( 2000, 2, 28 ) == 2,
           "2000 is a leap year" );
    CHECK( holiday_days_from_civil( 1900, 3, 1 ) - holiday_days_from_civil( 1900, 2, 28 ) == 1,
           "1900 is not a leap year" );
    for ( day = first; day <= last; day++ )
    {
        int yy, mm, dd;

        holiday_civil_from_days( day, &yy, &mm, &dd );
        if ( yy != y || mm != m || dd != d || !holiday_date_valid( yy, mm, dd )
        ||   holiday_days_from_civil( yy, mm, dd ) != day )
        {
            CHECK( 0, "day %ld came back %04d-%02d-%02d, expected %04d-%02d-%02d",
                   day, yy, mm, dd, y, m, d );
            return;
        }
        /* the next calendar day, counted by hand */
        d++;
        if ( !holiday_date_valid( y, m, d ) )
        {
            d = 1;
            if ( ++m > 12 )
            {
                m = 1;
                y++;
            }
        }
    }
}

static void test_validation( void )
{
    static const struct { int y, m, d, ok; } cases[] =
    {
        { 2024,  2, 29, 1 }, { 2023,  2, 29, 0 }, { 2000,  2, 29, 1 },
        { 1900,  2, 29, 0 }, { 2100,  2, 29, 0 }, { 2026,  4, 31, 0 },
        { 2026,  4, 30, 1 }, { 2026, 12, 31, 1 }, { 2026, 13,  1, 0 },
        { 2026,  0, 10, 0 }, { 2026,  5,  0, 0 }, { 1899, 12, 31, 0 },
        { 1900,  1,  1, 1 }, { 9999, 12, 31, 1 }, { 10000, 1,  1, 0 },
        { 2026,  1, 32, 0 }, { 2026,  6, 31, 0 }, { 2026,  9, 31, 0 },
        { 2026, 11, 31, 0 }, { 2026,  7, 31, 1 },
    };
    size_t i;

    for ( i = 0; i < sizeof(cases) / sizeof(cases[0]); i++ )
        CHECK( holiday_date_valid( cases[i].y, cases[i].m, cases[i].d ) == cases[i].ok,
               "valid %04d-%02d-%02d should be %d", cases[i].y, cases[i].m, cases[i].d,
               cases[i].ok );
}

static void test_parse( void )
{
    static const struct { const char *text; int ok, y, m, d; } cases[] =
    {
        { "2026-11-02", 1, 2026, 11,  2 },
        { "2024-02-29", 1, 2024,  2, 29 },
        { "2027-02-29", 0 }, { "2026-02-30", 0 }, { "2026-13-01", 0 },
        { "2026-1-02",  0 }, { "2026-01-2",  0 }, { "26-01-02",   0 },
        { "2026-01-02x", 0 }, { " 2026-01-02", 0 }, { "2026-01-02 ", 0 },
        { "2026/01/02", 0 }, { "", 0 }, { "yesterday", 0 }, { "abcd-ef-gh", 0 },
        { "1899-12-31", 0 }, { "0000-01-01", 0 }, { "+026-01-02", 0 },
    };
    size_t i;
    int y, m, d;

    CHECK( !holiday_parse_date( NULL, &y, &m, &d ), "NULL is not a date" );
    for ( i = 0; i < sizeof(cases) / sizeof(cases[0]); i++ )
    {
        int got;

        y = m = d = -1;
        got = holiday_parse_date( cases[i].text, &y, &m, &d );
        CHECK( got == cases[i].ok, "parse '%s' should be %d", cases[i].text, cases[i].ok );
        if ( got && cases[i].ok )
            CHECK( y == cases[i].y && m == cases[i].m && d == cases[i].d,
                   "parse '%s' gave %d-%d-%d", cases[i].text, y, m, d );
    }
}

static void test_easter_and_thanksgiving( void )
{
    /* Published Gregorian Easter Sundays, the extremes included. */
    static const int easter[][3] =
    {
        { 1943, 4, 25 }, { 1961, 4,  2 }, { 2000, 4, 23 }, { 2008, 3, 23 },
        { 2011, 4, 24 }, { 2019, 4, 21 }, { 2024, 3, 31 }, { 2025, 4, 20 },
        { 2026, 4,  5 }, { 2027, 3, 28 }, { 2028, 4, 16 }, { 2029, 4,  1 },
        { 2030, 4, 21 }, { 2038, 4, 25 }, { 2285, 3, 22 },
    };
    /* The fourth Thursday of November. */
    static const int thanks[][2] =
    {
        { 2020, 26 }, { 2021, 25 }, { 2022, 24 }, { 2023, 23 }, { 2024, 28 },
        { 2025, 27 }, { 2026, 26 }, { 2027, 25 }, { 2028, 23 }, { 2030, 28 },
    };
    size_t i;
    int y;

    for ( i = 0; i < sizeof(easter) / sizeof(easter[0]); i++ )
    {
        int m, d;

        holiday_easter( easter[i][0], &m, &d );
        CHECK( m == easter[i][1] && d == easter[i][2], "Easter %d is %d-%d, got %d-%d",
               easter[i][0], easter[i][1], easter[i][2], m, d );
    }
    for ( i = 0; i < sizeof(thanks) / sizeof(thanks[0]); i++ )
        CHECK( holiday_thanksgiving( thanks[i][0] ) == thanks[i][1],
               "Thanksgiving %d is the %d, got %d", thanks[i][0], thanks[i][1],
               holiday_thanksgiving( thanks[i][0] ) );
    /* Every year: Easter is a Sunday between March 22 and April 25, and
       Thanksgiving a Thursday from the 22nd to the 28th. 1970-01-01 was a
       Thursday, so (days + 4) % 7 is 0 on a Sunday. */
    for ( y = 1900; y <= 9999; y++ )
    {
        int m, d, t;
        long day;

        holiday_easter( y, &m, &d );
        day = holiday_days_from_civil( y, m, d );
        if ( ( ( day % 7 ) + 7 + 4 ) % 7 != 0
        ||   day < holiday_days_from_civil( y, 3, 22 )
        ||   day > holiday_days_from_civil( y, 4, 25 ) )
        {
            CHECK( 0, "Easter %d (%d-%d) is not a Sunday from Mar 22 to Apr 25", y, m, d );
            break;
        }
        t = holiday_thanksgiving( y );
        day = holiday_days_from_civil( y, 11, t );
        if ( t < 22 || t > 28 || ( ( day % 7 ) + 7 + 4 ) % 7 != 4 )
        {
            CHECK( 0, "Thanksgiving %d (Nov %d) is not a Thursday from the 22nd", y, t );
            break;
        }
    }
}

static void test_cooldown( void )
{
    HOLIDAY_COOLDOWN slots[4];
    int a = 0, b = 0, c = 0, d = 0, e = 0;   /* only their addresses matter */
    const long gap = 20;

    memset( slots, 0, sizeof(slots) );
    /* A then A: the second waits the whole gap, to the second. */
    CHECK( holiday_cooldown_ready( slots, 4, &a, 1000, gap ), "A first" );
    CHECK( !holiday_cooldown_ready( slots, 4, &a, 1000, gap ), "A again at once" );
    CHECK( !holiday_cooldown_ready( slots, 4, &a, 1000 + gap - 1, gap ), "A one second short" );
    CHECK( holiday_cooldown_ready( slots, 4, &a, 1000 + gap, gap ), "A exactly at the gap" );

    /* A, B, A: B does not reset A's clock (the bug: a single "last area"). */
    memset( slots, 0, sizeof(slots) );
    CHECK( holiday_cooldown_ready( slots, 4, &a, 2000, gap ), "A" );
    CHECK( holiday_cooldown_ready( slots, 4, &b, 2001, gap ), "B after A" );
    CHECK( !holiday_cooldown_ready( slots, 4, &a, 2002, gap ), "A after B, inside A's gap" );
    CHECK( !holiday_cooldown_ready( slots, 4, &b, 2002, gap ), "B inside its own gap" );
    /* B keeps its own time. */
    CHECK( holiday_cooldown_ready( slots, 4, &a, 2000 + gap, gap ), "A at its gap" );
    CHECK( !holiday_cooldown_ready( slots, 4, &b, 2000 + gap, gap ), "B a second short" );
    CHECK( holiday_cooldown_ready( slots, 4, &b, 2001 + gap, gap ), "B at its gap" );

    /* A refused try does not restart the clock. */
    memset( slots, 0, sizeof(slots) );
    CHECK( holiday_cooldown_ready( slots, 4, &a, 3000, gap ), "A" );
    CHECK( !holiday_cooldown_ready( slots, 4, &a, 3010, gap ), "A refused" );
    CHECK( holiday_cooldown_ready( slots, 4, &a, 3000 + gap, gap ), "A at the gap from the first" );

    /* A full table reuses the oldest slot: that key fires again (errs
       toward a broadcast), the others keep their clocks. */
    memset( slots, 0, sizeof(slots) );
    CHECK( holiday_cooldown_ready( slots, 4, &a, 4000, gap ), "a" );
    CHECK( holiday_cooldown_ready( slots, 4, &b, 4001, gap ), "b" );
    CHECK( holiday_cooldown_ready( slots, 4, &c, 4002, gap ), "c" );
    CHECK( holiday_cooldown_ready( slots, 4, &d, 4003, gap ), "d" );
    CHECK( holiday_cooldown_ready( slots, 4, &e, 4004, gap ), "e takes a's slot" );
    CHECK( !holiday_cooldown_ready( slots, 4, &e, 4005, gap ), "e now waits" );
    CHECK( !holiday_cooldown_ready( slots, 4, &c, 4005, gap ), "c still waits" );
    CHECK( holiday_cooldown_ready( NULL, 0, &a, 0, gap ), "no table never refuses" );
}

int main( void )
{
    test_round_trip();
    test_validation();
    test_parse();
    test_easter_and_thanksgiving();
    test_cooldown();
    if ( failures == 0 )
        printf( "ok\n" );
    return failures != 0;
}

/*
 * tests/test_holiday_rules.c -- src/holiday_rules.c checked exactly:
 * the day arithmetic over every day from 1900 to 9999, date validation
 * and parsing, Easter and Thanksgiving against published dates, and the
 * firework cooldown table at its boundaries (review, 2026-11-02), and
 * New York's wall clock across the daylight-saving changes (the automatic
 * seasonal restart at 3am New York, 2026-11-12).
 * Prints "FAIL ..." for each failure and "ok" when there are none.
 * Built and run by tests/test_holiday_rules.py. Given the argument "ny",
 * it reads UTC epochs from stdin instead and prints each as New York's
 * "epoch y m d hour minute offset", which the Python test holds to the
 * system's America/New_York.
 */
#include <stdio.h>
#include <stdlib.h>
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

static void test_new_york( void )
{
    /* Published transitions and ordinary hours, from zoneinfo:
       epoch, then New York's y m d hour minute and the offset. */
    static const struct { long long utc; int y, m, d, h, mi; long off; } cases[] =
    {
        { 1772953199LL, 2026,  3,  8,  1, 59, -18000 },  /* a second before spring */
        { 1772953200LL, 2026,  3,  8,  3,  0, -14400 },  /* 2:00 EST is 3:00 EDT */
        { 1793512799LL, 2026, 11,  1,  1, 59, -14400 },  /* a second before autumn */
        { 1793512800LL, 2026, 11,  1,  1,  0, -18000 },  /* 1:00 again, EST */
        { 1805007600LL, 2027,  3, 14,  3,  0, -14400 },
        { 1825567200LL, 2027, 11,  7,  1,  0, -18000 },
        { 1762063199LL, 2025, 11,  2,  1, 59, -14400 },
        { 1710053999LL, 2024,  3, 10,  1, 59, -18000 },
        { 1857016800LL, 2028, 11,  5,  1,  0, -18000 },
        { 1583650800LL, 2020,  3,  8,  3,  0, -14400 },
        { 2140667999LL, 2037, 11,  1,  1, 59, -14400 },
        { 1793606400LL, 2026, 11,  2,  3,  0, -18000 },  /* Hallows End over: 3am EST */
        { 1792306800LL, 2026, 10, 18,  3,  0, -14400 },  /* Hallows End begins: 3am EDT */
        { 1797409800LL, 2026, 12, 16,  3, 30, -18000 },  /* Winter Veil */
        { 1798772400LL, 2026, 12, 31, 22,  0, -18000 },  /* UTC's new year, not New York's */
        { 1798758000LL, 2026, 12, 31, 18,  0, -18000 },
        { 0LL,          1969, 12, 31, 19,  0, -18000 },
        { -1LL,         1969, 12, 31, 18, 59, -18000 },  /* floor division before 1970 */
    };
    size_t i;
    int y;

    for ( i = 0; i < sizeof(cases) / sizeof(cases[0]); i++ )
    {
        int yy = 0, mm = 0, dd = 0, hh = -1, mi = -1;
        long off = holiday_new_york_offset( cases[i].utc );

        holiday_new_york_time( cases[i].utc, &yy, &mm, &dd, &hh, &mi );
        CHECK( off == cases[i].off && yy == cases[i].y && mm == cases[i].m
               && dd == cases[i].d && hh == cases[i].h && mi == cases[i].mi,
               "New York at %lld is %04d-%02d-%02d %02d:%02d (%ld), got "
               "%04d-%02d-%02d %02d:%02d (%ld)", cases[i].utc, cases[i].y, cases[i].m,
               cases[i].d, cases[i].h, cases[i].mi, cases[i].off, yy, mm, dd, hh, mi, off );
    }
    holiday_new_york_time( 1772953200LL, NULL, NULL, NULL, NULL, NULL );  /* NULLs are fine */

    /* Every year from 2007 (the rule's first) to 2100: walking the year a
       minute at a time, the offset changes exactly twice, from EST to EDT
       at 07:00 UTC on a Sunday from March 8 to 14 and back at 06:00 UTC on
       a Sunday from November 1 to 7; and every New York day has exactly
       sixty minutes in the 3am hour -- the restart's window -- the two
       changeover days included (2:00 to 3:00 is skipped in spring, 1:00
       to 2:00 repeated in autumn, neither touches 3:00). */
    for ( y = 2007; y <= 2100; y++ )
    {
        /* New York's January 1 to its December 31, midnight to midnight
           (EST either end). */
        long long from = (long long) holiday_days_from_civil( y, 1, 1 ) * 86400 + 5 * 3600;
        long long to   = (long long) holiday_days_from_civil( y + 1, 1, 1 ) * 86400 + 5 * 3600;
        long long t, spring = 0, autumn = 0;
        long prev = holiday_new_york_offset( from );
        int changes = 0, bad_window = 0, last_day = -1, window = 0, days = 0;

        for ( t = from; t < to; t += 60 )
        {
            long off = holiday_new_york_offset( t );
            int ny_y, ny_m, ny_d, hh, mi, key;

            if ( off != prev )
            {
                changes++;
                if ( off == -14400 )
                    spring = t;
                else
                    autumn = t;
                prev = off;
            }
            holiday_new_york_time( t, &ny_y, &ny_m, &ny_d, &hh, &mi );
            key = ny_m * 100 + ny_d;
            if ( key != last_day )
            {
                if ( last_day != -1 && window != 60 )
                    bad_window++;
                last_day = key;
                window = 0;
                days++;
            }
            if ( hh == 3 )
                window++;
        }
        if ( window != 60 )
            bad_window++;
        CHECK( changes == 2, "%d: the offset changed %d times", y, changes );
        CHECK( bad_window == 0, "%d: %d days without exactly sixty 3am minutes", y, bad_window );
        CHECK( days == 365 + ( ( y % 4 == 0 && y % 100 != 0 ) || y % 400 == 0 ),
               "%d: walked %d New York days", y, days );
        if ( spring != 0 )
        {
            int sy, sm, sd;
            long long day = spring / 86400;

            holiday_civil_from_days( (long) day, &sy, &sm, &sd );
            CHECK( spring % 86400 == 7 * 3600 && sm == 3 && sd >= 8 && sd <= 14
                   && ( ( day % 7 ) + 7 + 4 ) % 7 == 0,
                   "%d: spring forward at %lld is not 07:00 UTC on March's second Sunday",
                   y, spring );
        }
        if ( autumn != 0 )
        {
            int ay, am, ad;
            long long day = autumn / 86400;

            holiday_civil_from_days( (long) day, &ay, &am, &ad );
            CHECK( autumn % 86400 == 6 * 3600 && am == 11 && ad >= 1 && ad <= 7
                   && ( ( day % 7 ) + 7 + 4 ) % 7 == 0,
                   "%d: fall back at %lld is not 06:00 UTC on November's first Sunday",
                   y, autumn );
        }
    }
}

/* "ny": UTC epochs on stdin, New York's clock out, for the Python test. */
static int print_new_york( void )
{
    char line[64];

    while ( fgets( line, sizeof(line), stdin ) != NULL )
    {
        long long utc = strtoll( line, NULL, 10 );
        int y, m, d, h, mi;

        holiday_new_york_time( utc, &y, &m, &d, &h, &mi );
        printf( "%lld %d %d %d %d %d %ld\n", utc, y, m, d, h, mi,
                holiday_new_york_offset( utc ) );
    }
    return 0;
}

int main( int argc, char **argv )
{
    if ( argc > 1 && !strcmp( argv[1], "ny" ) )
        return print_new_york();
    test_round_trip();
    test_validation();
    test_parse();
    test_easter_and_thanksgiving();
    test_cooldown();
    test_new_york();
    if ( failures == 0 )
        printf( "ok\n" );
    return failures != 0;
}

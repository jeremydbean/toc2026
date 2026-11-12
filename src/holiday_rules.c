/*
 * holiday_rules.c -- the calendar arithmetic and the cooldown table behind
 * holiday.c, pure so tests/test_holiday_rules.c can check them exactly.
 * See holiday_rules.h.
 */
#include <stddef.h>
#include "holiday_rules.h"

/* Hinnant's days_from_civil. */
long holiday_days_from_civil( int y, int m, int d )
{
    long era, yoe, doy, doe;

    y -= m <= 2;
    era = ( y >= 0 ? y : y - 399 ) / 400;
    yoe = y - era * 400;
    doy = ( 153 * ( m + ( m > 2 ? -3 : 9 ) ) + 2 ) / 5 + d - 1;
    doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + doe - 719468;
}

/* Hinnant's civil_from_days. */
void holiday_civil_from_days( long days, int *y, int *m, int *d )
{
    long z = days + 719468;
    long era = ( z >= 0 ? z : z - 146096 ) / 146097;
    long doe = z - era * 146097;
    long yoe = ( doe - doe / 1460 + doe / 36524 - doe / 146096 ) / 365;
    long doy = doe - ( 365 * yoe + yoe / 4 - yoe / 100 );
    long mp = ( 5 * doy + 2 ) / 153;

    *d = (int)( doy - ( 153 * mp + 2 ) / 5 + 1 );
    *m = (int)( mp < 10 ? mp + 3 : mp - 9 );
    *y = (int)( yoe + era * 400 + ( *m <= 2 ) );
}

int holiday_date_valid( int y, int m, int d )
{
    static const int days_in[13] = { 0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 };
    int leap, last;

    if ( y < 1900 || y > 9999 || m < 1 || m > 12 || d < 1 )
        return 0;
    leap = ( y % 4 == 0 && y % 100 != 0 ) || y % 400 == 0;
    last = days_in[m] + ( m == 2 && leap ? 1 : 0 );
    return d <= last;
}

static int digits( const char *s, int n, int *out )
{
    int i, v = 0;

    for ( i = 0; i < n; i++ )
    {
        if ( s[i] < '0' || s[i] > '9' )
            return 0;
        v = v * 10 + ( s[i] - '0' );
    }
    *out = v;
    return 1;
}

int holiday_parse_date( const char *text, int *y, int *m, int *d )
{
    int yy, mm, dd;

    if ( text == NULL
    ||   !digits( text, 4, &yy ) || text[4] != '-'
    ||   !digits( text + 5, 2, &mm ) || text[7] != '-'
    ||   !digits( text + 8, 2, &dd ) || text[10] != '\0'
    ||   !holiday_date_valid( yy, mm, dd ) )
        return 0;
    *y = yy; *m = mm; *d = dd;
    return 1;
}

void holiday_easter( int y, int *mon, int *day )
{
    int a = y % 19, b = y / 100, c = y % 100, d = b / 4, e = b % 4;
    int f = ( b + 8 ) / 25, g = ( b - f + 1 ) / 3;
    int h = ( 19 * a + b - d - g + 15 ) % 30;
    int i = c / 4, k = c % 4;
    int l = ( 32 + 2 * e + 2 * i - h - k ) % 7;
    int m = ( a + 11 * h + 22 * l ) / 451;

    *mon = ( h + l - 7 * m + 114 ) / 31;
    *day = ( ( h + l - 7 * m + 114 ) % 31 ) + 1;
}

int holiday_thanksgiving( int y )
{
    long nov1 = holiday_days_from_civil( y, 11, 1 );
    int  wday = (int)( ( ( nov1 % 7 ) + 7 + 4 ) % 7 );   /* 0 is Sunday */
    int  first = 1 + ( 4 - wday + 7 ) % 7;

    return first + 21;
}

/* Floor division, so an epoch before 1970 still lands on its own day. */
static long long floor_div( long long a, long long b )
{
    long long q = a / b;

    return ( a % b != 0 && ( ( a < 0 ) != ( b < 0 ) ) ) ? q - 1 : q;
}

/* The day of the month of the n-th Sunday (n from 1) of y-m. 1970-01-01
   was a Thursday, so ( days + 4 ) % 7 is 0 on a Sunday. */
static int nth_sunday( int y, int m, int n )
{
    long first = holiday_days_from_civil( y, m, 1 );
    int  wday  = (int)( ( ( first % 7 ) + 7 + 4 ) % 7 );

    return 1 + ( 7 - wday ) % 7 + 7 * ( n - 1 );
}

long holiday_new_york_offset( long long utc )
{
    long long day = floor_div( utc, 86400 );
    long long start, end;
    int y, m, d;

    /* The UTC year: it differs from New York's only in the first hours
       of January 1, which are winter either way. */
    holiday_civil_from_days( (long) day, &y, &m, &d );
    start = (long long) holiday_days_from_civil( y, 3, nth_sunday( y, 3, 2 ) ) * 86400
          + 7 * 3600;
    end   = (long long) holiday_days_from_civil( y, 11, nth_sunday( y, 11, 1 ) ) * 86400
          + 6 * 3600;
    return utc >= start && utc < end ? -4L * 3600 : -5L * 3600;
}

void holiday_new_york_time( long long utc, int *y, int *m, int *d,
                            int *hour, int *minute )
{
    long long local = utc + holiday_new_york_offset( utc );
    long long day = floor_div( local, 86400 );
    long long secs = local - day * 86400;
    int yy, mm, dd;

    holiday_civil_from_days( (long) day, &yy, &mm, &dd );
    if ( y != NULL )      *y = yy;
    if ( m != NULL )      *m = mm;
    if ( d != NULL )      *d = dd;
    if ( hour != NULL )   *hour = (int)( secs / 3600 );
    if ( minute != NULL ) *minute = (int)( ( secs % 3600 ) / 60 );
}

int holiday_cooldown_ready( HOLIDAY_COOLDOWN *slots, int count,
                            const void *key, long now, long gap )
{
    int i, free_slot = -1, oldest = 0;

    if ( slots == NULL || count <= 0 )
        return 1;
    for ( i = 0; i < count; i++ )
    {
        if ( slots[i].key != NULL && slots[i].key == key )
        {
            if ( now - slots[i].at < gap )
                return 0;
            slots[i].at = now;
            return 1;
        }
        if ( slots[i].key == NULL && free_slot < 0 )
            free_slot = i;
        if ( slots[i].at < slots[oldest].at )
            oldest = i;
    }
    i = free_slot >= 0 ? free_slot : oldest;
    slots[i].key = key;
    slots[i].at = now;
    return 1;
}

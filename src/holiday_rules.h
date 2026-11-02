/*
 * The holiday calendar's arithmetic and the firework cooldown table, with
 * no game state behind them, so tests/test_holiday_rules.c can check them
 * exactly -- every boundary, every year (review, 2026-11-02). holiday.c
 * calls these; nothing here may include merc.h.
 */
#ifndef HOLIDAY_RULES_H
#define HOLIDAY_RULES_H

/* Days from 1970-01-01 to y-m-d, proleptic Gregorian, and back. */
long holiday_days_from_civil( int y, int m, int d );
void holiday_civil_from_days( long days, int *y, int *m, int *d );

/* A real, whole Gregorian date from 1900 to 9999: February 29 only in a
   leap year, no 31st of a thirty-day month. */
int  holiday_date_valid( int y, int m, int d );

/* Parse "YYYY-MM-DD" exactly: four digits, a dash, two, a dash, two, and
   nothing after, naming a valid date. True and the parts set, or false. */
int  holiday_parse_date( const char *text, int *y, int *m, int *d );

/* Easter Sunday (the anonymous Gregorian computus) and the fourth
   Thursday of November. */
void holiday_easter( int y, int *mon, int *day );
int  holiday_thanksgiving( int y );

/* One cooldown per key: true, and the key's clock started, when `now` is
   at least `gap` seconds after the key last fired (or it never has).
   Keys are compared as pointers and never dereferenced. A full table
   reuses its oldest slot, which errs toward firing. */
typedef struct holiday_cooldown
{
    const void *key;
    long        at;
} HOLIDAY_COOLDOWN;

int  holiday_cooldown_ready( HOLIDAY_COOLDOWN *slots, int count,
                             const void *key, long now, long gap );

#endif

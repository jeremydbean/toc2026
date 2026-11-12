/*
 * Checked decimal number parsing, with no game state behind it, so
 * tests/test_numparse.c can check it exactly (modernization project 2,
 * 2026-11-11: every atoi() on typed input replaced). atoi() read "5abc"
 * as 5, "abc" and "" as 0, and a number past int's range as whatever the
 * C library made of it; these refuse all of them. Nothing here may
 * include merc.h.
 */
#ifndef NUMPARSE_H
#define NUMPARSE_H

#include <limits.h>     /* INT_MIN and the rest, for the ranges callers pass */
#include <stdbool.h>

/* A whole decimal number: optional surrounding whitespace, an optional
   '+' or '-', at least one digit, and nothing else. True, and *out set,
   only when the number is all of the text and lies in [min, max]; false
   leaves *out untouched. A NULL text is refused. */
bool parse_int( const char *text, int min, int max, int *out );
bool parse_long( const char *text, long min, long max, long *out );

/* Reading a number a character at a time, as the area and player file
   readers do (fread_number and its kin, db.c): one more digit onto a
   magnitude. True, and *mag = *mag * 10 + digit, when the result is no
   more than limit; false, *mag untouched, when it would pass it -- the
   check comes before the arithmetic, so nothing overflows (review of
   d19b0e92: #4295367296 wrapped to 400000 and loaded). */
bool digit_append( unsigned long *mag, int digit, unsigned long limit );
/* a + b, true when it fits. */
bool int_add_checked( int a, int b, int *out );
bool long_add_checked( long a, long b, long *out );

#endif

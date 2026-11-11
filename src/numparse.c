/*
 * numparse.c -- checked decimal number parsing, pure so
 * tests/test_numparse.c can check it exactly. See numparse.h.
 */
#include <ctype.h>
#include <errno.h>
#include <stdlib.h>
#include "numparse.h"

bool parse_long( const char *text, long min, long max, long *out )
{
    const char *p;
    char *end;
    long value;

    if ( text == NULL || out == NULL || min > max )
        return false;

    /* strtol skips leading space and takes a sign itself, but it also
       takes "0x" in base 0 and returns 0 for no digits at all; insist on
       a digit after the sign so "", "-" and "+ 5" are refused. */
    p = text;
    while ( isspace( (unsigned char) *p ) )
        p++;
    if ( *p == '+' || *p == '-' )
        p++;
    if ( !isdigit( (unsigned char) *p ) )
        return false;

    errno = 0;
    value = strtol( text, &end, 10 );
    if ( errno == ERANGE || end == text )
        return false;
    while ( isspace( (unsigned char) *end ) )
        end++;
    if ( *end != '\0' )
        return false;
    if ( value < min || value > max )
        return false;

    *out = value;
    return true;
}

bool parse_int( const char *text, int min, int max, int *out )
{
    long value;

    if ( out == NULL || min > max )
        return false;
    if ( !parse_long( text, (long) min, (long) max, &value ) )
        return false;
    *out = (int) value;
    return true;
}

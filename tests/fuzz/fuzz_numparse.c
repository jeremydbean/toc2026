/*
 * Fuzz target (a): src/numparse.c, held to an independent reference.
 * numparse.c includes no merc.h, so this links it alone.
 *
 * Input: 2 bytes choose the bounds, the rest is the text. parse_long and
 * parse_int must agree exactly with ref_parse below (a different
 * algorithm: digits accumulated in 128 bits), digit_append with 128-bit
 * arithmetic, and the add_checked pair with 128-bit sums. A disagreement
 * aborts, and libFuzzer keeps the input.
 */
#include <ctype.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "numparse.h"

typedef __int128 wide;

/* Whitespace, an optional sign, digits, whitespace; nothing else. */
static int ref_parse( const char *text, wide min, wide max, wide *out )
{
    const char *p = text;
    int neg = 0, digits = 0;
    wide v = 0;

    while ( isspace( (unsigned char) *p ) )
        p++;
    if ( *p == '+' || *p == '-' )
        neg = *p++ == '-';
    while ( isdigit( (unsigned char) *p ) )
    {
        if ( v < (wide) 1 << 100 )
            v = v * 10 + ( *p - '0' );
        digits++;
        p++;
    }
    while ( isspace( (unsigned char) *p ) )
        p++;
    if ( digits == 0 || *p != '\0' )
        return 0;
    if ( neg )
        v = -v;
    if ( v < min || v > max )
        return 0;
    *out = v;
    return 1;
}

static const long long_bounds[] = { LONG_MIN, LONG_MIN + 1, INT_MIN, -1, 0, 1,
                                    1000000, INT_MAX, LONG_MAX - 1, LONG_MAX };
#define NBOUNDS ( sizeof(long_bounds) / sizeof(long_bounds[0]) )

static void fail( const char *what, const char *text )
{
    fprintf( stderr, "numparse disagrees with the reference: %s on \"%s\"\n",
             what, text );
    abort();
}

static long long_from( const uint8_t *data, size_t size, size_t at )
{
    long v = 0;
    size_t i;

    for ( i = 0; i < sizeof(long) && at + i < size; i++ )
        v = (long) ( ( (unsigned long) v << 8 ) | data[at + i] );
    return v;
}

int LLVMFuzzerTestOneInput( const uint8_t *data, size_t size )
{
    char *text;
    long lmin, lmax, lv = 12345;
    int imin, imax, iv = 12345;
    wide ref;
    int ok, rok;

    if ( size < 2 )
        return 0;
    lmin = long_bounds[data[0] % NBOUNDS];
    lmax = long_bounds[data[1] % NBOUNDS];
    imin = (int) ( lmin < INT_MIN ? INT_MIN : lmin > INT_MAX ? INT_MAX : lmin );
    imax = (int) ( lmax < INT_MIN ? INT_MIN : lmax > INT_MAX ? INT_MAX : lmax );

    text = malloc( size - 1 );
    if ( text == NULL )
        return 0;
    memcpy( text, data + 2, size - 2 );
    text[size - 2] = '\0';

    ok  = parse_long( text, lmin, lmax, &lv );
    rok = lmin <= lmax && ref_parse( text, lmin, lmax, &ref );
    if ( ok != rok || ( ok && lv != (long) ref ) )
        fail( "parse_long", text );
    if ( !ok && lv != 12345 )
        fail( "parse_long wrote *out on a refusal", text );

    ok  = parse_int( text, imin, imax, &iv );
    rok = imin <= imax && ref_parse( text, imin, imax, &ref );
    if ( ok != rok || ( ok && iv != (int) ref ) )
        fail( "parse_int", text );
    if ( !ok && iv != 12345 )
        fail( "parse_int wrote *out on a refusal", text );

    /* digit_append and the checked sums, on numbers taken from the input. */
    {
        unsigned long mag = (unsigned long) long_from( data, size, 2 );
        unsigned long limit = (unsigned long) long_from( data, size, 10 );
        int digit = size > 18 ? (int) ( data[18] % 12 ) - 1 : 5;
        unsigned long before = mag;
        unsigned __int128 next = (unsigned __int128) mag * 10 + (unsigned) ( digit < 0 ? 0 : digit );
        int want = digit >= 0 && digit <= 9 && next <= limit;

        if ( digit_append( &mag, digit, limit ) != want
          || ( want ? mag != (unsigned long) next : mag != before ) )
            fail( "digit_append", text );
    }
    {
        long a = long_from( data, size, 2 ), b = long_from( data, size, 10 );
        int ia = (int) a, ib = (int) b, isum = 7;
        long lsum = 7;
        wide ws = (wide) a + b, iws = (wide) ia + ib;
        int want = ws >= LONG_MIN && ws <= LONG_MAX;
        int iwant = iws >= INT_MIN && iws <= INT_MAX;

        if ( long_add_checked( a, b, &lsum ) != want || ( want && lsum != (long) ws ) )
            fail( "long_add_checked", text );
        if ( int_add_checked( ia, ib, &isum ) != iwant || ( iwant && isum != (int) iws ) )
            fail( "int_add_checked", text );
    }

    free( text );
    return 0;
}

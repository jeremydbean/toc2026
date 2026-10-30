#include "text_fold.h"

#include <ctype.h>

/*
 * A separator is written only before the next word, so a run of
 * whitespace costs one byte and only when a character follows it. Room
 * is asked for the separator, the character and the terminator together:
 * the help loader's first version asked for one byte and the terminator,
 * and a separator and a character in one step wrote its terminator one
 * past the end (review, 2026-10-30).
 */
int fold_whitespace( const char *in, char *out, size_t size, int *changed )
{
    const char *p;
    size_t n = 0;
    int pending = 0;
    int differs = 0;

    if ( size == 0 )
        return -1;
    out[0] = '\0';
    for ( p = in; *p != '\0'; p++ )
    {
        size_t need;

        if ( isspace( (unsigned char) *p ) )
        {
            if ( *p != ' ' || pending || n == 0 )
                differs = 1;
            pending = 1;
            continue;
        }
        need = ( pending && n > 0 ) ? 2 : 1;
        if ( n + need + 1 > size )
        {
            out[0] = '\0';
            return -1;
        }
        if ( pending && n > 0 )
            out[n++] = ' ';
        pending = 0;
        out[n++] = *p;
    }
    if ( pending )
        differs = 1;                    /* trailing whitespace dropped */
    out[n] = '\0';
    if ( changed != NULL )
        *changed = differs;
    return (int) n;
}

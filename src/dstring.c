#include "dstring.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define DSTRING_INITIAL_CAPACITY 64

static bool dstring_reserve( DString *str, size_t needed )
{
    size_t new_capacity;
    char *new_data;

    if (needed <= str->capacity)
        return true;

    new_capacity = str->capacity == 0 ? DSTRING_INITIAL_CAPACITY : str->capacity;
    while (new_capacity < needed)
    {
        if (new_capacity > (size_t)-1 / 2)
        {
            new_capacity = needed;
            break;
        }
        new_capacity *= 2;
    }

    new_data = realloc( str->data, new_capacity );
    if (new_data == NULL)
        return false;

    str->data = new_data;
    str->capacity = new_capacity;
    return true;
}

void dstring_init( DString *str )
{
    str->data = NULL;
    str->length = 0;
    str->capacity = 0;
    str->limit = 0;
    str->truncated = false;

    if (dstring_reserve( str, DSTRING_INITIAL_CAPACITY ))
        str->data[0] = '\0';
}

void dstring_init_limit( DString *str, size_t limit )
{
    dstring_init( str );
    str->limit = limit;
}

/* Would `more` bytes still fit under the limit? */
bool dstring_fits( const DString *str, size_t more )
{
    return str->limit == 0
        || ( more <= str->limit && str->length <= str->limit - more );
}

void dstring_init_copy( DString *str, const char *cstr )
{
    size_t len;

    dstring_init( str );
    if (cstr == NULL)
        return;

    len = strlen( cstr );
    if (!dstring_reserve( str, len + 1 ) || str->data == NULL)
        return;

    memcpy( str->data, cstr, len + 1 );
    str->length = len;
}

void dstring_free( DString *str )
{
    free( str->data );
    str->data = NULL;
    str->length = 0;
    str->capacity = 0;
}

void dstring_clear( DString *str )
{
    if (str->data != NULL)
        str->data[0] = '\0';
    str->length = 0;
    str->truncated = false;
}

bool dstring_append_cstr( DString *str, const char *text )
{
    size_t add_len;

    if (text == NULL)
        return true;

    add_len = strlen( text );
    if (!dstring_fits( str, add_len ))
    {
        str->truncated = true;
        return false;
    }
    if (!dstring_reserve( str, str->length + add_len + 1 ))
        return false;

    memcpy( str->data + str->length, text, add_len + 1 );
    str->length += add_len;
    return true;
}

bool dstring_append_char( DString *str, char c )
{
    if (!dstring_fits( str, 1 ))
    {
        str->truncated = true;
        return false;
    }
    if (!dstring_reserve( str, str->length + 2 ))
        return false;

    str->data[str->length++] = c;
    str->data[str->length] = '\0';
    return true;
}

/*
 * Append formatted text, whole or not at all: a line that would pass the
 * limit is left off and `truncated` set.
 */
bool dstring_vprintf( DString *str, const char *format, va_list args )
{
    va_list again;
    int needed;
    size_t add_len;

    va_copy( again, args );
    needed = vsnprintf( NULL, 0, format, again );
    va_end( again );
    if (needed < 0)
        return false;

    add_len = (size_t) needed;
    if (!dstring_fits( str, add_len ))
    {
        str->truncated = true;
        return false;
    }
    if (!dstring_reserve( str, str->length + add_len + 1 ))
        return false;

    vsnprintf( str->data + str->length, add_len + 1, format, args );
    str->length += add_len;
    return true;
}

bool dstring_printf( DString *str, const char *format, ... )
{
    va_list args;
    bool ok;

    va_start( args, format );
    ok = dstring_vprintf( str, format, args );
    va_end( args );
    return ok;
}

const char *dstring_cstr( const DString *str )
{
    return str->data != NULL ? str->data : "";
}

size_t dstring_length( const DString *str )
{
    return str->length;
}


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
        new_capacity *= 2;

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

    if (dstring_reserve( str, DSTRING_INITIAL_CAPACITY ))
        str->data[0] = '\0';
}

void dstring_init_copy( DString *str, const char *cstr )
{
    size_t len;

    dstring_init( str );
    if (cstr == NULL)
        return;

    len = strlen( cstr );
    if (!dstring_reserve( str, len + 1 ))
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
}

bool dstring_append_cstr( DString *str, const char *text )
{
    size_t add_len;

    if (text == NULL)
        return true;

    add_len = strlen( text );
    if (!dstring_reserve( str, str->length + add_len + 1 ))
        return false;

    memcpy( str->data + str->length, text, add_len + 1 );
    str->length += add_len;
    return true;
}

bool dstring_append_char( DString *str, char c )
{
    if (!dstring_reserve( str, str->length + 2 ))
        return false;

    str->data[str->length++] = c;
    str->data[str->length] = '\0';
    return true;
}

int dstring_printf( DString *str, const char *fmt, ... )
{
    va_list ap;
    int needed;
    int written;

    if (fmt == NULL)
    {
        dstring_clear( str );
        return 0;
    }

    va_start( ap, fmt );
    needed = vsnprintf( NULL, 0, fmt, ap );
    va_end( ap );

    if (needed < 0)
    {
        dstring_clear( str );
        return needed;
    }

    if (!dstring_reserve( str, (size_t)needed + 1 ))
    {
        dstring_clear( str );
        return -1;
    }

    va_start( ap, fmt );
    written = vsnprintf( str->data, (size_t)needed + 1, fmt, ap );
    va_end( ap );

    if (written >= 0)
        str->length = (size_t)written;
    else
        dstring_clear( str );

    return written;
}

const char *dstring_cstr( const DString *str )
{
    return str->data != NULL ? str->data : "";
}

size_t dstring_length( const DString *str )
{
    return str->length;
}


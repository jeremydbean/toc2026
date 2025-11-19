#pragma once

#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>

typedef struct dstring {
    char   *data;
    size_t  length;
    size_t  capacity;
} DString;

void    dstring_init( DString *str );
void    dstring_init_copy( DString *str, const char *cstr );
void    dstring_free( DString *str );
void    dstring_clear( DString *str );
bool    dstring_append_cstr( DString *str, const char *text );
bool    dstring_append_char( DString *str, char c );
int     dstring_printf( DString *str, const char *fmt, ... );
const char *dstring_cstr( const DString *str );
size_t  dstring_length( const DString *str );


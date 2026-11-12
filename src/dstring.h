#pragma once

#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>

/*
 * A string that grows as it is written (realloc, never alloc_mem: the
 * size-class ceiling of 32,704 bytes does not apply to it).
 *
 * A listing a player asks for -- STASH, HISTORY, NOTE LIST, WHO, a shop's
 * LIST -- is built in one of these, bounded, rather than in a fixed
 * MAX_STRING_LENGTH array that cut it short (growable output buffers,
 * 2026-11-12): dstring_init_limit( &out, DSTRING_OUTPUT_MAX ), then
 * dstring_printf / dstring_append_cstr, then page_to_char( dstring_cstr(
 * &out ), ch ) and dstring_free. An append that would pass the limit
 * appends nothing, returns false and sets `truncated`, so the caller can
 * say the rest was left off -- whole lines only, never half a colour
 * token. page_to_char sends text past its 32,000-byte pager block
 * unpaged, and write_to_buffer sends a large text in pieces, so neither
 * sink has a ceiling a bounded DString can reach.
 */
#define DSTRING_OUTPUT_MAX      ( 256 * 1024 )

typedef struct dstring {
    char   *data;
    size_t  length;
    size_t  capacity;
    size_t  limit;          /* the most `length` may reach; 0 is no limit */
    bool    truncated;      /* an append was refused at the limit */
} DString;

void    dstring_init( DString *str );
void    dstring_init_limit( DString *str, size_t limit );
void    dstring_init_copy( DString *str, const char *cstr );
void    dstring_free( DString *str );
void    dstring_clear( DString *str );
bool    dstring_append_cstr( DString *str, const char *text );
bool    dstring_append_char( DString *str, char c );
bool    dstring_printf( DString *str, const char *format, ... )
#if defined(__GNUC__)
        __attribute__(( format( printf, 2, 3 ) ))
#endif
        ;
bool    dstring_vprintf( DString *str, const char *format, va_list args );
bool    dstring_fits( const DString *str, size_t more );
const char *dstring_cstr( const DString *str );
size_t  dstring_length( const DString *str );

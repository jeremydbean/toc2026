/*
 * The permanent-memory classifier (src/memrange.c), built with
 * -fsanitize=address,pointer-compare and run with
 * ASAN_OPTIONS=detect_invalid_pointer_pairs=2 by tests/test_memory_ranges.py.
 *
 * free_mem asks whether a pointer -- usually an ordinary heap allocation --
 * lies inside one of alloc_perm's blocks, and free_string, str_dup and
 * str_perm whether a string lies in the boot string space. The old code
 * answered with <, >= between the pointer and each block's bounds: pointers
 * into different objects, which C leaves undefined and ASan reports as an
 * invalid pointer pair. This plays the same questions -- interior pointers,
 * the ends, ordinary heap blocks, blocks noted out of address order -- so
 * any relational comparison of unrelated pointers left in memrange.c stops
 * the run.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "memrange.h"

#define BLOCK   4096
#define BLOCKS  24
#define HEAPS   200

static int failures;
static int checks;

static void expect( int ok, const char *what, int n )
{
    checks++;
    if ( !ok )
    {
        failures++;
        printf( "FAIL %s (%d)\n", what, n );
    }
}

int main( void )
{
    MEM_BLOCK_SET set = { NULL, 0, 0, BLOCK };
    char *blocks[BLOCKS];
    char *heap[HEAPS];
    char *space;
    size_t used;
    int i;

    for ( i = 0; i < BLOCKS; i++ )
        if ( ( blocks[i] = calloc( 1, BLOCK ) ) == NULL )
            return 2;
    for ( i = 0; i < HEAPS; i++ )
        if ( ( heap[i] = malloc( (size_t) ( 1 + i % 97 ) ) ) == NULL )
            return 2;

    /* Noted out of address order: odd ones first, then the evens backwards. */
    for ( i = 1; i < BLOCKS; i += 2 )
        expect( mem_block_set_add( &set, blocks[i] ), "add odd", i );
    for ( i = BLOCKS - 2; i >= 0; i -= 2 )
        expect( mem_block_set_add( &set, blocks[i] ), "add even", i );
    for ( i = 1; i < set.count; i++ )
        expect( set.base[i - 1] < set.base[i], "kept sorted", i );
    printf( "ok sorted\n" );

    /* Interior pointers count, at both ends; one past the end does not. */
    for ( i = 0; i < BLOCKS; i++ )
    {
        expect( mem_block_set_has( &set, blocks[i] ), "block start", i );
        expect( mem_block_set_has( &set, blocks[i] + 1 ), "block start+1", i );
        expect( mem_block_set_has( &set, blocks[i] + BLOCK / 2 ), "block middle", i );
        expect( mem_block_set_has( &set, blocks[i] + BLOCK - 1 ), "block last byte", i );
        expect( !mem_block_set_has( &set, blocks[i] + BLOCK ), "one past the end", i );
    }
    printf( "ok interior\n" );

    /* Ordinary heap blocks, live and of every small size, are not permanent. */
    for ( i = 0; i < HEAPS; i++ )
    {
        expect( !mem_block_set_has( &set, heap[i] ), "heap block", i );
        expect( !mem_block_set_has( &set, heap[i] + i % 97 ), "heap block end", i );
    }
    {
        int on_stack = 0;

        expect( !mem_block_set_has( &set, &on_stack ), "stack", 0 );
        expect( !mem_block_set_has( &set, NULL ), "NULL", 0 );
        expect( !mem_block_set_has( &set, "a literal" ), "literal", 0 );
    }
    printf( "ok heap\n" );

    /* A string-space-like range: in it below the top, not at or past it,
       and nothing from another allocation, whichever side of it. */
    if ( ( space = calloc( 1, 8192 ) ) == NULL )
        return 2;
    used = 5000;
    expect( mem_addr_in( space, space, used ), "space start", 0 );
    expect( mem_addr_in( space + used - 1, space, used ), "space last", 0 );
    expect( !mem_addr_in( space + used, space, used ), "space top", 0 );
    expect( !mem_addr_in( space + 8191, space, used ), "space beyond top", 0 );
    expect( !mem_addr_in( space, space, 0 ), "empty space", 0 );
    expect( !mem_addr_in( NULL, space, used ), "NULL in space", 0 );
    expect( !mem_addr_in( space, NULL, used ), "no space", 0 );
    for ( i = 0; i < HEAPS; i++ )
        expect( !mem_addr_in( heap[i], space, used ), "heap in space", i );
    for ( i = 0; i < BLOCKS; i++ )
        expect( !mem_addr_in( blocks[i], space, used ), "block in space", i );
    printf( "ok space\n" );

    for ( i = 0; i < BLOCKS; i++ )
        free( blocks[i] );
    for ( i = 0; i < HEAPS; i++ )
        free( heap[i] );
    free( space );
    free( set.base );

    printf( "%d checks, %d failures\n", checks, failures );
    return failures == 0 ? 0 : 1;
}

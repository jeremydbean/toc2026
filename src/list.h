#pragma once

#include <stdbool.h>
#include <stddef.h>

/*
 * Simple, non-intrusive double-linked list for game-wide containers.
 * Nodes are allocated per insertion so callers do not need to embed
 * list pointers into their structs.
 */
typedef struct list_node
{
    void *data;
    struct list_node *prev;
    struct list_node *next;
} LIST_NODE;

typedef struct list
{
    LIST_NODE *head;
    LIST_NODE *tail;
    size_t size;
} LIST;

typedef struct list_iterator
{
    /*
     * Double-pointer cursor: points to the field (*pnext) that holds the
     * next node to yield.  When list_remove() unlinks a node it updates
     * prev->next (or list->head, which is exactly what *pnext resolves to
     * before the first call to list_iterator_next), so the iterator
     * automatically skips over any node that is removed while iterating.
     * This avoids the use-after-free that occurred when extract_char()
     * freed a LIST_NODE that was still stored in the old `next` field.
     */
    LIST_NODE **pnext;
} LIST_ITERATOR;

void    list_init( LIST *list );
LIST_NODE *list_push_front( LIST *list, void *data );
void    list_remove( LIST *list, LIST_NODE *node );
void *  list_find_first( const LIST *list, bool (*predicate)( const void *data, void *ctx ), void *ctx );
void    list_foreach( const LIST *list, void (*callback)( void *data, void *ctx ), void *ctx );
void    list_iterator_start( LIST_ITERATOR *iter, LIST *list );
void *  list_iterator_next( LIST_ITERATOR *iter );

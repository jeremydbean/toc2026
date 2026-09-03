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
    /*
     * Nodes unlinked by list_remove() are tombstoned and parked here rather
     * than freed immediately, because an active iterator may still hold a
     * cursor aliasing the removed node's `next` field.  Chained through
     * `prev`, which is meaningless once a node leaves the live list.
     * list_flush_pending() reclaims them at a point where no iteration is
     * in progress.
     */
    LIST_NODE *pending;
} LIST;

typedef struct list_iterator
{
    /*
     * Double-pointer cursor: points to the field (*pnext) that holds the
     * next node to yield.  When list_remove() unlinks a node it updates
     * prev->next (or list->head, which is exactly what *pnext resolves to
     * before the first call to list_iterator_next), so the iterator
     * automatically skips over any node that is removed while iterating.
     *
     * That handles removal of a node *ahead* of the cursor.  Removal of the
     * node the cursor sits on is handled by list_remove() tombstoning the
     * node and deferring the free: the cursor keeps aliasing valid memory,
     * the tombstoned node still points at its successor, and
     * list_iterator_next() skips tombstones.  Together these cover the
     * use-after-free that occurred when extract_char() freed a LIST_NODE
     * that an in-progress iteration was still using.
     */
    LIST_NODE **pnext;
} LIST_ITERATOR;

void    list_init( LIST *list );
LIST_NODE *list_push_front( LIST *list, void *data );
void    list_remove( LIST *list, LIST_NODE *node );
void    list_flush_pending( LIST *list );
void *  list_find_first( const LIST *list, bool (*predicate)( const void *data, void *ctx ), void *ctx );
void    list_foreach( const LIST *list, void (*callback)( void *data, void *ctx ), void *ctx );
void    list_iterator_start( LIST_ITERATOR *iter, LIST *list );
void *  list_iterator_next( LIST_ITERATOR *iter );

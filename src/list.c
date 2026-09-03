#include "merc.h"
#include "list.h"

static LIST_NODE *list_create_node( void *data )
{
    LIST_NODE *node = malloc( sizeof( *node ) );
    if ( node == NULL )
    {
        return NULL;
    }

    node->data = data;
    node->prev = NULL;
    node->next = NULL;
    return node;
}

void list_init( LIST *list )
{
    list->head = NULL;
    list->tail = NULL;
    list->size = 0;
    list->pending = NULL;
}

LIST_NODE *list_push_front( LIST *list, void *data )
{
    LIST_NODE *node = list_create_node( data );
    if ( node == NULL )
    {
        return NULL;
    }

    node->next = list->head;
    if ( list->head != NULL )
    {
        list->head->prev = node;
    }
    else
    {
        list->tail = node;
    }

    list->head = node;
    ++list->size;
    return node;
}

void list_remove( LIST *list, LIST_NODE *node )
{
    if ( list == NULL || node == NULL )
    {
        return;
    }

    if ( node->prev != NULL )
    {
        node->prev->next = node->next;
    }
    else
    {
        list->head = node->next;
    }

    if ( node->next != NULL )
    {
        node->next->prev = node->prev;
    }
    else
    {
        list->tail = node->prev;
    }

    if ( list->size > 0 )
    {
        --list->size;
    }

    /*
     * Do not free the node here.  An iterator that already yielded this node
     * holds a cursor aliasing node->next, and extract_char() removes the very
     * character a FOR_EACH_CHARACTER loop is standing on whenever a mobile
     * dies inside the loop (damage(), multi_hit(), raw_kill()).  Freeing now
     * left that cursor dangling; the read usually survived only because glibc
     * overwrites just the first 16 bytes of a freed chunk, leaving `next`
     * intact until the chunk was recycled -- an intermittent, unreproducible
     * crash.
     *
     * Instead tombstone the node and park it.  node->next still points at the
     * successor it had when it was unlinked, so a parked cursor walks forward
     * correctly, and list_iterator_next() skips tombstones so an already
     * removed element is never handed back to a caller.
     */
    node->data = NULL;
    node->prev = list->pending;
    list->pending = node;
}

void list_flush_pending( LIST *list )
{
    LIST_NODE *node;
    LIST_NODE *next;

    if ( list == NULL )
    {
        return;
    }

    /*
     * Only safe where no iteration is in progress.  Every LIST_ITERATOR in
     * the tree is a function-local, so no iteration outlives a single pass of
     * the game loop; that is where this is called from.
     */
    for ( node = list->pending; node != NULL; node = next )
    {
        next = node->prev;
        free( node );
    }

    list->pending = NULL;
}

void *list_find_first( const LIST *list, bool (*predicate)( const void *data, void *ctx ), void *ctx )
{
    LIST_NODE *current;

    if ( list == NULL || predicate == NULL )
    {
        return NULL;
    }

    for ( current = list->head; current != NULL; current = current->next )
    {
        if ( predicate( current->data, ctx ) )
        {
            return current->data;
        }
    }

    return NULL;
}

void list_foreach( const LIST *list, void (*callback)( void *data, void *ctx ), void *ctx )
{
    LIST_NODE *current;

    if ( list == NULL || callback == NULL )
    {
        return;
    }

    for ( current = list->head; current != NULL; current = current->next )
    {
        callback( current->data, ctx );
    }
}

void list_iterator_start( LIST_ITERATOR *iter, LIST *list )
{
    if ( iter == NULL )
    {
        return;
    }

    iter->pnext = ( list != NULL ) ? &list->head : NULL;
}

void *list_iterator_next( LIST_ITERATOR *iter )
{
    LIST_NODE *node;

    if ( iter == NULL || iter->pnext == NULL )
    {
        return NULL;
    }

    /*
     * Advance the cursor to point at node->next.  If list_remove() later
     * unlinks node->next, it will update node->next to skip the removed
     * entry, which is exactly the field our cursor now aliases.
     *
     * Tombstoned nodes (data == NULL) were removed while this iteration was
     * running, so skip them rather than handing back an element the game has
     * already extracted.  Walking through one is safe because list_remove()
     * defers the free and leaves node->next pointing at its successor.
     */
    while ( ( node = *iter->pnext ) != NULL )
    {
        iter->pnext = &node->next;

        if ( node->data != NULL )
        {
            return node->data;
        }
    }

    return NULL;
}

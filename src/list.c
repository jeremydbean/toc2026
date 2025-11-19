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

    free( node );
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

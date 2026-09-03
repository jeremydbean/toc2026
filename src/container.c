#include "merc.h"

LIST character_list;
LIST object_list;

static bool character_name_matches( const void *data, void *ctx )
{
    const CHAR_DATA *candidate = data;
    const char *target = ctx;

    if ( candidate == NULL || candidate->name == NULL || target == NULL )
    {
        return false;
    }

    return !str_cmp( candidate->name, target );
}

static bool object_name_matches( const void *data, void *ctx )
{
    const OBJ_DATA *candidate = data;
    const char *target = ctx;

    if ( candidate == NULL || candidate->name == NULL || target == NULL )
    {
        return false;
    }

    return is_name( target, candidate->name );
}

static void remove_entry( LIST *list, void *target )
{
    LIST_NODE *node;

    if ( list == NULL || target == NULL )
    {
        return;
    }

    for ( node = list->head; node != NULL; node = node->next )
    {
        if ( node->data == target )
        {
            list_remove( list, node );
            break;
        }
    }
}

void register_character( CHAR_DATA *ch )
{
    if ( list_push_front( &character_list, ch ) == NULL )
    {
        bug( "Unable to track character in container list", 0 );
    }
}

void unregister_character( CHAR_DATA *ch )
{
    remove_entry( &character_list, ch );
}

CHAR_DATA *find_char_by_name( const char *name )
{
    return list_find_first( &character_list, character_name_matches, (void *)(uintptr_t) name );
}

void register_object( OBJ_DATA *obj )
{
    if ( list_push_front( &object_list, obj ) == NULL )
    {
        bug( "Unable to track object in container list", 0 );
    }
}

void unregister_object( OBJ_DATA *obj )
{
    remove_entry( &object_list, obj );
}

OBJ_DATA *find_object_by_name( const char *name )
{
    return list_find_first( &object_list, object_name_matches, (void *)(uintptr_t) name );
}

/*
 * Reclaim list nodes that list_remove() tombstoned while an iteration was in
 * progress.  Call this only where no FOR_EACH_CHARACTER/FOR_EACH_OBJECT walk
 * is active; the top of the game loop is the one such point, since every
 * LIST_ITERATOR in the tree is a function-local that cannot outlive a pass.
 */
void flush_container_lists( void )
{
    list_flush_pending( &character_list );
    list_flush_pending( &object_list );
}

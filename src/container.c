#include "merc.h"

#if USE_CONTAINER_LISTS
LIST character_list;
#endif

#if USE_CONTAINER_LISTS
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
#endif

void register_character( CHAR_DATA *ch )
{
#if USE_CONTAINER_LISTS
    if ( list_push_front( &character_list, ch ) == NULL )
    {
        bugf( "Unable to track character in container list for %s", ch != NULL ? ch->name : "(null)" );
    }
#else
    UNUSED_PARAM( ch );
#endif
}

void unregister_character( CHAR_DATA *ch )
{
#if USE_CONTAINER_LISTS
    LIST_NODE *node;

    for ( node = character_list.head; node != NULL; node = node->next )
    {
        if ( node->data == ch )
        {
            list_remove( &character_list, node );
            break;
        }
    }
#else
    UNUSED_PARAM( ch );
#endif
}

CHAR_DATA *find_char_by_name( const char *name )
{
#if USE_CONTAINER_LISTS
    return list_find_first( &character_list, character_name_matches, (void *) name );
#else
    CHAR_DATA *ch;

    for ( ch = char_list; ch != NULL; ch = ch->next )
    {
        if ( ch->name != NULL && !str_cmp( ch->name, name ) )
        {
            return ch;
        }
    }

    return NULL;
#endif
}

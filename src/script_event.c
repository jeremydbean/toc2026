#include "merc.h"

/*
 * Simple linked-list dispatcher that keeps the server decoupled from any
 * particular scripting runtime. The future Lua bridge can register callbacks
 * for the high-level hooks emitted from comm.c and interp.c without forcing
 * the core loop to know about Lua headers.
 */

typedef struct script_event_listener_node script_event_listener_node;
struct script_event_listener_node
{
    script_event_type           type;
    script_event_callback       callback;
    void                       *context;
    script_event_listener_node *next;
};

static script_event_listener_node *script_event_head = NULL;

void script_event_subscribe( script_event_type type,
                             script_event_callback callback,
                             void *context )
{
    script_event_listener_node *listener;

    if ( callback == NULL )
        return;

    listener = alloc_mem( sizeof( *listener ) );
    listener->type     = type;
    listener->callback = callback;
    listener->context  = context;
    listener->next     = script_event_head;
    script_event_head  = listener;
}

void script_event_unsubscribe( script_event_callback callback, void *context )
{
    script_event_listener_node **prev = &script_event_head;

    while ( *prev != NULL )
    {
        script_event_listener_node *entry = *prev;

        if ( entry->callback == callback && entry->context == context )
        {
            *prev = entry->next;
            free_mem( entry, sizeof( *entry ) );
            continue;
        }

        prev = &entry->next;
    }
}

void script_event_emit( script_event_type type, void *payload )
{
    script_event_listener_node *listener = script_event_head;

    while ( listener != NULL )
    {
        script_event_listener_node *next = listener->next;

        if ( listener->type == type && listener->callback != NULL )
        {
            listener->callback( type, payload, listener->context );
        }

        listener = next;
    }
}

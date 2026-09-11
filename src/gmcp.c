/***************************************************************************
 * High-level GMCP messages used by the official Times of Chaos Mudlet UI. *
 *                                                                         *
 * telnet_proto.c owns option negotiation, framing, and input filtering.   *
 * This module owns package discovery and game-state JSON.                 *
 ***************************************************************************/

#include <ctype.h>
#include <stdio.h>
#include <string.h>

#include "merc.h"
#include "telnet_proto.h"

#define TOC_MUDLET_PACKAGE_VERSION "1.0.0"
#define TOC_MUDLET_PACKAGE_URL \
    "https://raw.githubusercontent.com/jeremydbean/toc2026/main/mudlet/TimesOfChaos.mpackage"
#define TOC_MUDLET_MAP_URL \
    "https://raw.githubusercontent.com/jeremydbean/toc2026/main/mudlet/toc-newbie-map.xml"

static const char * const gmcp_direction_name[10] =
{
    "n", "e", "s", "w", "u", "d", "ne", "nw", "se", "sw"
};

static const char * const gmcp_sector_name[SECT_MAX] =
{
    "inside", "city", "field", "forest", "hills", "mountains",
    "water", "deep-water", "underwater", "air", "desert", "underground"
};

static bool gmcp_token_equal( const char *message, const char *token )
{
    size_t i;
    size_t token_length;

    if ( message == NULL || token == NULL )
        return false;

    token_length = strlen( token );
    for ( i = 0; i < token_length; ++i )
    {
        if ( message[i] == '\0'
          || tolower((unsigned char)message[i])
             != tolower((unsigned char)token[i]) )
            return false;
    }

    return message[token_length] == '\0'
        || isspace((unsigned char)message[token_length]);
}

static const char *gmcp_payload( const char *message )
{
    while ( message != NULL && *message != '\0'
         && !isspace((unsigned char)*message) )
        ++message;
    while ( message != NULL && isspace((unsigned char)*message) )
        ++message;
    return message != NULL ? message : "";
}

static void gmcp_json_append_quoted( char *buffer, size_t buffer_size,
                                     const char *value )
{
    const unsigned char *cursor;
    char escaped[8];

    toc_strlcat( buffer, "\"", buffer_size );
    if ( value != NULL )
    {
        for ( cursor = (const unsigned char *)value; *cursor != '\0'; ++cursor )
        {
            switch ( *cursor )
            {
            case '\"': toc_strlcat( buffer, "\\\"", buffer_size ); break;
            case '\\': toc_strlcat( buffer, "\\\\", buffer_size ); break;
            case '\b': toc_strlcat( buffer, "\\b",  buffer_size ); break;
            case '\f': toc_strlcat( buffer, "\\f",  buffer_size ); break;
            case '\n': toc_strlcat( buffer, "\\n",  buffer_size ); break;
            case '\r': toc_strlcat( buffer, "\\r",  buffer_size ); break;
            case '\t': toc_strlcat( buffer, "\\t",  buffer_size ); break;
            default:
                if ( *cursor < 0x20 || *cursor >= 0x7f )
                {
                    snprintf( escaped, sizeof(escaped), "\\u%04x",
                              (unsigned int)*cursor );
                    toc_strlcat( buffer, escaped, buffer_size );
                }
                else
                {
                    escaped[0] = (char)*cursor;
                    escaped[1] = '\0';
                    toc_strlcat( buffer, escaped, buffer_size );
                }
                break;
            }
        }
    }
    toc_strlcat( buffer, "\"", buffer_size );
}

static const char *gmcp_area_name( const char *raw_name )
{
    const char *name;
    const char *brace;

    if ( raw_name == NULL )
        return "Unknown Area";

    name = raw_name;
    while ( isspace((unsigned char)*name) )
        ++name;

    if ( *name == '{' && (brace = strchr(name, '}')) != NULL )
    {
        name = brace + 1;
        while ( isspace((unsigned char)*name) )
            ++name;
    }

    return *name != '\0' ? name : "Unknown Area";
}

static void gmcp_reset_snapshots( DESCRIPTOR_DATA *d )
{
    if ( d == NULL )
        return;

    d->gmcp_vitals_valid = false;
    d->gmcp_status_valid = false;
    d->gmcp_last_character = NULL;
    d->gmcp_last_room = -1;
}

static void gmcp_send_initial( DESCRIPTOR_DATA *d )
{
    char json[MAX_STRING_LENGTH];

    if ( d == NULL || !d->gmcp_enabled || d->gmcp_initial_sent )
        return;

    d->gmcp_initial_sent = true;

    snprintf( json, sizeof(json), "{\"url\":\"%s\"}",
              TOC_MUDLET_MAP_URL );
    telnet_send_gmcp( d, "Client.Map", json );

    snprintf( json, sizeof(json),
              "{\"version\":\"%s\",\"url\":\"%s\"}",
              TOC_MUDLET_PACKAGE_VERSION, TOC_MUDLET_PACKAGE_URL );
    telnet_send_gmcp( d, "Client.GUI", json );
}

void gmcp_on_enabled( DESCRIPTOR_DATA *d )
{
    if ( d == NULL )
        return;

    d->gmcp_enabled = true;
    gmcp_reset_snapshots( d );
    gmcp_send_initial( d );

    if ( d->connected == CON_PLAYING )
    {
        gmcp_send_room( d );
        gmcp_send_character( d );
    }
}

void gmcp_on_disabled( DESCRIPTOR_DATA *d )
{
    if ( d == NULL )
        return;

    d->gmcp_enabled = false;
    d->gmcp_initial_sent = false;
    gmcp_reset_snapshots( d );
}

void gmcp_handle_message( DESCRIPTOR_DATA *d, const char *message )
{
    const char *payload;

    if ( d == NULL || message == NULL )
        return;

    if ( gmcp_token_equal(message, "Core.Ping") )
    {
        payload = gmcp_payload( message );
        telnet_send_gmcp( d, "Core.Ping",
                          payload[0] != '\0' ? payload : "{}" );
        return;
    }

    if ( gmcp_token_equal(message, "Core.Supports.Set")
      || gmcp_token_equal(message, "Core.Supports.Add") )
    {
        /* A package installed after login can miss the first state snapshot. */
        gmcp_send_initial( d );
        gmcp_reset_snapshots( d );
        if ( d->connected == CON_PLAYING )
        {
            gmcp_send_room( d );
            gmcp_send_character( d );
        }
    }
}

void gmcp_send_character( DESCRIPTOR_DATA *d )
{
    CHAR_DATA *ch;
    const char *class_name;
    long maximum_exp;
    long to_level;
    char json[MAX_STRING_LENGTH];
    char number[64];

    if ( d == NULL || !d->gmcp_enabled || d->connected != CON_PLAYING )
        return;

    ch = d->character;
    if ( ch == NULL )
        return;

    maximum_exp = IS_NPC(ch) ? ch->exp : next_xp_level( ch );
    to_level = maximum_exp > ch->exp ? maximum_exp - ch->exp : 0;

    if ( !d->gmcp_vitals_valid
      || d->gmcp_last_hit != ch->hit
      || d->gmcp_last_max_hit != ch->max_hit
      || d->gmcp_last_mana != ch->mana
      || d->gmcp_last_max_mana != ch->max_mana
      || d->gmcp_last_move != ch->move
      || d->gmcp_last_max_move != ch->max_move
      || d->gmcp_last_exp != ch->exp
      || d->gmcp_last_max_exp != maximum_exp )
    {
        snprintf( json, sizeof(json),
            "{\"hp\":%d,\"maxhp\":%d,\"mana\":%d,\"maxmana\":%d,"
            "\"move\":%d,\"maxmove\":%d,\"moves\":%d,\"maxmoves\":%d,"
            "\"exp\":%ld,\"maxexp\":%ld,\"tnl\":%ld,\"level\":%d}",
            ch->hit, ch->max_hit, ch->mana, ch->max_mana,
            ch->move, ch->max_move, ch->move, ch->max_move,
            ch->exp, maximum_exp, to_level, ch->level );
        telnet_send_gmcp( d, "Char.Vitals", json );

        d->gmcp_last_hit = ch->hit;
        d->gmcp_last_max_hit = ch->max_hit;
        d->gmcp_last_mana = ch->mana;
        d->gmcp_last_max_mana = ch->max_mana;
        d->gmcp_last_move = ch->move;
        d->gmcp_last_max_move = ch->max_move;
        d->gmcp_last_exp = ch->exp;
        d->gmcp_last_max_exp = maximum_exp;
        d->gmcp_vitals_valid = true;
    }

    if ( !d->gmcp_status_valid
      || d->gmcp_last_character != ch
      || d->gmcp_last_level != ch->level
      || d->gmcp_last_class != ch->class
      || d->gmcp_last_race != ch->race )
    {
        class_name = IS_NPC(ch) ? "mobile" : class_table[ch->class].name;
        toc_strlcpy( json, "{\"name\":", sizeof(json) );
        gmcp_json_append_quoted( json, sizeof(json), ch->name );
        toc_strlcat( json, ",\"level\":", sizeof(json) );
        snprintf( number, sizeof(number), "%d", ch->level );
        toc_strlcat( json, number, sizeof(json) );
        toc_strlcat( json, ",\"class\":", sizeof(json) );
        gmcp_json_append_quoted( json, sizeof(json), class_name );
        toc_strlcat( json, ",\"race\":", sizeof(json) );
        gmcp_json_append_quoted( json, sizeof(json), race_table[ch->race].name );
        toc_strlcat( json, "}", sizeof(json) );
        telnet_send_gmcp( d, "Char.Status", json );

        d->gmcp_last_character = ch;
        d->gmcp_last_level = ch->level;
        d->gmcp_last_class = ch->class;
        d->gmcp_last_race = ch->race;
        d->gmcp_status_valid = true;
    }
}

void gmcp_send_room( DESCRIPTOR_DATA *d )
{
    CHAR_DATA *ch;
    ROOM_INDEX_DATA *room;
    EXIT_DATA *exit_data;
    char json[MAX_STRING_LENGTH];
    char number[64];
    int direction;
    bool first_exit;

    if ( d == NULL || !d->gmcp_enabled || d->connected != CON_PLAYING )
        return;

    ch = d->character;
    if ( ch == NULL || ch->in_room == NULL )
        return;

    room = ch->in_room;
    if ( d->gmcp_last_room == room->vnum )
        return;

    snprintf( json, sizeof(json), "{\"num\":%d,\"name\":", room->vnum );
    gmcp_json_append_quoted( json, sizeof(json), room->name );
    toc_strlcat( json, ",\"area\":", sizeof(json) );
    gmcp_json_append_quoted( json, sizeof(json),
        room->area != NULL ? gmcp_area_name(room->area->name) : "Unknown Area" );
    toc_strlcat( json, ",\"environment\":", sizeof(json) );
    gmcp_json_append_quoted( json, sizeof(json),
        room->sector_type >= 0 && room->sector_type < SECT_MAX
            ? gmcp_sector_name[room->sector_type] : "unknown" );
    toc_strlcat( json, ",\"exits\":{", sizeof(json) );

    first_exit = true;
    for ( direction = 0; direction < 10; ++direction )
    {
        exit_data = room->exit[direction];
        if ( exit_data == NULL || exit_data->u1.to_room == NULL
          || IS_SET(exit_data->exit_info, EX_SECRET)
          || !can_see_room(ch, exit_data->u1.to_room) )
            continue;

        if ( !first_exit )
            toc_strlcat( json, ",", sizeof(json) );
        first_exit = false;
        gmcp_json_append_quoted( json, sizeof(json),
                                 gmcp_direction_name[direction] );
        toc_strlcat( json, ":", sizeof(json) );
        snprintf( number, sizeof(number), "%d", exit_data->u1.to_room->vnum );
        toc_strlcat( json, number, sizeof(json) );
    }

    toc_strlcat( json, "},\"indoors\":", sizeof(json) );
    toc_strlcat( json,
        IS_SET(room->room_flags, ROOM_INDOORS) ? "true" : "false",
        sizeof(json) );
    toc_strlcat( json, "}", sizeof(json) );
    telnet_send_gmcp( d, "Room.Info", json );

    d->gmcp_last_room = room->vnum;
}

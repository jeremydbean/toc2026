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

#define TOC_MUDLET_PACKAGE_VERSION "1.5.1"
#define TOC_MUDLET_PACKAGE_URL \
    "https://raw.githubusercontent.com/jeremydbean/toc2026/main/mudlet/TimesOfChaos.mpackage"
#define TOC_MUDLET_MAP_URL \
    "https://raw.githubusercontent.com/jeremydbean/toc2026/main/mudlet/toc-world-map.xml"

static const char * const gmcp_direction_name[10] =
{
    "n", "e", "s", "w", "u", "d", "ne", "nw", "se", "sw"
};

static const char * const gmcp_sector_name[SECT_MAX] =
{
    "inside", "city", "field", "forest", "hills", "mountains",
    "water", "deep-water", "underwater", "air", "desert", "underground"
};

#define GMCP_ROLE_MAX 5

/*
 * Room flags worth telling a client about: the ones that change how a
 * player treats a room rather than how the game implements it.
 *
 * ROOM_DT is in here and it is not the spoiler it looks like. Room.Info
 * describes the room you are standing in, and a death trap kills you on
 * the way in -- so the only character who ever receives this flag is one
 * it has already killed. What it buys is a map that remembers, which is
 * the difference between dying there once and dying there twice.
 */
static const struct
{
    long        flag;
    const char *name;
} gmcp_room_flag[] =
{
    { ROOM_DT,          "deathtrap" },
    { ROOM_SAFE,        "safe" },
    { ROOM_NO_RECALL,   "norecall" },
    { ROOM_JAIL,        "jail" },
    { ROOM_LAW,         "law" },
    { ROOM_PRIVATE,     "private" },
    { ROOM_SOLITARY,    "solitary" },
    { ROOM_NO_MOB,      "nomob" },
    { ROOM_ARENA,       "arena" },
    { ROOM_SILENT,      "silent" },
    { ROOM_PET_SHOP,    "petshop" },
    { ROOM_HP_REGEN,    "hpregen" },
    { ROOM_MANA_REGEN,  "manaregen" },
    { 0,                NULL }
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

static uint32_t gmcp_room_hash( const char *json )
{
    const unsigned char *cursor;
    uint32_t hash;

    hash = UINT32_C(2166136261);
    for ( cursor = (const unsigned char *)json; *cursor != '\0'; ++cursor )
    {
        hash ^= (uint32_t)*cursor;
        hash *= UINT32_C(16777619);
    }

    return hash;
}

static void gmcp_reset_snapshots( DESCRIPTOR_DATA *d )
{
    if ( d == NULL )
        return;

    d->gmcp_vitals_valid = false;
    d->gmcp_status_valid = false;
    d->gmcp_last_character = NULL;
    d->gmcp_last_room = -1;
    d->gmcp_last_room_hash = 0;
    d->gmcp_last_affect_hash = 0;
    d->gmcp_last_quest_hash = 0;
    d->gmcp_last_target_hash = 0;
    d->gmcp_last_online_hash = 0;
    d->gmcp_last_chars_hash = 0;
    d->gmcp_last_items_sig = 0;
    d->gmcp_affects_valid = false;
    d->gmcp_quest_valid = false;
    d->gmcp_target_valid = false;
    d->gmcp_online_valid = false;
    d->gmcp_chars_valid = false;
    d->gmcp_last_wait = -1;
    d->gmcp_last_group_hash = 0;
    d->gmcp_group_valid = false;
    d->gmcp_items_valid = false;
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
        gmcp_send_affects( d );
        gmcp_send_quest( d );
        gmcp_send_target( d );
        gmcp_send_chars( d );
        gmcp_send_items( d );
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
            gmcp_send_affects( d );
            gmcp_send_quest( d );
            gmcp_send_target( d );
            gmcp_send_chars( d );
            gmcp_send_items( d );
            gmcp_send_lag( d );
            gmcp_send_group( d );
        }
    }
}

void gmcp_send_character( DESCRIPTOR_DATA *d )
{
    CHAR_DATA *ch;
    const char *class_name;
    long maximum_exp;
    long to_level;
    int exp_pct;
    char json[MAX_STRING_LENGTH];
    char number[64];

    if ( d == NULL || !d->gmcp_enabled || d->connected != CON_PLAYING )
        return;

    ch = d->character;
    if ( ch == NULL )
        return;

    maximum_exp = IS_NPC(ch) ? ch->exp : next_xp_level( ch );
    to_level = maximum_exp > ch->exp ? maximum_exp - ch->exp : 0;

    /* Progress through the current level, 0-100, for a WoW-style bar
       that fills across the level rather than sitting near the top of a
       cumulative total. The floor is exp_per_level * level -- the baseline
       this codebase uses everywhere for "the exp to be at this level" --
       and the band runs from there to the next level's threshold. */
    {
        long floor = IS_NPC(ch) ? 0
            : (long) exp_per_level( ch, ch->pcdata->points ) * ch->level;
        long band = maximum_exp - floor;
        exp_pct = ( band > 0 && ch->exp > floor )
            ? (int) ( ( ch->exp - floor ) * 100 / band ) : 0;
        if ( exp_pct < 0 ) exp_pct = 0;
        if ( exp_pct > 100 ) exp_pct = 100;
    }

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
            "\"exp\":%ld,\"maxexp\":%ld,\"tnl\":%ld,\"level\":%d,"
            "\"exp_pct\":%d}",
            ch->hit, ch->max_hit, ch->mana, ch->max_mana,
            ch->move, ch->max_move, ch->move, ch->max_move,
            ch->exp, maximum_exp, to_level, ch->level, exp_pct );
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

/*
 * One line of channel talk, to one descriptor that has just been sent
 * it. Callers stand beside the delivery rather than guessing at the
 * audience, so there is deliberately no filtering here: if you are
 * calling this, the player heard it.
 */
/*
 * What is currently on the character, so a client can show it rather
 * than the player typing AFFECTS to find out.
 *
 * Shadowmeld is listed by hand for the same reason do_affect lists it
 * by hand: it is a bare bit in affected_by2 with no duration and no
 * AFFECT_DATA behind it, so walking ch->affected cannot see it, and a
 * melded character would otherwise be told they were affected by
 * nothing at all.
 *
 * The walk is bounded. affect_data is a linked list and a corrupt or
 * pathological one would otherwise spin here with the descriptor
 * blocked behind it.
 */
void gmcp_send_affects( DESCRIPTOR_DATA *d )
{
    CHAR_DATA *ch;
    AFFECT_DATA *paf;
    char json[MAX_STRING_LENGTH];
    char number[64];
    sh_int seen[64];
    uint32_t hash;
    int seen_count;
    int count;
    int i;
    bool first;

    if ( d == NULL || !d->gmcp_enabled || d->connected != CON_PLAYING )
        return;

    ch = d->character;
    if ( ch == NULL )
        return;

    toc_strlcpy( json, "{\"affects\":[", sizeof(json) );
    first = true;
    count = 0;
    seen_count = 0;

    for ( paf = ch->affected; paf != NULL && count < 64; paf = paf->next )
    {
        const char *name;

        count++;
        if ( paf->type < 0 || paf->type >= MAX_SKILL )
            continue;
        name = skill_table[paf->type].name;
        if ( name == NULL || name[0] == '\0' )
            continue;

        /* One row per spell. Several spells are modelled as a pair of
           affects sharing one name -- bless carries a hitroll affect
           and a saving-throw affect, both called "bless" -- and a
           list that says so twice is reporting the implementation
           rather than the character. The pair is added together with
           the same duration, so the first is as good as either. */
        for ( i = 0; i < seen_count; i++ )
            if ( seen[i] == paf->type )
                break;
        if ( i < seen_count )
            continue;
        if ( seen_count < (int)(sizeof(seen) / sizeof(seen[0])) )
            seen[seen_count++] = paf->type;

        if ( !first )
            toc_strlcat( json, ",", sizeof(json) );
        first = false;

        toc_strlcat( json, "{\"name\":", sizeof(json) );
        gmcp_json_append_quoted( json, sizeof(json), name );
        toc_strlcat( json, ",\"duration\":", sizeof(json) );
        snprintf( number, sizeof(number), "%d", paf->duration );
        toc_strlcat( json, number, sizeof(json) );
        toc_strlcat( json, ",\"level\":", sizeof(json) );
        snprintf( number, sizeof(number), "%d", paf->level );
        toc_strlcat( json, number, sizeof(json) );
        toc_strlcat( json, "}", sizeof(json) );
    }

    if ( !IS_NPC(ch) && IS_AFFECTED2(ch, AFF2_SHADOWMELD) )
    {
        if ( !first )
            toc_strlcat( json, ",", sizeof(json) );
        first = false;
        /* No duration: it holds until you leave the room, strike, or
           go visible, which is not a number of ticks. */
        toc_strlcat( json,
            "{\"name\":\"shadowmeld\",\"duration\":-1,\"level\":0}",
            sizeof(json) );
    }

    toc_strlcat( json, "]}", sizeof(json) );

    hash = gmcp_room_hash( json );
    if ( d->gmcp_affects_valid && d->gmcp_last_affect_hash == hash )
        return;

    telnet_send_gmcp( d, "Char.Affects", json );
    d->gmcp_last_affect_hash = hash;
    d->gmcp_affects_valid = true;
}


/*
 * Percent of a maximum, clamped, for a health bar. max_hit can be
 * zero or negative on a half-built mobile, and a bar is better empty
 * than dividing by it.
 */
static int gmcp_percent( long value, long maximum )
{
    if ( maximum <= 0 )
        return 0;
    if ( value <= 0 )
        return 0;
    if ( value >= maximum )
        return 100;
    return (int)( ( value * 100L ) / maximum );
}


/*
 * The quest a character is on, for a panel that can count the timer
 * down where AQUEST TIME has to be asked. The countdown moves once a
 * minute, so this re-sends about that often and no more.
 */
void gmcp_send_quest( DESCRIPTOR_DATA *d )
{
    CHAR_DATA *ch;
    MOB_INDEX_DATA *mob;
    OBJ_INDEX_DATA *obj;
    char json[MAX_STRING_LENGTH];
    char number[64];
    uint32_t hash;
    bool active;

    if ( d == NULL || !d->gmcp_enabled || d->connected != CON_PLAYING )
        return;

    ch = d->character;
    if ( ch == NULL || IS_NPC(ch) )
        return;

    active = IS_SET(ch->act, PLR_QUESTOR);

    toc_strlcpy( json, "{\"active\":", sizeof(json) );
    toc_strlcat( json, active ? "true" : "false", sizeof(json) );

    toc_strlcat( json, ",\"kind\":", sizeof(json) );
    gmcp_json_append_quoted( json, sizeof(json),
        !active ? "none"
      : ch->questemergency ? "emergency"
      : ch->questrush ? "rush" : "normal" );

    toc_strlcat( json, ",\"countdown\":", sizeof(json) );
    snprintf( number, sizeof(number), "%d", active ? (int)ch->countdown : 0 );
    toc_strlcat( json, number, sizeof(json) );

    /* What the questmaster actually asked for. */
    toc_strlcat( json, ",\"target\":", sizeof(json) );
    mob = ch->questmob > 0 ? get_mob_index( ch->questmob ) : NULL;
    obj = ch->questobj > 0 ? get_obj_index( ch->questobj ) : NULL;
    gmcp_json_append_quoted( json, sizeof(json),
          mob != NULL && mob->short_descr != NULL ? mob->short_descr
        : obj != NULL && obj->short_descr != NULL ? obj->short_descr
        : active ? "the questmaster" : "" );

    toc_strlcat( json, ",\"kill\":", sizeof(json) );
    toc_strlcat( json, mob != NULL ? "true" : "false", sizeof(json) );

    /* Where the quest master said it was last seen. Only while there is
       still a target: once it is dealt with, the next stop is the
       quest master, and the room is history. */
    {
        ROOM_INDEX_DATA *where = ( active && ( mob != NULL || obj != NULL )
                                   && ch->questroom > 0 )
                                 ? get_room_index( ch->questroom ) : NULL;

        if ( where != NULL && where->name != NULL )
        {
            char region[MAX_INPUT_LENGTH];

            quest_area_name( where->area != NULL ? where->area->name : NULL,
                             region, sizeof(region) );
            /* The target room's vnum, so the Mudlet client can walk
               there: the map keys rooms by vnum, so WALK QUEST is just
               gotoRoom(num). Only present when the target is located. */
            toc_strlcat( json, ",\"num\":", sizeof(json) );
            snprintf( number, sizeof(number), "%d", ch->questroom );
            toc_strlcat( json, number, sizeof(json) );
            toc_strlcat( json, ",\"room\":", sizeof(json) );
            gmcp_json_append_quoted( json, sizeof(json), where->name );
            toc_strlcat( json, ",\"area\":", sizeof(json) );
            gmcp_json_append_quoted( json, sizeof(json), region );
        }
    }

    toc_strlcat( json, ",\"streak\":", sizeof(json) );
    snprintf( number, sizeof(number), "%d", (int)ch->queststreak );
    toc_strlcat( json, number, sizeof(json) );

    toc_strlcat( json, ",\"points\":", sizeof(json) );
    snprintf( number, sizeof(number), "%d", ch->questpoints );
    toc_strlcat( json, number, sizeof(json) );

    /* Minutes until they may ask for another one. */
    toc_strlcat( json, ",\"wait\":", sizeof(json) );
    snprintf( number, sizeof(number), "%d", (int)ch->nextquest );
    toc_strlcat( json, number, sizeof(json) );
    toc_strlcat( json, "}", sizeof(json) );

    hash = gmcp_room_hash( json );
    if ( d->gmcp_quest_valid && d->gmcp_last_quest_hash == hash )
        return;

    telnet_send_gmcp( d, "Char.Quest", json );
    d->gmcp_last_quest_hash = hash;
    d->gmcp_quest_valid = true;
}


/*
 * Who you are fighting and how they are doing. The game says this in
 * prose -- "is in awful condition" -- which a bar can say better, and
 * which is the one number a player watches hardest.
 */
/*
 * The fight meter's figures, appended to a Char.Target object: the
 * running fight while it lasts, the last one after. Per round divides
 * by at least one, because a fight won with its opening blow has
 * damage and no completed round.
 */
static void gmcp_meter_append( char *json, size_t size, const PC_DATA *pc )
{
    char number[128];

    snprintf( number, sizeof(number),
              "\"rounds\":%d,\"damage\":%ld,\"per_round\":%ld",
              pc->meter_rounds, pc->meter_damage,
              pc->meter_damage / UMAX( 1, pc->meter_rounds ) );
    toc_strlcat( json, number, size );
}


void gmcp_send_target( DESCRIPTOR_DATA *d )
{
    CHAR_DATA *ch;
    CHAR_DATA *victim;
    const PC_DATA *pc;
    char json[MAX_STRING_LENGTH];
    char number[64];
    uint32_t hash;

    if ( d == NULL || !d->gmcp_enabled || d->connected != CON_PLAYING )
        return;

    ch = d->character;
    if ( ch == NULL )
        return;

    victim = ch->fighting;
    /* A switched character is driving a mobile, which keeps no meter. */
    pc = IS_NPC(ch) ? NULL : ch->pcdata;

    if ( victim == NULL || !can_see( ch, victim ) )
    {
        toc_strlcpy( json, "{\"fighting\":false", sizeof(json) );
        if ( pc != NULL && ( pc->meter_rounds > 0 || pc->meter_damage > 0 ) )
        {
            toc_strlcat( json, ",\"last\":{", sizeof(json) );
            gmcp_meter_append( json, sizeof(json), pc );
            toc_strlcat( json, "}", sizeof(json) );
        }
        toc_strlcat( json, "}", sizeof(json) );
    }
    else
    {
        toc_strlcpy( json, "{\"fighting\":true,\"name\":", sizeof(json) );
        gmcp_json_append_quoted( json, sizeof(json), PERS( victim, ch ) );
        toc_strlcat( json, ",\"level\":", sizeof(json) );
        snprintf( number, sizeof(number), "%d", victim->level );
        toc_strlcat( json, number, sizeof(json) );
        toc_strlcat( json, ",\"percent\":", sizeof(json) );
        snprintf( number, sizeof(number), "%d",
                  gmcp_percent( victim->hit, victim->max_hit ) );
        toc_strlcat( json, number, sizeof(json) );
        if ( pc != NULL )
        {
            toc_strlcat( json, ",", sizeof(json) );
            gmcp_meter_append( json, sizeof(json), pc );
        }
        toc_strlcat( json, "}", sizeof(json) );
    }

    hash = gmcp_room_hash( json );
    if ( d->gmcp_target_valid && d->gmcp_last_target_hash == hash )
        return;

    telnet_send_gmcp( d, "Char.Target", json );
    d->gmcp_last_target_hash = hash;
    d->gmcp_target_valid = true;
}


/*
 * Who else is on, as far as you could tell -- the client's online
 * roster. online_can_list() decides, not can_see(), so the list does not
 * flicker with a concealment roll. Names only, alphabetical, and the
 * count is of the names sent: a hidden player is not a number either.
 */
/* An ordering, which str_cmp() is not: it answers only whether two
   strings differ, so as a qsort comparator it left the roster in no
   order at all. Found by the hero plaque's test. */
static int gmcp_name_order( const void *a, const void *b )
{
    const char *x = *(const char * const *) a;
    const char *y = *(const char * const *) b;

    while ( *x != '\0' && LOWER(*x) == LOWER(*y) )
    {
        x++;
        y++;
    }
    return LOWER(*x) - LOWER(*y);
}


void gmcp_send_online( DESCRIPTOR_DATA *d )
{
    CHAR_DATA *ch;
    DESCRIPTOR_DATA *od;
    const char *names[128];
    char json[MAX_STRING_LENGTH];
    char number[32];
    uint32_t hash;
    int count = 0;
    int i;

    if ( d == NULL || !d->gmcp_enabled || d->connected != CON_PLAYING )
        return;

    ch = d->original ? d->original : d->character;
    if ( ch == NULL )
        return;

    for ( od = descriptor_list; od != NULL; od = od->next )
    {
        CHAR_DATA *wch;

        if ( od->connected != CON_PLAYING || od->character == NULL )
            continue;
        wch = od->original ? od->original : od->character;

        /* WHO's own rule: a switched immortal stays out of sight of
           anybody below it. */
        if ( od->original != NULL && get_trust( ch ) < 67 )
            continue;
        if ( !online_can_list( ch, wch ) )
            continue;
        if ( count < (int)( sizeof(names) / sizeof(names[0]) ) )
            names[count++] = wch->name;
    }

    qsort( names, (size_t) count, sizeof(names[0]), gmcp_name_order );

    snprintf( number, sizeof(number), "{\"count\":%d,", count );
    toc_strlcpy( json, number, sizeof(json) );
    toc_strlcat( json, "\"players\":[", sizeof(json) );
    for ( i = 0; i < count; i++ )
    {
        if ( i > 0 )
            toc_strlcat( json, ",", sizeof(json) );
        gmcp_json_append_quoted( json, sizeof(json), names[i] );
    }
    toc_strlcat( json, "]}", sizeof(json) );

    hash = gmcp_room_hash( json );
    if ( d->gmcp_online_valid && d->gmcp_last_online_hash == hash )
        return;

    telnet_send_gmcp( d, "Char.Online", json );
    d->gmcp_last_online_hash = hash;
    d->gmcp_online_valid = true;
}


/*
 * How long until the character can act again, for a lag bar.
 *
 * Sent when the wait *changes* -- an action that lagged, or the wait
 * running down or out -- and never while it sits at zero, so a quiet
 * character costs nothing. It rides the output flush like every other
 * feed rather than firing per pulse, which is what keeps it from
 * flooding the link four times a second. The client drains its bar
 * between messages; each one is the authoritative remainder, so a
 * client clock that drifts is corrected by the next.
 *
 * Staff are never held by a wait (comm.c skips it for IS_IMMORTAL), so
 * they are sent no lag rather than a bar for a pause that never comes.
 */
void gmcp_send_lag( DESCRIPTOR_DATA *d )
{
    CHAR_DATA *ch;
    char json[64];
    int wait;

    if ( d == NULL || !d->gmcp_enabled || d->connected != CON_PLAYING )
        return;

    ch = d->character;
    if ( ch == NULL )
        return;

    wait = IS_IMMORTAL( ch ) ? 0 : UMAX( 0, (int) ch->wait );

    /* Only when a fresh wait is applied (or extended), and once when it
       clears. The steady per-pulse decrements in between are predictable,
       so the client drains its own bar rather than being told four times
       a second -- the whole point of not flooding the link. */
    if ( wait > d->gmcp_last_wait
      || ( wait == 0 && d->gmcp_last_wait > 0 ) )
    {
        snprintf( json, sizeof(json), "{\"ms\":%d}",
                  wait * ( 1000 / PULSE_PER_SECOND ) );
        telnet_send_gmcp( d, "Char.Lag", json );
    }
    d->gmcp_last_wait = wait;
}


/*
 * The group you are in, for a party panel: each member's level and
 * how they are holding up, whether they are the leader and whether
 * they are in the room with you.
 *
 * Players only, walked off the descriptor list -- a pet or a charmed
 * mobile follows its master but is not a party member, and walking the
 * whole character list for every flush would cost thousands of checks
 * to find a handful of people. Alone is not a group: a list of one,
 * which is only you, is sent empty so a solo player draws nothing.
 */
#define GMCP_GROUP_MAX 16

void gmcp_send_group( DESCRIPTOR_DATA *d )
{
    CHAR_DATA *ch;
    DESCRIPTOR_DATA *od;
    char json[MAX_STRING_LENGTH];
    char number[192];
    uint32_t hash;
    int count = 0;

    if ( d == NULL || !d->gmcp_enabled || d->connected != CON_PLAYING )
        return;

    ch = d->character;
    if ( ch == NULL )
        return;

    toc_strlcpy( json, "{\"members\":[", sizeof(json) );
    for ( od = descriptor_list; od != NULL && count < GMCP_GROUP_MAX;
          od = od->next )
    {
        CHAR_DATA *gch;

        if ( od->connected != CON_PLAYING || od->character == NULL )
            continue;
        gch = od->character;
        if ( !is_same_group( ch, gch ) )
            continue;

        if ( count > 0 )
            toc_strlcat( json, ",", sizeof(json) );
        toc_strlcat( json, "{\"name\":", sizeof(json) );
        gmcp_json_append_quoted( json, sizeof(json),
            IS_NPC(gch) ? gch->short_descr : gch->name );
        snprintf( number, sizeof(number),
            ",\"level\":%d,\"hp\":%d,\"mana\":%d,\"move\":%d,"
            "\"leader\":%s,\"here\":%s,\"you\":%s}",
            gch->level,
            gmcp_percent( gch->hit, gch->max_hit ),
            gmcp_percent( gch->mana, gch->max_mana ),
            gmcp_percent( gch->move, gch->max_move ),
            gch->leader == NULL ? "true" : "false",
            gch->in_room == ch->in_room ? "true" : "false",
            gch == ch ? "true" : "false" );
        toc_strlcat( json, number, sizeof(json) );
        count++;
    }
    toc_strlcat( json, "]}", sizeof(json) );

    if ( count < 2 )
        toc_strlcpy( json, "{\"members\":[]}", sizeof(json) );

    hash = gmcp_room_hash( json );
    if ( d->gmcp_group_valid && d->gmcp_last_group_hash == hash )
        return;

    telnet_send_gmcp( d, "Char.Group", json );
    d->gmcp_last_group_hash = hash;
    d->gmcp_group_valid = true;
}


/*
 * Who and what is in the room with you. Room.Info says what the room
 * is for; this says who is standing in it, which changes constantly
 * and so is its own message rather than another field there.
 */
void gmcp_send_chars( DESCRIPTOR_DATA *d )
{
    CHAR_DATA *ch;
    CHAR_DATA *rch;
    char json[MAX_STRING_LENGTH];
    char number[64];
    uint32_t hash;
    int count;
    bool first;

    if ( d == NULL || !d->gmcp_enabled || d->connected != CON_PLAYING )
        return;

    ch = d->character;
    if ( ch == NULL || ch->in_room == NULL )
        return;

    toc_strlcpy( json, "{\"chars\":[", sizeof(json) );
    first = true;
    count = 0;

    for ( rch = ch->in_room->people; rch != NULL && count < 40;
          rch = rch->next_in_room )
    {
        if ( rch == ch || !can_see( ch, rch ) )
            continue;
        count++;

        if ( !first )
            toc_strlcat( json, ",", sizeof(json) );
        first = false;

        toc_strlcat( json, "{\"name\":", sizeof(json) );
        gmcp_json_append_quoted( json, sizeof(json), PERS( rch, ch ) );
        toc_strlcat( json, ",\"npc\":", sizeof(json) );
        toc_strlcat( json, IS_NPC(rch) ? "true" : "false", sizeof(json) );
        toc_strlcat( json, ",\"aggressive\":", sizeof(json) );
        toc_strlcat( json,
            IS_NPC(rch) && IS_SET(rch->act, ACT_AGGRESSIVE) ? "true" : "false",
            sizeof(json) );
        toc_strlcat( json, ",\"level\":", sizeof(json) );
        snprintf( number, sizeof(number), "%d", rch->level );
        toc_strlcat( json, number, sizeof(json) );
        toc_strlcat( json, ",\"percent\":", sizeof(json) );
        snprintf( number, sizeof(number), "%d",
                  gmcp_percent( rch->hit, rch->max_hit ) );
        toc_strlcat( json, number, sizeof(json) );
        toc_strlcat( json, ",\"fighting\":", sizeof(json) );
        toc_strlcat( json, rch->fighting != NULL ? "true" : "false",
                     sizeof(json) );
        toc_strlcat( json, "}", sizeof(json) );
    }

    toc_strlcat( json, "]}", sizeof(json) );

    hash = gmcp_room_hash( json );
    if ( d->gmcp_chars_valid && d->gmcp_last_chars_hash == hash )
        return;

    telnet_send_gmcp( d, "Room.Chars", json );
    d->gmcp_last_chars_hash = hash;
    d->gmcp_chars_valid = true;
}


/*
 * What is carried and what is worn.
 *
 * Unlike the others this hashes a cheap signature rather than the
 * finished payload: an inventory runs to dozens of items, this is
 * called from the main loop, and building all that string only to
 * throw it away four times a second is work nobody asked for. The
 * signature is integer arithmetic over the vnums and wear slots,
 * which is what a change to either would move.
 */
static uint32_t gmcp_items_signature( CHAR_DATA *ch )
{
    OBJ_DATA *obj;
    uint32_t sig = 2166136261u;
    int count = 0;

    for ( obj = ch->carrying; obj != NULL && count < 200; obj = obj->next_content )
    {
        count++;
        sig = ( sig ^ (uint32_t)( obj->pIndexData != NULL
                                ? obj->pIndexData->vnum : 0 ) ) * 16777619u;
        sig = ( sig ^ (uint32_t)( obj->wear_loc + 2 ) ) * 16777619u;
    }

    return sig ^ (uint32_t)count;
}


void gmcp_send_items( DESCRIPTOR_DATA *d )
{
    CHAR_DATA *ch;
    OBJ_DATA *obj;
    char json[MAX_STRING_LENGTH];
    char number[64];
    uint32_t sig;
    int count;
    bool first;

    if ( d == NULL || !d->gmcp_enabled || d->connected != CON_PLAYING )
        return;

    ch = d->character;
    if ( ch == NULL )
        return;

    sig = gmcp_items_signature( ch );
    if ( d->gmcp_items_valid && d->gmcp_last_items_sig == sig )
        return;

    toc_strlcpy( json, "{\"inventory\":[", sizeof(json) );
    first = true;
    count = 0;

    for ( obj = ch->carrying; obj != NULL && count < 100;
          obj = obj->next_content )
    {
        if ( obj->wear_loc != WEAR_NONE || !can_see_obj( ch, obj ) )
            continue;
        count++;

        if ( !first )
            toc_strlcat( json, ",", sizeof(json) );
        first = false;
        toc_strlcat( json, "{\"name\":", sizeof(json) );
        gmcp_json_append_quoted( json, sizeof(json),
            obj->short_descr != NULL ? obj->short_descr : "something" );
        toc_strlcat( json, "}", sizeof(json) );
    }

    toc_strlcat( json, "],\"equipment\":[", sizeof(json) );
    first = true;
    count = 0;

    for ( obj = ch->carrying; obj != NULL && count < 100;
          obj = obj->next_content )
    {
        if ( obj->wear_loc == WEAR_NONE || !can_see_obj( ch, obj ) )
            continue;
        count++;

        if ( !first )
            toc_strlcat( json, ",", sizeof(json) );
        first = false;
        toc_strlcat( json, "{\"name\":", sizeof(json) );
        gmcp_json_append_quoted( json, sizeof(json),
            obj->short_descr != NULL ? obj->short_descr : "something" );
        toc_strlcat( json, ",\"slot\":", sizeof(json) );
        snprintf( number, sizeof(number), "%d", obj->wear_loc );
        toc_strlcat( json, number, sizeof(json) );
        toc_strlcat( json, "}", sizeof(json) );
    }

    toc_strlcat( json, "]}", sizeof(json) );

    telnet_send_gmcp( d, "Char.Items", json );
    d->gmcp_last_items_sig = sig;
    d->gmcp_items_valid = true;
}


/*
 * One achievement, at the moment it is earned. Sent from the same
 * branch that prints the banner, so a client is told exactly when the
 * player is told and never for the silent catch-up awards a login can
 * hand out in bulk.
 */
void gmcp_send_achievement( CHAR_DATA *ch, const char *title,
                            const char *description, int points, int total )
{
    char json[MAX_STRING_LENGTH];
    char number[64];

    if ( ch == NULL || ch->desc == NULL || title == NULL )
        return;
    if ( !ch->desc->gmcp_enabled || ch->desc->connected != CON_PLAYING )
        return;

    toc_strlcpy( json, "{\"title\":", sizeof(json) );
    gmcp_json_append_quoted( json, sizeof(json), title );
    toc_strlcat( json, ",\"description\":", sizeof(json) );
    gmcp_json_append_quoted( json, sizeof(json),
                             description != NULL ? description : "" );
    toc_strlcat( json, ",\"points\":", sizeof(json) );
    snprintf( number, sizeof(number), "%d", points );
    toc_strlcat( json, number, sizeof(json) );
    toc_strlcat( json, ",\"total\":", sizeof(json) );
    snprintf( number, sizeof(number), "%d", total );
    toc_strlcat( json, number, sizeof(json) );
    toc_strlcat( json, "}", sizeof(json) );

    telnet_send_gmcp( ch->desc, "Char.Achievement", json );
}


void gmcp_send_channel( DESCRIPTOR_DATA *d, const char *channel,
                        const char *speaker, const char *text )
{
    char json[MAX_STRING_LENGTH];
    char number[64];

    if ( d == NULL || !d->gmcp_enabled || d->connected != CON_PLAYING )
        return;
    if ( channel == NULL || text == NULL )
        return;

    toc_strlcpy( json, "{\"channel\":", sizeof(json) );
    gmcp_json_append_quoted( json, sizeof(json), channel );
    toc_strlcat( json, ",\"speaker\":", sizeof(json) );
    gmcp_json_append_quoted( json, sizeof(json),
                             speaker != NULL ? speaker : "" );
    toc_strlcat( json, ",\"text\":", sizeof(json) );
    gmcp_json_append_quoted( json, sizeof(json), text );

    /* The colour this listener chose for the channel, so the client's
       chat window matches its main window. Absent with colour off. */
    {
        CHAR_DATA *who = d->original != NULL ? d->original : d->character;
        const char *colour = who != NULL
            ? color_name( who, channel_color_category( channel ) ) : NULL;

        if ( colour != NULL )
        {
            toc_strlcat( json, ",\"color\":", sizeof(json) );
            gmcp_json_append_quoted( json, sizeof(json), colour );
        }
    }
    toc_strlcat( json, ",\"time\":", sizeof(json) );
    snprintf( number, sizeof(number), "%ld", (long)current_time );
    toc_strlcat( json, number, sizeof(json) );
    toc_strlcat( json, "}", sizeof(json) );

    telnet_send_gmcp( d, "Comm.Channel", json );
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
    uint32_t room_hash;

    if ( d == NULL || !d->gmcp_enabled || d->connected != CON_PLAYING )
        return;

    ch = d->character;
    if ( ch == NULL || ch->in_room == NULL )
        return;

    room = ch->in_room;

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

    /*
     * Doors, for the exits listed above. A client that knows a door is
     * shut can open it before walking into it rather than after; one
     * that does not spends a timeout finding out.
     */
    toc_strlcat( json, "},\"doors\":{", sizeof(json) );

    first_exit = true;
    for ( direction = 0; direction < 10; ++direction )
    {
        const char *state;

        exit_data = room->exit[direction];
        if ( exit_data == NULL || exit_data->u1.to_room == NULL
          || IS_SET(exit_data->exit_info, EX_SECRET)
          || !IS_SET(exit_data->exit_info, EX_ISDOOR)
          || !can_see_room(ch, exit_data->u1.to_room) )
            continue;

        state = IS_SET(exit_data->exit_info, EX_LOCKED) ? "locked"
              : IS_SET(exit_data->exit_info, EX_CLOSED) ? "closed"
              : "open";

        if ( !first_exit )
            toc_strlcat( json, ",", sizeof(json) );
        first_exit = false;
        gmcp_json_append_quoted( json, sizeof(json),
                                 gmcp_direction_name[direction] );
        toc_strlcat( json, ":", sizeof(json) );
        gmcp_json_append_quoted( json, sizeof(json), state );
    }

    toc_strlcat( json, "},\"flags\":[", sizeof(json) );

    first_exit = true;
    for ( direction = 0; gmcp_room_flag[direction].name != NULL; ++direction )
    {
        if ( !IS_SET(room->room_flags, gmcp_room_flag[direction].flag) )
            continue;
        if ( !first_exit )
            toc_strlcat( json, ",", sizeof(json) );
        first_exit = false;
        gmcp_json_append_quoted( json, sizeof(json),
                                 gmcp_room_flag[direction].name );
    }

    /*
     * What the room is for. A shopkeeper or a guildmaster is the reason
     * to come back to a room and the reason to label it on a map. These
     * are services and not an inventory of who is standing about, so a
     * mobile wandering through changes nothing and does not churn the
     * payload hash.
     */
    toc_strlcat( json, "],\"services\":[", sizeof(json) );

    first_exit = true;
    {
        static const char * const role_name[GMCP_ROLE_MAX] =
            { "shop", "quest", "practice", "train", "healer" };
        CHAR_DATA *rch;
        bool seen[GMCP_ROLE_MAX];
        int index;

        for ( index = 0; index < GMCP_ROLE_MAX; ++index )
            seen[index] = false;

        for ( rch = room->people; rch != NULL; rch = rch->next_in_room )
        {
            int role = -1;

            if ( !IS_NPC(rch) || !can_see(ch, rch) )
                continue;

            if ( rch->pIndexData != NULL && rch->pIndexData->pShop != NULL )
                role = 0;
            else if ( IS_SET(rch->act, ACT_QUESTM) )
                role = 1;
            else if ( IS_SET(rch->act, ACT_PRACTICE) )
                role = 2;
            else if ( IS_SET(rch->act, ACT_TRAIN) )
                role = 3;
            else if ( IS_SET(rch->act, ACT_IS_HEALER) )
                role = 4;

            /* Two shopkeepers in a room is one "shop", not two. */
            if ( role < 0 || seen[role] )
                continue;
            seen[role] = true;

            if ( !first_exit )
                toc_strlcat( json, ",", sizeof(json) );
            first_exit = false;
            gmcp_json_append_quoted( json, sizeof(json), role_name[role] );
        }
    }

    toc_strlcat( json, "],\"indoors\":", sizeof(json) );
    toc_strlcat( json,
        IS_SET(room->room_flags, ROOM_INDOORS) ? "true" : "false",
        sizeof(json) );
    toc_strlcat( json, "}", sizeof(json) );

    room_hash = gmcp_room_hash( json );
    if ( d->gmcp_last_room == room->vnum
      && d->gmcp_last_room_hash == room_hash )
        return;

    telnet_send_gmcp( d, "Room.Info", json );

    d->gmcp_last_room = room->vnum;
    d->gmcp_last_room_hash = room_hash;
}

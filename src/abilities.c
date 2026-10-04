/***************************************************************************
 * abilities.c -- what a character can learn, what they have, and who
 * teaches the rest.
 *
 * Owner, 2026-10-04: a player can level for weeks without knowing a whole
 * group of spells is theirs for the asking -- Alaric reached 28 as a
 * necromancer without the life & undeath group that raises his servants.
 * GAINLIST (ABILITIES is the same command) lists every skill and spell this
 * character's class and guild can learn, ticked or crossed, and for each
 * purchase still missing says what to GAIN, from whom, where, and how to
 * WALKTO them; the Oracle is handed the same list when asked. GAINLIST
 * TRAINERS is the old list of what each trainer sells. Nothing is announced
 * at a level gain: a player may know full well what they have not bought,
 * and does not need telling every level (owner).
 *
 * What counts as learnable is what the game's own GAIN would give this
 * character, read from guildmaster_table with do_gain's rules: a group a
 * trainer who serves them sells (rated above 0 for their class), or a
 * single skill sold on its own. Psionics, which are granted rather than
 * bought, are summarised on their own line.
 ***************************************************************************/

#include <string.h>
#include "merc.h"
#include "magic.h"

#define ABILITY_NONE (-1)

/* Where one ability can be had: the guildmaster_table row that sells it,
   the group it comes in (or -1 sold on its own), and what it costs. */
typedef struct ability_source
{
    int gm;
    int group;
    int cost;
} ABILITY_SOURCE;

/* One thing to GAIN that would bring missing abilities: a group, or a
   single skill (sn set, group -1). */
typedef struct ability_buy
{
    int gm;
    int group;
    int sn;
    int cost;
    int lowest;     /* the lowest level among what it brings that is missing */
} ABILITY_BUY;

/* do_gain's test: whether this trainer row will deal with this character. */
static bool gm_serves( const struct guildmaster_type *gm, CHAR_DATA *ch )
{
    if ( gm->class == CLASS_OTHER && ch->class == gm->guild )
        return FALSE;
    if ( gm->class != CLASS_ANY && gm->class != CLASS_OTHER
    &&   ch->class != gm->class )
        return FALSE;
    if ( gm->guild != GUILD_ANY && ch->pcdata->guild != gm->guild )
        return FALSE;
    return TRUE;
}

/* Every skill a group gives, one level of nesting deep ("necro default"
   names "necromancy"), as gn_add hands them out. */
static void group_skills( int gn, bool *out )
{
    int i;

    for ( i = 0; i < MAX_IN_GROUP && group_table[gn].spells[i] != NULL; i++ )
    {
        int inner = group_lookup( group_table[gn].spells[i] );
        int sn;

        if ( inner >= 0 && inner != gn )
        {
            int j;

            for ( j = 0; j < MAX_IN_GROUP && group_table[inner].spells[j] != NULL; j++ )
                if ( ( sn = skill_lookup( group_table[inner].spells[j] ) ) >= 0 )
                    out[sn] = TRUE;
            continue;
        }
        if ( ( sn = skill_lookup( group_table[gn].spells[i] ) ) >= 0 )
            out[sn] = TRUE;
    }
}

/* The cheapest place to GAIN each skill this character's class and guild
   can buy. */
static void ability_sources( CHAR_DATA *ch, ABILITY_SOURCE *src )
{
    int sn, row, i;

    for ( sn = 0; sn < MAX_SKILL; sn++ )
    {
        src[sn].gm = ABILITY_NONE;
        src[sn].group = ABILITY_NONE;
        src[sn].cost = 0;
    }

    for ( row = 0; guildmaster_table[row].vnum != 0; row++ )
    {
        const struct guildmaster_type *gm = &guildmaster_table[row];

        if ( !gm_serves( gm, ch ) || get_mob_index( gm->vnum ) == NULL )
            continue;

        for ( i = 0; i < MAX_GAIN && gm->can_gain[i] != NULL; i++ )
        {
            int gn = group_lookup( gm->can_gain[i] );

            if ( gn > 0 )
            {
                bool in_group[MAX_SKILL];
                int cost = group_table[gn].rating[ch->class];

                if ( cost <= 0 )
                    continue;
                memset( in_group, 0, sizeof(in_group) );
                group_skills( gn, in_group );
                for ( sn = 0; sn < MAX_SKILL; sn++ )
                    if ( in_group[sn]
                    &&   ( src[sn].gm == ABILITY_NONE || cost < src[sn].cost ) )
                    {
                        src[sn].gm = row;
                        src[sn].group = gn;
                        src[sn].cost = cost;
                    }
                continue;
            }

            /* A single skill. GAIN refuses a spell outside a group. */
            if ( ( sn = skill_lookup( gm->can_gain[i] ) ) >= 0
            &&   skill_table[sn].spell_fun == spell_null
            &&   skill_table[sn].rating[ch->class] > 0
            &&   ( src[sn].gm == ABILITY_NONE
                || skill_table[sn].rating[ch->class] < src[sn].cost ) )
            {
                src[sn].gm = row;
                src[sn].group = ABILITY_NONE;
                src[sn].cost = skill_table[sn].rating[ch->class];
            }
        }
    }
}

/* Whether this skill belongs in the list at all for this character. */
static bool ability_listed( CHAR_DATA *ch, int sn, const ABILITY_SOURCE *src )
{
    int level;

    if ( skill_table[sn].name == NULL || is_psionic_sn( sn ) )
        return FALSE;
    level = skill_table[sn].skill_level[ch->class];
    if ( level < 0 || level >= LEVEL_IMMORTAL )
        return FALSE;
    /* Held already (a class's own basics, a remort gift), or for sale. */
    return ch->pcdata->learned[sn] > 0 || src[sn].gm != ABILITY_NONE;
}

static bool ability_missing( CHAR_DATA *ch, int sn, const ABILITY_SOURCE *src )
{
    return ability_listed( ch, sn, src ) && ch->pcdata->learned[sn] <= 0;
}

/* Gather the purchases that would bring what is missing, one per group or
   single skill, ordered by the lowest level among what each brings. */
static int ability_buys( CHAR_DATA *ch, const ABILITY_SOURCE *src, ABILITY_BUY *buys )
{
    int sn, n = 0, i, j;

    for ( sn = 0; sn < MAX_SKILL; sn++ )
    {
        int level;

        if ( !ability_missing( ch, sn, src ) )
            continue;
        level = skill_table[sn].skill_level[ch->class];
        for ( i = 0; i < n; i++ )
            if ( buys[i].gm == src[sn].gm
            &&   ( src[sn].group != ABILITY_NONE
                   ? buys[i].group == src[sn].group : buys[i].sn == sn ) )
                break;
        if ( i == n )
        {
            if ( n >= MAX_SKILL )
                continue;
            buys[n].gm = src[sn].gm;
            buys[n].group = src[sn].group;
            buys[n].sn = src[sn].group == ABILITY_NONE ? sn : ABILITY_NONE;
            buys[n].cost = src[sn].cost;
            buys[n].lowest = level;
            n++;
        }
        else if ( level < buys[i].lowest )
            buys[i].lowest = level;
    }

    for ( i = 1; i < n; i++ )
        for ( j = i; j > 0 && buys[j].lowest < buys[j - 1].lowest; j-- )
        {
            ABILITY_BUY t = buys[j];

            buys[j] = buys[j - 1];
            buys[j - 1] = t;
        }
    return n;
}

/* A trainer's name without its article, where to find them, and what to
   type after WALKTO -- from the WALKTO destinations, which name every
   trainer's home; failing that, from wherever one stands right now. */
static void trainer_where( int row, char *name, size_t name_size,
                           char *place, size_t place_size,
                           char *walk, size_t walk_size )
{
    MOB_INDEX_DATA *idx = get_mob_index( guildmaster_table[row].vnum );
    const char *s = idx != NULL ? idx->short_descr : "a trainer";
    size_t len;

    if ( !str_prefix( "the ", s ) )
        s += 4;
    else if ( !str_prefix( "a ", s ) )
        s += 2;
    toc_strlcpy( name, s, name_size );
    len = strlen( name );
    while ( len > 0 && ( name[len - 1] == '.' || name[len - 1] == ' ' ) )
        name[--len] = '\0';

    if ( walkto_trainer_place( name, place, place_size, walk, walk_size ) )
        return;

    toc_strlcpy( walk, "", walk_size );
    toc_strlcpy( place, "not in the world right now", place_size );
    if ( idx != NULL )
    {
        LIST_ITERATOR iter;
        CHAR_DATA *wch;

        FOR_EACH_CHARACTER( iter, wch )
            if ( IS_NPC(wch) && wch->pIndexData == idx && wch->in_room != NULL )
            {
                toc_strlcpy( place, wch->in_room->name, place_size );
                break;
            }
    }
}

/* What a purchase brings that is missing: "create skeleton 15, ...". */
static void buy_contents( CHAR_DATA *ch, const ABILITY_SOURCE *src,
                          const ABILITY_BUY *b, char *out, size_t size )
{
    char item[MAX_INPUT_LENGTH];
    int sn;
    bool first = TRUE;

    out[0] = '\0';
    for ( sn = 0; sn < MAX_SKILL; sn++ )
    {
        if ( !ability_missing( ch, sn, src ) || src[sn].gm != b->gm )
            continue;
        if ( b->group != ABILITY_NONE ? src[sn].group != b->group : sn != b->sn )
            continue;
        snprintf( item, sizeof(item), "%s%s %d", first ? "" : ", ",
                  skill_table[sn].name, skill_table[sn].skill_level[ch->class] );
        toc_strlcat( out, item, size );
        first = FALSE;
    }
}

/* Append text to out, breaking lines before 78 columns under a 5-space
   indent; *col is the current column. */
static void ability_wrap( char *out, size_t size, size_t *col, const char *text )
{
    const char *p = text;

    while ( *p != '\0' )
    {
        const char *end = strchr( p, ' ' );
        size_t word = end != NULL ? (size_t)( end - p ) : strlen( p );
        char piece[MAX_INPUT_LENGTH];

        if ( *col > 5 && *col + 1 + word > 77 )
        {
            toc_strlcat( out, "\n\r     ", size );
            *col = 5;
        }
        else if ( *col > 5 )
        {
            toc_strlcat( out, " ", size );
            (*col)++;
        }
        if ( word >= sizeof(piece) )
            word = sizeof(piece) - 1;
        memcpy( piece, p, word );
        piece[word] = '\0';
        toc_strlcat( out, piece, size );
        *col += word;
        p += word;
        while ( *p == ' ' )
            p++;
    }
}

static int psionics_held( CHAR_DATA *ch )
{
    int sn, held = 0;

    for ( sn = 0; sn < MAX_SKILL; sn++ )
        if ( skill_table[sn].name != NULL && is_psionic_sn( sn )
        &&   ch->pcdata->learned[sn] > 0 )
            held++;
    return held;
}

static void show_abilities( CHAR_DATA *ch )
{
    static ABILITY_SOURCE src[MAX_SKILL];
    static ABILITY_BUY buys[MAX_SKILL];
    static char out[32768];
    char buf[2 * MAX_STRING_LENGTH];
    char what[MAX_STRING_LENGTH];
    char name[MAX_INPUT_LENGTH];
    char place[MAX_INPUT_LENGTH];
    char walk[MAX_INPUT_LENGTH];
    int sn, i, nbuys, col = 0;
    int learned = 0, missing = 0;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
    {
        send_to_char( "Only players have abilities to learn.\n\r", ch );
        return;
    }

    ability_sources( ch, src );
    for ( sn = 0; sn < MAX_SKILL; sn++ )
    {
        if ( !ability_listed( ch, sn, src ) )
            continue;
        if ( ch->pcdata->learned[sn] > 0 )
            learned++;
        else
            missing++;
    }
    nbuys = ability_buys( ch, src, buys );

    out[0] = '\0';
    snprintf( buf, sizeof(buf),
              "{0BAbilities for a level %d %s%s%s%s:{00 %d learned, %s%d not yet{00.\n\r\n\r",
              ch->level, class_table[ch->class].name,
              ch->pcdata->guild >= 0 && ch->pcdata->guild < MAX_CLASS ? " of the " : "",
              ch->pcdata->guild >= 0 && ch->pcdata->guild < MAX_CLASS
                  ? get_guildname( ch->pcdata->guild ) : "",
              ch->pcdata->guild >= 0 && ch->pcdata->guild < MAX_CLASS ? " guild" : "",
              learned, missing > 0 ? "{0C" : "", missing );
    toc_strlcat( out, buf, sizeof(out) );

    if ( nbuys > 0 )
    {
        toc_strlcat( out, "{0BNot yet learned{00 ({0CX{00 usable now, - at a later level), "
                          "and what to GAIN:\n\r", sizeof(out) );
        for ( i = 0; i < nbuys; i++ )
        {
            size_t wcol;
            bool now = buys[i].lowest <= ch->level;

            trainer_where( buys[i].gm, name, sizeof(name), place, sizeof(place),
                           walk, sizeof(walk) );
            buy_contents( ch, src, &buys[i], what, sizeof(what) );
            if ( buys[i].group != ABILITY_NONE )
                snprintf( buf, sizeof(buf), " %s %s (group, %d train%s):",
                          now ? "{0CX{00" : "-", group_table[buys[i].group].name,
                          buys[i].cost, buys[i].cost == 1 ? "" : "s" );
            else
                snprintf( buf, sizeof(buf), " %s %s (%d train%s):",
                          now ? "{0CX{00" : "-", skill_table[buys[i].sn].name,
                          buys[i].cost, buys[i].cost == 1 ? "" : "s" );
            toc_strlcat( out, buf, sizeof(out) );
            /* the visible width of what was just written */
            wcol = strlen( buf ) - ( now ? 6 : 0 );
            if ( buys[i].group != ABILITY_NONE )
                ability_wrap( out, sizeof(out), &wcol, what );
            snprintf( buf, sizeof(buf), "\n\r     %s, %s%s%s\n\r", name, place,
                      walk[0] != '\0' ? " -- walkto " : "", walk );
            toc_strlcat( out, buf, sizeof(out) );
        }
        toc_strlcat( out, "\n\r", sizeof(out) );
    }

    if ( learned > 0 )
    {
        toc_strlcat( out, "{0BLearned{00 ({0A+{00):\n\r", sizeof(out) );
        for ( sn = 0; sn < MAX_SKILL; sn++ )
        {
            if ( !ability_listed( ch, sn, src ) || ch->pcdata->learned[sn] <= 0 )
                continue;
            snprintf( buf, sizeof(buf), " {0A+{00 %-18s %3d%%",
                      skill_table[sn].name, ch->pcdata->learned[sn] );
            toc_strlcat( out, buf, sizeof(out) );
            if ( ++col % 3 == 0 )
                toc_strlcat( out, "\n\r", sizeof(out) );
        }
        if ( col % 3 != 0 )
            toc_strlcat( out, "\n\r", sizeof(out) );
        toc_strlcat( out, "\n\r", sizeof(out) );
    }

    snprintf( buf, sizeof(buf),
              "Psionic powers: %d of 17 held. They awaken between levels 18 and 21\n\r"
              "for those owed them (a second remort, or a gift); Salir the Monk\n\r"
              "trains them -- walkto salir.\n\r", psionics_held( ch ) );
    toc_strlcat( out, buf, sizeof(out) );
    toc_strlcat( out, "GAINLIST TRAINERS lists what each of your trainers sells.\n\r",
                 sizeof(out) );

    page_to_char( out, ch );
}

/*
 * The same list, on one line, for the Oracle: handed to her with every
 * question so "what am I missing" is answered from the game, with the
 * trainer and the WALKTO to reach them. No tab or line break may appear in
 * it -- it rides in the question spool's last field.
 */
void abilities_oracle_summary( CHAR_DATA *ch, char *out, size_t size )
{
    static ABILITY_SOURCE src[MAX_SKILL];
    static ABILITY_BUY buys[MAX_SKILL];
    char what[MAX_STRING_LENGTH];
    char item[2 * MAX_STRING_LENGTH];
    char name[MAX_INPUT_LENGTH];
    char place[MAX_INPUT_LENGTH];
    char walk[MAX_INPUT_LENGTH];
    int sn, i, nbuys, learned = 0;

    out[0] = '\0';
    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return;

    ability_sources( ch, src );
    for ( sn = 0; sn < MAX_SKILL; sn++ )
        if ( ability_listed( ch, sn, src ) && ch->pcdata->learned[sn] > 0 )
            learned++;
    nbuys = ability_buys( ch, src, buys );

    snprintf( out, size, "level %d %s%s%s; %d skills and spells learned; psionics %d"
              " of 17; not yet learned (each: what to GAIN, the trains, the abilities"
              " it brings with the level each is usable at, the trainer, where, and"
              " the WALKTO):",
              ch->level, class_table[ch->class].name,
              ch->pcdata->guild >= 0 && ch->pcdata->guild < MAX_CLASS ? ", guild " : "",
              ch->pcdata->guild >= 0 && ch->pcdata->guild < MAX_CLASS
                  ? get_guildname( ch->pcdata->guild ) : "",
              learned, psionics_held( ch ) );
    for ( i = 0; i < nbuys; i++ )
    {
        trainer_where( buys[i].gm, name, sizeof(name), place, sizeof(place),
                       walk, sizeof(walk) );
        buy_contents( ch, src, &buys[i], what, sizeof(what) );
        snprintf( item, sizeof(item), " %s%s (%d trains; %s) from %s, %s%s%s;",
                  buys[i].group != ABILITY_NONE ? "group " : "",
                  buys[i].group != ABILITY_NONE ? group_table[buys[i].group].name
                                                : skill_table[buys[i].sn].name,
                  buys[i].cost, what, name, place,
                  walk[0] != '\0' ? ", walkto " : "", walk );
        if ( strlen( out ) + strlen( item ) + 1 >= size )
            break;
        toc_strlcat( out, item, size );
    }
    if ( nbuys == 0 )
        toc_strlcat( out, " nothing -- everything their class and guild can buy is learned.",
                     size );
}

/* GAINLIST and ABILITIES: the list above; GAINLIST TRAINERS the old one. */
void do_gainlist( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];

    one_argument( argument, arg );
    if ( arg[0] != '\0' && !str_prefix( arg, "trainers" ) )
    {
        gainlist_by_trainer( ch, "" );
        return;
    }
    show_abilities( ch );
}

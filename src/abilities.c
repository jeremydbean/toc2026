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
#include "interp.h"
#include "combat_rules.h"
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

/* do_gain's test: whether this trainer row will deal with a character of
   this class and guild. */
static bool gm_serves_build( const struct guildmaster_type *gm, int cls, int guild )
{
    if ( gm->class == CLASS_OTHER && cls == gm->guild )
        return FALSE;
    if ( gm->class != CLASS_ANY && gm->class != CLASS_OTHER
    &&   cls != gm->class )
        return FALSE;
    if ( gm->guild != GUILD_ANY && guild != gm->guild )
        return FALSE;
    return TRUE;
}

/* Every skill a group gives, through nested groups ("necro default"
   names "necromancy"), exactly as gn_add hands them out: group_add reads
   a member as a skill first and only then as a group. Asking the group
   first took "harm" for the "harmful" group, both prefix matches, and
   listed cause serious and cause critical for builds that never get them
   (class review, 2026-10-26). */
static void group_skills_depth( int gn, bool *out, int depth )
{
    int i;

    for ( i = 0; i < MAX_IN_GROUP && group_table[gn].spells[i] != NULL; i++ )
    {
        int sn = skill_lookup( group_table[gn].spells[i] );
        int inner;

        if ( sn >= 0 )
        {
            out[sn] = TRUE;
            continue;
        }
        inner = group_lookup( group_table[gn].spells[i] );
        if ( inner >= 0 && inner != gn && depth < 4 )
            group_skills_depth( inner, out, depth + 1 );
    }
}

static void group_skills( int gn, bool *out )
{
    group_skills_depth( gn, out, 0 );
}

/* The cheapest place to GAIN each skill a class and guild can buy. */
static void ability_sources_build( int cls, int guild, ABILITY_SOURCE *src )
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

        if ( !gm_serves_build( gm, cls, guild ) || get_mob_index( gm->vnum ) == NULL )
            continue;

        for ( i = 0; i < MAX_GAIN && gm->can_gain[i] != NULL; i++ )
        {
            int gn = group_lookup( gm->can_gain[i] );

            if ( gn > 0 )
            {
                bool in_group[MAX_SKILL];
                int cost = group_table[gn].rating[cls];

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
            &&   skill_table[sn].rating[cls] > 0
            &&   ( src[sn].gm == ABILITY_NONE
                || skill_table[sn].rating[cls] < src[sn].cost ) )
            {
                src[sn].gm = row;
                src[sn].group = ABILITY_NONE;
                src[sn].cost = skill_table[sn].rating[cls];
            }
        }
    }
}

/* The same for this character's own class and guild. */
static void ability_sources( CHAR_DATA *ch, ABILITY_SOURCE *src )
{
    ability_sources_build( ch->class, ch->pcdata->guild, src );
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
static void ability_wrap( DString *out, size_t *col, const char *text )
{
    const char *p = text;

    while ( *p != '\0' )
    {
        const char *end = strchr( p, ' ' );
        size_t word = end != NULL ? (size_t)( end - p ) : strlen( p );
        char piece[MAX_INPUT_LENGTH];

        if ( *col > 5 && *col + 1 + word > 77 )
        {
            dstring_append_cstr( out, "\n\r     " );
            *col = 5;
        }
        else if ( *col > 5 )
        {
            dstring_append_cstr( out, " " );
            (*col)++;
        }
        if ( word >= sizeof(piece) )
            word = sizeof(piece) - 1;
        memcpy( piece, p, word );
        piece[word] = '\0';
        dstring_append_cstr( out, piece );
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
    DString out;        /* grown as it is written (2026-11-12) */
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

    dstring_init_limit( &out, DSTRING_OUTPUT_MAX );
    snprintf( buf, sizeof(buf),
              "{0BAbilities for a level %d %s%s%s%s:{00 %d learned, %s%d not yet{00.\n\r\n\r",
              ch->level, class_table[ch->class].name,
              ch->pcdata->guild >= 0 && ch->pcdata->guild < MAX_CLASS ? " of the " : "",
              ch->pcdata->guild >= 0 && ch->pcdata->guild < MAX_CLASS
                  ? get_guildname( ch->pcdata->guild ) : "",
              ch->pcdata->guild >= 0 && ch->pcdata->guild < MAX_CLASS ? " guild" : "",
              learned, missing > 0 ? "{0C" : "", missing );
    dstring_append_cstr( &out, buf );

    if ( nbuys > 0 )
    {
        dstring_append_cstr( &out, "{0BNot yet learned{00 ({0CX{00 usable now, - at a later level), "
                          "and what to GAIN:\n\r" );
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
            dstring_append_cstr( &out, buf );
            /* the visible width of what was just written */
            wcol = strlen( buf ) - ( now ? 6 : 0 );
            if ( buys[i].group != ABILITY_NONE )
                ability_wrap( &out, &wcol, what );
            snprintf( buf, sizeof(buf), "\n\r     %s, %s%s%s\n\r", name, place,
                      walk[0] != '\0' ? " -- walkto " : "", walk );
            dstring_append_cstr( &out, buf );
        }
        dstring_append_cstr( &out, "\n\r" );
    }

    if ( learned > 0 )
    {
        dstring_append_cstr( &out, "{0BLearned{00 ({0A+{00):\n\r" );
        for ( sn = 0; sn < MAX_SKILL; sn++ )
        {
            if ( !ability_listed( ch, sn, src ) || ch->pcdata->learned[sn] <= 0 )
                continue;
            snprintf( buf, sizeof(buf), " {0A+{00 %-18s %3d%%",
                      skill_table[sn].name, ch->pcdata->learned[sn] );
            dstring_append_cstr( &out, buf );
            if ( ++col % 3 == 0 )
                dstring_append_cstr( &out, "\n\r" );
        }
        if ( col % 3 != 0 )
            dstring_append_cstr( &out, "\n\r" );
        dstring_append_cstr( &out, "\n\r" );
    }

    snprintf( buf, sizeof(buf),
              "Psionic powers: %d of 17 held. They awaken between levels 18 and 21\n\r"
              "for those owed them (a second remort, or a gift); Salir the Monk\n\r"
              "trains them -- walkto salir.\n\r", psionics_held( ch ) );
    dstring_append_cstr( &out, buf );
    dstring_append_cstr( &out, "GAINLIST TRAINERS lists what each of your trainers sells.\n\r" );

    page_to_char( dstring_cstr( &out ), ch );
    dstring_free( &out );
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

/*
 * GAINLIST PREVIEW <class> <guild>: what any build would learn, level by
 * level, before anybody commits a life to it (class review, 2026-10-26).
 * Read from the same tables and GAIN rules as the list above: what the
 * class and guild are given, and what a trainer serving them sells, at the
 * level the class's column opens it. Monks and necromancers have their own
 * paths and take no guild.
 */
static int preview_class( const char *arg )
{
    int i;

    for ( i = 0; i < MAX_CLASS; i++ )
        if ( arg[0] != '\0' && !str_prefix( arg, class_table[i].name ) )
            return i;
    return -1;
}

static void preview_given( int cls, int guild, bool *given )
{
    const char *groups[4];
    int i, gn;

    groups[0] = "rom basics";
    groups[1] = class_table[cls].base_group;
    groups[2] = class_table[cls].default_group;
    groups[3] = guild_group_name( guild );
    memset( given, 0, sizeof(bool) * MAX_SKILL );
    for ( i = 0; i < 4; i++ )
        if ( groups[i] != NULL && ( gn = group_lookup( groups[i] ) ) >= 0 )
            group_skills( gn, given );
}

/* Whether a build of this class can hold sn at all, and how. */
static bool preview_holds( int cls, int sn, const bool *given, const ABILITY_SOURCE *src )
{
    int level;

    if ( skill_table[sn].name == NULL || is_psionic_sn( sn ) )
        return FALSE;
    level = skill_table[sn].skill_level[cls];
    if ( level < 1 || level >= LEVEL_IMMORTAL )
        return FALSE;
    return given[sn] || src[sn].gm != ABILITY_NONE;
}

static void build_preview( CHAR_DATA *ch, int cls, int guild )
{
    static ABILITY_SOURCE src[MAX_SKILL], own_src[MAX_SKILL];
    static bool given[MAX_SKILL], own_given[MAX_SKILL];
    static int order[MAX_SKILL];
    DString out;        /* grown as it is written (2026-11-12) */
    char buf[MAX_STRING_LENGTH];
    int seen_gm[MAX_SKILL], seen_key[MAX_SKILL];
    int sn, i, j, n = 0, bought = 0, trains = 0, nseen = 0, col = 0;
    static const int marks[4] = { 10, 25, 40, 50 };

    ability_sources_build( cls, guild, src );
    preview_given( cls, guild, given );

    for ( sn = 0; sn < MAX_SKILL; sn++ )
    {
        int key;

        if ( !preview_holds( cls, sn, given, src ) )
            continue;
        order[n++] = sn;
        if ( given[sn] )
            continue;
        bought++;
        /* A group is paid for once, however many of its spells it brings. */
        key = src[sn].group != ABILITY_NONE ? -1 - src[sn].group : sn;
        for ( i = 0; i < nseen; i++ )
            if ( seen_gm[i] == src[sn].gm && seen_key[i] == key )
                break;
        if ( i == nseen && nseen < MAX_SKILL )
        {
            seen_gm[nseen] = src[sn].gm;
            seen_key[nseen++] = key;
            trains += src[sn].cost;
        }
    }
    for ( i = 1; i < n; i++ )
        for ( j = i; j > 0
              && skill_table[order[j]].skill_level[cls] < skill_table[order[j - 1]].skill_level[cls];
              j-- )
        {
            int tmp = order[j];

            order[j] = order[j - 1];
            order[j - 1] = tmp;
        }

    dstring_init_limit( &out, DSTRING_OUTPUT_MAX );
    if ( cls == CLASS_MONK || cls == CLASS_NECRO )
        snprintf( buf, sizeof(buf), "{0BA %s, level by level:{00\n\r", class_table[cls].name );
    else
        snprintf( buf, sizeof(buf), "{0BA %s of the %s guild, level by level:{00\n\r",
                  class_table[cls].name, get_guildname( guild ) );
    dstring_append_cstr( &out, buf );
    snprintf( buf, sizeof(buf),
              "%d abilities: %d given, %d more to GAIN (* below) for %d trains in all.\n\r\n\r",
              n, n - bought, bought, trains );
    dstring_append_cstr( &out, buf );

    for ( i = 0; i < n; i++ )
    {
        sn = order[i];
        snprintf( buf, sizeof(buf), " %2d %s%-19.19s",
                  skill_table[sn].skill_level[cls], given[sn] ? " " : "*",
                  skill_table[sn].name );
        dstring_append_cstr( &out, buf );
        if ( ++col % 3 == 0 )
            dstring_append_cstr( &out, "\n\r" );
    }
    if ( col % 3 != 0 )
        dstring_append_cstr( &out, "\n\r" );

    /* Swings a round before haste, as multi_hit rolls them: two sure, and
       each extra swing a chance, not a sure blow (review, 2026-10-27: this
       printed four for a warrior, who expects 2.73 at full skill). Shown
       at full skill; dual wield apart, since it needs a weapon in the
       off hand. */
    {
        int dual_from = -1, x;

        snprintf( buf, sizeof(buf), "\n\rSwings a round at full skill, before haste: two "
                  "sure, then second attack %d%%, third attack %d%%.\n\r",
                  swing_chance_percent( 100 / 2 ), swing_chance_percent( 100 / 4 ) );
        dstring_append_cstr( &out, buf );
        for ( i = 0; i < 4; i++ )
        {
            int second = preview_holds( cls, gsn_second_attack, given, src )
                      && skill_table[gsn_second_attack].skill_level[cls] <= marks[i] ? 100 : 0;
            int third = preview_holds( cls, gsn_third_attack, given, src )
                     && skill_table[gsn_third_attack].skill_level[cls] <= marks[i] ? 100 : 0;

            x = expected_swings_x100( second, third, 0, 0 );
            snprintf( buf, sizeof(buf), "  level %d: %d.%02d", marks[i], x / 100, x % 100 );
            dstring_append_cstr( &out, buf );
        }
        dstring_append_cstr( &out, "\n\r" );
        if ( preview_holds( cls, gsn_dual_wield, given, src ) )
            dual_from = skill_table[gsn_dual_wield].skill_level[cls];
        if ( dual_from >= 0 && dual_from < LEVEL_IMMORTAL )
        {
            x = swing_chance_percent( ( 100 + 100 ) / 5 );
            snprintf( buf, sizeof(buf), "  Dual wield, with a weapon in the off hand: "
                      "+0.%02d a round from level %d.\n\r", x, dual_from );
            dstring_append_cstr( &out, buf );
        }
    }

    /* What this guild costs or gives against the class's own. */
    if ( cls < CLASS_MONK && guild != cls )
    {
        char gains[MAX_STRING_LENGTH], loses[MAX_STRING_LENGTH];
        size_t gcol = 0, lcol = 0;

        ability_sources_build( cls, cls, own_src );
        preview_given( cls, cls, own_given );
        gains[0] = loses[0] = '\0';
        for ( sn = 0; sn < MAX_SKILL; sn++ )
        {
            bool here = preview_holds( cls, sn, given, src );
            bool own = preview_holds( cls, sn, own_given, own_src );

            if ( here && !own )
            {
                snprintf( buf, sizeof(buf), "%s%s", gcol++ ? ", " : "", skill_table[sn].name );
                toc_strlcat( gains, buf, sizeof(gains) );
            }
            else if ( own && !here )
            {
                snprintf( buf, sizeof(buf), "%s%s", lcol++ ? ", " : "", skill_table[sn].name );
                toc_strlcat( loses, buf, sizeof(loses) );
            }
        }
        snprintf( buf, sizeof(buf), "Against a %s in the %s guild, this adds:",
                  class_table[cls].name, get_guildname( cls ) );
        dstring_append_cstr( &out, "\n\r" );
        dstring_append_cstr( &out, buf );
        gcol = strlen( buf );
        ability_wrap( &out, &gcol, gains[0] != '\0' ? gains : "nothing" );
        dstring_append_cstr( &out, "\n\rand gives up:" );
        lcol = 13;
        ability_wrap( &out, &lcol, loses[0] != '\0' ? loses : "nothing" );
        dstring_append_cstr( &out, "\n\r" );
    }
    dstring_append_cstr( &out, "\n\rA level is the earliest the class can use it. GAINLIST shows your own.\n\r" );
    page_to_char( dstring_cstr( &out ), ch );
    dstring_free( &out );
}

static void gainlist_preview( CHAR_DATA *ch, char *argument )
{
    char carg[MAX_INPUT_LENGTH], garg[MAX_INPUT_LENGTH];
    int cls, guild;

    argument = one_argument( argument, carg );
    one_argument( argument, garg );
    if ( ( cls = preview_class( carg ) ) < 0 )
    {
        send_to_char( "Syntax: gainlist preview <class> <guild>\n\r"
                      "  class: mage, cleric, thief, warrior, monk or necromancer\n\r"
                      "  guild: mage, cleric, thief or warrior (monks and necromancers have none)\n\r", ch );
        return;
    }
    if ( cls == CLASS_MONK || cls == CLASS_NECRO )
        guild = cls;
    else if ( ( guild = preview_class( garg ) ) < 0 || guild >= CLASS_MONK )
    {
        send_to_char( "Which guild? gainlist preview <class> <mage|cleric|thief|warrior>\n\r", ch );
        return;
    }
    build_preview( ch, cls, guild );
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
    if ( arg[0] != '\0' && !str_prefix( arg, "preview" ) )
    {
        gainlist_preview( ch, one_argument( argument, arg ) );
        return;
    }
    show_abilities( ch );
}

/*
 * JOIN SWITCH <guild> CONFIRM at the guild clerk (2026-11-15): one change
 * of guild in a first life, at level 15 or below, for a mage, cleric,
 * thief or warrior already in one of those four guilds.
 *
 * Taken back is what the old guild alone gave: its own group (free), and
 * every group or single skill held that a trainer sells to this class in
 * the old guild and no trainer sells it in the new one -- what GAIN would
 * not have let them buy as the new guild. Each of those is refunded in full:
 * the trains GAIN took for it (its rating for the class) and the practices
 * spent past 1% (at today's intelligence, rounded the player's way, as the
 * stray-mage-groups fix refunds). Then the new guild's group is given free,
 * everything the class, race and new guild owe is given back by the same
 * repair a login runs (apply_class_and_guild_skills), and anything owed
 * either way keeps the percentage it had. A warrior who leaves the
 * warriors' guild loses Hero's Grip, which that guild alone gives.
 *
 * Without CONFIRM it runs exactly that on the character and puts every
 * field it touched back, so the preview is the change. With CONFIRM it is
 * done once a milestone snapshot is on the disk ("guildswitch"), marked
 * (GuildSwitched, case 'G') and saved.
 */
#define GUILD_SWITCH_MAX_LEVEL 15

static bool four_guild( int guild )
{
    return guild == GUILD_MAGE || guild == GUILD_CLERIC || guild == GUILD_THIEF
        || guild == GUILD_WARRIOR;
}

/* Whether some trainer that deals with this class and guild sells the group
   (gn) or, with gn -1, the single skill sn. */
static bool sold_to( int cls, int guild, int gn, int sn )
{
    int row, i;

    for ( row = 0; guildmaster_table[row].vnum != 0; row++ )
    {
        const struct guildmaster_type *gm = &guildmaster_table[row];

        if ( !gm_serves_build( gm, cls, guild ) || get_mob_index( gm->vnum ) == NULL )
            continue;
        for ( i = 0; i < MAX_GAIN && gm->can_gain[i] != NULL; i++ )
        {
            if ( gn > 0 && group_lookup( gm->can_gain[i] ) == gn )
                return TRUE;
            if ( gn <= 0 && sn >= 0 && group_lookup( gm->can_gain[i] ) <= 0
            &&   skill_lookup( gm->can_gain[i] ) == sn )
                return TRUE;
        }
    }
    return FALSE;
}

/* The switch itself, on the character as it is. Fills the report and the
   refunds; returns whether anything at all changed hands. */
static void guild_switch_apply( CHAR_DATA *ch, int new_guild, DString *report,
                                int *trains_back, int *pracs_back )
{
    static sh_int old[MAX_SKILL];
    static bool kept_member[MAX_SKILL];
    static bool removed_member[MAX_SKILL];
    int old_guild = ch->pcdata->guild, cls = ch->class;
    int gg_old = guild_group_name( old_guild ) != NULL
                 ? group_lookup( guild_group_name( old_guild ) ) : -1;
    int gn, sn, shown = 0;

    *trains_back = 0;
    *pracs_back = 0;
    memcpy( old, ch->pcdata->learned, sizeof(old) );
    memset( removed_member, 0, sizeof(removed_member) );

    /* Groups: the old guild's own, and any sold to the old guild alone. */
    for ( gn = 0; gn < MAX_GROUP && group_table[gn].name != NULL; gn++ )
    {
        if ( !ch->pcdata->group_known[gn] )
            continue;
        if ( gn == gg_old )
        {
            ch->pcdata->group_known[gn] = FALSE;
            group_skills( gn, removed_member );
            continue;
        }
        if ( sold_to( cls, old_guild, gn, -1 ) && !sold_to( cls, new_guild, gn, -1 )
        &&   group_table[gn].rating[cls] > 0 )
        {
            ch->pcdata->group_known[gn] = FALSE;
            group_skills( gn, removed_member );
            *trains_back += group_table[gn].rating[cls];
            dstring_printf( report, "%s%s (group, %d train%s)", shown++ ? ", " : "  ",
                            group_table[gn].name, group_table[gn].rating[cls],
                            group_table[gn].rating[cls] == 1 ? "" : "s" );
        }
    }

    /* Skills of the groups still held are theirs whatever else happens. */
    memset( kept_member, 0, sizeof(kept_member) );
    for ( gn = 0; gn < MAX_GROUP && group_table[gn].name != NULL; gn++ )
        if ( ch->pcdata->group_known[gn] )
            group_skills( gn, kept_member );

    /* Single skills sold to the old guild alone. */
    for ( sn = 0; sn < MAX_SKILL; sn++ )
    {
        if ( old[sn] <= 0 || kept_member[sn] || skill_table[sn].name == NULL )
            continue;
        if ( sold_to( cls, old_guild, -1, sn ) && !sold_to( cls, new_guild, -1, sn )
        &&   skill_table[sn].rating[cls] > 0 )
        {
            *trains_back += skill_table[sn].rating[cls];
            dstring_printf( report, "%s%s (skill, %d train%s)", shown++ ? ", " : "  ",
                            skill_table[sn].name, skill_table[sn].rating[cls],
                            skill_table[sn].rating[cls] == 1 ? "" : "s" );
        }
    }

    /* Everything off; the new guild in; what is owed and held, back. */
    for ( sn = 0; sn < MAX_SKILL; sn++ )
        ch->pcdata->learned[sn] = 0;
    ch->pcdata->guild = (sh_int) new_guild;
    apply_class_and_guild_skills( ch );
    for ( gn = 0; gn < MAX_GROUP && group_table[gn].name != NULL; gn++ )
        if ( ch->pcdata->group_known[gn] )
            gn_add( ch, gn );
    grant_heros_grip( ch );
    for ( sn = 0; sn < MAX_SKILL; sn++ )
    {
        bool single_kept = old[sn] > 0 && !kept_member[sn] && !removed_member[sn]
            && !( sold_to( cls, old_guild, -1, sn ) && !sold_to( cls, new_guild, -1, sn ) )
            && sn != gsn_heros_grip;

        /* Anything held some other way -- chosen at creation, bought where
           the new guild may still buy it, given by staff -- stays as it
           was. Only what the old guild gave or sold alone goes. */
        if ( single_kept && ch->pcdata->learned[sn] <= 0 )
            ch->pcdata->learned[sn] = old[sn];
        if ( ch->pcdata->learned[sn] > 0 )
        {
            if ( old[sn] > ch->pcdata->learned[sn] )
                ch->pcdata->learned[sn] = old[sn];
            continue;
        }
        if ( old[sn] > 1 )
        {
            int gain = UMAX( 1, int_app[get_curr_stat( ch, STAT_INT )].learn
                                / UMAX( 1, skill_table[sn].rating[cls] ) );

            *pracs_back += ( old[sn] - 1 + gain - 1 ) / gain;
        }
    }
    if ( shown > 0 )
        dstring_append_cstr( report, "\n\r" );
}

void guild_switch( CHAR_DATA *clerk, CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH], confirm[MAX_INPUT_LENGTH];
    static sh_int keep_learned[MAX_SKILL];
    static bool keep_known[MAX_GROUP];
    int new_guild, trains = 0, pracs = 0, keep_guild, keep_train, keep_prac;
    DString report;

    argument = one_argument( argument, arg );
    one_argument( argument, confirm );
    if ( ch->pcdata->guild_switched )
    {
        act( "$n tells you 'You have changed guild once already.  That is the only time.'",
             clerk, NULL, ch, TO_VICT );
        return;
    }
    if ( ch->pcdata->num_remorts > 0 || ch->level > GUILD_SWITCH_MAX_LEVEL
    ||   ch->class < CLASS_MAGE || ch->class > CLASS_WARRIOR
    ||   !four_guild( ch->pcdata->guild ) )
    {
        act( "$n tells you 'A change of guild is for a first life, at level 15 or below, in\n\r"
             "the mages', clerics', thieves' or warriors' guild.'", clerk, NULL, ch, TO_VICT );
        return;
    }
    new_guild = guild_lookup( arg );
    if ( arg[0] == '\0' || !four_guild( new_guild ) || new_guild == ch->pcdata->guild )
    {
        act( "$n tells you 'JOIN SWITCH <mage|cleric|thief|warrior>: I will tell you what\n\r"
             "it costs and gives back before anything changes.'", clerk, NULL, ch, TO_VICT );
        return;
    }

    /* Run it, then put everything back unless confirmed. */
    memcpy( keep_learned, ch->pcdata->learned, sizeof(keep_learned) );
    memcpy( keep_known, ch->pcdata->group_known, sizeof(keep_known) );
    keep_guild = ch->pcdata->guild;
    keep_train = ch->train;
    keep_prac = ch->practice;
    dstring_init_limit( &report, DSTRING_OUTPUT_MAX );
    guild_switch_apply( ch, new_guild, &report, &trains, &pracs );

    if ( str_cmp( confirm, "confirm" ) )
    {
        char buf[MAX_STRING_LENGTH];

        memcpy( ch->pcdata->learned, keep_learned, sizeof(keep_learned) );
        memcpy( ch->pcdata->group_known, keep_known, sizeof(keep_known) );
        ch->pcdata->guild = (sh_int) keep_guild;
        ch->train = (sh_int) keep_train;
        ch->practice = (sh_int) keep_prac;
        snprintf( buf, sizeof(buf), "Leaving the %s guild for the %s guild, once, for good:\n\r",
                  get_guildname( keep_guild ), get_guildname( new_guild ) );
        send_to_char( buf, ch );
        if ( dstring_cstr( &report )[0] != '\0' )
        {
            send_to_char( "  Taken back, with what you paid for it:\n\r", ch );
            send_to_char( dstring_cstr( &report ), ch );
        }
        snprintf( buf, sizeof(buf), "  The %s guild's own training goes; the %s guild's comes free.\n\r"
                  "  Returned to you: %d train%s and %d practice%s.\n\r"
                  "JOIN SWITCH %s CONFIRM does it.  You can change guild only once.\n\r",
                  get_guildname( keep_guild ), get_guildname( new_guild ),
                  trains, trains == 1 ? "" : "s", pracs, pracs == 1 ? "" : "s",
                  get_guildname( new_guild ) );
        send_to_char( buf, ch );
        dstring_free( &report );
        return;
    }

    /* Confirmed: the old character is copied whole before anything holds. */
    memcpy( ch->pcdata->learned, keep_learned, sizeof(keep_learned) );
    memcpy( ch->pcdata->group_known, keep_known, sizeof(keep_known) );
    ch->pcdata->guild = (sh_int) keep_guild;
    ch->train = (sh_int) keep_train;
    ch->practice = (sh_int) keep_prac;
    if ( !player_milestone_required( ch, ch, "guildswitch" ) )
    {
        dstring_free( &report );
        return;
    }
    dstring_free( &report );
    dstring_init_limit( &report, DSTRING_OUTPUT_MAX );
    guild_switch_apply( ch, new_guild, &report, &trains, &pracs );
    ch->train = sh_int_clamp( (long long) ch->train + trains );
    ch->practice = sh_int_clamp( (long long) ch->practice + pracs );
    ch->pcdata->guild_switched = TRUE;
    save_char_obj( ch );
    {
        char buf[MAX_STRING_LENGTH];

        snprintf( buf, sizeof(buf), "Guild switch: %s left the %s guild for the %s guild; "
                  "%d trains and %d practices returned.", ch->name,
                  get_guildname( keep_guild ), get_guildname( new_guild ), trains, pracs );
        log_string( buf );
        act( "$n tells you 'You are now a member of the $t guild.'",
             clerk, get_guildname( new_guild ), ch, TO_VICT );
        snprintf( buf, sizeof(buf), "%d train%s and %d practice%s are yours again.  GAINLIST shows "
                  "what the %s guild\n\rteaches.\n\r", trains, trains == 1 ? "" : "s",
                  pracs, pracs == 1 ? "" : "s", get_guildname( new_guild ) );
        send_to_char( buf, ch );
    }
    playlog_outcome( ch, "guild-switch", "success", get_guildname( new_guild ), NULL, NULL );
    dstring_free( &report );
}

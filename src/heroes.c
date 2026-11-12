/*
 * The Hall of Heroes' two rolls (owner, 2026-11-11: "improve the hero
 * plaque ... automatically displaying all heroes when they hit hero
 * level. also, make a plaque for remorts and do the same").
 *
 * heroes/<Name> is one small record per character who has reached hero
 * level or been reborn:
 *
 *     Lev 57 Trust 57  Alaric the Bold     (the old first line, kept)
 *     Since 1794000000                     (first became a hero; 0: before records)
 *     Remorts 3
 *     Reborn 1794100000                    (last remort; 0: not known)
 *     Class warrior
 *     Race human
 *
 * It is written the moment a character reaches hero level or remorts and
 * at every save after, so a name is on the plaque (LOOK PLAQUE) and on the
 * tablet (LOOK TABLET) at once. Records from before this carry only the
 * first line; hero_records_backfill() fills them from the player files at
 * boot, once. Staff (trust LEVEL_IMMORTAL and up) are on neither.
 */

#include <ctype.h>
#include <dirent.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "merc.h"
#include "numparse.h"

#define HERO_RECORD_MAX 2048

typedef struct
{
    char name[16];
    char first[160];        /* the old first line, as it was */
    int  level;
    int  trust;             /* from the first line; staff are on neither roll */
    long since;
    int  remorts;
    long reborn;
    char cls[24];
    char race[24];
    bool has_remorts;       /* a record written since 2026-11-11 */
} HERO_RECORD;

static bool hero_name_ok( const char *n )
{
    size_t i, len = strlen( n );

    if ( len < 2 || len > 12 )
        return false;
    for ( i = 0; i < len; i++ )
        if ( !isalpha( (unsigned char) n[i] ) )
            return false;
    return true;
}

static void strip_eol( char *s )
{
    size_t len = strlen( s );

    while ( len > 0 && ( s[len - 1] == '\n' || s[len - 1] == '\r' ) )
        s[--len] = '\0';
}

/* The first line's "Lev N Trust N", read with the checked parsers. A
   line that does not say both leaves them 0 (a mortal's record). */
static void hero_first_line( const char *line, int *level, int *trust )
{
    char copy[160];
    char lev_word[MAX_INPUT_LENGTH], lev[MAX_INPUT_LENGTH];
    char tru_word[MAX_INPUT_LENGTH], tru[MAX_INPUT_LENGTH];
    char *rest;

    toc_strlcpy( copy, line, sizeof(copy) );
    rest = one_argument( copy, lev_word );
    rest = one_argument( rest, lev );
    rest = one_argument( rest, tru_word );
    one_argument( rest, tru );
    if ( str_cmp( lev_word, "Lev" ) || str_cmp( tru_word, "Trust" ) )
        return;
    if ( !parse_int( lev, 0, INT_MAX, level ) )
        *level = 0;
    if ( !parse_int( tru, 0, INT_MAX, trust ) )
        *trust = 0;
}

/* A record that names somebody of staff rank, by its first line. A mortal
   later made staff is rewritten with their rank at their next save
   (hero_record_write) or at boot from their file (backfill_dir). */
static bool hero_record_is_staff( const HERO_RECORD *rec )
{
    return rec->level >= LEVEL_IMMORTAL || rec->trust >= LEVEL_IMMORTAL;
}

/* Read heroes/<Name>; false if there is none. */
static bool hero_record_read( const char *name, HERO_RECORD *rec )
{
    char path[MAX_INPUT_LENGTH];
    char line[256];
    FILE *fp;
    int lineno = 0;

    memset( rec, 0, sizeof(*rec) );
    toc_strlcpy( rec->name, name, sizeof(rec->name) );
    rec->name[0] = UPPER( rec->name[0] );
    snprintf( path, sizeof(path), "%s%s", HERO_DIR, rec->name );
    if ( ( fp = fopen( path, "r" ) ) == NULL )
        return false;
    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        char key[32];
        char value[160];

        strip_eol( line );
        if ( lineno++ == 0 )
        {
            toc_strlcpy( rec->first, line, sizeof(rec->first) );
            hero_first_line( line, &rec->level, &rec->trust );
            continue;
        }
        value[0] = '\0';
        if ( sscanf( line, "%31s %159[^\n]", key, value ) < 1 )
            continue;
        /* A malformed number is read as unknown (0), never as whatever
           atoi made of it. */
        if ( !strcmp( key, "Since" ) )
        {
            if ( !parse_long( value, 0, LONG_MAX, &rec->since ) )
                rec->since = 0;
        }
        else if ( !strcmp( key, "Remorts" ) )
        {
            if ( !parse_int( value, 0, INT_MAX, &rec->remorts ) )
                rec->remorts = 0;
            rec->has_remorts = true;
        }
        else if ( !strcmp( key, "Reborn" ) )
        {
            if ( !parse_long( value, 0, LONG_MAX, &rec->reborn ) )
                rec->reborn = 0;
        }
        else if ( !strcmp( key, "Class" ) )
            toc_strlcpy( rec->cls, value, sizeof(rec->cls) );
        else if ( !strcmp( key, "Race" ) )
            toc_strlcpy( rec->race, value, sizeof(rec->race) );
    }
    fclose( fp );
    return true;
}

static void hero_record_store( const HERO_RECORD *rec )
{
    char path[64];
    char tmp[80];
    FILE *fp;

    snprintf( path, sizeof(path), "%s%.15s", HERO_DIR, rec->name );
    snprintf( tmp, sizeof(tmp), "%s.tmp", path );
    if ( ( fp = fopen( tmp, "w" ) ) == NULL )
    {
        bug( "hero_record_store: cannot write a hero record.", 0 );
        return;
    }
    fprintf( fp, "%s\n", rec->first );
    fprintf( fp, "Since %ld\n", rec->since );
    fprintf( fp, "Remorts %d\n", rec->remorts );
    fprintf( fp, "Reborn %ld\n", rec->reborn );
    if ( rec->cls[0] != '\0' )
        fprintf( fp, "Class %s\n", rec->cls );
    if ( rec->race[0] != '\0' )
        fprintf( fp, "Race %s\n", rec->race );
    if ( !temp_file_commit( fp, tmp, path ) )
        bug( "hero_record_store: a hero record was not written.", 0 );
}

/*
 * Write the character's record if they belong on either roll. `reborn`
 * says a remort is happening now. The date they first became a hero is
 * kept from the record already there: a record that predates the dates
 * keeps 0 ("before records"), and a brand new one is dated now.
 */
void hero_record_write( CHAR_DATA *ch, bool reborn )
{
    HERO_RECORD rec;
    bool existed;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return;
    if ( get_trust( ch ) >= LEVEL_IMMORTAL )
    {
        /* Staff are on neither roll. One promoted from mortal keeps the
           record, rewritten with the rank so the rolls leave it out (and a
           demotion's next save puts them back). */
        if ( hero_record_read( ch->name, &rec ) && !hero_record_is_staff( &rec ) )
        {
            snprintf( rec.first, sizeof(rec.first), "Lev %2d Trust %2d  %s",
                      ch->level, get_trust( ch ), ch->name );
            hero_record_store( &rec );
        }
        return;
    }
    if ( !IS_HERO(ch) && ch->pcdata->num_remorts <= 0 )
        return;

    existed = hero_record_read( ch->name, &rec );
    snprintf( rec.first, sizeof(rec.first), "Lev %2d Trust %2d  %s%s",
              ch->level, get_trust( ch ), ch->name,
              ch->pcdata->title != NULL ? ch->pcdata->title : "" );
    if ( !existed )
        rec.since = (long) current_time;
    rec.remorts = ch->pcdata->num_remorts;
    if ( reborn )
        rec.reborn = (long) current_time;
    if ( ch->class >= 0 && ch->class < MAX_CLASS )
        toc_strlcpy( rec.cls, class_table[ch->class].name, sizeof(rec.cls) );
    if ( ch->race >= 0 && ch->race < MAX_PC_RACE )
        toc_strlcpy( rec.race, pc_race_table[ch->race].name, sizeof(rec.race) );
    hero_record_store( &rec );
}

/* The character file's few fields the rolls need, read without loading. */
static bool hero_fields_from_file( const char *path, int *level, int *trust,
                                   int *remorts, int *cls, char *race, size_t race_size )
{
    FILE *fp;
    char line[512];

    *level = *trust = *remorts = 0;
    *cls = -1;
    race[0] = '\0';
    if ( ( fp = fopen( path, "r" ) ) == NULL )
        return false;
    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        if ( !strncmp( line, "#O", 2 ) || !strncmp( line, "End", 3 )
        ||   !strncmp( line, "#PET", 4 ) )
            break;
        strip_eol( line );
        /* A malformed field is read as unknown; the rolls never act on a
           number atoi guessed at. */
        if ( !strncmp( line, "Levl ", 5 ) )
        {
            if ( !parse_int( line + 5, 0, INT_MAX, level ) )
                *level = 0;
        }
        else if ( !strncmp( line, "Tru ", 4 ) )
        {
            if ( !parse_int( line + 4, 0, INT_MAX, trust ) )
                *trust = 0;
        }
        else if ( !strncmp( line, "NumRemorts ", 11 ) )
        {
            if ( !parse_int( line + 11, 0, INT_MAX, remorts ) )
                *remorts = 0;
        }
        else if ( !strncmp( line, "Cla ", 4 ) )
        {
            if ( !parse_int( line + 4, 0, MAX_CLASS - 1, cls ) )
                *cls = -1;
        }
        else if ( !strncmp( line, "Race ", 5 ) )
        {
            char *tilde;

            toc_strlcpy( race, line + 5, race_size );
            strip_eol( race );
            if ( ( tilde = strchr( race, '~' ) ) != NULL )
                *tilde = '\0';
        }
    }
    fclose( fp );
    return true;
}

static int backfill_dir( const char *dirpath )
{
    DIR *dp;
    struct dirent *ent;
    int filled = 0;

    if ( ( dp = opendir( dirpath ) ) == NULL )
        return 0;
    while ( ( ent = readdir( dp ) ) != NULL )
    {
        char path[MAX_INPUT_LENGTH];
        char race[32];
        int level, trust, remorts, cls;
        HERO_RECORD rec;
        bool existed;

        /* hero_name_ok holds the name to twelve letters; a path that would
           not fit is skipped, never read under a cut-short name. */
        if ( !hero_name_ok( ent->d_name ) || !isupper( (unsigned char) ent->d_name[0] )
        ||   !toc_path_join( path, sizeof(path), dirpath, "", ent->d_name ) )
            continue;
        if ( !hero_fields_from_file( path, &level, &trust, &remorts, &cls,
                                     race, sizeof(race) ) )
            continue;
        if ( level >= LEVEL_IMMORTAL || trust >= LEVEL_IMMORTAL )
        {
            /* Promoted since their record was written: write the rank in,
               so the rolls leave them out. */
            if ( hero_record_read( ent->d_name, &rec ) && !hero_record_is_staff( &rec ) )
            {
                snprintf( rec.first, sizeof(rec.first), "Lev %2d Trust %2d  %s",
                          level, trust > level ? trust : level, rec.name );
                hero_record_store( &rec );
                filled++;
            }
            continue;
        }
        if ( level < LEVEL_HERO && remorts <= 0 )
            continue;
        existed = hero_record_read( ent->d_name, &rec );
        if ( existed && rec.has_remorts )
            continue;                       /* already a full record */
        if ( !existed )
            snprintf( rec.first, sizeof(rec.first), "Lev %2d Trust %2d  %s",
                      level, trust > level ? trust : level, rec.name );
        /* rec.since stays 0: when they became a hero was never written. */
        rec.remorts = remorts;
        if ( cls >= 0 && cls < MAX_CLASS )
            toc_strlcpy( rec.cls, class_table[cls].name, sizeof(rec.cls) );
        if ( race[0] != '\0' )
            toc_strlcpy( rec.race, race, sizeof(rec.race) );
        hero_record_store( &rec );
        filled++;
    }
    closedir( dp );
    return filled;
}

/* At boot: give every record from before 2026-11-11, and every reborn
   character without one, the fields the rolls show. Each is done once. */
void hero_records_backfill( void )
{
    char buf[MAX_STRING_LENGTH];
    int filled = backfill_dir( PLAYER_DIR ) + backfill_dir( PLAYER_ARCHIVE_DIR );

    if ( filled > 0 )
    {
        snprintf( buf, sizeof(buf), "Heroes: %d record%s filled in from the player files.",
                  filled, filled == 1 ? "" : "s" );
        log_string( buf );
    }
}

static HERO_RECORD hero_all[HERO_RECORD_MAX];

static int hero_load_all( void )
{
    DIR *dp;
    struct dirent *ent;
    int count = 0;

    if ( ( dp = opendir( HERO_DIR ) ) == NULL )
        return 0;
    while ( ( ent = readdir( dp ) ) != NULL && count < HERO_RECORD_MAX )
        if ( hero_name_ok( ent->d_name ) && hero_record_read( ent->d_name, &hero_all[count] )
        &&   !hero_record_is_staff( &hero_all[count] ) )
            count++;
    closedir( dp );
    return count;
}

/* An ordering, which str_cmp() is not. */
static int hero_by_name( const void *a, const void *b )
{
    const char *x = ( (const HERO_RECORD *) a )->name;
    const char *y = ( (const HERO_RECORD *) b )->name;

    while ( *x != '\0' && LOWER(*x) == LOWER(*y) )
    {
        x++;
        y++;
    }
    return LOWER(*x) - LOWER(*y);
}

static int hero_by_since( const void *a, const void *b )
{
    long x = ( (const HERO_RECORD *) a )->since;
    long y = ( (const HERO_RECORD *) b )->since;

    return x < y ? 1 : x > y ? -1 : hero_by_name( a, b );
}

static int hero_by_remorts( const void *a, const void *b )
{
    const HERO_RECORD *x = a;
    const HERO_RECORD *y = b;

    if ( x->remorts != y->remorts )
        return y->remorts - x->remorts;
    return hero_by_name( a, b );
}

static void hero_date( long when, char *out, size_t size )
{
    time_t t = (time_t) when;
    struct tm *tm;

    if ( when <= 0 || ( tm = localtime( &t ) ) == NULL )
    {
        toc_strlcpy( out, "-", size );
        return;
    }
    strftime( out, size, "%Y-%m-%d", tm );
}

/* Built in a DString (growable output buffers, 2026-11-12): the rolls
   were a static 64K array, and a tablet of HERO_RECORD_MAX reborn runs
   past it. */

bool show_hero_plaque( CHAR_DATA *ch )
{
    DString roll_out;
    char line[512];
    int count, dated = 0, rows, r, c, i;

    if ( ( count = hero_load_all() ) == 0 )
        return false;

    dstring_init_limit( &roll_out, DSTRING_OUTPUT_MAX );
    dstring_append_cstr( &roll_out,
        "                          *********************\n\r"
        "                          *   Heroes of ToC   *\n\r"
        "                          *********************\n\r\n\r" );
    snprintf( line, sizeof(line),
        "  %d have reached the pinnacle of mortal power.  A name appears here\n\r"
        "  the moment its owner becomes a hero.\n\r\n\r", count );
    dstring_append_cstr( &roll_out, line );

    qsort( hero_all, (size_t) count, sizeof(hero_all[0]), hero_by_since );
    for ( i = 0; i < count && hero_all[i].since > 0; i++ )
        dated++;
    if ( dated > 0 )
    {
        dstring_append_cstr( &roll_out, "  The newest:\n\r" );
        for ( i = 0; i < dated && i < 8; i++ )
        {
            char when[16];

            hero_date( hero_all[i].since, when, sizeof(when) );
            snprintf( line, sizeof(line), "    %-12.12s  %-10.10s  %-10.10s  hero since %s\n\r",
                      hero_all[i].name, hero_all[i].cls[0] ? hero_all[i].cls : "-",
                      hero_all[i].race[0] ? hero_all[i].race : "-", when );
            dstring_append_cstr( &roll_out, line );
        }
        dstring_append_cstr( &roll_out, "\n\r" );
    }

    qsort( hero_all, (size_t) count, sizeof(hero_all[0]), hero_by_name );
    dstring_append_cstr( &roll_out,
        "|-----------------------------------------------------------------------------|\n\r" );
    /* Six columns, read down rather than across, as the old plaque was. */
    rows = ( count + 5 ) / 6;
    for ( r = 0; r < rows; r++ )
    {
        toc_strlcpy( line, "|", sizeof(line) );
        for ( c = 0; c < 6; c++ )
        {
            char cell[16];

            i = c * rows + r;
            snprintf( cell, sizeof(cell), c < 5 ? "%-12.12s " : "%-12.12s",
                      i < count ? hero_all[i].name : "" );
            toc_strlcat( line, cell, sizeof(line) );
        }
        toc_strlcat( line, "|\n\r", sizeof(line) );
        dstring_append_cstr( &roll_out, line );
    }
    dstring_append_cstr( &roll_out,
        "|-----------------------------------------------------------------------------|\n\r"
        "  Those who gave it up to begin again are named on the tablet beside it.\n\r" );
    page_to_char( dstring_cstr( &roll_out ), ch );
    dstring_free( &roll_out );
    return true;
}

bool show_remort_tablet( CHAR_DATA *ch )
{
    DString roll_out;
    char line[512];
    int count, reborn = 0, i;

    count = hero_load_all();
    qsort( hero_all, (size_t) count, sizeof(hero_all[0]), hero_by_remorts );
    for ( i = 0; i < count && hero_all[i].remorts > 0; i++ )
        reborn++;

    dstring_init_limit( &roll_out, DSTRING_OUTPUT_MAX );
    dstring_append_cstr( &roll_out,
        "                       ****************************\n\r"
        "                       *    The Reborn of ToC     *\n\r"
        "                       ****************************\n\r\n\r" );
    if ( reborn == 0 )
    {
        dstring_append_cstr( &roll_out,
            "  The black stone is smooth: nobody has yet given up the pinnacle to\n\r"
            "  begin again.  A name appears here the moment its owner is reborn.\n\r" );
        send_to_char( dstring_cstr( &roll_out ), ch );
        dstring_free( &roll_out );
        return true;
    }
    snprintf( line, sizeof(line),
        "  %d have given up the pinnacle of mortal power to begin again.  A name\n\r"
        "  appears here the moment its owner is reborn, and climbs with each life.\n\r\n\r"
        "  Lives  Name          Class       Race        Last reborn\n\r"
        "  -----  ------------  ----------  ----------  -----------\n\r", reborn );
    dstring_append_cstr( &roll_out, line );
    for ( i = 0; i < reborn; i++ )
    {
        char when[16];

        hero_date( hero_all[i].reborn, when, sizeof(when) );
        snprintf( line, sizeof(line), "  %5d  %-12.12s  %-10.10s  %-10.10s  %s\n\r",
                  hero_all[i].remorts, hero_all[i].name,
                  hero_all[i].cls[0] ? hero_all[i].cls : "-",
                  hero_all[i].race[0] ? hero_all[i].race : "-", when );
        dstring_append_cstr( &roll_out, line );
    }
    page_to_char( dstring_cstr( &roll_out ), ch );
    dstring_free( &roll_out );
    return true;
}

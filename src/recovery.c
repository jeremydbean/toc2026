/***************************************************************************
 * recovery.c -- the recovery ledger: what was restored, never rolled back.
 *
 * Owner, 2026-10-23: nearly impossible to lose a player, and staff or a
 * delegated AI able to put back a character, their gear or their stash.
 * A receipt for a restore cannot live in the thing being restored. The
 * git restore requests marked themselves applied inside the player file
 * ("restore:<id>" among the login fixes), so a full PRESTORE to the copy
 * taken just before the request -- the obvious undo -- took the mark away
 * with everything else, and the next login applied the same request again
 * (handoff review, 2026-10-23, reproduced live).
 *
 * The ledger is ../player/recovery/ledger.tsv, append-only, one event a
 * line, flushed to the disk before the caller goes on:
 *
 *   seq  epoch  event  state  uid  player  request  kind  actor  detail
 *
 *   request   pending / committed / rejected / retry   (restores.c)
 *   prestore  committed / refused                      (act_wiz.c)
 *   snapshot  committed                                 (save.c, milestones)
 *   corpse    created / archived / restored             (corpses.c)
 *   uid       assign / retire                           (logins, deletions)
 *
 * Nothing here is ever rewritten or removed: an undo is a new event. It
 * sits under player/ so it travels everywhere a character file does --
 * the state sync to git, the deploy's exclusions, toc-restore, the
 * installers' state -- and no PRESTORE copies over it. It holds names and
 * counts, never a password or an address.
 *
 * A player's uid is the one identity that survives everything a name and
 * a file do not: created with the character, kept across every restore,
 * retired when the character is deleted, so a new character who takes
 * the name is somebody else. The old "Id" in the player file is a random
 * number up to 65535 and rolls back with the file; it is not used here.
 ***************************************************************************/

#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200112L
#endif

#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>
#include "merc.h"

#define RECOVERY_LEDGER   RECOVERY_DIR "ledger.tsv"

typedef struct ledger_request
{
    char id[40];
    int  state;
} LEDGER_REQUEST;

typedef struct ledger_uid
{
    char name[16];
    char uid[24];
} LEDGER_UID;

static LEDGER_REQUEST *ledger_requests = NULL;
static int ledger_request_count = 0, ledger_request_cap = 0;
static LEDGER_UID *ledger_uids = NULL;
static int ledger_uid_count = 0, ledger_uid_cap = 0;
static long ledger_seq = 0;
static bool ledger_loaded = false;


/* --- Writing a file so that it is on the disk, not only in the kernel. ---

   fclose and rename are enough against a crash of the game; a host that
   loses power can still lose what the kernel had not written, and a
   rename can be lost with the directory it was made in. These are what
   the recovery files go through. */

bool durable_close( FILE *fp )
{
    bool ok = true;

    if ( fp == NULL )
        return false;
    if ( ferror( fp ) || fflush( fp ) != 0 )
        ok = false;
    if ( ok && fsync( fileno( fp ) ) != 0 )
        ok = false;
    if ( fclose( fp ) != 0 )
        ok = false;
    return ok;
}

/* The directory a path sits in, flushed, so a file made or renamed there
   is still there after a power cut. */
bool durable_dir_sync( const char *path )
{
    char dir[MAX_STRING_LENGTH];
    char *slash;
    int fd;
    bool ok;

    if ( path == NULL || toc_strlcpy( dir, path, sizeof(dir) ) >= sizeof(dir) )
        return false;
    if ( ( slash = strrchr( dir, '/' ) ) == NULL )
        toc_strlcpy( dir, ".", sizeof(dir) );
    else if ( slash == dir )
        slash[1] = '\0';
    else
        *slash = '\0';
    if ( ( fd = open( dir, O_RDONLY ) ) < 0 )
        return false;
    ok = fsync( fd ) == 0;
    close( fd );
    return ok;
}

/* temp_file_commit, with the file and the rename flushed to the disk. */
bool durable_commit( FILE *fp, const char *temp_path, const char *path )
{
    char buf[MAX_STRING_LENGTH];
    int err;

    if ( !durable_close( fp ) )
    {
        err = errno;
        remove( temp_path );
        snprintf( buf, sizeof(buf), "Write failed: %s could not be written (%s); "
                  "%s is unchanged.", temp_path, strerror( err ), path );
        log_string( buf );
        return false;
    }
    if ( rename( temp_path, path ) != 0 )
    {
        err = errno;
        remove( temp_path );
        snprintf( buf, sizeof(buf), "Write failed: %s could not replace %s (%s).",
                  temp_path, path, strerror( err ) );
        log_string( buf );
        return false;
    }
    if ( !durable_dir_sync( path ) )
    {
        snprintf( buf, sizeof(buf), "Write: %s was renamed into place but its "
                  "directory could not be flushed.", path );
        log_string( buf );
    }
    return true;
}

bool recovery_ensure_dir( const char *path )
{
    struct stat st;

    if ( mkdir( path, 0755 ) == 0 )
        return true;
    return errno == EEXIST && stat( path, &st ) == 0 && S_ISDIR( st.st_mode );
}


/* --- The ledger. --- */

/* A field with no tab or line break in it, for one column of a line. */
static void ledger_field( char *dst, size_t size, const char *src )
{
    size_t i;

    toc_strlcpy( dst, src != NULL && src[0] != '\0' ? src : "-", size );
    for ( i = 0; dst[i] != '\0'; i++ )
        if ( dst[i] == '\t' || dst[i] == '\n' || dst[i] == '\r' )
            dst[i] = ' ';
}

static int ledger_state_code( const char *state )
{
    if ( !strcmp( state, "pending" ) )   return RECOVERY_PENDING;
    if ( !strcmp( state, "committed" ) ) return RECOVERY_COMMITTED;
    if ( !strcmp( state, "rejected" ) )  return RECOVERY_REJECTED;
    return RECOVERY_NONE;
}

static void ledger_note_request( const char *id, int state )
{
    int i;

    if ( state == RECOVERY_NONE )
        return;                 /* "retry" leaves the last state standing */
    for ( i = 0; i < ledger_request_count; i++ )
        if ( !strcmp( ledger_requests[i].id, id ) )
        {
            /* Committed and rejected are final: nothing reopens them. */
            if ( ledger_requests[i].state != RECOVERY_COMMITTED
            &&   ledger_requests[i].state != RECOVERY_REJECTED )
                ledger_requests[i].state = state;
            return;
        }
    if ( ledger_request_count >= ledger_request_cap )
    {
        int cap = ledger_request_cap ? ledger_request_cap * 2 : 64;
        LEDGER_REQUEST *grown = realloc( ledger_requests, (size_t) cap * sizeof(*grown) );

        if ( grown == NULL )
        {
            bug( "recovery: out of memory for the request index", 0 );
            return;
        }
        ledger_requests = grown;
        ledger_request_cap = cap;
    }
    toc_strlcpy( ledger_requests[ledger_request_count].id, id,
                 sizeof(ledger_requests[0].id) );
    ledger_requests[ledger_request_count++].state = state;
}

static LEDGER_UID *ledger_uid_slot( const char *name )
{
    int i;

    for ( i = 0; i < ledger_uid_count; i++ )
        if ( !str_cmp( ledger_uids[i].name, name ) )
            return &ledger_uids[i];
    return NULL;
}

static void ledger_note_uid( const char *name, const char *uid, bool assign )
{
    LEDGER_UID *slot = ledger_uid_slot( name );

    if ( slot == NULL )
    {
        if ( !assign )
            return;
        if ( ledger_uid_count >= ledger_uid_cap )
        {
            int cap = ledger_uid_cap ? ledger_uid_cap * 2 : 256;
            LEDGER_UID *grown = realloc( ledger_uids, (size_t) cap * sizeof(*grown) );

            if ( grown == NULL )
            {
                bug( "recovery: out of memory for the uid index", 0 );
                return;
            }
            ledger_uids = grown;
            ledger_uid_cap = cap;
        }
        slot = &ledger_uids[ledger_uid_count++];
        toc_strlcpy( slot->name, name, sizeof(slot->name) );
    }
    if ( assign )
        toc_strlcpy( slot->uid, uid, sizeof(slot->uid) );
    else if ( !strcmp( slot->uid, uid ) )
        slot->uid[0] = '\0';
}

void recovery_boot( void )
{
    FILE *fp;
    char line[MAX_STRING_LENGTH * 2];
    long lines = 0, bad = 0;

    ledger_loaded = true;
    ledger_request_count = 0;
    ledger_uid_count = 0;
    ledger_seq = 0;
    if ( ( fp = fopen( RECOVERY_LEDGER, "r" ) ) == NULL )
        return;
    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        char *col[10];
        char *p = line;
        int n = 0;
        long seq;

        if ( line[0] == '#' || line[0] == '\n' )
            continue;
        line[strcspn( line, "\r\n" )] = '\0';
        while ( n < 10 )
        {
            col[n++] = p;
            if ( ( p = strchr( p, '\t' ) ) == NULL )
                break;
            *p++ = '\0';
        }
        if ( n < 9 )
        {
            bad++;          /* a line cut short by a crash: the rest stand */
            continue;
        }
        lines++;
        seq = atol( col[0] );
        if ( seq > ledger_seq )
            ledger_seq = seq;
        if ( !strcmp( col[2], "request" ) )
            ledger_note_request( col[6], ledger_state_code( col[3] ) );
        else if ( !strcmp( col[2], "uid" ) )
            ledger_note_uid( col[5], col[4], !strcmp( col[3], "assign" ) );
    }
    fclose( fp );
    snprintf( line, sizeof(line), "Recovery ledger: %ld events, %d requests, %d "
              "players%s.", lines, ledger_request_count, ledger_uid_count,
              bad > 0 ? " (some lines were cut short and skipped)" : "" );
    log_string( line );
}

/*
 * One event, on the disk before this returns true. A false return means
 * it may not have been kept, and whatever it records must be treated as
 * not having happened yet (a request stays pending; it is tried again).
 */
bool recovery_record( const char *event, const char *state, const char *player,
                      const char *request, const char *kind, const char *actor,
                      const char *detail )
{
    char f_player[32], f_request[48], f_kind[32], f_actor[32], f_detail[512];
    char line[MAX_STRING_LENGTH];
    const char *uid;
    FILE *fp;
    bool created;
    struct stat st;

    if ( !ledger_loaded )
        recovery_boot();
    if ( !recovery_ensure_dir( "../player" ) || !recovery_ensure_dir( RECOVERY_DIR ) )
    {
        bug( "recovery_record: cannot make " RECOVERY_DIR, 0 );
        return false;
    }
    created = stat( RECOVERY_LEDGER, &st ) != 0;
    uid = player != NULL ? recovery_uid( player ) : "";
    ledger_field( f_player, sizeof(f_player), player );
    ledger_field( f_request, sizeof(f_request), request );
    ledger_field( f_kind, sizeof(f_kind), kind );
    ledger_field( f_actor, sizeof(f_actor), actor );
    ledger_field( f_detail, sizeof(f_detail), detail );
    snprintf( line, sizeof(line), "%ld\t%ld\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n",
              ledger_seq + 1, (long) ( current_time > 0 ? current_time : time( NULL ) ),
              event, state, uid[0] != '\0' ? uid : "-", f_player, f_request,
              f_kind, f_actor, f_detail );
    if ( ( fp = fopen( RECOVERY_LEDGER, "a" ) ) == NULL )
    {
        bug( "recovery_record: cannot open the ledger", 0 );
        return false;
    }
    if ( fputs( line, fp ) == EOF )
    {
        fclose( fp );
        bug( "recovery_record: cannot write the ledger", 0 );
        return false;
    }
    if ( !durable_close( fp ) )
    {
        bug( "recovery_record: the ledger did not reach the disk", 0 );
        return false;
    }
    if ( created )
        durable_dir_sync( RECOVERY_LEDGER );
    ledger_seq++;
    if ( !strcmp( event, "request" ) && request != NULL )
        ledger_note_request( request, ledger_state_code( state ) );
    return true;
}

long recovery_sequence( void )
{
    if ( !ledger_loaded )
        recovery_boot();
    return ledger_seq;
}

int recovery_request_state( const char *request )
{
    int i;

    if ( !ledger_loaded )
        recovery_boot();
    for ( i = 0; i < ledger_request_count; i++ )
        if ( !strcmp( ledger_requests[i].id, request ) )
            return ledger_requests[i].state;
    return RECOVERY_NONE;
}


/* --- Player identity. --- */

const char *recovery_uid( const char *name )
{
    LEDGER_UID *slot;

    if ( !ledger_loaded )
        recovery_boot();
    if ( name == NULL || ( slot = ledger_uid_slot( name ) ) == NULL )
        return "";
    return slot->uid;
}

static bool recovery_assign_uid( const char *name, const char *why )
{
    char uid[24];
    char proper[16];

    toc_strlcpy( proper, capitalize( name ), sizeof(proper) );
    snprintf( uid, sizeof(uid), "P%08lx%04lx%04x",
              (unsigned long) ( current_time > 0 ? current_time : time( NULL ) ) & 0xffffffffUL,
              (unsigned long) ( ledger_seq + 1 ) & 0xffffUL,
              (unsigned) number_range( 0, 0xffff ) );
    /* The index changes only once the line is down, so a failed write
       leaves the name without one and the next login tries again. */
    ledger_note_uid( proper, uid, true );
    if ( !recovery_record( "uid", "assign", proper, "-", "player", "-", why ) )
    {
        LEDGER_UID *slot = ledger_uid_slot( proper );

        if ( slot != NULL )
            slot->uid[0] = '\0';
        return false;
    }
    return true;
}

/* From the nanny, before anything else is recorded for them: a new
   character always gets a uid of their own, even in a name somebody had
   before; an old one without a uid gets one now. */
void recovery_player_login( CHAR_DATA *ch, bool new_character )
{
    if ( ch == NULL || IS_NPC(ch) || ch->name == NULL )
        return;
    if ( new_character )
    {
        const char *old = recovery_uid( ch->name );

        if ( old[0] != '\0' )
        {
            char was[24];

            toc_strlcpy( was, old, sizeof(was) );
            recovery_record( "uid", "retire", ch->name, "-", "player", "-",
                             "a new character took the name" );
            ledger_note_uid( capitalize( ch->name ), was, false );
        }
        recovery_assign_uid( ch->name, "created" );
    }
    else if ( recovery_uid( ch->name )[0] == '\0' )
        recovery_assign_uid( ch->name, "first seen since the ledger began" );
}

/* A deleted character's uid goes with them; their history keeps it. */
void recovery_player_retire( const char *name, const char *why )
{
    const char *uid = recovery_uid( name );
    char was[24];

    if ( uid[0] == '\0' )
        return;
    toc_strlcpy( was, uid, sizeof(was) );
    recovery_record( "uid", "retire", name, "-", "player", "-", why );
    ledger_note_uid( capitalize( name ), was, false );
}

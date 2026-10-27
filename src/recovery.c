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
 * The ledger is ../player/recovery/ledger.tsv, append-only, one record a
 * line, each on the disk before the caller goes on:
 *
 *   seq epoch event state uid player request kind actor detail check
 *
 * `check` is the FNV-1a of everything before it, in eight hex digits, and
 * a record is only a record with its check and its newline. The first
 * version trusted any nine columns: a write cut short left a line with no
 * end, the next record was appended onto it, and the boot after read the
 * two as the first -- a player's uid assignment vanished and they were
 * given a second (independent review, 2026-10-23). Now a torn tail is
 * copied aside (ledger.torn.<epoch>) and cut off at boot, a failed write
 * is cut back to where it began at once, and nothing is appended while
 * the end of the file is in doubt. Records from before the check (ten
 * columns, complete) are still read.
 *
 *   request   pending / committed / rejected / retry / abandoned
 *   prestore  pending / committed
 *   snapshot  committed
 *   corpse    created / archived / pending-archive
 *   uid       assign / retire
 *
 * Nothing here is ever rewritten: an undo is a new record. It sits under
 * player/ so it travels everywhere a character file does, and no PRESTORE
 * copies over it. It holds names and counts, never a password or an
 * address.
 *
 * A player's uid is the one identity that survives everything a name and
 * a file do not: created with the character, kept across every restore,
 * retired when the character is deleted.
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
    char id[48];
    char player[16];
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
static bool ledger_tail_doubtful = false;   /* a failed write not cut back */


/* --- Failure injection, for the tests only. ---

   TOC_FAULT names points that always fail ("fsync,dirsync"); the file
   named by TOC_FAULT_FILE names one point that fails once -- "save 2" is
   the second save from now -- and is removed when it does. Neither is set
   anywhere but tests/. */
bool recovery_fault( const char *point )
{
    const char *always = getenv( "TOC_FAULT" );
    const char *once = getenv( "TOC_FAULT_FILE" );

    if ( always != NULL && strstr( always, point ) != NULL )
        return true;
    if ( once != NULL && once[0] != '\0' )
    {
        FILE *fp = fopen( once, "r" );
        char want[128] = "";

        if ( fp == NULL )
            return false;
        if ( fgets( want, sizeof(want), fp ) == NULL )
            want[0] = '\0';
        fclose( fp );
        want[strcspn( want, "\r\n" )] = '\0';
        /* "<point>" fails the next one; "<point> <n>" the n-th from now. */
        {
            char *space = strchr( want, ' ' );
            int n = space != NULL ? atoi( space + 1 ) : 1;

            if ( space != NULL )
                *space = '\0';
            if ( want[0] == '\0' || strcmp( want, point ) != 0 )
                return false;
            if ( n > 1 )
            {
                if ( ( fp = fopen( once, "w" ) ) != NULL )
                {
                    fprintf( fp, "%s %d\n", point, n - 1 );
                    fclose( fp );
                }
                return false;
            }
            remove( once );
            return true;
        }
    }
    return false;
}


/* --- Writing a file so that it is on the disk, not only in the kernel. ---

   fclose and rename are enough against a crash of the game; a host that
   loses power can still lose what the kernel had not written, and a
   rename can be lost with the directory it was made in. */

bool durable_close( FILE *fp )
{
    bool ok = true;

    if ( fp == NULL )
        return false;
    if ( ferror( fp ) || fflush( fp ) != 0 )
        ok = false;
    if ( ok && ( recovery_fault( "fsync" ) || fsync( fileno( fp ) ) != 0 ) )
        ok = false;
    if ( fclose( fp ) != 0 )
        ok = false;
    return ok;
}

/* The directory a path sits in, flushed, so a file made or renamed there
   is still there after a power cut. A trailing slash names the directory
   itself, whose own parent is then flushed. */
bool durable_dir_sync( const char *path )
{
    char dir[MAX_STRING_LENGTH];
    char *slash;
    size_t len;
    int fd;
    bool ok;

    if ( path == NULL || toc_strlcpy( dir, path, sizeof(dir) ) >= sizeof(dir) )
        return false;
    for ( len = strlen( dir ); len > 1 && dir[len - 1] == '/'; len-- )
        dir[len - 1] = '\0';
    if ( ( slash = strrchr( dir, '/' ) ) == NULL )
        toc_strlcpy( dir, ".", sizeof(dir) );
    else if ( slash == dir )
        slash[1] = '\0';
    else
        *slash = '\0';
    if ( recovery_fault( "dirsync" ) )
        return false;
    if ( ( fd = open( dir, O_RDONLY ) ) < 0 )
        return false;
    ok = fsync( fd ) == 0;
    close( fd );
    return ok;
}

/*
 * A file written aside, flushed, renamed over `path`, the rename flushed.
 * DURABLE_OK; DURABLE_FAILED with the old file still in place (the temp
 * is removed); or DURABLE_UNCERTAIN -- renamed, so the new file is what
 * the game will read, but the directory did not confirm it is on the
 * disk. Uncertain is not failure: the old file is gone. A caller keeping
 * a receipt treats it as not yet committed and reconciles later.
 */
int durable_commit( FILE *fp, const char *temp_path, const char *path )
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
        return DURABLE_FAILED;
    }
    if ( rename( temp_path, path ) != 0 )
    {
        err = errno;
        remove( temp_path );
        snprintf( buf, sizeof(buf), "Write failed: %s could not replace %s (%s).",
                  temp_path, path, strerror( err ) );
        log_string( buf );
        return DURABLE_FAILED;
    }
    if ( !durable_dir_sync( path ) )
    {
        snprintf( buf, sizeof(buf), "Write: %s is in place but its directory could "
                  "not be flushed; it is not confirmed on the disk.", path );
        log_string( buf );
        return DURABLE_UNCERTAIN;
    }
    return DURABLE_OK;
}

/* A directory, made if need be -- and when made, its own entry flushed
   into its parent, or a power cut can take the directory and everything
   since written in it. */
bool recovery_ensure_dir( const char *path )
{
    struct stat st;

    if ( mkdir( path, 0755 ) == 0 )
        return durable_dir_sync( path );
    return errno == EEXIST && stat( path, &st ) == 0 && S_ISDIR( st.st_mode );
}


/* --- The ledger. --- */

static unsigned long ledger_check( const char *text, size_t len )
{
    unsigned long hash = 2166136261UL;
    size_t i;

    for ( i = 0; i < len; i++ )
        hash = ( ( hash ^ (unsigned char) text[i] ) * 16777619UL ) & 0xffffffffUL;
    return hash;
}

/* A field with no tab or line break in it, for one column of a record. */
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
    if ( !strcmp( state, "abandoned" ) ) return RECOVERY_ABANDONED;
    return RECOVERY_NONE;
}

static void ledger_note_request( const char *id, const char *player, int state )
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
    toc_strlcpy( ledger_requests[ledger_request_count].player, player != NULL ? player : "",
                 sizeof(ledger_requests[0].player) );
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

/*
 * Make the ledger end at a record boundary: anything after its last
 * newline is a write that never finished. It is copied aside, so nothing
 * is thrown away, then cut off, and the cut flushed. True when the file
 * ends cleanly (or does not exist yet).
 */
static bool ledger_trim_tail( void )
{
    char buf[MAX_STRING_LENGTH];
    char quarantine[MAX_INPUT_LENGTH];
    struct stat st;
    off_t end, keep;
    long torn;
    int fd;
    bool ok = true;

    if ( stat( RECOVERY_LEDGER, &st ) != 0 )
        return errno == ENOENT;
    if ( ( fd = open( RECOVERY_LEDGER, O_RDWR ) ) < 0 )
        return false;
    end = st.st_size;
    /* Back from the end to the last newline. */
    for ( keep = end; keep > 0; keep-- )
    {
        char c;

        if ( lseek( fd, keep - 1, SEEK_SET ) < 0 || read( fd, &c, 1 ) != 1 )
        {
            close( fd );
            return false;
        }
        if ( c == '\n' )
            break;
    }
    torn = (long) ( end - keep );
    if ( torn == 0 )
    {
        close( fd );
        return true;
    }
    /* The torn bytes, kept where staff can read them. */
    snprintf( quarantine, sizeof(quarantine), "%sledger.torn.%ld", RECOVERY_DIR,
              (long) ( current_time > 0 ? current_time : time( NULL ) ) );
    {
        FILE *out = fopen( quarantine, "ab" );
        long i;

        if ( out == NULL || lseek( fd, keep, SEEK_SET ) < 0 )
            ok = false;
        for ( i = 0; ok && i < torn; i++ )
        {
            char c;

            if ( read( fd, &c, 1 ) != 1 || fputc( c, out ) == EOF )
                ok = false;
        }
        if ( out != NULL && !durable_close( out ) )
            ok = false;
    }
    if ( ok && ( ftruncate( fd, keep ) != 0 || fsync( fd ) != 0 ) )
        ok = false;
    close( fd );
    snprintf( buf, sizeof(buf), "Recovery ledger: %ld byte%s of an unfinished record at "
              "its end %s (kept in %s).", torn, torn == 1 ? "" : "s",
              ok ? "cut off" : "could NOT be cut off", quarantine );
    log_string( buf );
    if ( !ok )
        bug( "recovery: the ledger's torn end could not be cut off", 0 );
    return ok;
}


/*
 * One ledger line into its ten columns, in place. A record ends with its
 * newline, and one with eleven columns is whole only if its check (the
 * last) matches; ten columns is a record from before the check.
 */
#define LEDGER_ROW_SKIP    0
#define LEDGER_ROW_OK      1
#define LEDGER_ROW_LEGACY  2
#define LEDGER_ROW_BAD     (-1)

static int ledger_split( char *line, char *col[10] )
{
    char *p = line;
    size_t len = strlen( line );
    int n = 0, tabs = 0, kind = LEDGER_ROW_OK;
    char *q;

    if ( line[0] == '#' )
        return LEDGER_ROW_SKIP;
    if ( len == 0 || line[len - 1] != '\n' )
        return LEDGER_ROW_BAD;
    line[len - 1] = '\0';
    if ( len >= 2 && line[len - 2] == '\r' )
        line[len - 2] = '\0';
    for ( q = line; *q != '\0'; q++ )
        if ( *q == '\t' )
            tabs++;
    if ( tabs == 10 )
    {
        char *tab = strrchr( line, '\t' );
        char *end;
        unsigned long want = strtoul( tab + 1, &end, 16 );

        if ( strlen( tab + 1 ) != 8 || *end != '\0'
        ||   ledger_check( line, (size_t) ( tab - line ) ) != want )
            return LEDGER_ROW_BAD;
        *tab = '\0';
    }
    else if ( tabs == 9 )
        kind = LEDGER_ROW_LEGACY;
    else
        return LEDGER_ROW_BAD;
    while ( n < 10 )
    {
        col[n++] = p;
        if ( ( p = strchr( p, '\t' ) ) == NULL )
            break;
        *p++ = '\0';
    }
    if ( n != 10 || !isdigit( (unsigned char) col[0][0] ) )
        return LEDGER_ROW_BAD;
    return kind;
}

void recovery_boot( void )
{
    FILE *fp;
    char line[MAX_STRING_LENGTH * 2];
    long lines = 0, bad = 0, legacy = 0, out_of_order = 0, last_seq = 0;

    ledger_loaded = true;
    ledger_request_count = 0;
    ledger_uid_count = 0;
    ledger_seq = 0;
    ledger_tail_doubtful = !ledger_trim_tail();
    if ( ( fp = fopen( RECOVERY_LEDGER, "r" ) ) == NULL )
        return;
    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        char *col[10];
        long seq;
        int kind = ledger_split( line, col );

        if ( kind == LEDGER_ROW_SKIP )
            continue;
        if ( kind == LEDGER_ROW_BAD )
        {
            bad++;
            continue;
        }
        if ( kind == LEDGER_ROW_LEGACY )
            legacy++;
        lines++;
        seq = atol( col[0] );
        if ( seq <= last_seq )
            out_of_order++;
        last_seq = seq;
        if ( seq > ledger_seq )
            ledger_seq = seq;
        if ( !strcmp( col[2], "request" ) || !strcmp( col[2], "prestore" ) )
            ledger_note_request( col[6], col[5], ledger_state_code( col[3] ) );
        else if ( !strcmp( col[2], "uid" ) )
            ledger_note_uid( col[5], col[4], !strcmp( col[3], "assign" ) );
    }
    fclose( fp );
    snprintf( line, sizeof(line), "Recovery ledger: %ld records (%ld from before the "
              "check), %d requests, %d players%s%s%s.",
              lines, legacy, ledger_request_count, ledger_uid_count,
              bad > 0 ? "; some lines were not whole records and were skipped" : "",
              out_of_order > 0 ? "; some sequence numbers were out of order" : "",
              ledger_tail_doubtful ? "; its end is in doubt, so nothing will be written "
                                     "to it until that is mended" : "" );
    log_string( line );
    if ( bad > 0 )
        bug( "recovery_boot: ledger lines skipped as not whole records", (int) bad );
}

/* Append one whole record and flush it; on any failure, cut the file back
   to where it was, so a partial record never sits under the next one. */
static bool ledger_append( const char *record )
{
    struct stat st;
    size_t len = strlen( record ), done = 0;
    off_t before;
    bool created, ok = true;
    int fd;

    if ( ledger_tail_doubtful )
    {
        if ( !ledger_trim_tail() )
            return false;
        ledger_tail_doubtful = false;
    }
    created = stat( RECOVERY_LEDGER, &st ) != 0;
    if ( ( fd = open( RECOVERY_LEDGER, O_WRONLY | O_CREAT | O_APPEND, 0644 ) ) < 0 )
        return false;
    if ( ( before = lseek( fd, 0, SEEK_END ) ) < 0 )
    {
        close( fd );
        return false;
    }
    if ( recovery_fault( "ledger" ) )
    {
        /* Half a record, then the failure: what a full disk does. */
        if ( write( fd, record, len / 2 ) < 0 )
            ok = false;
        ok = false;
    }
    while ( ok && done < len )
    {
        ssize_t n = write( fd, record + done, len - done );

        if ( n <= 0 )
            ok = false;
        else
            done += (size_t) n;
    }
    if ( ok && ( recovery_fault( "fsync" ) || fsync( fd ) != 0 ) )
        ok = false;
    if ( !ok )
    {
        if ( ftruncate( fd, before ) != 0 || fsync( fd ) != 0 )
        {
            ledger_tail_doubtful = true;
            bug( "recovery: a failed ledger write could not be cut back", 0 );
        }
        close( fd );
        return false;
    }
    close( fd );
    if ( created && !durable_dir_sync( RECOVERY_LEDGER ) )
        return false;
    return true;
}

/*
 * One record, on the disk before this returns true. A false return means
 * it was not kept, and whatever it records must be treated as not having
 * happened yet (a request stays pending; it is tried again).
 */
bool recovery_record( const char *event, const char *state, const char *player,
                      const char *request, const char *kind, const char *actor,
                      const char *detail )
{
    char f_player[32], f_request[64], f_kind[32], f_actor[32], f_detail[512];
    char line[MAX_STRING_LENGTH];
    const char *uid;
    size_t len;

    if ( !ledger_loaded )
        recovery_boot();
    if ( !recovery_ensure_dir( "../player" ) || !recovery_ensure_dir( RECOVERY_DIR ) )
    {
        bug( "recovery_record: cannot make " RECOVERY_DIR, 0 );
        return false;
    }
    uid = player != NULL ? recovery_uid( player ) : "";
    ledger_field( f_player, sizeof(f_player), player );
    ledger_field( f_request, sizeof(f_request), request );
    ledger_field( f_kind, sizeof(f_kind), kind );
    ledger_field( f_actor, sizeof(f_actor), actor );
    ledger_field( f_detail, sizeof(f_detail), detail );
    snprintf( line, sizeof(line), "%ld\t%ld\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s",
              ledger_seq + 1, (long) ( current_time > 0 ? current_time : time( NULL ) ),
              event, state, uid[0] != '\0' ? uid : "-", f_player, f_request,
              f_kind, f_actor, f_detail );
    len = strlen( line );
    snprintf( line + len, sizeof(line) - len, "\t%08lx\n", ledger_check( line, len ) );
    if ( !ledger_append( line ) )
    {
        bug( "recovery_record: the ledger record was not kept", 0 );
        return false;
    }
    ledger_seq++;
    if ( ( !strcmp( event, "request" ) || !strcmp( event, "prestore" ) ) && request != NULL )
        ledger_note_request( request, player, ledger_state_code( state ) );
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

/*
 * At login, before anything else may change them: every staff restore of
 * theirs left pending -- a crash or a failed save between giving and
 * committing. The player file's mark says whether it reached the file: if
 * so it is committed; if not it never happened and is abandoned, and may
 * be done again. (Git requests, whose ids have no colon, are restores.c's.)
 */
void recovery_reconcile_login( CHAR_DATA *ch )
{
    char mark[80];
    char buf[MAX_STRING_LENGTH];
    int i;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
        return;
    for ( i = 0; i < ledger_request_count; i++ )
    {
        LEDGER_REQUEST *r = &ledger_requests[i];

        if ( r->state != RECOVERY_PENDING || strchr( r->id, ':' ) == NULL
        ||   str_cmp( r->player, ch->name ) )
            continue;
        /* A death or a resurrection with its corpse still kept: settled by
           the corpse keeper, which also mends the corpse (corpses.c). */
        if ( corpse_registry_reconcile_login( ch, r->id ) )
            continue;
        snprintf( mark, sizeof(mark), "restore:%s", r->id );
        if ( player_fix_has( ch, mark ) )
            recovery_record( "request", "committed", ch->name, r->id, "reconcile", "login",
                             "the player file held it; committed at their next login" );
        else
            recovery_record( "request", "abandoned", ch->name, r->id, "reconcile", "login",
                             "it never reached the player file; nothing was given" );
        snprintf( buf, sizeof(buf), "Recovery: %s's pending restore %s %s at login.",
                  ch->name, r->id, r->state == RECOVERY_COMMITTED ? "committed" : "abandoned" );
        log_string( buf );
    }
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
    /* The index changes only once the record is down, so a failed write
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

/*
 * Whose a snapshot is: the uid the ledger recorded when that copy was
 * taken as a milestone (a "snapshot" record whose detail starts with its
 * name). Empty when the ledger never recorded it -- an ordinary save's
 * copy, or one from before the ledger -- which is not the same as a
 * mismatch, and callers say which.
 */
bool recovery_snapshot_uid( const char *snapname, char *out, size_t size )
{
    FILE *fp;
    char line[MAX_STRING_LENGTH * 2];
    size_t namelen;

    if ( size > 0 )
        out[0] = '\0';
    if ( snapname == NULL || snapname[0] == '\0'
    ||   ( fp = fopen( RECOVERY_LEDGER, "r" ) ) == NULL )
        return false;
    namelen = strlen( snapname );
    while ( fgets( line, sizeof(line), fp ) != NULL )
    {
        char *col[10];
        int kind = ledger_split( line, col );

        if ( kind != LEDGER_ROW_OK && kind != LEDGER_ROW_LEGACY )
            continue;
        if ( strcmp( col[2], "snapshot" ) || strncmp( col[9], snapname, namelen )
        ||   col[9][namelen] != ' ' || !strcmp( col[4], "-" ) )
            continue;
        toc_strlcpy( out, col[4], size );
    }
    fclose( fp );
    return out[0] != '\0';
}

/* A deleted character put back by PRESTORE takes back the uid that was
   retired with them: the same character, not a new one in an old name. */
bool recovery_reinstate_uid( const char *name, const char *uid, const char *why )
{
    char proper[16];

    if ( recovery_uid( name )[0] != '\0' || uid == NULL || uid[0] == '\0' )
        return false;
    toc_strlcpy( proper, capitalize( name ), sizeof(proper) );
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

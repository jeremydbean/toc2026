/*
 * The connection guard's record of players' addresses (2026-11-06).
 *
 * An address a player has logged in from within GUARD_TRUST_DAYS is never
 * paused by the connection guard (connguard.c). This file keeps that list,
 * in memory and in log/player_addresses.tsv, and reads the older journals
 * once to start it. It holds no game state and takes the time as an
 * argument, so tests/test_guardstore.c can play a hundred days of logins
 * against a synthetic clock and a failing disk.
 *
 * Two times per address, because they are different facts: `last` is the
 * newest login seen, `persisted` the newest one the file is known to hold.
 * A write is due when a day has passed since the last one that landed --
 * never measured from the last login, or a player logging in more often
 * than once a day would postpone the write for ever, and a restart would
 * read back their first login only (review, 2026-11-06). A write that
 * fails leaves `persisted` alone, so the next chance tries again.
 */
#ifndef TOC_GUARDSTORE_H
#define TOC_GUARDSTORE_H

#include <stdio.h>
#include <time.h>
#include "netaddr.h"

#define GUARD_PERSIST_GAP  86400    /* a line an address a day, at most */

typedef struct guard_trust
{
    uint32_t key;                   /* net_addr_guard_key */
    char     text[NET_ADDR_TEXT];   /* the address last logged in from */
    time_t   last;                  /* a player last logged in from it */
    time_t   persisted;             /* the newest login the file holds */
} GUARD_TRUST;

typedef struct guard_store
{
    GUARD_TRUST *rows;
    int          count;
    int          max;
    long         file_lines;        /* lines in the file, for the rewrite */
} GUARD_STORE;

/* An empty store of at most `max` addresses (rows is caller's array). */
void         guard_store_init   ( GUARD_STORE *s, GUARD_TRUST *rows, int max );

GUARD_TRUST *guard_store_find   ( GUARD_STORE *s, uint32_t key );

/* A login from `a` at `when`: the newest time wins. When the store is full
   the address longest unseen gives way. */
GUARD_TRUST *guard_store_note   ( GUARD_STORE *s, const NET_ADDR *a, time_t when );

/* A player logged in from the address behind `key` within `days`. */
int          guard_store_trusted( GUARD_STORE *s, uint32_t key, time_t now, long days );

/* Rows logged in from within `days` of `now`. */
int          guard_store_active ( GUARD_STORE *s, time_t now, long days );

/* Whether `t` has a login the file does not hold and a day has passed
   since the last line that landed. */
int          guard_store_due    ( const GUARD_TRUST *t );

/* Whether `t` has a login the file does not hold at all. */
int          guard_store_dirty  ( const GUARD_TRUST *t );

/* Append `t`'s newest login to `path`; 1 only when every byte reached the
   file and it closed cleanly, and then `persisted` is that login. */
int          guard_store_append ( GUARD_STORE *s, const char *path, GUARD_TRUST *t );

/* Write the whole store to `tmp` and rename it over `path`: 1 on success,
   every row then persisted. A failure leaves `path` as it was. */
int          guard_store_rewrite( GUARD_STORE *s, const char *path, const char *tmp );

/* Read `path` into the store: the number of lines read, or -1 when there
   is no such file. Rows read are persisted at the time the file gives.
   Lines starting with # are comments. */
long         guard_store_load   ( GUARD_STORE *s, const char *path );

/*
 * The one-time start from older journals, for a store with no file yet.
 * Only rows that tie an authenticated login to a numeric address in one
 * record count; a host name tells nothing about the address, and two lines
 * are never joined by nearness, since an unrelated connection can fall
 * between them.
 *
 * log/logins.tsv: "<epoch>\t<name>\t<host>\t<event>[\t<secs>]". Written
 *   after the password is accepted; connect, reconnect and new count, and
 *   only when the host is an address.
 * toc.log: "<ctime> :: <Name>@<host> has connected." (or "reconnected.",
 *   "new player."), written after the password; only a numeric host.
 *
 * 1 and the address and time, or 0.
 */
int          guard_seed_login_row( const char *line, NET_ADDR *a, time_t *when );
int          guard_seed_log_line ( const char *line, NET_ADDR *a, time_t *when );

#endif

/*
 * The wrong-password window (review, 2026-11-09): the failures one address
 * made within the last LOCK_WINDOW seconds, each with the character it
 * named. A failure counts while it is younger than the window; it leaves
 * the window, name and all, the moment it is not. Pure arithmetic with no
 * game state -- it includes no merc.h -- so tests/test_lock_window.c holds
 * it to a synthetic clock. loginlock.c keeps one per address.
 */
#ifndef TOC_LOCKWINDOW_H
#define TOC_LOCKWINDOW_H

#define LOCK_WINDOW_SLOTS 8             /* at least the lockout threshold */
#define LOCK_WINDOW_NAME  16

typedef struct lock_window
{
    long at[LOCK_WINDOW_SLOTS];         /* oldest first */
    char name[LOCK_WINDOW_SLOTS][LOCK_WINDOW_NAME];
    int  n;
} LOCK_WINDOW;

/* Drop every failure `window` seconds old or older, at `now`. */
void lock_window_expire( LOCK_WINDOW *w, long now, long window );

/* Count a failure naming `name` at `now`; the failures inside the window
   after it, this one included. Past LOCK_WINDOW_SLOTS the oldest goes. */
int  lock_window_add( LOCK_WINDOW *w, long now, long window, const char *name );

/* The failures inside the window at `now`. */
int  lock_window_count( LOCK_WINDOW *w, long now, long window );

/* A login of `name` that finished: its own slips are forgiven, and every
   failure that named anybody else stays counted, so logging into one's own
   character between guesses at another's resets nothing. */
void lock_window_forget_name( LOCK_WINDOW *w, const char *name );

void lock_window_clear( LOCK_WINDOW *w );

#endif

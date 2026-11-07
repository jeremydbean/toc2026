/*
 * Player passwords (2026-11-07): SHA-512 crypt, with the old DES hashes
 * still read and moved over at each player's next login.
 *
 * Three kinds of stored hash, all a standard crypt(3) string:
 *
 *   - DES, 13 characters, salted with the name: what every character
 *     had before. Only the first eight characters of a password count
 *     (and only seven bits of each). Read by the system's crypt(), as
 *     always; never written again while SHA-512 works.
 *
 *   - "$6$<salt>$<hash>", SHA-512 crypt: a password chosen from now on
 *     (creation, PASSWORD, RESETPWD). Every character counts.
 *
 *   - "$6$.8<salt>$<hash>", SHA-512 crypt of the old password as DES saw
 *     it -- its first eight characters, seven bits each. This is what a
 *     login moves a DES hash to (password_upgrade): the hash is SHA-512,
 *     and exactly the passwords DES accepted are still accepted, so
 *     nothing a player types changes. A new salt never starts with '.',
 *     so the marker cannot be taken by one. A player who types eight
 *     characters or fewer is checked by plain SHA-512 crypt either way,
 *     so even the system's crypt() accepts these for them.
 *
 * SHA-512 crypt is implemented here (Drepper's specification, the one
 * glibc and libxcrypt follow) so a hash this game writes can be checked
 * on any machine it runs on, whatever its crypt() supports. A self-test
 * against the specification's vectors runs before the first use; if it
 * fails, nothing is written in SHA-512 and nothing is moved over, and the
 * game goes on with DES exactly as before. Every hash written is checked
 * against the password before it is used, and against the system's
 * crypt() too where that supports SHA-512.
 *
 * This file holds no game state (no merc.h): tests/test_password.c
 * checks it against libxcrypt directly.
 */
#ifndef TOC_PASSWORD_H
#define TOC_PASSWORD_H

#include <stddef.h>

#define PASSWORD_HASH_MAX   128     /* "$6$" + 16 salt + "$" + 86 + room */
#define PASSWORD_LEGACY_MARK ".8"   /* salt prefix: a moved DES password */

/* Whether `typed` is the password `stored` holds. Never true for a NULL
   or empty `stored`, nor for one the system's crypt() cannot read. */
int password_matches( const char *typed, const char *stored );

/* A new hash of `typed` into out: SHA-512 with a fresh salt, or -- only
   when SHA-512 failed its self-test -- DES salted with `legacy_salt` (the
   name), as the game always did. 0 when nothing usable could be made. */
int password_hash( const char *typed, const char *legacy_salt,
                   char *out, size_t outsz );

/* Whether `stored` is an old DES hash a login should move to SHA-512. */
int password_is_legacy( const char *stored );

/* The SHA-512 hash a login moves `stored` to, given the password that was
   just accepted for it: into out, and 1 -- only when `stored` is DES,
   `typed` matches it, SHA-512 works, and the new hash accepts `typed`.
   The new hash accepts exactly what the old one did. */
int password_upgrade( const char *typed, const char *stored,
                      char *out, size_t outsz );

/* 1 when SHA-512 crypt passed its self-test (run once, on first use). */
int password_sha512_ok( void );

/* The SHA-512 crypt of key with the setting's salt (and rounds=, if it
   has one), into out; 0 when the setting is not "$6$...". Exposed for
   the tests. */
int password_sha512_crypt( const char *key, size_t keylen, const char *setting,
                           char *out, size_t outsz );

/* Equal strings, taking as long whatever the first difference. */
int password_hash_equal( const char *a, const char *b );

#endif

/*
 * src/password.c against the system's libxcrypt (tests/test_password.py
 * builds and runs this). Prints "ok" and exits 0 when everything holds;
 * otherwise a FAIL line for each thing that does not.
 *
 *   - our SHA-512 crypt reproduces the specification's vectors and
 *     libxcrypt for keys and salts of every awkward length, and rounds=;
 *   - a new hash is SHA-512 with a 16-character salt that never starts
 *     with '.', accepts its password whole and nothing shorter or longer;
 *   - a DES hash moved at login accepts exactly what DES accepted, for
 *     thousands of passwords and their near misses (the first eight
 *     characters, a ninth changed, a case changed, the high bit set);
 *   - only a real DES hash is moved, only with its own password, and
 *     never twice; nothing is accepted against a NULL, empty or broken
 *     hash; other crypt formats read as they always did;
 *   - the system's crypt() reads every hash we write -- and a moved one
 *     for any password of eight characters or fewer -- so code from
 *     before this change, put back by a rollback, still lets them in.
 */
#define _DEFAULT_SOURCE
#include <crypt.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "password.h"

static int failures;

#define CHECK(cond, ...) do { if ( !(cond) ) { failures++; printf( "FAIL " __VA_ARGS__ ); printf( "\n" ); } } while ( 0 )

static const char alphabet[] =
    "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

static unsigned long rng = 20261107UL;

static unsigned next_rand( void )
{
    rng = rng * 6364136223846793005UL + 1442695040888963407UL;
    return (unsigned) ( rng >> 33 );
}

static void random_printable( char *out, int len )
{
    int i;

    for ( i = 0; i < len; i++ )
        out[i] = (char) ( 0x20 + next_rand() % 95 );   /* what the game's input keeps */
    out[len] = '\0';
}

static int sys_matches( const char *typed, const char *stored )
{
    const char *r = crypt( typed, stored );

    return r != NULL && strcmp( r, stored ) == 0;
}

static void test_vectors( void )
{
    static const struct { const char *setting, *key, *expect; } v[] =
    {
        { "$6$saltstring", "Hello world!",
          "$6$saltstring$svn8UoSVapNtMuq1ukKS4tPQd8iKwSMHWjl/O817G3uBnIFNjnQJuesI68u4OTLiBFdcbYEdFCoEOfaS35inz1" },
        { "$6$rounds=10000$saltstringsaltstring", "Hello world!",
          "$6$rounds=10000$saltstringsaltst$OW1/O6BYHV6BcXZu8QVeXbDWra3Oeqh0sbHbbMCVNSnCM/UrjmM0Dp8vOuZeHBy/YTBmSK6H9qs/y3RnOaw5v." },
        { "$6$rounds=5000$toolongsaltstring", "This is just a test",
          "$6$rounds=5000$toolongsaltstrin$lQ8jolhgVRVhY4b5pZKaysCLi0QBxGoNeKQzQ3glMhwllF7oGDZxUhx1yxdYcz/e1JSbq3y6JMxxl8audkUEm0" },
        { "$6$rounds=1400$anotherlongsaltstring",
          "a very much longer text to encrypt.  This one even stretches over morethan one line.",
          "$6$rounds=1400$anotherlongsalts$POfYwTEok97VWcjxIiSOjiykti.o/pQs.wPvMxQ6Fm7I6IoYN3CmLs66x9t0oSwbtEW7o7UmJEiDwGqd8p4ur1" },
        { "$6$rounds=77777$short", "we have a short salt string but not a short password",
          "$6$rounds=77777$short$WuQyW2YR.hBNpjjRhpYD/ifIw05xdfeEyQoMxIXbkvr0gge1a1x3yRULJ5CCaUeOxFmtlcGZelFl5CxtgfiAc0" },
        { "$6$rounds=123456$asaltof16chars..", "a short string",
          "$6$rounds=123456$asaltof16chars..$BtCwjqMJGx5hrJhZywWvt0RLE8uZ4oPwcelCjmw2kSYu.Ec6ycULevoBK25fs2xXgMNrCzIMVcgEJAstJeonj1" },
        { "$6$rounds=10$roundstoolow", "the minimum number is still observed",
          "$6$rounds=1000$roundstoolow$kUMsbe306n21p9R.FRkW3IGn.S9NPN0x50YhH1xhLsPuWGsUSklZt58jaTfF4ZEQpyUNGc0dqbpBYYBaHHrsX." }
    };
    char out[PASSWORD_HASH_MAX];
    size_t i;

    CHECK( password_sha512_ok(), "self-test" );
    for ( i = 0; i < sizeof(v) / sizeof(v[0]); i++ )
    {
        CHECK( password_sha512_crypt( v[i].key, strlen( v[i].key ), v[i].setting, out, sizeof(out) )
               && strcmp( out, v[i].expect ) == 0, "vector %d: %s", (int) i, out );
        CHECK( password_matches( v[i].key, v[i].expect ), "vector %d does not match", (int) i );
    }
    CHECK( !password_sha512_crypt( "x", 1, "$5$abc", out, sizeof(out) ), "$5$ is not ours" );
    CHECK( !password_sha512_crypt( "x", 1, "$6$abc", out, 20 ), "a short buffer is refused" );
}

static void test_against_libxcrypt( void )
{
    static const int lengths[] = { 0, 1, 7, 8, 9, 15, 16, 31, 63, 64, 65, 100, 127, 128, 129, 200, 255 };
    char key[300], setting[64], salt[24], ours[PASSWORD_HASH_MAX];
    const char *sys;
    int i, n, s;

    for ( i = 0; i < 300; i++ )
    {
        int len = i < (int) ( sizeof(lengths) / sizeof(lengths[0]) )
                ? lengths[i] : (int) ( next_rand() % 200 );
        int saltlen = (int) ( next_rand() % 20 );

        random_printable( key, len );
        for ( s = 0; s < saltlen; s++ )
            salt[s] = alphabet[next_rand() % 64];
        salt[saltlen] = '\0';
        if ( i % 5 == 0 )
            n = snprintf( setting, sizeof(setting), "$6$rounds=%u$%s", 1000 + next_rand() % 1500, salt );
        else
            n = snprintf( setting, sizeof(setting), "$6$%s", salt );
        (void) n;
        sys = crypt( key, setting );
        if ( sys == NULL || sys[0] == '*' )
            continue;           /* a setting libxcrypt will not take: nothing to compare */
        CHECK( password_sha512_crypt( key, strlen( key ), setting, ours, sizeof(ours) )
               && strcmp( ours, sys ) == 0, "libxcrypt disagrees: len %d setting %s", len, setting );
    }
}

static void test_new_hashes( void )
{
    char pw[64], out[PASSWORD_HASH_MAX], longer[80], other[PASSWORD_HASH_MAX];
    int i, len;

    for ( i = 0; i < 60; i++ )
    {
        len = 5 + (int) ( next_rand() % 30 );
        random_printable( pw, len );
        CHECK( password_hash( pw, "Zname", out, sizeof(out) ), "hash %d", i );
        CHECK( strncmp( out, "$6$", 3 ) == 0 && strlen( out ) == 3 + 16 + 1 + 86,
               "a new hash is SHA-512 with a 16-character salt: %s", out );
        CHECK( out[3] != '.', "a new salt never starts with '.': %s", out );
        CHECK( strchr( out, '~' ) == NULL, "no tilde" );
        CHECK( !password_is_legacy( out ), "a new hash is not DES" );
        CHECK( password_matches( pw, out ), "a new hash accepts its password" );
        CHECK( sys_matches( pw, out ), "the system's crypt reads our hash" );
        snprintf( longer, sizeof(longer), "%sx", pw );
        CHECK( !password_matches( longer, out ), "one more character is refused" );
        pw[len - 1] = '\0';
        CHECK( !password_matches( pw, out ), "one fewer character is refused" );
        if ( len > 8 )
        {
            pw[8] = '\0';
            CHECK( !password_matches( pw, out ), "the first eight alone are refused" );
        }
        CHECK( !password_upgrade( pw, out, other, sizeof(other) ), "a SHA-512 hash is never moved" );
    }
    /* Two hashes of one password differ by their salt. */
    {
        char a[PASSWORD_HASH_MAX], b[PASSWORD_HASH_MAX];

        CHECK( password_hash( "Zsamepass", "Zn", a, sizeof(a) ) && password_hash( "Zsamepass", "Zn", b, sizeof(b) )
               && strcmp( a, b ) != 0, "salts differ" );
    }
}

/* Does `typed` get in, by DES and by the moved hash? They must agree. */
static void compare( const char *typed, const char *des, const char *moved, const char *what )
{
    int by_des = sys_matches( typed, des );
    int by_sha = password_matches( typed, moved );
    int has_80 = 0, i;

    for ( i = 0; i < 8 && typed[i] != '\0'; i++ )
        if ( (unsigned char) typed[i] == 0x80 )
            has_80 = 1;
    if ( has_80 )
        CHECK( !by_sha, "%s: a 0x80 byte is refused (the game's input never has one)", what );
    else
        CHECK( by_des == by_sha, "%s: DES says %d, the moved hash %d (typed len %d)",
               what, by_des, by_sha, (int) strlen( typed ) );
}

static void test_moved_hashes( void )
{
    char pw[64], v[80], moved[PASSWORD_HASH_MAX], again[PASSWORD_HASH_MAX];
    const char *d;
    char des[32];
    int i, len, k;

    for ( i = 0; i < 150; i++ )
    {
        len = 1 + (int) ( next_rand() % 20 );
        random_printable( pw, len );
        d = crypt( pw, i % 2 ? "Zn" : "Al" );
        if ( d == NULL )
        {
            CHECK( 0, "DES unavailable" );
            return;
        }
        snprintf( des, sizeof(des), "%s", d );
        CHECK( password_is_legacy( des ), "a DES hash is legacy: %s", des );
        CHECK( password_matches( pw, des ), "DES is read as before" );

        CHECK( password_upgrade( pw, des, moved, sizeof(moved) ), "moved %d", i );
        CHECK( strncmp( moved, "$6$" PASSWORD_LEGACY_MARK, 5 ) == 0 && strlen( moved ) == 3 + 16 + 1 + 86,
               "a moved hash is marked SHA-512: %s", moved );
        CHECK( strchr( moved, '~' ) == NULL, "no tilde" );
        CHECK( !password_upgrade( pw, moved, again, sizeof(again) ), "never moved twice" );

        compare( pw, des, moved, "the password" );
        snprintf( v, sizeof(v), "%.8s", pw );
        compare( v, des, moved, "the first eight" );
        snprintf( v, sizeof(v), "%.8s%s", pw, "ZZtail" );
        compare( v, des, moved, "the first eight and more" );
        snprintf( v, sizeof(v), "%.7s", pw );
        compare( v, des, moved, "the first seven" );
        snprintf( v, sizeof(v), "%sQ", pw );
        compare( v, des, moved, "one more character" );
        for ( k = 0; k < len && k < 10; k++ )
        {
            snprintf( v, sizeof(v), "%s", pw );
            v[k] = (char) ( v[k] == 'a' ? 'b' : 'a' );
            compare( v, des, moved, "one character changed" );
            snprintf( v, sizeof(v), "%s", pw );
            v[k] = (char) ( (unsigned char) v[k] | 0x80 );
            compare( v, des, moved, "the high bit set" );
        }
        snprintf( v, sizeof(v), "%s", pw );
        for ( k = 0; v[k] != '\0'; k++ )
            if ( v[k] >= 'a' && v[k] <= 'z' ) { v[k] = (char) ( v[k] - 32 ); break; }
        compare( v, des, moved, "a case changed" );
        compare( "", des, moved, "nothing" );

        /* Code from before this change reads it for eight or fewer. */
        if ( len <= 8 )
            CHECK( sys_matches( pw, moved ), "the system's crypt reads a moved hash of %d characters", len );

        /* Only with its own password. */
        snprintf( v, sizeof(v), "%sQ", pw );
        if ( !sys_matches( v, des ) )
            CHECK( !password_upgrade( v, des, again, sizeof(again) ), "a wrong password moves nothing" );
    }
}

static void test_refusals( void )
{
    char out[PASSWORD_HASH_MAX];
    const char *md5 = crypt( "Zmd5pass", "$1$saltsalt" );

    CHECK( !password_matches( "x", NULL ), "NULL hash" );
    CHECK( !password_matches( "x", "" ), "empty hash" );
    CHECK( !password_matches( NULL, "abcdefghijklm" ), "NULL password" );
    CHECK( !password_matches( "x", "$6$" ), "a bare $6$" );
    CHECK( !password_matches( "x", "$6$abc$" ), "a $6$ with no hash" );
    CHECK( !password_matches( "", "$6$abc$" ), "nothing against a $6$ with no hash" );
    CHECK( !password_matches( "x", "*" ), "a locked hash" );
    if ( md5 != NULL && strncmp( md5, "$1$", 3 ) == 0 )
    {
        CHECK( password_matches( "Zmd5pass", md5 ), "MD5 reads as it always did" );
        CHECK( !password_upgrade( "Zmd5pass", md5, out, sizeof(out) ), "MD5 is not moved" );
    }
    CHECK( !password_is_legacy( NULL ) && !password_is_legacy( "" ), "nothing is not DES" );
    CHECK( !password_is_legacy( "abcdefghijkl" ) && !password_is_legacy( "abcdefghijklmn" ), "DES is 13" );
    CHECK( !password_is_legacy( "abcdefghijk~m" ) && !password_is_legacy( "abcdef$hijklm" ), "DES's alphabet" );
    CHECK( !password_upgrade( "Zsomepass", "abcdefghijklm", out, sizeof(out) ), "a hash it does not match" );
    CHECK( !password_upgrade( "Zsomepass", crypt( "Zsomepass", "Zn" ), out, 20 ), "a short buffer" );
    CHECK( password_hash_equal( "abc", "abc" ) && !password_hash_equal( "abc", "abd" )
           && !password_hash_equal( "abc", "abcd" ) && !password_hash_equal( NULL, "a" ), "equal" );
}

int main( void )
{
    test_vectors();
    test_against_libxcrypt();
    test_new_hashes();
    test_moved_hashes();
    test_refusals();
    if ( failures == 0 )
        printf( "ok\n" );
    return failures == 0 ? 0 : 1;
}

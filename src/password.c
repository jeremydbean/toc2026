/*
 * Player passwords: see password.h.
 */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#ifndef _XOPEN_SOURCE
#define _XOPEN_SOURCE 700
#endif

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#if !defined(NOCRYPT) && !defined(__APPLE__)
#include <crypt.h>
#endif
#include "password.h"

/* ------------------------------------------------------------------ */
/* SHA-512 (FIPS 180-4).                                               */
/* ------------------------------------------------------------------ */

typedef struct
{
    uint64_t      h[8];
    uint64_t      bytes;            /* total fed in, which fits: keys are short */
    unsigned char buf[128];
    size_t        used;
} SHA512_CTX;

static const uint64_t sha512_k[80] =
{
    0x428a2f98d728ae22ULL, 0x7137449123ef65cdULL, 0xb5c0fbcfec4d3b2fULL, 0xe9b5dba58189dbbcULL,
    0x3956c25bf348b538ULL, 0x59f111f1b605d019ULL, 0x923f82a4af194f9bULL, 0xab1c5ed5da6d8118ULL,
    0xd807aa98a3030242ULL, 0x12835b0145706fbeULL, 0x243185be4ee4b28cULL, 0x550c7dc3d5ffb4e2ULL,
    0x72be5d74f27b896fULL, 0x80deb1fe3b1696b1ULL, 0x9bdc06a725c71235ULL, 0xc19bf174cf692694ULL,
    0xe49b69c19ef14ad2ULL, 0xefbe4786384f25e3ULL, 0x0fc19dc68b8cd5b5ULL, 0x240ca1cc77ac9c65ULL,
    0x2de92c6f592b0275ULL, 0x4a7484aa6ea6e483ULL, 0x5cb0a9dcbd41fbd4ULL, 0x76f988da831153b5ULL,
    0x983e5152ee66dfabULL, 0xa831c66d2db43210ULL, 0xb00327c898fb213fULL, 0xbf597fc7beef0ee4ULL,
    0xc6e00bf33da88fc2ULL, 0xd5a79147930aa725ULL, 0x06ca6351e003826fULL, 0x142929670a0e6e70ULL,
    0x27b70a8546d22ffcULL, 0x2e1b21385c26c926ULL, 0x4d2c6dfc5ac42aedULL, 0x53380d139d95b3dfULL,
    0x650a73548baf63deULL, 0x766a0abb3c77b2a8ULL, 0x81c2c92e47edaee6ULL, 0x92722c851482353bULL,
    0xa2bfe8a14cf10364ULL, 0xa81a664bbc423001ULL, 0xc24b8b70d0f89791ULL, 0xc76c51a30654be30ULL,
    0xd192e819d6ef5218ULL, 0xd69906245565a910ULL, 0xf40e35855771202aULL, 0x106aa07032bbd1b8ULL,
    0x19a4c116b8d2d0c8ULL, 0x1e376c085141ab53ULL, 0x2748774cdf8eeb99ULL, 0x34b0bcb5e19b48a8ULL,
    0x391c0cb3c5c95a63ULL, 0x4ed8aa4ae3418acbULL, 0x5b9cca4f7763e373ULL, 0x682e6ff3d6b2b8a3ULL,
    0x748f82ee5defb2fcULL, 0x78a5636f43172f60ULL, 0x84c87814a1f0ab72ULL, 0x8cc702081a6439ecULL,
    0x90befffa23631e28ULL, 0xa4506cebde82bde9ULL, 0xbef9a3f7b2c67915ULL, 0xc67178f2e372532bULL,
    0xca273eceea26619cULL, 0xd186b8c721c0c207ULL, 0xeada7dd6cde0eb1eULL, 0xf57d4f7fee6ed178ULL,
    0x06f067aa72176fbaULL, 0x0a637dc5a2c898a6ULL, 0x113f9804bef90daeULL, 0x1b710b35131c471bULL,
    0x28db77f523047d84ULL, 0x32caab7b40c72493ULL, 0x3c9ebe0a15c9bebcULL, 0x431d67c49c100d4cULL,
    0x4cc5d4becb3e42b6ULL, 0x597f299cfc657e2aULL, 0x5fcb6fab3ad6faecULL, 0x6c44198c4a475817ULL
};

#define ROTR64(x, n)  ( ( (x) >> (n) ) | ( (x) << ( 64 - (n) ) ) )

static void sha512_block( SHA512_CTX *c, const unsigned char *p )
{
    uint64_t w[80], a, b, d, e, f, g, h, cc, t1, t2;
    int i;

    for ( i = 0; i < 16; i++ )
        w[i] = ( (uint64_t) p[8*i]   << 56 ) | ( (uint64_t) p[8*i+1] << 48 )
             | ( (uint64_t) p[8*i+2] << 40 ) | ( (uint64_t) p[8*i+3] << 32 )
             | ( (uint64_t) p[8*i+4] << 24 ) | ( (uint64_t) p[8*i+5] << 16 )
             | ( (uint64_t) p[8*i+6] <<  8 ) |   (uint64_t) p[8*i+7];
    for ( i = 16; i < 80; i++ )
    {
        uint64_t s0 = ROTR64( w[i-15], 1 ) ^ ROTR64( w[i-15], 8 ) ^ ( w[i-15] >> 7 );
        uint64_t s1 = ROTR64( w[i-2], 19 ) ^ ROTR64( w[i-2], 61 ) ^ ( w[i-2] >> 6 );
        w[i] = w[i-16] + s0 + w[i-7] + s1;
    }

    a = c->h[0]; b = c->h[1]; cc = c->h[2]; d = c->h[3];
    e = c->h[4]; f = c->h[5]; g = c->h[6]; h = c->h[7];
    for ( i = 0; i < 80; i++ )
    {
        uint64_t S1  = ROTR64( e, 14 ) ^ ROTR64( e, 18 ) ^ ROTR64( e, 41 );
        uint64_t ch  = ( e & f ) ^ ( ~e & g );
        uint64_t S0  = ROTR64( a, 28 ) ^ ROTR64( a, 34 ) ^ ROTR64( a, 39 );
        uint64_t maj = ( a & b ) ^ ( a & cc ) ^ ( b & cc );

        t1 = h + S1 + ch + sha512_k[i] + w[i];
        t2 = S0 + maj;
        h = g; g = f; f = e; e = d + t1;
        d = cc; cc = b; b = a; a = t1 + t2;
    }
    c->h[0] += a; c->h[1] += b; c->h[2] += cc; c->h[3] += d;
    c->h[4] += e; c->h[5] += f; c->h[6] += g; c->h[7] += h;
}

static void sha512_init( SHA512_CTX *c )
{
    c->h[0] = 0x6a09e667f3bcc908ULL; c->h[1] = 0xbb67ae8584caa73bULL;
    c->h[2] = 0x3c6ef372fe94f82bULL; c->h[3] = 0xa54ff53a5f1d36f1ULL;
    c->h[4] = 0x510e527fade682d1ULL; c->h[5] = 0x9b05688c2b3e6c1fULL;
    c->h[6] = 0x1f83d9abfb41bd6bULL; c->h[7] = 0x5be0cd19137e2179ULL;
    c->bytes = 0;
    c->used = 0;
}

static void sha512_update( SHA512_CTX *c, const void *data, size_t len )
{
    const unsigned char *p = (const unsigned char *) data;

    c->bytes += len;
    while ( len > 0 )
    {
        size_t take = 128 - c->used;

        if ( take > len )
            take = len;
        memcpy( c->buf + c->used, p, take );
        c->used += take;
        p += take;
        len -= take;
        if ( c->used == 128 )
        {
            sha512_block( c, c->buf );
            c->used = 0;
        }
    }
}

static void sha512_final( SHA512_CTX *c, unsigned char out[64] )
{
    uint64_t bits_lo = c->bytes << 3, bits_hi = c->bytes >> 61;
    int i;

    c->buf[c->used++] = 0x80;
    if ( c->used > 112 )
    {
        memset( c->buf + c->used, 0, 128 - c->used );
        sha512_block( c, c->buf );
        c->used = 0;
    }
    memset( c->buf + c->used, 0, 112 - c->used );
    for ( i = 0; i < 8; i++ )
    {
        c->buf[112 + i] = (unsigned char) ( bits_hi >> ( 56 - 8 * i ) );
        c->buf[120 + i] = (unsigned char) ( bits_lo >> ( 56 - 8 * i ) );
    }
    sha512_block( c, c->buf );
    for ( i = 0; i < 64; i++ )
        out[i] = (unsigned char) ( c->h[i / 8] >> ( 56 - 8 * ( i % 8 ) ) );
    memset( c, 0, sizeof(*c) );
}

/* ------------------------------------------------------------------ */
/* SHA-512 crypt ("$6$"), after Ulrich Drepper's specification.        */
/* ------------------------------------------------------------------ */

#define SHA_SALT_MAX     16
#define SHA_ROUNDS_DEF   5000
#define SHA_ROUNDS_MIN   1000
#define SHA_ROUNDS_MAX   999999999UL

static const char itoa64[] =
    "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

static char *b64_from_24bit( char *p, unsigned b2, unsigned b1, unsigned b0, int n )
{
    unsigned long w = ( (unsigned long) b2 << 16 ) | ( (unsigned long) b1 << 8 ) | b0;

    while ( n-- > 0 )
    {
        *p++ = itoa64[w & 0x3f];
        w >>= 6;
    }
    return p;
}

int password_sha512_crypt( const char *key, size_t keylen, const char *setting,
                           char *out, size_t outsz )
{
    static const unsigned char order[21][3] =
    {
        {  0, 21, 42 }, { 22, 43,  1 }, { 44,  2, 23 }, {  3, 24, 45 },
        { 25, 46,  4 }, { 47,  5, 26 }, {  6, 27, 48 }, { 28, 49,  7 },
        { 50,  8, 29 }, {  9, 30, 51 }, { 31, 52, 10 }, { 53, 11, 32 },
        { 12, 33, 54 }, { 34, 55, 13 }, { 56, 14, 35 }, { 15, 36, 57 },
        { 37, 58, 16 }, { 59, 17, 38 }, { 18, 39, 60 }, { 40, 61, 19 },
        { 62, 20, 41 }
    };
    SHA512_CTX ctx, alt;
    unsigned char a[64], b[64], dp[64], ds[64];
    unsigned char *p_bytes = NULL, *s_bytes = NULL;
    const char *salt;
    size_t saltlen, cnt;
    unsigned long rounds = SHA_ROUNDS_DEF, r;
    int custom = 0, i, n;
    char head[48], *q;
    int ok = 0;

    if ( key == NULL || setting == NULL || out == NULL
      || strncmp( setting, "$6$", 3 ) != 0 )
        return 0;
    salt = setting + 3;
    if ( strncmp( salt, "rounds=", 7 ) == 0 )
    {
        char *end;
        unsigned long want = strtoul( salt + 7, &end, 10 );

        if ( *end == '$' && end != salt + 7 )
        {
            salt = end + 1;
            rounds = want < SHA_ROUNDS_MIN ? SHA_ROUNDS_MIN
                   : want > SHA_ROUNDS_MAX ? SHA_ROUNDS_MAX : want;
            custom = 1;
        }
    }
    saltlen = strcspn( salt, "$" );
    if ( saltlen > SHA_SALT_MAX )
        saltlen = SHA_SALT_MAX;

    /* B = H(key salt key) */
    sha512_init( &alt );
    sha512_update( &alt, key, keylen );
    sha512_update( &alt, salt, saltlen );
    sha512_update( &alt, key, keylen );
    sha512_final( &alt, b );

    /* A = H(key salt B... and a bit walk of keylen) */
    sha512_init( &ctx );
    sha512_update( &ctx, key, keylen );
    sha512_update( &ctx, salt, saltlen );
    for ( cnt = keylen; cnt > 64; cnt -= 64 )
        sha512_update( &ctx, b, 64 );
    sha512_update( &ctx, b, cnt );
    for ( cnt = keylen; cnt > 0; cnt >>= 1 )
        if ( cnt & 1 )
            sha512_update( &ctx, b, 64 );
        else
            sha512_update( &ctx, key, keylen );
    sha512_final( &ctx, a );

    /* P: the key, keylen times, hashed and stretched to keylen bytes. */
    sha512_init( &alt );
    for ( cnt = 0; cnt < keylen; cnt++ )
        sha512_update( &alt, key, keylen );
    sha512_final( &alt, dp );
    p_bytes = (unsigned char *) malloc( keylen > 0 ? keylen : 1 );
    if ( p_bytes == NULL )
        goto done;
    for ( cnt = 0; cnt < keylen; cnt++ )
        p_bytes[cnt] = dp[cnt % 64];

    /* S: the salt, 16 + A[0] times, hashed and cut to the salt's length. */
    sha512_init( &alt );
    for ( cnt = 0; cnt < 16u + a[0]; cnt++ )
        sha512_update( &alt, salt, saltlen );
    sha512_final( &alt, ds );
    s_bytes = (unsigned char *) malloc( saltlen > 0 ? saltlen : 1 );
    if ( s_bytes == NULL )
        goto done;
    for ( cnt = 0; cnt < saltlen; cnt++ )
        s_bytes[cnt] = ds[cnt % 64];

    for ( r = 0; r < rounds; r++ )
    {
        sha512_init( &ctx );
        if ( r & 1 )
            sha512_update( &ctx, p_bytes, keylen );
        else
            sha512_update( &ctx, a, 64 );
        if ( r % 3 != 0 )
            sha512_update( &ctx, s_bytes, saltlen );
        if ( r % 7 != 0 )
            sha512_update( &ctx, p_bytes, keylen );
        if ( r & 1 )
            sha512_update( &ctx, a, 64 );
        else
            sha512_update( &ctx, p_bytes, keylen );
        sha512_final( &ctx, a );
    }

    if ( custom )
        n = snprintf( head, sizeof(head), "$6$rounds=%lu$", rounds );
    else
        n = snprintf( head, sizeof(head), "$6$" );
    /* head, salt, '$', 86 characters, NUL */
    if ( n < 0 || (size_t) n + saltlen + 1 + 86 + 1 > outsz )
        goto done;
    memcpy( out, head, (size_t) n );
    q = out + n;
    memcpy( q, salt, saltlen );
    q += saltlen;
    *q++ = '$';
    for ( i = 0; i < 21; i++ )
        q = b64_from_24bit( q, a[order[i][0]], a[order[i][1]], a[order[i][2]], 4 );
    q = b64_from_24bit( q, 0, 0, a[63], 2 );
    *q = '\0';
    ok = 1;

done:
    if ( p_bytes != NULL )
    {
        memset( p_bytes, 0, keylen > 0 ? keylen : 1 );
        free( p_bytes );
    }
    if ( s_bytes != NULL )
        free( s_bytes );
    memset( a, 0, sizeof(a) );
    memset( b, 0, sizeof(b) );
    memset( dp, 0, sizeof(dp) );
    memset( ds, 0, sizeof(ds) );
    return ok;
}

/* ------------------------------------------------------------------ */
/* The game's rules.                                                   */
/* ------------------------------------------------------------------ */

int password_hash_equal( const char *a, const char *b )
{
    size_t la, lb, i;
    unsigned diff;

    if ( a == NULL || b == NULL )
        return 0;
    la = strlen( a );
    lb = strlen( b );
    diff = (unsigned) ( la ^ lb );
    for ( i = 0; i < la && i < lb; i++ )
        diff |= (unsigned) ( (unsigned char) a[i] ^ (unsigned char) b[i] );
    return diff == 0;
}

/* The system's crypt(), as the game always called it. NULL when it has
   no answer. */
static const char *system_crypt( const char *typed, const char *stored )
{
#if defined(NOCRYPT)
    (void) stored;
    return typed;
#else
    return crypt( typed, stored );
#endif
}

/* The password as DES saw it: the first eight characters, seven bits of
   each. 0 when a character would become a NUL (a byte of 0x80), which
   this form cannot say; the game's input never holds one (comm.c keeps
   printable ASCII only). */
static int des_key_form( const char *typed, char out[9] )
{
    int i;

    for ( i = 0; i < 8 && typed[i] != '\0'; i++ )
    {
        out[i] = (char) ( (unsigned char) typed[i] & 0x7f );
        if ( out[i] == '\0' )
            return 0;
    }
    out[i] = '\0';
    return 1;
}

static int sha512_setting_is_legacy( const char *stored )
{
    const char *salt = stored + 3;

    if ( strncmp( salt, "rounds=", 7 ) == 0 )
    {
        const char *end = strchr( salt, '$' );

        if ( end == NULL )
            return 0;
        salt = end + 1;
    }
    return strncmp( salt, PASSWORD_LEGACY_MARK, strlen( PASSWORD_LEGACY_MARK ) ) == 0;
}

static int sha512_matches( const char *typed, const char *stored )
{
    char key[9], hash[PASSWORD_HASH_MAX];
    const char *use = typed;
    int ok;

    if ( sha512_setting_is_legacy( stored ) )
    {
        if ( !des_key_form( typed, key ) )
            return 0;
        use = key;
    }
    if ( password_sha512_ok() )
        ok = password_sha512_crypt( use, strlen( use ), stored, hash, sizeof(hash) )
          && password_hash_equal( hash, stored );
    else
    {
        /* Our own failed its self-test: let the system's crypt() try,
           which on Linux reads SHA-512 itself. */
        const char *sys = system_crypt( use, stored );

        ok = sys != NULL && password_hash_equal( sys, stored );
    }
    memset( key, 0, sizeof(key) );
    memset( hash, 0, sizeof(hash) );
    return ok;
}

int password_matches( const char *typed, const char *stored )
{
    const char *sys;

    if ( typed == NULL || stored == NULL || stored[0] == '\0' )
        return 0;
    if ( strncmp( stored, "$6$", 3 ) == 0 )
        return sha512_matches( typed, stored );
    /* Everything else is read exactly as it always was. */
    sys = system_crypt( typed, stored );
    return sys != NULL && strcmp( sys, stored ) == 0;
}

int password_is_legacy( const char *stored )
{
    size_t i;

    if ( stored == NULL || strlen( stored ) != 13 )
        return 0;
    for ( i = 0; i < 13; i++ )
        if ( strchr( itoa64, stored[i] ) == NULL || stored[i] == '\0' )
            return 0;
    return 1;
}

/* Self-test: the specification's own vectors (the cheap ones; the
   others are in tests/test_password.c). */
static int sha512_self_test( void )
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
        { "$6$rounds=10$roundstoolow", "the minimum number is still observed",
          "$6$rounds=1000$roundstoolow$kUMsbe306n21p9R.FRkW3IGn.S9NPN0x50YhH1xhLsPuWGsUSklZt58jaTfF4ZEQpyUNGc0dqbpBYYBaHHrsX." }
    };
    char out[PASSWORD_HASH_MAX];
    size_t i;

    for ( i = 0; i < sizeof(v) / sizeof(v[0]); i++ )
        if ( !password_sha512_crypt( v[i].key, strlen( v[i].key ), v[i].setting,
                                     out, sizeof(out) )
          || strcmp( out, v[i].expect ) != 0 )
            return 0;
    return 1;
}

int password_sha512_ok( void )
{
    static int state = -1;

    if ( state < 0 )
        state = sha512_self_test();
    return state;
}

/* Sixteen salt characters from the kernel's randomness, or -- where there
   is none -- from whatever this moment offers, hashed: a salt need only
   differ, not be secret. A new salt never starts with '.', the mark of a
   moved DES password. */
static void make_salt( char salt[SHA_SALT_MAX + 1], int legacy )
{
    unsigned char raw[64];
    size_t got = 0, i, start;
    FILE *fp;

    fp = fopen( "/dev/urandom", "rb" );
    if ( fp != NULL )
    {
        got = fread( raw, 1, sizeof(raw), fp );
        fclose( fp );
    }
    if ( got < SHA_SALT_MAX )
    {
        static unsigned long counter;
        SHA512_CTX c;
        struct { time_t t; clock_t k; long pid; unsigned long n; const void *where; } seed;

        seed.t = time( NULL );
        seed.k = clock();
        seed.pid = (long) getpid();
        seed.n = ++counter;
        seed.where = (const void *) &seed;
        sha512_init( &c );
        sha512_update( &c, raw, got );
        sha512_update( &c, &seed, sizeof(seed) );
        sha512_final( &c, raw );
    }

    start = 0;
    if ( legacy )
    {
        memcpy( salt, PASSWORD_LEGACY_MARK, strlen( PASSWORD_LEGACY_MARK ) );
        start = strlen( PASSWORD_LEGACY_MARK );
    }
    for ( i = start; i < SHA_SALT_MAX; i++ )
        salt[i] = itoa64[raw[i] & 0x3f];
    if ( !legacy && salt[0] == '.' )
        salt[0] = itoa64[2 + raw[SHA_SALT_MAX] % 62];   /* '0'..'z', never '.' or '/' */
    salt[SHA_SALT_MAX] = '\0';
    memset( raw, 0, sizeof(raw) );
}

/* The system's crypt(), where it reads SHA-512, must agree with ours. */
static int system_agrees( const char *key, const char *hash )
{
    const char *sys = system_crypt( key, hash );

    if ( sys == NULL || strncmp( sys, "$6$", 3 ) != 0 )
        return 1;                   /* it does not read SHA-512: nothing to ask */
    return strcmp( sys, hash ) == 0;
}

static int sha512_new( const char *key, int legacy, char *out, size_t outsz )
{
    char setting[4 + SHA_SALT_MAX + 1], salt[SHA_SALT_MAX + 1];

    make_salt( salt, legacy );
    snprintf( setting, sizeof(setting), "$6$%s", salt );
    if ( !password_sha512_crypt( key, strlen( key ), setting, out, outsz ) )
        return 0;
    return system_agrees( key, out );
}

int password_hash( const char *typed, const char *legacy_salt, char *out, size_t outsz )
{
    const char *des;

    if ( typed == NULL || out == NULL || outsz == 0 )
        return 0;
    out[0] = '\0';
#if !defined(NOCRYPT)
    if ( password_sha512_ok() )
    {
        if ( sha512_new( typed, 0, out, outsz ) && password_matches( typed, out )
          && strchr( out, '~' ) == NULL )
            return 1;
        out[0] = '\0';
    }
#endif
    /* As the game always did. */
    des = system_crypt( typed, legacy_salt != NULL ? legacy_salt : "" );
    if ( des == NULL || des[0] == '\0' || des[0] == '*' || strlen( des ) >= outsz
      || strchr( des, '~' ) != NULL )
        return 0;
    memcpy( out, des, strlen( des ) + 1 );
    return 1;
}

int password_upgrade( const char *typed, const char *stored, char *out, size_t outsz )
{
    char key[9];
    int ok = 0;

    if ( typed == NULL || out == NULL || outsz == 0 )
        return 0;
    out[0] = '\0';
#if defined(NOCRYPT)
    (void) stored;
    (void) key;
    return 0;
#else
    if ( !password_sha512_ok() || !password_is_legacy( stored )
      || !password_matches( typed, stored ) || !des_key_form( typed, key ) )
        return 0;
    if ( sha512_new( key, 1, out, outsz )
      && sha512_setting_is_legacy( out )
      && password_matches( typed, out )
      && password_matches( key, out )
      && strchr( out, '~' ) == NULL )
        ok = 1;
    memset( key, 0, sizeof(key) );
    if ( !ok )
        out[0] = '\0';
    return ok;
#endif
}

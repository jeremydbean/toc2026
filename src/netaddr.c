/*
 * Client network addresses: see netaddr.h.
 */
#ifndef _DEFAULT_SOURCE
#define _DEFAULT_SOURCE
#endif
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif

#include <arpa/inet.h>
#include <netinet/in.h>
#include <string.h>
#include <sys/socket.h>
#include "netaddr.h"

static const unsigned char v4_mapped[12] = { 0,0,0,0, 0,0,0,0, 0,0,0xff,0xff };

int net_addr_parse( const char *text, NET_ADDR *out )
{
    struct in_addr four;
    struct in6_addr six;
    size_t n;

    if ( text == NULL || out == NULL )
        return 0;
    memset( out, 0, sizeof(*out) );
    n = strlen( text );
    if ( n == 0 || n >= 64 )
        return 0;
    /* inet_pton reads the whole string or refuses it, so a trailing word
       or a short dotted prefix is no address. */
    if ( inet_pton( AF_INET, text, &four ) == 1 )
    {
        out->family = 4;
        memcpy( out->b, &four.s_addr, 4 );
        return 1;
    }
    if ( inet_pton( AF_INET6, text, &six ) == 1 )
    {
        if ( memcmp( six.s6_addr, v4_mapped, sizeof(v4_mapped) ) == 0 )
        {
            out->family = 4;
            memcpy( out->b, six.s6_addr + 12, 4 );
            return 1;
        }
        out->family = 6;
        memcpy( out->b, six.s6_addr, 16 );
        return 1;
    }
    return 0;
}

void net_addr_from_v4( uint32_t s_addr, NET_ADDR *out )
{
    memset( out, 0, sizeof(*out) );
    out->family = 4;
    memcpy( out->b, &s_addr, 4 );
}

int net_addr_equal( const NET_ADDR *a, const NET_ADDR *b )
{
    if ( a == NULL || b == NULL || a->family == 0 || a->family != b->family )
        return 0;
    return memcmp( a->b, b->b, a->family == 4 ? 4 : 16 ) == 0;
}

void net_addr_text( const NET_ADDR *a, char *buf, size_t size )
{
    char text[NET_ADDR_TEXT];

    if ( buf == NULL || size == 0 )
        return;
    buf[0] = '\0';
    if ( a == NULL || a->family == 0 )
        return;
    if ( inet_ntop( a->family == 4 ? AF_INET : AF_INET6, a->b, text, sizeof(text) ) == NULL )
        return;
    strncpy( buf, text, size - 1 );
    buf[size - 1] = '\0';
}

int net_addr_is_loopback( const NET_ADDR *a )
{
    static const unsigned char one[16] = { 0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,1 };

    if ( a == NULL )
        return 0;
    if ( a->family == 4 )
        return a->b[0] == 127;
    if ( a->family == 6 )
        return memcmp( a->b, one, 16 ) == 0;
    return 0;
}

uint32_t net_addr_guard_key( const NET_ADDR *a )
{
    uint32_t key;
    uint32_t hash = 2166136261u;        /* FNV-1a over the /64 */
    int i;

    if ( a == NULL || a->family == 0 )
        return 0;
    if ( a->family == 4 )
    {
        memcpy( &key, a->b, 4 );
        return key;
    }
    for ( i = 0; i < 8; i++ )
    {
        hash ^= a->b[i];
        hash *= 16777619u;
    }
    return htonl( 0xF0000000u | ( hash & 0x0FFFFFFFu ) );
}

int net_addr_key_is_v6( uint32_t key )
{
    return ( ntohl( key ) >> 28 ) == 0xF;
}

int net_addr_canonical( const char *text, char *buf, size_t size )
{
    NET_ADDR a;

    if ( buf == NULL || size == 0 )
        return 0;
    if ( text == NULL || !net_addr_parse( text, &a ) )
    {
        if ( text != NULL && buf != text )
        {
            strncpy( buf, text, size - 1 );
            buf[size - 1] = '\0';
        }
        return 0;
    }
    net_addr_text( &a, buf, size );
    return 1;
}

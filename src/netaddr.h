/*
 * A client's network address, kept apart from its host name (2026-11-06).
 *
 * A connection's host string was the one thing bans, the shared-address
 * notice and the staff views read, and it changes: the asynchronous
 * resolver (dnsasync.c) replaces the numeric address with a PTR name when
 * one comes back. So a numeric ban stopped matching once the name arrived,
 * two players on one address looked like two addresses when only one of
 * them had resolved, and two addresses with the same PTR name looked like
 * one. NET_ADDR is the address as it was accepted (or as the web bridge's
 * PROXY header named it), by family and bytes, and it never changes for
 * the life of the connection; the host name is display only.
 *
 * Nothing here touches game state, so this file includes no merc.h and
 * tests/test_guard_addresses.c can check it alone.
 */
#ifndef TOC_NETADDR_H
#define TOC_NETADDR_H

#include <stddef.h>
#include <stdint.h>

#define NET_ADDR_TEXT 48            /* INET6_ADDRSTRLEN (46), rounded */

typedef struct net_addr
{
    int           family;           /* 0 none, 4 IPv4, 6 IPv6 */
    unsigned char b[16];            /* network order; IPv4 uses b[0..3] */
} NET_ADDR;

/* The whole of `text` as one IPv4 or IPv6 address, nothing before or
   after it: 1 and *out, or 0. An IPv4-mapped IPv6 address (::ffff:a.b.c.d)
   is that IPv4 address. A numeric prefix ("1.2.3.4x", "1.2.3") is not an
   address. */
int      net_addr_parse     ( const char *text, NET_ADDR *out );

/* An IPv4 address from its network-order 32 bits. */
void     net_addr_from_v4   ( uint32_t s_addr, NET_ADDR *out );

/* Same family and the same bytes. Two empty addresses are not equal. */
int      net_addr_equal     ( const NET_ADDR *a, const NET_ADDR *b );

/* The canonical text: dotted IPv4, or RFC 5952 compressed IPv6; "" for none. */
void     net_addr_text      ( const NET_ADDR *a, char *buf, size_t size );

/* 127.0.0.0/8 or ::1. */
int      net_addr_is_loopback( const NET_ADDR *a );

/* The 32-bit key the login throttle and the connection guard count by,
   network order: an IPv4 address is itself; an IPv6 address is its /64 --
   what one subscriber is normally given -- folded by FNV-1a into
   240.0.0.0/4, which no real IPv4 peer can come from. Internal only: never
   shown as though it were an address. 0 for none. */
uint32_t net_addr_guard_key ( const NET_ADDR *a );

/* Whether a guard key is a folded IPv6 /64 rather than an IPv4 address. */
int      net_addr_key_is_v6 ( uint32_t key );

/* `text` rewritten as its canonical address text: 1, or 0 when it is not
   an address (and buf is left as `text`). */
int      net_addr_canonical ( const char *text, char *buf, size_t size );

#endif

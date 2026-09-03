/*
 * Telnet option handling.
 *
 * The original input path read raw bytes straight into the command buffer
 * with no IAC handling at all, so any client that negotiated options fed
 * protocol bytes into the interpreter as garbage. That is why the server
 * supported none of the modern MUD options.
 *
 * This module adds a single state machine that consumes negotiation and
 * subnegotiation from the input stream, and the option handlers built on it:
 *
 *   MSSP (70)  server status, so listing sites can index the game
 *   NAWS (31)  client window size, used to drive page length and wrap width
 *   GMCP (201) structured out-of-band data for modern clients
 *
 * Everything here is optional for the player: a plain Telnet client that
 * negotiates nothing keeps working exactly as before.
 */
#ifndef TELNET_PROTO_H
#define TELNET_PROTO_H

#include <stddef.h>

struct descriptor_data;

/* Telnet option numbers that <arpa/telnet.h> does not define. */
#ifndef TELOPT_MSSP
#define TELOPT_MSSP     70
#endif
#ifndef TELOPT_GMCP
#define TELOPT_GMCP     201
#endif
#ifndef TELOPT_COMPRESS2
#define TELOPT_COMPRESS2 86
#endif

/* MSSP in-band markers. */
#define MSSP_VAR        1
#define MSSP_VAL        2

/*
 * Consume `length` raw bytes, appending application data to `out`.
 * Returns the number of bytes written. Negotiation is answered as a side
 * effect. `out` must have room for at least `length` bytes.
 */
size_t  telnet_filter_input     ( struct descriptor_data *d,
                                  const char *raw, size_t length,
                                  char *out, size_t out_max );

/* Offer the options we support. Called once per new connection. */
void    telnet_offer_options    ( struct descriptor_data *d );

/* Send one GMCP message, ignored unless the client enabled GMCP. */
void    telnet_send_gmcp        ( struct descriptor_data *d,
                                  const char *package, const char *json );

/*
 * MCCP2 output compression. telnet_write_compressed() is the deflating half
 * of write_to_descriptor(); telnet_end_compression() must be called when a
 * descriptor closes so the zlib stream is released.
 */
bool    telnet_write_compressed ( struct descriptor_data *d,
                                  const char *txt, int length );
void    telnet_end_compression  ( struct descriptor_data *d );

#endif

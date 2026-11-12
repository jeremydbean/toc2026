# Networking Decoupling Plan

This document proposes a staged refactor to separate the networking layer from the game logic in `src/comm.c`, moving away from the monolithic `select()`-driven loop and towards a modular, poll-based architecture with explicit buffering.

## Objectives
- Isolate low-level I/O details from game mechanics so alternative frontends (web client, Discord bot) can reuse the game loop without coupling to sockets.
- Replace `select()` with `poll()` to avoid file-descriptor limits and simplify descriptor management.
- Introduce clear abstractions for network events, buffered input parsing, and queued output to reduce fragmentation and overflow risk.

## Architecture Overview
1. **NetworkOps abstraction**: Define an interface describing how the networking backend provides events and transmits data. The game loop consumes this interface rather than calling `select()` directly.
2. **Event-driven polling**: Implement a `network_poll()` helper around `poll()` (`<poll.h>` on POSIX) to produce a list of ready descriptors and their event types.
3. **Buffered input pipeline**: Separate raw byte reception from command parsing using per-descriptor circular buffers. Parsing occurs only after reads succeed.
4. **Dynamic output queues**: Replace fixed `alloc_mem` chunks with resizeable output buffers to prevent fragmentation and simplify partial writes.

## NetworkOps Interface
Add a new header (e.g., `src/network.h`) or place the definitions in `merc.h` alongside descriptor structures. The interface separates polling, read/write hooks, and teardown logic.

```c
/* merc.h */
typedef enum {
    NET_EVENT_READ,
    NET_EVENT_WRITE,
    NET_EVENT_ERROR,
    NET_EVENT_HANGUP
} NET_EVENT_TYPE;

typedef struct {
    int fd;
    NET_EVENT_TYPE type;
} NET_EVENT;

typedef struct network_ops {
    /* Populate `events` with ready descriptors; return count or -1 on error. */
    int (*poll)(NET_EVENT *events, size_t max_events, int timeout_ms);
    /* Read raw bytes from `fd` into `dest`; return bytes read or -1 on error. */
    ssize_t (*recv_bytes)(int fd, unsigned char *dest, size_t len);
    /* Write queued bytes to `fd`; return bytes written or -1 on error. */
    ssize_t (*send_bytes)(int fd, const unsigned char *src, size_t len);
    void (*close_fd)(int fd);
} NETWORK_OPS;
```

Expose a `NETWORK_OPS *net_ops` instance that the game loop receives at startup. Existing descriptor management (e.g., `DESCRIPTOR_DATA`) gains no new responsibilities; it simply reacts to events delivered by the interface.

## Polling with `poll()`
Replace the `select()` block in `game_loop_unix` with a polling helper that builds `struct pollfd` arrays from active descriptors.

```c
#include <poll.h>

#define MAX_EVENTS 256
static int poll_descriptors(NET_EVENT *out_events, size_t max_events, int timeout_ms)
{
    struct pollfd fds[MAX_EVENTS];
    nfds_t nfds = 0;

    for (DESCRIPTOR_DATA *d = descriptor_list; d != NULL && nfds < MAX_EVENTS; d = d->next) {
        fds[nfds].fd = d->descriptor;
        fds[nfds].events = POLLIN;
        if (d->outbuf.len > 0) {
            fds[nfds].events |= POLLOUT;
        }
        fds[nfds].revents = 0;
        nfds++;
    }

    int ready = poll(fds, nfds, timeout_ms);
    if (ready <= 0) {
        return ready; /* 0 on timeout, -1 on error */
    }

    size_t emitted = 0;
    for (nfds_t i = 0; i < nfds && emitted < max_events; i++) {
        if (fds[i].revents & (POLLERR | POLLHUP | POLLNVAL)) {
            out_events[emitted++] = (NET_EVENT){ fds[i].fd, NET_EVENT_ERROR };
        } else {
            if (fds[i].revents & POLLIN) {
                out_events[emitted++] = (NET_EVENT){ fds[i].fd, NET_EVENT_READ };
            }
            if (fds[i].revents & POLLOUT) {
                out_events[emitted++] = (NET_EVENT){ fds[i].fd, NET_EVENT_WRITE };
            }
        }
    }
    return (int)emitted;
}
```

The main loop becomes a consumer of `net_ops->poll` instead of constructing FD sets. Each loop iteration:
1. Calls `net_ops->poll(event_buf, MAX_EVENTS, 1000)`.
2. For `NET_EVENT_READ`, invoke a raw read helper that fills the descriptor's circular buffer.
3. For `NET_EVENT_WRITE`, flush queued output from the descriptor's dynamic buffer.
4. Handle `NET_EVENT_ERROR`/`HANGUP` by closing descriptors and notifying the game layer.

## Circular Input Buffer
Introduce a reusable circular buffer that stores raw bytes, decoupling socket reads from command parsing. This prevents `MAX_INPUT_LENGTH` overflows and allows deferred parsing.

```c
typedef struct {
    unsigned char *data;
    size_t capacity;
    size_t head; /* write position */
    size_t tail; /* read position */
} CIRCBUF;

static int circbuf_init(CIRCBUF *buf, size_t capacity)
{
    buf->data = malloc(capacity);
    if (buf->data == NULL) return -1;
    buf->capacity = capacity;
    buf->head = buf->tail = 0;
    return 0;
}

static size_t circbuf_available(const CIRCBUF *buf)
{ /* bytes currently stored */
    if (buf->head >= buf->tail) return buf->head - buf->tail;
    return buf->capacity - (buf->tail - buf->head);
}

static size_t circbuf_space(const CIRCBUF *buf)
{ return buf->capacity - circbuf_available(buf) - 1; }

static size_t circbuf_write(CIRCBUF *buf, const unsigned char *src, size_t len)
{
    size_t written = 0;
    while (written < len && circbuf_space(buf) > 0) {
        buf->data[buf->head] = src[written++];
        buf->head = (buf->head + 1) % buf->capacity;
    }
    return written;
}

static size_t circbuf_read(CIRCBUF *buf, unsigned char *dst, size_t len)
{
    size_t read = 0;
    while (read < len && circbuf_available(buf) > 0) {
        dst[read++] = buf->data[buf->tail];
        buf->tail = (buf->tail + 1) % buf->capacity;
    }
    return read;
}
```

`read_from_descriptor` becomes a thin wrapper:
- Call `net_ops->recv_bytes(d->descriptor, tmp, sizeof(tmp))`.
- Write into the descriptor's `CIRCBUF`.
- Call a new `parse_input(d)` that scans the circular buffer for newline-delimited commands, copies each into `input[]`, and passes them to the existing interpreter.

## Dynamic Output Queue
Replace the `write_to_buffer` pattern (fixed `alloc_mem` chunks) with a resizeable byte array stored on each descriptor.

```c
typedef struct {
    unsigned char *data;
    size_t len;
    size_t cap;
} OUTBUF;

static int outbuf_reserve(OUTBUF *buf, size_t needed)
{
    if (needed <= buf->cap) return 0;
    size_t new_cap = buf->cap ? buf->cap : 512;
    while (new_cap < needed) new_cap *= 2;
    unsigned char *grown = realloc(buf->data, new_cap);
    if (grown == NULL) return -1;
    buf->data = grown;
    buf->cap = new_cap;
    return 0;
}

static int outbuf_append(OUTBUF *buf, const unsigned char *src, size_t len)
{
    if (outbuf_reserve(buf, buf->len + len + 1) != 0) return -1;
    memcpy(buf->data + buf->len, src, len);
    buf->len += len;
    buf->data[buf->len] = '\0';
    return 0;
}

static int flush_output(DESCRIPTOR_DATA *d, const NETWORK_OPS *ops)
{
    ssize_t sent = ops->send_bytes(d->descriptor, d->outbuf.data, d->outbuf.len);
    if (sent < 0) return -1;
    if ((size_t)sent < d->outbuf.len) {
        memmove(d->outbuf.data, d->outbuf.data + sent, d->outbuf.len - (size_t)sent);
    }
    d->outbuf.len -= (size_t)sent;
    return 0;
}
```

Game code queues text with `outbuf_append(&d->outbuf, (const unsigned char *)buf, strlen(buf));`. The poller marks descriptors with pending output so `poll()` watches for `POLLOUT`.

## Integration Steps
1. **Introduce new buffer structs** (`CIRCBUF`, `OUTBUF`) and `NETWORK_OPS` definitions in a shared header (`merc.h` or new `network.h`).
2. **Refactor descriptor state**: add `CIRCBUF inbuf; OUTBUF outbuf;` to `DESCRIPTOR_DATA` with initialization/cleanup in `new_descriptor` and `close_socket`.
3. **Replace `select()`**: create `network_poll` implementing `NETWORK_OPS.poll` using `poll()`; update `game_loop_unix` to consume events instead of manipulating FD sets.
4. **Split read/parse**: rewrite `read_from_descriptor` to only receive bytes into `inbuf`; implement `parse_input` to extract newline-terminated commands, honoring `MAX_INPUT_LENGTH` by discarding or truncating oversized lines.
5. **Replace `write_to_buffer`**: route all output through `outbuf_append`; modify `process_output` to call `flush_output` when poll signals `NET_EVENT_WRITE`.
6. **Future frontends**: to add a WebSocket or Discord layer, supply alternative `NETWORK_OPS` implementations that translate their event models into the same `NET_EVENT` sequence consumed by the game loop.

## Notes on Compatibility
- Keep telnet negotiation logic in the parsing layer: raw reads push bytes into `inbuf`, and the parser handles telnet command filtering before producing gameplay commands.
- Preserve throttling logic (e.g., snoop prompts, descriptor timeouts) by operating on parsed commands rather than raw bytes.
- Ensure `poll()` arrays respect a reasonable cap; if more descriptors are needed, switch to a dynamically allocated `struct pollfd` list sized from the descriptor count.
- Unit-test the buffer helpers in isolation to validate wrap-around behavior and partial write handling.

# Networking Refactor Plan: Decoupling Networking from Game Logic

## Objectives
- Replace the monolithic `game_loop_unix`/`select()` flow with a pluggable network layer.
- Introduce clear separation between raw byte transport, input parsing, and game command dispatching.
- Modernize descriptor polling using `poll(2)` to avoid `FD_SETSIZE` limits.
- Add resilient buffering for inbound/outbound data to reduce fragmentation and input overflows.

## Abstractions
### NetworkOps interface
Define a small interface that owns sockets/poll state and exposes descriptor-level events to the game loop.

```c
/* merc.h */
typedef enum {
    NET_EVENT_INPUT,
    NET_EVENT_DISCONNECT,
    NET_EVENT_OOB
} net_event_type;

typedef struct {
    DESCRIPTOR_DATA *d;   /* owning descriptor */
    net_event_type type;  /* INPUT, DISCONNECT, etc. */
    size_t bytes_ready;   /* hint for reads */
} net_event;

typedef struct network_ops {
    bool  (*init)(int port, bool noresolve);
    void  (*shutdown)(void);
    size_t (*poll)(net_event *events, size_t max_events, int timeout_ms);
    bool  (*accept_new)(void); /* listener handling; may enqueue NET_EVENT_INPUT on new descriptor */
} network_ops;

/* Entry point used by the game loop */
extern const network_ops *network_layer;
```

### Polling API usage
The game loop asks the network layer for ready events and then hands them to parsing/game logic:

```c
/* comm.c */
static void game_loop(void)
{
    net_event events[MAX_CONNECTIONS];

    for (;;) {
        size_t count = network_layer->poll(events, MAX_CONNECTIONS, 50);
        for (size_t i = 0; i < count; ++i) {
            switch (events[i].type) {
            case NET_EVENT_INPUT:
                process_network_input(events[i].d);
                break;
            case NET_EVENT_DISCONNECT:
                close_descriptor(events[i].d);
                break;
            default:
                break;
            }
        }

        /* existing game tick/update logic (update_handler, etc.) */
    }
}
```

## Replacing `select()` with `poll()`
### Poll backing implementation
Implement a `poll()`-based network backend behind the interface above.

```c
/* comm.c */
#include <poll.h>

typedef struct {
    struct pollfd *fds;
    size_t count;
    size_t cap;
} poll_backend;

static poll_backend backend;

static bool poll_backend_init(int port, bool noresolve)
{
    /* existing listen_socket setup reused here */
    backend.cap = 64;
    backend.count = 0;
    backend.fds = calloc(backend.cap, sizeof(struct pollfd));
    if (!backend.fds)
        return false;

    /* add listen_socket as fds[0] */
    backend.fds[backend.count++] = (struct pollfd){ listen_socket, POLLIN, 0 };
    return true;
}

static void poll_backend_shutdown(void)
{
    free(backend.fds);
    backend.fds = NULL;
    backend.cap = backend.count = 0;
}

static void poll_backend_register(DESCRIPTOR_DATA *d)
{
    if (backend.count == backend.cap) {
        backend.cap *= 2;
        backend.fds = realloc(backend.fds, backend.cap * sizeof(struct pollfd));
    }
    backend.fds[backend.count++] = (struct pollfd){ d->descriptor, POLLIN, 0 };
}

static size_t poll_backend_poll(net_event *events, size_t max_events, int timeout_ms)
{
    int ready = poll(backend.fds, backend.count, timeout_ms);
    size_t emitted = 0;
    if (ready <= 0)
        return 0;

    for (size_t i = 0; i < backend.count && emitted < max_events; ++i) {
        struct pollfd *pfd = &backend.fds[i];
        if (pfd->revents & (POLLERR | POLLHUP | POLLNVAL)) {
            events[emitted++] = (net_event){ .d = pfd_to_descriptor(pfd), .type = NET_EVENT_DISCONNECT };
        } else if (pfd->revents & POLLIN) {
            events[emitted++] = (net_event){ .d = pfd_to_descriptor(pfd), .type = NET_EVENT_INPUT, .bytes_ready = 0 };
        }
        pfd->revents = 0;
    }
    return emitted;
}

static const network_ops poll_ops = {
    .init = poll_backend_init,
    .shutdown = poll_backend_shutdown,
    .poll = poll_backend_poll,
    .accept_new = accept_new_connection
};

const network_ops *network_layer = &poll_ops;
```

## Input buffering
### Circular buffer for raw bytes
Instead of mixing read+parse in `read_from_descriptor`, maintain a per-descriptor ring buffer. Parsing consumes complete lines/commands without risking `MAX_INPUT_LENGTH` overflow.

```c
/* merc.h */
typedef struct {
    char *data;
    size_t cap;
    size_t head; /* write position */
    size_t tail; /* read position */
} ring_buffer;

struct descriptor_data {
    int descriptor;
    ring_buffer inbuf;   /* raw bytes */
    BUFFER *outbuf;      /* dynamic output buffer */
};
```

Initialization and growth:

```c
static bool ring_init(ring_buffer *rb, size_t cap)
{
    rb->data = malloc(cap);
    if (!rb->data)
        return false;
    rb->cap = cap;
    rb->head = rb->tail = 0;
    return true;
}

static size_t ring_available(const ring_buffer *rb)
{
    return rb->cap - 1 - ((rb->head + rb->cap - rb->tail) % rb->cap);
}

static void ring_write_byte(ring_buffer *rb, unsigned char c)
{
    rb->data[rb->head] = (char)c;
    rb->head = (rb->head + 1) % rb->cap;
}
```

Read path decoupled from parsing:

```c
static bool read_from_descriptor(DESCRIPTOR_DATA *d)
{
    char tmp[512];
    ssize_t n = recv(d->descriptor, tmp, sizeof(tmp), 0);
    if (n <= 0)
        return false;

    /* grow ring buffer if nearly full */
    size_t need = (size_t)n;
    if (ring_available(&d->inbuf) < need) {
        ring_grow(&d->inbuf, d->inbuf.cap * 2 + need);
    }

    for (ssize_t i = 0; i < n; ++i) {
        ring_write_byte(&d->inbuf, (unsigned char)tmp[i]);
    }
    return true;
}

static bool process_network_input(DESCRIPTOR_DATA *d)
{
    char line[MAX_INPUT_LENGTH];
    while (ring_pop_line(&d->inbuf, line, sizeof(line))) {
        read_command_from_ring(d, line); /* existing nanny/interpret logic */
    }
    return true;
}
```

## Output queueing
### Dynamic growable buffer
Replace `write_to_buffer`'s fixed chunks with a resizeable array (can reuse existing `BUFFER` helper if preferred or implement a minimal struct):

```c
/* merc.h */
typedef struct {
    char *data;
    size_t len;
    size_t cap;
} out_buffer;
```

Append API and flush:

```c
static bool outbuf_append(out_buffer *buf, const char *src, size_t n)
{
    if (buf->len + n + 1 > buf->cap) {
        size_t new_cap = buf->cap ? buf->cap * 2 : 1024;
        while (new_cap < buf->len + n + 1)
            new_cap *= 2;
        char *tmp = realloc(buf->data, new_cap);
        if (!tmp)
            return false;
        buf->data = tmp;
        buf->cap = new_cap;
    }
    memcpy(buf->data + buf->len, src, n);
    buf->len += n;
    buf->data[buf->len] = '\0';
    return true;
}

static bool write_to_buffer(DESCRIPTOR_DATA *d, const char *txt, size_t length)
{
    if (length == 0)
        length = strlen(txt);
    return outbuf_append(&d->outbuf, txt, length);
}

static bool flush_output(DESCRIPTOR_DATA *d)
{
    ssize_t n = send(d->descriptor, d->outbuf.data, d->outbuf.len, 0);
    if (n <= 0)
        return false;
    memmove(d->outbuf.data, d->outbuf.data + n, d->outbuf.len - (size_t)n);
    d->outbuf.len -= (size_t)n;
    return true;
}
```

## Migration steps
1. Introduce the `NetworkOps` interface and `network_layer` pointer; provide the `poll()` backend as the first implementation.
2. Refactor `game_loop_unix` to delegate to `network_layer->poll` and move parsing into `process_network_input`.
3. Add per-descriptor ring buffers and replace the existing `read_from_descriptor` parsing logic with raw byte ingestion + line extraction helpers.
4. Swap `write_to_buffer` over to the dynamic `out_buffer` helper and adjust flush logic to consume partial writes correctly.
5. Keep the existing telnet negotiation/echo handling but move those behaviors to the parsing stage (after raw bytes are read from the ring buffer).
6. Add regression tests or runtime assertions for buffer growth and descriptor lifecycle to catch truncation/fragmentation regressions early.

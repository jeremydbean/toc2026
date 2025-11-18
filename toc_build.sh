#!/usr/bin/env bash
set -e

# Move to repository root (assumes script lives in toc-master folder)
cd "$(dirname "$0")"

# Patch out old gettimeofday prototype in comm.c
sed -i '/gettimeofday.*args/s/^/\//\//' src/comm.c
grep -q '#include <sys/time.h>' src/comm.c || sed -i '1i#include <sys/time.h>' src/comm.c

# Stub out handle_web_who_request in webserver.c to avoid broken HTML strings
sed -i '/handle_web_who_request/,/}/c\
void handle_web_who_request( void *wdesc, char *arg ) { \
    /* Who page not supported in this build */ \
}' src/webserver.c

# Clean and rebuild
make clean
make

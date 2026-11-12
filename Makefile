# Top-level Makefile for ToC MUD on Ubuntu 24.04+
# ?= so the environment can point this at ccache, which is what
# stops CI's deliberate `make clean` costing a full rebuild.
CC       ?= gcc
PYTHON   ?= python3

# Default flags favor stability while still surfacing helpful warnings. Use
# `make CFLAGS="..."` to override for local builds.
CFLAGS   ?= -std=c17 -O2 -DROM -Dunix
# CONVERSION_WARNINGS: silent narrowing (an int into a 16-bit field), a
# shadowed local and a signed/unsigned comparison. The whole tree is clean
# under them (strict-warnings sweep, 2026-11-12), and
# tests/test_strict_warnings.py keeps it that way -- see AGENTS.md,
# "Strict Warnings". Keep them in any WARNFLAGS you pass.
CONVERSION_WARNINGS := -Wshadow -Wsign-compare -Wconversion -Wsign-conversion
# QUALITY_WARNINGS: a cast that drops const, a function with no prototype
# in scope (a header and its definition drifting apart) and an unused
# parameter (UNUSED_PARAM says it is meant). Clean since 2026-11-12, the
# same sweep's second pass. -Warith-conversion -- an int sum stored back
# into a 16-bit field (sh_int += 1), fixed with sh_int_clamp -- is gcc's
# alone; clang does not know it, so it is added only where the compiler
# takes it.
# -Wstrict-prototypes and -Wold-style-definition (an empty or K&R
# parameter list) joined them on 2026-11-12, and gcc's -Wformat-overflow=2
# (a sprintf-family call whose output may not fit; clang reads no level)
# and -Wformat-truncation=2 (an snprintf that may cut its text short, its
# result checked or not: clean under gcc 13 and 14 since the same day).
ARITH_CONVERSION_WARNING := $(shell $(CC) -Werror -Warith-conversion -x c -fsyntax-only /dev/null >/dev/null 2>&1 && echo -Warith-conversion)
FORMAT_OVERFLOW_WARNING := $(shell $(CC) -Werror -Wformat-overflow=2 -x c -fsyntax-only /dev/null >/dev/null 2>&1 && echo -Wformat-overflow=2)
FORMAT_TRUNCATION_WARNING := $(shell $(CC) -Werror -Wformat-truncation=2 -x c -fsyntax-only /dev/null >/dev/null 2>&1 && echo -Wformat-truncation=2)
QUALITY_WARNINGS := -Wcast-qual -Wmissing-prototypes -Wunused-parameter -Wstrict-prototypes -Wold-style-definition $(ARITH_CONVERSION_WARNING) $(FORMAT_OVERFLOW_WARNING) $(FORMAT_TRUNCATION_WARNING)
WARNFLAGS?= -Wall -Wextra -Wno-missing-field-initializers $(CONVERSION_WARNINGS) $(QUALITY_WARNINGS)

# Emit a .d per object listing the headers it read. Without this a header
# edit recompiles nothing, and a constant that sizes a struct member leaves
# half the objects with one layout and half with another -- which links
# cleanly and then corrupts memory at runtime.
DEPFLAGS := -MMD -MP

UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
	LDFLAGS := -lm -lz -pthread
else
	# -rdynamic: crash.log's backtrace (playlog.c) names functions, not
	# bare addresses.
	LDFLAGS := -lcrypt -lm -lz -pthread -rdynamic
endif

SRC_DIR  := src
AREA_DIR := area
SRCS     := $(wildcard $(SRC_DIR)/*.c) $(wildcard $(AREA_DIR)/*.c)
OBJS := $(SRCS:.c=.o)
DEPS     := $(OBJS:.o=.d)
TARGET   := merc

.PHONY: all clean hyrule-area hyrule-manifest test-hyrule seasonal-areas

all: $(TARGET)

hyrule-area: data/hyrule_first_quest.json data/hyrule_room_prose.json data/hyrule_mob_prose.json scripts/build_hyrule_area.py
	$(PYTHON) scripts/build_hyrule_area.py

hyrule-manifest: scripts/build_hyrule_manifest.py
	$(PYTHON) scripts/build_hyrule_manifest.py

seasonal-areas: scripts/build_seasonal_areas.py $(wildcard data/seasonal/*.json) area/dresden.are area/limbo.are area/midennir.are
	$(PYTHON) scripts/build_seasonal_areas.py

test-hyrule: hyrule-area
	$(PYTHON) -m unittest tests.test_hyrule_progression -v

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(WARNFLAGS) -o $@ $^ $(LDFLAGS)

$(SRC_DIR)/%.o: $(SRC_DIR)/%.c
	$(CC) $(CFLAGS) $(WARNFLAGS) $(DEPFLAGS) -c $< -o $@

$(AREA_DIR)/%.o: $(AREA_DIR)/%.c
	$(CC) $(CFLAGS) $(WARNFLAGS) $(DEPFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(DEPS) $(TARGET)

-include $(DEPS)

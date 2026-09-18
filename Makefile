# Top-level Makefile for ToC MUD on Ubuntu 24.04+
CC       := gcc
PYTHON   ?= python3

# Default flags favor stability while still surfacing helpful warnings. Use
# `make CFLAGS="..."` to override for local builds.
CFLAGS   ?= -std=gnu89 -O2 -fcommon -DROM -Dunix
WARNFLAGS?= -Wall -Wextra -Wno-unused-parameter -Wno-missing-field-initializers

# Emit a .d per object listing the headers it read. Without this a header
# edit recompiles nothing, and a constant that sizes a struct member leaves
# half the objects with one layout and half with another -- which links
# cleanly and then corrupts memory at runtime.
DEPFLAGS := -MMD -MP

UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
	LDFLAGS := -lm -lz
else
	LDFLAGS := -lcrypt -lm -lz
endif

SRC_DIR  := src
AREA_DIR := area
SRCS     := $(wildcard $(SRC_DIR)/*.c) $(wildcard $(AREA_DIR)/*.c)
OBJS := $(filter-out $(SRC_DIR)/nicedb.o $(AREA_DIR)/resolve.o $(SRC_DIR)/webserver.o, $(SRCS:.c=.o))
DEPS     := $(OBJS:.o=.d)
TARGET   := merc

.PHONY: all clean hyrule-area hyrule-manifest test-hyrule

all: $(TARGET)

hyrule-area: data/hyrule_first_quest.json scripts/build_hyrule_area.py
	$(PYTHON) scripts/build_hyrule_area.py

hyrule-manifest: scripts/build_hyrule_manifest.py
	$(PYTHON) scripts/build_hyrule_manifest.py

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

# Top-level Makefile for ToC MUD on Ubuntu 24.04+
CC       := gcc

# Default flags favor stability while still surfacing helpful warnings. Use
# `make CFLAGS="..."` to override for local builds.
CFLAGS   ?= -std=gnu89 -O2 -fcommon -DROM
WARNFLAGS?= -Wall -Wextra -Wno-unused-parameter -Wno-missing-field-initializers

UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
	LDFLAGS := -lm
else
	LDFLAGS := -lcrypt -lm
endif

SRC_DIR  := src
AREA_DIR := area
SRCS     := $(wildcard $(SRC_DIR)/*.c) $(wildcard $(AREA_DIR)/*.c)
OBJS := $(filter-out $(SRC_DIR)/nicedb.o $(AREA_DIR)/resolve.o $(SRC_DIR)/webserver.o, $(SRCS:.c=.o))
TARGET   := merc

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(WARNFLAGS) -o $@ $^ $(LDFLAGS)

$(SRC_DIR)/%.o: $(SRC_DIR)/%.c
	$(CC) $(CFLAGS) $(WARNFLAGS) -c $< -o $@

$(AREA_DIR)/%.o: $(AREA_DIR)/%.c
	$(CC) $(CFLAGS) $(WARNFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET)

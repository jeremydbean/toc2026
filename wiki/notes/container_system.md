# Container System Design

This change introduces a reusable, non-intrusive container layer for global MUD data. It avoids embedding `next` pointers directly inside structs so that entity ownership can change without rewriting the structs themselves.

## Generic list implementation
- `src/list.h` / `src/list.c` provide a minimal double-linked list with push/remove/foreach helpers.
- Nodes are allocated per insertion, so core structs do not need to carry list bookkeeping fields.

## Migrating characters off intrusive lists
- `USE_CONTAINER_LISTS` toggles whether `CHAR_DATA` exposes the old `next` pointer. When enabled, characters are tracked through the global `character_list` container instead of the intrusive field.
- `register_character` and `unregister_character` in `src/container.c` add/remove characters to/from the container without requiring a `next` member on `CHAR_DATA`.
- `find_char_by_name` now iterates through the container when the toggle is enabled, giving a modern search path decoupled from legacy traversal.

To complete the migration:
1. Define `USE_CONTAINER_LISTS=1` at compile time.
2. Replace sites that push to `char_list` (e.g., in `comm.c` when players connect or `db.c` when mobs load) with `register_character`.
3. Replace `char_list` removals with `unregister_character` in extraction paths.
4. Update existing `char_list` iterations to call `list_foreach` or `find_char_by_name`.

## Feature impact
Because the list is generic and external to game structs, the same container can back new features such as:
- A "Recent Combat Log" that records participants as they enter/leave fights without modifying `CHAR_DATA`.
- A "Global Auction House" that tracks item lots in a dedicated `LIST` without embedding auction-specific pointers into `OBJ_DATA`.

Once adoption is complete, adding new global collections becomes a matter of instantiating a `LIST` and reusing the traversal helpers—no core struct surgery required.

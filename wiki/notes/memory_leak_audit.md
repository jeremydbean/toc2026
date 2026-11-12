# Memory Leak Audit Notes

## Allocation patterns in `src/db.c`
- `boot_db` allocates the shared string space once via `calloc` during startup; it never needs to be freed while the process is running because it backs all of the permanent strings loaded into the game world.
- Mobile and object instances come from free lists managed in `create_mobile` and `create_object`; when the free list is empty they allocate fresh blocks with `alloc_perm`, mirroring the original ROM/Merc allocator behavior.

## Freeing allocations when entities leave the game
- `free_char` iterates over carried items and affects before returning a character to the free list, ensuring both NPCs and PCs drop their allocated payloads when extracted from the world.
- Object extraction routes through `extract_obj`/`extract_obj_player`, which recursively remove contained objects, free all attached affects and extra descriptions, and return the base object structures to the free list to balance the earlier allocations.

## Leak testing guidance
- With Valgrind available in the runtime container image, you can start the MUD under `valgrind --leak-check=full ./merc` (or use the helper script described in the README) to confirm the extraction paths release memory when characters quit or objects are destroyed.

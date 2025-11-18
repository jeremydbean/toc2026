/*
 * Values mirrored from db.c and used across the maxload implementation.
 */
#ifndef MAXLOAD_H
#define MAXLOAD_H

/* Provide the ITEM_MAX_LOAD forward declaration and args() macro when this
 * header is included before merc.h.
 */
#ifndef args
#define args(list) list
#endif

typedef struct item_max_load ITEM_MAX_LOAD;

#define MAXLOAD_KEY_HASH 127
#define MAXLOADFILE "../area/maxload.txt"

/* Global hash table and counter defined in maxload.c. */
extern ITEM_MAX_LOAD *maxload_index_hash[MAXLOAD_KEY_HASH];
extern int top_maxload;

/* Hook used after loading the maxload file. */
int maxload_chain args((void));

#endif /* MAXLOAD_H */

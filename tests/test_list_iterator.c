/*
 * Regression test for the character/object list iterator.
 *
 * extract_char() removes the very element a FOR_EACH_CHARACTER loop is
 * standing on whenever a mobile dies inside the loop, which happens in
 * violence_update(), aggr_update(), do_mindblast(), spell_earthquake() and
 * about a dozen other places. list_remove() used to free the node
 * immediately, leaving the iterator cursor (which aliases node->next)
 * dangling. Because `next` is the last field of LIST_NODE, glibc's freed-chunk
 * metadata usually left it readable, so the bug surfaced only as rare
 * unreproducible corruption.
 *
 * Build and run this under AddressSanitizer; scripts/validate.sh does so.
 *   gcc -g -fsanitize=address,undefined -Isrc -o t tests/test_list_iterator.c src/list.c
 */
#include <stdio.h>
#include "list.h"

#define HAVE_FLUSH 1

static int failures = 0;

static void check(const char *what, int ok)
{
    printf("  %-58s %s\n", what, ok ? "PASS" : "FAIL");
    if (!ok) failures++;
}

/* Find the node holding `data` so we can remove it like remove_entry() does. */
static LIST_NODE *node_of(LIST *l, void *data)
{
    LIST_NODE *n;
    for (n = l->head; n != NULL; n = n->next)
        if (n->data == data) return n;
    return NULL;
}


/* Remove every remaining live node, then reclaim. Keeps the harness leak-free. */
static void teardown(LIST *l)
{
    while (l->head != NULL) list_remove(l, l->head);
#ifdef HAVE_FLUSH
    list_flush_pending(l);
#endif
}

int main(void)
{
    static char A='A', B='B', C='C', D='D';
    LIST l;
    LIST_ITERATOR it;
    void *seen[8];
    int n, ok;
    void *v;

    /* Case 1: remove the node the cursor is standing on (the UAF case). */
    list_init(&l);
    list_push_front(&l, &D); list_push_front(&l, &C);
    list_push_front(&l, &B); list_push_front(&l, &A);   /* A B C D */
    n = 0;
    list_iterator_start(&it, &l);
    while ((v = list_iterator_next(&it)) != NULL) {
        seen[n++] = v;
        if (v == &B) list_remove(&l, node_of(&l, &B));  /* remove CURRENT */
        if (n > 6) break;
    }
    ok = (n == 4 && seen[0]==&A && seen[1]==&B && seen[2]==&C && seen[3]==&D);
    check("remove current node: iteration completes correctly", ok);
    if (!ok) { int i; printf("    got %d:", n); for(i=0;i<n;i++) printf(" %c", *(char*)seen[i]); printf("\n"); }

    teardown(&l);

    /* Case 2: remove the node just ahead of the cursor -- must be skipped. */
    list_init(&l);
    list_push_front(&l, &D); list_push_front(&l, &C);
    list_push_front(&l, &B); list_push_front(&l, &A);
    n = 0;
    list_iterator_start(&it, &l);
    while ((v = list_iterator_next(&it)) != NULL) {
        seen[n++] = v;
        if (v == &B) list_remove(&l, node_of(&l, &C));  /* remove NEXT */
        if (n > 6) break;
    }
    ok = (n == 3 && seen[0]==&A && seen[1]==&B && seen[2]==&D);
    check("remove next node: it is skipped", ok);

    teardown(&l);

    /* Case 3: remove current AND the one ahead in the same step. */
    list_init(&l);
    list_push_front(&l, &D); list_push_front(&l, &C);
    list_push_front(&l, &B); list_push_front(&l, &A);
    n = 0;
    list_iterator_start(&it, &l);
    while ((v = list_iterator_next(&it)) != NULL) {
        seen[n++] = v;
        if (v == &B) { list_remove(&l, node_of(&l,&B)); list_remove(&l, node_of(&l,&C)); }
        if (n > 6) break;
    }
    ok = (n == 3 && seen[0]==&A && seen[1]==&B && seen[2]==&D);
    check("remove current + next: no removed element handed back", ok);
    if (!ok) { int i; printf("    got %d:", n); for(i=0;i<n;i++) printf(" %c", *(char*)seen[i]); printf("\n"); }

    teardown(&l);

    /* Case 4: removing every element while iterating (mass extinction). */
    list_init(&l);
    list_push_front(&l, &D); list_push_front(&l, &C);
    list_push_front(&l, &B); list_push_front(&l, &A);
    n = 0;
    list_iterator_start(&it, &l);
    while ((v = list_iterator_next(&it)) != NULL) {
        seen[n++] = v;
        list_remove(&l, node_of(&l, v));
        if (n > 6) break;
    }
    ok = (n == 4 && l.size == 0 && l.head == NULL);
    check("remove every node while iterating", ok);

    /* Case 5: flush reclaims memory and leaves the live list usable. */
#ifdef HAVE_FLUSH
    list_flush_pending(&l);
    check("flush leaves an empty, usable list", l.head == NULL && l.size == 0);
    list_push_front(&l, &A);
    list_iterator_start(&it, &l);
    check("list still works after a flush", list_iterator_next(&it) == &A);
    list_flush_pending(&l);
#endif

    teardown(&l);

    printf("\n%s (%d failure(s))\n", failures ? "FAILED" : "ALL PASS", failures);
    return failures != 0;
}

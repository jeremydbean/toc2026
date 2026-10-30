/*
 * Text folding with no game state behind it, so its bounds can be tested
 * on their own under AddressSanitizer (tests/test_text_fold.c). db.c's
 * help loader calls it; nothing here may include merc.h.
 */
#ifndef TEXT_FOLD_H
#define TEXT_FOLD_H

#include <stddef.h>

/* Copy `in` to `out` with every run of whitespace folded to one space and
   none kept at either end. Returns the length written, or -1 -- with out
   holding an empty string -- when the folded text and its terminator do
   not fit in `size` bytes: never a cut-short copy. *changed, if given, is
   set when the folded text differs from `in`. */
int fold_whitespace( const char *in, char *out, size_t size, int *changed );

#endif

/*
 * textbox.c -- a bordered box that fits what is in it (2026-11-24).
 *
 * SCORE was drawn with fixed printf widths inside a 62-column frame. A
 * field width is only a minimum, so any value longer than its field --
 * 30,000 hit points in a "%5d", a nine-digit casino total -- pushed its
 * row's right border out past every other row's. Each such case was
 * patched on its own (the bank and the casino totals were given rows of
 * their own). This builds the box from what is going into it instead:
 *
 *   TEXT_BOX *box = tbox_new( );
 *   tbox_rule( box );
 *   tbox_row( box );
 *   tbox_cell( box, "Hp:", "%d (%d)", ch->hit, ch->max_hit );
 *   tbox_cell( box, "Mana:", "%d (%d)", ch->mana, ch->max_mana );
 *   tbox_text( box, "You are %s.", tier );
 *   tbox_rule( box );
 *   tbox_send( box, ch );                     -- sends it and frees it
 *
 * A row of cells is label-and-value pairs, the label to the left and the
 * value to the right of its cell. Every row with the same number of cells
 * shares its column widths across the whole box, so the bars between them
 * line up from top to bottom. Each column is as wide as its widest entry,
 * and the box is as wide as its widest row (never narrower than SCORE's
 * old 62 columns); narrower rows are spread to fill it. A text row is
 * free text, wrapped at spaces once it passes TBOX_WRAP_INNER.
 *
 * Widths are what shows: colour tokens ("{0C") and raw "\x02" markers with
 * their slot byte count for nothing (color_strlen), so a coloured value
 * lines up with a plain one, and a wrap neither comes early for colour nor
 * cuts a marker from its slot (tests/test_textbox.c).
 */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "merc.h"

#define TBOX_MAX_ROWS    64
#define TBOX_MAX_CELLS   4
#define TBOX_LABEL       48
#define TBOX_VALUE       192
#define TBOX_TEXT        1024
#define TBOX_MIN_INNER   58     /* SCORE as it always was: 62 in all */
#define TBOX_WRAP_INNER  74     /* free text wraps here: 78 in all */

enum tbox_kind { TBOX_RULE, TBOX_CELLS, TBOX_TEXTROW };

struct tbox_row
{
    enum tbox_kind kind;
    size_t ncells;
    char label[TBOX_MAX_CELLS][TBOX_LABEL];
    char value[TBOX_MAX_CELLS][TBOX_VALUE];
    char text[TBOX_TEXT];
};

struct text_box
{
    size_t nrows;
    bool full;                          /* a row was dropped: said once */
    struct tbox_row rows[TBOX_MAX_ROWS];
};

TEXT_BOX *tbox_new( void )
{
    TEXT_BOX *box = calloc( 1, sizeof( *box ) );

    if ( box == NULL )
        bug( "tbox_new: out of memory", 0 );
    return box;
}

void tbox_free( TEXT_BOX *box )
{
    free( box );
}

static struct tbox_row *tbox_add( TEXT_BOX *box, enum tbox_kind kind )
{
    struct tbox_row *row;

    if ( box == NULL )
        return NULL;
    if ( box->nrows >= TBOX_MAX_ROWS )
    {
        if ( !box->full )
            bug( "tbox_add: more than %d rows; the rest are left out",
                 TBOX_MAX_ROWS );
        box->full = true;
        return NULL;
    }
    row = &box->rows[box->nrows++];
    memset( row, 0, sizeof( *row ) );
    row->kind = kind;
    return row;
}

void tbox_rule( TEXT_BOX *box )
{
    /* Two rules running together draw as one. */
    if ( box != NULL && box->nrows > 0
      && box->rows[box->nrows - 1].kind == TBOX_RULE )
        return;
    tbox_add( box, TBOX_RULE );
}

void tbox_row( TEXT_BOX *box )
{
    tbox_add( box, TBOX_CELLS );
}

void tbox_cell( TEXT_BOX *box, const char *label, const char *fmt, ... )
{
    struct tbox_row *row;
    va_list args;

    if ( box == NULL )
        return;
    row = box->nrows > 0 ? &box->rows[box->nrows - 1] : NULL;
    if ( row == NULL || row->kind != TBOX_CELLS || row->ncells >= TBOX_MAX_CELLS )
        row = tbox_add( box, TBOX_CELLS );
    if ( row == NULL )
        return;
    toc_strlcpy( row->label[row->ncells], label != NULL ? label : "", TBOX_LABEL );
    va_start( args, fmt );
    vsnprintf( row->value[row->ncells], TBOX_VALUE, fmt, args );
    va_end( args );
    color_truncate( row->value[row->ncells], TBOX_VALUE - 1 );
    row->ncells++;
}

void tbox_text( TEXT_BOX *box, const char *fmt, ... )
{
    struct tbox_row *row = tbox_add( box, TBOX_TEXTROW );
    va_list args;

    if ( row == NULL )
        return;
    va_start( args, fmt );
    vsnprintf( row->text, sizeof( row->text ), fmt, args );
    va_end( args );
    color_truncate( row->text, sizeof( row->text ) - 1 );
}

static void tbox_pad( DString *out, size_t n )
{
    while ( n-- > 0 )
        dstring_append_char( out, ' ' );
}

/* The bytes of str that show at most `width` columns, never splitting a
   colour token: how far to cut. */
static size_t tbox_bytes_for( const char *str, size_t width )
{
    size_t i = 0, shown = 0;
    unsigned char slot;

    while ( str[i] != '\0' )
    {
        /* A raw marker and its slot byte, as color_strlen skips them: never
           counted, never cut apart (review, 2026-11-24). */
        if ( str[i] == '\x02' )
        {
            i += str[i + 1] != '\0' ? 2 : 1;
            continue;
        }
        if ( color_token_prefix( str[i] ) && color_parse_slot( str + i + 1, &slot ) )
        {
            i += 3;
            continue;
        }
        if ( shown == width )
            break;
        shown++;
        i++;
    }
    return i;
}

/* One line of a text row: "| " text, padded, " |". */
static void tbox_text_line( DString *out, const char *text, size_t len,
                            size_t inner )
{
    char line[TBOX_TEXT];
    size_t shown;

    if ( len >= sizeof( line ) )
        len = sizeof( line ) - 1;
    memcpy( line, text, len );
    line[len] = '\0';
    shown = color_strlen( line );
    dstring_append_cstr( out, "| " );
    dstring_append_cstr( out, line );
    tbox_pad( out, shown < inner ? inner - shown : 0 );
    dstring_append_cstr( out, " |\n\r" );
}

/* A text row, wrapped at spaces to `inner` columns; a word longer than a
   whole line is cut. */
static void tbox_render_text( DString *out, const char *text, size_t inner )
{
    while ( *text != '\0' )
    {
        size_t fits = tbox_bytes_for( text, inner );
        size_t cut = fits;

        if ( text[fits] != '\0' )
        {
            /* Back up to the last space that fits, if there is one. */
            size_t i;

            for ( i = fits; i > 0 && text[i] != ' '; i-- )
                ;
            if ( i > 0 )
                cut = i;
        }
        tbox_text_line( out, text, cut, inner );
        text += cut;
        while ( *text == ' ' )
            text++;
    }
}

void tbox_render( const TEXT_BOX *box, DString *out )
{
    /* Per number of cells: each column's label and value widths. */
    size_t label_w[TBOX_MAX_CELLS + 1][TBOX_MAX_CELLS];
    size_t value_w[TBOX_MAX_CELLS + 1][TBOX_MAX_CELLS];
    size_t natural[TBOX_MAX_CELLS + 1];
    size_t inner = TBOX_MIN_INNER;
    size_t r, n, c;

    if ( box == NULL || out == NULL )
        return;
    memset( label_w, 0, sizeof( label_w ) );
    memset( value_w, 0, sizeof( value_w ) );
    memset( natural, 0, sizeof( natural ) );

    for ( r = 0; r < box->nrows; r++ )
    {
        const struct tbox_row *row = &box->rows[r];

        if ( row->kind == TBOX_CELLS )
            for ( c = 0; c < row->ncells; c++ )
            {
                label_w[row->ncells][c] = UMAX( label_w[row->ncells][c],
                                                color_strlen( row->label[c] ) );
                value_w[row->ncells][c] = UMAX( value_w[row->ncells][c],
                                                color_strlen( row->value[c] ) );
            }
        else if ( row->kind == TBOX_TEXTROW )
            inner = UMAX( inner, UMIN( color_strlen( row->text ),
                                       (size_t) TBOX_WRAP_INNER ) );
    }

    /* A cell is its label, a space if it has both, and its value; the
       cells of a row are joined by " | ". */
    for ( n = 1; n <= TBOX_MAX_CELLS; n++ )
    {
        size_t width = 3 * ( n - 1 );

        for ( c = 0; c < n; c++ )
            width += label_w[n][c] + value_w[n][c]
                   + ( label_w[n][c] > 0 && value_w[n][c] > 0 ? 1 : 0 );
        natural[n] = width;
        inner = UMAX( inner, width );
    }

    /* Rows narrower than the box take the difference in their values,
       spread over the columns, the rightmost taking any remainder. */
    for ( n = 1; n <= TBOX_MAX_CELLS; n++ )
    {
        size_t extra = inner - natural[n];

        for ( c = 0; c < n; c++ )
            value_w[n][c] += extra / n + ( c >= n - extra % n ? 1 : 0 );
    }

    for ( r = 0; r < box->nrows; r++ )
    {
        const struct tbox_row *row = &box->rows[r];

        switch ( row->kind )
        {
        case TBOX_RULE:
            for ( c = 0; c < inner + 4; c++ )
                dstring_append_char( out, '-' );
            dstring_append_cstr( out, "\n\r" );
            break;

        case TBOX_TEXTROW:
            if ( row->text[0] == '\0' )
                tbox_text_line( out, "", 0, inner );
            else
                tbox_render_text( out, row->text, inner );
            break;

        case TBOX_CELLS:
            n = row->ncells;
            if ( n == 0 )
                break;
            dstring_append_cstr( out, "| " );
            for ( c = 0; c < n; c++ )
            {
                size_t lw = color_strlen( row->label[c] );
                size_t vw = color_strlen( row->value[c] );

                if ( c > 0 )
                    dstring_append_cstr( out, " | " );
                dstring_append_cstr( out, row->label[c] );
                tbox_pad( out, label_w[n][c] - lw );
                if ( label_w[n][c] > 0 && value_w[n][c] > 0 )
                    dstring_append_char( out, ' ' );
                tbox_pad( out, value_w[n][c] - vw );
                dstring_append_cstr( out, row->value[c] );
            }
            dstring_append_cstr( out, " |\n\r" );
            break;
        }
    }
}

void tbox_send( TEXT_BOX *box, CHAR_DATA *ch )
{
    DString out;

    if ( box == NULL )
        return;
    dstring_init( &out );
    tbox_render( box, &out );
    send_to_char_dstring( &out, ch );
    dstring_free( &out );
    tbox_free( box );
}

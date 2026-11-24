/*
 * tests/test_textbox.c -- src/textbox.c on its own (2026-11-24 review).
 *
 * A text row is wrapped by visible width. Colour comes in two forms: a
 * "{XY" token and a raw "\x02" marker followed by its slot byte (room
 * names, socials, announcements). color_strlen() skips both; the wrap
 * used to skip only the token, so a marker cost two columns of every line
 * it was on and a cut could fall between "\x02" and its slot byte. Every
 * line drawn must be exactly as wide as the box once colour is skipped,
 * and no "\x02" may be left without its slot byte.
 */
#include <stdio.h>
#include <string.h>
#include "merc.h"

/* What textbox.c and color.c need from the rest of the game. */
void bug( const char *str, int param ) { (void) str; (void) param; }
bool str_cmp( const char *a, const char *b )
{
    for ( ; *a || *b; a++, b++ )
        if ( LOWER( *a ) != LOWER( *b ) )
            return true;
    return false;
}
bool str_prefix( const char *a, const char *b )
{
    for ( ; *a; a++, b++ )
        if ( LOWER( *a ) != LOWER( *b ) )
            return true;
    return false;
}
void send_to_char_dstring( const DString *s, CHAR_DATA *ch ) { (void) s; (void) ch; }

static int failures;

static void fail( const char *what, const char *line )
{
    size_t i;

    failures++;
    printf( "FAIL: %s: ", what );
    for ( i = 0; line[i] != '\0'; i++ )
        printf( (unsigned char) line[i] < 32 ? "\\x%02x" : "%c", (unsigned char) line[i] );
    printf( "\n" );
}

/* Every line of the box as wide as the first; no marker cut in two; and
   every wrapped line but the last filled to within `slack` columns of the
   box, so a wrap is not made early by colour that takes no room. */
static void check_box( const char *name, const char *text, size_t slack )
{
    TEXT_BOX *box = tbox_new( );
    DString out;
    char copy[8192];
    char *line, *next;
    size_t width = 0;
    int lines = 0;
    size_t short_line = 0;

    tbox_rule( box );
    tbox_text( box, "%s", text );
    tbox_rule( box );
    dstring_init( &out );
    tbox_render( box, &out );
    tbox_free( box );
    snprintf( copy, sizeof( copy ), "%s", dstring_cstr( &out ) );
    dstring_free( &out );

    for ( line = copy; line != NULL && *line != '\0'; line = next )
    {
        size_t shown, i;

        next = strstr( line, "\n\r" );
        if ( next != NULL )
        {
            *next = '\0';
            next += 2;
        }
        shown = color_strlen( line );
        if ( lines++ == 0 )
            width = shown;
        else if ( shown != width )
            fail( name, line );
        if ( line[0] == '|' )
        {
            /* The text drawn, without the padding and the border. */
            char body[8192];
            size_t len;

            snprintf( body, sizeof( body ), "%s", line + 2 );
            len = strlen( body );
            if ( len >= 2 )
                body[len - 2] = '\0';
            len = strlen( body );
            while ( len > 0 && body[len - 1] == ' ' )
                body[--len] = '\0';
            if ( next != NULL && strncmp( next, "---", 3 ) != 0
                 && color_strlen( body ) + 4 + slack < width )
                short_line = color_strlen( body );
        }
        for ( i = 0; line[i] != '\0'; i++ )
            if ( line[i] == '\x02' && ( line[i + 1] == '\0' || line[i + 1] == ' '
                                        || line[i + 1] == '|' ) )
                fail( "a marker cut from its slot", line );
    }
    if ( lines < 4 )
        fail( "the text was not wrapped", name );
    if ( short_line != 0 )
    {
        char what[256];

        snprintf( what, sizeof( what ), "%s: a line wrapped early, at %lu of %lu columns",
                  name, (unsigned long) short_line, (unsigned long) ( width - 4 ) );
        fail( what, "" );
    }
}

int main( void )
{
    char text[2048];
    size_t i;

    /* Markers around words: the wrap must not count them. */
    text[0] = '\0';
    for ( i = 0; i < 12; i++ )
        strcat( text, "\x02\x10" "coloured\x02\x01 words " );
    check_box( "markers between words", text, 15 );

    /* One long word with a marker every few letters: nowhere to break at a
       space, so the cut is by width alone and must step over the marker. */
    text[0] = '\0';
    for ( i = 0; i < 60; i++ )
        strcat( text, "abc\x02\x10" );
    check_box( "markers in an unbroken run", text, 0 );

    /* The same with tokens, which were always right. */
    text[0] = '\0';
    for ( i = 0; i < 12; i++ )
        strcat( text, "{11coloured{00 words " );
    check_box( "tokens between words", text, 15 );

    if ( failures == 0 )
        printf( "ok\n" );
    return failures != 0;
}

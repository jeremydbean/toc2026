#include "merc.h"

#define COLOR_OPTION_COUNT ((int)(sizeof(col_disp_table) / sizeof(col_disp_table[0])))
#define COLOR_TABLE_SLOTS  (int)(sizeof(((PC_DATA *)0)->col_table) / sizeof(sh_int))

enum color_option_index
{
    COLOR_GREY = 0,
    COLOR_BLUE,
    COLOR_GREEN,
    COLOR_CYAN,
    COLOR_RED,
    COLOR_MAGENTA,
    COLOR_BROWN,
    COLOR_YELLOW,
    COLOR_BRIGHT_GREY,
    COLOR_BRIGHT_BLUE,
    COLOR_BRIGHT_GREEN,
    COLOR_BRIGHT_CYAN,
    COLOR_BRIGHT_RED,
    COLOR_BRIGHT_MAGENTA,
    COLOR_WHITE,
    COLOR_PLAIN                         /* the 256-colour names follow */
};

const struct col_disp_table_type col_disp_table[] =
{
    { "grey",            "\x1b[90m"   },   /* high-intensity black = dark grey */
    { "blue",            "\x1b[34m"   },
    { "green",           "\x1b[32m"   },
    { "cyan",            "\x1b[36m"   },
    { "red",             "\x1b[31m"   },
    { "magenta",         "\x1b[35m"   },
    { "brown",           "\x1b[33m"   },
    { "yellow",          "\x1b[93m"   },   /* high-intensity yellow */
    { "bright_grey",     "\x1b[37m"   },   /* normal white = light grey */
    { "bright_blue",     "\x1b[94m"   },   /* high-intensity blue */
    { "bright_green",    "\x1b[92m"   },   /* high-intensity green */
    { "bright_cyan",     "\x1b[96m"   },   /* high-intensity cyan */
    { "bright_red",      "\x1b[91m"   },   /* high-intensity red */
    { "bright_magenta",  "\x1b[95m"   },   /* high-intensity magenta */
    { "white",           "\x1b[97m"   },   /* high-intensity white */
    { "plain",           "" },
    /* The xterm 256-colour palette, added 2026-10-23. Appended after
       "plain" and never reordered: a player's choice is saved as its
       index here (ColTable), so inserting above would change everyone's
       colours. A client without 256 colours shows them in its default. */
    { "orange",         "\x1b[38;5;208m" },
    { "amber",          "\x1b[38;5;214m" },
    { "gold",           "\x1b[38;5;220m" },
    { "lime",           "\x1b[38;5;118m" },
    { "mint",           "\x1b[38;5;121m" },
    { "teal",           "\x1b[38;5;30m" },
    { "turquoise",      "\x1b[38;5;44m" },
    { "sky",            "\x1b[38;5;117m" },
    { "navy",           "\x1b[38;5;18m" },
    { "indigo",         "\x1b[38;5;54m" },
    { "purple",         "\x1b[38;5;93m" },
    { "violet",         "\x1b[38;5;135m" },
    { "lavender",       "\x1b[38;5;183m" },
    { "pink",           "\x1b[38;5;218m" },
    { "rose",           "\x1b[38;5;204m" },
    { "crimson",        "\x1b[38;5;160m" },
    { "maroon",         "\x1b[38;5;88m" },
    { "coral",          "\x1b[38;5;209m" },
    { "salmon",         "\x1b[38;5;210m" },
    { "peach",          "\x1b[38;5;223m" },
    { "tan",            "\x1b[38;5;180m" },
    { "olive",          "\x1b[38;5;100m" },
    { "silver",         "\x1b[38;5;250m" },
    { "charcoal",       "\x1b[38;5;240m" }
};

const struct col_table_type col_table[] =
{
    { "regular",    COL_REGULAR,   COLOR_BRIGHT_GREY, false },
    { "gossips",    COL_GOSSIP,    COLOR_MAGENTA,     false },
    { "shouts",     COL_SHOUTS,    COLOR_WHITE,       false },
    { "question",   COL_QUESTION,  COLOR_BRIGHT_CYAN, false },
    { "castle",     COL_CASTLE,    COLOR_CYAN,        false },
    { "tell",       COL_TELL,      COLOR_GREEN,       false },
    { "says",       COL_SAYS,      COLOR_RED,         false },
    { "socials",    COL_SOCIALS,   COLOR_MAGENTA,     false },
    { "highlight",  COL_HIGHLIGHT, COLOR_WHITE,       false },
    { "damage",     COL_DAMAGE,    COLOR_RED,         false },
    { "defense",    COL_DEFENSE,   COLOR_GREY,        false },
    { "disarm",     COL_DISARM,    COLOR_BRIGHT_RED,  false },
    { "hero",       COL_HERO,      COLOR_YELLOW,      false },
    { "wizinfo",    COL_WIZINFO,   COLOR_BRIGHT_CYAN, true  },
    { "immtalk",    COL_IMMTALK,   COLOR_BROWN,       true  },
    { "room_name",  COL_ROOM_NAME, COLOR_BROWN,       false },
    { NULL,          0,             COLOR_PLAIN,       false }
};

static const char *const color_reset_sequence = "\x1b[0m";

static int color_hex_value( char ch );
bool color_parse_slot( const char *str, unsigned char *slot_out );

static bool is_valid_color_slot( int slot )
{
    return slot >= 0 && slot < COLOR_TABLE_SLOTS;
}

int color_display_count( void )
{
    return COLOR_OPTION_COUNT;
}

const char *color_reset_code( void )
{
    return color_reset_sequence;
}

const struct col_table_type *color_category_lookup( const char *name )
{
    int idx;

    if ( name == NULL || name[0] == '\0' )
    {
        return NULL;
    }

    for ( idx = 0; col_table[idx].name != NULL; ++idx )
    {
        if ( !str_prefix( name, col_table[idx].name ) )
        {
            return &col_table[idx];
        }
    }

    return NULL;
}

int color_display_lookup( const char *name )
{
    int idx;

    if ( name == NULL || name[0] == '\0' )
    {
        return -1;
    }

    for ( idx = 0; idx < COLOR_OPTION_COUNT; ++idx )
    {
        if ( !str_prefix( name, col_disp_table[idx].type ) )
        {
            return idx;
        }
    }

    return -1;
}

void color_update_defaults( CHAR_DATA *ch, bool overwrite )
{
    int idx;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
    {
        return;
    }

    for ( idx = 0; col_table[idx].name != NULL; ++idx )
    {
        int slot = col_table[idx].num;

        if ( !is_valid_color_slot( slot ) )
        {
            continue;
        }

        if ( overwrite
          || ch->pcdata->col_table[slot] < 0
          || ch->pcdata->col_table[slot] >= COLOR_OPTION_COUNT )
        {
            ch->pcdata->col_table[slot] = (sh_int)(col_table[idx].def);
        }
    }
}

const char *color_code( const CHAR_DATA *ch, int slot )
{
    int entry;

    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
    {
        return "";
    }

    if ( !ch->pcdata->color )
    {
        return "";
    }

    if ( ch->desc != NULL && !ch->desc->color )
    {
        return "";
    }

    if ( !is_valid_color_slot( slot ) )
    {
        slot = COL_REGULAR;
    }

    entry = ch->pcdata->col_table[slot];
    if ( entry < 0 || entry >= COLOR_OPTION_COUNT )
    {
        return "";
    }

    return col_disp_table[entry].ansi_str;
}

/*
 * The name of the colour this character has chosen for a category --
 * "bright_magenta" -- or NULL when they would see it uncoloured. The same
 * answer color_code() gives as an escape sequence, for a client that
 * draws the line somewhere else and has to match the main window.
 */
const char *color_name( const CHAR_DATA *ch, int slot )
{
    int entry;

    if ( !color_is_enabled( ch ) )
        return NULL;
    if ( !is_valid_color_slot( slot ) )
        slot = COL_REGULAR;

    entry = ch->pcdata->col_table[slot];
    if ( entry < 0 || entry >= COLOR_OPTION_COUNT )
        return NULL;
    if ( col_disp_table[entry].ansi_str == NULL
    ||   col_disp_table[entry].ansi_str[0] == '\0' )
        return NULL;                    /* "plain" */
    return col_disp_table[entry].type;
}


bool color_is_enabled( const CHAR_DATA *ch )
{
    if ( ch == NULL || IS_NPC(ch) || ch->pcdata == NULL )
    {
        return false;
    }

    if ( !ch->pcdata->color )
    {
        return false;
    }

    if ( ch->desc != NULL && !ch->desc->color )
    {
        return false;
    }

    return true;
}

static int color_hex_value( char ch )
{
    if ( ch >= '0' && ch <= '9' )
    {
        return ch - '0';
    }

    if ( ch >= 'a' && ch <= 'f' )
    {
        return 10 + ( ch - 'a' );
    }

    if ( ch >= 'A' && ch <= 'F' )
    {
        return 10 + ( ch - 'A' );
    }

    return -1;
}

bool color_token_prefix( char ch )
{
    /* Only '{' is the canonical color prefix.  '&' and '$' were legacy
     * alternatives: '&' was never used in code; '$' conflicts with the
     * act() substitution codes ($n, $e, etc.) and could cause those
     * tokens to be misidentified as color markers. */
    return ( ch == '{' );
}

bool color_parse_slot( const char *str, unsigned char *slot_out )
{
    int high;
    int low;

    if ( str == NULL
      || *str == '\0'
      || *( str + 1 ) == '\0'
      || slot_out == NULL )
    {
        return false;
    }

    high = color_hex_value( *str );
    low  = color_hex_value( *( str + 1 ) );

    if ( high < 0 || low < 0 )
    {
        return false;
    }

    *slot_out = (unsigned char)(( high << 4 ) | low );
    return true;
}

/*
 * Cut str to at most max bytes without leaving half a colour token: a
 * TITLE cut at 45 through "{0B" left "{0", which prints as itself.
 */
void color_truncate( char *str, size_t max )
{
    size_t len;

    if ( str == NULL || strlen( str ) <= max )
        return;
    str[max] = '\0';
    len = max;
    if ( len >= 1 && color_token_prefix( str[len - 1] ) )
        str[len - 1] = '\0';
    else if ( len >= 2 && color_token_prefix( str[len - 2] )
           && color_hex_value( str[len - 1] ) >= 0 )
        str[len - 2] = '\0';
}

/*
 * End str with a colour reset when it carries any colour token and does
 * not already end with one, so a coloured title does not tint " is here."
 * and every WHO line after it. Does nothing without room for the reset.
 */
void color_close( char *str, size_t size )
{
    const char *p;
    size_t len;
    unsigned char slot;
    bool coloured = false;

    if ( str == NULL )
        return;
    for ( p = str; *p != '\0'; p++ )
        if ( color_token_prefix( *p ) && color_parse_slot( p + 1, &slot ) )
            coloured = true;
    len = strlen( str );
    if ( !coloured
      || ( len >= 3 && !strcmp( str + len - 3, "{00" ) )
      || len + 4 > size )
        return;
    toc_strlcat( str, "{00", size );
}

void color_append_marker( DString *buf, const CHAR_DATA *recipient, bool allow_color, unsigned char slot )
{
    const char *sequence;

    if ( buf == NULL || !allow_color )
    {
        return;
    }

    if ( slot == 0 )
    {
        sequence = color_reset_code();
    }
    else
    {
        sequence = color_code( recipient, slot );
    }

    /* A slot set to "plain" has no sequence of its own, but it still has
       to end the colour before it: fight and room-name lines close with
       the regular slot, and with regular set to plain their colour ran
       on into everything after. */
    if ( sequence == NULL || *sequence == '\0' )
        sequence = color_reset_code();
    if ( sequence != NULL && *sequence != '\0' )
    {
        dstring_append_cstr( buf, sequence );
    }
}

void color_convert( const char *text, const CHAR_DATA *recipient, bool allow_color, DString *out )
{
    const char *str;
    unsigned char color_slot;

    if ( text == NULL || out == NULL )
    {
        return;
    }

    for ( str = text; *str != '\0'; )
    {
        if ( *str == '\x02' )
        {
            ++str;
            if ( *str == '\0' )
            {
                break;
            }

            color_append_marker( out, recipient, allow_color, (unsigned char)*str );
            ++str;
            continue;
        }

        if ( color_token_prefix( *str )
          && color_parse_slot( str + 1, &color_slot ) )
        {
            color_append_marker( out, recipient, allow_color, color_slot );
            str += 3;
            continue;
        }

        dstring_append_char( out, *str );
        ++str;
    }
}

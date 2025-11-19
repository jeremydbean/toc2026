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
    COLOR_PLAIN
};

const struct col_disp_table_type col_disp_table[] =
{
    { "grey",            "\x1b[1;30m" },
    { "blue",            "\x1b[0;34m" },
    { "green",           "\x1b[0;32m" },
    { "cyan",            "\x1b[0;36m" },
    { "red",             "\x1b[0;31m" },
    { "magenta",         "\x1b[0;35m" },
    { "brown",           "\x1b[0;33m" },
    { "yellow",          "\x1b[1;33m" },
    { "bright_grey",     "\x1b[0;37m" },
    { "bright_blue",     "\x1b[1;34m" },
    { "bright_green",    "\x1b[1;32m" },
    { "bright_cyan",     "\x1b[1;36m" },
    { "bright_red",      "\x1b[1;31m" },
    { "bright_magenta",  "\x1b[1;35m" },
    { "white",           "\x1b[1;37m" },
    { "plain",           "" }
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
            ch->pcdata->col_table[slot] = col_table[idx].def;
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
    return ( ch == '{' || ch == '&' || ch == '$' );
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

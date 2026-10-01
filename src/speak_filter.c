/*
 * Speech filters: swedish (the SWEDISH command, PLR_SWEDISH) and drunk
 * (COND_DRUNK). Both lived in comm.c until the 2026 modernisation moved
 * swedish_speak into an uncompiled src/swedish.txt and dropped
 * speak_filter and drunk_speak entirely, leaving do_say to emit raw --
 * so SWEDISH set a flag nothing read and drunk speech stopped slurring.
 * This restores all three as compiled code, with bounded appends in
 * place of the originals' strcat/strcpy.
 */
#include <string.h>
#include <ctype.h>
#include "merc.h"

/* Append src into dst at *ppos, NUL-terminated and bounded. */
static void sf_append( char *dst, size_t dstsize, size_t *ppos, const char *src )
{
    while ( *src != '\0' && *ppos + 1 < dstsize )
        dst[(*ppos)++] = *src++;
    dst[*ppos] = '\0';
}


/*
 * The Swedish Chef. Ported from the historical comm.c syllable table;
 * the branch order is load bearing (the longer prefixes have to be
 * tested before the single letters they start with).
 */
static char *swedish_speak( const char *str )
{
    static char buf[MAX_STRING_LENGTH];
    size_t pos = 0;
    int iSyl;
    int length;
    bool i_seen = FALSE;
    bool in_word = FALSE;
    const char *pName;

    struct syl_type { char *old; char *new; };
    static const struct syl_type syl_table[] =
    {
        { "an", "oon" }, { "au", "oo" }, { "ew", "oo" }, { "ow", "oo" },
        { "the", "zee" }, { "th", "t" }, { "tion", "shun" },
        { "a", "e" }, { "b", "b" }, { "c", "c" }, { "d", "d" },
        { "e", "e" }, { "f", "ff" }, { "g", "g" }, { "h", "h" },
        { "j", "j" }, { "k", "k" }, { "l", "l" }, { "m", "m" },
        { "n", "n" }, { "o", "u" }, { "p", "p" }, { "q", "q" },
        { "r", "r" }, { "s", "s" }, { "t", "t" }, { "u", "oo" },
        { "v", "f" }, { "w", "v" }, { "x", "x" }, { "y", "y" },
        { "z", "z" }, { "", "" }
    };

    buf[0] = '\0';
    for ( pName = str; *pName != '\0'; pName += length )
    {
        length = 1;
        if ( !str_prefix( " ", pName ) )
        {
            sf_append( buf, sizeof(buf), &pos, " " );
            in_word = FALSE;
            i_seen = FALSE;
        }
        else if ( !str_prefix( "e ", pName ) )
            sf_append( buf, sizeof(buf), &pos, "e-a" );
        else if ( !str_prefix( "en ", pName ) )
        {
            sf_append( buf, sizeof(buf), &pos, "ee" );
            length = 2;
        }
        else if ( !str_prefix( "o", pName ) && in_word == FALSE )
        {
            sf_append( buf, sizeof(buf), &pos, "oo" );
            in_word = TRUE;
        }
        else if ( !str_prefix( "u", pName ) && in_word == FALSE )
        {
            sf_append( buf, sizeof(buf), &pos, "u" );
            in_word = TRUE;
        }
        else if ( !str_prefix( "e", pName ) && in_word == FALSE )
        {
            sf_append( buf, sizeof(buf), &pos, "i" );
            in_word = TRUE;
        }
        else if ( !str_prefix( "ir", pName ) && in_word == FALSE )
        {
            sf_append( buf, sizeof(buf), &pos, "ur" );
            in_word = TRUE;
            length = 2;
        }
        else if ( !str_prefix( "i", pName ) )
        {
            if ( i_seen == FALSE && in_word == TRUE )
            {
                sf_append( buf, sizeof(buf), &pos, "ee" );
                i_seen = TRUE;
            }
            else
                sf_append( buf, sizeof(buf), &pos, "i" );
            in_word = TRUE;
        }
        else
        {
            for ( iSyl = 0;
                  ( length = (int) strlen( syl_table[iSyl].old ) ) != 0;
                  iSyl++ )
            {
                if ( !str_prefix( syl_table[iSyl].old, pName ) )
                {
                    sf_append( buf, sizeof(buf), &pos, syl_table[iSyl].new );
                    in_word = TRUE;
                    break;
                }
            }
            if ( length == 0 )
            {
                char one[2];
                one[0] = *pName;
                one[1] = '\0';
                sf_append( buf, sizeof(buf), &pos, one );
                length = 1;
            }
        }
    }

    return buf;
}


/*
 * Drunk slurring: double some consonants, randomly capitalise, hiccup.
 * Ported from the historical comm.c; written with a bounded cursor
 * (each input letter yields at most two, so the room left is checked
 * before each write).
 */
char *drunk_speak( const char *str )
{
    static char buf[MAX_STRING_LENGTH];
    size_t pos = 0;
    const char *cp1;
    int numb;

    for ( cp1 = str; *cp1 != '\0' && pos + 2 < sizeof(buf); cp1++ )
    {
        buf[pos++] = *cp1;
        switch ( UPPER( *cp1 ) )
        {
        case 'S': buf[pos++] = 's'; break;
        case 'O': buf[pos++] = 'h'; break;
        case 'T': buf[pos++] = 't'; break;
        case 'I': buf[pos++] = 'i'; break;
        default: break;
        }
    }
    buf[pos] = '\0';

    for ( pos = 0; buf[pos] != '\0'; pos++ )
    {
        numb = number_range( 1, 4 );
        if ( numb == 1 )
            buf[pos] = UPPER( buf[pos] );
    }

    return buf;
}


/*
 * The one place say, tell and the channels pass their text through, so
 * a filter added here reaches all of them. Mobiles are never filtered;
 * PLR_SWEDISH shares the act bitfield with the ACT_* flags, so the
 * !IS_NPC guard is what keeps a mobile's own bit from being read as it.
 */
char *speak_filter( CHAR_DATA *ch, const char *str )
{
    static char filterbuf[MAX_STRING_LENGTH];

    toc_strlcpy( filterbuf, str, sizeof(filterbuf) );

    if ( IS_NPC( ch ) )
        return filterbuf;

    if ( IS_SET( ch->act, PLR_SWEDISH ) )
        toc_strlcpy( filterbuf, swedish_speak( filterbuf ), sizeof(filterbuf) );

    if ( ch->pcdata != NULL && ch->pcdata->condition[COND_DRUNK] > 10 )
        toc_strlcpy( filterbuf, drunk_speak( filterbuf ), sizeof(filterbuf) );

    return filterbuf;
}

/*
 * season.c  --  Real-world calendar-aware seasonal area selection.
 *
 * At boot, the area loader calls get_seasonal_area() for each filename in
 * area.lst so that the appropriate holiday variant is loaded automatically.
 * No area.lst edits or reboots are needed to switch seasons.
 *
 * WoW-inspired seasonal calendar:
 *   Hallows End  : Oct 18 – Nov  1  (halloween variants)
 *   Winter Veil  : Dec 16 – Jan  6  (xmas variants)
 *   (all other dates load the standard versions)
 */

#include <time.h>
#include <string.h>
#include "merc.h"

/* Internal season identifier. */
typedef enum
{
    SEASON_NORMAL    = 0,
    SEASON_HALLOWEEN = 1,
    SEASON_CHRISTMAS = 2
} SEASON_TYPE;

/*
 * Determine the current real-world season from the OS clock.
 * The server runs NTP-synced, so no internet call is needed.
 */
static SEASON_TYPE get_current_season( void )
{
    time_t     now;
    struct tm *tm_now;
    int        mon, day;

    now    = time( NULL );
    tm_now = localtime( &now );
    mon    = tm_now->tm_mon + 1;   /* 1-12 */
    day    = tm_now->tm_mday;      /* 1-31 */

    /* Hallows End: Oct 18 – Nov 1 */
    if ( (mon == 10 && day >= 18) || (mon == 11 && day == 1) )
        return SEASON_HALLOWEEN;

    /* Winter Veil: Dec 16 – Jan 6 */
    if ( (mon == 12 && day >= 16) || (mon == 1 && day <= 6) )
        return SEASON_CHRISTMAS;

    return SEASON_NORMAL;
}

/*
 * Return a human-readable season name for display in do_time(),
 * or NULL during normal (off-season) periods.
 */
const char *get_season_name( void )
{
    switch ( get_current_season() )
    {
        case SEASON_HALLOWEEN: return "Hallows End";
        case SEASON_CHRISTMAS: return "Winter Veil";
        default:               return NULL;
    }
}

/*
 * Given a base area filename from area.lst, return the season-appropriate
 * variant if one exists, otherwise return the original filename unchanged.
 *
 * Mappings:
 *   dresden.are  → dresden_halloween.are  (Halloween)
 *                  dresden_xmas.are       (Christmas)
 *   limbo.are    → limbo_halloween.are    (Halloween)
 *                  limbo_xmas.are         (Christmas)
 *   midennir.are → midennir_halloween.are (Halloween only)
 */
const char *get_seasonal_area( const char *area_file )
{
    SEASON_TYPE season;

    if ( area_file == NULL )
        return area_file;

    season = get_current_season();

    if ( season == SEASON_HALLOWEEN )
    {
        if ( !str_cmp( area_file, "dresden.are"  ) ) return "dresden_halloween.are";
        if ( !str_cmp( area_file, "limbo.are"    ) ) return "limbo_halloween.are";
        if ( !str_cmp( area_file, "midennir.are" ) ) return "midennir_halloween.are";
    }
    else if ( season == SEASON_CHRISTMAS )
    {
        if ( !str_cmp( area_file, "dresden.are"  ) ) return "dresden_xmas.are";
        if ( !str_cmp( area_file, "limbo.are"    ) ) return "limbo_xmas.are";
        /* No midennir_xmas.are -- fall through to normal */
    }

    return area_file;
}

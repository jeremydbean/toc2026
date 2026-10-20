/*
 * The black market: Vesh the Smuggler, who comes and goes and is never
 * where he was.
 *
 * Owner's design (2026-10-20). He is in the world about one hour in ten:
 * a visit of twenty to forty minutes, then three to six hours away. While
 * he is about he moves about once a minute -- a step through an exit, or
 * now and then a vanishing and a reappearance somewhere else entirely.
 * Nothing finds him from afar: not WHERE, TRACK, the travel spells,
 * clairvoyance, PROJECT, LOCATE OBJECT or the Oracle. A player sees him
 * standing in the same room, or one room away with SCAN, and that is all.
 *
 * He carries five things at most, drawn fresh each visit from a pool of
 * hundreds: the three best pieces the world places on a mobile for every
 * wear slot in every band of five levels from 29 up, and at any level what
 * is otherwise rare or unobtainable -- the holiday bosses' drops out of
 * season, the training cakes and Valhalla's lucky clovers. Each character
 * may buy one of each item from a stock, remembered in the player file by
 * the stock's id, so a relog does not reset it and the next visit does.
 *
 * He does not stand still for business either. A mortal who finds him has
 * BM_BROWSE_MAX seconds to start buying; the first purchase opens a sale
 * window for that buyer alone, long enough to buy one of everything, and
 * when it closes -- or the buyer walks off, or has had one of everything --
 * he vanishes to somewhere else, so a crowd cannot form at one find.
 * Arrivals, departures, vanishings and every purchase are logged with the
 * room; arrivals and purchases also go to staff on WIZINFO.
 *
 * How he is hidden: can_see() asks black_market_sees(), which allows the
 * same room only (and staff), and refuses the psionic projection that
 * PROJECT walks through distant rooms. Everything that finds a character
 * elsewhere -- get_char_world, travel_target, do_where, clairvoyance --
 * goes through can_see. can_see_obj() hides his goods the same way, which
 * is what LOCATE OBJECT and the Oracle ask. SCAN steps the scanner into
 * each neighbouring room, so it sees him one room out; do_scan skips him
 * any further.
 */
#include <time.h>
#include <stdlib.h>
#include <limits.h>
#include "merc.h"
#include "db.h"

extern AREA_DATA *area_first;

CHAR_DATA *black_market_dealer = NULL;

/* When he next arrives (while away) or leaves (while here). */
static time_t bm_next_change = 0;
/* The stock's id: the time it was rolled. What a player bought is kept
   against this, so a new stock is a fresh allowance. */
static long bm_stock_id = 0;

/* About one hour in ten: thirty minutes in, four and a half away. */
#define BM_FIRST_MIN       (10 * 60)
#define BM_FIRST_MAX       (6 * 60 * 60)
#define BM_STAY_MIN        (20 * 60)
#define BM_STAY_MAX        (40 * 60)
#define BM_AWAY_MIN        (3 * 60 * 60)
#define BM_AWAY_MAX        (6 * 60 * 60)

/* He moves about once a minute; one move in eight is a vanishing. */
#define BM_MOVE_MIN        45
#define BM_MOVE_MAX        75
#define BM_TELEPORT_ODDS   8

/* A mortal who finds him has this long to start buying. */
#define BM_BROWSE_MAX      90
/* The first purchase holds him this long for that buyer, and each further
   purchase this much more: five items is three minutes at most. */
#define BM_SALE_FIRST      60
#define BM_SALE_MORE       30

static time_t bm_next_move = 0;
static time_t bm_browse_since = 0;
static CHAR_DATA *bm_buyer = NULL;
static time_t bm_sale_ends = 0;
static bool bm_sold_out = false;

/* The gear pool: the three best pieces the world places on a mobile for
   each wear slot in each band of five levels from 29 up (owner,
   2026-10-20: best in slot from 29; below that only the rarities). */
#define BM_GEAR_MIN_LEVEL  29
#define BM_BAND_WIDTH      5
#define BM_BANDS           7        /* 29-33 ... 54-58, 59 */
#define BM_SLOTS           14
#define BM_PER_SLOT        3
#define BM_POOL_MAX        ( BM_BANDS * BM_SLOTS * BM_PER_SLOT )
#define BM_STOCK_MAX       5
#define BM_VNUM_MAX        65536

static const int bm_slot_flags[BM_SLOTS] =
{
    ITEM_WEAR_FINGER, ITEM_WEAR_NECK, ITEM_WEAR_BODY, ITEM_WEAR_HEAD,
    ITEM_WEAR_LEGS, ITEM_WEAR_FEET, ITEM_WEAR_HANDS, ITEM_WEAR_ARMS,
    ITEM_WEAR_ABOUT, ITEM_WEAR_WAIST, ITEM_WEAR_WRIST, ITEM_WEAR_SHIELD,
    ITEM_WIELD, ITEM_HOLD
};

static int bm_pool[BM_POOL_MAX];            /* vnums */
static int bm_pool_size = 0;
static bool bm_gear_built = false;

/* What only the holidays give, sold out of season too. */
static const int bm_boss_drops[] =
{
    OBJ_VNUM_HORSEMAN_REAPER, OBJ_VNUM_HORSEMAN_HELM,
    OBJ_VNUM_WINTER_HAMMER,   OBJ_VNUM_WINTER_MANTLE,
    OBJ_VNUM_PUMPKIN_CHARM,   OBJ_VNUM_SNOWFLAKE_PEND
};
/* Training cakes: the holidays' two, and Valhalla's wedding cake, which
   nothing in the world places. */
static const int bm_cakes[] =
{
    OBJ_VNUM_HORSEMAN_CAKE, OBJ_VNUM_WINTER_CAKE, 9955
};
/* Valhalla's two lucky clovers (levels 5 and 20), held in the hand;
   nothing places them either. */
static const int bm_charms[] =
{
    9943, 9944
};
#define BM_BOSS_DROP_CHANCE   40   /* percent of stocks */
#define BM_CAKE_CHANCE        30
#define BM_CHARM_CHANCE       30

/* What cannot be had in the ordinary way -- nothing in the world resets it
   onto a mobile -- costs five times the dealer's standard price (owner,
   2026-10-20: black market stuff is expensive and hard to get). */
#define BM_RARE_MARKUP        5

/* Hyrule's objects, every one of them: the Triforce and its pieces, the
   Master Sword, the guardians' keys and treasures are a progression of
   their own, and the dealer never sells any part of it (owner,
   2026-10-20). The generator owns 30200 onward; this covers the lot. */
#define BM_HYRULE_OBJ_FIRST   30200
#define BM_HYRULE_OBJ_LAST    30999

/* Vnums a reset puts on a mobile, and vnums some door or container in
   the world asks for as its key. Built with the gear pool. */
static bool bm_placed[BM_VNUM_MAX];
static bool bm_is_key[BM_VNUM_MAX];

/* Areas whose gear is not the dealer's to sell, and where he never goes:
   Hyrule is a progression of its own, the yard and the seasonal file are
   not places, and nothing in the world leads to the last two. */
static const char * const bm_skip_areas[] =
{
    "hyrule.are", "dummy.are", "seasonal.are", "quest1.are", "tdespair.are",
    NULL
};


/* Vnums are short on some fields and int on others; one range test,
   through a long, serves both without the compiler calling it moot. */
static bool bm_vnum_ok( long vnum )
{
    return vnum > 0 && vnum < BM_VNUM_MAX;
}

bool is_black_market_dealer( const CHAR_DATA *ch )
{
    return ch != NULL && IS_NPC(ch) && ch->pIndexData != NULL
        && ch->pIndexData->vnum == MOB_VNUM_BLACK_MARKET;
}

/*
 * Whether `looker` may see the dealer at all. Staff always; nobody else
 * from another room; and never the psionic projection PROJECT walks
 * through distant rooms, which stands in the room it looks at.
 */
bool black_market_sees( const CHAR_DATA *looker, const CHAR_DATA *dealer )
{
    if ( looker == NULL || dealer == NULL )
        return false;
    if ( !IS_NPC(looker) && IS_TRUSTED( (CHAR_DATA *) looker, LEVEL_IMMORTAL ) )
        return true;
    if ( IS_NPC(looker) && looker->pIndexData != NULL
    &&   looker->pIndexData->vnum == MOB_VNUM_PSIONIC_PROJECTION )
        return false;
    return looker->in_room != NULL && looker->in_room == dealer->in_room;
}

/* The dealer and the treasure goblin: seen in their own room and nowhere
   else, by the same rule (black_market_sees). */
bool is_unfindable_mob( const CHAR_DATA *ch )
{
    return is_black_market_dealer( ch ) || is_treasure_goblin( ch );
}

/* Whether an object is the dealer's, however deep in a container. */
bool black_market_holds( const OBJ_DATA *obj )
{
    int depth = 0;

    while ( obj != NULL && obj->in_obj != NULL && depth++ < 32 )
        obj = obj->in_obj;
    return obj != NULL && is_black_market_dealer( obj->carried_by );
}

static bool bm_skip_area( const AREA_DATA *area )
{
    int i;

    if ( area == NULL || area->file_name == NULL )
        return true;
    for ( i = 0; bm_skip_areas[i] != NULL; i++ )
        if ( !str_cmp( area->file_name, bm_skip_areas[i] ) )
            return true;
    return false;
}

/* "room 4207 (The Temple of Mota, dresden.are)", for the log and WIZINFO. */
static void bm_where( ROOM_INDEX_DATA *room, char *out, size_t len )
{
    if ( room == NULL )
    {
        toc_strlcpy( out, "nowhere", len );
        return;
    }
    snprintf( out, len, "room %d (%s, %s)", room->vnum,
              room->name != NULL ? room->name : "?",
              room->area != NULL && room->area->file_name != NULL
                  ? room->area->file_name : "?" );
}


/* ---------------------------------------------------------------- stock */

/* What a mobile of this level carries, on average, in copper -- the
   averages of mob_index_set_wealth's rolls. A price is about forty of
   these at the item's level; the black market asks sixty. */
static long bm_kill_value( int level )
{
    level = URANGE( 1, level, 60 );
    if ( level < 5 )  return level;
    if ( level < 10 ) return 102L * level;
    if ( level < 20 ) return 5104L * level;
    if ( level < 30 ) return 10208L * level;
    if ( level < 50 ) return 15306L * level;
    return 270402L * level;
}

/* The treasure goblin pays in the same currency. */
long black_market_kill_value( int level )
{
    return bm_kill_value( level );
}

#define BM_PRICE_KILLS      60
#define BM_CAKE_PRICE_KILLS 40      /* at level 50 */
/* Far below LONG_MAX, so the markup cannot overflow it. */
#define BM_PRICE_CAP        ( LONG_MAX / 64 )

/* A dealer names round sums: whole platinum, whole gold or whole silver,
   so LIST reads "811p" and not "811p 20g 60s". */
static long bm_round( long copper )
{
    long unit = copper >= COPPER_PER_PLATINUM ? COPPER_PER_PLATINUM
              : copper >= COPPER_PER_GOLD     ? COPPER_PER_GOLD
              : COPPER_PER_SILVER;

    return UMAX( unit, ( copper + unit / 2 ) / unit * unit );
}

/* The dealer's standard price: sixty kills at the item's level or three
   times its worth, whichever is more; a training cake forty level-50
   kills. Five times that for anything no reset puts on a mobile. */
static long bm_price( OBJ_INDEX_DATA *pObj )
{
    long by_cost, by_kills, price;

    if ( pObj->item_type == ITEM_CAKE )
        price = BM_CAKE_PRICE_KILLS * bm_kill_value( 50 );
    else
    {
        by_cost  = pObj->cost > BM_PRICE_CAP / 3 ? BM_PRICE_CAP : pObj->cost * 3;
        by_kills = BM_PRICE_KILLS * bm_kill_value( pObj->level );
        price    = UMAX( by_cost, by_kills );
    }
    price = UMIN( BM_PRICE_CAP, price );
    if ( !bm_vnum_ok( pObj->vnum ) || !bm_placed[pObj->vnum] )
        price *= BM_RARE_MARKUP;
    return bm_round( price );
}

/* Anything a player's progress depends on, which the dealer never sells:
   Hyrule's whole object range, every key, and anything a door or a
   container in the world takes as its key. */
static bool bm_progression( OBJ_INDEX_DATA *pObj )
{
    if ( pObj == NULL )
        return true;
    if ( pObj->vnum >= BM_HYRULE_OBJ_FIRST && pObj->vnum <= BM_HYRULE_OBJ_LAST )
        return true;
    if ( pObj->item_type == ITEM_KEY )
        return true;
    if ( bm_vnum_ok( pObj->vnum ) && bm_is_key[pObj->vnum] )
        return true;
    return false;
}

/* What a piece is worth to whoever wears it, damage first: the same order
   COMPARE and the Gear Finder use, simply weighted, because the dealer
   chooses for nobody in particular. */
static double bm_gear_score( OBJ_INDEX_DATA *pObj )
{
    AFFECT_DATA *paf;
    double score = 0.0;

    for ( paf = pObj->affected; paf != NULL; paf = paf->next )
    {
        switch ( paf->location )
        {
        case APPLY_DAMROLL: score += 3.0 * paf->modifier; break;
        case APPLY_HITROLL: score += 2.0 * paf->modifier; break;
        case APPLY_STR: case APPLY_DEX: case APPLY_INT:
        case APPLY_WIS: case APPLY_CON:
                            score += 2.0 * paf->modifier; break;
        case APPLY_HIT:     score += paf->modifier / 5.0; break;
        case APPLY_MANA:    score += paf->modifier / 10.0; break;
        case APPLY_MOVE:    score += paf->modifier / 20.0; break;
        case APPLY_AC:      score -= paf->modifier / 2.0; break;
        case APPLY_SAVING_PARA: case APPLY_SAVING_ROD:
        case APPLY_SAVING_PETRI: case APPLY_SAVING_BREATH:
        case APPLY_SAVING_SPELL:
                            score -= paf->modifier; break;
        default: break;
        }
    }
    if ( pObj->item_type == ITEM_ARMOR )
        score += ( pObj->value[0] + pObj->value[1] + pObj->value[2]
                 + pObj->value[3] ) / 8.0;
    if ( pObj->item_type == ITEM_WEAPON )
        score += pObj->value[1] * ( pObj->value[2] + 1 ) / 2.0 * 1.5;
    return score;
}

static int bm_slot_of( int wear_flags )
{
    int i;

    for ( i = 0; i < BM_SLOTS; i++ )
        if ( IS_SET( wear_flags, bm_slot_flags[i] ) )
            return i;
    return -1;
}

/* Whether a prototype may be stocked at all. */
static bool bm_sellable( OBJ_INDEX_DATA *pObj )
{
    if ( pObj == NULL || pObj->level < 1 || pObj->level > LEVEL_HERO4 + 4 )
        return false;
    if ( !IS_SET( pObj->wear_flags, ITEM_TAKE ) )
        return false;
    if ( IS_SET( pObj->extra_flags, ITEM_NODROP )
    ||   IS_SET( pObj->extra_flags, ITEM_NOREMOVE )
    ||   IS_SET( pObj->extra_flags, ITEM_INVENTORY )
    ||   IS_SET( pObj->extra_flags, ITEM_ROT_DEATH )
    /* LIST hides it from anyone without detect invisible: a wasted slot. */
    ||   IS_SET( pObj->extra_flags, ITEM_INVIS ) )
        return false;
    /* A load-limited item is unique by design; infinite copies of it
       would break that. */
    if ( get_maxload_index( pObj->vnum ) != NULL )
        return false;
    if ( bm_progression( pObj ) )
        return false;
    if ( pObj->vnum >= OBJ_VNUM_QUEST_TOKEN_FIRST
    &&   pObj->vnum <= OBJ_VNUM_QUEST_TOKEN_LAST )
        return false;
    return true;
}

/*
 * The gear pool: for each band of five levels from 29 and each slot, the three
 * highest-scoring pieces that some mobile carries or wears by reset,
 * outside the skipped areas and staff rooms. Built once, the first time a
 * stock is rolled; the world's prototypes do not change while the game
 * runs except by building, and a built piece is not in the world until
 * something resets it.
 */
static void bm_build_gear( void )
{
    static double best[BM_BANDS][BM_SLOTS][BM_PER_SLOT];
    static int vnums[BM_BANDS][BM_SLOTS][BM_PER_SLOT];
    AREA_DATA *area;
    int iHash, b, s, k;

    for ( b = 0; b < BM_BANDS; b++ )
        for ( s = 0; s < BM_SLOTS; s++ )
            for ( k = 0; k < BM_PER_SLOT; k++ )
            {
                vnums[b][s][k] = 0;
                best[b][s][k] = 0.0;
            }

    for ( area = area_first; area != NULL; area = area->next )
    {
        RESET_DATA *pReset;
        ROOM_INDEX_DATA *mob_room = NULL;

        if ( bm_skip_area( area ) )
            continue;
        for ( pReset = area->reset_first; pReset != NULL; pReset = pReset->next )
        {
            if ( pReset->command == 'M' )
                mob_room = get_room_index( pReset->arg3 );
            else if ( ( pReset->command == 'G' || pReset->command == 'E' )
                 &&   mob_room != NULL
                 &&   !IS_SET( mob_room->room_flags, ROOM_IMP_ONLY )
                 &&   !IS_SET( mob_room->room_flags, ROOM_GODS_ONLY )
                 &&   bm_vnum_ok( pReset->arg1 ) )
                bm_placed[pReset->arg1] = true;
        }
    }

    /* Every key a door or a container asks for: progression, never sold. */
    for ( iHash = 0; iHash < MAX_KEY_HASH; iHash++ )
    {
        ROOM_INDEX_DATA *room;
        OBJ_INDEX_DATA *pObj;
        int door;

        for ( room = room_index_hash[iHash]; room != NULL; room = room->next )
            for ( door = 0; door <= 9; door++ )
                if ( room->exit[door] != NULL
                &&   bm_vnum_ok( room->exit[door]->key ) )
                    bm_is_key[room->exit[door]->key] = true;
        for ( pObj = obj_index_hash[iHash]; pObj != NULL; pObj = pObj->next )
            if ( pObj->item_type == ITEM_CONTAINER
            &&   bm_vnum_ok( pObj->value[2] ) )
                bm_is_key[pObj->value[2]] = true;
    }

    for ( iHash = 0; iHash < MAX_KEY_HASH; iHash++ )
    {
        OBJ_INDEX_DATA *pObj;

        for ( pObj = obj_index_hash[iHash]; pObj != NULL; pObj = pObj->next )
        {
            double score;

            if ( !bm_vnum_ok( pObj->vnum )
            ||   !bm_placed[pObj->vnum] || !bm_sellable( pObj ) )
                continue;
            if ( pObj->item_type != ITEM_ARMOR && pObj->item_type != ITEM_WEAPON
            &&   pObj->item_type != ITEM_CLOTHING
            &&   pObj->item_type != ITEM_TREASURE
            &&   pObj->item_type != ITEM_LIGHT )
                continue;
            if ( pObj->level < BM_GEAR_MIN_LEVEL
            ||   ( s = bm_slot_of( pObj->wear_flags ) ) < 0 )
                continue;
            b = URANGE( 0, ( pObj->level - BM_GEAR_MIN_LEVEL ) / BM_BAND_WIDTH,
                        BM_BANDS - 1 );
            score = bm_gear_score( pObj );
            if ( score <= 0.0 )
                continue;
            /* Insert into this band and slot's best three, highest first;
               a tie goes to the lower vnum, so the pool is the same every
               boot whatever order the hash walks in. */
            for ( k = 0; k < BM_PER_SLOT; k++ )
                if ( vnums[b][s][k] == 0 || score > best[b][s][k]
                ||   ( score == best[b][s][k] && pObj->vnum < vnums[b][s][k] ) )
                    break;
            if ( k >= BM_PER_SLOT )
                continue;
            {
                int j;

                for ( j = BM_PER_SLOT - 1; j > k; j-- )
                {
                    best[b][s][j]  = best[b][s][j - 1];
                    vnums[b][s][j] = vnums[b][s][j - 1];
                }
            }
            best[b][s][k]  = score;
            vnums[b][s][k] = pObj->vnum;
        }
    }

    bm_pool_size = 0;
    for ( b = 0; b < BM_BANDS; b++ )
        for ( s = 0; s < BM_SLOTS; s++ )
            for ( k = 0; k < BM_PER_SLOT; k++ )
                if ( vnums[b][s][k] != 0 )
                    bm_pool[bm_pool_size++] = vnums[b][s][k];
    bm_gear_built = true;
}

static int bm_stock_count( CHAR_DATA *dealer )
{
    OBJ_DATA *obj;
    int n = 0;

    for ( obj = dealer->carrying; obj != NULL; obj = obj->next_content )
        n++;
    return n;
}

static bool bm_stock_one( CHAR_DATA *dealer, int vnum )
{
    OBJ_INDEX_DATA *pObj;
    OBJ_DATA *obj;

    if ( bm_stock_count( dealer ) >= BM_STOCK_MAX )
        return false;
    if ( ( pObj = get_obj_index( vnum ) ) == NULL || pObj->level < 0
    ||   bm_progression( pObj ) )
        return false;
    for ( obj = dealer->carrying; obj != NULL; obj = obj->next_content )
        if ( obj->pIndexData == pObj )
            return false;
    /* A negative level: no random enchantment, the prototype's own level. */
    obj = create_object( pObj, -UMAX( 1, pObj->level ) );
    SET_BIT( obj->extra_flags, ITEM_INVENTORY );
    obj->cost = bm_price( pObj );
    obj->timer = 0;
    obj_to_char( obj, dealer );
    return true;
}

#define BM_PICK(list) \
    ( (list)[number_range( 0, (int)( sizeof(list) / sizeof((list)[0]) ) - 1 )] )

/* Throw out the old stock and lay out a new one: the rarities that came up
   this time, then pieces from the gear pool until he carries five. */
void black_market_restock( void )
{
    CHAR_DATA *dealer = black_market_dealer;
    OBJ_DATA *obj, *obj_next;
    long id = (long) current_time;
    int tries;

    if ( dealer == NULL )
        return;
    if ( !bm_gear_built )
        bm_build_gear();

    for ( obj = dealer->carrying; obj != NULL; obj = obj_next )
    {
        obj_next = obj->next_content;
        extract_obj( obj );
    }

    /* A new id even when two stocks fall in the same second. */
    bm_stock_id = id > bm_stock_id ? id : bm_stock_id + 1;

    if ( number_percent() <= BM_BOSS_DROP_CHANCE )
        bm_stock_one( dealer, BM_PICK( bm_boss_drops ) );
    if ( number_percent() <= BM_CAKE_CHANCE )
        bm_stock_one( dealer, BM_PICK( bm_cakes ) );
    if ( number_percent() <= BM_CHARM_CHANCE )
        bm_stock_one( dealer, BM_PICK( bm_charms ) );

    for ( tries = 0; tries < 50 && bm_pool_size > 0
          && bm_stock_count( dealer ) < BM_STOCK_MAX; tries++ )
        bm_stock_one( dealer, bm_pool[number_range( 0, bm_pool_size - 1 )] );
}


/* ------------------------------------------------------------- movement */

/* Somewhere he may stand: a room anyone could walk into. */
static bool bm_room_ok( ROOM_INDEX_DATA *room )
{
    static ROOM_INDEX_DATA *halls[1024];
    static int nhalls = -1;
    int door, i;
    bool has_exit = false;

    if ( room == NULL || bm_skip_area( room->area ) )
        return false;
    if ( IS_SET( room->room_flags, ROOM_NO_MOB )
    ||   IS_SET( room->room_flags, ROOM_DT )
    ||   IS_SET( room->room_flags, ROOM_JAIL )
    ||   IS_SET( room->room_flags, ROOM_PRIVATE )
    ||   IS_SET( room->room_flags, ROOM_SOLITARY )
    ||   IS_SET( room->room_flags, ROOM_IMP_ONLY )
    ||   IS_SET( room->room_flags, ROOM_GODS_ONLY )
    ||   IS_SET( room->room_flags, ROOM_HEROES_ONLY )
    ||   IS_SET( room->room_flags, ROOM_NEWBIES_ONLY )
    ||   IS_SET( room->room_flags, ROOM_PET_SHOP )
    ||   IS_SET( room->room_flags, ROOM_ARENA ) )
        return false;

    for ( door = 0; door <= 9; door++ )
        if ( room->exit[door] != NULL && room->exit[door]->u1.to_room != NULL )
            has_exit = true;
    if ( !has_exit )
        return false;

    /* Never inside a guild hall, which only its members could reach. */
    if ( nhalls < 0 )
        nhalls = guild_hall_rooms( halls, 1024 );
    for ( i = 0; i < nhalls; i++ )
        if ( halls[i] == room )
            return false;
    return true;
}

static ROOM_INDEX_DATA *bm_random_room( void )
{
    int tries;

    for ( tries = 0; tries < 40; tries++ )
    {
        ROOM_INDEX_DATA *room = random_scatter_room( NULL );

        if ( bm_room_ok( room ) )
            return room;
    }
    return NULL;
}

/* A mortal standing with him: staff watching do not hold him. */
/*
 * What the treasure goblin's sack holds for whoever killed him: the best
 * piece the world places on a mobile for one slot, chosen at random, among
 * pieces of the killer's level or up to five below it (owner,
 * 2026-10-20). The window widens to ten levels if those five hold nothing.
 */
int black_market_gear_for_level( int level )
{
    int best_vnum[BM_SLOTS];
    double best_score[BM_SLOTS];
    int width, s, iHash;

    if ( !bm_gear_built )
        bm_build_gear();
    level = URANGE( 1, level, LEVEL_HERO4 + 4 );
    for ( width = 5; width <= 10; width += 5 )
    {
        int slots[BM_SLOTS], n = 0;

        for ( s = 0; s < BM_SLOTS; s++ )
        {
            best_vnum[s] = 0;
            best_score[s] = 0.0;
        }
        for ( iHash = 0; iHash < MAX_KEY_HASH; iHash++ )
        {
            OBJ_INDEX_DATA *pObj;

            for ( pObj = obj_index_hash[iHash]; pObj != NULL; pObj = pObj->next )
            {
                double score;

                if ( pObj->level > level || pObj->level < level - width
                ||   !bm_vnum_ok( pObj->vnum ) || !bm_placed[pObj->vnum]
                ||   !bm_sellable( pObj ) )
                    continue;
                if ( pObj->item_type != ITEM_ARMOR && pObj->item_type != ITEM_WEAPON
                &&   pObj->item_type != ITEM_CLOTHING
                &&   pObj->item_type != ITEM_TREASURE
                &&   pObj->item_type != ITEM_LIGHT )
                    continue;
                if ( ( s = bm_slot_of( pObj->wear_flags ) ) < 0 )
                    continue;
                if ( ( score = bm_gear_score( pObj ) ) <= 0.0 )
                    continue;
                if ( score > best_score[s]
                ||   ( score == best_score[s] && pObj->vnum < best_vnum[s] ) )
                {
                    best_score[s] = score;
                    best_vnum[s] = pObj->vnum;
                }
            }
        }
        for ( s = 0; s < BM_SLOTS; s++ )
            if ( best_vnum[s] != 0 )
                slots[n++] = s;
        if ( n > 0 )
            return best_vnum[slots[number_range( 0, n - 1 )]];
    }
    return 0;
}

int black_market_rarity( void )
{
    switch ( number_range( 0, 2 ) )
    {
    case 0:  return BM_PICK( bm_boss_drops );
    case 1:  return BM_PICK( bm_cakes );
    default: return BM_PICK( bm_charms );
    }
}

/* The treasure goblin keeps to the same rooms. */
bool black_market_room_ok( ROOM_INDEX_DATA *room )
{
    return bm_room_ok( room );
}

ROOM_INDEX_DATA *black_market_random_room( void )
{
    return bm_random_room();
}

static bool bm_has_customer( CHAR_DATA *dealer )
{
    CHAR_DATA *rch;

    if ( dealer->in_room == NULL )
        return false;
    for ( rch = dealer->in_room->people; rch != NULL; rch = rch->next_in_room )
        if ( !IS_NPC(rch) && !IS_TRUSTED( rch, LEVEL_IMMORTAL ) )
            return true;
    return false;
}

/* Whatever business he was doing ends when he moves. */
static void bm_end_business( void )
{
    bm_buyer = NULL;
    bm_sale_ends = 0;
    bm_sold_out = false;
    bm_browse_since = 0;
    bm_next_move = current_time + number_range( BM_MOVE_MIN, BM_MOVE_MAX );
}

/*
 * He vanishes and steps out somewhere else: `farewell` is said to the room
 * he leaves first, if any; `why` goes to the log.
 */
static void bm_teleport( CHAR_DATA *dealer, ROOM_INDEX_DATA *to,
                         const char *farewell, const char *why )
{
    char from[MAX_STRING_LENGTH], where[MAX_STRING_LENGTH];
    char line[MAX_STRING_LENGTH * 2 + 128];

    bm_end_business();
    if ( to == NULL || to == dealer->in_room )
        return;
    bm_where( dealer->in_room, from, sizeof(from) );
    if ( farewell != NULL )
        act( farewell, dealer, NULL, NULL, TO_ROOM );
    act( "$n pulls $s hood low, steps into the nearest shadow and is gone.",
         dealer, NULL, NULL, TO_ROOM );
    char_from_room( dealer );
    char_to_room( dealer, to );
    act( "$n slips out of the shadows, a heavy pack over $s shoulder.",
         dealer, NULL, NULL, TO_ROOM );
    bm_where( to, where, sizeof(where) );
    snprintf( line, sizeof(line), "Black market: the dealer vanished from %s "
              "to %s (%s).", from, where, why );
    log_string( line );
}

/* A step through some exit he may take; false when there is none. */
static bool bm_step( CHAR_DATA *dealer )
{
    int doors[10], n = 0, door;

    for ( door = 0; door <= 9; door++ )
    {
        EXIT_DATA *pexit = dealer->in_room->exit[door];

        if ( pexit != NULL && !IS_SET( pexit->exit_info, EX_CLOSED )
        &&   bm_room_ok( pexit->u1.to_room ) )
            doors[n++] = door;
    }
    if ( n == 0 )
        return false;
    move_char( dealer, doors[number_range( 0, n - 1 )], false );
    return true;
}

/* He arrives: somewhere at random, with a fresh stock. */
bool black_market_arrive( ROOM_INDEX_DATA *room )
{
    MOB_INDEX_DATA *pMob;
    char where[MAX_STRING_LENGTH];
    char line[MAX_STRING_LENGTH * 2];
    long stay;

    if ( black_market_dealer != NULL )
        return false;
    if ( ( pMob = get_mob_index( MOB_VNUM_BLACK_MARKET ) ) == NULL )
    {
        bug( "Black market: dealer mobile %d is missing.", MOB_VNUM_BLACK_MARKET );
        return false;
    }
    if ( room == NULL && ( room = bm_random_room() ) == NULL )
        return false;

    black_market_dealer = create_mobile( pMob );
    char_to_room( black_market_dealer, room );
    act( "$n slips out of the shadows, a heavy pack over $s shoulder.",
         black_market_dealer, NULL, NULL, TO_ROOM );
    black_market_restock();
    bm_end_business();

    stay = number_range( BM_STAY_MIN, BM_STAY_MAX );
    bm_next_change = current_time + stay;
    bm_where( room, where, sizeof(where) );
    snprintf( line, sizeof(line), "Black market: the dealer appeared in %s with "
              "%d items (stock %ld), for %ld minutes.", where,
              bm_stock_count( black_market_dealer ), bm_stock_id, stay / 60 );
    log_string( line );
    wizinfo( line, LEVEL_IMMORTAL );
    return true;
}

/* He leaves the world, taking his stock with him. */
void black_market_depart( void )
{
    CHAR_DATA *dealer = black_market_dealer;
    char where[MAX_STRING_LENGTH];
    char line[MAX_STRING_LENGTH + 64];

    if ( dealer == NULL )
        return;
    bm_where( dealer->in_room, where, sizeof(where) );
    if ( dealer->in_room != NULL )
        act( "$n shoulders $s pack and melts into the shadows.", dealer,
             NULL, NULL, TO_ROOM );
    extract_char( dealer, true );     /* clears black_market_dealer */
    black_market_dealer = NULL;
    bm_end_business();
    bm_next_change = current_time + number_range( BM_AWAY_MIN, BM_AWAY_MAX );
    snprintf( line, sizeof(line), "Black market: the dealer left the world "
              "from %s.", where );
    log_string( line );
}

/* extract_char calls this, so a PURGE or a quit cannot leave a dangling
   pointer. */
void black_market_forget( CHAR_DATA *ch )
{
    if ( ch == NULL )
        return;
    if ( ch == black_market_dealer )
    {
        black_market_dealer = NULL;
        bm_buyer = NULL;
    }
    if ( ch == bm_buyer )
        bm_buyer = NULL;
}

static bool bm_already_bought( CHAR_DATA *ch, int vnum );

/* Whether the buyer has had one of everything he carries. */
static bool bm_bought_everything( CHAR_DATA *ch, CHAR_DATA *dealer )
{
    OBJ_DATA *obj;

    for ( obj = dealer->carrying; obj != NULL; obj = obj->next_content )
        if ( !bm_already_bought( ch, obj->pIndexData->vnum ) )
            return false;
    return true;
}

/* Every mobile pulse, from update_handler. */
void black_market_update( void )
{
    CHAR_DATA *dealer;
    bool still = getenv( "TOC_BLACK_MARKET_STILL" ) != NULL;

    if ( bm_next_change == 0 )
    {
        bm_next_change = current_time
                       + number_range( BM_FIRST_MIN, BM_FIRST_MAX );
        return;
    }

    if ( ( dealer = black_market_dealer ) == NULL )
    {
        if ( current_time >= bm_next_change && !black_market_arrive( NULL ) )
            bm_next_change = current_time + 10 * 60;   /* try again later */
        return;
    }

    if ( dealer->in_room == NULL || dealer->fighting != NULL
    ||   dealer->position != POS_STANDING )
        return;

    /* A sale under way: the window closes, the buyer walks off, or the
       buyer has had one of everything -- and he is gone, so the next
       customer has to find him again. */
    if ( bm_sale_ends != 0 )
    {
        if ( bm_buyer == NULL || bm_buyer->in_room != dealer->in_room )
            bm_teleport( dealer, bm_random_room(), NULL, "his buyer left" );
        else if ( bm_sold_out )
            bm_teleport( dealer, bm_random_room(),
                "$n tucks the coin away. 'Pleasure. Don't look for me here again.'",
                "his buyer had one of everything" );
        else if ( current_time >= bm_sale_ends )
            bm_teleport( dealer, bm_random_room(),
                "$n glances at the doorway. 'Too many eyes. Another time.'",
                "the sale window closed" );
        return;
    }

    if ( current_time >= bm_next_change && !bm_has_customer( dealer ) && !still )
    {
        black_market_depart();
        return;
    }

    /* The live tests hold him still: a move between two commands would
       make every assertion about where he is a coin toss. */
    if ( still )
        return;

    /* Somebody standing with him has a minute and a half to start buying. */
    if ( bm_has_customer( dealer ) )
    {
        if ( bm_browse_since == 0 )
            bm_browse_since = current_time;
        else if ( current_time - bm_browse_since >= BM_BROWSE_MAX )
            bm_teleport( dealer, bm_random_room(),
                "$n mutters, 'Buy or move along. I don't stand still for gawkers.'",
                "nobody bought" );
        return;
    }
    bm_browse_since = 0;

    if ( current_time < bm_next_move )
        return;
    bm_next_move = current_time + number_range( BM_MOVE_MIN, BM_MOVE_MAX );
    if ( number_range( 1, BM_TELEPORT_ODDS ) == 1 || !bm_step( dealer ) )
        bm_teleport( dealer, bm_random_room(), NULL, "wandering" );
}


/* ------------------------------------------------------------ purchases */

static bool bm_already_bought( CHAR_DATA *ch, int vnum )
{
    char word[MAX_INPUT_LENGTH];
    const char *p;

    if ( IS_NPC(ch) || ch->pcdata == NULL
    ||   ch->pcdata->black_market_stock != bm_stock_id
    ||   ch->pcdata->black_market_bought == NULL )
        return false;
    for ( p = ch->pcdata->black_market_bought; *p != '\0'; )
    {
        p = one_argument( (char *) p, word );
        if ( word[0] != '\0' && atoi( word ) == vnum )
            return true;
    }
    return false;
}

/* LIST's marker for what this character has had from this stock. */
bool black_market_bought( CHAR_DATA *ch, CHAR_DATA *keeper, OBJ_DATA *obj )
{
    return is_black_market_dealer( keeper ) && obj != NULL
        && bm_already_bought( ch, obj->pIndexData->vnum );
}

/* One of each item, a character, a stock; and one customer at a time. */
bool black_market_buy_refuses( CHAR_DATA *ch, CHAR_DATA *keeper, OBJ_DATA *obj )
{
    if ( !is_black_market_dealer( keeper ) || obj == NULL )
        return false;
    if ( IS_NPC(ch) || ch->pcdata == NULL )
    {
        act( "$n tells you 'I don't deal with errand boys.'", keeper, NULL, ch, TO_VICT );
        return true;
    }
    if ( bm_already_bought( ch, obj->pIndexData->vnum ) )
    {
        act( "$n tells you 'One to a customer. You've had your $p.'",
             keeper, obj, ch, TO_VICT );
        return true;
    }
    if ( bm_buyer != NULL && bm_buyer != ch )
    {
        act( "$n tells you 'I'm with a customer. Find me again some other time.'",
             keeper, NULL, ch, TO_VICT );
        return true;
    }
    return false;
}

void black_market_record( CHAR_DATA *ch, CHAR_DATA *keeper, OBJ_DATA *obj )
{
    char buf[MAX_STRING_LENGTH];
    char where[MAX_STRING_LENGTH];
    char price[MAX_INPUT_LENGTH];
    char line[MAX_STRING_LENGTH * 2];

    if ( !is_black_market_dealer( keeper ) || obj == NULL
    ||   IS_NPC(ch) || ch->pcdata == NULL )
        return;
    if ( ch->pcdata->black_market_stock != bm_stock_id
    ||   ch->pcdata->black_market_bought == NULL )
    {
        free_string( ch->pcdata->black_market_bought );
        ch->pcdata->black_market_bought = str_dup( "" );
        ch->pcdata->black_market_stock = bm_stock_id;
    }
    snprintf( buf, sizeof(buf), "%s%s%d", ch->pcdata->black_market_bought,
              ch->pcdata->black_market_bought[0] != '\0' ? " " : "",
              obj->pIndexData->vnum );
    free_string( ch->pcdata->black_market_bought );
    ch->pcdata->black_market_bought = str_dup( buf );
    /* Written at once: a crash between the purchase and the next save
       must not hand the allowance back. */
    save_char_obj( ch );

    /* The sale window: the first purchase opens it for this buyer, each
       further one stretches it. */
    if ( bm_buyer == NULL )
    {
        bm_buyer = ch;
        bm_sale_ends = current_time + BM_SALE_FIRST;
    }
    else
        bm_sale_ends += BM_SALE_MORE;
    if ( bm_bought_everything( ch, keeper ) )
        bm_sold_out = true;

    format_price( bm_price( obj->pIndexData ), price, sizeof(price) );
    bm_where( keeper->in_room, where, sizeof(where) );
    snprintf( line, sizeof(line), "Black market: %s bought %s (%d) for %s in %s.",
              ch->name, obj->short_descr, obj->pIndexData->vnum, price, where );
    log_string( line );
    wizinfo( line, LEVEL_IMMORTAL );
}


/* ---------------------------------------------------------------- staff */

void do_blackmarket( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    CHAR_DATA *dealer = black_market_dealer;

    one_argument( argument, arg );

    if ( arg[0] == '\0' || !str_prefix( arg, "status" ) )
    {
        OBJ_DATA *obj;

        if ( !bm_gear_built )
            bm_build_gear();
        if ( dealer == NULL || dealer->in_room == NULL )
        {
            snprintf( buf, sizeof(buf), "The dealer is away; he returns in about "
                      "%ld minutes.\n\r",
                      (long) UMAX( 0, bm_next_change - current_time ) / 60 );
            send_to_char( buf, ch );
        }
        else
        {
            snprintf( buf, sizeof(buf), "The dealer is in room %d (%s), leaving in "
                      "about %ld minutes. Stock %ld:\n\r", dealer->in_room->vnum,
                      dealer->in_room->name,
                      (long) UMAX( 0, bm_next_change - current_time ) / 60,
                      bm_stock_id );
            send_to_char( buf, ch );
            for ( obj = dealer->carrying; obj != NULL; obj = obj->next_content )
            {
                char price[MAX_INPUT_LENGTH];

                format_price( obj->cost, price, sizeof(price) );
                snprintf( buf, sizeof(buf), "  [%2d %12s] %s (%d)\n\r", obj->level,
                          price, obj->short_descr, obj->pIndexData->vnum );
                send_to_char( buf, ch );
            }
            if ( bm_buyer != NULL )
            {
                snprintf( buf, sizeof(buf), "Selling to %s for %ld more seconds.\n\r",
                          bm_buyer->name,
                          (long) UMAX( 0, bm_sale_ends - current_time ) );
                send_to_char( buf, ch );
            }
        }
        snprintf( buf, sizeof(buf), "Pool: %d pieces of gear, %d rarities.\n\r",
                  bm_pool_size,
                  (int) ( sizeof(bm_boss_drops) / sizeof(bm_boss_drops[0])
                        + sizeof(bm_cakes) / sizeof(bm_cakes[0])
                        + sizeof(bm_charms) / sizeof(bm_charms[0]) ) );
        send_to_char( buf, ch );
        send_to_char( "Syntax: blackmarket [status|summon|here|restock|dismiss]\n\r", ch );
        return;
    }

    if ( !str_prefix( arg, "summon" ) || !str_prefix( arg, "here" ) )
    {
        bool here = !str_prefix( arg, "here" );

        if ( dealer == NULL )
        {
            if ( !black_market_arrive( here ? ch->in_room : NULL ) )
            {
                send_to_char( "He would not come.\n\r", ch );
                return;
            }
        }
        else if ( here )
            bm_teleport( dealer, ch->in_room, NULL, "called by staff" );
        snprintf( buf, sizeof(buf), "The dealer is in room %d.\n\r",
                  black_market_dealer->in_room->vnum );
        send_to_char( buf, ch );
        snprintf( buf, sizeof(buf), "%s called the black market dealer to room %d.",
                  ch->name, black_market_dealer->in_room->vnum );
        log_string( buf );
        return;
    }

    if ( !str_prefix( arg, "restock" ) )
    {
        if ( dealer == NULL )
        {
            send_to_char( "He is away.\n\r", ch );
            return;
        }
        black_market_restock();
        bm_end_business();
        send_to_char( "New stock laid out.\n\r", ch );
        return;
    }

    if ( !str_prefix( arg, "dismiss" ) )
    {
        if ( dealer == NULL )
        {
            send_to_char( "He is already away.\n\r", ch );
            return;
        }
        black_market_depart();
        send_to_char( "The dealer is gone.\n\r", ch );
        return;
    }

    send_to_char( "Syntax: blackmarket [status|summon|here|restock|dismiss]\n\r", ch );
}

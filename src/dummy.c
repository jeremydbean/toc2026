/***************************************************************************
 * The training yard: a dummy you can hit as hard as you like, that hits    *
 * back, and that nobody walks away from dead.                              *
 *                                                                          *
 * The point of the place is a number. "Is this sword better than that      *
 * one" is otherwise answered by going and fighting something and forming   *
 * an impression, which is a slow way to be wrong. Here you set the dummy   *
 * up, swing for a minute, type DUMMY REPORT and read what you actually     *
 * did -- and what it did back.                                             *
 *                                                                          *
 * It defaults to your own level, because the question is almost always     *
 * "how do I do against something my size", and a reading against anything  *
 * else is a different question the player did not ask.                     *
 ***************************************************************************/

#include <stdio.h>
#include <string.h>
#include <time.h>

#include "merc.h"
#include "interp.h"
#include "magic.h"

/*
 * What the dummy can pretend to be. They differ in defence rather
 * than in flavour, because each one isolates a different question
 * somebody might be asking about their gear.
 */
typedef struct dummy_shape
{
    const char *name;
    const char *blurb;
    int         ac;
    int         hitroll;
    int         damage_scale;   /* percent of a level-typical blow */
    long        off_flags;
} DUMMY_SHAPE;

static const DUMMY_SHAPE dummy_shape_table[] =
{
    { "soft",    "no armour, no defences -- a clean reading of your damage",
      100,   0,  40, 0 },
    { "armored", "heavily armoured -- is your hitroll keeping up",
      -120, 10,  70, 0 },
    { "evasive", "dodges and parries -- are you landing anything",
      -20,   5,  50, OFF_DODGE | OFF_PARRY },
    { "brutal",  "hits as hard as its level allows -- what can you take",
      -40,  10, 140, 0 },
    { NULL, NULL, 0, 0, 0, 0 }
};

/*
 * What it hits you with. Indices into attack_table, which is what
 * carries the damage school: the point is to test your resistances
 * and your saves, not to vary the verb.
 */
typedef struct dummy_attack
{
    const char *name;
    int         attack;         /* attack_table index */
    const char *blurb;
} DUMMY_ATTACK;

static const DUMMY_ATTACK dummy_attack_table[] =
{
    { "slash",     1,  "ordinary edged weapon damage" },
    { "pierce",    2,  "ordinary thrusting damage" },
    { "bash",      6,  "ordinary blunt damage" },
    { "fire",     29,  "tests fire resistance and immunity" },
    { "cold",     30,  "tests cold resistance" },
    { "lightning",28,  "tests lightning resistance" },
    { "acid",     14,  "tests acid resistance" },
    { "energy",   18,  "tests energy resistance" },
    { "holy",     20,  "tests holy resistance, and alignment" },
    { NULL, 0, NULL }
};

#define DUMMY_SHAPE_DEFAULT  0
#define DUMMY_ATTACK_DEFAULT 0

/* There is one dummy, so one set of settings. An area reset rebuilds
   the mobile and loses these; the next DUMMY command puts them back,
   which is why the menu always writes them rather than trusting them. */
static int dummy_shape = DUMMY_SHAPE_DEFAULT;
static int dummy_attack = DUMMY_ATTACK_DEFAULT;



/*
 * What it can cast at you.  Named by what they test rather than by
 * the spell, because the player is choosing a question, not a
 * spellbook.  Resolved by name through skill_lookup so a renamed
 * spell is an entry that politely does nothing rather than a wrong
 * one.
 */
typedef struct dummy_spell
{
    const char *name;
    const char *spell;
    const char *blurb;
} DUMMY_SPELL;

static const DUMMY_SPELL dummy_spell_table[] =
{
    { "none",      "",               "no spells -- weapon damage only" },
    { "force",     "magic missile",  "small and frequent, barely resisted" },
    { "fire",      "fireball",       "fire, and a saving throw for half" },
    { "cold",      "chill touch",    "cold, and a save against the chill" },
    { "lightning", "lightning bolt", "lightning, and a save for half" },
    { "acid",      "acid blast",     "acid, and a save for half" },
    { "light",     "colour spray",   "light, and a save for half" },
    { "harm",      "harm",           "heavy, and very little resists it" },
    { "negative",  "cause critical", "negative energy, no saving throw" },
    { NULL, NULL, NULL }
};

#define DUMMY_SPELL_NONE 0

static int  dummy_spell  = DUMMY_SPELL_NONE;
static bool dummy_hasted = false;

/* Whether anybody has chosen a level.  Until somebody has, the dummy
   follows whoever is looking at it, which is the comparison almost
   everybody wants; once somebody has, it stays put, because a
   setting the menu silently undoes is worse than no setting. */
static bool dummy_level_chosen = false;


/*
 * Which column of the report a blow belongs in.  ROM already carries
 * the split: dt is the weapon type at or above TYPE_HIT, and the
 * skill number that caused it otherwise, where a spell is a skill
 * with a real spell function behind it.
 */
static int dummy_source( int dt )
{
    if ( dt >= TYPE_HIT || dt < 0 || dt >= MAX_SKILL )
        return DUMMY_FROM_WEAPON;

    return skill_table[dt].spell_fun != spell_null
         ? DUMMY_FROM_SPELL : DUMMY_FROM_SKILL;
}


static const char *dummy_source_name[3] = { "weapon", "spells", "skills" };
static const char *dummy_avoid_name[4]  = { "ducked", "parried", "dodged",
                                            "blocked" };

/*
 * One row per attack.  The key is dt, which ROM already sets to the
 * skill that caused the blow or to the weapon's attack type, so
 * every spell and every special attack separates itself and nothing
 * here has to guess.
 */
static DUMMY_SOURCE_DATA *dummy_slot( DUMMY_SOURCE_DATA *table, int dt )
{
    int i;

    for ( i = 0; i < DUMMY_MAX_SOURCES; i++ )
    {
        if ( table[i].attempts > 0 && table[i].dt == dt )
            return &table[i];
    }

    for ( i = 0; i < DUMMY_MAX_SOURCES; i++ )
    {
        if ( table[i].attempts == 0 )
        {
            table[i].dt = dt;
            return &table[i];
        }
    }

    /* Full. The totals above are still right; this one is not
       itemised, which is the honest failure for a display. */
    return NULL;
}


static void dummy_tally( DUMMY_SOURCE_DATA *table, int dt, int dam )
{
    DUMMY_SOURCE_DATA *row = dummy_slot( table, dt );

    if ( row == NULL )
        return;

    row->attempts++;
    if ( dam <= 0 )
        return;

    row->hits++;
    row->damage += dam;
    if ( dam > row->best )
        row->best = dam;
}


static const char *dummy_dt_name( int dt )
{
    if ( dt >= 0 && dt < MAX_SKILL && skill_table[dt].name != NULL )
        return skill_table[dt].name;

    if ( dt >= TYPE_HIT && dt <= TYPE_HIT + MAX_DAMAGE_MESSAGE )
        return attack_table[dt - TYPE_HIT].name;

    return "unknown";
}


/*
 * Biggest first, because the first line is the answer to "what is
 * actually doing the work".  Selection sort over at most
 * DUMMY_MAX_SOURCES rows, which is cheaper than being clever.
 */
static void dummy_sort( DUMMY_SOURCE_DATA *table )
{
    int i, j, pick;
    DUMMY_SOURCE_DATA swap;

    for ( i = 0; i < DUMMY_MAX_SOURCES - 1; i++ )
    {
        pick = i;
        for ( j = i + 1; j < DUMMY_MAX_SOURCES; j++ )
        {
            if ( table[j].damage > table[pick].damage
            || ( table[j].damage == table[pick].damage
              && table[j].attempts > table[pick].attempts ) )
                pick = j;
        }
        if ( pick != i )
        {
            swap = table[i];
            table[i] = table[pick];
            table[pick] = swap;
        }
    }
}


/*
 * The itemised half of a report. Returns the number of rows drawn so
 * the caller knows whether to head it at all.
 */
static int dummy_itemise( CHAR_DATA *ch, DUMMY_SOURCE_DATA *table,
                          long total )
{
    char buf[MAX_STRING_LENGTH];
    int i, drawn = 0;

    dummy_sort( table );

    for ( i = 0; i < DUMMY_MAX_SOURCES; i++ )
    {
        DUMMY_SOURCE_DATA *row = &table[i];

        if ( row->attempts <= 0 )
            continue;

        snprintf( buf, sizeof(buf),
            "{0C|{00   %-18s {0F%7ld{00 %3ld%%  %4d of %-4d  avg %-5ld "
            "best %d\n\r",
            dummy_dt_name( row->dt ), row->damage,
            total > 0 ? row->damage * 100 / total : 0,
            row->hits, row->attempts,
            row->hits > 0 ? row->damage / row->hits : 0,
            row->best );
        send_to_char( buf, ch );
        drawn++;
    }

    return drawn;
}


/*
 * What a mobile of this level is typically worth in hit points,
 * averaged over every mobile in the world at that level.
 *
 * The alternative was to invent a number, and an invented number is
 * the one thing a training yard must not report: "you would kill
 * this in nine seconds" is only worth reading if the thing being
 * killed is a real measure of the world. Cached, because the walk is
 * over every prototype and the answer cannot change without a reboot.
 */
long dummy_typical_hp( int level )
{
    extern MOB_INDEX_DATA *mob_index_hash[MAX_KEY_HASH];
    static long cache[MAX_LEVEL + 1];
    static bool cached[MAX_LEVEL + 1];
    MOB_INDEX_DATA *proto;
    long total = 0;
    int count = 0;
    int bucket;

    level = URANGE( 0, level, MAX_LEVEL );

    if ( cached[level] )
        return cache[level];

    for ( bucket = 0; bucket < MAX_KEY_HASH; bucket++ )
    {
        for ( proto = mob_index_hash[bucket]; proto != NULL;
              proto = proto->next )
        {
            if ( proto->level != level )
                continue;
            total += (long)proto->hit[2]
                   + ( (long)proto->hit[0] * ( proto->hit[1] + 1 ) ) / 2;
            count++;
        }
    }

    /* Nothing in the world at that level: give the curve rather than
       a zero, and say nothing false. */
    cache[level] = count > 0 ? total / count : (long)level * 20 + 20;
    cached[level] = true;
    return cache[level];
}


bool is_training_dummy( CHAR_DATA *ch )
{
    return ch != NULL && IS_NPC(ch) && ch->pIndexData != NULL
        && ch->pIndexData->vnum == MOB_VNUM_TRAINING_DUMMY;
}


static CHAR_DATA *dummy_in_room( CHAR_DATA *ch )
{
    CHAR_DATA *rch;

    if ( ch == NULL || ch->in_room == NULL )
        return NULL;

    for ( rch = ch->in_room->people; rch != NULL; rch = rch->next_in_room )
        if ( is_training_dummy( rch ) )
            return rch;

    return NULL;
}


static void dummy_session_clear( CHAR_DATA *ch )
{
    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return;

    int i;

    ch->pcdata->dummy_dealt = 0;
    ch->pcdata->dummy_taken = 0;
    ch->pcdata->dummy_attempts = 0;
    ch->pcdata->dummy_worst = 0;
    for ( i = 0; i < 3; i++ )
    {
        ch->pcdata->dummy_dealt_from[i] = 0;
        ch->pcdata->dummy_taken_from[i] = 0;
    }
    for ( i = 0; i < 4; i++ )
    {
        ch->pcdata->dummy_avoided[i] = 0;
        ch->pcdata->dummy_evaded[i] = 0;
    }
    memset( ch->pcdata->dummy_out, 0, sizeof(ch->pcdata->dummy_out) );
    memset( ch->pcdata->dummy_in, 0, sizeof(ch->pcdata->dummy_in) );
    ch->pcdata->dummy_hits = 0;
    ch->pcdata->dummy_misses = 0;
    ch->pcdata->dummy_struck = 0;
    ch->pcdata->dummy_swings = 0;
    ch->pcdata->dummy_best = 0;
    ch->pcdata->dummy_started = 0;
    ch->pcdata->dummy_level = 0;
}


/*
 * Both halves of every blow in the yard come through here, from the
 * one place in damage() that would otherwise subtract hit points.
 */
/*
 * The one place a player's half of a training fight is started, so
 * that the clock and the level are agreed between every counter.
 */
static PC_DATA *dummy_session( CHAR_DATA *ch, CHAR_DATA *victim )
{
    CHAR_DATA *player;
    CHAR_DATA *target;

    if ( ch == NULL || victim == NULL || ch == victim )
        return NULL;

    if ( !is_training_dummy( ch ) && !is_training_dummy( victim ) )
        return NULL;

    player = is_training_dummy( victim ) ? ch : victim;
    target = is_training_dummy( victim ) ? victim : ch;

    if ( IS_NPC(player) || player->pcdata == NULL )
        return NULL;

    /* The clock starts at the first blow either way, so a player who
       spends a minute choosing a weapon is not charged for the pause. */
    if ( player->pcdata->dummy_started == 0 )
    {
        player->pcdata->dummy_started = current_time;
        player->pcdata->dummy_level = target->level;
    }

    return player->pcdata;
}


void dummy_record( CHAR_DATA *ch, CHAR_DATA *victim, int dam, int dt )
{
    PC_DATA *pc = dummy_session( ch, victim );
    int from;

    if ( pc == NULL )
        return;

    from = dummy_source( dt );

    if ( is_training_dummy( victim ) )
    {
        pc->dummy_swings++;
        dummy_tally( pc->dummy_out, dt, dam );
        if ( dam > 0 )
        {
            pc->dummy_hits++;
            pc->dummy_dealt += dam;
            pc->dummy_dealt_from[from] += dam;
            if ( dam > pc->dummy_best )
                pc->dummy_best = dam;
        }
        else
        {
            pc->dummy_misses++;
        }
        return;
    }

    pc->dummy_attempts++;
    dummy_tally( pc->dummy_in, dt, dam );
    if ( dam > 0 )
    {
        pc->dummy_taken += dam;
        pc->dummy_taken_from[from] += dam;
        pc->dummy_struck++;
        if ( dam > pc->dummy_worst )
            pc->dummy_worst = dam;
    }
}


/*
 * A blow turned aside returns out of damage() above the subtraction
 * the yard hooks, so without this the report could not tell a parry
 * from a swing that never happened -- which is most of what somebody
 * comparing two shields wants to know.
 */
void dummy_defended( CHAR_DATA *ch, CHAR_DATA *victim, int dt, int how )
{
    PC_DATA *pc = dummy_session( ch, victim );

    if ( pc == NULL || how < 0 || how >= 4 )
        return;

    if ( is_training_dummy( victim ) )
    {
        /* It turned your blow aside: still one of your swings, and
           still an attempt by whatever you swung. */
        pc->dummy_swings++;
        pc->dummy_evaded[how]++;
        dummy_tally( pc->dummy_out, dt, 0 );
    }
    else
    {
        pc->dummy_attempts++;
        pc->dummy_avoided[how]++;
        dummy_tally( pc->dummy_in, dt, 0 );
    }
}



/*
 * Nothing dies in the yard, and nothing leaves hurt either.
 *
 * The dummy absorbs everything. The player is floored at a single hit
 * point rather than made invulnerable, because the floor is the
 * lesson: a brutal dummy that puts you on 1 and holds you there has
 * told you something that one which cannot touch you has not.
 */
bool dummy_absorb( CHAR_DATA *ch, CHAR_DATA *victim, int dam, int dt )
{
    if ( is_training_dummy( victim ) )
    {
        dummy_record( ch, victim, dam, dt );
        return true;
    }

    if ( is_training_dummy( ch ) && !IS_NPC(victim) )
    {
        dummy_record( ch, victim, dam, dt );
        victim->hit -= dam;
        if ( victim->hit < 1 )
            victim->hit = 1;
        return true;
    }

    return false;
}


static void dummy_configure( CHAR_DATA *dummy, int level, int shape,
                             int attack )
{
    const DUMMY_SHAPE *form = &dummy_shape_table[shape];
    long blow;
    int i;

    dummy_shape = shape;
    dummy_attack = attack;

    dummy->level = (sh_int)level;
    dummy->max_hit = (int)dummy_typical_hp( level );
    dummy->hit = dummy->max_hit;
    dummy->hitroll = (sh_int)( level / 4 + form->hitroll );
    dummy->dam_type = (sh_int)dummy_attack_table[attack].attack;

    for ( i = 0; i < 4; i++ )
        dummy->armor[i] = (sh_int)form->ac;

    /* A level-typical blow, scaled by the shape: the dummy should
       read like something of its level, not like a boss. */
    blow = ( (long)level * 2 + 6 ) * form->damage_scale / 100;
    dummy->damage[0] = (sh_int)UMAX( 1, blow / 6 );
    dummy->damage[1] = 6;
    dummy->damage[2] = (sh_int)UMAX( 0, blow / 3 );
    dummy->damroll = (sh_int)( level / 5 );

    dummy->off_flags = form->off_flags;

    if ( dummy_hasted )
        SET_BIT( dummy->affected_by, AFF_HASTE );
    else
        REMOVE_BIT( dummy->affected_by, AFF_HASTE );

    /* The spec is what casts; it is assigned here rather than in the
       area file so that an area reset cannot quietly take it away. */
    dummy->spec_fun = spec_lookup( "spec_training_dummy" );
}


/*
 * It casts what it was told to, once per mobile pulse while it is
 * fighting.  Deliberately not a random spellbook: a reading you
 * cannot reproduce is not a measurement.
 */
bool spec_training_dummy( CHAR_DATA *mob, CHAR_DATA *ch, DO_FUN *cmd,
                          char *arg )
{
    CHAR_DATA *victim;
    int sn;

    UNUSED_PARAM( ch );
    UNUSED_PARAM( arg );

    if ( cmd != NULL || mob->position != POS_FIGHTING )
        return false;

    if ( dummy_spell == DUMMY_SPELL_NONE )
        return false;

    if ( ( victim = mob->fighting ) == NULL || IS_NPC(victim) )
        return false;

    sn = skill_lookup( dummy_spell_table[dummy_spell].spell );
    if ( sn < 0 || skill_table[sn].spell_fun == spell_null )
        return false;

    (*skill_table[sn].spell_fun) ( sn, mob->level, mob, victim );
    return true;
}


static void dummy_menu( CHAR_DATA *ch, CHAR_DATA *dummy )
{
    char buf[MAX_STRING_LENGTH];
    int i;

    send_to_char(
        "\n\r{0C.-[ The training dummy ]----------------------------------------.{00\n\r",
        ch );

    snprintf( buf, sizeof(buf),
        "{0C|{00 Level   {0F%-4d{00  worth %ld hit points, a level %d mobile's average\n\r",
        dummy->level, (long)dummy->max_hit, dummy->level );
    send_to_char( buf, ch );

    snprintf( buf, sizeof(buf),
        "{0C|{00 Shape   {0F%-8s{00  %s\n\r",
        dummy_shape_table[dummy_shape].name,
        dummy_shape_table[dummy_shape].blurb );
    send_to_char( buf, ch );

    snprintf( buf, sizeof(buf),
        "{0C|{00 Hits in {0F%-8s{00  %s\n\r",
        dummy_attack_table[dummy_attack].name,
        dummy_attack_table[dummy_attack].blurb );
    send_to_char( buf, ch );

    snprintf( buf, sizeof(buf),
        "{0C|{00 Casts   {0F%-8s{00  %s\n\r",
        dummy_spell_table[dummy_spell].name,
        dummy_spell_table[dummy_spell].blurb );
    send_to_char( buf, ch );

    snprintf( buf, sizeof(buf),
        "{0C|{00 Haste   {0F%-8s{00  %s\n\r",
        dummy_hasted ? "on" : "off",
        dummy_hasted ? "an extra attack each round"
                     : "one attack each round" );
    send_to_char( buf, ch );

    send_to_char(
        "{0C'----------------------------------------------------------------'{00\n\r",
        ch );

    send_to_char(
        "\n\r  dummy <level>        any level; it starts at your own\n\r"
        "  dummy shape <name>   soft, armored, evasive, brutal\n\r"
        "  dummy hits <type>    what it attacks you with\n\r"
        "  dummy magic <kind>   what it casts at you, or none\n\r"
        "  dummy haste          an extra attack a round, on or off\n\r"
        "  dummy reset          your level, the defaults, numbers cleared\n\r"
        "  dummy report         stop, heal you both, and read the numbers\n\r"
        "\n\r  Then just KILL DUMMY.  Neither of you can die here.\n\r\n\r",
        ch );

    send_to_char( "  Damage types: ", ch );
    for ( i = 0; dummy_attack_table[i].name != NULL; i++ )
    {
        snprintf( buf, sizeof(buf), "%s%s",
                  i > 0 ? ", " : "", dummy_attack_table[i].name );
        send_to_char( buf, ch );
    }
    send_to_char( "\n\r  Spells:       ", ch );
    for ( i = 0; dummy_spell_table[i].name != NULL; i++ )
    {
        snprintf( buf, sizeof(buf), "%s%s",
                  i > 0 ? ", " : "", dummy_spell_table[i].name );
        send_to_char( buf, ch );
    }
    send_to_char( "\n\r", ch );
}


static void dummy_verdict( CHAR_DATA *ch, long dealt, int seconds, int level )
{
    char buf[MAX_STRING_LENGTH];
    long typical;
    long dps;
    long ttk;

    if ( seconds < 1 )
        seconds = 1;

    dps = dealt / seconds;
    typical = dummy_typical_hp( level );

    if ( dps < 1 )
    {
        send_to_char( "You did not land enough to measure.\n\r", ch );
        return;
    }

    ttk = typical / dps;

    snprintf( buf, sizeof(buf),
        "A level %d mobile averages %ld hit points, so at this rate you\n\r"
        "would drop one in {0F%ld{00 second%s.  ",
        level, typical, ttk, ttk == 1 ? "" : "s" );
    send_to_char( buf, ch );

    /* Banded on time to kill rather than raw damage: so many hit
       points a second means nothing without something to spend it on. */
    if ( ttk <= 5 )
        send_to_char( "That is devastating.\n\r", ch );
    else if ( ttk <= 15 )
        send_to_char( "That is strong.\n\r", ch );
    else if ( ttk <= 30 )
        send_to_char( "That is solid.\n\r", ch );
    else if ( ttk <= 60 )
        send_to_char( "That is slow going.\n\r", ch );
    else
        send_to_char( "You will struggle with anything of that level.\n\r",
                      ch );
}


/*
 * Everything back as it was, both ways, and the run's numbers wiped.
 * Shared by REPORT and RESET: the only difference between those two
 * is whether you get to read the figures before they go.
 */
static void dummy_stand_down( CHAR_DATA *ch, CHAR_DATA *dummy )
{
    if ( ch->fighting != NULL )
        stop_fighting( ch, true );

    if ( dummy != NULL )
    {
        if ( dummy->fighting != NULL )
            stop_fighting( dummy, true );

        /*
         * An attacked mobile remembers who hit it, and one that hates
         * you sets about you again the moment the fight stops --
         * which is right for everything else in the world and wrong
         * for this. Stopping the fight alone left the dummy swinging
         * the instant the report printed.
         */
        remove_all_hates( dummy );
        if ( dummy->hunting != NULL )
            do_stop_hunting( dummy, dummy->hunting->name );

        dummy->hit = dummy->max_hit;
        dummy->position = POS_STANDING;
        act( "$n straightens up, good as new.", dummy, NULL, NULL, TO_ROOM );
    }

    ch->hit = ch->max_hit;
    ch->mana = ch->max_mana;
    ch->move = ch->max_move;
    if ( ch->position == POS_FIGHTING )
        ch->position = POS_STANDING;

    dummy_session_clear( ch );
}


static void dummy_report( CHAR_DATA *ch, CHAR_DATA *dummy )
{
    char buf[MAX_STRING_LENGTH];
    PC_DATA *pc = ch->pcdata;
    int seconds;
    int swings, attempts;
    int i, shown;
    long dealt, taken;

    if ( pc->dummy_started == 0 )
    {
        send_to_char( "You have not hit anything yet.\n\r", ch );
        return;
    }

    seconds = (int)( current_time - pc->dummy_started );
    if ( seconds < 1 )
        seconds = 1;

    dealt    = pc->dummy_dealt;
    taken    = pc->dummy_taken;
    swings   = pc->dummy_swings;
    attempts = pc->dummy_attempts;

    send_to_char(
        "\n\r{0C.-[ Training report ]-------------------------------------------.{00\n\r",
        ch );

    snprintf( buf, sizeof(buf),
        "{0C|{00 A level %d %s dummy, hitting in %s%s%s,\n\r"
        "{0C|{00 over %d second%s.\n\r",
        pc->dummy_level, dummy_shape_table[dummy_shape].name,
        dummy_attack_table[dummy_attack].name,
        dummy_spell == DUMMY_SPELL_NONE ? "" : ", casting ",
        dummy_spell == DUMMY_SPELL_NONE
            ? ( dummy_hasted ? ", hasted" : "" )
            : dummy_spell_table[dummy_spell].name,
        seconds, seconds == 1 ? "" : "s" );
    send_to_char( buf, ch );

    /* ------------------------------------------------ your offence */
    send_to_char(
        "{0C|{00\n\r{0C|{00 {0EWHAT YOU DID{00\n\r", ch );

    snprintf( buf, sizeof(buf),
        "{0C|{00   total {0F%-8ld{00 per second {0F%-6ld{00 per swing {0F%ld{00\n\r",
        dealt, dealt / seconds,
        swings > 0 ? dealt / swings : 0 );
    send_to_char( buf, ch );

    if ( swings > 0 )
    {
        snprintf( buf, sizeof(buf),
            "{0C|{00   landed {0F%d{00 of {0F%d{00 (%d%%)   best {0F%d{00   "
            "average landed {0F%ld{00\n\r",
            pc->dummy_hits, swings, pc->dummy_hits * 100 / swings,
            pc->dummy_best,
            pc->dummy_hits > 0 ? dealt / pc->dummy_hits : 0 );
        send_to_char( buf, ch );

        snprintf( buf, sizeof(buf),
            "{0C|{00   missed {0F%d{00   turned aside by it {0F%d{00\n\r",
            pc->dummy_misses,
            pc->dummy_evaded[0] + pc->dummy_evaded[1]
          + pc->dummy_evaded[2] + pc->dummy_evaded[3] );
        send_to_char( buf, ch );
    }

    /* Where it came from. Only the columns that did something: a row
       of zeroes is three lines of nothing to read past. */
    if ( dealt > 0 )
    {
        shown = 0;
        send_to_char( "{0C|{00   from ", ch );
        for ( i = 0; i < 3; i++ )
        {
            if ( pc->dummy_dealt_from[i] <= 0 )
                continue;
            snprintf( buf, sizeof(buf), "%s{0F%s{00 %ld (%ld%%)",
                      shown++ > 0 ? "   " : "",
                      dummy_source_name[i], pc->dummy_dealt_from[i],
                      pc->dummy_dealt_from[i] * 100 / dealt );
            send_to_char( buf, ch );
        }
        send_to_char( "\n\r", ch );
    }

    /* And the same thing attack by attack, which is the resolution
       somebody choosing between two spellbooks needs. */
    if ( pc->dummy_out[0].attempts > 0 )
    {
        send_to_char( "{0C|{00   {0Eattack by attack{00\n\r", ch );
        dummy_itemise( ch, pc->dummy_out, dealt );
    }

    /* ------------------------------------------------ your defence */
    send_to_char(
        "{0C|{00\n\r{0C|{00 {0EWHAT IT DID TO YOU{00\n\r", ch );

    snprintf( buf, sizeof(buf),
        "{0C|{00   total {0F%-8ld{00 per second {0F%-6ld{00 in {0F%d{00 "
        "landed blow%s\n\r",
        taken, taken / seconds, pc->dummy_struck,
        pc->dummy_struck == 1 ? "" : "s" );
    send_to_char( buf, ch );

    if ( pc->dummy_struck > 0 )
    {
        snprintf( buf, sizeof(buf),
            "{0C|{00   worst {0F%d{00   average landed {0F%ld{00\n\r",
            pc->dummy_worst, taken / pc->dummy_struck );
        send_to_char( buf, ch );
    }

    if ( attempts > 0 )
    {
        int avoided = pc->dummy_avoided[0] + pc->dummy_avoided[1]
                    + pc->dummy_avoided[2] + pc->dummy_avoided[3];

        snprintf( buf, sizeof(buf),
            "{0C|{00   it tried {0F%d{00 time%s; you stopped {0F%d{00 "
            "of them (%d%%)\n\r",
            attempts, attempts == 1 ? "" : "s", avoided,
            avoided * 100 / attempts );
        send_to_char( buf, ch );

        if ( avoided > 0 )
        {
            shown = 0;
            send_to_char( "{0C|{00     ", ch );
            for ( i = 0; i < 4; i++ )
            {
                if ( pc->dummy_avoided[i] <= 0 )
                    continue;
                snprintf( buf, sizeof(buf), "%s{0F%s{00 %d (%d%%)",
                          shown++ > 0 ? "   " : "",
                          dummy_avoid_name[i], pc->dummy_avoided[i],
                          pc->dummy_avoided[i] * 100 / attempts );
                send_to_char( buf, ch );
            }
            send_to_char( "\n\r", ch );
        }
    }

    if ( taken > 0 )
    {
        shown = 0;
        send_to_char( "{0C|{00   from ", ch );
        for ( i = 0; i < 3; i++ )
        {
            if ( pc->dummy_taken_from[i] <= 0 )
                continue;
            snprintf( buf, sizeof(buf), "%s{0F%s{00 %ld (%ld%%)",
                      shown++ > 0 ? "   " : "",
                      dummy_source_name[i], pc->dummy_taken_from[i],
                      pc->dummy_taken_from[i] * 100 / taken );
            send_to_char( buf, ch );
        }
        send_to_char( "\n\r", ch );
    }

    if ( pc->dummy_in[0].attempts > 0 )
    {
        send_to_char( "{0C|{00   {0Eattack by attack{00\n\r", ch );
        dummy_itemise( ch, pc->dummy_in, taken );
    }

    if ( taken > 0 && ch->max_hit > 0 )
    {
        long survive = ( (long)ch->max_hit * seconds ) / UMAX( 1, taken );

        snprintf( buf, sizeof(buf),
            "{0C|{00   it would take you from full in {0F%ld{00 second%s\n\r",
            survive, survive == 1 ? "" : "s" );
        send_to_char( buf, ch );
    }

    send_to_char(
        "{0C'----------------------------------------------------------------'{00\n\r",
        ch );

    dummy_verdict( ch, dealt, seconds, pc->dummy_level );

    dummy_stand_down( ch, dummy );
    send_to_char( "You are patched up and rested.\n\r", ch );
}


void do_dummy( CHAR_DATA *ch, char *argument )
{
    char arg1[MAX_INPUT_LENGTH];
    char arg2[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    CHAR_DATA *dummy;
    bool is_reset;
    int i;

    if ( IS_NPC(ch) || ch->pcdata == NULL )
        return;

    argument = one_argument( argument, arg1 );
    one_argument( argument, arg2 );

    /* "re" is a prefix of both RESET and REPORT, and report is tested
       first, so reset needs enough letters to tell them apart. */
    is_reset = ( strlen( arg1 ) >= 3 && !str_prefix( arg1, "reset" ) );

    dummy = dummy_in_room( ch );

    if ( !str_prefix( arg1, "report" ) && arg1[0] != '\0' )
    {
        dummy_report( ch, dummy );
        return;
    }

    if ( dummy == NULL )
    {
        send_to_char(
            "There is no training dummy here.  The yard is through the\n\r"
            "practice ring, in the southwestern corner of Oak Tree Square.\n\r",
            ch );
        return;
    }

    /*
     * Changing it mid-run would make the numbers a blend of two
     * different opponents, which is worse than no numbers at all.
     */
    if ( arg1[0] != '\0' && !is_reset && ch->pcdata->dummy_started != 0 )
    {
        send_to_char(
            "You are in the middle of a run.  DUMMY REPORT first -- a\n\r"
            "reading means nothing if the thing you were hitting changed\n\r"
            "half way through.\n\r", ch );
        return;
    }

    if ( arg1[0] == '\0' )
    {
        /* Nobody has set it up, or it has reset: it is your size.
           That is the comparison almost everybody actually wants --
           but only until somebody says otherwise, or the menu would
           undo the level they just chose. */
        if ( !dummy_level_chosen && dummy->level != ch->level
        &&   ch->pcdata->dummy_started == 0 )
            dummy_configure( dummy, ch->level, dummy_shape, dummy_attack );
        dummy_menu( ch, dummy );
        return;
    }

    if ( is_reset )
    {
        bool had_run = ( ch->pcdata->dummy_started != 0 );

        /* The stance going back to default and the numbers staying
           up is half a reset, and the half it leaves is the half
           that makes the next reading wrong. */
        dummy_stand_down( ch, dummy );
        dummy_spell = DUMMY_SPELL_NONE;
        dummy_hasted = false;
        dummy_level_chosen = false;
        dummy_configure( dummy, UMAX( 1, ch->level ),
                         DUMMY_SHAPE_DEFAULT, DUMMY_ATTACK_DEFAULT );
        snprintf( buf, sizeof(buf),
            "Back to a level %d %s dummy, hitting in %s.%s\n\r",
            dummy->level, dummy_shape_table[DUMMY_SHAPE_DEFAULT].name,
            dummy_attack_table[DUMMY_ATTACK_DEFAULT].name,
            had_run ? "  The run so far is discarded." : "" );
        send_to_char( buf, ch );
        return;
    }

    if ( !str_prefix( arg1, "shape" ) )
    {
        for ( i = 0; dummy_shape_table[i].name != NULL; i++ )
        {
            if ( !str_prefix( arg2, dummy_shape_table[i].name ) )
            {
                dummy_configure( dummy, dummy->level, i, dummy_attack );
                snprintf( buf, sizeof(buf),
                    "The dummy settles into a %s stance: %s.\n\r",
                    dummy_shape_table[i].name, dummy_shape_table[i].blurb );
                send_to_char( buf, ch );
                act( "$n adjusts the training dummy.", ch, NULL, NULL,
                     TO_ROOM );
                return;
            }
        }
        send_to_char( "No shape by that name.  Try soft, armored, "
                      "evasive or brutal.\n\r", ch );
        return;
    }

    if ( !str_prefix( arg1, "magic" ) || !str_prefix( arg1, "casts" )
    ||   !str_prefix( arg1, "spell" ) )
    {
        for ( i = 0; dummy_spell_table[i].name != NULL; i++ )
        {
            if ( arg2[0] == '\0'
            ||   str_prefix( arg2, dummy_spell_table[i].name ) )
                continue;

            dummy_spell = i;
            dummy_configure( dummy, dummy->level, dummy_shape,
                             dummy_attack );
            if ( i == DUMMY_SPELL_NONE )
                send_to_char( "It puts its hands down.  Weapon damage "
                              "only.\n\r", ch );
            else
            {
                snprintf( buf, sizeof(buf),
                    "It will cast %s at you -- %s.\n\r",
                    dummy_spell_table[i].spell,
                    dummy_spell_table[i].blurb );
                send_to_char( buf, ch );
            }
            return;
        }
        send_to_char( "It does not know that one.  DUMMY lists what it "
                      "can cast.\n\r", ch );
        return;
    }

    if ( !str_prefix( arg1, "haste" ) )
    {
        if ( arg2[0] == '\0' )
            dummy_hasted = !dummy_hasted;
        else
            dummy_hasted = ( !str_cmp( arg2, "on" )
                          || !str_cmp( arg2, "yes" ) );

        dummy_configure( dummy, dummy->level, dummy_shape, dummy_attack );
        send_to_char( dummy_hasted
            ? "It blurs, and comes at you twice as often.\n\r"
            : "It slows back to one attack a round.\n\r", ch );
        return;
    }

    if ( !str_prefix( arg1, "hits" ) || !str_prefix( arg1, "damage" ) )
    {
        for ( i = 0; dummy_attack_table[i].name != NULL; i++ )
        {
            if ( !str_prefix( arg2, dummy_attack_table[i].name ) )
            {
                dummy_configure( dummy, dummy->level, dummy_shape, i );
                snprintf( buf, sizeof(buf),
                    "It will come at you with %s -- %s.\n\r",
                    dummy_attack_table[i].name,
                    dummy_attack_table[i].blurb );
                send_to_char( buf, ch );
                return;
            }
        }
        send_to_char( "It cannot hit you with that.  DUMMY lists what "
                      "it can.\n\r", ch );
        return;
    }

    if ( is_number( arg1 ) )
    {
        int level = atoi( arg1 );

        if ( level < 1 || level > MAX_LEVEL )
        {
            snprintf( buf, sizeof(buf),
                      "Pick a level between 1 and %d.\n\r", MAX_LEVEL );
            send_to_char( buf, ch );
            return;
        }

        dummy_level_chosen = true;
        dummy_configure( dummy, level, dummy_shape, dummy_attack );
        snprintf( buf, sizeof(buf),
            "The dummy is now level %d, and worth %ld hit points -- what a\n\r"
            "level %d mobile averages.\n\r",
            level, (long)dummy->max_hit, level );
        send_to_char( buf, ch );
        act( "$n adjusts the training dummy.", ch, NULL, NULL, TO_ROOM );
        return;
    }

    dummy_menu( ch, dummy );
}


/*
 * You get into the yard by entering the practice ring, so you should
 * get out of it the same way round.  Walking north still works; this
 * is the command the way in leads you to expect.
 */
void do_leave( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    ROOM_INDEX_DATA *back;

    one_argument( argument, arg );

    if ( ch->in_room == NULL
    ||   ch->in_room->vnum != ROOM_VNUM_TRAINING_YARD )
    {
        send_to_char( "There is nothing here to leave.  EXITS lists the "
                      "ways out.\n\r", ch );
        return;
    }

    /*
     * LEAVE RING is the signposted form and the one the room tells
     * you.  A bare LEAVE works because there is only one thing here
     * to leave, but an argument that names something else is a typo
     * worth saying so about rather than silently obeying.
     */
    if ( arg[0] != '\0'
    &&   str_prefix( arg, "ring" ) && str_prefix( arg, "yard" )
    &&   str_prefix( arg, "practice" ) )
    {
        send_to_char( "Leave what?  The practice ring is the way out.\n\r",
                      ch );
        return;
    }

    if ( ( back = get_room_index( ROOM_VNUM_OAK_SQUARE ) ) == NULL )
    {
        send_to_char( "The practice ring will not open.\n\r", ch );
        return;
    }

    /* Walking out mid-run would throw away the only reason to have
       been in here, so take the reading on the way past. */
    if ( !IS_NPC(ch) && ch->pcdata != NULL && ch->pcdata->dummy_started != 0 )
        dummy_report( ch, dummy_in_room( ch ) );

    act( "$n ducks back out through the practice ring.", ch, NULL, NULL,
         TO_ROOM );
    char_from_room( ch );
    char_to_room( ch, back );
    act( "$n steps out of the practice ring.", ch, NULL, NULL, TO_ROOM );
    do_look( ch, "auto" );
}

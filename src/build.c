/***************************************************************************
 * In-game building: editing mobile prototypes in words.                    *
 *                                                                          *
 * SET MOB <vnum> <field> <value> changes a mobile prototype in an area     *
 * made with ANEW, taking names rather than numbers: "race dwarf", "sex     *
 * female", "act +aggressive -sentinel", "hp 4d10+80". MSHOW <vnum> reads a *
 * prototype back in the same words, so what it prints is what SET takes.  *
 *                                                                          *
 * Two rules hold everything here to what the next boot will load:         *
 *                                                                          *
 *  - load_mobiles adjusts some fields as it reads them (a race's natural   *
 *    flags are ORed in; hitroll, damage bonus and armour are clamped to    *
 *    the level). Each edit applies the same adjustment at once and says    *
 *    so, rather than show a value a reboot would quietly change.           *
 *  - A prototype string is made with str_perm, never str_dup: instances    *
 *    share their prototype's strings by pointer, and extracting one frees  *
 *    anything outside string_space (see str_perm in db.c).                 *
 *                                                                          *
 * Only a prototype in an ANEW area's range can be edited: that range is    *
 * what ASAVE writes, so an edit anywhere else could never be kept.         *
 ***************************************************************************/

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "merc.h"
#include "interp.h"

/* db.c's counts of what has been allocated, kept honest for MEMORY. */
extern int top_affect;
extern int top_ed;
extern AREA_DATA *area_first;

struct build_flag
{
    const char *name;
    long        bit;
};

/* Shops (at the end of the file, after the object tables they name). */
static void shop_words( SHOP_DATA *s, char *out, size_t size );
static bool mob_shop_edit( CHAR_DATA *ch, MOB_INDEX_DATA *m, char *value );

/* The names are the ones MSHOW prints and SET accepts, one word each. */
static const struct build_flag act_names[] =
{
    { "sentinel",      ACT_SENTINEL      },
    { "scavenger",     ACT_SCAVENGER     },
    { "healer",        ACT_IS_HEALER     },
    { "skill_train",   ACT_GAIN          },
    { "aggressive",    ACT_AGGRESSIVE    },
    { "stay_area",     ACT_STAY_AREA     },
    { "wimpy",         ACT_WIMPY         },
    { "pet",           ACT_PET           },
    { "train",         ACT_TRAIN         },
    { "practice",      ACT_PRACTICE      },
    { "update_always", ACT_UPDATE_ALWAYS },
    { "no_shove",      ACT_NOSHOVE       },
    { "undead",        ACT_UNDEAD        },
    { "cleric",        ACT_CLERIC        },
    { "mage",          ACT_MAGE          },
    { "thief",         ACT_THIEF         },
    { "warrior",       ACT_WARRIOR       },
    { "no_align",      ACT_NOALIGN       },
    { "no_purge",      ACT_NOPURGE       },
    { "mountable",     ACT_MOUNTABLE     },
    { "no_kill",       ACT_NOKILL        },
    { "questmaster",   ACT_QUESTM        },
    { NULL, 0 }
};

static const struct build_flag act2_names[] =
{
    { "no_teleport",   ACT2_NO_TPORT     },
    { "repairer",      ACT2_REPAIR       },
    { NULL, 0 }
};

static const struct build_flag affect_names[] =
{
    { "blind",         AFF_BLIND         },
    { "invisible",     AFF_INVISIBLE     },
    { "detect_evil",   AFF_DETECT_EVIL   },
    { "detect_invis",  AFF_DETECT_INVIS  },
    { "detect_magic",  AFF_DETECT_MAGIC  },
    { "detect_hidden", AFF_DETECT_HIDDEN },
    { "berserk",       AFF_BERSERK       },
    { "sanctuary",     AFF_SANCTUARY     },
    { "faerie_fire",   AFF_FAERIE_FIRE   },
    { "infrared",      AFF_INFRARED      },
    { "curse",         AFF_CURSE         },
    { "swim",          AFF_SWIM          },
    { "poison",        AFF_POISON        },
    { "protect",       AFF_PROTECT       },
    { "regeneration",  AFF_REGENERATION  },
    { "sneak",         AFF_SNEAK         },
    { "hide",          AFF_HIDE          },
    { "sleep",         AFF_SLEEP         },
    { "charm",         AFF_CHARM         },
    { "flying",        AFF_FLYING        },
    { "pass_door",     AFF_PASS_DOOR     },
    { "haste",         AFF_HASTE         },
    { "calm",          AFF_CALM          },
    { "plague",        AFF_PLAGUE        },
    { "weaken",        AFF_WEAKEN        },
    { NULL, 0 }
};

static const struct build_flag affect2_names[] =
{
    { "dark_vision",   AFF2_DARK_VISION  },
    { "detect_good",   AFF2_DETECT_GOOD  },
    { "hold",          AFF2_HOLD         },
    { "hot_flames",    AFF2_FLAMING_HOT  },
    { "cold_flames",   AFF2_FLAMING_COLD },
    { "paralysis",     AFF2_PARALYSIS    },
    { "stealth",       AFF2_STEALTH      },
    { "stunned",       AFF2_STUNNED      },
    { "sleepless",     AFF2_NO_RECOVER   },
    { "force_sword",   AFF2_FORCE_SWORD  },
    { "ghostly",       AFF2_GHOST        },
    { "madness",       AFF2_MADNESS      },
    { "divine_protection", AFF2_DIVINE_PROT },
    { "shadowmeld",    AFF2_SHADOWMELD   },
    { NULL, 0 }
};

static const struct build_flag off_names[] =
{
    { "area_attack",   OFF_AREA_ATTACK   },
    { "backstab",      OFF_BACKSTAB      },
    { "bash",          OFF_BASH          },
    { "berserk",       OFF_BERSERK       },
    { "disarm",        OFF_DISARM        },
    { "dodge",         OFF_DODGE         },
    { "fade",          OFF_FADE          },
    { "fast",          OFF_FAST          },
    { "kick",          OFF_KICK          },
    { "kick_dirt",     OFF_KICK_DIRT     },
    { "parry",         OFF_PARRY         },
    { "rescue",        OFF_RESCUE        },
    { "tail",          OFF_TAIL          },
    { "trip",          OFF_TRIP          },
    { "crush",         OFF_CRUSH         },
    { "assist_all",    ASSIST_ALL        },
    { "assist_align",  ASSIST_ALIGN      },
    { "assist_race",   ASSIST_RACE       },
    { "assist_players", ASSIST_PLAYERS   },
    { "assist_guard",  ASSIST_GUARD      },
    { "assist_vnum",   ASSIST_VNUM       },
    { "summoner",      OFF_SUMMONER      },
    { "needs_master",  NEEDS_MASTER      },
    { "attack_opener", OFF_ATTACK_DOOR_OPENER },
    { NULL, 0 }
};

static const struct build_flag off2_names[] =
{
    { "hunter",        OFF2_HUNTER       },
    { NULL, 0 }
};

/* Immunities, resistances and vulnerabilities share their names. */
static const struct build_flag imm_names[] =
{
    { "summon",    IMM_SUMMON    }, { "charm",     IMM_CHARM     },
    { "magic",     IMM_MAGIC     }, { "weapon",    IMM_WEAPON    },
    { "bash",      IMM_BASH      }, { "pierce",    IMM_PIERCE    },
    { "slash",     IMM_SLASH     }, { "fire",      IMM_FIRE      },
    { "cold",      IMM_COLD      }, { "lightning", IMM_LIGHTNING },
    { "acid",      IMM_ACID      }, { "poison",    IMM_POISON    },
    { "negative",  IMM_NEGATIVE  }, { "holy",      IMM_HOLY      },
    { "energy",    IMM_ENERGY    }, { "mental",    IMM_MENTAL    },
    { "disease",   IMM_DISEASE   }, { "drowning",  IMM_DROWNING  },
    { "light",     IMM_LIGHT     }, { "wind",      IMM_WIND      },
    { NULL, 0 }
};

static const struct build_flag res_names[] =
{
    { "charm",     RES_CHARM     }, { "magic",     RES_MAGIC     },
    { "weapon",    RES_WEAPON    }, { "bash",      RES_BASH      },
    { "pierce",    RES_PIERCE    }, { "slash",     RES_SLASH     },
    { "fire",      RES_FIRE      }, { "cold",      RES_COLD      },
    { "lightning", RES_LIGHTNING }, { "acid",      RES_ACID      },
    { "poison",    RES_POISON    }, { "negative",  RES_NEGATIVE  },
    { "holy",      RES_HOLY      }, { "energy",    RES_ENERGY    },
    { "mental",    RES_MENTAL    }, { "disease",   RES_DISEASE   },
    { "drowning",  RES_DROWNING  }, { "light",     RES_LIGHT     },
    { "wind",      RES_WIND      },
    { NULL, 0 }
};

static const struct build_flag vuln_names[] =
{
    { "magic",     VULN_MAGIC     }, { "weapon",    VULN_WEAPON    },
    { "bash",      VULN_BASH      }, { "pierce",    VULN_PIERCE    },
    { "slash",     VULN_SLASH     }, { "fire",      VULN_FIRE      },
    { "cold",      VULN_COLD      }, { "lightning", VULN_LIGHTNING },
    { "acid",      VULN_ACID      }, { "poison",    VULN_POISON    },
    { "negative",  VULN_NEGATIVE  }, { "holy",      VULN_HOLY      },
    { "energy",    VULN_ENERGY    }, { "mental",    VULN_MENTAL    },
    { "disease",   VULN_DISEASE   }, { "drowning",  VULN_DROWNING  },
    { "light",     VULN_LIGHT     }, { "wind",      VULN_WIND      },
    { "iron",      VULN_IRON      }, { "wood",      VULN_WOOD      },
    { "silver",    VULN_SILVER    },
    { NULL, 0 }
};

static const struct build_flag form_names[] =
{
    { "edible",    FORM_EDIBLE    }, { "poisonous", FORM_POISON    },
    { "magical",   FORM_MAGICAL   }, { "instant_rot", FORM_INSTANT_DECAY },
    { "other",     FORM_OTHER     }, { "animal",    FORM_ANIMAL    },
    { "sentient",  FORM_SENTIENT  }, { "undead",    FORM_UNDEAD    },
    { "construct", FORM_CONSTRUCT }, { "mist",      FORM_MIST      },
    { "intangible", FORM_INTANGIBLE }, { "biped",   FORM_BIPED     },
    { "centaur",   FORM_CENTAUR   }, { "insect",    FORM_INSECT    },
    { "spider",    FORM_SPIDER    }, { "crustacean", FORM_CRUSTACEAN },
    { "worm",      FORM_WORM      }, { "blob",      FORM_BLOB      },
    { "mammal",    FORM_MAMMAL    }, { "bird",      FORM_BIRD      },
    { "reptile",   FORM_REPTILE   }, { "snake",     FORM_SNAKE     },
    { "dragon",    FORM_DRAGON    }, { "amphibian", FORM_AMPHIBIAN },
    { "fish",      FORM_FISH      }, { "cold_blooded", FORM_COLD_BLOOD },
    { NULL, 0 }
};

static const struct build_flag part_names[] =
{
    { "head",      PART_HEAD      }, { "arms",      PART_ARMS      },
    { "legs",      PART_LEGS      }, { "heart",     PART_HEART     },
    { "brains",    PART_BRAINS    }, { "guts",      PART_GUTS      },
    { "hands",     PART_HANDS     }, { "feet",      PART_FEET      },
    { "fingers",   PART_FINGERS   }, { "ears",      PART_EAR       },
    { "eyes",      PART_EYE       }, { "long_tongue", PART_LONG_TONGUE },
    { "eyestalks", PART_EYESTALKS }, { "tentacles", PART_TENTACLES },
    { "fins",      PART_FINS      }, { "wings",     PART_WINGS     },
    { "tail",      PART_TAIL      }, { "claws",     PART_CLAWS     },
    { "fangs",     PART_FANGS     }, { "horns",     PART_HORNS     },
    { "scales",    PART_SCALES    }, { "tusks",     PART_TUSKS     },
    { NULL, 0 }
};

static const struct build_flag sex_names[] =
{
    { "male",    SEX_MALE    }, { "female",  SEX_FEMALE  },
    { "neutral", SEX_NEUTRAL }, { "none",    SEX_NEUTRAL },
    { "it",      SEX_NEUTRAL }, { "sexless", SEX_NEUTRAL },
    { NULL, 0 }
};

static const struct build_flag size_names[] =
{
    { "tiny",  SIZE_TINY  }, { "small", SIZE_SMALL }, { "medium", SIZE_MEDIUM },
    { "large", SIZE_LARGE }, { "huge",  SIZE_HUGE  }, { "giant",  SIZE_GIANT  },
    { NULL, 0 }
};

/* The positions a mobile can sensibly be found in. */
static const struct build_flag position_names[] =
{
    { "standing", POS_STANDING }, { "sitting",  POS_SITTING  },
    { "resting",  POS_RESTING  }, { "sleeping", POS_SLEEPING },
    { NULL, 0 }
};


/*
 * A prototype string, through str_perm (see there). str_perm gives back
 * an empty string when the game's string space is full, which used to let
 * an edit report success and keep nothing; the builder is told instead.
 */
static char *perm_text( CHAR_DATA *ch, const char *text )
{
    char *kept = str_perm( text );

    if ( text != NULL && text[0] != '\0' && kept[0] == '\0' )
        send_to_char( "The game's string space is full, so that text was not kept.  "
                      "Tell an implementor.\n\r", ch );
    return kept;
}


/* A name in a table: an exact match first, then the first it begins. */
static const struct build_flag *flag_find( const struct build_flag *t,
                                           const char *name )
{
    const struct build_flag *f;

    if ( name[0] == '\0' )
        return NULL;
    for ( f = t; f->name != NULL; f++ )
        if ( !str_cmp( name, f->name ) )
            return f;
    for ( f = t; f->name != NULL; f++ )
        if ( !str_prefix( name, f->name ) )
            return f;
    return NULL;
}

/* The name of one value in an enumeration table. */
static const char *enum_name( const struct build_flag *t, long value )
{
    for ( ; t->name != NULL; t++ )
        if ( t->bit == value )
            return t->name;
    return "unknown";
}

/* The names of the bits set, or "none". */
static void flag_names( const struct build_flag *t, long bits,
                        char *out, size_t size )
{
    long shown = 0;

    out[0] = '\0';
    for ( ; t->name != NULL; t++ )
    {
        /* A synonym ("body" for torso) is named once. */
        if ( IS_SET( bits, t->bit ) && !IS_SET( shown, t->bit ) )
        {
            SET_BIT( shown, t->bit );
            if ( out[0] != '\0' )
                toc_strlcat( out, " ", size );
            toc_strlcat( out, t->name, size );
        }
    }
    if ( out[0] == '\0' )
        toc_strlcpy( out, "none", size );
}

/* Every name in a table, for a "which ones are there" answer. */
static void table_names( const struct build_flag *t, char *out, size_t size )
{
    long seen = 0;

    out[0] = '\0';
    for ( ; t->name != NULL; t++ )
    {
        /* A synonym ("it" for neutral) is not worth listing twice. */
        if ( t->bit != 0 && IS_SET( seen, t->bit ) )
            continue;
        SET_BIT( seen, t->bit );
        if ( out[0] != '\0' )
            toc_strlcat( out, " ", size );
        toc_strlcat( out, t->name, size );
    }
}


/*
 * Change a flag word from words: "+aggressive -sentinel stay_area", or
 * "none". A bare name adds. `fixed' are bits that come back at every boot
 * whatever the file says -- a race's natural flags -- so taking one away
 * is refused and explained rather than allowed to look as if it worked.
 */
static bool flag_edit( CHAR_DATA *ch, const struct build_flag *t, long *bits,
                       const char *what, char *args, long fixed,
                       const char *fixed_why )
{
    char word[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    long result = *bits;
    bool any = false;

    if ( args[0] == '\0' )
    {
        table_names( t, buf, sizeof(buf) );
        send_to_char( "Give names to add (+name or name) or take away (-name), "
                      "or NONE.\n\r", ch );
        snprintf( word, sizeof(word), "%s: ", what );
        send_to_char( word, ch );
        send_to_char( buf, ch );
        send_to_char( "\n\r", ch );
        return false;
    }

    for ( ; ; )
    {
        const struct build_flag *f;
        const char *name;
        bool remove;

        args = one_argument( args, word );
        if ( word[0] == '\0' )
            break;

        if ( !str_cmp( word, "none" ) )
        {
            result &= fixed;
            any = true;
            continue;
        }

        remove = ( word[0] == '-' );
        name   = ( word[0] == '-' || word[0] == '+' ) ? word + 1 : word;

        if ( ( f = flag_find( t, name ) ) == NULL )
        {
            char msg[MAX_INPUT_LENGTH * 2];

            snprintf( msg, sizeof(msg), "There is no %s called '%s'.  They are:\n\r",
                      what, name );
            send_to_char( msg, ch );
            table_names( t, buf, sizeof(buf) );
            send_to_char( buf, ch );
            send_to_char( "\n\r", ch );
            return false;
        }

        if ( remove )
        {
            if ( IS_SET( fixed, f->bit ) )
            {
                snprintf( buf, sizeof(buf), "'%s' cannot be taken away: %s.\n\r",
                          f->name, fixed_why );
                send_to_char( buf, ch );
                return false;
            }
            REMOVE_BIT( result, f->bit );
        }
        else
            SET_BIT( result, f->bit );
        any = true;
    }

    if ( !any )
        return false;
    *bits = result;
    return true;
}


/* "4d10+80", "4d10", "2d6-3" or a plain "50". */
static bool parse_dice( const char *s, int *number, int *type, int *bonus )
{
    char *end;
    long n, t, b = 0;

    while ( isspace( (unsigned char) *s ) )
        s++;
    if ( !isdigit( (unsigned char) *s ) && *s != '-' )
        return false;

    n = strtol( s, &end, 10 );
    if ( *end == '\0' )
    {
        *number = 0;
        *type   = 0;
        *bonus  = (int) URANGE( -1000000L, n, 1000000L );
        return n >= -1000000L && n <= 1000000L;
    }
    if ( LOWER( *end ) != 'd' || n < 0 )
        return false;

    s = end + 1;
    if ( !isdigit( (unsigned char) *s ) )
        return false;
    t = strtol( s, &end, 10 );
    if ( *end == '+' || *end == '-' )
    {
        s = end;
        b = strtol( s, &end, 10 );
    }
    if ( *end != '\0' || n > 10000 || t > 10000 || b < -1000000L || b > 1000000L )
        return false;

    *number = (int) n;
    *type   = (int) t;
    *bonus  = (int) b;
    return true;
}


/* What load_mobiles would do to these fields at this level, done now. */
static void apply_level_clamps( CHAR_DATA *ch, MOB_INDEX_DATA *m )
{
    char buf[MAX_STRING_LENGTH];
    int ac_cap = 100 - 6 * m->level;
    int i;
    bool ac = false;

    if ( m->hitroll < m->level / 2 )
    {
        m->hitroll = (sh_int) ( m->level / 2 );
        snprintf( buf, sizeof(buf), "Hitroll raised to %d, the least a level %d "
                  "mobile gets.\n\r", m->hitroll, m->level );
        send_to_char( buf, ch );
    }
    if ( m->damage[DICE_BONUS] < 3 * m->level / 4 )
    {
        m->damage[DICE_BONUS] = (sh_int) ( 3 * m->level / 4 );
        snprintf( buf, sizeof(buf), "Damage bonus raised to %d, the least a "
                  "level %d mobile gets.\n\r", m->damage[DICE_BONUS], m->level );
        send_to_char( buf, ch );
    }
    for ( i = 0; i < 4; i++ )
    {
        if ( m->ac[i] > ac_cap )
        {
            m->ac[i] = (sh_int) ac_cap;
            ac = true;
        }
    }
    if ( ac )
    {
        snprintf( buf, sizeof(buf), "Armour brought down to %d, the worst a "
                  "level %d mobile has (lower is better).\n\r", ac_cap, m->level );
        send_to_char( buf, ch );
    }
}


/* Text wrapped at 72 columns, each line ending "\n\r", appended to out. */
static void wrap_into( const char *text, char *out, size_t size )
{
    char word[MAX_INPUT_LENGTH];
    size_t col = 0;

    for ( ; ; )
    {
        size_t len = 0;

        while ( isspace( (unsigned char) *text ) )
            text++;
        if ( *text == '\0' )
            break;
        while ( *text != '\0' && !isspace( (unsigned char) *text )
             && len < sizeof(word) - 1 )
            word[len++] = *text++;
        word[len] = '\0';

        if ( col > 0 && col + 1 + len > 72 )
        {
            toc_strlcat( out, "\n\r", size );
            col = 0;
        }
        else if ( col > 0 )
        {
            toc_strlcat( out, " ", size );
            col++;
        }
        toc_strlcat( out, word, size );
        col += len;
    }
    if ( col > 0 )
        toc_strlcat( out, "\n\r", size );
}


/* The attack_table index of a name ("slash", "flaming bite"), or -1. */
static int attack_named( const char *name )
{
    char want[MAX_INPUT_LENGTH];
    char *p;
    int i;

    toc_strlcpy( want, name, sizeof(want) );
    for ( p = want; *p != '\0'; p++ )
        if ( *p == '_' )
            *p = ' ';

    for ( i = 0; i <= MAX_DAMAGE_MESSAGE; i++ )
        if ( !str_cmp( want, attack_table[i].name ) )
            return i;
    for ( i = 0; i <= MAX_DAMAGE_MESSAGE; i++ )
        if ( !str_prefix( want, attack_table[i].name ) )
            return i;
    return -1;
}

static void attack_list( char *out, size_t size )
{
    int i;

    out[0] = '\0';
    for ( i = 0; i <= MAX_DAMAGE_MESSAGE; i++ )
    {
        char one[64];
        char *p;

        toc_strlcpy( one, attack_table[i].name, sizeof(one) );
        for ( p = one; *p != '\0'; p++ )
            if ( *p == ' ' )
                *p = '_';
        if ( out[0] != '\0' )
            toc_strlcat( out, " ", size );
        toc_strlcat( out, one, size );
    }
}


/* A race by name, exact first; -1 if none. */
static int race_named( const char *name )
{
    int race;

    for ( race = 0; race_table[race].name != NULL; race++ )
        if ( !str_cmp( name, race_table[race].name ) )
            return race;
    for ( race = 0; race_table[race].name != NULL; race++ )
        if ( !str_prefix( name, race_table[race].name ) )
            return race;
    return -1;
}

/* A special by name, with or without its "spec_". */
static SPEC_FUN *spec_named( const char *name )
{
    char full[MAX_INPUT_LENGTH];
    SPEC_FUN *fun;

    if ( ( fun = spec_lookup( name ) ) != NULL )
        return fun;
    snprintf( full, sizeof(full), "spec_%s", name );
    return spec_lookup( full );
}


/*
 * Which prototype a builder means, or NULL after saying why it cannot be
 * edited. Only an ANEW area's prototypes can be: the range is what ASAVE
 * writes, so a change to any other would be lost at the next boot.
 */
static MOB_INDEX_DATA *editable_mob( CHAR_DATA *ch, const char *arg )
{
    char buf[MAX_STRING_LENGTH];
    MOB_INDEX_DATA *m;
    AREA_DATA *pArea;
    int vnum;

    if ( !is_number( (char *) arg ) || strlen( arg ) > 5
      || ( vnum = atoi( arg ) ) <= 0
      || ( m = get_mob_index( vnum ) ) == NULL )
    {
        snprintf( buf, sizeof(buf), "There is no mobile %s.  MCREATE makes one.\n\r",
                  arg );
        send_to_char( buf, ch );
        return NULL;
    }

    if ( ( pArea = area_for_vnum( vnum ) ) == NULL )
    {
        snprintf( buf, sizeof(buf),
                  "Mobile %d came with the game, not from an area built here, and "
                  "a change\n\rto it could never be saved.  Copy it into your own "
                  "area instead:\n\r  mcreate <new vnum> %d\n\r", vnum, vnum );
        send_to_char( buf, ch );
        return NULL;
    }

    if ( !may_build_area( ch, pArea ) )
    {
        snprintf( buf, sizeof(buf), "Mobile %d belongs to %s, and you are not one "
                  "of its builders.\n\r", vnum, pArea->name );
        send_to_char( buf, ch );
        return NULL;
    }

    return m;
}


/* The full prototype, in the words SET MOB takes. */
static void show_mob( CHAR_DATA *ch, MOB_INDEX_DATA *m )
{
    char buf[MAX_STRING_LENGTH];
    char flags[1024];
    static char out[4 * MAX_STRING_LENGTH];
    const size_t size = sizeof(out);
    AREA_DATA *pArea = area_for_vnum( m->vnum );
    MOB_ACTION_DATA *action;
    int actions = 0;
    const char *spec;

    out[0] = '\0';

    for ( action = m->action; action != NULL; action = action->next )
        actions++;

    snprintf( buf, sizeof(buf), "Mobile %d, in %s.\n\r", m->vnum,
              pArea != NULL ? pArea->name : "an area that shipped with the game" );
    toc_strlcat( out, buf, size );
    snprintf( buf, sizeof(buf), "keywords: %s\n\rshort:    %s\n\rlong:     %s",
              m->player_name, m->short_descr, m->long_descr );
    toc_strlcat( out, buf, size );
    if ( m->long_descr[0] == '\0'
      || m->long_descr[strlen( m->long_descr ) - 1] != '\r' )
        toc_strlcat( out, "\n\r", size );
    toc_strlcat( out, "desc:\n\r", size );
    toc_strlcat( out, m->description[0] != '\0' ? m->description
                                               : "  (none)\n\r", size );

    snprintf( buf, sizeof(buf),
              "race: %s   sex: %s   size: %s   material: %s\n\r"
              "level: %d   alignment: %d   hitroll: %d\n\r"
              "hp: %dd%d+%d   mana: %dd%d+%d   damage: %dd%d+%d   attack: %s\n\r"
              "ac: pierce %d  bash %d  slash %d  exotic %d   (lower is better)\n\r"
              "position: %s   default: %s   wealth: %ld\n\r",
              race_table[m->race].name, enum_name( sex_names, m->sex ),
              enum_name( size_names, m->size ), material_name( m->material ),
              m->level, m->alignment, m->hitroll,
              m->hit[DICE_NUMBER], m->hit[DICE_TYPE], m->hit[DICE_BONUS],
              m->mana[DICE_NUMBER], m->mana[DICE_TYPE], m->mana[DICE_BONUS],
              m->damage[DICE_NUMBER], m->damage[DICE_TYPE], m->damage[DICE_BONUS],
              m->dam_type >= 0 && m->dam_type <= MAX_DAMAGE_MESSAGE
                  ? attack_table[m->dam_type].name : "unknown",
              m->ac[AC_PIERCE], m->ac[AC_BASH], m->ac[AC_SLASH], m->ac[AC_EXOTIC],
              enum_name( position_names, m->start_pos ),
              enum_name( position_names, m->default_pos ), m->wealth );
    toc_strlcat( out, buf, size );

    flag_names( act_names, m->act, flags, sizeof(flags) );
    snprintf( buf, sizeof(buf), "act:        %s\n\r", flags );
    toc_strlcat( out, buf, size );
    if ( m->act2 != 0 )
    {
        flag_names( act2_names, m->act2, flags, sizeof(flags) );
        snprintf( buf, sizeof(buf), "act2:       %s\n\r", flags );
        toc_strlcat( out, buf, size );
    }
    flag_names( affect_names, m->affected_by, flags, sizeof(flags) );
    snprintf( buf, sizeof(buf), "affect:     %s\n\r", flags );
    toc_strlcat( out, buf, size );
    if ( m->affected_by2 != 0 )
    {
        flag_names( affect2_names, m->affected_by2, flags, sizeof(flags) );
        snprintf( buf, sizeof(buf), "affect2:    %s\n\r", flags );
        toc_strlcat( out, buf, size );
    }
    flag_names( off_names, m->off_flags, flags, sizeof(flags) );
    snprintf( buf, sizeof(buf), "offense:    %s\n\r", flags );
    toc_strlcat( out, buf, size );
    if ( m->off_flags2 != 0 )
    {
        flag_names( off2_names, m->off_flags2, flags, sizeof(flags) );
        snprintf( buf, sizeof(buf), "offense2:   %s\n\r", flags );
        toc_strlcat( out, buf, size );
    }
    flag_names( imm_names, m->imm_flags, flags, sizeof(flags) );
    snprintf( buf, sizeof(buf), "immune:     %s\n\r", flags );
    toc_strlcat( out, buf, size );
    flag_names( res_names, m->res_flags, flags, sizeof(flags) );
    snprintf( buf, sizeof(buf), "resist:     %s\n\r", flags );
    toc_strlcat( out, buf, size );
    flag_names( vuln_names, m->vuln_flags, flags, sizeof(flags) );
    snprintf( buf, sizeof(buf), "vulnerable: %s\n\r", flags );
    toc_strlcat( out, buf, size );
    flag_names( form_names, m->form, flags, sizeof(flags) );
    snprintf( buf, sizeof(buf), "form:       %s\n\r", flags );
    toc_strlcat( out, buf, size );
    flag_names( part_names, m->parts, flags, sizeof(flags) );
    snprintf( buf, sizeof(buf), "parts:      %s\n\r", flags );
    toc_strlcat( out, buf, size );

    spec = m->spec_fun != NULL ? special_name( m->spec_fun ) : "none";
    snprintf( buf, sizeof(buf), "special: %s   actions: %d\n\r", spec, actions );
    toc_strlcat( out, buf, size );
    if ( m->pShop != NULL )
    {
        char terms[256];

        shop_words( m->pShop, terms, sizeof(terms) );
        snprintf( buf, sizeof(buf), "shop:    %s\n\r", terms );
    }
    else
        snprintf( buf, sizeof(buf), "shop:    none\n\r" );
    toc_strlcat( out, buf, size );

    toc_strlcat( out, "(Mobiles already loaded keep their old form; LOAD one to "
                      "see a change.)\n\r", size );
    page_to_char( out, ch );
}


/* MSHOW <vnum> -- a mobile prototype in the words SET MOB takes. */
void do_mshow( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    MOB_INDEX_DATA *m;

    one_argument( argument, arg );
    if ( arg[0] == '\0' || !is_number( arg ) || strlen( arg ) > 5
      || ( m = get_mob_index( atoi( arg ) ) ) == NULL )
    {
        send_to_char( "Syntax: mshow <mobile vnum>\n\r", ch );
        return;
    }
    show_mob( ch, m );
}


static void mob_field_help( CHAR_DATA *ch )
{
    send_to_char(
        "Syntax: set mob <vnum> <field> <value>\n\r"
        "  keywords <words>          short <text>       long <text>\n\r"
        "  desc <text>  (desc + <text> adds a line, desc clear empties it)\n\r"
        "  race <name>   sex male|female|neutral   size tiny..giant\n\r"
        "  level <n>     alignment <n>|good|neutral|evil   hitroll <n>\n\r"
        "  hp <dice>     mana <dice>   damage <dice>     e.g. 4d10+80\n\r"
        "  attack <name> (slash, bite, flaming_bite...)\n\r"
        "  ac <n>  or  ac pierce|bash|slash|exotic <n>   (lower is better)\n\r"
        "  position <pos>  default <pos>   (standing sitting resting sleeping)\n\r"
        "  wealth <n>    material <name>   special <name>|none\n\r"
        "  shop  (then: markup <%>  pays <%>  buys <types>  hours <o> <c>  none)\n\r"
        "  act affect affect2 offense immune resist vulnerable form parts\n\r"
        "      +name adds, -name takes away, none clears:  act +aggressive -wimpy\n\r"
        "MSHOW <vnum> shows the mobile in these words.  ASAVE keeps changes.\n\r",
        ch );
}


/*
 * SET MOB <vnum> <field> <value>: reached from do_set when the target is a
 * number, so "set mob guard ..." still edits a mobile in the world.
 */
bool build_set_mob( CHAR_DATA *ch, char *argument )
{
    char arg1[MAX_INPUT_LENGTH];
    char field[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    char value[MAX_INPUT_LENGTH];
    char race_why[MAX_INPUT_LENGTH];
    MOB_INDEX_DATA *m;
    long race_fixed;

    smash_tilde( argument );
    argument = one_argument( argument, arg1 );
    argument = one_argument( argument, field );
    while ( isspace( (unsigned char) *argument ) )
        argument++;
    toc_strlcpy( value, argument, sizeof(value) );

    if ( ( m = editable_mob( ch, arg1 ) ) == NULL )
        return false;

    if ( field[0] == '\0' )
    {
        show_mob( ch, m );
        return false;
    }

    snprintf( race_why, sizeof(race_why), "that is part of being %s %s",
              strchr( "aeiou", LOWER( race_table[m->race].name[0] ) ) ? "an" : "a",
              race_table[m->race].name );

    if ( !str_cmp( field, "shop" ) )
        return mob_shop_edit( ch, m, value );

    /* Every field below wants a value; an empty one would match every
       name, since str_prefix calls "" a prefix of anything. */
    if ( value[0] == '\0' )
    {
        mob_field_help( ch );
        return false;
    }

    /* ---- words ---- */
    if ( !str_prefix( field, "keywords" ) || !str_cmp( field, "name" ) )
    {
        m->player_name = perm_text( ch, value );
    }
    else if ( !str_prefix( field, "short" ) )
    {
        m->short_descr = perm_text( ch, value );
    }
    else if ( !str_prefix( field, "long" ) )
    {
        char text[MAX_STRING_LENGTH];

        snprintf( text, sizeof(text), "%s\n\r", value );
        text[0] = UPPER( text[0] );
        m->long_descr = perm_text( ch, text );
    }
    else if ( !str_prefix( field, "description" ) )
    {
        char text[2 * MAX_STRING_LENGTH];

        text[0] = '\0';
        if ( !str_cmp( value, "clear" ) )
            ;
        else if ( value[0] == '+' )
        {
            toc_strlcpy( text, m->description, sizeof(text) );
            wrap_into( value + 1, text, sizeof(text) );
        }
        else if ( value[0] != '\0' )
            wrap_into( value, text, sizeof(text) );
        else
        {
            mob_field_help( ch );
            return false;
        }
        if ( strlen( text ) >= MAX_STRING_LENGTH - 2 )
        {
            send_to_char( "That description is too long.\n\r", ch );
            return false;
        }
        text[0] = UPPER( text[0] );
        m->description = perm_text( ch, text );
    }

    /* ---- what it is ---- */
    else if ( !str_prefix( field, "race" ) )
    {
        int race = race_named( value );

        if ( value[0] == '\0' || race < 0 )
        {
            send_to_char( "No such race.  Try human, elf, dwarf, giant, dragon, "
                          "wolf, bear...\n\r", ch );
            return false;
        }
        m->race        = (sh_int) race;
        /* What load_mobiles ORs in at every boot, ORed in now; form and
           parts are the race's own outright. */
        m->act        |= race_table[race].act;
        m->affected_by |= race_table[race].aff;
        m->off_flags  |= race_table[race].off;
        m->imm_flags  |= race_table[race].imm;
        m->res_flags  |= race_table[race].res;
        m->vuln_flags |= race_table[race].vuln;
        m->form        = race_table[race].form;
        m->parts       = race_table[race].parts;
    }
    else if ( !str_prefix( field, "sex" ) )
    {
        const struct build_flag *f = flag_find( sex_names, value );

        if ( f == NULL ) { send_to_char( "Sex is male, female or neutral.\n\r", ch ); return false; }
        m->sex = (sh_int) f->bit;
    }
    else if ( !str_prefix( field, "size" ) )
    {
        const struct build_flag *f = flag_find( size_names, value );

        if ( f == NULL )
        {
            send_to_char( "Size is tiny, small, medium, large, huge or giant.\n\r", ch );
            return false;
        }
        m->size = (sh_int) f->bit;
    }
    else if ( !str_prefix( field, "material" ) )
    {
        int mat = material_lookup( value );

        if ( value[0] == '\0' || ( mat == 19 && str_prefix( value, "unknown" ) ) )
        {
            send_to_char( "Materials: adamantite brass bronze cloth copper food "
                          "glass gold herb iron\n\r  leather paper pill silver "
                          "'spell component' steel stone vellum wood unknown\n\r", ch );
            return false;
        }
        m->material = (sh_int) mat;
    }

    /* ---- numbers ---- */
    else if ( !str_prefix( field, "level" ) )
    {
        int level = atoi( value );

        if ( !is_number( value ) || level < 1 || level > 200 )
        {
            send_to_char( "Level is a number from 1 to 200.\n\r", ch );
            return false;
        }
        kill_table[URANGE(0, m->level, MAX_LEVEL-1)].number--;
        m->level = (sh_int) level;
        kill_table[URANGE(0, m->level, MAX_LEVEL-1)].number++;
        apply_level_clamps( ch, m );
    }
    else if ( !str_prefix( field, "alignment" ) )
    {
        int align;

        if ( !str_cmp( value, "good" ) )           align = 1000;
        else if ( !str_cmp( value, "neutral" ) )   align = 0;
        else if ( !str_cmp( value, "evil" ) )      align = -1000;
        else if ( is_number( value ) || ( value[0] == '-' && is_number( value + 1 ) ) )
            align = atoi( value );
        else
            align = 99999;
        if ( align < -1000 || align > 1000 )
        {
            send_to_char( "Alignment is good, neutral, evil, or a number from "
                          "-1000 to 1000.\n\r", ch );
            return false;
        }
        m->alignment = (sh_int) align;
    }
    else if ( !str_prefix( field, "hitroll" ) && str_cmp( field, "hit" ) )
    {
        if ( !is_number( value ) || strlen( value ) > 4 )
        {
            send_to_char( "Hitroll is a number.\n\r", ch );
            return false;
        }
        m->hitroll = (sh_int) atoi( value );
        apply_level_clamps( ch, m );
    }
    else if ( !str_cmp( field, "hp" ) || !str_prefix( field, "hitpoints" )
           || !str_cmp( field, "hit" ) )
    {
        int n, t, b;

        if ( !parse_dice( value, &n, &t, &b ) || b < -100000 )
        {
            send_to_char( "Hit points are dice: 4d10+80 (four ten-sided dice, plus "
                          "80).\n\r", ch );
            return false;
        }
        m->hit[DICE_NUMBER] = n;
        m->hit[DICE_TYPE]   = t;
        m->hit[DICE_BONUS]  = b;
    }
    else if ( !str_prefix( field, "mana" ) || !str_prefix( field, "damage" ) )
    {
        sh_int *dice = !str_prefix( field, "mana" ) ? m->mana : m->damage;
        int n, t, b;

        if ( !parse_dice( value, &n, &t, &b ) || n > 32767 || t > 32767
          || b < -32768 || b > 32767 )
        {
            send_to_char( "Give dice: 2d6+3 (two six-sided dice, plus 3).\n\r", ch );
            return false;
        }
        dice[DICE_NUMBER] = (sh_int) n;
        dice[DICE_TYPE]   = (sh_int) t;
        dice[DICE_BONUS]  = (sh_int) b;
        apply_level_clamps( ch, m );
    }
    else if ( !str_prefix( field, "attack" ) || !str_cmp( field, "damtype" ) )
    {
        int at = attack_named( value );

        if ( value[0] == '\0' || at < 0 )
        {
            attack_list( buf, sizeof(buf) );
            send_to_char( "Attacks: ", ch );
            send_to_char( buf, ch );
            send_to_char( "\n\r", ch );
            return false;
        }
        m->dam_type = (sh_int) at;
    }
    else if ( !str_cmp( field, "ac" ) || !str_prefix( field, "armor" )
           || !str_prefix( field, "armour" ) )
    {
        char kind[MAX_INPUT_LENGTH];
        char *rest = one_argument( value, kind );
        int which = -1;
        int ac;
        int i;

        if ( !str_prefix( kind, "pierce" ) )      which = AC_PIERCE;
        else if ( !str_prefix( kind, "bash" ) )   which = AC_BASH;
        else if ( !str_prefix( kind, "slash" ) )  which = AC_SLASH;
        else if ( !str_prefix( kind, "exotic" ) ) which = AC_EXOTIC;
        else rest = value;

        while ( isspace( (unsigned char) *rest ) )
            rest++;
        if ( !( is_number( rest ) || ( rest[0] == '-' && is_number( rest + 1 ) ) )
          || strlen( rest ) > 6 )
        {
            send_to_char( "Armour is a number, lower is better: ac -20, or ac "
                          "slash -40.\n\r", ch );
            return false;
        }
        ac = URANGE( -10000, atoi( rest ), 10000 );
        for ( i = 0; i < 4; i++ )
            if ( which < 0 || which == i )
                m->ac[i] = (sh_int) ac;
        apply_level_clamps( ch, m );
    }
    else if ( !str_prefix( field, "wealth" ) )
    {
        if ( !is_number( value ) || strlen( value ) > 8 )
        {
            send_to_char( "Wealth is a number (0 means what a mobile of its level "
                          "usually carries).\n\r", ch );
            return false;
        }
        mob_index_set_wealth( m, atol( value ) );
    }
    else if ( !str_prefix( field, "position" ) || !str_prefix( field, "start" )
           || !str_prefix( field, "default" ) )
    {
        const struct build_flag *f = flag_find( position_names, value );

        if ( f == NULL )
        {
            send_to_char( "Positions: standing sitting resting sleeping.\n\r", ch );
            return false;
        }
        if ( !str_prefix( field, "default" ) )
            m->default_pos = (sh_int) f->bit;
        else
            m->start_pos = (sh_int) f->bit;
    }
    else if ( !str_prefix( field, "special" ) || !str_cmp( field, "spec" ) )
    {
        SPEC_FUN *fun = NULL;

        if ( value[0] == '\0' )
        {
            send_to_char( "Give a special's name, or NONE.  HELP SPECIALS lists "
                          "them.\n\r", ch );
            return false;
        }
        if ( str_cmp( value, "none" ) && ( fun = spec_named( value ) ) == NULL )
        {
            snprintf( buf, sizeof(buf), "There is no special called %s.\n\r", value );
            send_to_char( buf, ch );
            return false;
        }
        m->spec_fun = fun;
    }

    /* ---- flag words ---- */
    else if ( !str_cmp( field, "act" ) )
    {
        long bits = m->act;

        race_fixed = race_table[m->race].act | ACT_IS_NPC;
        if ( !flag_edit( ch, act_names, &bits, "act flag", value, race_fixed, race_why ) )
            return false;
        m->act = bits | ACT_IS_NPC;
    }
    else if ( !str_cmp( field, "act2" ) )
    {
        if ( !flag_edit( ch, act2_names, &m->act2, "act2 flag", value, 0, race_why ) )
            return false;
    }
    else if ( !str_cmp( field, "affect2" ) || !str_cmp( field, "aff2" ) )
    {
        if ( !flag_edit( ch, affect2_names, &m->affected_by2, "affect", value, 0,
                         race_why ) )
            return false;
    }
    else if ( !str_prefix( field, "affects" ) || !str_cmp( field, "aff" ) )
    {
        if ( !flag_edit( ch, affect_names, &m->affected_by, "affect", value,
                         race_table[m->race].aff, race_why ) )
            return false;
    }
    else if ( !str_cmp( field, "offense2" ) || !str_cmp( field, "off2" ) )
    {
        if ( !flag_edit( ch, off2_names, &m->off_flags2, "offense", value, 0,
                         race_why ) )
            return false;
    }
    else if ( !str_prefix( field, "offense" ) || !str_prefix( field, "offence" ) )
    {
        if ( !flag_edit( ch, off_names, &m->off_flags, "offense", value,
                         race_table[m->race].off, race_why ) )
            return false;
    }
    else if ( !str_prefix( field, "immune" ) || !str_prefix( field, "immunities" ) )
    {
        if ( !flag_edit( ch, imm_names, &m->imm_flags, "immunity", value,
                         race_table[m->race].imm, race_why ) )
            return false;
    }
    else if ( !str_prefix( field, "resist" ) || !str_prefix( field, "resistances" ) )
    {
        if ( !flag_edit( ch, res_names, &m->res_flags, "resistance", value,
                         race_table[m->race].res, race_why ) )
            return false;
    }
    else if ( !str_prefix( field, "vulnerable" ) || !str_prefix( field, "vulnerabilities" ) )
    {
        if ( !flag_edit( ch, vuln_names, &m->vuln_flags, "vulnerability", value,
                         race_table[m->race].vuln, race_why ) )
            return false;
    }
    else if ( !str_prefix( field, "form" ) )
    {
        if ( !flag_edit( ch, form_names, &m->form, "form", value,
                         race_table[m->race].form, race_why ) )
            return false;
    }
    else if ( !str_prefix( field, "parts" ) )
    {
        if ( !flag_edit( ch, part_names, &m->parts, "part", value,
                         race_table[m->race].parts, race_why ) )
            return false;
    }
    else
    {
        mob_field_help( ch );
        return false;
    }

    snprintf( buf, sizeof(buf), "Mobile %d's %s is set.  MSHOW %d to look; ASAVE "
              "to keep it.\n\r", m->vnum, field, m->vnum );
    send_to_char( buf, ch );
    return true;
}


/*
 * ------------------------------------------------------------------------
 * Objects: SET OBJ <vnum> and OSHOW.
 *
 * An object's five values mean different things for each type -- a
 * weapon's are its class, dice, attack and flags; a container's its
 * capacity, lid and key -- so the value fields are named per type and a
 * field another type owns is refused with the list of this type's. V0 to
 * V4 stay available underneath, for the types nobody has named yet.
 *
 * Every value written is kept at 0 or above: the area file reads values
 * with fread_flag, which has no minus sign, and ASAVE refuses a negative
 * one rather than write it.
 * ------------------------------------------------------------------------
 */

DECLARE_SPELL_FUN( spell_null );

static const struct build_flag type_names[] =
{
    { "light",       ITEM_LIGHT       }, { "scroll",      ITEM_SCROLL      },
    { "wand",        ITEM_WAND        }, { "staff",       ITEM_STAFF       },
    { "weapon",      ITEM_WEAPON      }, { "treasure",    ITEM_TREASURE    },
    { "armor",       ITEM_ARMOR       }, { "armour",      ITEM_ARMOR       },
    { "potion",      ITEM_POTION      }, { "clothing",    ITEM_CLOTHING    },
    { "furniture",   ITEM_FURNITURE   }, { "trash",       ITEM_TRASH       },
    { "container",   ITEM_CONTAINER   }, { "drink",       ITEM_DRINK_CON   },
    { "key",         ITEM_KEY         }, { "food",        ITEM_FOOD        },
    { "money",       ITEM_MONEY       }, { "boat",        ITEM_BOAT        },
    { "fountain",    ITEM_FOUNTAIN    }, { "pill",        ITEM_PILL        },
    { "map",         ITEM_MAP         }, { "scuba_gear",  ITEM_SCUBA_GEAR  },
    { "portal",      ITEM_PORTAL      }, { "saddle",      ITEM_SADDLE      },
    { "herb",        ITEM_HERB        }, { "spell_component", ITEM_SPELL_COMPONENT },
    { "training_food", ITEM_CAKE      },
    { NULL, 0 }
};

static const struct build_flag wear_names[] =
{
    { "take",      ITEM_TAKE        }, { "finger",    ITEM_WEAR_FINGER },
    { "neck",      ITEM_WEAR_NECK   }, { "torso",     ITEM_WEAR_BODY   },
    { "body",      ITEM_WEAR_BODY   }, { "head",      ITEM_WEAR_HEAD   },
    { "legs",      ITEM_WEAR_LEGS   }, { "feet",      ITEM_WEAR_FEET   },
    { "hands",     ITEM_WEAR_HANDS  }, { "arms",      ITEM_WEAR_ARMS   },
    { "shield",    ITEM_WEAR_SHIELD }, { "about",     ITEM_WEAR_ABOUT  },
    { "waist",     ITEM_WEAR_WAIST  }, { "wrist",     ITEM_WEAR_WRIST  },
    { "wield",     ITEM_WIELD       }, { "hold",      ITEM_HOLD        },
    { "two_hands", ITEM_TWO_HANDS   },
    { NULL, 0 }
};

static const struct build_flag extra_names[] =
{
    { "glow",        ITEM_GLOW        }, { "hum",         ITEM_HUM         },
    { "dark",        ITEM_DARK        }, { "lock",        ITEM_LOCK        },
    { "evil",        ITEM_EVIL        }, { "invis",       ITEM_INVIS       },
    { "magic",       ITEM_MAGIC       }, { "nodrop",      ITEM_NODROP      },
    { "bless",       ITEM_BLESS       }, { "anti_good",   ITEM_ANTI_GOOD   },
    { "anti_evil",   ITEM_ANTI_EVIL   }, { "anti_neutral", ITEM_ANTI_NEUTRAL },
    { "noremove",    ITEM_NOREMOVE    }, { "inventory",   ITEM_INVENTORY   },
    { "nopurge",     ITEM_NOPURGE     }, { "rot_death",   ITEM_ROT_DEATH   },
    { "vis_death",   ITEM_VIS_DEATH   }, { "metal",       ITEM_METAL       },
    { "bounce",      ITEM_BOUNCE      }, { "no_identify", ITEM_NOIDENTIFY  },
    { "no_locate",   ITEM_NOLOCATE    }, { "race_restricted", ITEM_RACE_RESTRICTED },
    { NULL, 0 }
};

static const struct build_flag extra2_names[] =
{
    { "humans_only",    ITEM2_HUMAN_ONLY    }, { "elves_only",     ITEM2_ELF_ONLY      },
    { "dwarves_only",   ITEM2_DWARF_ONLY    }, { "halflings_only", ITEM2_HALFLING_ONLY },
    { "saurians_only",  ITEM2_SAURIAN_ONLY  }, { "no_steal",       ITEM2_NOSTEAL       },
    { "no_teleport",    ITEM2_NO_TPORT      },
    { NULL, 0 }
};

static const struct build_flag weapon_class_names[] =
{
    { "exotic", WEAPON_EXOTIC }, { "sword",   WEAPON_SWORD   },
    { "dagger", WEAPON_DAGGER }, { "spear",   WEAPON_SPEAR   },
    { "mace",   WEAPON_MACE   }, { "axe",     WEAPON_AXE     },
    { "flail",  WEAPON_FLAIL  }, { "whip",    WEAPON_WHIP    },
    { "polearm", WEAPON_POLEARM }, { "bow",   WEAPON_BOW     },
    { NULL, 0 }
};

static const struct build_flag weapon_flag_names[] =
{
    { "flaming",  WEAPON_FLAMING  }, { "frost",     WEAPON_FROST     },
    { "vampiric", WEAPON_VAMPIRIC }, { "sharp",     WEAPON_SHARP     },
    { "vorpal",   WEAPON_VORPAL   }, { "two_handed", WEAPON_TWO_HANDS },
    { NULL, 0 }
};

static const struct build_flag container_names[] =
{
    { "closeable", CONT_CLOSEABLE }, { "pickproof", CONT_PICKPROOF },
    { "closed",    CONT_CLOSED    }, { "locked",    CONT_LOCKED    },
    { "trapped",   CONT_TRAPPED   },
    { NULL, 0 }
};

static const struct build_flag coin_names[] =
{
    { "copper", TYPE_COPPER }, { "silver",   TYPE_SILVER   },
    { "gold",   TYPE_GOLD   }, { "platinum", TYPE_PLATINUM },
    { NULL, 0 }
};

/* Portal kinds by what do_enter does with each value[0]. */
static const struct build_flag portal_names[] =
{
    { "plain",        0 }, { "random",       1 },
    { "crystal_ball", 4 }, { "keyed",        6 },
    { NULL, 0 }
};

static const struct build_flag apply_names[] =
{
    { "strength",     APPLY_STR           }, { "dexterity",    APPLY_DEX          },
    { "intelligence", APPLY_INT           }, { "wisdom",       APPLY_WIS          },
    { "constitution", APPLY_CON           }, { "hp",           APPLY_HIT          },
    { "mana",         APPLY_MANA          }, { "moves",        APPLY_MOVE         },
    { "ac",           APPLY_AC            }, { "hitroll",      APPLY_HITROLL      },
    { "damroll",      APPLY_DAMROLL       }, { "saves",        APPLY_SAVING_SPELL },
    { "save_para",    APPLY_SAVING_PARA   }, { "save_rod",     APPLY_SAVING_ROD   },
    { "save_petri",   APPLY_SAVING_PETRI  }, { "save_breath",  APPLY_SAVING_BREATH },
    { "age",          APPLY_AGE           }, { "weight",       APPLY_WEIGHT       },
    { "height",       APPLY_HEIGHT        },
    { NULL, 0 }
};

/* The letters load_objects turns into these conditions. */
static const struct build_flag condition_names[] =
{
    { "perfect", 100 }, { "good",    90 }, { "average", 75 }, { "worn", 50 },
    { "damaged",  25 }, { "broken",  10 }, { "ruined",   0 },
    { NULL, 0 }
};


/* A condition in words, rounded down the way the area file stores it. */
static const char *condition_word( int condition )
{
    const struct build_flag *f;

    for ( f = condition_names; f->name != NULL; f++ )
        if ( condition >= f->bit )
            return f->name;
    return "ruined";
}


/* A number at or above zero, no larger than `hi'; -1 when it is not one. */
static long plain_number( const char *s, long hi )
{
    long n;

    if ( s[0] == '\0' || !isdigit( (unsigned char) s[0] ) || !is_number( (char *) s )
      || strlen( s ) > 12 )
        return -1;
    n = atol( s );
    return n <= hi ? n : -1;
}


/* "5g 20s", "1p", "350" (copper), "3 gold": a price in copper, or -1. */
static long parse_price( char *s )
{
    char word[MAX_INPUT_LENGTH];
    long total = 0;
    bool any = false;

    for ( ; ; )
    {
        char unit_word[MAX_INPUT_LENGTH];
        char *end;
        long n;
        long unit = 1;

        s = one_argument( s, word );
        if ( word[0] == '\0' )
            break;
        if ( !isdigit( (unsigned char) word[0] ) )
            return -1;
        n = strtol( word, &end, 10 );
        if ( *end == '\0' )
        {
            /* "3 gold": the unit may be the next word. */
            char *peek = one_argument( s, unit_word );

            if ( unit_word[0] != '\0' && !isdigit( (unsigned char) unit_word[0] ) )
            {
                end = unit_word;
                s = peek;
            }
        }
        switch ( LOWER( *end ) )
        {
        case '\0': case 'c': unit = 1;                   break;
        case 's':            unit = COPPER_PER_SILVER;   break;
        case 'g':            unit = COPPER_PER_GOLD;     break;
        case 'p':            unit = COPPER_PER_PLATINUM; break;
        default:             return -1;
        }
        if ( n < 0 || n > 1000000L )
            return -1;
        total += n * unit;
        if ( total > 100000L * COPPER_PER_PLATINUM )
            return -1;
        any = true;
    }
    return any ? total : -1;
}


/* A spell that can be stored on an item: it has to do something, and it
   has to have a slot, because the area file holds spells by slot. */
static int storable_spell( const char *name )
{
    int sn = skill_lookup( name );

    if ( sn <= 0 || skill_table[sn].spell_fun == NULL
      || skill_table[sn].spell_fun == spell_null || skill_table[sn].slot <= 0 )
        return -1;
    return sn;
}

static const char *spell_word( int sn )
{
    return sn > 0 && sn < MAX_SKILL && skill_table[sn].name != NULL
        ? skill_table[sn].name : "none";
}


/* Is any object made from this prototype being worn? Equip and unequip
   read the prototype's affects, so changing them under a worn copy would
   take off something other than what was put on. */
static bool prototype_worn( OBJ_INDEX_DATA *o )
{
    LIST_ITERATOR iter;
    OBJ_DATA *obj;

    FOR_EACH_OBJECT( iter, obj )
    {
        if ( obj->pIndexData == o && obj->wear_loc != WEAR_NONE )
            return true;
    }
    return false;
}


static OBJ_INDEX_DATA *editable_obj( CHAR_DATA *ch, const char *arg )
{
    char buf[MAX_STRING_LENGTH];
    OBJ_INDEX_DATA *o;
    AREA_DATA *pArea;
    int vnum;

    if ( !is_number( (char *) arg ) || strlen( arg ) > 5
      || ( vnum = atoi( arg ) ) <= 0
      || ( o = get_obj_index( vnum ) ) == NULL )
    {
        snprintf( buf, sizeof(buf), "There is no object %s.  OCREATE makes one.\n\r",
                  arg );
        send_to_char( buf, ch );
        return NULL;
    }

    if ( ( pArea = area_for_vnum( vnum ) ) == NULL )
    {
        snprintf( buf, sizeof(buf),
                  "Object %d came with the game, not from an area built here, and "
                  "a change\n\rto it could never be saved.  Copy it into your own "
                  "area instead:\n\r  ocreate <new vnum> %d\n\r", vnum, vnum );
        send_to_char( buf, ch );
        return NULL;
    }

    if ( !may_build_area( ch, pArea ) )
    {
        snprintf( buf, sizeof(buf), "Object %d belongs to %s, and you are not one "
                  "of its builders.\n\r", vnum, pArea->name );
        send_to_char( buf, ch );
        return NULL;
    }

    return o;
}


/* The value fields of this object's type, in words, appended to out. */
static void describe_values( OBJ_INDEX_DATA *o, char *out, size_t size )
{
    char buf[MAX_STRING_LENGTH];
    char flags[512];

    buf[0] = '\0';
    switch ( o->item_type )
    {
    case ITEM_LIGHT:
        if ( o->value[2] == 999 || o->value[2] == -1 )
            snprintf( buf, sizeof(buf), "hours: infinite\n\r" );
        else
            snprintf( buf, sizeof(buf), "hours: %d\n\r", o->value[2] );
        break;
    case ITEM_WEAPON:
        flag_names( weapon_flag_names, o->value[4], flags, sizeof(flags) );
        snprintf( buf, sizeof(buf),
                  "class: %s   dice: %dd%d (average %d)   attack: %s\n\r"
                  "weapon: %s\n\r",
                  enum_name( weapon_class_names, o->value[0] ),
                  o->value[1], o->value[2], ( 1 + o->value[2] ) * o->value[1] / 2,
                  o->value[3] >= 0 && o->value[3] <= MAX_DAMAGE_MESSAGE
                      ? attack_table[o->value[3]].name : "unknown",
                  flags );
        break;
    case ITEM_ARMOR:
    case ITEM_CLOTHING:
        snprintf( buf, sizeof(buf),
                  "ac: pierce %d  bash %d  slash %d  exotic %d   (higher is better)\n\r",
                  o->value[0], o->value[1], o->value[2], o->value[3] );
        break;
    case ITEM_CONTAINER:
        flag_names( container_names, o->value[1], flags, sizeof(flags) );
        snprintf( buf, sizeof(buf), "capacity: %d   container: %s   key: %d\n\r",
                  o->value[0], flags, o->value[2] );
        break;
    case ITEM_DRINK_CON:
        snprintf( buf, sizeof(buf),
                  "capacity: %d   amount: %d   liquid: %s   poisoned: %s\n\r",
                  o->value[0], o->value[1],
                  o->value[2] >= 0 && o->value[2] < LIQ_MAX
                      ? liq_table[o->value[2]].liq_name : "unknown",
                  o->value[3] != 0 ? "yes" : "no" );
        break;
    case ITEM_FOOD:
        snprintf( buf, sizeof(buf), "hours: %d   poisoned: %s\n\r",
                  o->value[0], o->value[3] != 0 ? "yes" : "no" );
        break;
    case ITEM_MONEY:
        snprintf( buf, sizeof(buf), "coins: %d   coin: %s\n\r",
                  o->value[0], enum_name( coin_names, o->value[1] ) );
        break;
    case ITEM_PILL:
    case ITEM_POTION:
    case ITEM_SCROLL:
        snprintf( buf, sizeof(buf), "spell level: %d   spells: '%s' '%s' '%s'\n\r",
                  o->value[0], spell_word( o->value[1] ), spell_word( o->value[2] ),
                  spell_word( o->value[3] ) );
        break;
    case ITEM_WAND:
    case ITEM_STAFF:
        snprintf( buf, sizeof(buf), "spell level: %d   charges: %d   spell: '%s'\n\r",
                  o->value[0], o->value[1], spell_word( o->value[3] ) );
        break;
    case ITEM_PORTAL:
        snprintf( buf, sizeof(buf), "portal: %s   destination: %d   key: %d\n\r",
                  enum_name( portal_names, o->value[0] ), o->value[1], o->value[4] );
        break;
    }
    toc_strlcat( out, buf, size );
}


/* The full prototype, in the words SET OBJ takes. */
static void show_obj( CHAR_DATA *ch, OBJ_INDEX_DATA *o )
{
    static char out[4 * MAX_STRING_LENGTH];
    const size_t size = sizeof(out);
    char buf[MAX_STRING_LENGTH];
    char flags[1024];
    char price[64];
    AREA_DATA *pArea = area_for_vnum( o->vnum );
    AFFECT_DATA *paf;
    EXTRA_DESCR_DATA *ed;
    long grants = 0;

    out[0] = '\0';
    snprintf( buf, sizeof(buf), "Object %d, in %s.\n\r", o->vnum,
              pArea != NULL ? pArea->name : "an area that shipped with the game" );
    toc_strlcat( out, buf, size );
    snprintf( buf, sizeof(buf), "keywords: %s\n\rshort:    %s\n\rlong:     %s\n\r",
              o->name, o->short_descr, o->description );
    toc_strlcat( out, buf, size );

    format_price( o->cost, price, sizeof(price) );
    snprintf( buf, sizeof(buf),
              "type: %s   level: %d   weight: %d   cost: %s\n\r"
              "condition: %s   material: %s\n\r",
              enum_name( type_names, o->item_type ), o->level, o->weight, price,
              condition_word( o->condition ), material_name( o->material ) );
    toc_strlcat( out, buf, size );

    flag_names( wear_names, (unsigned short) o->wear_flags, flags, sizeof(flags) );
    snprintf( buf, sizeof(buf), "wear:  %s\n\r", flags );
    toc_strlcat( out, buf, size );
    flag_names( extra_names, o->extra_flags, flags, sizeof(flags) );
    if ( o->extra_flags2 != 0 )
    {
        char more[512];

        flag_names( extra2_names, o->extra_flags2, more, sizeof(more) );
        if ( !str_cmp( flags, "none" ) )
            flags[0] = '\0';
        else
            toc_strlcat( flags, " ", sizeof(flags) );
        toc_strlcat( flags, more, sizeof(flags) );
    }
    snprintf( buf, sizeof(buf), "flags: %s\n\r", flags );
    toc_strlcat( out, buf, size );

    describe_values( o, out, size );

    buf[0] = '\0';
    for ( paf = o->affected; paf != NULL; paf = paf->next )
    {
        char one[96];

        grants |= paf->bitvector;
        if ( paf->location == APPLY_NONE )
            continue;
        snprintf( one, sizeof(one), "%s%+d %s", buf[0] != '\0' ? ", " : "",
                  paf->modifier, enum_name( apply_names, paf->location ) );
        toc_strlcat( buf, one, sizeof(buf) );
    }
    snprintf( flags, sizeof(flags), "affects: %s\n\r", buf[0] != '\0' ? buf : "none" );
    toc_strlcat( out, flags, size );
    if ( grants != 0 )
    {
        flag_names( affect_names, grants, flags, sizeof(flags) );
        snprintf( buf, sizeof(buf), "grants:  %s\n\r", flags );
        toc_strlcat( out, buf, size );
    }

    buf[0] = '\0';
    for ( ed = o->extra_descr; ed != NULL; ed = ed->next )
    {
        if ( buf[0] != '\0' )
            toc_strlcat( buf, ", ", sizeof(buf) );
        toc_strlcat( buf, ed->keyword, sizeof(buf) );
    }
    snprintf( flags, sizeof(flags), "details: %s\n\r", buf[0] != '\0' ? buf : "none" );
    toc_strlcat( out, flags, size );

    snprintf( buf, sizeof(buf), "values:  %d %d %d %d %d\n\r",
              o->value[0], o->value[1], o->value[2], o->value[3], o->value[4] );
    toc_strlcat( out, buf, size );
    toc_strlcat( out, "(Objects already made keep their old values; LOAD one to "
                      "see a change.)\n\r", size );
    page_to_char( out, ch );
}


/* OSHOW <vnum> -- an object prototype in the words SET OBJ takes. */
void do_oshow( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    OBJ_INDEX_DATA *o;

    one_argument( argument, arg );
    if ( arg[0] == '\0' || !is_number( arg ) || strlen( arg ) > 5
      || ( o = get_obj_index( atoi( arg ) ) ) == NULL )
    {
        send_to_char( "Syntax: oshow <object vnum>\n\r", ch );
        return;
    }
    show_obj( ch, o );
}


static void obj_field_help( CHAR_DATA *ch )
{
    send_to_char(
        "Syntax: set obj <vnum> <field> <value>\n\r"
        "  keywords <words>   short <text>   long <text>   material <name>\n\r"
        "  type <type>   level <n>   weight <n>   cost 5g 20s   condition perfect..ruined\n\r"
        "  wear +take +wield ...    flags +glow +magic -nodrop ...\n\r"
        "  affect +hitroll 2   affect -hitroll   affect none\n\r"
        "  grants +haste       (a power while worn)   detail <keyword> <text>\n\r"
        "By type:\n\r"
        "  weapon     class <sword..bow>  dice 2d6  attack <name>  weapon +sharp\n\r"
        "  armor      ac <n>  or  ac pierce|bash|slash|exotic <n>  (higher is better)\n\r"
        "  light      hours <n>|infinite\n\r"
        "  container  capacity <n>  container +closeable +locked  key <vnum>\n\r"
        "  drink      capacity <n>  amount <n>|full  liquid <name>  poisoned yes|no\n\r"
        "  food       hours <n>  poisoned yes|no      money  coins <n>  coin gold\n\r"
        "  potion pill scroll   spell level <n>   spells <spell> [<spell> <spell>]\n\r"
        "  wand staff           spell level <n>   charges <n>   spell <spell>\n\r"
        "  portal     portal plain|random|crystal_ball|keyed  destination <vnum>  key <vnum>\n\r"
        "  any type   v0..v4 <number>\n\r"
        "OSHOW <vnum> shows the object in these words.  ASAVE keeps changes.\n\r",
        ch );
}


/*
 * The fields one item type gives its values. Returns 1 when the field was
 * this type's and was set, 0 when it is not a value field of this type,
 * and -1 when it was but the value was refused (and said so).
 */
static int set_obj_value_field( CHAR_DATA *ch, OBJ_INDEX_DATA *o,
                                const char *field, char *value )
{
    char buf[MAX_STRING_LENGTH];
    const struct build_flag *f;
    long n;
    int t = o->item_type;

    if ( strlen( field ) < 3 && str_cmp( field, "ac" ) && str_cmp( field, "to" ) )
        return 0;

    if ( ( t == ITEM_LIGHT || t == ITEM_FOOD ) && !str_prefix( field, "hours" ) )
    {
        if ( t == ITEM_LIGHT && !str_prefix( value, "infinite" ) )
            n = 999;
        else if ( ( n = plain_number( value, 998 ) ) < 0 )
        {
            send_to_char( "Hours is a number from 0 to 998, or (for a light) "
                          "infinite.\n\r", ch );
            return -1;
        }
        o->value[t == ITEM_LIGHT ? 2 : 0] = (int) n;
        return 1;
    }

    if ( t == ITEM_WEAPON )
    {
        if ( !str_prefix( field, "class" ) )
        {
            if ( ( f = flag_find( weapon_class_names, value ) ) == NULL )
            {
                table_names( weapon_class_names, buf, sizeof(buf) );
                send_to_char( "Classes: ", ch ); send_to_char( buf, ch );
                send_to_char( "\n\r", ch );
                return -1;
            }
            o->value[0] = (int) f->bit;
            return 1;
        }
        if ( !str_prefix( field, "dice" ) || !str_prefix( field, "damage" ) )
        {
            int dn, dt, db;

            if ( !parse_dice( value, &dn, &dt, &db ) || db != 0 || dn > 100 || dt > 1000 )
            {
                send_to_char( "Weapon dice are 2d6: two six-sided dice, no bonus "
                              "(give the bonus as an affect: damroll).\n\r", ch );
                return -1;
            }
            o->value[1] = dn;
            o->value[2] = dt;
            return 1;
        }
        if ( !str_prefix( field, "attack" ) )
        {
            int at = attack_named( value );

            if ( at < 0 )
            {
                attack_list( buf, sizeof(buf) );
                send_to_char( "Attacks: ", ch ); send_to_char( buf, ch );
                send_to_char( "\n\r", ch );
                return -1;
            }
            o->value[3] = at;
            return 1;
        }
        if ( !str_prefix( field, "weapon" ) )
        {
            long bits = o->value[4];

            if ( !flag_edit( ch, weapon_flag_names, &bits, "weapon flag", value, 0, "" ) )
                return -1;
            o->value[4] = (int) bits;
            return 1;
        }
    }

    if ( ( t == ITEM_ARMOR || t == ITEM_CLOTHING )
      && ( !str_cmp( field, "ac" ) || !str_prefix( field, "armor" )
        || !str_prefix( field, "armour" ) ) )
    {
        char kind[MAX_INPUT_LENGTH];
        char *rest = one_argument( value, kind );
        int which = -1;
        int i;

        if ( !str_prefix( kind, "pierce" ) )      which = 0;
        else if ( !str_prefix( kind, "bash" ) )   which = 1;
        else if ( !str_prefix( kind, "slash" ) )  which = 2;
        else if ( !str_prefix( kind, "exotic" ) ) which = 3;
        else rest = value;
        while ( isspace( (unsigned char) *rest ) )
            rest++;
        if ( ( n = plain_number( rest, 1000 ) ) < 0 )
        {
            send_to_char( "Armour on an item is 0 or more, higher is better: ac 5, "
                          "or ac slash 8.\n\r", ch );
            return -1;
        }
        for ( i = 0; i < 4; i++ )
            if ( which < 0 || which == i )
                o->value[i] = (int) n;
        return 1;
    }

    if ( t == ITEM_CONTAINER )
    {
        if ( !str_prefix( field, "capacity" ) )
        {
            if ( ( n = plain_number( value, 100000 ) ) < 0 )
            {
                send_to_char( "Capacity is the weight it holds, a number.\n\r", ch );
                return -1;
            }
            o->value[0] = (int) n;
            return 1;
        }
        if ( !str_prefix( field, "container" ) || !str_prefix( field, "lid" ) )
        {
            long bits = o->value[1];

            if ( !flag_edit( ch, container_names, &bits, "container flag", value, 0, "" ) )
                return -1;
            o->value[1] = (int) bits;
            return 1;
        }
    }

    if ( ( t == ITEM_CONTAINER || t == ITEM_PORTAL ) && !str_cmp( field, "key" ) )
    {
        if ( ( n = plain_number( value, 32767 ) ) < 0
          || ( n != 0 && get_obj_index( (int) n ) == NULL ) )
        {
            send_to_char( "Key is the vnum of an object that exists, or 0 for "
                          "none.\n\r", ch );
            return -1;
        }
        o->value[t == ITEM_CONTAINER ? 2 : 4] = (int) n;
        return 1;
    }

    if ( t == ITEM_DRINK_CON )
    {
        if ( !str_prefix( field, "capacity" ) || !str_prefix( field, "amount" ) )
        {
            bool cap = !str_prefix( field, "capacity" );

            if ( !cap && !str_cmp( value, "full" ) )
                n = o->value[0];
            else if ( ( n = plain_number( value, 10000 ) ) < 0 )
            {
                send_to_char( "Give a number of drinks.\n\r", ch );
                return -1;
            }
            o->value[cap ? 0 : 1] = (int) n;
            if ( o->value[1] > o->value[0] )
                o->value[1] = o->value[0];
            return 1;
        }
        if ( !str_prefix( field, "liquid" ) )
        {
            int liq;

            for ( liq = 0; liq < LIQ_MAX; liq++ )
                if ( !str_prefix( value, liq_table[liq].liq_name ) )
                    break;
            if ( liq >= LIQ_MAX )
            {
                buf[0] = '\0';
                for ( liq = 0; liq < LIQ_MAX; liq++ )
                {
                    toc_strlcat( buf, " ", sizeof(buf) );
                    toc_strlcat( buf, liq_table[liq].liq_name, sizeof(buf) );
                }
                send_to_char( "Liquids:", ch ); send_to_char( buf, ch );
                send_to_char( "\n\r", ch );
                return -1;
            }
            o->value[2] = liq;
            return 1;
        }
    }

    if ( ( t == ITEM_DRINK_CON || t == ITEM_FOOD ) && !str_prefix( field, "poisoned" ) )
    {
        if ( !str_cmp( value, "yes" ) || !str_cmp( value, "on" ) )       o->value[3] = 1;
        else if ( !str_cmp( value, "no" ) || !str_cmp( value, "off" ) )  o->value[3] = 0;
        else { send_to_char( "Poisoned yes or no.\n\r", ch ); return -1; }
        return 1;
    }

    if ( t == ITEM_MONEY )
    {
        if ( !str_prefix( field, "coins" ) && str_cmp( field, "coin" ) )
        {
            if ( ( n = plain_number( value, 2000000000L ) ) < 0 )
            {
                send_to_char( "Give a number of coins.\n\r", ch );
                return -1;
            }
            o->value[0] = (int) n;
            return 1;
        }
        if ( !str_cmp( field, "coin" ) )
        {
            if ( ( f = flag_find( coin_names, value ) ) == NULL )
            {
                send_to_char( "Coin is copper, silver, gold or platinum.\n\r", ch );
                return -1;
            }
            o->value[1] = (int) f->bit;
            return 1;
        }
    }

    if ( t == ITEM_PILL || t == ITEM_POTION || t == ITEM_SCROLL
      || t == ITEM_WAND || t == ITEM_STAFF )
    {
        bool device = ( t == ITEM_WAND || t == ITEM_STAFF );

        if ( !str_prefix( field, "spell" ) || !str_prefix( field, "spells" ) )
        {
            char name[MAX_INPUT_LENGTH];
            char *rest = value;
            int sn[3] = { -1, -1, -1 };
            int i;

            /* "spell level 20" sets the level the spells are cast at. */
            rest = one_argument( value, name );
            if ( !str_cmp( name, "level" ) )
            {
                if ( ( n = plain_number( rest, 200 ) ) < 0 )
                {
                    send_to_char( "Spell level is a number from 0 to 200.\n\r", ch );
                    return -1;
                }
                o->value[0] = (int) n;
                return 1;
            }

            rest = value;
            for ( i = 0; i < ( device ? 1 : 3 ); i++ )
            {
                rest = one_argument( rest, name );
                if ( name[0] == '\0' )
                    break;
                if ( !str_cmp( name, "none" ) )
                    continue;
                if ( ( sn[i] = storable_spell( name ) ) < 0 )
                {
                    snprintf( buf, sizeof(buf), "'%s' is not a spell an item can "
                              "hold.  Quote a spell of two words: 'cure light'.\n\r",
                              name );
                    send_to_char( buf, ch );
                    return -1;
                }
            }
            if ( device )
                o->value[3] = sn[0];
            else
            {
                o->value[1] = sn[0];
                o->value[2] = sn[1];
                o->value[3] = sn[2];
            }
            return 1;
        }
        if ( device && !str_prefix( field, "charges" ) )
        {
            if ( ( n = plain_number( value, 100 ) ) < 0 )
            {
                send_to_char( "Charges is a number from 0 to 100.\n\r", ch );
                return -1;
            }
            o->value[1] = o->value[2] = (int) n;
            return 1;
        }
    }

    if ( t == ITEM_PORTAL )
    {
        if ( !str_cmp( field, "portal" ) || !str_prefix( field, "kind" ) )
        {
            if ( ( f = flag_find( portal_names, value ) ) == NULL )
            {
                send_to_char( "A portal is plain, random (costs 500 gold, goes "
                              "anywhere), crystal_ball or keyed.\n\r", ch );
                return -1;
            }
            o->value[0] = (int) f->bit;
            return 1;
        }
        if ( !str_prefix( field, "destination" ) || !str_cmp( field, "to" ) )
        {
            if ( ( n = plain_number( value, WORLD_SIZE ) ) < 0
              || get_room_index( (int) n ) == NULL )
            {
                send_to_char( "Destination is the vnum of a room that exists.\n\r", ch );
                return -1;
            }
            o->value[1] = (int) n;
            return 1;
        }
    }

    return 0;
}


/* Add, replace or take away a stat affect: "+hitroll 2", "-hitroll", "none". */
static bool obj_affect_edit( CHAR_DATA *ch, OBJ_INDEX_DATA *o, char *value )
{
    char word[MAX_INPUT_LENGTH];
    char amount[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    const struct build_flag *f;
    AFFECT_DATA *paf, *prev = NULL;
    bool remove;
    const char *name;
    int mod;

    value = one_argument( value, word );
    one_argument( value, amount );

    if ( !str_cmp( word, "none" ) )
    {
        /* Keep only the worn powers, which GRANTS owns. */
        AFFECT_DATA *keep = NULL, *last = NULL, *next;

        for ( paf = o->affected; paf != NULL; paf = next )
        {
            next = paf->next;
            if ( paf->bitvector == 0 )
                continue;
            paf->location = APPLY_NONE;
            paf->modifier = 0;
            paf->next     = NULL;
            if ( last == NULL ) keep = paf; else last->next = paf;
            last = paf;
        }
        o->affected = keep;
        return true;
    }

    remove = ( word[0] == '-' );
    name   = ( word[0] == '-' || word[0] == '+' ) ? word + 1 : word;
    if ( ( f = flag_find( apply_names, name ) ) == NULL )
    {
        table_names( apply_names, buf, sizeof(buf) );
        send_to_char( "Affects: ", ch ); send_to_char( buf, ch );
        send_to_char( "\n\r  affect +hitroll 2, affect -hitroll, affect none\n\r", ch );
        return false;
    }

    /* Find this location's affect, if there is one. */
    for ( paf = o->affected; paf != NULL; prev = paf, paf = paf->next )
        if ( paf->location == f->bit && paf->bitvector == 0 )
            break;

    if ( remove )
    {
        if ( paf == NULL )
        {
            send_to_char( "It has no such affect.\n\r", ch );
            return false;
        }
        if ( prev == NULL ) o->affected = paf->next; else prev->next = paf->next;
        return true;
    }

    if ( !is_number( amount ) || ( mod = atoi( amount ) ) == 0 || mod < -1000 || mod > 1000 )
    {
        send_to_char( "Give an amount from -1000 to 1000: affect +hitroll 2, affect "
                      "ac -10.\n\r", ch );
        return false;
    }

    if ( paf == NULL )
    {
        paf             = alloc_perm( sizeof(*paf) );
        paf->type       = -1;
        paf->duration   = -1;
        paf->bitvector  = 0;
        paf->bitvector2 = 0;
        paf->location   = (sh_int) f->bit;
        paf->next       = o->affected;
        o->affected     = paf;
        top_affect++;
    }
    paf->level    = o->level;
    paf->modifier = (sh_int) mod;
    return true;
}


/* Worn powers: "+haste -sanctuary". Each is a bit on an affect with no
   stat, written back as an F record. */
static bool obj_grants_edit( CHAR_DATA *ch, OBJ_INDEX_DATA *o, char *value )
{
    AFFECT_DATA *paf, *prev, *next;
    long bits = 0;
    long before;

    for ( paf = o->affected; paf != NULL; paf = paf->next )
        bits |= paf->bitvector;
    before = bits;

    if ( !flag_edit( ch, affect_names, &bits, "power", value, 0, "" ) )
        return false;

    /* Take away what went: clear the bits, and drop an affect left with
       neither a stat nor a power. */
    prev = NULL;
    for ( paf = o->affected; paf != NULL; paf = next )
    {
        next = paf->next;
        paf->bitvector &= (int) bits;
        if ( paf->bitvector == 0 && paf->location == APPLY_NONE )
        {
            if ( prev == NULL ) o->affected = next; else prev->next = next;
            continue;
        }
        prev = paf;
    }

    /* Add what came: one powers-only affect holds them. */
    if ( ( bits & ~before ) != 0 )
    {
        paf             = alloc_perm( sizeof(*paf) );
        paf->type       = -1;
        paf->level      = o->level;
        paf->duration   = -1;
        paf->location   = APPLY_NONE;
        paf->modifier   = 0;
        paf->bitvector  = (int) ( bits & ~before );
        paf->bitvector2 = 0;
        paf->next       = o->affected;
        o->affected     = paf;
        top_affect++;
    }
    return true;
}


/* An extra description: "detail runes The runes spell a name.", "detail
   runes + more", "detail runes none". */
static bool obj_detail_apply( CHAR_DATA *ch, OBJ_INDEX_DATA *o, const char *keyword,
                              char *value );

static bool obj_detail_edit( CHAR_DATA *ch, OBJ_INDEX_DATA *o, char *value )
{
    char keyword[MAX_INPUT_LENGTH];

    value = one_argument( value, keyword );
    while ( isspace( (unsigned char) *value ) )
        value++;
    if ( keyword[0] == '\0' || value[0] == '\0' )
    {
        send_to_char( "Syntax: detail <keyword> <text>      what LOOK <keyword> shows\n\r"
                      "        detail <keyword> + <text>    add to it\n\r"
                      "        detail <keyword> none        take it away\n\r"
                      "Quote several keywords: detail 'runes markings' <text>\n\r", ch );
        return false;
    }
    return obj_detail_apply( ch, o, keyword, value );
}

/* The detail under exactly these keywords: set, added to, or taken away. */
static bool obj_detail_apply( CHAR_DATA *ch, OBJ_INDEX_DATA *o, const char *keyword,
                              char *value )
{
    char text[2 * MAX_STRING_LENGTH];
    EXTRA_DESCR_DATA *ed, *prev = NULL;

    for ( ed = o->extra_descr; ed != NULL; prev = ed, ed = ed->next )
        if ( !str_cmp( ed->keyword, keyword ) )
            break;

    if ( !str_cmp( value, "none" ) )
    {
        if ( ed == NULL )
        {
            send_to_char( "It has no such detail.\n\r", ch );
            return false;
        }
        if ( prev == NULL ) o->extra_descr = ed->next; else prev->next = ed->next;
        return true;
    }

    text[0] = '\0';
    if ( value[0] == '+' && ed != NULL )
        toc_strlcpy( text, ed->description, sizeof(text) );
    wrap_into( value[0] == '+' ? value + 1 : value, text, sizeof(text) );
    if ( strlen( text ) >= MAX_STRING_LENGTH - 2 )
    {
        send_to_char( "That detail is too long.\n\r", ch );
        return false;
    }
    text[0] = UPPER( text[0] );

    if ( ed == NULL )
    {
        ed          = alloc_perm( sizeof(*ed) );
        ed->keyword = perm_text( ch, keyword );
        ed->next    = NULL;
        /* At the end, so details read in the order they were added. */
        if ( o->extra_descr == NULL )
            o->extra_descr = ed;
        else
        {
            EXTRA_DESCR_DATA *last = o->extra_descr;

            while ( last->next != NULL )
                last = last->next;
            last->next = ed;
        }
        top_ed++;
    }
    ed->description = perm_text( ch, text );
    return true;
}


/* Wear slots, extra flags and the second extra word, edited as one list. */
static bool obj_flags_edit( CHAR_DATA *ch, OBJ_INDEX_DATA *o, char *value )
{
    char word[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    long one = o->extra_flags;
    long two = o->extra_flags2;

    if ( value[0] == '\0' || !str_cmp( value, "none" ) )
    {
        if ( value[0] == '\0' )
        {
            table_names( extra_names, buf, sizeof(buf) );
            send_to_char( "Flags: ", ch ); send_to_char( buf, ch );
            table_names( extra2_names, buf, sizeof(buf) );
            send_to_char( " ", ch ); send_to_char( buf, ch );
            send_to_char( "\n\r", ch );
            return false;
        }
        o->extra_flags  = 0;
        o->extra_flags2 = 0;
        return true;
    }

    /* Each name belongs to one of the two words; edit each in turn. */
    for ( ; ; )
    {
        const char *name;
        char single[MAX_INPUT_LENGTH];

        value = one_argument( value, word );
        if ( word[0] == '\0' )
            break;
        name = ( word[0] == '-' || word[0] == '+' ) ? word + 1 : word;
        toc_strlcpy( single, word, sizeof(single) );
        if ( flag_find( extra_names, name ) != NULL )
        {
            if ( !flag_edit( ch, extra_names, &one, "flag", single, 0, "" ) )
                return false;
        }
        else if ( !flag_edit( ch, extra2_names, &two, "flag", single, 0, "" ) )
            return false;
    }
    o->extra_flags  = (int) one;
    o->extra_flags2 = (int) two;
    return true;
}


/*
 * SET OBJ <vnum> <field> <value>: reached from do_set when the target is a
 * number, so "set obj sword ..." still edits an object in the world.
 */
bool build_set_obj( CHAR_DATA *ch, char *argument )
{
    char arg1[MAX_INPUT_LENGTH];
    char field[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    char value[MAX_INPUT_LENGTH];
    OBJ_INDEX_DATA *o;
    const struct build_flag *f;
    long n;
    int r;

    smash_tilde( argument );
    argument = one_argument( argument, arg1 );
    argument = one_argument( argument, field );
    while ( isspace( (unsigned char) *argument ) )
        argument++;
    toc_strlcpy( value, argument, sizeof(value) );

    if ( ( o = editable_obj( ch, arg1 ) ) == NULL )
        return false;

    if ( field[0] == '\0' )
    {
        show_obj( ch, o );
        return false;
    }

    /* A field with no value only ever means "what goes here?" -- and an
       empty word is a prefix of every name to str_prefix. */
    if ( value[0] == '\0' && str_prefix( field, "flags" ) )
    {
        obj_field_help( ch );
        return false;
    }

    if ( ( r = set_obj_value_field( ch, o, field, value ) ) != 0 )
    {
        if ( r < 0 )
            return false;
    }
    else if ( !str_prefix( field, "keywords" ) || !str_cmp( field, "name" ) )
        o->name = perm_text( ch, value );
    else if ( !str_prefix( field, "short" ) )
        o->short_descr = perm_text( ch, value );
    else if ( !str_prefix( field, "long" ) )
    {
        value[0] = UPPER( value[0] );
        o->description = perm_text( ch, value );
    }
    else if ( !str_prefix( field, "material" ) )
    {
        int mat = material_lookup( value );

        if ( mat == 19 && str_prefix( value, "unknown" ) )
        {
            send_to_char( "Materials: adamantite brass bronze cloth copper food "
                          "glass gold herb iron\n\r  leather paper pill silver "
                          "'spell component' steel stone vellum wood unknown\n\r", ch );
            return false;
        }
        o->material = (sh_int) mat;
    }
    else if ( !str_prefix( field, "type" ) )
    {
        if ( ( f = flag_find( type_names, value ) ) == NULL )
        {
            table_names( type_names, buf, sizeof(buf) );
            send_to_char( "Types: ", ch ); send_to_char( buf, ch );
            send_to_char( "\n\r", ch );
            return false;
        }
        if ( o->item_type != f->bit )
        {
            int i;

            /* The old type's values mean nothing to the new one. */
            o->item_type = (sh_int) f->bit;
            for ( i = 0; i < 5; i++ )
                o->value[i] = 0;
            if ( o->item_type == ITEM_PILL || o->item_type == ITEM_POTION
              || o->item_type == ITEM_SCROLL )
                o->value[1] = o->value[2] = o->value[3] = -1;
            if ( o->item_type == ITEM_WAND || o->item_type == ITEM_STAFF )
                o->value[3] = -1;
            send_to_char( "Its values are cleared for the new type; OSHOW shows "
                          "what to set.\n\r", ch );
        }
    }
    else if ( !str_prefix( field, "level" ) )
    {
        if ( ( n = plain_number( value, 200 ) ) < 0 )
        {
            send_to_char( "Level is a number from 0 to 200.\n\r", ch );
            return false;
        }
        o->level = (sh_int) n;
    }
    else if ( !str_prefix( field, "weight" ) )
    {
        if ( ( n = plain_number( value, 30000 ) ) < 0 )
        {
            send_to_char( "Weight is a number from 0 to 30000.\n\r", ch );
            return false;
        }
        o->weight = (sh_int) n;
    }
    else if ( !str_prefix( field, "cost" ) || !str_prefix( field, "price" ) )
    {
        if ( ( n = parse_price( value ) ) < 0 )
        {
            send_to_char( "Give a price: 5g 20s, 1p, 3 gold, or a number of "
                          "copper.\n\r", ch );
            return false;
        }
        o->cost = n;
    }
    else if ( !str_prefix( field, "condition" ) )
    {
        if ( ( f = flag_find( condition_names, value ) ) == NULL )
        {
            send_to_char( "Condition: perfect good average worn damaged broken "
                          "ruined.\n\r", ch );
            return false;
        }
        o->condition = (sh_int) f->bit;
    }
    else if ( !str_prefix( field, "wear" ) )
    {
        long bits = (unsigned short) o->wear_flags;

        if ( !flag_edit( ch, wear_names, &bits, "wear slot", value, 0, "" ) )
            return false;
        o->wear_flags = (sh_int) bits;
    }
    else if ( !str_prefix( field, "flags" ) || !str_prefix( field, "extra" ) )
    {
        if ( !obj_flags_edit( ch, o, value ) )
            return false;
    }
    else if ( !str_prefix( field, "affects" ) || !str_prefix( field, "grants" )
           || !str_prefix( field, "powers" ) )
    {
        if ( prototype_worn( o ) )
        {
            send_to_char( "Somebody is wearing one of these.  Its affects come off "
                          "as they went on,\n\rso they cannot change under it: have "
                          "it taken off first.\n\r", ch );
            return false;
        }
        if ( !str_prefix( field, "affects" ) ? !obj_affect_edit( ch, o, value )
                                             : !obj_grants_edit( ch, o, value ) )
            return false;
    }
    else if ( !str_prefix( field, "details" ) )
    {
        if ( !obj_detail_edit( ch, o, value ) )
            return false;
    }
    else if ( !str_prefix( field, "description" ) )
    {
        /* What LOOK <object> shows is a detail under the object's own
           keywords; without one, LOOK repeats the long line. Passed as
           they are, not quoted into a line to be parsed again: keywords
           with an apostrophe would close the quote early (review). */
        if ( !obj_detail_apply( ch, o, o->name, value ) )
            return false;
    }
    else if ( LOWER( field[0] ) == 'v' && field[1] >= '0' && field[1] <= '4'
           && field[2] == '\0' )
    {
        if ( ( n = plain_number( value, 2000000000L ) ) < 0 )
        {
            send_to_char( "A value is a number, 0 or more.\n\r", ch );
            return false;
        }
        o->value[field[1] - '0'] = (int) n;
    }
    else
    {
        snprintf( buf, sizeof(buf), "%s has no field '%s'.\n\r",
                  enum_name( type_names, o->item_type ), field );
        send_to_char( buf, ch );
        obj_field_help( ch );
        return false;
    }

    snprintf( buf, sizeof(buf), "Object %d's %s is set.  OSHOW %d to look; ASAVE "
              "to keep it.\n\r", o->vnum, field, o->vnum );
    send_to_char( buf, ch );
    return true;
}


/*
 * ------------------------------------------------------------------------
 * Resets: PLACE, RESETS and UNPLACE.
 *
 * A reset is what makes something come back: every few minutes the game
 * walks an area's reset list and puts each mobile, object and door state
 * back as the list says. The list is order sensitive, and these commands
 * keep its order for the builder:
 *
 *  - G (give) and E (equip) act on the mobile the last M reset made, so
 *    an item for a mobile goes straight after that mobile's M and the
 *    items already given it.
 *  - P (put in) fills a container already made, so it goes straight after
 *    the O that makes the container.
 *  - M, O and D go at the end.
 *
 * reset_area runs from the top, so a reset belongs to the room of the last
 * M or O above it -- which is how RESETS lists a room's and UNPLACE takes
 * a mobile's items away with it.
 *
 * Each PLACE also does at once what the reset will do, so the builder sees
 * the mobile or the item straight away. Only an ANEW area can hold resets,
 * because ASAVE is what writes them.
 * ------------------------------------------------------------------------
 */

extern int top_reset;
extern const int16_t rev_dir[];
extern char * const dir_name[];

/* The room each reset in the list acts on, by the rule above. */
static ROOM_INDEX_DATA *reset_room( RESET_DATA *r, ROOM_INDEX_DATA *context )
{
    switch ( r->command )
    {
    case 'M':
    case 'O':
        return get_room_index( r->arg3 );
    case 'D':
    case 'R':
        return get_room_index( r->arg1 );
    default:
        return context;
    }
}


/* Does a prototype's area load no later than this one? A reset naming one
   that loads later stops the boot (see reset_is_writable in db.c). */
static bool loads_no_later( int vnum, AREA_DATA *pArea )
{
    AREA_DATA *owner = area_for_vnum( vnum );
    AREA_DATA *scan;

    if ( owner == NULL )
        return true;
    for ( scan = area_first; scan != NULL; scan = scan->next )
    {
        if ( scan == owner )
            return true;
        if ( scan == pArea )
            return false;
    }
    return false;
}


/* The room a builder may place things in, or NULL after saying why not. */
static ROOM_INDEX_DATA *placeable_room( CHAR_DATA *ch )
{
    ROOM_INDEX_DATA *room = ch->in_room;

    if ( room == NULL )
        return NULL;
    if ( !area_is_built( room->area ) )
    {
        send_to_char( "Resets are kept by ASAVE, which only an area made with ANEW "
                      "has.  Build in one.\n\r", ch );
        return NULL;
    }
    if ( !may_build_area( ch, room->area ) )
    {
        send_to_char( "You are not one of this area's builders.\n\r", ch );
        return NULL;
    }
    return room;
}


static RESET_DATA *new_reset( char command, int arg1, int arg2, int arg3 )
{
    RESET_DATA *r = alloc_perm( sizeof(*r) );

    r->command  = command;
    r->arg1     = (sh_int) arg1;
    r->arg2     = (sh_int) arg2;
    r->arg3     = (sh_int) arg3;
    r->room_max = 0;
    r->next     = NULL;
    top_reset++;
    return r;
}

static void reset_append( AREA_DATA *pArea, RESET_DATA *r )
{
    if ( pArea->reset_first == NULL )
        pArea->reset_first = r;
    if ( pArea->reset_last != NULL )
        pArea->reset_last->next = r;
    pArea->reset_last = r;
}

/*
 * The way out of this room in this direction is no longer a door (RLINK
 * OPEN), or no longer there (RLINK NONE): its 'D' resets go, or RESETS
 * would list them and the next ASAVE drop them without a word.
 */
void build_forget_door( ROOM_INDEX_DATA *room, int door )
{
    AREA_DATA *pArea;
    RESET_DATA *r, *prev = NULL, *next;

    if ( room == NULL || ( pArea = room->area ) == NULL )
        return;
    for ( r = pArea->reset_first; r != NULL; r = next )
    {
        next = r->next;
        if ( r->command == 'D' && r->arg1 == room->vnum && r->arg2 == door )
        {
            if ( prev == NULL ) pArea->reset_first = next; else prev->next = next;
            if ( pArea->reset_last == r )
                pArea->reset_last = prev;
            continue;
        }
        prev = r;
    }
}


/* A door has one state: placing it again changes the reset it has. */
static void set_door_reset( AREA_DATA *pArea, int room_vnum, int door, int state )
{
    RESET_DATA *r;

    for ( r = pArea->reset_first; r != NULL; r = r->next )
    {
        if ( r->command == 'D' && r->arg1 == room_vnum && r->arg2 == door )
        {
            r->arg3 = (sh_int) state;
            return;
        }
    }
    reset_append( pArea, new_reset( 'D', room_vnum, door, state ) );
}

static void reset_insert_after( AREA_DATA *pArea, RESET_DATA *after, RESET_DATA *r )
{
    r->next     = after->next;
    after->next = r;
    if ( pArea->reset_last == after )
        pArea->reset_last = r;
}


/* After an M is added or removed: each M's world cap is the number of M
   resets the area has for that mobile, and its room cap the number in its
   own room -- what fix_reset_room_limits works out at boot. */
static void recount_mob_resets( AREA_DATA *pArea, int vnum )
{
    RESET_DATA *r, *o;
    AREA_DATA *other;
    int in_world = 0;

    /* reset_area holds an M back once the mobile's count across the whole
       world reaches the cap, so the cap counts every area's M resets for
       it -- a shipped mobile placed here as well as in its own area would
       otherwise stop coming back after its first death (review,
       2026-10-08). */
    for ( other = area_first; other != NULL; other = other->next )
        for ( o = other->reset_first; o != NULL; o = o->next )
            if ( o->command == 'M' && o->arg1 == vnum )
                in_world++;

    for ( r = pArea->reset_first; r != NULL; r = r->next )
    {
        int in_room = 0;

        if ( r->command != 'M' || r->arg1 != vnum )
            continue;
        for ( o = pArea->reset_first; o != NULL; o = o->next )
            if ( o->command == 'M' && o->arg1 == vnum && o->arg3 == r->arg3 )
                in_room++;
        r->arg2     = (sh_int) UMAX( r->arg2, in_world );
        r->room_max = (sh_int) in_room;
    }
}


/*
 * The last M in this room for this mobile, and the last reset attached to
 * it (its own G and E resets), or NULL.
 */
static RESET_DATA *mob_reset_in_room( AREA_DATA *pArea, ROOM_INDEX_DATA *room,
                                      int mob_vnum, RESET_DATA **tail )
{
    RESET_DATA *r, *found = NULL;

    *tail = NULL;
    for ( r = pArea->reset_first; r != NULL; r = r->next )
    {
        if ( r->command == 'M' && r->arg1 == mob_vnum && r->arg3 == room->vnum )
        {
            found = r;
            *tail = r;
        }
        else if ( found != NULL && *tail != NULL
               && ( r->command == 'G' || r->command == 'E' ) && (*tail)->next == r )
            *tail = r;
    }
    return found;
}

/* The same for an O that makes a container here, and its P resets. */
static RESET_DATA *obj_reset_in_room( AREA_DATA *pArea, ROOM_INDEX_DATA *room,
                                      int obj_vnum, RESET_DATA **tail )
{
    RESET_DATA *r, *found = NULL;

    *tail = NULL;
    for ( r = pArea->reset_first; r != NULL; r = r->next )
    {
        if ( r->command == 'O' && r->arg1 == obj_vnum && r->arg3 == room->vnum )
        {
            found = r;
            *tail = r;
        }
        else if ( found != NULL && *tail != NULL && r->command == 'P'
               && (*tail)->next == r )
            *tail = r;
    }
    return found;
}


/* Where an equipped item goes, by its wear slots in WEAR's order, skipping
   a paired slot the mobile's earlier E resets have taken. */
static int equip_slot( OBJ_INDEX_DATA *o, RESET_DATA *m, RESET_DATA *tail )
{
    bool used[MAX_WEAR];
    RESET_DATA *r;
    int i;

    for ( i = 0; i < MAX_WEAR; i++ )
        used[i] = false;
    /* Only this mobile's own resets: those after its M, up to the tail. */
    for ( r = m; r != tail && r != NULL; )
    {
        r = r->next;
        if ( r != NULL && r->command == 'E' && r->arg3 >= 0 && r->arg3 < MAX_WEAR )
            used[r->arg3] = true;
    }

#define SLOT_FREE( a, b ) ( !used[a] ? (a) : ( !used[b] ? (b) : -1 ) )
    if ( o->item_type == ITEM_LIGHT )                    return SLOT_FREE( WEAR_LIGHT, WEAR_LIGHT );
    if ( IS_SET( o->wear_flags, ITEM_WEAR_FINGER ) )     return SLOT_FREE( WEAR_FINGER_L, WEAR_FINGER_R );
    if ( IS_SET( o->wear_flags, ITEM_WEAR_NECK ) )       return SLOT_FREE( WEAR_NECK_1, WEAR_NECK_2 );
    if ( IS_SET( o->wear_flags, ITEM_WEAR_BODY ) )       return SLOT_FREE( WEAR_BODY, WEAR_BODY );
    if ( IS_SET( o->wear_flags, ITEM_WEAR_HEAD ) )       return SLOT_FREE( WEAR_HEAD, WEAR_HEAD );
    if ( IS_SET( o->wear_flags, ITEM_WEAR_LEGS ) )       return SLOT_FREE( WEAR_LEGS, WEAR_LEGS );
    if ( IS_SET( o->wear_flags, ITEM_WEAR_FEET ) )       return SLOT_FREE( WEAR_FEET, WEAR_FEET );
    if ( IS_SET( o->wear_flags, ITEM_WEAR_HANDS ) )      return SLOT_FREE( WEAR_HANDS, WEAR_HANDS );
    if ( IS_SET( o->wear_flags, ITEM_WEAR_ARMS ) )       return SLOT_FREE( WEAR_ARMS, WEAR_ARMS );
    if ( IS_SET( o->wear_flags, ITEM_WEAR_ABOUT ) )      return SLOT_FREE( WEAR_ABOUT, WEAR_ABOUT );
    if ( IS_SET( o->wear_flags, ITEM_WEAR_WAIST ) )      return SLOT_FREE( WEAR_WAIST, WEAR_WAIST );
    if ( IS_SET( o->wear_flags, ITEM_WEAR_WRIST ) )      return SLOT_FREE( WEAR_WRIST_L, WEAR_WRIST_R );
    if ( IS_SET( o->wear_flags, ITEM_WEAR_SHIELD ) )     return SLOT_FREE( WEAR_SHIELD, WEAR_SHIELD );
    if ( IS_SET( o->wear_flags, ITEM_WIELD ) )           return SLOT_FREE( WEAR_WIELD, WEAR_WIELD );
    if ( IS_SET( o->wear_flags, ITEM_HOLD ) )            return SLOT_FREE( WEAR_HOLD, WEAR_HOLD );
#undef SLOT_FREE
    return -2;
}

static const char *wear_slot_word( int slot )
{
    switch ( slot )
    {
    case WEAR_LIGHT:    return "as a light";
    case WEAR_FINGER_L: return "on the left finger";
    case WEAR_FINGER_R: return "on the right finger";
    case WEAR_NECK_1:
    case WEAR_NECK_2:   return "around the neck";
    case WEAR_BODY:     return "on the torso";
    case WEAR_HEAD:     return "on the head";
    case WEAR_LEGS:     return "on the legs";
    case WEAR_FEET:     return "on the feet";
    case WEAR_HANDS:    return "on the hands";
    case WEAR_ARMS:     return "on the arms";
    case WEAR_SHIELD:   return "as a shield";
    case WEAR_ABOUT:    return "about the body";
    case WEAR_WAIST:    return "around the waist";
    case WEAR_WRIST_L:  return "on the left wrist";
    case WEAR_WRIST_R:  return "on the right wrist";
    case WEAR_WIELD:    return "wielded";
    case WEAR_HOLD:     return "held";
    }
    return "somewhere";
}


/* A mobile made from this prototype, standing in this room. */
static CHAR_DATA *mob_here( ROOM_INDEX_DATA *room, MOB_INDEX_DATA *m )
{
    CHAR_DATA *rch;

    for ( rch = room->people; rch != NULL; rch = rch->next_in_room )
        if ( IS_NPC( rch ) && rch->pIndexData == m )
            return rch;
    return NULL;
}

static OBJ_DATA *obj_here( ROOM_INDEX_DATA *room, OBJ_INDEX_DATA *o )
{
    OBJ_DATA *obj;

    for ( obj = room->contents; obj != NULL; obj = obj->next_content )
        if ( obj->pIndexData == o )
            return obj;
    return NULL;
}


static void place_help( CHAR_DATA *ch )
{
    send_to_char(
        "Syntax: place mob <vnum> [<how many>]     a mobile here, coming back\n\r"
        "        place obj <vnum>                  an object on the floor here\n\r"
        "        place obj <vnum> in <container>   inside a container placed here\n\r"
        "        place obj <vnum> on <mob>         carried by a mobile placed here\n\r"
        "        place obj <vnum> worn <mob>       worn or wielded by it\n\r"
        "        place door <dir> open|closed|locked\n\r"
        "RESETS lists what is placed here; UNPLACE <n> takes one away.  ASAVE keeps\n\r"
        "them.\n\r", ch );
}


/* PLACE -- put something in the room that comes back at every reset. */
void do_place( CHAR_DATA *ch, char *argument )
{
    char what[MAX_INPUT_LENGTH];
    char arg[MAX_INPUT_LENGTH];
    char how[MAX_INPUT_LENGTH];
    char target[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    ROOM_INDEX_DATA *room;
    AREA_DATA *pArea;

    argument = one_argument( argument, what );
    argument = one_argument( argument, arg );
    argument = one_argument( argument, how );
    one_argument( argument, target );

    if ( what[0] == '\0' || arg[0] == '\0' )
    {
        place_help( ch );
        return;
    }
    if ( ( room = placeable_room( ch ) ) == NULL )
        return;
    pArea = room->area;

    if ( !str_prefix( what, "mobile" ) )
    {
        MOB_INDEX_DATA *m;
        long count = 1;
        int i;

        if ( !is_number( arg ) || ( m = get_mob_index( atoi( arg ) ) ) == NULL )
        {
            snprintf( buf, sizeof(buf), "There is no mobile %s.\n\r", arg );
            send_to_char( buf, ch );
            return;
        }
        if ( how[0] != '\0' && ( ( count = plain_number( how, 20 ) ) < 1 ) )
        {
            send_to_char( "How many: a number from 1 to 20.\n\r", ch );
            return;
        }
        if ( !loads_no_later( m->vnum, pArea ) )
        {
            send_to_char( "That mobile's area loads after this one, so the game could "
                          "not find it\n\rwhen this area's resets are read.\n\r", ch );
            return;
        }
        for ( i = 0; i < count; i++ )
        {
            CHAR_DATA *mob;

            reset_append( pArea, new_reset( 'M', m->vnum, 1, room->vnum ) );
            mob = create_mobile( m );
            char_to_room( mob, room );
        }
        recount_mob_resets( pArea, m->vnum );
        snprintf( buf, sizeof(buf), "%s will be here%s after every reset.\n\r",
                  m->short_descr, count > 1 ? " (that many of them)" : "" );
        buf[0] = UPPER( buf[0] );
        send_to_char( buf, ch );
    }
    else if ( !str_prefix( what, "object" ) )
    {
        OBJ_INDEX_DATA *o;
        RESET_DATA *r;

        if ( !is_number( arg ) || ( o = get_obj_index( atoi( arg ) ) ) == NULL )
        {
            snprintf( buf, sizeof(buf), "There is no object %s.\n\r", arg );
            send_to_char( buf, ch );
            return;
        }
        if ( !loads_no_later( o->vnum, pArea ) )
        {
            send_to_char( "That object's area loads after this one, so the game could "
                          "not find it\n\rwhen this area's resets are read.\n\r", ch );
            return;
        }

        if ( how[0] == '\0' )
        {
            if ( !IS_SET( o->wear_flags, ITEM_TAKE ) && o->item_type != ITEM_CONTAINER
              && o->item_type != ITEM_FOUNTAIN && o->item_type != ITEM_FURNITURE
              && o->item_type != ITEM_PORTAL )
                send_to_char( "(It cannot be picked up -- no TAKE -- so it stays as "
                              "scenery.)\n\r", ch );
            reset_append( pArea, new_reset( 'O', o->vnum, 0, room->vnum ) );
            obj_to_room( create_object( o, o->level ), room );
            snprintf( buf, sizeof(buf), "%s will lie here after every reset that "
                      "finds the area empty.\n\r", o->short_descr );
        }
        else if ( !str_cmp( how, "in" ) )
        {
            OBJ_INDEX_DATA *box;
            RESET_DATA *tail;
            OBJ_DATA *box_here;

            if ( !is_number( target ) || ( box = get_obj_index( atoi( target ) ) ) == NULL
              || obj_reset_in_room( pArea, room, box->vnum, &tail ) == NULL )
            {
                send_to_char( "Name a container placed in this room: PLACE OBJ <its vnum> "
                              "first.\n\r", ch );
                return;
            }
            if ( box->item_type != ITEM_CONTAINER )
            {
                send_to_char( "That is not a container.\n\r", ch );
                return;
            }
            r = new_reset( 'P', o->vnum, 0, box->vnum );
            reset_insert_after( pArea, tail, r );
            if ( ( box_here = obj_here( room, box ) ) != NULL )
                obj_to_obj( create_object( o, o->level ), box_here );
            snprintf( buf, sizeof(buf), "%s will be put back in %s at every reset.\n\r",
                      o->short_descr, box->short_descr );
        }
        else if ( !str_cmp( how, "on" ) || !str_prefix( how, "worn" )
               || !str_prefix( how, "wear" ) || !str_prefix( how, "wielded" )
               || !str_prefix( how, "equip" ) )
        {
            MOB_INDEX_DATA *m;
            RESET_DATA *mreset, *tail;
            CHAR_DATA *mob;
            bool worn = str_cmp( how, "on" ) != 0;
            int slot = 0;

            if ( !is_number( target ) || ( m = get_mob_index( atoi( target ) ) ) == NULL
              || ( mreset = mob_reset_in_room( pArea, room, m->vnum, &tail ) ) == NULL )
            {
                send_to_char( "Name a mobile placed in this room: PLACE MOB <its vnum> "
                              "first.\n\r", ch );
                return;
            }
            if ( worn && ( slot = equip_slot( o, mreset, tail ) ) < 0 )
            {
                send_to_char( slot == -2
                    ? "It has no wear slot it can be worn in (SET OBJ ... WEAR).\n\r"
                    : "That mobile already wears something there.\n\r", ch );
                return;
            }
            r = new_reset( worn ? 'E' : 'G', o->vnum, -1, worn ? slot : 0 );
            reset_insert_after( pArea, tail, r );
            if ( ( mob = mob_here( room, m ) ) != NULL )
            {
                OBJ_DATA *obj = create_object( o, o->level );

                obj_to_char( obj, mob );
                if ( worn && get_eq_char( mob, slot ) == NULL )
                    equip_char( mob, obj, slot );
            }
            if ( worn )
                snprintf( buf, sizeof(buf), "%s will wear %s %s at every reset.\n\r",
                          m->short_descr, o->short_descr, wear_slot_word( slot ) );
            else
                snprintf( buf, sizeof(buf), "%s will carry %s at every reset.\n\r",
                          m->short_descr, o->short_descr );
        }
        else
        {
            place_help( ch );
            return;
        }
        buf[0] = UPPER( buf[0] );
        send_to_char( buf, ch );
    }
    else if ( !str_prefix( what, "door" ) || !str_prefix( what, "exit" ) )
    {
        static const struct build_flag door_states[] =
        {
            { "open", 0 }, { "closed", 1 }, { "locked", 2 }, { NULL, 0 }
        };
        const struct build_flag *state = flag_find( door_states, how );
        EXIT_DATA *pexit;
        int door;
        int sides = 1;

        for ( door = 0; door <= 9; door++ )
            if ( !str_prefix( arg, dir_name[door] ) )
                break;
        if ( door > 9 || ( pexit = room->exit[door] ) == NULL )
        {
            send_to_char( "There is no exit that way.\n\r", ch );
            return;
        }
        if ( !IS_SET( pexit->exit_info, EX_ISDOOR ) )
        {
            send_to_char( "That way is not a door.  RLINK <dir> DOOR makes it one.\n\r", ch );
            return;
        }
        if ( state == NULL )
        {
            send_to_char( "A door is placed open, closed or locked.\n\r", ch );
            return;
        }
        if ( state->bit == 2 && pexit->key <= 0 )
            send_to_char( "(It has no key: RLINK <dir> KEY <vnum> gives it one.)\n\r", ch );

        /* Doors whose state is fixed at load (secret, trapped) keep it. */
        if ( pexit->lock == 4 || pexit->lock == 5 )
        {
            send_to_char( "That door is secret or trapped, and resets that way "
                          "whatever is placed.\n\r", ch );
            return;
        }

        set_door_reset( pArea, room->vnum, door, (int) state->bit );
        REMOVE_BIT( pexit->exit_info, EX_CLOSED | EX_LOCKED );
        if ( state->bit >= 1 ) SET_BIT( pexit->exit_info, EX_CLOSED );
        if ( state->bit >= 2 ) SET_BIT( pexit->exit_info, EX_LOCKED );

        /* The far side too, when it is a door in an area this builder may
           build in -- otherwise a door locked from one side only. */
        {
            ROOM_INDEX_DATA *there = pexit->u1.to_room;
            EXIT_DATA *back;

            if ( there != NULL && ( back = there->exit[rev_dir[door]] ) != NULL
              && back->u1.to_room == room && IS_SET( back->exit_info, EX_ISDOOR )
              && area_is_built( there->area )
              && may_build_area( ch, there->area )
              && back->lock != 4 && back->lock != 5 )
            {
                set_door_reset( there->area, there->vnum, rev_dir[door], (int) state->bit );
                REMOVE_BIT( back->exit_info, EX_CLOSED | EX_LOCKED );
                if ( state->bit >= 1 ) SET_BIT( back->exit_info, EX_CLOSED );
                if ( state->bit >= 2 ) SET_BIT( back->exit_info, EX_LOCKED );
                sides = 2;
            }
        }
        snprintf( buf, sizeof(buf), "The door %s will be %s after every reset%s.\n\r",
                  dir_name[door], state->name,
                  sides == 2 ? ", from both sides" : " (this side only)" );
        send_to_char( buf, ch );
    }
    else
    {
        place_help( ch );
        return;
    }

    snprintf( buf, sizeof(buf), "%s placed %s %s in room %d.", ch->name, what, arg,
              room->vnum );
    log_string( buf );
    send_to_char( "RESETS lists this room's; ASAVE keeps them.\n\r", ch );
}


/* One reset in words, for RESETS. */
static void reset_words( RESET_DATA *r, char *out, size_t size )
{
    MOB_INDEX_DATA *m;
    OBJ_INDEX_DATA *o, *box;
    static const char *door_word[] =
        { "open", "closed", "locked", "wizlocked", "secret", "trapped" };

    switch ( r->command )
    {
    case 'M':
        m = get_mob_index( r->arg1 );
        snprintf( out, size, "mobile %d, %s", r->arg1, m ? m->short_descr : "(gone)" );
        break;
    case 'O':
        o = get_obj_index( r->arg1 );
        snprintf( out, size, "object %d, %s, on the floor", r->arg1,
                  o ? o->short_descr : "(gone)" );
        break;
    case 'P':
        o = get_obj_index( r->arg1 );
        box = get_obj_index( r->arg3 );
        snprintf( out, size, "    object %d, %s, in %s", r->arg1,
                  o ? o->short_descr : "(gone)", box ? box->short_descr : "(gone)" );
        break;
    case 'G':
        o = get_obj_index( r->arg1 );
        snprintf( out, size, "    object %d, %s, carried", r->arg1,
                  o ? o->short_descr : "(gone)" );
        break;
    case 'E':
        o = get_obj_index( r->arg1 );
        snprintf( out, size, "    object %d, %s, %s", r->arg1,
                  o ? o->short_descr : "(gone)", wear_slot_word( r->arg3 ) );
        break;
    case 'D':
        snprintf( out, size, "door %s, %s", r->arg2 >= 0 && r->arg2 <= 9
                  ? dir_name[r->arg2] : "?", r->arg3 >= 0 && r->arg3 <= 5
                  ? door_word[r->arg3] : "?" );
        break;
    case 'R':
        snprintf( out, size, "the first %d exits shuffled", r->arg2 );
        break;
    default:
        snprintf( out, size, "a '%c' reset", r->command );
        break;
    }
}


/* RESETS -- what comes back in this room, numbered for UNPLACE. */
void do_resets( CHAR_DATA *ch, char *argument )
{
    char buf[MAX_STRING_LENGTH];
    char line[512];
    ROOM_INDEX_DATA *room = ch->in_room;
    ROOM_INDEX_DATA *context = NULL;
    RESET_DATA *r;
    int n = 0;

    UNUSED_PARAM( argument );
    if ( room == NULL || room->area == NULL )
        return;

    buf[0] = '\0';
    for ( r = room->area->reset_first; r != NULL; r = r->next )
    {
        ROOM_INDEX_DATA *where = reset_room( r, context );

        if ( r->command == 'M' || r->command == 'O' )
            context = where;
        if ( where != room )
            continue;
        reset_words( r, line, sizeof(line) );
        snprintf( buf + strlen( buf ), sizeof(buf) - strlen( buf ), "%3d. %s\n\r",
                  ++n, line );
        if ( strlen( buf ) > sizeof(buf) - 200 )
        {
            toc_strlcat( buf, "  ...and more.\n\r", sizeof(buf) );
            break;
        }
    }

    if ( n == 0 )
    {
        send_to_char( "Nothing is placed in this room.  PLACE puts something here.\n\r", ch );
        return;
    }
    page_to_char( buf, ch );
}


/* UNPLACE <n> -- take a reset out of this room, and a mobile's or
   container's own resets with it. What is in the room now stays. */
void do_unplace( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    char line[512];
    ROOM_INDEX_DATA *room;
    ROOM_INDEX_DATA *context = NULL;
    AREA_DATA *pArea;
    RESET_DATA *r, *prev = NULL, *target = NULL, *target_prev = NULL;
    int n = 0, want, removed = 0, mob_vnum = 0;

    one_argument( argument, arg );
    if ( !is_number( arg ) || ( want = atoi( arg ) ) < 1 )
    {
        send_to_char( "Syntax: unplace <number>   (the number RESETS shows)\n\r", ch );
        return;
    }
    if ( ( room = placeable_room( ch ) ) == NULL )
        return;
    pArea = room->area;

    for ( r = pArea->reset_first; r != NULL; prev = r, r = r->next )
    {
        ROOM_INDEX_DATA *where = reset_room( r, context );

        if ( r->command == 'M' || r->command == 'O' )
            context = where;
        if ( where == room && ++n == want )
        {
            target      = r;
            target_prev = prev;
            break;
        }
    }
    if ( target == NULL )
    {
        send_to_char( "There is no reset with that number here.  RESETS lists them.\n\r", ch );
        return;
    }

    reset_words( target, line, sizeof(line) );

    /* Unlink it, and what hangs off it: a mobile's G and E, a container's
       P -- the resets straight after it that act on what it made. */
    {
        char kind = target->command;
        RESET_DATA *next = target->next;

        if ( kind == 'M' )
            mob_vnum = target->arg1;
        if ( target_prev == NULL ) pArea->reset_first = next;
        else                       target_prev->next  = next;
        if ( pArea->reset_last == target )
            pArea->reset_last = target_prev;
        removed = 1;

        while ( next != NULL
             && ( ( kind == 'M' && ( next->command == 'G' || next->command == 'E' ) )
               || ( kind == 'O' && next->command == 'P' ) ) )
        {
            RESET_DATA *after = next->next;

            if ( target_prev == NULL ) pArea->reset_first = after;
            else                       target_prev->next  = after;
            if ( pArea->reset_last == next )
                pArea->reset_last = target_prev;
            removed++;
            next = after;
        }
    }

    if ( mob_vnum != 0 )
        recount_mob_resets( pArea, mob_vnum );

    snprintf( buf, sizeof(buf), "Taken out: %s%s.  What is in the room now stays until "
              "it is purged.\n\r", line,
              removed > 1 ? " and what it carried or held" : "" );
    send_to_char( buf, ch );
}


/*
 * ------------------------------------------------------------------------
 * BUILD: the guided builder.
 *
 * For a builder who would rather be asked than remember syntax. BUILD
 * AREA, BUILD ROOM, BUILD MOB and BUILD OBJ each ask one question at a
 * time, and every answer goes through the very commands a builder could
 * type -- ANEW, GOTO, RLINK, MCREATE, SET MOB, SET OBJ, PLACE, ASAVE --
 * so the wizard can never make something those would refuse. A refused
 * answer is refused in the command's own words and the question is asked
 * again; a blank answer keeps what is there.
 *
 * While a build is under way, comm.c hands every typed line here before
 * anything else (and before the line is split on semicolons, which a
 * description may well contain). CANCEL stops; a line beginning with "/"
 * runs as an ordinary command, so LOOK or SAY need not end the build.
 * ------------------------------------------------------------------------
 */

#define WIZ_AREA  1
#define WIZ_ROOM  2
#define WIZ_MOB   3
#define WIZ_OBJ   4

/* What a question does with its answer. */
#define Q_VNUM      1   /* which vnum to make it at                       */
#define Q_COPY      2   /* blank, or a copy of a vnum                     */
#define Q_SET       3   /* SET MOB/OBJ <vnum> <field> <answer>            */
#define Q_DESC      4   /* description, a line at a time, "." to end      */
#define Q_MORE      5   /* "<field> <value>" until a blank line           */
#define Q_PLACE     6   /* make it come back here                         */
#define Q_SAVE      7   /* ASAVE                                          */
#define Q_ROOMNAME  8
#define Q_ROOMDESC  9
#define Q_SECTOR    10
#define Q_EXIT      11  /* dig a way out, or finish                       */
#define Q_AREASIZE  12
#define Q_AREANAME  13
#define Q_END       0

struct wiz_q
{
    int         kind;
    int         item_type;      /* objects: the type it is asked for; 0 any */
    const char *field;
    const char *ask;
};

static const struct wiz_q wiz_area_steps[] =
{
    { Q_AREASIZE, 0, NULL,
      "How many rooms will it have, roughly?  [20]  (It gets room to grow.)" },
    { Q_AREANAME, 0, NULL,
      "What is the area called?  e.g. The Sunken Grotto" },
    { Q_END, 0, NULL, NULL }
};

static const struct wiz_q wiz_room_steps[] =
{
    { Q_ROOMNAME, 0, NULL,
      "What is this room called?  e.g. The Mouth of the Grotto" },
    { Q_ROOMDESC, 0, NULL,
      "Describe it, a line at a time.  A line with only a . on it ends the\n\r"
      "description; an empty one keeps what is there." },
    { Q_SECTOR, 0, NULL,
      "What kind of ground is it?  inside city field forest hills mountain\n\r"
      "water_swim water_noswim underwater air desert underground  [Enter keeps it]" },
    { Q_EXIT, 0, NULL,
      "Dig a way out?  Give a direction (north, up, southeast...) to dig a new\n\r"
      "room that way, or press Enter to finish." },
    { Q_SAVE, 0, NULL, "Save the area now?  (yes/no)  [yes]" },
    { Q_END, 0, NULL, NULL }
};

static const struct wiz_q wiz_mob_steps[] =
{
    { Q_VNUM, 0, NULL, "Which vnum should it have?" },
    { Q_COPY, 0, NULL,
      "Start from a copy of an existing mobile?  Give its vnum, or press Enter\n\r"
      "for a blank one." },
    { Q_SET, 0, "keywords", "What will players call it?  e.g. dwarf smith" },
    { Q_SET, 0, "short", "How does it read in a sentence?  e.g. a burly dwarf smith" },
    { Q_SET, 0, "long",
      "What line shows it in the room?  e.g. A burly dwarf smith works here." },
    { Q_DESC, 0, NULL,
      "What does LOOK at it show?  A line at a time; a line with only a . ends\n\r"
      "it, and an empty one keeps what is there." },
    { Q_SET, 0, "race", "What race?  human elf dwarf giant dragon wolf ...  [Enter keeps it]" },
    { Q_SET, 0, "sex", "Male, female or neutral?  [Enter keeps it]" },
    { Q_SET, 0, "level", "What level?  [Enter keeps it]" },
    { Q_SET, 0, "alignment", "Good, neutral or evil?  [Enter keeps it]" },
    { Q_SET, 0, "attack", "How does it hit?  punch slash bite claw pound ...  [Enter keeps it]" },
    { Q_MORE, 0, NULL,
      "Anything else?  Give a field and a value -- act +aggressive, hp 4d10+80,\n\r"
      "offense +parry, special cast_mage (HELP MSHOW lists them) -- or press\n\r"
      "Enter to finish." },
    { Q_PLACE, 0, NULL,
      "Place it in this room, so it is here after every reset?  (yes/no)  [yes]" },
    { Q_SAVE, 0, NULL, "Save the area now?  (yes/no)  [yes]" },
    { Q_END, 0, NULL, NULL }
};

static const struct wiz_q wiz_obj_steps[] =
{
    { Q_VNUM, 0, NULL, "Which vnum should it have?" },
    { Q_COPY, 0, NULL,
      "Start from a copy of an existing object?  Give its vnum, or press Enter\n\r"
      "for a blank one." },
    { Q_SET, 0, "keywords", "What will players call it?  e.g. sword runed" },
    { Q_SET, 0, "short", "How does it read in a sentence?  e.g. a runed sword" },
    { Q_SET, 0, "long",
      "What line shows it on the ground?  e.g. A runed sword lies here." },
    { Q_DESC, 0, NULL,
      "What does LOOK at it show?  A line at a time; a line with only a . ends\n\r"
      "it, and an empty one keeps what is there." },
    { Q_SET, 0, "type",
      "What kind of thing is it?  weapon armor clothing light container drink\n\r"
      "food potion pill scroll wand staff treasure key ...  [Enter keeps it]" },
    { Q_SET, ITEM_WEAPON, "class",
      "What kind of weapon?  sword dagger axe mace spear flail whip polearm bow" },
    { Q_SET, ITEM_WEAPON, "dice",   "Its damage dice?  e.g. 2d6" },
    { Q_SET, ITEM_WEAPON, "attack", "How does it hit?  slash pierce pound ..." },
    { Q_SET, ITEM_ARMOR, "ac",      "How much armour does it give?  e.g. 5 (higher is better)" },
    { Q_SET, ITEM_CLOTHING, "ac",   "How much armour does it give?  e.g. 1 (higher is better)" },
    { Q_SET, ITEM_LIGHT, "hours",   "How many hours does it burn?  A number, or infinite." },
    { Q_SET, ITEM_CONTAINER, "capacity", "How much weight does it hold?  e.g. 100" },
    { Q_SET, ITEM_CONTAINER, "container",
      "A lid?  +closeable +closed +locked +pickproof, or Enter for none" },
    { Q_SET, ITEM_DRINK_CON, "liquid",   "What is in it?  water beer wine ale milk ..." },
    { Q_SET, ITEM_DRINK_CON, "capacity", "How many drinks does it hold?  e.g. 10" },
    { Q_SET, ITEM_DRINK_CON, "amount",   "How full is it?  A number, or full." },
    { Q_SET, ITEM_FOOD, "hours",    "How many hours does it fill you for?  e.g. 6" },
    { Q_SET, ITEM_MONEY, "coins",   "How many coins?" },
    { Q_SET, ITEM_MONEY, "coin",    "Copper, silver, gold or platinum?" },
    { Q_SET, ITEM_POTION, "spells", "Which spells?  e.g. 'cure light' armor" },
    { Q_SET, ITEM_PILL, "spells",   "Which spells?  e.g. 'cure light' armor" },
    { Q_SET, ITEM_SCROLL, "spells", "Which spells?  e.g. 'cure light' armor" },
    { Q_SET, ITEM_WAND, "spell",    "Which spell?  e.g. 'magic missile'" },
    { Q_SET, ITEM_STAFF, "spell",   "Which spell?  e.g. 'magic missile'" },
    { Q_SET, ITEM_WAND, "charges",  "How many charges?" },
    { Q_SET, ITEM_STAFF, "charges", "How many charges?" },
    { Q_SET, 0, "wear",
      "Where is it worn?  +take lets it be picked up; then +wield +hold +finger\n\r"
      "+neck +torso +head +legs +feet +hands +arms +shield +waist +wrist  [Enter keeps it]" },
    { Q_SET, 0, "level",  "What level is it for?  [Enter keeps it]" },
    { Q_SET, 0, "weight", "How heavy is it?  [Enter keeps it]" },
    { Q_SET, 0, "cost",   "What is it worth?  e.g. 5g 20s  [Enter keeps it]" },
    { Q_MORE, 0, NULL,
      "Anything else?  Give a field and a value -- affect +hitroll 2, grants\n\r"
      "+haste, flags +glow, detail runes They read... (HELP OSHOW lists them) --\n\r"
      "or press Enter to finish." },
    { Q_PLACE, 0, NULL,
      "Place it so it comes back?  floor, on <mobile vnum>, worn <mobile vnum>,\n\r"
      "in <container vnum>, or no.  [no]" },
    { Q_SAVE, 0, NULL, "Save the area now?  (yes/no)  [yes]" },
    { Q_END, 0, NULL, NULL }
};

static const struct build_flag sector_names[] =
{
    { "inside",       SECT_INSIDE       }, { "city",        SECT_CITY        },
    { "field",        SECT_FIELD        }, { "forest",      SECT_FOREST      },
    { "hills",        SECT_HILLS        }, { "mountain",    SECT_MOUNTAIN    },
    { "water_swim",   SECT_WATER_SWIM   }, { "water_noswim", SECT_WATER_NOSWIM },
    { "underwater",   SECT_UNDER_WATER  }, { "air",         SECT_AIR         },
    { "desert",       SECT_DESERT       }, { "underground", SECT_UNDERGROUND },
    { NULL, 0 }
};


static const struct wiz_q *wiz_steps( int kind )
{
    switch ( kind )
    {
    case WIZ_AREA: return wiz_area_steps;
    case WIZ_ROOM: return wiz_room_steps;
    case WIZ_MOB:  return wiz_mob_steps;
    case WIZ_OBJ:  return wiz_obj_steps;
    }
    return NULL;
}

bool build_wizard_active( CHAR_DATA *ch )
{
    return ch != NULL && !IS_NPC( ch ) && ch->pcdata != NULL
        && ch->pcdata->wizard_kind != 0;
}

void build_wizard_clear( CHAR_DATA *ch )
{
    if ( ch == NULL || IS_NPC( ch ) || ch->pcdata == NULL )
        return;
    ch->pcdata->wizard_kind  = 0;
    ch->pcdata->wizard_step  = 0;
    ch->pcdata->wizard_vnum  = 0;
    ch->pcdata->wizard_extra = 0;
}


/* Whether this question is one to ask now: an object's value questions
   are asked only for the type it has become. */
static bool wiz_applies( CHAR_DATA *ch, const struct wiz_q *q )
{
    OBJ_INDEX_DATA *o;

    if ( q->item_type == 0 )
        return true;
    o = get_obj_index( ch->pcdata->wizard_vnum );
    return o != NULL && o->item_type == q->item_type;
}

/* Ask the question the build is on, skipping any that do not apply; at
   the end of the list, the build is done. */
static void wiz_ask( CHAR_DATA *ch )
{
    const struct wiz_q *steps = wiz_steps( ch->pcdata->wizard_kind );
    char buf[MAX_STRING_LENGTH];

    if ( steps == NULL )
    {
        build_wizard_clear( ch );
        return;
    }

    while ( steps[ch->pcdata->wizard_step].kind != Q_END
         && !wiz_applies( ch, &steps[ch->pcdata->wizard_step] ) )
        ch->pcdata->wizard_step++;

    if ( steps[ch->pcdata->wizard_step].kind == Q_END )
    {
        int vnum = ch->pcdata->wizard_vnum;
        int kind = ch->pcdata->wizard_kind;

        build_wizard_clear( ch );
        if ( kind == WIZ_MOB )
            snprintf( buf, sizeof(buf), "Done.  Mobile %d is built: MSHOW %d to read it, "
                      "SET MOB %d to change it.\n\r", vnum, vnum, vnum );
        else if ( kind == WIZ_OBJ )
            snprintf( buf, sizeof(buf), "Done.  Object %d is built: OSHOW %d to read it, "
                      "SET OBJ %d to change it.\n\r", vnum, vnum, vnum );
        else
            snprintf( buf, sizeof(buf), "Done.  BUILD ROOM builds where you stand, "
                      "BUILD MOB and BUILD OBJ fill it.\n\r" );
        send_to_char( buf, ch );
        return;
    }

    if ( steps[ch->pcdata->wizard_step].kind == Q_VNUM && ch->pcdata->wizard_vnum > 0 )
        snprintf( buf, sizeof(buf), "\n\r%s  [%d]\n\r",
                  steps[ch->pcdata->wizard_step].ask, ch->pcdata->wizard_vnum );
    else
        snprintf( buf, sizeof(buf), "\n\r%s\n\r", steps[ch->pcdata->wizard_step].ask );
    send_to_char( buf, ch );
}

static void wiz_next( CHAR_DATA *ch )
{
    ch->pcdata->wizard_step++;
    ch->pcdata->wizard_extra = 0;
    wiz_ask( ch );
}


/* The first free mobile, object or room vnum in an area's range, or 0. */
static int wiz_free_vnum( AREA_DATA *pArea, int kind )
{
    int vnum;

    if ( !area_is_built( pArea ) )
        return 0;
    for ( vnum = pArea->min_vnum; vnum <= pArea->max_vnum; vnum++ )
    {
        if ( kind == WIZ_MOB && get_mob_index( vnum ) == NULL )
            return vnum;
        if ( kind == WIZ_OBJ && get_obj_index( vnum ) == NULL )
            return vnum;
        if ( kind == WIZ_ROOM && get_room_index( vnum ) == NULL )
            return vnum;
    }
    return 0;
}

/* A room vnum to dig to from here: the next free one in this area's range,
   or for the workshop the next free one above this room. */
static int wiz_dig_vnum( ROOM_INDEX_DATA *here )
{
    int vnum;

    if ( area_is_built( here->area ) )
        return wiz_free_vnum( here->area, WIZ_ROOM );
    for ( vnum = here->vnum + 1; vnum <= WORLD_SIZE; vnum++ )
        if ( get_room_index( vnum ) == NULL && area_for_vnum( vnum ) == NULL )
            return vnum;
    return 0;
}


/*
 * A free block of `size' vnums for a new area: no room, mobile or object
 * in it, and clear of every area's declared range and of the span of
 * every area's rooms -- a gap inside a shipped area's numbers is that
 * area's, not free. 0 when there is none.
 */
static int wiz_free_block( int size )
{
    static bool used[WORLD_SIZE + 1];
    AREA_DATA *pArea;
    int vnum, run = 0;

    memset( used, 0, sizeof(used) );
    for ( vnum = 1; vnum <= WORLD_SIZE; vnum++ )
        if ( get_room_index( vnum ) != NULL || get_mob_index( vnum ) != NULL
          || get_obj_index( vnum ) != NULL )
            used[vnum] = true;

    for ( pArea = area_first; pArea != NULL; pArea = pArea->next )
    {
        int lo = WORLD_SIZE + 1, hi = 0, v;

        if ( pArea->min_vnum > 0 )
        {
            lo = pArea->min_vnum;
            hi = UMIN( pArea->max_vnum, WORLD_SIZE );
        }
        for ( v = 1; v <= WORLD_SIZE; v++ )
        {
            ROOM_INDEX_DATA *room = get_room_index( v );

            if ( room != NULL && room->area == pArea )
            {
                lo = UMIN( lo, v );
                hi = UMAX( hi, v );
            }
        }
        for ( v = lo; v <= hi; v++ )
            used[v] = true;
    }

    /* From 1000 up: the low numbers are the old world's. */
    for ( vnum = 1000; vnum <= WORLD_SIZE; vnum++ )
    {
        run = used[vnum] ? 0 : run + 1;
        if ( run == size )
            return vnum - size + 1;
    }
    return 0;
}


/* Hand a line to the editor for the prototype being built. */
static bool wiz_set( CHAR_DATA *ch, const char *field, const char *value )
{
    char cmd[MAX_STRING_LENGTH];

    snprintf( cmd, sizeof(cmd), "%d %s %s", ch->pcdata->wizard_vnum, field, value );
    return ch->pcdata->wizard_kind == WIZ_MOB ? build_set_mob( ch, cmd )
                                              : build_set_obj( ch, cmd );
}

static bool wiz_yes( const char *answer, bool dflt )
{
    if ( answer[0] == '\0' )
        return dflt;
    return !str_prefix( answer, "yes" );
}


/* Start the room questions for the room the builder is standing in. */
static void wiz_start_room( CHAR_DATA *ch )
{
    char buf[MAX_STRING_LENGTH];

    ch->pcdata->wizard_kind  = WIZ_ROOM;
    ch->pcdata->wizard_step  = 0;
    ch->pcdata->wizard_vnum  = ch->in_room->vnum;
    ch->pcdata->wizard_extra = 0;
    snprintf( buf, sizeof(buf), "Building room %d.  CANCEL stops; /<command> runs "
              "a command meanwhile.\n\r", ch->in_room->vnum );
    send_to_char( buf, ch );
    wiz_ask( ch );
}


/* One answer, to the question the build is on. */
void build_wizard_input( CHAR_DATA *ch, const char *line )
{
    char answer[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    const struct wiz_q *steps, *q;
    size_t len;

    if ( !build_wizard_active( ch ) )
        return;

    while ( isspace( (unsigned char) *line ) )
        line++;
    toc_strlcpy( answer, line, sizeof(answer) );
    len = strlen( answer );
    while ( len > 0 && isspace( (unsigned char) answer[len - 1] ) )
        answer[--len] = '\0';
    smash_tilde( answer );

    if ( !str_cmp( answer, "cancel" ) )
    {
        build_wizard_clear( ch );
        send_to_char( "Build stopped.  What it made so far stays; ASAVE keeps it.\n\r", ch );
        return;
    }
    if ( answer[0] == '/' )
    {
        interpret( ch, answer + 1 );
        if ( build_wizard_active( ch ) )
            wiz_ask( ch );
        return;
    }

    steps = wiz_steps( ch->pcdata->wizard_kind );
    if ( steps == NULL )
    {
        build_wizard_clear( ch );
        return;
    }
    q = &steps[ch->pcdata->wizard_step];

    /*
     * A room build works on the room it started in, and only that one.
     * Its answers write to ch->in_room, and a /GOTO, a teleport trap, a
     * flee or a summons can move the builder between questions -- after
     * which the next answer would have renamed whatever room they landed
     * in, the Temple included (review, 2026-10-08). So the room must
     * still be the one being built, and still be one they may edit.
     */
    if ( ch->pcdata->wizard_kind == WIZ_ROOM
      && ( ch->in_room == NULL || ch->in_room->vnum != ch->pcdata->wizard_vnum
        || !may_edit_room( ch, ch->in_room ) ) )
    {
        snprintf( buf, sizeof(buf), "You are no longer in room %d, so that build has "
                  "stopped.  BUILD ROOM there to\n\rcarry on; ASAVE keeps what is "
                  "done.\n\r", ch->pcdata->wizard_vnum );
        send_to_char( buf, ch );
        build_wizard_clear( ch );
        return;
    }

    switch ( q->kind )
    {
    case Q_AREASIZE:
    {
        long rooms = answer[0] == '\0' ? 20 : plain_number( answer, 1000 );

        if ( rooms < 1 )
        {
            send_to_char( "A number of rooms, from 1 to 1000.\n\r", ch );
            return;
        }
        /* Twice that, in tens: room to grow, and a range easy to read. */
        ch->pcdata->wizard_extra = (int) UMAX( 10, ( ( rooms * 2 + 9 ) / 10 ) * 10 );
        ch->pcdata->wizard_step++;
        wiz_ask( ch );
        return;
    }

    case Q_AREANAME:
    {
        char cmd[MAX_STRING_LENGTH];
        int size = UMAX( 10, ch->pcdata->wizard_extra );
        int lo;

        if ( answer[0] == '\0' )
        {
            send_to_char( "It needs a name.\n\r", ch );
            return;
        }
        if ( ( lo = wiz_free_block( size ) ) == 0 )
        {
            send_to_char( "There is no free block of vnums that size.  Try fewer rooms, "
                          "or ANEW a range by hand.\n\r", ch );
            build_wizard_clear( ch );
            return;
        }
        snprintf( cmd, sizeof(cmd), "%d %d %s", lo, lo + size - 1, answer );
        do_anew( ch, cmd );
        if ( area_for_vnum( lo ) == NULL )
        {
            /* ANEW said why. */
            build_wizard_clear( ch );
            return;
        }
        snprintf( cmd, sizeof(cmd), "%d", lo );
        do_goto( ch, cmd );
        if ( ch->in_room == NULL || ch->in_room->vnum != lo )
        {
            build_wizard_clear( ch );
            return;
        }
        wiz_start_room( ch );
        return;
    }

    case Q_ROOMNAME:
        if ( answer[0] != '\0' )
        {
            free_string( ch->in_room->name );
            ch->in_room->name = str_dup( answer );
        }
        wiz_next( ch );
        return;

    case Q_ROOMDESC:
    {
        char text[2 * MAX_STRING_LENGTH];

        if ( !str_cmp( answer, "." ) || ( answer[0] == '\0' ) )
        {
            wiz_next( ch );
            return;
        }
        text[0] = '\0';
        if ( ch->pcdata->wizard_extra > 0 )
            toc_strlcpy( text, ch->in_room->description, sizeof(text) );
        wrap_into( answer, text, sizeof(text) );
        if ( strlen( text ) >= MAX_STRING_LENGTH - 2 )
        {
            send_to_char( "That is as long as a description can be.\n\r", ch );
            wiz_next( ch );
            return;
        }
        text[0] = UPPER( text[0] );
        free_string( ch->in_room->description );
        ch->in_room->description = str_dup( text );
        ch->pcdata->wizard_extra++;
        send_to_char( "  (more, or . to end)\n\r", ch );
        return;
    }

    case Q_SECTOR:
    {
        const struct build_flag *f;

        if ( answer[0] != '\0' )
        {
            if ( ( f = flag_find( sector_names, answer ) ) == NULL )
            {
                send_to_char( "Not a kind of ground I know.\n\r", ch );
                return;
            }
            ch->in_room->sector_type = (sh_int) f->bit;
        }
        wiz_next( ch );
        return;
    }

    case Q_EXIT:
    {
        char cmd[MAX_INPUT_LENGTH];
        int door, to;

        if ( answer[0] == '\0' || !str_cmp( answer, "no" ) )
        {
            wiz_next( ch );
            return;
        }
        for ( door = 0; door <= 9; door++ )
            if ( !str_prefix( answer, dir_name[door] ) )
                break;
        if ( door > 9 )
        {
            send_to_char( "That is not a direction.\n\r", ch );
            return;
        }
        if ( ch->in_room->exit[door] != NULL )
        {
            send_to_char( "There is a way that way already.\n\r", ch );
            return;
        }
        if ( ( to = wiz_dig_vnum( ch->in_room ) ) == 0 )
        {
            send_to_char( "This area has no vnums left for a room.\n\r", ch );
            wiz_next( ch );
            return;
        }
        snprintf( cmd, sizeof(cmd), "%s %d", dir_name[door], to );
        do_rlink( ch, cmd );
        if ( ch->in_room->exit[door] == NULL )
            return;
        /* Walk through and build the new room the same way. */
        snprintf( cmd, sizeof(cmd), "%d", to );
        do_goto( ch, cmd );
        wiz_start_room( ch );
        return;
    }

    case Q_VNUM:
    {
        int vnum = ch->pcdata->wizard_vnum;
        bool taken;

        if ( answer[0] != '\0' )
        {
            if ( !is_number( answer ) || strlen( answer ) > 5 )
            {
                send_to_char( "A vnum is a number.\n\r", ch );
                return;
            }
            vnum = atoi( answer );
        }
        taken = ch->pcdata->wizard_kind == WIZ_MOB ? get_mob_index( vnum ) != NULL
                                                   : get_obj_index( vnum ) != NULL;
        if ( vnum <= 0 || area_for_vnum( vnum ) == NULL
          || !may_build_area( ch, area_for_vnum( vnum ) ) )
        {
            send_to_char( "That vnum is not in an area you can build in.\n\r", ch );
            return;
        }
        if ( taken )
        {
            send_to_char( "Something already has that vnum.\n\r", ch );
            return;
        }
        ch->pcdata->wizard_vnum = vnum;
        wiz_next( ch );
        return;
    }

    case Q_COPY:
    {
        char cmd[MAX_INPUT_LENGTH];

        if ( answer[0] != '\0' && !is_number( answer ) )
        {
            send_to_char( "Give a vnum to copy, or press Enter for a blank one.\n\r", ch );
            return;
        }
        snprintf( cmd, sizeof(cmd), "%d %s", ch->pcdata->wizard_vnum, answer );
        if ( ch->pcdata->wizard_kind == WIZ_MOB )
            do_mcreate( ch, cmd );
        else
            do_ocreate( ch, cmd );
        if ( ( ch->pcdata->wizard_kind == WIZ_MOB
               ? (void *) get_mob_index( ch->pcdata->wizard_vnum )
               : (void *) get_obj_index( ch->pcdata->wizard_vnum ) ) == NULL )
            return;     /* MCREATE/OCREATE said why; ask again */
        wiz_next( ch );
        return;
    }

    case Q_SET:
        if ( answer[0] != '\0' && !wiz_set( ch, q->field, answer ) )
            return;     /* refused in SET's own words; ask again */
        wiz_next( ch );
        return;

    case Q_DESC:
    {
        char value[MAX_INPUT_LENGTH + 4];

        if ( !str_cmp( answer, "." ) || answer[0] == '\0' )
        {
            wiz_next( ch );
            return;
        }
        snprintf( value, sizeof(value), "%s%s",
                  ch->pcdata->wizard_extra > 0 ? "+ " : "", answer );
        if ( wiz_set( ch, "desc", value ) )
            ch->pcdata->wizard_extra++;
        send_to_char( "  (more, or . to end)\n\r", ch );
        return;
    }

    case Q_MORE:
    {
        char field[MAX_INPUT_LENGTH];
        const char *rest;

        if ( answer[0] == '\0' || !str_cmp( answer, "done" ) )
        {
            wiz_next( ch );
            return;
        }
        rest = one_argument( answer, field );
        wiz_set( ch, field, rest );
        send_to_char( "  (another, or Enter to finish)\n\r", ch );
        return;
    }

    case Q_PLACE:
    {
        char cmd[MAX_INPUT_LENGTH];

        if ( ch->pcdata->wizard_kind == WIZ_MOB )
        {
            if ( wiz_yes( answer, true ) )
            {
                snprintf( cmd, sizeof(cmd), "mob %d", ch->pcdata->wizard_vnum );
                do_place( ch, cmd );
            }
        }
        else if ( answer[0] != '\0' && str_cmp( answer, "no" ) )
        {
            if ( !str_prefix( answer, "floor" ) )
                snprintf( cmd, sizeof(cmd), "obj %d", ch->pcdata->wizard_vnum );
            else
                snprintf( cmd, sizeof(cmd), "obj %d %s", ch->pcdata->wizard_vnum, answer );
            do_place( ch, cmd );
        }
        wiz_next( ch );
        return;
    }

    case Q_SAVE:
        if ( wiz_yes( answer, true ) )
        {
            /* The area being built: the room's (checked above for a room
               build), or the one the new mobile or object belongs to --
               not wherever the builder has wandered. */
            AREA_DATA *pArea = ch->pcdata->wizard_kind == WIZ_ROOM
                             ? ch->in_room->area
                             : area_for_vnum( ch->pcdata->wizard_vnum );

            if ( pArea == NULL )
                send_to_char( "There is no area to save.\n\r", ch );
            else if ( area_is_built( pArea ) )
            {
                if ( pArea == ch->in_room->area )
                    do_asave( ch, "" );
                else
                    do_asave( ch, pArea->name );
            }
            else if ( pArea == ch->in_room->area )
                do_rsave( ch, "confirm" );
        }
        wiz_next( ch );
        return;
    }

    snprintf( buf, sizeof(buf), "The build lost its place; it has stopped.\n\r" );
    send_to_char( buf, ch );
    build_wizard_clear( ch );
}


/* BUILD -- start a guided build. */
void do_build( CHAR_DATA *ch, char *argument )
{
    char arg[MAX_INPUT_LENGTH];
    AREA_DATA *here;

    if ( IS_NPC( ch ) || ch->pcdata == NULL || ch->in_room == NULL )
        return;

    one_argument( argument, arg );
    here = ch->in_room->area;

    if ( arg[0] == '\0' )
    {
        send_to_char(
            "BUILD asks you what you want, a question at a time, and builds it.\n\r"
            "  build area     a new area of your own, and its first room\n\r"
            "  build room     the room you are standing in, and rooms beyond it\n\r"
            "  build mob      a mobile for the area you are in\n\r"
            "  build obj      an object for the area you are in\n\r"
            "Press Enter to keep an answer, CANCEL to stop, and start a line with /\n\r"
            "to run a command along the way (/look).  HELP BUILDING has the rest.\n\r",
            ch );
        return;
    }

    if ( build_wizard_active( ch ) )
        build_wizard_clear( ch );

    if ( !str_prefix( arg, "area" ) )
    {
        ch->pcdata->wizard_kind = WIZ_AREA;
        ch->pcdata->wizard_step = 0;
        send_to_char( "A new area.  CANCEL stops at any question.\n\r", ch );
        wiz_ask( ch );
        return;
    }

    if ( !str_prefix( arg, "room" ) )
    {
        if ( !may_edit_room( ch, ch->in_room ) )
        {
            send_to_char( "This room is not yours to build: BUILD AREA makes a "
                          "place of your own.\n\r", ch );
            return;
        }
        wiz_start_room( ch );
        return;
    }

    if ( !str_prefix( arg, "mobile" ) || !str_prefix( arg, "object" ) )
    {
        int kind = !str_prefix( arg, "mobile" ) ? WIZ_MOB : WIZ_OBJ;

        if ( !area_is_built( here ) || !may_build_area( ch, here ) )
        {
            send_to_char( "Stand in an area you built (BUILD AREA makes one) -- "
                          "the new one goes in its range.\n\r", ch );
            return;
        }
        ch->pcdata->wizard_kind  = kind;
        ch->pcdata->wizard_step  = 0;
        ch->pcdata->wizard_vnum  = wiz_free_vnum( here, kind );
        ch->pcdata->wizard_extra = 0;
        if ( ch->pcdata->wizard_vnum == 0 )
        {
            build_wizard_clear( ch );
            send_to_char( "This area's range is full.\n\r", ch );
            return;
        }
        send_to_char( kind == WIZ_MOB ? "A new mobile.  CANCEL stops at any question.\n\r"
                                      : "A new object.  CANCEL stops at any question.\n\r",
                      ch );
        wiz_ask( ch );
        return;
    }

    do_build( ch, "" );
}


/*
 * ------------------------------------------------------------------------
 * Rooms: SET ROOM in words, and RSHOW.
 *
 * SET ROOM took flag letters (+AJ) and a sector number, the last corner of
 * building that wanted the file format by heart. It takes names now --
 * flags +indoors -dark, sector forest -- and the letters still work, so no
 * builder's habit breaks: a single letter is a letter, a word is a name.
 * do_rset in act_wiz.c keeps NAME and hands the rest here.
 * ------------------------------------------------------------------------
 */

static const struct build_flag room_flag_names[] =
{
    { "dark",          ROOM_DARK          }, { "jail",         ROOM_JAIL         },
    { "no_mob",        ROOM_NO_MOB        }, { "indoors",      ROOM_INDOORS      },
    { "cult_entrance", ROOM_CULT_ENTRANCE }, { "death_trap",   ROOM_DT           },
    { "private",       ROOM_PRIVATE       }, { "safe",         ROOM_SAFE         },
    { "solitary",      ROOM_SOLITARY      }, { "pet_shop",     ROOM_PET_SHOP     },
    { "no_recall",     ROOM_NO_RECALL     }, { "imp_only",     ROOM_IMP_ONLY     },
    { "gods_only",     ROOM_GODS_ONLY     }, { "heroes_only",  ROOM_HEROES_ONLY  },
    { "newbies_only",  ROOM_NEWBIES_ONLY  }, { "law",          ROOM_LAW          },
    { "hp_regen",      ROOM_HP_REGEN      }, { "mana_regen",   ROOM_MANA_REGEN   },
    { "arena",         ROOM_ARENA         }, { "castle_join",  ROOM_CASTLE_JOIN  },
    { "silent",        ROOM_SILENT        },
    { NULL, 0 }
};

/* The second word: written only when the first carries ROOM_FLAGS2. */
static const struct build_flag room_flag2_names[] =
{
    { "no_teleport", ROOM2_NO_TPORT   }, { "always_lit", ROOM2_ALWAYS_LIT },
    { "bank",        ROOM2_BANK       },
    { NULL, 0 }
};

/* Rooms whose data lives outside the room, which a save cannot write
   (room_is_saveable in db.c): their flags are not set by hand. */
#define ROOM_UNSAVEABLE ( ROOM_RIVER | ROOM_TELEPORT | ROOM_AFFECTED_BY )

/* A room flag by name: exact, or a prefix of three letters or more -- a
   shorter word is one of the old flag letters. */
static const struct build_flag *room_name_find( const struct build_flag *t,
                                                const char *name )
{
    const struct build_flag *f;

    for ( f = t; f->name != NULL; f++ )
        if ( !str_cmp( name, f->name ) )
            return f;
    if ( strlen( name ) < 3 )
        return NULL;
    for ( f = t; f->name != NULL; f++ )
        if ( !str_prefix( name, f->name ) )
            return f;
    return NULL;
}


/* The next space-separated word, case kept: one_argument lowercases, and
   the old flag letters are capitals (D is indoors; d is a different bit). */
static char *word_keep_case( char *src, char *dst, size_t size )
{
    size_t n = 0;

    while ( isspace( (unsigned char) *src ) )
        src++;
    while ( *src != '\0' && !isspace( (unsigned char) *src ) )
    {
        if ( n < size - 1 )
            dst[n++] = *src;
        src++;
    }
    dst[n] = '\0';
    return src;
}

static bool room_flags_edit( CHAR_DATA *ch, ROOM_INDEX_DATA *room, char *value )
{
    char word[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    long one = room->room_flags;
    long two = room->room_flags2;

    if ( !str_cmp( value, "none" ) )
    {
        one &= ROOM_UNSAVEABLE;
        two = 0;
    }
    else for ( ; ; )
    {
        const struct build_flag *f;
        const char *name;
        bool remove;

        value = word_keep_case( value, word, sizeof(word) );
        if ( word[0] == '\0' )
            break;
        remove = ( word[0] == '-' );
        name   = ( word[0] == '-' || word[0] == '+' ) ? word + 1 : word;

        if ( ( f = room_name_find( room_flag_names, name ) ) != NULL )
        {
            if ( remove ) REMOVE_BIT( one, f->bit ); else SET_BIT( one, f->bit );
        }
        else if ( ( f = room_name_find( room_flag2_names, name ) ) != NULL )
        {
            if ( remove ) REMOVE_BIT( two, f->bit ); else SET_BIT( two, f->bit );
        }
        else
        {
            int updated;
            const char *c;
            bool letters = ( name[0] != '\0' );

            /* The old way: capital letters as STAT shows them, or a number.
               A lowercase word that is no flag's name is a typo, and must
               not be read as letters -- "+river" would set four bits. */
            for ( c = name; *c != '\0'; c++ )
                if ( !isupper( (unsigned char) *c ) && !isdigit( (unsigned char) *c ) )
                    letters = false;
            if ( !letters || !flags_from_argument( word, (int) one, &updated ) )
            {
                table_names( room_flag_names, buf, sizeof(buf) );
                send_to_char( "Room flags: ", ch );
                send_to_char( buf, ch );
                table_names( room_flag2_names, buf, sizeof(buf) );
                send_to_char( " ", ch );
                send_to_char( buf, ch );
                send_to_char( "\n\r  +name adds, -name takes away, none clears.\n\r", ch );
                return false;
            }
            if ( updated < 0 )
            {
                /* 2147483648 reads as INT_MIN, which no save can write. */
                send_to_char( "That number is beyond the flags a room can hold.\n\r", ch );
                return false;
            }
            if ( ( (long) updated & ~one & ROOM_UNSAVEABLE ) != 0 )
            {
                send_to_char( "River, teleport and room-affect rooms keep data a save "
                              "cannot write yet,\n\rso those flags are not set by hand.\n\r",
                              ch );
                return false;
            }
            one = updated;
        }
    }

    if ( two != 0 )
        SET_BIT( one, ROOM_FLAGS2 );
    else
        REMOVE_BIT( one, ROOM_FLAGS2 );
    room->room_flags  = (int) one;
    room->room_flags2 = (int) two;
    return true;
}


/* What LOOK <keyword> shows in this room: "runes The runes read...",
   "runes + more", "runes none". */
static bool room_detail_edit( CHAR_DATA *ch, ROOM_INDEX_DATA *room, char *value )
{
    char keyword[MAX_INPUT_LENGTH];
    char text[2 * MAX_STRING_LENGTH];
    EXTRA_DESCR_DATA *ed, *prev = NULL;

    value = one_argument( value, keyword );
    while ( isspace( (unsigned char) *value ) )
        value++;
    if ( keyword[0] == '\0' || value[0] == '\0' )
    {
        send_to_char( "Syntax: set room <vnum> detail <keyword> <text>\n\r"
                      "        set room <vnum> detail <keyword> + <text>    add to it\n\r"
                      "        set room <vnum> detail <keyword> none        take it away\n\r"
                      "Quote several keywords: detail 'altar stone' <text>\n\r", ch );
        return false;
    }

    for ( ed = room->extra_descr; ed != NULL; prev = ed, ed = ed->next )
        if ( !str_cmp( ed->keyword, keyword ) )
            break;

    if ( !str_cmp( value, "none" ) )
    {
        if ( ed == NULL )
        {
            send_to_char( "This room has no such detail.\n\r", ch );
            return false;
        }
        if ( prev == NULL ) room->extra_descr = ed->next; else prev->next = ed->next;
        return true;
    }

    text[0] = '\0';
    if ( value[0] == '+' && ed != NULL )
        toc_strlcpy( text, ed->description, sizeof(text) );
    wrap_into( value[0] == '+' ? value + 1 : value, text, sizeof(text) );
    if ( strlen( text ) >= MAX_STRING_LENGTH - 2 )
    {
        send_to_char( "That detail is too long.\n\r", ch );
        return false;
    }
    text[0] = UPPER( text[0] );

    if ( ed == NULL )
    {
        ed          = alloc_perm( sizeof(*ed) );
        ed->keyword = str_dup( keyword );
        ed->next    = room->extra_descr;
        room->extra_descr = ed;
        top_ed++;
    }
    else
        free_string( ed->description );
    ed->description = str_dup( text );
    return true;
}


/*
 * SET ROOM's fields in words. True when the field was one of these --
 * whether or not the value was taken -- so do_rset knows not to look
 * further; *changed says whether it was.
 */
bool build_set_room( CHAR_DATA *ch, ROOM_INDEX_DATA *room, const char *field,
                     char *value, bool *changed )
{
    char buf[MAX_STRING_LENGTH];
    char flags[1024];

    *changed = false;

    if ( !str_prefix( field, "flags" ) )
    {
        if ( !room_flags_edit( ch, room, value ) )
            return true;
        flag_names( room_flag_names, room->room_flags, flags, sizeof(flags) );
        if ( room->room_flags2 != 0 )
        {
            char more[512];

            flag_names( room_flag2_names, room->room_flags2, more, sizeof(more) );
            if ( !str_cmp( flags, "none" ) ) flags[0] = '\0';
            else toc_strlcat( flags, " ", sizeof(flags) );
            toc_strlcat( flags, more, sizeof(flags) );
        }
        snprintf( buf, sizeof(buf), "Room %d flags are now: %s\n\r", room->vnum, flags );
        send_to_char( buf, ch );
        *changed = true;
        return true;
    }

    if ( !str_prefix( field, "sector" ) || !str_cmp( field, "ground" ) )
    {
        const struct build_flag *f = NULL;
        int sector;

        if ( is_number( value ) )
            sector = atoi( value );
        else if ( ( f = flag_find( sector_names, value ) ) != NULL )
            sector = (int) f->bit;
        else
            sector = -1;
        if ( sector < 0 || sector >= SECT_MAX )
        {
            table_names( sector_names, buf, sizeof(buf) );
            send_to_char( "Ground: ", ch );
            send_to_char( buf, ch );
            send_to_char( "\n\r", ch );
            return true;
        }
        room->sector_type = (sh_int) sector;
        snprintf( buf, sizeof(buf), "Room %d is %s ground now.\n\r", room->vnum,
                  enum_name( sector_names, sector ) );
        send_to_char( buf, ch );
        *changed = true;
        return true;
    }

    if ( !str_prefix( field, "description" ) )
    {
        char text[2 * MAX_STRING_LENGTH];

        text[0] = '\0';
        if ( value[0] == '+' )
            toc_strlcpy( text, room->description, sizeof(text) );
        wrap_into( value[0] == '+' ? value + 1 : value, text, sizeof(text) );
        if ( strlen( text ) >= MAX_STRING_LENGTH - 2 )
        {
            send_to_char( "That description is too long.\n\r", ch );
            return true;
        }
        text[0] = UPPER( text[0] );
        free_string( room->description );
        room->description = str_dup( text );
        snprintf( buf, sizeof(buf), "Description of room %d %s.\n\r", room->vnum,
                  value[0] == '+' ? "added to" : "replaced" );
        send_to_char( buf, ch );
        *changed = true;
        return true;
    }

    if ( !str_prefix( field, "details" ) || !str_prefix( field, "extra" ) )
    {
        if ( room_detail_edit( ch, room, value ) )
        {
            snprintf( buf, sizeof(buf), "Room %d's details are set.\n\r", room->vnum );
            send_to_char( buf, ch );
            *changed = true;
        }
        return true;
    }

    return false;
}


/* What a door is, by its lock number, as RLINK names it. */
static const char *exit_kind( const EXIT_DATA *pexit )
{
    switch ( pexit->lock )
    {
    case 0:  return "open way";
    case 1:  return "door";
    case 2:  return "door that cannot be picked";
    case 3:  return "door";
    case 4:  return "secret door";
    case 5:  return "trapped door";
    }
    return "way";
}


/* RSHOW [vnum] -- a room in the words SET ROOM and RLINK take. */
void do_rshow( CHAR_DATA *ch, char *argument )
{
    static char out[4 * MAX_STRING_LENGTH];
    const size_t size = sizeof(out);
    char buf[MAX_STRING_LENGTH];
    char flags[1024];
    ROOM_INDEX_DATA *room = ch->in_room;
    EXTRA_DESCR_DATA *ed;
    RESET_DATA *r;
    ROOM_INDEX_DATA *context = NULL;
    int door, resets = 0;

    if ( argument[0] != '\0' )
    {
        if ( !is_number( argument ) || strlen( argument ) > 5
          || ( room = get_room_index( atoi( argument ) ) ) == NULL )
        {
            send_to_char( "Syntax: rshow [room vnum]\n\r", ch );
            return;
        }
    }
    if ( room == NULL )
        return;

    out[0] = '\0';
    snprintf( buf, sizeof(buf), "Room %d, in %s%s.\n\r", room->vnum,
              room->area != NULL && room->area->name != NULL ? room->area->name : "no area",
              area_is_buildable( room->area ) ? "" : " (shipped: implementor only)" );
    toc_strlcat( out, buf, size );
    snprintf( buf, sizeof(buf), "name:   %s\n\rground: %s\n\r", room->name,
              enum_name( sector_names, room->sector_type ) );
    toc_strlcat( out, buf, size );

    flag_names( room_flag_names, room->room_flags, flags, sizeof(flags) );
    if ( room->room_flags2 != 0 )
    {
        char more[512];

        flag_names( room_flag2_names, room->room_flags2, more, sizeof(more) );
        if ( !str_cmp( flags, "none" ) ) flags[0] = '\0';
        else toc_strlcat( flags, " ", sizeof(flags) );
        toc_strlcat( flags, more, sizeof(flags) );
    }
    if ( IS_SET( room->room_flags, ROOM_RIVER ) )        toc_strlcat( flags, " (river)", sizeof(flags) );
    if ( IS_SET( room->room_flags, ROOM_TELEPORT ) )     toc_strlcat( flags, " (teleport)", sizeof(flags) );
    if ( IS_SET( room->room_flags, ROOM_AFFECTED_BY ) )  toc_strlcat( flags, " (room affect)", sizeof(flags) );
    snprintf( buf, sizeof(buf), "flags:  %s\n\rdesc:\n\r", flags );
    toc_strlcat( out, buf, size );
    toc_strlcat( out, room->description != NULL && room->description[0] != '\0'
                      ? room->description : "  (none)\n\r", size );
    if ( room->description != NULL && room->description[0] != '\0'
      && room->description[strlen( room->description ) - 1] != '\r'
      && room->description[strlen( room->description ) - 1] != '\n' )
        toc_strlcat( out, "\n\r", size );

    toc_strlcat( out, "exits:\n\r", size );
    for ( door = 0; door <= 9; door++ )
    {
        EXIT_DATA *pexit = room->exit[door];
        ROOM_INDEX_DATA *to;

        if ( pexit == NULL )
            continue;
        to = pexit->u1.to_room;
        snprintf( buf, sizeof(buf), "  %-9s to %d (%s), %s", dir_name[door],
                  to != NULL ? to->vnum : -1, to != NULL ? to->name : "nowhere",
                  exit_kind( pexit ) );
        toc_strlcat( out, buf, size );
        if ( pexit->key > 0 )
        {
            snprintf( buf, sizeof(buf), ", key %d", pexit->key );
            toc_strlcat( out, buf, size );
        }
        if ( pexit->keyword != NULL && pexit->keyword[0] != '\0' )
        {
            snprintf( buf, sizeof(buf), ", called '%s'", pexit->keyword );
            toc_strlcat( out, buf, size );
        }
        toc_strlcat( out, "\n\r", size );
    }

    buf[0] = '\0';
    for ( ed = room->extra_descr; ed != NULL; ed = ed->next )
    {
        if ( buf[0] != '\0' )
            toc_strlcat( buf, ", ", sizeof(buf) );
        toc_strlcat( buf, ed->keyword, sizeof(buf) );
    }
    snprintf( flags, sizeof(flags), "details: %s\n\r", buf[0] != '\0' ? buf : "none" );
    toc_strlcat( out, flags, size );

    if ( room->area != NULL )
        for ( r = room->area->reset_first; r != NULL; r = r->next )
        {
            ROOM_INDEX_DATA *where = reset_room( r, context );

            if ( r->command == 'M' || r->command == 'O' )
                context = where;
            if ( where == room )
                resets++;
        }
    snprintf( buf, sizeof(buf), "resets: %d%s\n\r", resets,
              resets > 0 ? "  (RESETS lists them)" : "" );
    toc_strlcat( out, buf, size );
    page_to_char( out, ch );
}


/*
 * ------------------------------------------------------------------------
 * Shops: SET MOB <vnum> SHOP ...
 *
 * get_cost in act_obj.c charges a buyer value * profit_buy / 100 and pays
 * a seller value * profit_sell / 100, for the item types in buy_type and
 * nothing else; the keeper trades between open_hour and close_hour. In
 * words those are the markup, what it pays, what it buys and its hours.
 * What it sells is whatever it carries: PLACE OBJ <vnum> ON <keeper> gives
 * it stock, and a shopkeeper's stock never runs out.
 * ------------------------------------------------------------------------
 */

extern SHOP_DATA *shop_last;
extern int top_shop;

static void shop_words( SHOP_DATA *s, char *out, size_t size )
{
    char types[256];
    int i;

    types[0] = '\0';
    for ( i = 0; i < MAX_TRADE; i++ )
    {
        if ( s->buy_type[i] <= 0 )
            continue;
        if ( types[0] != '\0' )
            toc_strlcat( types, " ", sizeof(types) );
        toc_strlcat( types, enum_name( type_names, s->buy_type[i] ), sizeof(types) );
    }
    snprintf( out, size, "markup %d%%, pays %d%%, buys %s, open %d to %d",
              s->profit_buy, s->profit_sell, types[0] != '\0' ? types : "nothing",
              s->open_hour, s->close_hour );
}


static void shop_unlink( SHOP_DATA *s )
{
    SHOP_DATA *p, *prev = NULL;

    for ( p = shop_first; p != NULL; prev = p, p = p->next )
    {
        if ( p != s )
            continue;
        if ( prev == NULL ) shop_first = p->next; else prev->next = p->next;
        if ( shop_last == p )
            shop_last = prev;
        top_shop--;
        return;
    }
}


static void shop_help( CHAR_DATA *ch )
{
    send_to_char( "Syntax: set mob <vnum> shop                  make it a shopkeeper\n\r"
                  "        set mob <vnum> shop markup <percent>  what buyers pay, of value\n\r"
                  "        set mob <vnum> shop pays <percent>    what it pays sellers\n\r"
                  "        set mob <vnum> shop buys <types>      what it will buy: weapon armor ...\n\r"
                  "        set mob <vnum> shop hours <open> <close>   0 to 23\n\r"
                  "        set mob <vnum> shop none              no longer a shop\n\r"
                  "It sells what it carries: PLACE OBJ <vnum> ON <its vnum>.\n\r", ch );
}


/* SET MOB <vnum> SHOP ...; true when something changed. */
static bool mob_shop_edit( CHAR_DATA *ch, MOB_INDEX_DATA *m, char *value )
{
    char word[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];
    SHOP_DATA *s = m->pShop;
    char *rest;

    rest = one_argument( value, word );

    if ( !str_cmp( word, "none" ) || !str_cmp( word, "no" ) )
    {
        if ( s == NULL )
        {
            send_to_char( "It keeps no shop.\n\r", ch );
            return false;
        }
        shop_unlink( s );
        m->pShop = NULL;
        send_to_char( "It keeps no shop now.\n\r", ch );
        return true;
    }

    if ( s == NULL )
    {
        int i;

        s              = alloc_perm( sizeof(*s) );
        s->keeper      = m->vnum;
        for ( i = 0; i < MAX_TRADE; i++ )
            s->buy_type[i] = 0;
        s->profit_buy  = 120;
        s->profit_sell = 80;
        s->open_hour   = 0;
        s->close_hour  = 23;
        s->next        = NULL;
        if ( shop_first == NULL )
            shop_first = s;
        if ( shop_last != NULL )
            shop_last->next = s;
        shop_last = s;
        top_shop++;
        m->pShop = s;
        if ( word[0] == '\0' || !str_cmp( word, "yes" ) )
        {
            send_to_char( "It keeps a shop now: markup 120%, pays 80%, buys nothing, "
                          "open all day.\n\r", ch );
            return true;
        }
    }
    else if ( word[0] == '\0' )
    {
        shop_help( ch );
        return false;
    }

    if ( !str_prefix( word, "markup" ) || !str_prefix( word, "pays" ) )
    {
        long n = plain_number( rest, 1000 );
        bool markup = !str_prefix( word, "markup" );

        if ( n < 0 || ( markup && n < 1 ) )
        {
            send_to_char( "Give a percentage: shop markup 120, shop pays 80.\n\r", ch );
            return false;
        }
        if ( markup ) s->profit_buy = (sh_int) n; else s->profit_sell = (sh_int) n;
    }
    else if ( !str_prefix( word, "buys" ) )
    {
        sh_int types[MAX_TRADE];
        int count = 0, i;

        for ( i = 0; i < MAX_TRADE; i++ )
            types[i] = 0;
        for ( ; ; )
        {
            const struct build_flag *f;

            rest = one_argument( rest, word );
            if ( word[0] == '\0' || !str_cmp( word, "nothing" ) )
                break;
            if ( ( f = flag_find( type_names, word ) ) == NULL )
            {
                snprintf( buf, sizeof(buf), "There is no item type called '%s'.\n\r", word );
                send_to_char( buf, ch );
                return false;
            }
            if ( count >= MAX_TRADE )
            {
                snprintf( buf, sizeof(buf), "A shop buys at most %d types.\n\r", MAX_TRADE );
                send_to_char( buf, ch );
                return false;
            }
            types[count++] = (sh_int) f->bit;
        }
        for ( i = 0; i < MAX_TRADE; i++ )
            s->buy_type[i] = types[i];
    }
    else if ( !str_prefix( word, "hours" ) )
    {
        char second[MAX_INPUT_LENGTH];
        long open, close;

        rest = one_argument( rest, word );
        one_argument( rest, second );
        open  = plain_number( word, 23 );
        close = plain_number( second, 23 );
        if ( open < 0 || close < 0 )
        {
            send_to_char( "Hours are 0 to 23: shop hours 6 22.\n\r", ch );
            return false;
        }
        s->open_hour  = (sh_int) open;
        s->close_hour = (sh_int) close;
    }
    else
    {
        shop_help( ch );
        return false;
    }

    shop_words( s, word, sizeof(word) );
    snprintf( buf, sizeof(buf), "Its shop: %s.\n\r", word );
    send_to_char( buf, ch );
    return true;
}

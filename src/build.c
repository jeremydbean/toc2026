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

struct build_flag
{
    const char *name;
    long        bit;
};

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
    snprintf( buf, sizeof(buf), "special: %s   shop: %s   actions: %d\n\r",
              spec, m->pShop != NULL ? "yes" : "no", actions );
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
        "  act affect affect2 offense immune resist vulnerable form parts\n\r"
        "      +name adds, -name takes away, none clears:  act +aggressive -wimpy\n\r"
        "MSHOW <vnum> shows the mobile in these words.  ASAVE keeps changes.\n\r",
        ch );
}


/*
 * SET MOB <vnum> <field> <value>: reached from do_set when the target is a
 * number, so "set mob guard ..." still edits a mobile in the world.
 */
void build_set_mob( CHAR_DATA *ch, char *argument )
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
        return;

    if ( field[0] == '\0' )
    {
        show_mob( ch, m );
        return;
    }

    snprintf( race_why, sizeof(race_why), "that is part of being %s %s",
              strchr( "aeiou", LOWER( race_table[m->race].name[0] ) ) ? "an" : "a",
              race_table[m->race].name );

    /* Every field below wants a value; an empty one would match every
       name, since str_prefix calls "" a prefix of anything. */
    if ( value[0] == '\0' )
    {
        mob_field_help( ch );
        return;
    }

    /* ---- words ---- */
    if ( !str_prefix( field, "keywords" ) || !str_cmp( field, "name" ) )
    {
        m->player_name = str_perm( value );
    }
    else if ( !str_prefix( field, "short" ) )
    {
        m->short_descr = str_perm( value );
    }
    else if ( !str_prefix( field, "long" ) )
    {
        char text[MAX_STRING_LENGTH];

        snprintf( text, sizeof(text), "%s\n\r", value );
        text[0] = UPPER( text[0] );
        m->long_descr = str_perm( text );
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
            return;
        }
        if ( strlen( text ) >= MAX_STRING_LENGTH - 2 )
        {
            send_to_char( "That description is too long.\n\r", ch );
            return;
        }
        text[0] = UPPER( text[0] );
        m->description = str_perm( text );
    }

    /* ---- what it is ---- */
    else if ( !str_prefix( field, "race" ) )
    {
        int race = race_named( value );

        if ( value[0] == '\0' || race < 0 )
        {
            send_to_char( "No such race.  Try human, elf, dwarf, giant, dragon, "
                          "wolf, bear...\n\r", ch );
            return;
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

        if ( f == NULL ) { send_to_char( "Sex is male, female or neutral.\n\r", ch ); return; }
        m->sex = (sh_int) f->bit;
    }
    else if ( !str_prefix( field, "size" ) )
    {
        const struct build_flag *f = flag_find( size_names, value );

        if ( f == NULL )
        {
            send_to_char( "Size is tiny, small, medium, large, huge or giant.\n\r", ch );
            return;
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
            return;
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
            return;
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
            return;
        }
        m->alignment = (sh_int) align;
    }
    else if ( !str_prefix( field, "hitroll" ) && str_cmp( field, "hit" ) )
    {
        if ( !is_number( value ) || strlen( value ) > 4 )
        {
            send_to_char( "Hitroll is a number.\n\r", ch );
            return;
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
            return;
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
            return;
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
            return;
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
            return;
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
            return;
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
            return;
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
            return;
        }
        if ( str_cmp( value, "none" ) && ( fun = spec_named( value ) ) == NULL )
        {
            snprintf( buf, sizeof(buf), "There is no special called %s.\n\r", value );
            send_to_char( buf, ch );
            return;
        }
        m->spec_fun = fun;
    }

    /* ---- flag words ---- */
    else if ( !str_cmp( field, "act" ) )
    {
        long bits = m->act;

        race_fixed = race_table[m->race].act | ACT_IS_NPC;
        if ( !flag_edit( ch, act_names, &bits, "act flag", value, race_fixed, race_why ) )
            return;
        m->act = bits | ACT_IS_NPC;
    }
    else if ( !str_cmp( field, "act2" ) )
    {
        if ( !flag_edit( ch, act2_names, &m->act2, "act2 flag", value, 0, race_why ) )
            return;
    }
    else if ( !str_cmp( field, "affect2" ) || !str_cmp( field, "aff2" ) )
    {
        if ( !flag_edit( ch, affect2_names, &m->affected_by2, "affect", value, 0,
                         race_why ) )
            return;
    }
    else if ( !str_prefix( field, "affects" ) || !str_cmp( field, "aff" ) )
    {
        if ( !flag_edit( ch, affect_names, &m->affected_by, "affect", value,
                         race_table[m->race].aff, race_why ) )
            return;
    }
    else if ( !str_cmp( field, "offense2" ) || !str_cmp( field, "off2" ) )
    {
        if ( !flag_edit( ch, off2_names, &m->off_flags2, "offense", value, 0,
                         race_why ) )
            return;
    }
    else if ( !str_prefix( field, "offense" ) || !str_prefix( field, "offence" ) )
    {
        if ( !flag_edit( ch, off_names, &m->off_flags, "offense", value,
                         race_table[m->race].off, race_why ) )
            return;
    }
    else if ( !str_prefix( field, "immune" ) || !str_prefix( field, "immunities" ) )
    {
        if ( !flag_edit( ch, imm_names, &m->imm_flags, "immunity", value,
                         race_table[m->race].imm, race_why ) )
            return;
    }
    else if ( !str_prefix( field, "resist" ) || !str_prefix( field, "resistances" ) )
    {
        if ( !flag_edit( ch, res_names, &m->res_flags, "resistance", value,
                         race_table[m->race].res, race_why ) )
            return;
    }
    else if ( !str_prefix( field, "vulnerable" ) || !str_prefix( field, "vulnerabilities" ) )
    {
        if ( !flag_edit( ch, vuln_names, &m->vuln_flags, "vulnerability", value,
                         race_table[m->race].vuln, race_why ) )
            return;
    }
    else if ( !str_prefix( field, "form" ) )
    {
        if ( !flag_edit( ch, form_names, &m->form, "form", value,
                         race_table[m->race].form, race_why ) )
            return;
    }
    else if ( !str_prefix( field, "parts" ) )
    {
        if ( !flag_edit( ch, part_names, &m->parts, "part", value,
                         race_table[m->race].parts, race_why ) )
            return;
    }
    else
    {
        mob_field_help( ch );
        return;
    }

    snprintf( buf, sizeof(buf), "Mobile %d's %s is set.  MSHOW %d to look; ASAVE "
              "to keep it.\n\r", m->vnum, field, m->vnum );
    send_to_char( buf, ch );
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
static bool obj_detail_edit( CHAR_DATA *ch, OBJ_INDEX_DATA *o, char *value )
{
    char keyword[MAX_INPUT_LENGTH];
    char text[2 * MAX_STRING_LENGTH];
    EXTRA_DESCR_DATA *ed, *prev = NULL;

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
        ed->keyword = str_perm( keyword );
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
    ed->description = str_perm( text );
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
void build_set_obj( CHAR_DATA *ch, char *argument )
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
        return;

    if ( field[0] == '\0' )
    {
        show_obj( ch, o );
        return;
    }

    /* A field with no value only ever means "what goes here?" -- and an
       empty word is a prefix of every name to str_prefix. */
    if ( value[0] == '\0' && str_prefix( field, "flags" ) )
    {
        obj_field_help( ch );
        return;
    }

    if ( ( r = set_obj_value_field( ch, o, field, value ) ) != 0 )
    {
        if ( r < 0 )
            return;
    }
    else if ( !str_prefix( field, "keywords" ) || !str_cmp( field, "name" ) )
        o->name = str_perm( value );
    else if ( !str_prefix( field, "short" ) )
        o->short_descr = str_perm( value );
    else if ( !str_prefix( field, "long" ) )
    {
        value[0] = UPPER( value[0] );
        o->description = str_perm( value );
    }
    else if ( !str_prefix( field, "material" ) )
    {
        int mat = material_lookup( value );

        if ( mat == 19 && str_prefix( value, "unknown" ) )
        {
            send_to_char( "Materials: adamantite brass bronze cloth copper food "
                          "glass gold herb iron\n\r  leather paper pill silver "
                          "'spell component' steel stone vellum wood unknown\n\r", ch );
            return;
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
            return;
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
            return;
        }
        o->level = (sh_int) n;
    }
    else if ( !str_prefix( field, "weight" ) )
    {
        if ( ( n = plain_number( value, 30000 ) ) < 0 )
        {
            send_to_char( "Weight is a number from 0 to 30000.\n\r", ch );
            return;
        }
        o->weight = (sh_int) n;
    }
    else if ( !str_prefix( field, "cost" ) || !str_prefix( field, "price" ) )
    {
        if ( ( n = parse_price( value ) ) < 0 )
        {
            send_to_char( "Give a price: 5g 20s, 1p, 3 gold, or a number of "
                          "copper.\n\r", ch );
            return;
        }
        o->cost = n;
    }
    else if ( !str_prefix( field, "condition" ) )
    {
        if ( ( f = flag_find( condition_names, value ) ) == NULL )
        {
            send_to_char( "Condition: perfect good average worn damaged broken "
                          "ruined.\n\r", ch );
            return;
        }
        o->condition = (sh_int) f->bit;
    }
    else if ( !str_prefix( field, "wear" ) )
    {
        long bits = (unsigned short) o->wear_flags;

        if ( !flag_edit( ch, wear_names, &bits, "wear slot", value, 0, "" ) )
            return;
        o->wear_flags = (sh_int) bits;
    }
    else if ( !str_prefix( field, "flags" ) || !str_prefix( field, "extra" ) )
    {
        if ( !obj_flags_edit( ch, o, value ) )
            return;
    }
    else if ( !str_prefix( field, "affects" ) || !str_prefix( field, "grants" )
           || !str_prefix( field, "powers" ) )
    {
        if ( prototype_worn( o ) )
        {
            send_to_char( "Somebody is wearing one of these.  Its affects come off "
                          "as they went on,\n\rso they cannot change under it: have "
                          "it taken off first.\n\r", ch );
            return;
        }
        if ( !str_prefix( field, "affects" ) ? !obj_affect_edit( ch, o, value )
                                             : !obj_grants_edit( ch, o, value ) )
            return;
    }
    else if ( !str_prefix( field, "details" ) )
    {
        if ( !obj_detail_edit( ch, o, value ) )
            return;
    }
    else if ( !str_prefix( field, "description" ) )
    {
        /* What LOOK <object> shows is a detail under the object's own
           keywords; without one, LOOK repeats the long line. */
        char detail[2 * MAX_INPUT_LENGTH];

        snprintf( detail, sizeof(detail), "'%s' %s", o->name, value );
        if ( !obj_detail_edit( ch, o, detail ) )
            return;
    }
    else if ( LOWER( field[0] ) == 'v' && field[1] >= '0' && field[1] <= '4'
           && field[2] == '\0' )
    {
        if ( ( n = plain_number( value, 2000000000L ) ) < 0 )
        {
            send_to_char( "A value is a number, 0 or more.\n\r", ch );
            return;
        }
        o->value[field[1] - '0'] = (int) n;
    }
    else
    {
        snprintf( buf, sizeof(buf), "%s has no field '%s'.\n\r",
                  enum_name( type_names, o->item_type ), field );
        send_to_char( buf, ch );
        obj_field_help( ch );
        return;
    }

    snprintf( buf, sizeof(buf), "Object %d's %s is set.  OSHOW %d to look; ASAVE "
              "to keep it.\n\r", o->vnum, field, o->vnum );
    send_to_char( buf, ch );
}

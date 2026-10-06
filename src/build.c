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
    out[0] = '\0';
    for ( ; t->name != NULL; t++ )
    {
        if ( IS_SET( bits, t->bit ) )
        {
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

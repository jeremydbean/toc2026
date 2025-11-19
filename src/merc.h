#pragma once

/**************************************************************************
 * SEGROMv1 was written and concieved by Eclipse<Eclipse@bud.indirect.com *
 * Soulcrusher <soul@pcix.com> and Gravestone <bones@voicenet.com> all    *
 * rights are reserved.  This is based on the original work of the DIKU   *
 * MERC coding team and Russ Taylor for the ROM2.3 code base.             *
 **************************************************************************/

/*
 * Accommodate old non-Ansi compilers.
 */
/* Simplified for modern ANSI C */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>












































































































































































































































































							[2];
							[MAX_LEVEL+1]
				   DO_FUN *cmd, char *arg ) );
			    FILE *stream) );
	char      *     name;
	int		can_carry;
	int		factor;
	int		hp;
	int		intel;
	int		todam;
	int		tohit;
	int		wis;
	int 		con;
	int             dex;
	int             mob_vnum;
	int             obj[4];
	int             str;
	int             were_type;
	int16_t                  vnum;
	ROOM_INDEX_DATA *       to_room;
        char           *offense_on;
        char           *offense_text;
        int            offense_id;
    /* mobile stuff */
    /* parts stuff */
    /* stats */
    AFFECT_DATA *       affected;
    AFFECT_DATA *       affected;
    AFFECT_DATA *       affected;
    AFFECT_DATA *       next;
    ALIAS_DATA		alias		[MAX_ALIASES];
    AREA_DATA *         area;
    AREA_DATA *         next;
    BAN_DATA *  next;
    BOARD_DATA *        pboard;
    BOARD_DATA * next;
    bool		 visible;      /* is it visible when room changes */
    bool		confirm_pkill;
    bool                color;                /* set state of color */
    bool                color;          /* color state */
    bool                confirm_delete;
    bool                confirm_unsaved_quit;
    bool                empty;
    bool                enchanted;
    bool                fcommand;
    bool                group_known     [MAX_GROUP];
    bool                has_saved;
    bool                new_format;
    bool                new_format;
    bool                on_quest;             /* questing state */
    bool                psionic_grant_pending;
    bool        fMana;                  /* Class gains mana on level    */
    bool        group_chosen[MAX_GROUP];
    bool        pc_race;                /* can be chosen by pcs */
    bool        skill_chosen[MAX_SKILL];
    bool        valid;
    char                command;
    char                inbuf           [4 * MAX_INPUT_LENGTH];
    char                incomm          [MAX_INPUT_LENGTH];
    char                inlast          [MAX_INPUT_LENGTH];
    char        who_name        [7];    /* Three-letter name for 'who'  */
    char        who_name[8];
    char      name[20];
    char *		ident;
    char *		not_vict_action;
    char *		prompt;
    char *		rreply;
    char *		slay;
    char *		vict_action;
    char *	first;
    char *	second;
    char *              action_to_char;
    char *              action_to_char;
    char *              action_to_room;
    char *              action_to_room;
    char *              arrive;
    char *              bamfin;
    char *              bamfout;
    char *              can_gain[MAX_GAIN];
    char *              can_teach[MAX_TEACH];
    char *              depart;
    char *              description;
    char *              description;
    char *              description;
    char *              description;
    char *              description;
    char *              description;
    char *              host;
    char *              ignore;
    char *              keyword;
    char *              list_remorts;
    char *              long_descr;
    char *              long_descr;
    char *              name;
    char *              name;
    char *              name;
    char *              name;
    char *              name;
    char *              not_vict_action;     /* act style action */
    char *              outbuf;
    char *              owner;
    char *              player_name;
    char *              psionic_grant_spec;
    char *              pwd;
    char *              short_descr;
    char *              short_descr;
    char *              short_descr;
    char *              short_descr;
    char *              showstr_head;
    char *              showstr_point;
    char *              title;
    char *              trans;
    char *              vict_action;         /* act style action */
    char *      arrive;                 /* arrival messages for races */
    char *      base_group;             /* base skills gained           */
    char *      char_auto;
    char *      date;
    char *      date;
    char *      default_group;          /* default skills gained        */
    char *      depart;                 /* depart messages for races */
    char *      keyword;
    char *      liq_color;
    char *      liq_name;
    char *      msg;
    char *      msg_off;                /* Wear off message             */
    char *      name;
    char *      name;
    char *      name;
    char *      name;                   /* call name of the race */
    char *      name;                   /* MUST be in race_type */
    char *      name;                   /* name and message */
    char *      name;                   /* Name of skill                */
    char *      name;                   /* the full name of the class */
    char *      noun_damage;            /* Damage message               */
    char *      old_text;
    char *      others_auto;
    char *      owner;
    char *      sender;
    char *      skills[5];              /* bonus skills for the race */
    char *      spells[MAX_IN_GROUP];
    char *      subject;
    char *      subject;
    char *      text;
    char *      text;
    char *      to_list;
    char *    char_found;
    char *    char_no_arg;
    char *    char_not_found;
    char *    others_found;
    char *    others_no_arg;
    char *    vict_found;
    char *description;          /* What to see                      */
    char *keyword;              /* Keyword in look/examine          */
    char text[1024];
    CHAR_DATA   *ch;
    CHAR_DATA *		questgiver;
    CHAR_DATA *         carried_by;
    CHAR_DATA *         character;
    CHAR_DATA *         fighting;
    CHAR_DATA *         hunting;       /* For hunt.c hunting routine. */
    CHAR_DATA *         leader;
    CHAR_DATA *         master;
    CHAR_DATA *         next;
    CHAR_DATA *         next_in_room;
    CHAR_DATA *         original;
    CHAR_DATA *         people;
    CHAR_DATA *         pet;
    CHAR_DATA *         reply;
    CHAR_DATA *         trapped;
    DESCRIPTOR_DATA *   desc;
    DESCRIPTOR_DATA *   next;
    DESCRIPTOR_DATA *   snoop_by;
    EXIT_DATA *         exit    [10];
    EXTRA_DESCR_DATA *  extra_descr;
    EXTRA_DESCR_DATA *  extra_descr;
    EXTRA_DESCR_DATA *  extra_descr;
    EXTRA_DESCR_DATA *next;     /* Next in list                     */
    GEN_DATA    *next;
    GEN_DATA *          gen_data;
    HATE_DATA *		hates;
    HATE_DATA * next;
    HELP_DATA * next;
    int			corpses;
    int			ifd;
    int			ip;
    int			questpoints;
    int			top_web_desc;
    int		moon_phase;
    int		moon_place;
    int 		id;
    int 		port;
    int                 affected_by2; /* second group of flags */
    int                 affected_by;
    int                 bitvector2;
    int                 bitvector;
    int                 cost;
    int                 cost;
    int                 descriptor;
    int                 extra_flags2;    /* second group of flags */
    int                 extra_flags2; /* second group of flags */
    int                 extra_flags;
    int                 extra_flags;
    int                 last_level;
    int                 lines;  /* for the pager */
    int                 max_str;    */
    int                 num_remorts;
    int                 outsize;
    int                 outtop;
    int                 played;
    int                 questor         [10]; /* quest items */
    int                 repeat;
    int                 room_flags2;
    int                 room_flags;
    int                 value   [5];
    int                 value[5];
    int         change;
    int         damage;                 /* damage class */
    int         day;
    int         hour;
    int         mmhg;
    int         month;
    int         points_chosen;
    int         sky;
    int         status;
    int         sunlight;
    int         year;
    int16_t		 speed;        /* for rivers/teleport rooms (Haiku) */
    int16_t		 to_room;      /* for rivers/teleport rooms */
    int16_t		battleticks;
    int16_t		castle;
    int16_t		cloak_level;
    int16_t		countdown;
    int16_t		disaster_type;
    int16_t		id;
    int16_t		id;
    int16_t		lmb_timer;	      /* Timer for Sanity Check */
    int16_t		nextquest;
    int16_t		number;
    int16_t		number_repair;
    int16_t		pk_state;
    int16_t		questmob;
    int16_t		questobj;
    int16_t               timer;        /* for rivers/teleport rooms */
    int16_t              ac[4];
    int16_t              age;
    int16_t              alignment;
    int16_t              alignment;
    int16_t              arg1;
    int16_t              arg2;
    int16_t              arg3;
    int16_t              armor[4];
    int16_t              carry_number;
    int16_t              carry_weight;
    int16_t              class;
    int16_t              class;
    int16_t              col_table[32];        /* for those with color */
    int16_t              condition       [3];
    int16_t              condition;
    int16_t              condition;
    int16_t              connected;
    int16_t              count;
    int16_t              count;
    int16_t              dam_type;
    int16_t              dam_type;
    int16_t              damage[3];
    int16_t              damage[3];
    int16_t              damroll;
    int16_t              default_pos;
    int16_t              default_pos;
    int16_t              duration;
    int16_t              exit_info;
    int16_t              guild;
    int16_t              guild;
    int16_t              hit;
    int16_t              hit[3];
    int16_t              hitroll;
    int16_t              hitroll;
    int16_t              invis_level;
    int16_t              item_type;
    int16_t              item_type;
    int16_t              key;
    int16_t              killed;
    int16_t              killed;
    int16_t              learned         [MAX_SKILL];
    int16_t              level;
    int16_t              level;
    int16_t              level;
    int16_t              level;
    int16_t              level;
    int16_t              level;
    int16_t              light;
    int16_t              location;
    int16_t              lock;
    int16_t              login_attempts;
    int16_t              mana;
    int16_t              mana[3];
    int16_t              material;
    int16_t              material;
    int16_t              material;
    int16_t              material;
    int16_t              max_hit;
    int16_t              max_mana;
    int16_t              max_move;
    int16_t              mod_stat[MAX_STATS];
    int16_t              modifier;
    int16_t              mounted;              /* for riding stuff */
    int16_t              move;
    int16_t              nplayer;
    int16_t              number;
    int16_t              perm_hit;
    int16_t              perm_mana;
    int16_t              perm_move;
    int16_t              perm_stat[MAX_STATS];
    int16_t              points;
    int16_t              position;
    int16_t              practice;
    int16_t              psionic;              /* to determine if psi */
    int16_t              race;
    int16_t              race;
    int16_t              reset_num;
    int16_t              ridden;       /* used for riding code */
    int16_t              saving_throw;
    int16_t              sector_type;
    int16_t              sex;
    int16_t              sex;
    int16_t              size;
    int16_t              size;
    int16_t              start_pos;
    int16_t              start_pos;
    int16_t              timer;
    int16_t              timer;
    int16_t              train;
    int16_t              trap;
    int16_t              true_sex;
    int16_t              trust;
    int16_t              type;
    int16_t              version;
    int16_t              vnum;
    int16_t              vnum;
    int16_t              vnum;
    int16_t              vnum;
    int16_t              wait;
    int16_t              wear_flags;
    int16_t              wear_flags;
    int16_t              wear_loc;
    int16_t              weight;
    int16_t              weight;
    int16_t              wimpy;
    int16_t      attr_prime;             /* Prime attribute              */
    int16_t      beats;                  /* Waiting time after use       */
    int16_t      buy_type [MAX_TRADE];   /* Item types shop will buy     */
    int16_t      carry;
    int16_t      class_mult2[MAX_GUILD]; /* exp per multi class */
    int16_t      class_mult[MAX_CLASS];  /* exp per multi class */
    int16_t      close_hour;             /* First closing hour           */
    int16_t      defensive;
    int16_t      guild[MAX_GUILD];       /* Vnum of guild rooms          */
    int16_t      hitp;
    int16_t      hp_max;                 /* Max hp gained on leveling    */
    int16_t      hp_min;                 /* Min hp gained on leveling    */
    int16_t      keeper;                 /* Vnum of shop keeper mob      */
    int16_t      learn;
    int16_t      level;
    int16_t      level;
    int16_t      liq_affect[3];
    int16_t      mana_gain;
    int16_t      max_stats[MAX_STATS];   /* maximum stats */
    int16_t      min_mana;               /* Minimum mana used            */
    int16_t      minimum_position;       /* Position for caster / user   */
    int16_t      open_hour;              /* First opening hour           */
    int16_t      points;                 /* cost in points of the race */
    int16_t      practice;
    int16_t      profit_buy;             /* Cost multiplier for buying   */
    int16_t      profit_sell;            /* Cost multiplier for selling  */
    int16_t      rating[MAX_CLASS];
    int16_t      rating[MAX_CLASS];      /* How hard it is to learn      */
    int16_t      shock;
    int16_t      size;                   /* aff bits for the race */
    int16_t      skill_adept;            /* Maximum skill level          */
    int16_t      skill_level[MAX_CLASS]; /* Level needed by class        */
    int16_t      slot;                   /* Slot for #OBJECT loading     */
    int16_t      stats[MAX_STATS];       /* starting stats */
    int16_t      target;                 /* Legal targets                */
    int16_t      thac0_00;               /* Thac0 for level  0           */
    int16_t      thac0_32;               /* Thac0 for level 32           */
    int16_t      todam;
    int16_t      tohit;
    int16_t      weapon;                 /* First weapon                 */
    int16_t      weapon_prof[8];        /* Gives class weapon profs     */
    int16_t      wield;
    int16_t *    pgsn;                   /* Pointer to associated gsn    */
    long			bank;
    long		dcount;		     /* Prevents multi-killing */
    long		jw_timer;	      /* Jail warning timer for PC's */
    long		quest_pause;	      /* halt quest for a week on quit*/
    long                act2;
    long                act2;         /* second group of flags */
    long                act;
    long                act;
    long                affected_by2; /* second group of flags */
    long                affected_by;
    long                comm;         /* RT added to pad the vector */
    long                exp;
    long                form;
    long                form;
    long                imm_flags2;   /* second group of flags */
    long                imm_flags2;   /* second group of flags */
    long                imm_flags;
    long                imm_flags;
    long                new_copper;
    long                new_copper;
    long                new_gold;
    long                new_gold;
    long                new_platinum;
    long                new_platinum;
    long                new_silver;
    long                new_silver;
    long                off_flags2;   /* second group of flags */
    long                off_flags2;   /* second group of flags */
    long                off_flags;
    long                off_flags;
    long                parts;
    long                parts;
    long                pkills_given;
    long                pkills_received;
    long                res_flags2;   /* second group of flags */
    long                res_flags2;   /* second group of flags */
    long                res_flags;
    long                res_flags;
    long                vuln_flags2;  /* second group of flags */
    long                vuln_flags2;  /* second group of flags */
    long                vuln_flags;
    long                vuln_flags;
    long        act;                    /* act bits for the race */
    long        aff;                    /* aff bits for the race */
    long        ch;
    long        form;                   /* default form flag for the race */
    long        imm;                    /* imm bits for the race */
    long        off;                    /* off bits for the race */
    long        parts;                  /* default parts for the race */
    long        res;                    /* res bits for the race */
    long        vuln;                   /* vuln bits for the race */
    long mtype;
    MOB_ACTION_DATA *   action;
    MOB_ACTION_DATA *   next;
    MOB_INDEX_DATA *    next;
    MOB_INDEX_DATA *    pIndexData;
    NOTE_DATA *         pnote;
    NOTE_DATA * next;
    OBJ_ACTION_DATA *	action;
    OBJ_ACTION_DATA *	action;
    OBJ_ACTION_DATA *	next;
    OBJ_DATA *          carrying;
    OBJ_DATA *          contains;
    OBJ_DATA *          contents;
    OBJ_DATA *          in_obj;
    OBJ_DATA *          in_object;
    OBJ_DATA *          next;
    OBJ_DATA *          next_content;
    OBJ_INDEX_DATA *    next;
    OBJ_INDEX_DATA *    pIndexData;
    PC_DATA *           next;
    PC_DATA *           pcdata;
    pid_t		ipid;
    RESET_DATA *        next;
    RESET_DATA *        reset_first;
    RESET_DATA *        reset_last;
    ROOM_AFF_DATA *     affected;
    ROOM_INDEX_DATA *    room;
    ROOM_INDEX_DATA *   in_room;
    ROOM_INDEX_DATA *   in_room;
    ROOM_INDEX_DATA *   next;
    ROOM_INDEX_DATA *   was_in_room;
    SHOP_DATA *         pShop;
    SHOP_DATA * next;                   /* Next shop in list            */
    SPEC_FUN *          spec_fun;
    SPEC_FUN *          spec_fun;
    SPELL_FUN * spell_fun;              /* Spell pointer (for spells)   */
    TELEPORT_ROOM_DATA * next;
    time_t              last_note;
    time_t              logon;
    time_t      date_stamp;
    time_t      date_stamp;
    union
    WERE_FORM           were_shape;
    WIZ_DATA *  next;
    {
    } u1;
   char            *name;
   char *             name;       /* noun name */
   in const.c
   int                bitvector2; /* some affects use secondary flags */
   int                bitvector;  /* some affects use flags */
   int              item_curr_load;
   int              item_game_load;
   int              item_max_load;
   int              vnum;
   int16_t             aff_exit;   /* used to specify affected exits */
   int16_t             dam_dice;   /* size of dice */
   int16_t             dam_number; /* number of dice */
   int16_t             duration;   /* how long the affect to pc lasts */
   int16_t             level;      /* some affects are level dependant */
   int16_t             location;   /* some affects have apply data */
   int16_t             modifier;   /* how much to apply */
   int16_t             timer;      /* how long the affect lasts */
   int16_t             type;       /* which affect */
   ITEM_MAX_LOAD  * next;
   long             pkills_given;
   long             pkills_received;
   opposing castles realm. Obj->value[1] is the room where the
   owners castle relic resides.
   PKILL_LIST_DATA *next;
   ROOM_AFF_DATA *    next;       /* link em */
   ROOM_INDEX_DATA *  room;       /* Identify which room is affected*/
   These vnums are where stolen artifacts will be placed in the
  bool imm_only;
  char *ansi_str;
  char *name;
  char *type;
  int def;
  int num;
 *
 *
 *
 *                                                                         *
 *                                                                         *
 *                                                                         *
 *                                                                         *
 *                   (End of this section ... stop here)                   *
 *                   (Start of section ... start here)                     *
 *                   VALUES OF INTEREST TO AREA BUILDERS                   *
 *                   VALUES OF INTEREST TO AREA BUILDERS                   *
 *   '*': comment
 *   'D': set state of door
 *   'E': equip object to mobile
 *   'G': give object to mobile
 *   'M': read a mobile
 *   'O': read an object
 *   'P': put object in object
 *   'R': randomize room exits
 *   'S': stop (end of list)
 *   but some systems have incomplete or non-ansi header files.
 *   so players can go ahead and telnet to all the other descriptors.
 *   United States to foreign countries.
 *  Target types.
 * A kill structure (indexed by level).
 * ACT bits for mobs.
 * ACT bits for players.
 * Added by Eclipse
 * Added by Eclipse
 * Added by Eclipse
 * Adjust the pulse numbers to suit yourself.
 * All files are read in completely at bootup.
 * An affect.
 * Apply types (for affects).
 * Area definition.
 * Area-reset definition.
 * AREA_LIST contains a list of areas to boot.
 * Attribute bonus structures.
 * Bits for 'affected_by'.
 * but may be arbitrary beyond that.
 * Character macros.
 * Conditions.
 * Connected state for a channel.
 * Data files used by the server.
 * Data structure for notes.
 * Data which only PC's have.
 * Defined in #MOBILES.
 * Defined in #OBJECTS.
 * Defined in #ROOMS.
 * Description macros.
 * Descriptor (channel) structure.
 * Diavolo reports AIX compiler has bugs with short types.
 * Directions.
 * Eclipse.
 * Equpiment wear locations.
 * Exit data.
 * Exit flags.
 * Extra description data for a room or object.
 * Extra flags.
 * flags. Added by Eclipse
 * Function types.
 * Game parameters.
 * Global constants.
 * Global variables.
 * Help table types.
 * In particular, the U.S. Government prohibits its export from the
 * Increase the max'es if you add more of something.
 * Item types.
 * Liquids.
 * Maxload structure.
 * Mob actions and M-style added by Haiku
 * Most output files (bug, idea, typo, shutdown) are append-only.
 * Must be non-overlapping with spell/skill types,
 * Object macros.
 * One big lump ... this is every function in Merc.
 * One character (PC or NPC).
 * One object.
 * OS-dependent declarations.
 * Our function prototypes.
 * Per-class stuff.
 * Pkill list data
 * Positions.
 * Prototype for a mob.
 * Prototype for an object.
 * Prototype for guildmaster.  By Haiku.
 * Prototype for mob action data.  Used with new M style mobs
 * Reset commands:
 * Room affect data to add affects to rooms.
 * Room flags.
 * Room type.
 * Second group of affects
 * Second group of affects.
 * Second group of extra flags
 * Second group of Vulnerabilty
 * Sector types.
 * Sex.
 * Shop types.
 * Short scalar types.
 * Site ban structure.
 * Skills include spells as a particular case.
 * String and memory management parameters.
 * Structure for a social in the socials table.
 * Structure types.
 * teleport_room_data is for a linked list of all the teleporting rooms
 * The crypt(3) function is not available on some operating systems.
 * The NULL_FILE is held open so that we have a stream handle in reserve,
 * Then we close it whenever we need to open a file (e.g. a save file).
 * These are all very standard library functions,
 * These are skill_lookup return values for common skills and spells.
 * This is the in-memory version of #MOBILES.
 * Time and weather stuff.
 * to make the update of those rooms much faster.
 * TO types for act.
 * Turn on NOCRYPT to keep passwords in plain text.
 * Types of attacks.
 * Used in #MOBILES.
 * Used in #MOBILES.
 * Used in #MOBILES.
 * Used in #OBJECTS.
 * Used in #OBJECTS.
 * Used in #OBJECTS.
 * Used in #OBJECTS.
 * Used in #OBJECTS.
 * Used in #RESETS.
 * Used in #ROOMS.
 * Used in #ROOMS.
 * Used in #ROOMS.
 * Used in #ROOMS.
 * Uses a linked list similar to Haiku's Tport room data.
 * Utility macros.
 * Values for containers (value[1]).
 * Wear actions for objects requested via trinidad
 * Wear flags.
 * Well known mob virtual numbers.
 * Well known object virtual numbers.
 * Well known room virtual numbers.
 ***************************************************************************/
 ***************************************************************************/
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
 */
#define A                       0x00000001
#define aa                      0x04000000        /* doubled due to conflicts */
#define AC_BASH                         1
#define AC_EXOTIC                       3
#define AC_PIERCE                       0
#define AC_SLASH                        2
#define ACT2_LYCANTH	        (B)
#define ACT2_NO_TPORT           (A)
#define ACT2_REPAIR		(C)
#define ACT_AGGRESSIVE          (F)             /* Attacks PC's         */
#define ACT_B_BOY		(N)
#define ACT_CLERIC              (Q)
#define ACT_FLAGS2              (Z)
#define ACT_GAIN                (E)
#define ACT_IS_HEALER           (D)
#define ACT_IS_NPC              (A)             /* Auto set for mobs    */
#define ACT_MAGE                (R)
#define ACT_MOUNTABLE           (W)
#define ACT_NOALIGN             (U)
#define ACT_NOKILL		(X)
#define ACT_NOPURGE             (V)
#define ACT_NOSHOVE             (M)
#define ACT_PET                 (I)             /* Auto set for pets    */
#define ACT_PRACTICE            (K)             /* Can practice PC's    */
#define ACT_QUESTM		(Y)
#define ACT_SCAVENGER           (C)             /* Picks up objects     */
#define ACT_SENTINEL            (B)             /* Stays in one room    */
#define ACT_STAY_AREA           (G)             /* Won't leave area     */
#define ACT_THIEF               (S)
#define ACT_TRAIN               (J)             /* Can train PC's       */
#define ACT_UNDEAD              (O)
#define ACT_UPDATE_ALWAYS       (L)
#define ACT_WARRIOR             (T)
#define ACT_WIMPY               (H)
#define AFF2_DARK_VISION         (A)
#define AFF2_DETECT_GOOD         (B)
#define AFF2_DIVINE_PROT         (M)
#define AFF2_FLAMING_COLD        (E)
#define AFF2_FLAMING_HOT         (D)
#define AFF2_FORCE_SWORD         (J)
#define AFF2_GHOST		 (K)
#define AFF2_HOLD                (C)
#define AFF2_MADNESS		 (L)
#define AFF2_NO_RECOVER          (I)
#define AFF2_PARALYSIS           (F)
#define AFF2_STEALTH             (G)
#define AFF2_STUNNED             (H)
#define AFF_BERSERK             (G)
#define AFF_BLIND               (A)
#define AFF_CALM                (W)
#define AFF_CHARM               (S)
#define AFF_CURSE               (K)
#define AFF_DETECT_EVIL         (C)
#define AFF_DETECT_HIDDEN       (F)
#define AFF_DETECT_INVIS        (D)
#define AFF_DETECT_MAGIC        (E)
#define AFF_FAERIE_FIRE         (I)
#define AFF_FLAGS2              (Z)
#define AFF_FLYING              (T)
#define AFF_HASTE               (V)
#define AFF_HIDE                (Q)
#define AFF_INFRARED            (J)
#define AFF_INVISIBLE           (B)
#define AFF_PASS_DOOR           (U)
#define AFF_PLAGUE              (X)
#define AFF_POISON              (M)
#define AFF_PROTECT             (N)
#define AFF_REGENERATION        (O)
#define AFF_SANCTUARY           (H)
#define AFF_SLEEP               (R)
#define AFF_SNEAK               (P)
#define AFF_SWIM                (L)
#define AFF_WEAKEN              (Y)
#define ANGEL                   (MAX_LEVEL - 5)
#define APPLY_AC                     17
#define APPLY_AGE                     9
#define APPLY_CLASS                   7
#define APPLY_CON                     5
#define APPLY_DAMROLL                19
#define APPLY_DEX                     2
#define APPLY_EXP                    16
#define APPLY_GOLD                   15
#define APPLY_HEIGHT                 10
#define APPLY_HIT                    13
#define APPLY_HITROLL                18
#define APPLY_INT                     3
#define APPLY_LEVEL                   8
#define APPLY_MANA                   12
#define APPLY_MOVE                   14
#define APPLY_NONE                    0
#define APPLY_SAVING_BREATH          23
#define APPLY_SAVING_PARA            20
#define APPLY_SAVING_PETRI           22
#define APPLY_SAVING_ROD             21
#define APPLY_SAVING_SPELL           24
#define APPLY_SEX                     6
#define APPLY_STR                     1
#define APPLY_WEIGHT                 11
#define APPLY_WIS                     4
#define ARCHANGEL               (MAX_LEVEL - 4)
#define AREA_DIR        ""              /* Dir for saved areas */
#define AREA_DIR        "saved"         /* Dir for saved areas */
#define AREA_LIST       "area.lst"      /* List of areas                */
#define ASSIST_ALIGN            (Q)
#define ASSIST_ALL              (P)
#define ASSIST_GUARD            (T)
#define ASSIST_PLAYERS          (S)
#define ASSIST_RACE             (R)
#define ASSIST_VNUM             (U)
#define AVATAR                  (MAX_LEVEL - 6)
#define B                       0x00000002
#define BACKUP_DIR      "../backups/"   /* Backup files                 */
#define BAN_FILE	"ban.txt"	/* for 'bans'			*/
#define BATTLE_TICKS                2
#define bb                      0x08000000
#define BUG_FILE        "bugs.txt"      /* For 'bug' and bug( )         */
#define C                       0x00000004
#define CAN_WEAR(obj, part)     (IS_SET((obj)->wear_flags,  (part)))
#define CASTLE_CONSORTIUM	5
#define CASTLE_FORSAKEN	        4
#define CASTLE_FOUR             17503
#define CASTLE_HORDE		2
#define CASTLE_LEGION		3
#define CASTLE_NONE		0
#define CASTLE_ONE              17500
#define CASTLE_OUTCAST          6
#define CASTLE_ROGUE		7
#define CASTLE_THREE            17502
#define CASTLE_TWO              17501
#define CASTLE_VALHALLA		1
#define cc                      0x10000000
#define CD      CHAR_DATA
#define CH(d)				((d)->original ? (d)->original : (d)->character )
#define CHGRP_TO	"toc"	 	/* for saved files		*/
#define CLASS_ANY       -1
#define CLASS_CLERIC    1
#define CLASS_MAGE      0
#define CLASS_MONK      4
#define CLASS_NECRO     5
#define CLASS_OTHER     6
#define CLASS_THIEF     2
#define CLASS_WARRIOR   3
#define COL_CASTLE               5 /* 05 */
#define COL_DAMAGE               10 /* 0A */
#define COL_DEFENSE              11 /* 0B */
#define COL_DISARM               12 /* 0C */
#define COL_EXITS                14  0E
#define COL_GOSSIP               2 /* 02 */
#define COL_HERO                 13 /* 0D */
#define COL_HIGHLIGHT            9 /* 09 */
#define COL_IMMTALK              15 /* 0F */
#define COL_MAX                  16
#define COL_MOB                  11  0B
#define COL_OBJECT               12  0C
#define COL_PROMPT               17  11
#define COL_QUESTION             4 /* 04 */
#define COL_REGULAR              1 /* 01 */
#define COL_ROOM_NAME            16 /* 10 */
#define COL_SAYS                 7 /* 07 */
#define COL_SHOUTS               3 /* 03 */
#define COL_SOCIALS              8 /* 08 */
#define COL_TELL                 6 /* 06 */
#define COL_WIZINFO              14 /* 0E */
#define COMM_BRIEF              (M)
#define COMM_COMBINE            (O)
#define COMM_COMPACT            (L)
#define COMM_DEAF               (B)
#define COMM_NOBEEP		(bb)
#define COMM_NOCASTLE           (H)
#define COMM_NOCGOS             (Q)
#define COMM_NOCHANNELS         (W)
#define COMM_NOEMOTE            (T)
#define COMM_NOGOD              (R)
#define COMM_NOGOSSIP           (E)
#define COMM_NOGRATZ            (D)
#define COMM_NOHERO		(I)
#define COMM_NOINFO		(J)
#define COMM_NOMUSIC            (G)
#define COMM_NONOTE             (Y)
#define COMM_NOQUESTION         (F)
#define COMM_NORMUD		(Z)
#define COMM_NOSHOUT            (U)
#define COMM_NOTELL             (V)
#define COMM_NOTITLE		(aa)
#define COMM_NOWIZ              (C)
#define COMM_NOWIZINFO		(K)
#define COMM_PROMPT             (N)
#define COMM_QUIET              (A)
#define COMM_TELLOFF 		(S)
#define COMM_TELNET_GA          (P)
#define COMM_WHINE              (X)
#define CON_BREAK_CONNECT               15
#define CON_CONFIRM_NEW_NAME             3
#define CON_CONFIRM_NEW_PASSWORD         5
#define CON_COPYOVER_RECOVER		17
#define CON_DEFAULT_CHOICE              10
#define CON_GEN_GROUPS                  11
#define CON_GET_ALIGNMENT                9
#define CON_GET_NAME                     1
#define CON_GET_NEW_CLASS                8
#define CON_GET_NEW_PASSWORD             4
#define CON_GET_NEW_RACE                 6
#define CON_GET_NEW_SEX                  7
#define CON_GET_OLD_PASSWORD             2
#define CON_PICK_WEAPON                 12
#define CON_PLAYING                      0
#define CON_READ_IMOTD                  13
#define CON_READ_MOTD                   14
#define CON_RETRY_PASSWORD		16
#define COND_DRUNK                    0
#define COND_FULL                     1
#define COND_THIRST                   2
#define CONT_CLOSEABLE                1
#define CONT_CLOSED                   4
#define CONT_LOCKED                   8
#define CONT_PICKPROOF                2
#define CONT_TRAPPED                 16
#define COPPER_PER_GOLD      (COPPER_PER_SILVER * SILVER_PER_GOLD)
#define COPPER_PER_PLATINUM  (COPPER_PER_GOLD * GOLD_PER_PLATINUM)
#define COPPER_PER_SILVER    100L
#define CORPSE_DIR	"../corpse/"	/* save the corpses here 	*/
#define crypt(s1, s2)   (s1)
#define D                       0x00000008
#define DAM_ACID                7
#define DAM_BASH                1
#define DAM_COLD                5
#define DAM_DISEASE             13
#define DAM_DROWNING            14
#define DAM_ENERGY              11
#define DAM_FIRE                4
#define DAM_HARM                17
#define DAM_HOLY                10
#define DAM_LIGHT               15
#define DAM_LIGHTNING           6
#define DAM_MENTAL              12
#define DAM_NEGATIVE            9
#define DAM_NONE                0
#define DAM_OTHER               16
#define DAM_PIERCE              2
#define DAM_POISON              8
#define DAM_SLASH               3
#define DAM_UNHOLY              18
#define DAM_WIND                19
#define dd                      0x20000000
#define DECLARE_DO_FUN(fun) DO_FUN fun
#define DECLARE_SPEC_FUN(fun) SPEC_FUN fun
#define DECLARE_SPELL_FUN(fun) SPELL_FUN fun
#define DEITY                   (MAX_LEVEL - 2)
#define DEMI                    (MAX_LEVEL - 3)
#define DICE_BONUS                      2
#define DICE_NUMBER                     0
#define DICE_TYPE                       1
#define DIR_DOWN                      5
#define DIR_EAST                      1
#define DIR_NORTH                     0
#define DIR_NORTHEAST                 6
#define DIR_NORTHWEST                 7
#define DIR_SOUTH                     2
#define DIR_SOUTHEAST                 8
#define DIR_SOUTHWEST                 9
#define DIR_UP                        4
#define DIR_WEST                      3
#define E                       0x00000010
#define ee                      0x40000000
#define EX_CLOSED                     (B)
#define EX_ISDOOR                     (A)
#define EX_LOCKED                     (C)
#define EX_PICKPROOF                  (F)
#define EX_SECRET                     (H)
#define EX_TRAPPED                    (I)
#define EX_WIZLOCKED                  (G)
#define EXTRA_DIMENSIONAL             2
#define F                       0x00000020
#define ff                      0x80000000
#define FORM_AMPHIBIAN          (aa)
#define FORM_ANIMAL             (G)
#define FORM_BIPED              (M)
#define FORM_BIRD               (W)
#define FORM_BLOB               (S)
#define FORM_CENTAUR            (N)
#define FORM_COLD_BLOOD         (cc)
#define FORM_CONSTRUCT          (J)
#define FORM_CRUSTACEAN         (Q)
#define FORM_DRAGON             (Z)
#define FORM_EDIBLE             (A)
#define FORM_FISH               (bb)
#define FORM_INSECT             (O)
#define FORM_INSTANT_DECAY      (D)
#define FORM_INTANGIBLE         (L)
#define FORM_MAGICAL            (C)
#define FORM_MAMMAL             (V)
#define FORM_MIST               (K)
#define FORM_OTHER              (E)  /* defined by material bit */
#define FORM_POISON             (B)
#define FORM_REPTILE            (X)
#define FORM_SENTIENT           (H)
#define FORM_SNAKE              (Y)
#define FORM_SPIDER             (P)
#define FORM_UNDEAD             (I)
#define FORM_WORM               (R)
#define G                       0x00000040
#define GET_AC(ch,type)         ((ch)->armor[type] + ( IS_AWAKE(ch) ? dex_app[get_curr_stat(ch,STAT_DEX)].defensive : 0 ))
#define GET_AGE(ch)             ((int) (17 + ((ch)->played  + current_time - (ch)->logon )/72000))
#define GET_DAMROLL(ch)	((ch)->damroll+str_app[get_curr_stat(ch,STAT_STR)].todam)
#define GET_HITROLL(ch) ((ch)->hitroll+str_app[get_curr_stat(ch,STAT_STR)].tohit)
#define GOD                     (MAX_LEVEL - 1)
#define GOD_DIR         "../gods/"      /* list of gods                 */
#define GOLD_PER_PLATINUM    100L
#define GUEST                   (MAX_LEVEL _ 10)
#define GUILD_ANY       10
#define GUILD_CLERIC    1
#define GUILD_MAGE      0
#define GUILD_MONK      4
#define GUILD_NECRO     5
#define GUILD_NONE      11
#define GUILD_THIEF     2
#define GUILD_WARRIOR   3
#define H                       0x00000080
#define HERO                     LEVEL_HERO
#define HERO_DIR        "../heroes/"    /* list of heroes               */
#define HERO_STEP_XP             5000
#define I                       0x00000100
#define IDEA_FILE       "ideas.txt"     /* For 'idea'                   */
#define IDLE_TO_LIMBO_TICKS       5  /* Approx 5 char_update ticks (roughly minutes) for idle to limbo */
#define IMM_ACID                (K)
#define IMM_BASH                (E)
#define IMM_CHARM               (B)
#define IMM_COLD                (I)
#define IMM_DISEASE             (Q)
#define IMM_DROWNING            (R)
#define IMM_ENERGY              (O)
#define IMM_FIRE                (H)
#define IMM_FLAGS2               (Z)/* Jump to second listing */
#define IMM_HOLY                (N)
#define IMM_LIGHT               (S)
#define IMM_LIGHTNING           (J)
#define IMM_MAGIC               (C)
#define IMM_MENTAL              (P)
#define IMM_NEGATIVE            (M)
#define IMM_PIERCE              (F)
#define IMM_POISON              (L)
#define IMM_SLASH               (G)
#define IMM_SUMMON              (A)
#define IMM_WEAPON              (D)
#define IMM_WIND                (T)
#define IMMORTAL                (MAX_LEVEL - 7)
#define IMPLEMENTOR              MAX_LEVEL
#define INVALIDATE(data)	((data)->valid=false)
#define IS_AFFECTED(ch, sn)     (IS_SET((ch)->affected_by, (sn)))
#define IS_AFFECTED2(ch, sn)     (IS_SET((ch)->affected_by2, (sn)))
#define IS_AWAKE(ch)            (ch->position > POS_SLEEPING)
#define IS_EVIL(ch)             (ch->alignment <= -300)
#define IS_GOOD(ch)             (ch->alignment >= 300)
#define IS_HERO(ch)             (ch->level >= LEVEL_HERO)
#define IS_IMMORTAL(ch)         (ch->level >= LEVEL_IMMORTAL)
#define IS_IMMUNE               1
#define IS_IMP(ch)		(ch->level == MAX_LEVEL)
#define IS_NEUTRAL(ch)          (!IS_GOOD(ch) && !IS_EVIL(ch))
#define IS_NORMAL               0
#define IS_NPC(ch)              (IS_SET((ch)->act, ACT_IS_NPC))
#define IS_NULLSTR( str )		((str) == NULL || (str)[0]=='\0')
#define IS_OBJ_STAT(obj, stat)  (IS_SET((obj)->extra_flags, (stat)))
#define IS_OBJ_STAT2(obj,stat)  (IS_SET((obj)->extra_flags2,(stat)))
#define IS_OUTSIDE(ch) (!IS_SET( (ch)->in_room->room_flags, ROOM_INDOORS))
#define IS_QUESTOR(ch)		(IS_SET((ch)->act, PLR_QUESTOR ) )
#define IS_RESISTANT            2
#define IS_SET(flag, bit)       ((flag) & (bit))
#define IS_SET2(flag,bit)       ((flag) & (bit))
#define IS_SWITCHED(ch)         (ch->desc != NULL && ch->desc->original != NULL)
#define IS_TRUSTED(ch,level)    (get_trust((ch)) >= (level))
#define IS_VALID(data)		((data) != NULL && (data)->valid)
#define IS_VULNERABLE           3
#define IS_WEAPON_STAT(obj,stat)(IS_SET((obj)->value[4],(stat)))
#define ITEM2_ADD_DETECT_INVIS  (G)
#define ITEM2_ADD_FLY           (H)
#define ITEM2_ADD_INVIS         (F)
#define ITEM2_DWARF_ONLY        (C)
#define ITEM2_ELF_ONLY          (B)
#define ITEM2_HALFLING_ONLY     (D)
#define ITEM2_HUMAN_ONLY        (A)
#define ITEM2_NO_CAN_SEE        (I)
#define ITEM2_NO_TPORT	        (K)
#define ITEM2_NOSTEAL		(J)
#define ITEM2_SAURIAN_ONLY      (E)
#define ITEM_ACTION		     37
#define ITEM_ADD_AFFECT         (X)
#define ITEM_ANTI_EVIL          (K)
#define ITEM_ANTI_GOOD          (J)
#define ITEM_ANTI_NEUTRAL       (L)
#define ITEM_ARMOR                    9
#define ITEM_BLESS              (I)
#define ITEM_BOAT                    22
#define ITEM_BOUNCE		(S)
#define ITEM_CAKE		     38
#define ITEM_CASTLE_RELIC            32
#define ITEM_CLOTHING                11
#define ITEM_CONTAINER               15
#define ITEM_CORPSE_NPC              23
#define ITEM_CORPSE_PC               24
#define ITEM_DAMAGED						(aa)
#define ITEM_DARK               (C)
#define ITEM_DRINK_CON               17
#define ITEM_EMBALMED		(Y)
#define ITEM_EVIL               (E)
#define ITEM_FLAGS2             (Z)
#define ITEM_FOOD                    19
#define ITEM_FOUNTAIN                25
#define ITEM_FURNITURE               12
#define ITEM_GLOW               (A)
#define ITEM_HERB                    34
#define ITEM_HOLD               (O)
#define ITEM_HUM                (B)
#define ITEM_INVENTORY          (N)
#define ITEM_INVIS              (F)
#define ITEM_KEY                     18
#define ITEM_LIGHT                    1
#define ITEM_LOCK               (D)
#define ITEM_MAGIC              (G)
#define ITEM_MANIPULATION            31
#define ITEM_MAP                     28
#define ITEM_METAL              (R)
#define ITEM_MONEY                   20
#define ITEM_NODROP             (H)
#define ITEM_NOIDENTIFY         (U)
#define ITEM_NOLOCATE           (V)
#define ITEM_NOPURGE            (O)
#define ITEM_NOREMOVE           (M)
#define ITEM_PILL                    26
#define ITEM_PORTAL                  30
#define ITEM_POTION                  10
#define ITEM_PROTECT                 27
#define ITEM_RACE_RESTRICTED    (W)
#define ITEM_ROT_DEATH          (P)
#define ITEM_SADDLE                  33
#define ITEM_SCROLL                   2
#define ITEM_SCUBA_GEAR              29
#define ITEM_SOUL_CONTAINER          36
#define ITEM_SPELL_COMPONENT         35
#define ITEM_STAFF                    4
#define ITEM_TAKE               (A)
#define ITEM_TPORT		(T)
#define ITEM_TRASH                   13
#define ITEM_TREASURE                 8
#define ITEM_TWO_HANDS          (P)
#define ITEM_VIS_DEATH          (Q)
#define ITEM_WAND                     3
#define ITEM_WEAPON                   5
#define ITEM_WEAR_ABOUT         (K)
#define ITEM_WEAR_ARMS          (I)
#define ITEM_WEAR_BODY          (D)
#define ITEM_WEAR_FEET          (G)
#define ITEM_WEAR_FINGER        (B)
#define ITEM_WEAR_HANDS         (H)
#define ITEM_WEAR_HEAD          (E)
#define ITEM_WEAR_LEGS          (F)
#define ITEM_WEAR_NECK          (C)
#define ITEM_WEAR_SHIELD        (J)
#define ITEM_WEAR_WAIST         (L)
#define ITEM_WEAR_WRIST         (M)
#define ITEM_WIELD              (N)
#define J                       0x00000200
#define K                       0x00000400
#define L                       0x00000800
#define LEVEL_HERO                 (MAX_LEVEL - 19)
#define LEVEL_HERO1                (MAX_LEVEL - 18)
#define LEVEL_HERO2                (MAX_LEVEL - 17)
#define LEVEL_HERO3                (MAX_LEVEL - 16)
#define LEVEL_HERO4                (MAX_LEVEL - 15)
#define LEVEL_IMMORTAL             (MAX_LEVEL - 10)
#define LEVEL_KING								 (MAX_LEVEL - 11)
#define LINKDEAD_PURGE_TICKS      3  /* Approx 3 char_update ticks (roughly minutes) for linkdead purge */
#define LIQ_MAX         16
#define LIQ_WATER        0
#define LOWER(c)                ((c) >= 'A' && (c) <= 'Z' ? (c)+'a'-'A' : (c))
#define M                       0x00001000
#define MARTYR                  (MAX_LEVEL - 8)
#define MAX_ALIASES		   20
#define MAX_BOARD                   5  /* Max boards allowed in game       */
#define MAX_CLASS                   6
#define MAX_GAIN        10
#define MAX_GROUP                  56
#define MAX_GUILD       6 /*this has to be set when a new GM is added-Drakk*/
#define MAX_HUNTERS                50
#define MAX_IN_GROUP               20
#define MAX_INPUT_LENGTH          256
#define MAX_INPUT_LENGTH          256
#define MAX_KEY_HASH             1024
#define MAX_KEY_HASH             2048
#define MAX_LEVEL                  70
#define MAX_MESSAGE_LENGTH       2048
#define MAX_MSGS                  100   /*   Max number of messages.       */
#define MAX_PC_RACE                 6
#define MAX_PKILL_LIST             20
#define MAX_PKILL_LIST             20
#define MAX_SKILL                 226
#define MAX_SOCIALS               512
#define MAX_STAT	30
#define MAX_STATS       5
#define MAX_STRING_LENGTH        4096
#define MAX_STRING_LENGTH        4096
#define MAX_TEACH       35
#define MAX_TRADE        5
#define MAX_WEAR                     18
#define MID     MOB_INDEX_DATA
#define MOB_VNUM_ANIMATE             80
#define MOB_VNUM_CITYGUARD         4456
#define MOB_VNUM_FIDO              3090
#define MOB_VNUM_VAMPIRE           3404
#define MOON_DOWN		    1
#define MOON_FULL                   2
#define MOON_NEW		    0
#define MOON_UP	   		    0
#define MOON_WANING	            3
#define MOON_WAXING	            1
#define N                       0x00002000
#define NEEDS_MASTER            (W)
#define NOCRYPT
#define NOCRYPT
#define NOTE_FILE       "notes.txt"     /* For 'notes'                  */
#define NULL_FILE       "/dev/null"     /* To reserve one stream        */
#define NULL_FILE       "nul"           /* To reserve one stream        */
#define NULL_FILE       "proto.are"             /* To reserve one stream        */
#define O                       0x00004000
#define OBJ_VNUM_BARM		     93
#define OBJ_VNUM_BHEAD		     92
#define OBJ_VNUM_BLEG		     94
#define OBJ_VNUM_BOGUS               28
#define OBJ_VNUM_BRAINS              17
#define OBJ_VNUM_CORPSE_NPC          10
#define OBJ_VNUM_CORPSE_PC           11
#define OBJ_VNUM_GUTS                16
#define OBJ_VNUM_LIGHT_BALL          21
#define OBJ_VNUM_MAP               3162
#define OBJ_VNUM_MONEY_ONE            2
#define OBJ_VNUM_MONEY_SOME           3
#define OBJ_VNUM_MUSHROOM            20
#define OBJ_VNUM_PIT               3010
#define OBJ_VNUM_SCHOOL_BANNER     3716
#define OBJ_VNUM_SCHOOL_DAGGER     3701
#define OBJ_VNUM_SCHOOL_MACE       3700
#define OBJ_VNUM_SCHOOL_SHIELD     3704
#define OBJ_VNUM_SCHOOL_SWORD      3702
#define OBJ_VNUM_SCHOOL_VEST       3703
#define OBJ_VNUM_SEVERED_HEAD        12
#define OBJ_VNUM_SLICED_ARM          14
#define OBJ_VNUM_SLICED_LEG          15
#define OBJ_VNUM_SPRING              22
#define OBJ_VNUM_TORN_HEART          13
#define OD      OBJ_DATA
#define OFF2_HUNTER              (A)
#define OFF_AREA_ATTACK         (A)
#define OFF_ATTACK_DOOR_OPENER  (X)
#define OFF_BACKSTAB            (B)
#define OFF_BASH                (C)
#define OFF_BERSERK             (D)
#define OFF_CRUSH               (O)
#define OFF_DISARM              (E)
#define OFF_DODGE               (F)
#define OFF_FADE                (G)
#define OFF_FAST                (H)
#define OFF_FLAGS2               (Z) /* Jump to second listing */
#define OFF_KICK                (I)
#define OFF_KICK_DIRT           (J)
#define OFF_PARRY               (K)
#define OFF_RESCUE              (L)
#define OFF_SUMMONER            (V)
#define OFF_TAIL                (M)
#define OFF_TRIP                (N)
#define OFFENSE_FILE    "offense.txt"   /* For 'offenses'		*/
#define OID     OBJ_INDEX_DATA
#define P                       0x00008000
#define PAGELEN                    22
#define PAGELEN                    22
#define PART_ARMS               (B)
#define PART_BRAINS             (E)
#define PART_CLAWS              (U)
#define PART_EAR                (J)
#define PART_EYE                (K)
#define PART_EYESTALKS          (M)
#define PART_FANGS              (V)
#define PART_FEET               (H)
#define PART_FINGERS            (I)
#define PART_FINS               (O)
#define PART_GUTS               (F)
#define PART_HANDS              (G)
#define PART_HEAD               (A)
#define PART_HEART              (D)
#define PART_HORNS              (W)
#define PART_LEGS               (C)
#define PART_LONG_TONGUE        (L)
#define PART_SCALES             (X)
#define PART_TAIL               (Q)
#define PART_TENTACLES          (N)
#define PART_TUSKS              (Y)
#define PART_WINGS              (P)
#define PERS(ch, looker)        ( can_see( looker, (ch) ) ? ( IS_NPC(ch) ? (ch)->short_descr : (ch)->name ) : (IS_IMMORTAL(ch) ? "An Immortal" : "someone" ) )
#define PLAYER_DIR      ""              /* Player files                 */
#define PLAYER_DIR      ""              /* Player files                 */
#define PLAYER_DIR      "../player/"    /* Player files                 */
#define PLAYER_TEMP     "../player/temp"
#define PLAYER_TEMP     "temp"
#define PLAYER_TEMP     "temp"
#define PLR_AFK			(U)
#define PLR_AUTOASSIST          (C)
#define PLR_AUTOEXIT            (D)
#define PLR_AUTOGOLD            (G)
#define PLR_AUTOLOOT            (E)
#define PLR_AUTOSAC             (F)
#define PLR_AUTOSPLIT           (H)
#define PLR_BOUGHT_PET          (B)
#define PLR_CANLOOT             (P)
#define PLR_CASTLEHEAD		(S)
#define PLR_CLOAKED		(T)
#define PLR_DAMAGE_NUMBERS			(K)
#define PLR_DENY                (X)
#define PLR_EXCON		(ee)
#define PLR_FREEZE              (Y)
#define PLR_HOLYLIGHT           (N)
#define PLR_IS_NPC              (A)             /* Don't EVER set.      */
#define PLR_JAILED		(dd)
#define PLR_LOG                 (W)
#define PLR_NOFOLLOW            (R)
#define PLR_NOSUMMON            (Q)
#define PLR_QFLAG               (J)
#define PLR_QUESTOR		(V)
#define PLR_SWEDISH		(I)
#define PLR_TRAITOR             (bb)
#define PLR_WANTED              (aa)
#define PLR_WARNED		(cc)
#define PLR_WIZINVIS            (O)
#define POS_DEAD                      0
#define POS_FIGHTING                  7
#define POS_INCAP                     2
#define POS_MORTAL                    1
#define POS_RESTING                   5
#define POS_SITTING                   6
#define POS_SLEEPING                  4
#define POS_STANDING                  8
#define POS_STUNNED                   3
#define PULSE_AGGR            	  ( 1 * PULSE_PER_SECOND)
#define PULSE_AREA                (60 * PULSE_PER_SECOND)
#define PULSE_DEATHTRAP		  ( 2 * PULSE_PER_SECOND)
#define PULSE_DISASTER            (30 * PULSE_PER_SECOND)
#define PULSE_HUNTING             ( 1 * PULSE_PER_SECOND)
#define PULSE_MOBILE              ( 4 * PULSE_PER_SECOND)
#define PULSE_PER_SECOND            4
#define PULSE_ROOM            	  ( 1 * PULSE_PER_SECOND)
#define PULSE_TICK                (60 * PULSE_PER_SECOND)
#define PULSE_VIOLENCE            ( 3 * PULSE_PER_SECOND)
#define Q                       0x00010000
#define R                       0x00020000
#define RELIC_PRIZE             4513
#define RELIC_VNUM1             4506
#define RELIC_VNUM2             4507
#define RELIC_VNUM3             4508
#define RELIC_VNUM4             4509
#define RELIC_VNUM5             4510
#define RELIC_VNUM6             4511
#define RELIC_VNUM7             4512
#define REMOVE_BIT(var, bit)    ((var) &= ~(bit))
#define replace_string( pstr, nstr )	{free_string( ( pstr ) ); pstr = str_dup( ( nstr) ); }
#define RES_ACID                (K)
#define RES_BASH                (E)
#define RES_CHARM               (B)
#define RES_COLD                (I)
#define RES_DISEASE             (Q)
#define RES_DROWNING            (R)
#define RES_ENERGY              (O)
#define RES_FIRE                (H)
#define RES_FLAGS2              (Z)  /* Jump to second listing */
#define RES_HOLY                (N)
#define RES_LIGHT               (S)
#define RES_LIGHTNING           (J)
#define RES_MAGIC               (C)
#define RES_MENTAL              (P)
#define RES_NEGATIVE            (M)
#define RES_PIERCE              (F)
#define RES_POISON              (L)
#define RES_SLASH               (G)
#define RES_WEAPON              (D)
#define RES_WIND                (T)
#define RID     ROOM_INDEX_DATA
#define ROOM2_NO_TPORT	        (A)
#define ROOM_AFFECTED_BY        (H)
#define ROOM_ARENA		(V)
#define ROOM_BFS_MARK           (Y)
#define ROOM_CASTLE_JOIN	(W)
#define ROOM_CULT_ENTRANCE      (G)
#define ROOM_DARK               (A)
#define ROOM_DT			(I)
#define ROOM_FLAGS2             (Z)
#define ROOM_GODS_ONLY          (P)
#define ROOM_HEROES_ONLY        (Q)
#define ROOM_HP_REGEN		(T)
#define ROOM_IMP_ONLY           (O)
#define ROOM_INDOORS            (D)
#define ROOM_JAIL               (B)
#define ROOM_LAW                (S)
#define ROOM_MANA_REGEN		(U)
#define ROOM_NEWBIES_ONLY       (R)
#define ROOM_NO_MOB             (C)
#define ROOM_NO_RECALL          (N)
#define ROOM_PET_SHOP           (M)
#define ROOM_PRIVATE            (J)
#define ROOM_RIVER		(E)
#define ROOM_SAFE               (K)
#define ROOM_SILENT		(X)
#define ROOM_SOLITARY           (L)
#define ROOM_TELEPORT		(F)
#define ROOM_VNUM_ALTAR            4208
#define ROOM_VNUM_BANK		   4
#define ROOM_VNUM_CHAT             9960
#define ROOM_VNUM_DEATH            4216
#define ROOM_VNUM_JAIL		   3
#define ROOM_VNUM_LIMBO               2
#define ROOM_VNUM_SCHOOL           3700
#define ROOM_VNUM_TEMPLE           4207
#define S                       0x00040000
#define SAINT                   (MAX_LEVEL - 9)
#define SAVE_FILE       "board%d.msg"  /* Name of file for saving messages */
#define SECT_AIR                      9
#define SECT_CITY                     1
#define SECT_DESERT                  10
#define SECT_FIELD                    2
#define SECT_FOREST                   3
#define SECT_HILLS                    4
#define SECT_INSIDE                   0
#define SECT_MAX                     12
#define SECT_MOUNTAIN                 5
#define SECT_UNDER_WATER              8
#define SECT_UNDERGROUND             11
#define SECT_WATER_NOSWIM             7
#define SECT_WATER_SWIM               6
#define SET_BIT(var, bit)       ((var) |= (bit))
#define SEX_FEMALE                    2
#define SEX_MALE                      1
#define SEX_NEUTRAL                   0
#define SF      SPEC_FUN
#define SHOCKER                       4
#define SHUTDOWN_FILE   "shutdown.txt"  /* For 'shutdown'               */
#define SILVER_PER_GOLD      100L
#define SIZE_GIANT                      5
#define SIZE_HUGE                       4
#define SIZE_LARGE                      3
#define SIZE_MEDIUM                     2
#define SIZE_SMALL                      1
#define SIZE_TINY                       0
#define SKY_CLOUDLESS               0
#define SKY_CLOUDY                  1
#define SKY_LIGHTNING               3
#define SKY_RAINING                 2
#define STAT_CON        4
#define STAT_DEX        3
#define STAT_INT        1
#define STAT_STR        0
#define STAT_WIS        2
#define STINKING_CLOUD                1
#define SUN_DARK                    0
#define SUN_LIGHT                   2
#define SUN_RISE                    1
#define SUN_SET                     3
#define T                       0x00080000
#define TAR_CHAR_DEFENSIVE          2
#define TAR_CHAR_OFFENSIVE          1
#define TAR_CHAR_SELF               3
#define TAR_EXIT                    6
#define TAR_IGNORE                  0
#define TAR_OBJ_HERE                5
#define TAR_OBJ_INV                 4
#define TO_CHAR             3
#define TO_NOTVICT          1
#define TO_ROOM             0
#define TO_VICT             2
#define TYPE_COPPER	0
#define TYPE_GOLD	2
#define TYPE_HIT                     1000
#define TYPE_PLATINUM	3
#define TYPE_SILVER	1
#define TYPE_UNDEFINED               -1
#define TYPO_FILE       "typos.txt"     /* For 'typo'                   */
#define U                       0x00100000
#define UMAX(a, b)              ((a) > (b) ? (a) : (b))
#define UMIN(a, b)              ((a) < (b) ? (a) : (b))
#define UNUSED_PARAM(x) ((void)(x))
#define UPPER(c)                ((c) >= 'a' && (c) <= 'z' ? (c)+'A'-'a' : (c))
#define URANGE(a, b, c)         ((b) < (a) ? (a) : ((b) > (c) ? (c) : (b)))
#define V                       0x00200000
#define VALIDATE(data)		((data)->valid=true)
#define VNUM_RELIC_1		4
#define VNUM_RELIC_2		5
#define VNUM_RELIC_3		6
#define VNUM_RELIC_4		7
#define VOLCANIC                      3
#define VULN_ACID               (K)
#define VULN_BASH               (E)
#define VULN_COLD               (I)
#define VULN_DISEASE            (Q)
#define VULN_DROWNING           (R)
#define VULN_ENERGY             (O)
#define VULN_FIRE               (H)
#define VULN_FLAGS2             (Z)  /* Jump to second listing */
#define VULN_HOLY               (N)
#define VULN_IRON               (U)
#define VULN_LIGHT              (S)
#define VULN_LIGHTNING          (J)
#define VULN_MAGIC              (C)
#define VULN_MENTAL             (P)
#define VULN_NEGATIVE           (M)
#define VULN_PIERCE             (F)
#define VULN_POISON             (L)
#define VULN_SILVER             (Y)
#define VULN_SLASH              (G)
#define VULN_WEAPON             (D)
#define VULN_WIND               (T)
#define VULN_WOOD               (X)
#define W                       0x00400000
#define WAIT_STATE(ch, npulse)  ((ch)->wait = UMAX((ch)->wait, (npulse)))
#define WEAPON_AXE              5
#define WEAPON_BOW              9
#define WEAPON_DAGGER           2
#define WEAPON_EXOTIC           0
#define WEAPON_FLAIL            6
#define WEAPON_FLAMING          (A)
#define WEAPON_FROST            (B)
#define WEAPON_MACE             4
#define WEAPON_POLEARM          8
#define WEAPON_SHARP            (D)
#define WEAPON_SPEAR            3
#define WEAPON_SWORD            1
#define WEAPON_TWO_HANDS        (F)
#define WEAPON_VAMPIRIC         (C)
#define WEAPON_VORPAL           (E)
#define WEAPON_WHIP             7
#define WEAR_ABOUT                   12
#define WEAR_ARMS                    10
#define WEAR_BODY                     5
#define WEAR_FEET                     8
#define WEAR_FINGER_L                 1
#define WEAR_FINGER_R                 2
#define WEAR_HANDS                    9
#define WEAR_HEAD                     6
#define WEAR_HOLD                    17
#define WEAR_LEGS                     7
#define WEAR_LIGHT                    0
#define WEAR_NECK_1                   3
#define WEAR_NECK_2                   4
#define WEAR_NONE                    -1
#define WEAR_SHIELD                  11
#define WEAR_WAIST                   13
#define WEAR_WIELD                   16
#define WEAR_WRIST_L                 14
#define WEAR_WRIST_R                 15
#define WORLD_SIZE		30000
#define X                       0x00800000
#define Y                       0x01000000
#define Z                       0x02000000
#else
#endif
#endif
#endif
#endif
#endif
#endif
#endif
#endif
#endif
#endif
#endif
#endif
#endif
#endif
#endif
#endif
#endif
#endif
#if     defined(_AIX)
#if     defined(apollo)
#if     defined(hpux)
#if     defined(linux)
#if     defined(macintosh)
#if     defined(MIPS_OS)
#if     defined(MSDOS)
#if     defined(NeXT)
#if     defined(NOCRYPT)
#if     defined(sequent)
#if     defined(sun)
#if     defined(SYSV)
#if     defined(ultrix)
#if     defined(unix)
#if     defined(unix)
#if defined(macintosh)
#if defined(MSDOS)
#if defined(unix)
#undef  unix
#undef  unix
*/
*/
*/
*/
*/
*/
*/
*/
*/
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*
/*    char **             str;
/*  (Haiku)
/*  time_t              last_board;     need or not? */
/* #define CON_INPUT_BOARD                 18    */
/* (Y) resevered for future use */
/* 3 bits reserved, T-V */
/* 5 bits reserved, I-M */
/* AC types */
/* actual form */
/* body form */
/* body parts */
/* Castle gsn's */
/* damage classes */
/* Data for generating characters -- only used during generation */
/* dice */
/* for combat */
/* Hate data added by Haiku */
/* hunt data by Fatcat */
/* ident macros for identd */
/* IMM bits for mobs */
/* MAX_TEACH is max number of spells/skills guildmasters can have listed
/* monk gsn's */
/* OFF bits for mobiles */
/* penalty flags */
/* psi skills */
/* RES bits for mobs */
/* return values for check_imm */
/* Room Affects Flags */
/* RT ASCII conversions -- used so we can have letters in this file */
/* RT auto flags */
/* RT comm flags -- may be used on both mobs and chars */
/* RT personal flags */
/* Second OFF bits for mobiles */
/* size */
/* struct fcor char id */
/* VULN bits for mobs */
/* weapon class */
/* weapon gsns */
/* weapon types */
/***************************************************************************
/***************************************************************************
//    long                gold;
//    long                gold;
// Wizlist structure.
//#define LINKDEAD_TIMEOUT_PULSES   (5 * 60 * PULSE_PER_SECOND) /* 5 minutes before linkdead char is quit */
#define args(list) list
typedef void DO_FUN     args( ( CHAR_DATA *ch, char *argument ) );
typedef bool SPEC_FUN   args( ( CHAR_DATA *mob, CHAR_DATA *ch,
typedef void SPELL_FUN  args( ( int sn, int level, CHAR_DATA *ch, void *vo ) );
void act args( ( const char *format, CHAR_DATA *ch, const void *arg1, const void *arg2, int type ) );
char * act2_bit_name args( ( long act_flags, long act_flags2 ) );
char * act_bit_name args( ( long act_flags ) );
void act_new args( ( const char *format, CHAR_DATA *ch, const void *arg1, const void *arg2, int type, int min_pos) );
void add_copper args( (CHAR_DATA *ch, long amount) );
void add_follower args( ( CHAR_DATA *ch, CHAR_DATA *master ) );
void add_gold args( (CHAR_DATA *ch, long amount) );
void add_hate args( ( CHAR_DATA *ch, CHAR_DATA *vict ) );
void add_maxload_index args( (int vnum, int signval, int game_load) );
void add_money args( (CHAR_DATA *ch, long amount) );
void add_platinum args( (CHAR_DATA *ch, long amount) );
void add_silver args( (CHAR_DATA *ch, long amount) );
void advance_level args( ( CHAR_DATA *ch, bool is_advance ) );
char * affect2_bit_name args( ( long vector ) );
char * affect_bit_name args( ( long vector ) );
void affect_join args( ( CHAR_DATA *ch, AFFECT_DATA *paf ) );
char * affect_loc_name args( ( int location ) );
void affect_remove args( ( CHAR_DATA *ch, AFFECT_DATA *paf ) );
void affect_remove_obj args( (OBJ_DATA *obj, AFFECT_DATA *paf ) );
void affect_strip args( ( CHAR_DATA *ch, int sn ) );
void affect_to_char args( ( CHAR_DATA *ch, AFFECT_DATA *paf ) );
void affect_to_obj args( ( OBJ_DATA *obj, AFFECT_DATA *paf ) );
void affect_to_room args( ( ROOM_INDEX_DATA *pRoom, ROOM_AFF_DATA *raf ) );
void aggrostab args( (CHAR_DATA *ch, CHAR_DATA *victim ) );
void * alloc_mem args( ( int sMem ) );
void * alloc_perm args( ( int sMem ) );
void append_file args( ( CHAR_DATA *ch, char *file, char *str ) );
int apply_ac args( ( OBJ_DATA *obj, int iWear, int type ) );
void area_update args( ( void ) );
int     atoi            args( ( const char *string ) );
void ban_update args( ( void ) );
void boot_db args( ( void ) );
void bug args( ( const char *str, int param ) );
int calc_apply_stats args( ( void ) );
int calc_modifier args( (int apply_stats, int item_type, int nr_rolls));
void *  calloc          args( ( unsigned nelem, size_t size ) );
int can_carry_n args( ( CHAR_DATA *ch ) );
int can_carry_w args( ( CHAR_DATA *ch ) );
bool can_drop_obj args( ( CHAR_DATA *ch, OBJ_DATA *obj ) );
bool can_loot args( (CHAR_DATA *ch, OBJ_DATA *obj) );
bool can_see args( ( CHAR_DATA *ch, const CHAR_DATA *victim ) );
bool can_see_obj args( ( CHAR_DATA *ch, const OBJ_DATA *obj ) );
bool can_see_room args( ( CHAR_DATA *ch, ROOM_INDEX_DATA *pRoomIndex) );
char * capitalize args( ( const char *str ) );
int castle_lookup args( ( const char *name) );
void char_from_obj args( ( OBJ_DATA *obj) );
void char_from_room args( ( CHAR_DATA *ch ) );
void char_to_obj args( ( CHAR_DATA *ch, OBJ_DATA *obj) );
void char_to_room args( ( CHAR_DATA *ch, ROOM_INDEX_DATA *pRoomIndex ) );
bool check_aggrostab args( (CHAR_DATA *ch, CHAR_DATA *victim ) );
bool check_hate args( (CHAR_DATA *ch, CHAR_DATA *vict ) );
int check_immune args( (CHAR_DATA *ch, int dam_type) );
void check_improve args( ( CHAR_DATA *ch, int sn, bool success, int multiplier ) );
void check_sex args( ( CHAR_DATA *ch) );
bool check_specials args( ( CHAR_DATA *ch, DO_FUN *cmd, char *arg) );
int class_lookup args( ( const char *name) );
void clear_char args( ( CHAR_DATA *ch ) );
void clone_mobile args( ( CHAR_DATA *parent, CHAR_DATA *clone) );
void clone_object args( ( OBJ_DATA *parent, OBJ_DATA *clone ) );
void close_socket args( ( DESCRIPTOR_DATA *dclose ) );
long coins_to_copper args( (const CHAR_DATA *ch) );
char * comm_bit_name args( ( long comm_flags ) );
void corpse_back args( ( CHAR_DATA *ch, OBJ_DATA *corpse ) );
int count_obj_list args( ( OBJ_INDEX_DATA *obj, OBJ_DATA *list ) );
CD * create_mobile args( ( MOB_INDEX_DATA *pMobIndex ) );
OD * create_money args( ( int amount, int type ) );
OD * create_object args( ( OBJ_INDEX_DATA *pObjIndex, int level ) );
void create_room args( ( int vnum ) );
char *  crypt           args( ( const char *key, const char *salt ) );
char *  crypt           args( ( const char *key, const char *salt ) );
char *  crypt           args( ( const char *key, const char *salt ) );
char *  crypt           args( ( const char *key, const char *salt ) );
char *  crypt           args( ( const char *key, const char *salt ) );
char *  crypt           args( ( const char *key, const char *salt ) );
char *  crypt           args( ( const char *key, const char *salt ) );
char *  crypt           args( ( const char *key, const char *salt ) );
char *  crypt           args( ( const char *key, const char *salt ) );
bool damage args( ( CHAR_DATA *ch, CHAR_DATA *victim, int dam, int dt, int class ) );
int dice args( ( int number, int size ) );
void die_follower args( ( CHAR_DATA *ch ) );
void do_bounce args( (OBJ_DATA *obj) );
void do_check_psi args( ( CHAR_DATA *ch, char *argument ) );
int do_maxload_item args( (int vnum) );
void do_start_hunting args( ( CHAR_DATA *hunter, CHAR_DATA *target, int ANNOY) );
void do_stop_hunting args( ( CHAR_DATA *ch, char *args ) );
char * drunk_speak args( (const char *str) );
void equip_char args( ( CHAR_DATA *ch, OBJ_DATA *obj, int iWear ) );
int exp_per_level args( ( CHAR_DATA *ch, int points ) );
extern		OBJ_DATA*               RELIC_1;
extern		OBJ_DATA*               RELIC_2;
extern		OBJ_DATA*               RELIC_3;
extern		OBJ_DATA*               RELIC_4;
extern		ROOM_INDEX_DATA*        RELIC_ROOM_1;
extern		ROOM_INDEX_DATA*        RELIC_ROOM_2;
extern		ROOM_INDEX_DATA*        RELIC_ROOM_3;
extern		ROOM_INDEX_DATA*        RELIC_ROOM_4;
extern		void 	(*move_table[])(CHAR_DATA*, char*);
extern          AFFECT_DATA       *     affect_free;
extern          BAN_DATA          *     ban_free;
extern          BAN_DATA          *     ban_list;
extern          bool                    fLogAll;
extern          char                    bug_buf         [];
extern          char                    log_buf         [];
extern          CHAR_DATA         *     char_free;
extern          CHAR_DATA         *     char_list;
extern          DESCRIPTOR_DATA   *     descriptor_free;
extern          DESCRIPTOR_DATA   *     descriptor_list;
extern          EXTRA_DESCR_DATA  *     extra_descr_free;
extern          FILE *                  fpReserve;
extern          HELP_DATA         *     help_first;
extern          HUNTER_DATA             hunter_list     [];
extern          KILL_DATA               kill_table      [];
extern          NOTE_DATA         *     note_free;
extern          NOTE_DATA         *     note_list;
extern          OBJ_DATA          *     obj_free;
extern          OBJ_DATA          *     object_list;
extern          PC_DATA           *     pcdata_free;
extern          ROOM_AFF_DATA     *     room_aff_free;
extern          ROOM_AFF_DATA     *     room_aff_list;
extern          ROOM_INDEX_DATA   *     room_index_free;
extern          SHOP_DATA         *     shop_first;
extern          struct social_type      social_table[MAX_SOCIALS];
extern          TELEPORT_ROOM_DATA*	teleport_room_list;
extern          TIME_INFO_DATA          time_info;
extern          time_t                  current_time;
extern          WEATHER_DATA            weather_info;
extern  char *  const                   title_table     [MAX_CLASS]
extern  const   struct  attack_type     attack_table    [];
extern  const   struct  class_type      class_table     [MAX_CLASS];
extern  const   struct  con_app_type    con_app         [MAX_STAT+1];
extern  const   struct  dex_app_type    dex_app         [MAX_STAT+1];
extern  const   struct  group_type      group_table     [MAX_GROUP];
extern  const   struct  guildmaster_type guildmaster_table [];
extern  const   struct  int_app_type    int_app         [MAX_STAT+1];
extern  const   struct  liq_type        liq_table       [LIQ_MAX];
extern  const   struct  pc_race_type    pc_race_table   [];
extern  const   struct  race_type       race_table      [];
extern  const   struct  skill_type      skill_table     [MAX_SKILL];
extern  const   struct  str_app_type    str_app         [MAX_STAT+1];
extern  const   struct  wis_app_type    wis_app         [MAX_STAT+1];
extern  int16_t  gsn_backstab;
extern  int16_t  gsn_blindness;
extern  int16_t  gsn_charm_person;
extern  int16_t  gsn_curse;
extern  int16_t  gsn_disarm;
extern  int16_t  gsn_dodge;
extern  int16_t  gsn_doorbash;
extern  int16_t  gsn_enhanced_damage;
extern  int16_t  gsn_ghostly_presence;
extern  int16_t  gsn_hide;
extern  int16_t  gsn_invis;
extern  int16_t  gsn_kick;
extern  int16_t  gsn_mass_invis;
extern  int16_t  gsn_parry;
extern  int16_t  gsn_peek;
extern  int16_t  gsn_pick_lock;
extern  int16_t  gsn_plague;
extern  int16_t  gsn_poison;
extern  int16_t  gsn_rescue;
extern  int16_t  gsn_search;
extern  int16_t  gsn_second_attack;
extern  int16_t  gsn_sleep;
extern  int16_t  gsn_smite;
extern  int16_t  gsn_sneak;
extern  int16_t  gsn_steal;
extern  int16_t  gsn_third_attack;
extern int16_t  gsn_aggrostab;
extern int16_t  gsn_archery;
extern int16_t  gsn_astral_walk;
extern int16_t  gsn_axe;
extern int16_t  gsn_bash;
extern int16_t  gsn_baura;
extern int16_t  gsn_berserk;
extern int16_t  gsn_blinding_fists;
extern int16_t  gsn_brew;
extern int16_t  gsn_clairvoyance;
extern int16_t  gsn_concoct;
extern int16_t  gsn_confuse;
extern int16_t  gsn_crane_dance;
extern int16_t  gsn_dagger;
extern int16_t  gsn_danger_sense;
extern int16_t  gsn_despair;
extern int16_t  gsn_destruction;
extern int16_t  gsn_dirt;
extern int16_t  gsn_dshield;
extern int16_t  gsn_dual_wield;
extern int16_t  gsn_ego_whip;
extern int16_t  gsn_fast_healing;
extern int16_t  gsn_fatality;
extern int16_t  gsn_fists_of_fury;
extern int16_t  gsn_flail;
extern int16_t  gsn_haggle;
extern int16_t  gsn_hand_to_hand;
extern int16_t  gsn_iron_skin;
extern int16_t  gsn_levitate;
extern int16_t  gsn_listen_at_door;
extern int16_t  gsn_lore;
extern int16_t  gsn_mace;
extern int16_t  gsn_meditation;
extern int16_t  gsn_mindbar;
extern int16_t  gsn_mindblast;
extern int16_t  gsn_nerve_damage;
extern int16_t  gsn_nightmare;
extern int16_t  gsn_phase;
extern int16_t  gsn_polearm;
extern int16_t  gsn_project;
extern int16_t  gsn_psionic_armor;
extern int16_t  gsn_psychic_shield;
extern int16_t  gsn_punch;
extern int16_t  gsn_pyrotechnics;
extern int16_t  gsn_recall;
extern int16_t  gsn_ride;
extern int16_t  gsn_scribe;
extern int16_t  gsn_scrolls;
extern int16_t  gsn_shield_block;
extern int16_t  gsn_shift;
extern int16_t  gsn_shove;
extern int16_t  gsn_sleight_of_hand;
extern int16_t  gsn_spear;
extern int16_t  gsn_staves;
extern int16_t  gsn_stealth;
extern int16_t  gsn_steel_fist;
extern int16_t  gsn_stunning_blow;
extern int16_t  gsn_sword;
extern int16_t  gsn_telekinesis;
extern int16_t  gsn_torment;
extern int16_t  gsn_tracking;
extern int16_t  gsn_transfusion;
extern int16_t  gsn_trip;
extern int16_t  gsn_wands;
extern int16_t  gsn_whip;
char * extra2_bit_name args( ( int extra_flags ) );
char * extra_bit_name args( ( int extra_flags ) );
void extract_char args( ( CHAR_DATA *ch, bool fPull ) );
void extract_obj args( ( OBJ_DATA *obj ) );
void extract_obj_player args( ( OBJ_DATA *obj ) );
void extract_room args( ( ROOM_INDEX_DATA *pRoom ) );
int     fclose          args( ( FILE *stream ) );
int     fclose          args( ( FILE *stream ) );
void fill_comm_table_index args( (void) );
void fill_social_table_index args( (void) );
char * first_arg args( ( char *argument, char *arg_first, bool fCase ) );
long flag_convert args( ( char letter) );
char * form_bit_name args( ( long form_flags ) );
int     fprintf         args( ( FILE *stream, const char *format, ... ) );
int     fprintf         args( ( FILE *stream, const char *format, ... ) );
int     fread           args( ( void *ptr, int size, int n, FILE *stream ) );
siz_t   fread           args( ( void *ptr, size_t size, size_t n,
int     fread           args( ( void *ptr, int size, int n, FILE *stream ) );
long fread_flag args( ( FILE *fp ) );
char fread_letter args( ( FILE *fp ) );
long fread_long args( ( FILE *fp ) );
int fread_number args( ( FILE *fp ) );
char * fread_string args( ( FILE *fp ) );
char * fread_string_eol args(( FILE *fp ) );
void fread_to_eol args( ( FILE *fp ) );
char * fread_word args( ( FILE *fp ) );
void free_affect args( ( AFFECT_DATA* pAf ) );
void free_char args( ( CHAR_DATA *ch ) );
void free_mem args( ( void *pMem, int sMem ) );
void free_string args( ( char *pstr ) );
int     fseek           args( ( FILE *stream, long offset, int ptrname ) );
int     fseek           args( ( FILE *stream, long offset, int ptrname ) );
void gain_condition args( ( CHAR_DATA *ch, int iCond, int value ) );
void gain_exp args( ( CHAR_DATA *ch, int gain ) );
int get_age args( ( CHAR_DATA *ch ) );
char* get_castlename args( ( const int guild ) );
CD * get_char_room args( ( CHAR_DATA *ch, char *argument ) );
CD * get_char_world args( ( CHAR_DATA *ch, char *argument ) );
int get_curr_stat args( ( CHAR_DATA *ch, int stat ) );
OD * get_eq_char args( ( CHAR_DATA *ch, int iWear ) );
char * get_extra_descr args( ( const char *name, EXTRA_DESCR_DATA *ed ) );
char* get_guildname args( ( const int guild ) );
int get_max_train args( ( CHAR_DATA *ch, int stat ) );
ITEM_MAX_LOAD * get_maxload_index args( (int vnum) );
MID * get_mob_index args( ( int vnum ) );
void get_obj args( ( CHAR_DATA *ch, OBJ_DATA *obj, OBJ_DATA *container ) );
OD * get_obj_carry args( ( CHAR_DATA *ch, char *argument ) );
OD * get_obj_here args( ( CHAR_DATA *ch, char *argument ) );
OID * get_obj_index args( ( int vnum ) );
OD * get_obj_list args( ( CHAR_DATA *ch, char *argument, OBJ_DATA *list ) );
int get_obj_number args( ( OBJ_DATA *obj ) );
OD * get_obj_type args( ( OBJ_INDEX_DATA *pObjIndexData ) );
OD * get_obj_wear args( ( CHAR_DATA *ch, char *argument ) );
int get_obj_weight args( ( OBJ_DATA *obj ) );
OD * get_obj_world args( ( CHAR_DATA *ch, char *argument ) );
RID *get_random_room args ( ( CHAR_DATA *ch ) );
RID * get_room_index args( ( int vnum ) );
int get_skill args( ( const CHAR_DATA *ch, int sn ) );
int get_trust args( ( CHAR_DATA *ch ) );
int get_weapon_skill args(( CHAR_DATA *ch, int sn ) );
int get_weapon_sn args( ( CHAR_DATA *ch ) );
void gn_add args( ( CHAR_DATA *ch, int gn) );
void gn_remove args( ( CHAR_DATA *ch, int gn) );
void grant_psionics args( ( CHAR_DATA *ch, int chance, bool force_grant ) );
void group_add args( ( CHAR_DATA *ch, const char *name, bool deduct) );
int group_lookup args( (const char *name) );
void group_remove args( ( CHAR_DATA *ch, const char *name) );
int guild_lookup args( ( const char *name) );
bool has_enough_gold args( (const CHAR_DATA *ch, long gold_cost) );
void hunt_victim args( ( CHAR_DATA *ch, int ANNOY ) );
char * imm2_bit_name args( ( long imm_flags ) );
char * imm_bit_name args( ( long imm_flags ) );
int mana_cost (CHAR_DATA *ch, int min_mana, int level);
int interpolate args( ( int level, int value_00, int value_32 ) );
void interpret args( ( CHAR_DATA *ch, char *argument ) );
bool is_affected args( ( CHAR_DATA *ch, int sn ) );
bool is_full_name args( ( char *str, char *namelist ) );
bool is_name args( ( const char *str, const char *namelist ) );
bool is_note_to args( ( CHAR_DATA *ch, NOTE_DATA *pnote ) );
bool is_number args( ( char *arg ) );
bool is_old_mob args ( (CHAR_DATA *ch) );
bool is_safe args( (CHAR_DATA *ch, CHAR_DATA *victim ) );
bool is_safe_spell args( (CHAR_DATA *ch, CHAR_DATA *victim, bool area ) );
bool is_same_group args( ( CHAR_DATA *ach, CHAR_DATA *bch ) );
char * item_type_name args( ( OBJ_DATA *obj ) );
void list_group_costs args( ( CHAR_DATA *ch ) );
void list_group_known args( ( CHAR_DATA *ch ) );
bool load_char_obj args( ( DESCRIPTOR_DATA *d, char *name ) );
void load_pkills args( ( void ) );
void load_wizlist args( ( void ) );
void log_string args( ( const char *str ) );
void make_descriptor args( ( DESCRIPTOR_DATA *dnew, int desc ) );
int material_lookup args( ( const char *name) );
char* material_name args( (int material) );
void move_char args( ( CHAR_DATA *ch, int door, bool follow ) );
void multi_hit args( ( CHAR_DATA *ch, CHAR_DATA *victim, int dt ) );
AFFECT_DATA *new_affect args( ( void ) );
long next_xp_level args( ( CHAR_DATA *ch ) );
bool normalize_psionic_arguments args( ( const char *argument, char *output, size_t length, char *invalid ) );
void nuke_pets args( ( CHAR_DATA *ch ) );
int number_argument args( ( char *argument, char *arg ) );
int number_bits args( ( int width ) );
int number_door args( ( void ) );
int number_fuzzy args( ( int number ) );
int number_mm args( ( void ) );
int number_percent args( ( void ) );
int number_range args( ( int from, int to ) );
void obj_cast_spell args( ( int sn, int level, CHAR_DATA *ch, CHAR_DATA *victim, OBJ_DATA *obj ) );
void obj_from_char args( ( OBJ_DATA *obj ) );
void obj_from_obj args( ( OBJ_DATA *obj ) );
void obj_from_room args( ( OBJ_DATA *obj ) );
void obj_to_char args( ( OBJ_DATA *obj, CHAR_DATA *ch ) );
void obj_to_obj args( ( OBJ_DATA *obj, OBJ_DATA *obj_to ) );
void obj_to_room args( ( OBJ_DATA *obj, ROOM_INDEX_DATA *pRoomIndex ) );
char * off2_bit_name args( ( long off_flags ) );
char * off_bit_name args( ( long off_flags ) );
char * one_argument args( ( char *argument, char *arg_first ) );
void one_hit args( ( CHAR_DATA *ch, CHAR_DATA *victim, int dt ) );
void page_to_char args( ( const char *txt, CHAR_DATA *ch ) );
bool parse_gen_groups args( ( CHAR_DATA *ch,char *argument ) );
char * part_bit_name args( ( long part_flags ) );
void    perror          args( ( const char *s ) );
void    perror          args( ( const char *s ) );
int query_carry_coins args( ( CHAR_DATA *ch, long amount) );
int query_carry_weight args( ( CHAR_DATA *ch) );
long query_gold args( (CHAR_DATA *ch) );
int race_lookup args( ( const char *name) );
void raw_kill args( ( CHAR_DATA *ch, CHAR_DATA *victim ) );
void read_maxload_file args( (void) );
void recheck_sneak args( ( CHAR_DATA *ch ) );
void remove_all_hates args( ( CHAR_DATA *ch ) );
void remove_hate args( ( CHAR_DATA *ch, CHAR_DATA *vict ) );
void remove_room_affect args( ( ROOM_INDEX_DATA *pRoom, ROOM_AFF_DATA *raf ) );
char * res_bit_name args( ( long res_flags) );
void reset_char args( ( CHAR_DATA *ch ) );
void respawn_relic args( ( int i ) );
void room_affect args( (CHAR_DATA *ch, ROOM_INDEX_DATA *pRoom, int door) );
char * room_flag2_name args( ( int room_flag ) );
char * room_flag_name args( ( int room_flag ) );
bool room_is_dark args( ( ROOM_INDEX_DATA *pRoomIndex ) );
bool room_is_private args( ( ROOM_INDEX_DATA *pRoomIndex ) );
void save_char_obj args( ( CHAR_DATA *ch ) );
void save_pkills args( ( void ) );
void save_wizlist args( ( void ) );
bool saves_spell args( ( int level, CHAR_DATA *victim ) );
void send_info args( ( char *argument ) );
void send_to_char args( ( const char *txt, CHAR_DATA *ch ) );
void send_to_room args( ( const char *txt, int vnum ) );
void set_title args( ( CHAR_DATA *ch, char *title ) );
void show_obj_condition args((OBJ_DATA *obj, CHAR_DATA *ch));
void show_string args( ( struct descriptor_data *d, char *input) );
int skill_lookup args( ( const char *name ) );
int slot_lookup args( ( int slot ) );
void smash_tilde args( ( char *str ) );
char * speak_filter args( (CHAR_DATA *ch, const char *str) );
SF * spec_lookup args( ( const char *name ) );
char * special_name args( ( SPEC_FUN *spec ) );
size_t strlcat(char *dst, const char *src, size_t siz);
size_t strlcpy(char *dst, const char *src, size_t siz);
void stop_fighting args( ( CHAR_DATA *ch, bool fBoth ) );
void stop_follower args( ( CHAR_DATA *ch ) );
bool str_cmp args( ( const char *astr, const char *bstr ) );
int str_counter args( ( const char *astr, const char *bstr ) );
char * str_dup args( ( const char *str ) );
bool str_infix args( ( const char *astr, const char *bstr ) );
bool str_prefix args( ( const char *astr, const char *bstr ) );
bool str_suffix args( ( const char *astr, const char *bstr ) );
struct  affect_data
struct  area_data
struct  ban_data
struct  board_data
struct  char_data
struct  class_type
struct  con_app_type
struct  descriptor_data
struct  dex_app_type
struct  exit_data
struct  extra_descr_data
struct  group_type
struct  help_data
struct  int_app_type
struct  kill_data
struct  liq_type
struct  mob_index_data
struct  note_data
struct  obj_data
struct  obj_index_data
struct  pc_data
struct  reset_data
struct  room_index_data
struct  shop_data
struct  skill_type
struct  social_type
struct  str_app_type
struct  time_info_data
struct  weather_data
struct  wis_app_type
struct  wiz_data
struct alias_data
struct attack_type
struct col_disp_table_type
struct col_table_type
struct gen_data
struct guildmaster_type
struct hate_data
struct hunter_data
struct item_max_load
struct mob_action_data
struct my_mesg_buf{
struct obj_action_data
struct offense_data
struct pc_race_type  /* additional data for pc races */
struct pkill_list_data
struct race_type
struct room_aff_data
struct teleport_room_data
struct were_form
void tail_chain args( ( void ) );
typedef struct  affect_data             AFFECT_DATA;
typedef struct  alias_data              ALIAS_DATA;
typedef struct  area_data               AREA_DATA;
typedef struct  ban_data                BAN_DATA;
typedef struct  board_data              BOARD_DATA;
typedef struct  char_data               CHAR_DATA;
typedef struct  descriptor_data         DESCRIPTOR_DATA;
typedef struct  exit_data               EXIT_DATA;
typedef struct  extra_descr_data        EXTRA_DESCR_DATA;
typedef struct  gen_data                GEN_DATA;
typedef struct  hate_data		HATE_DATA;
typedef struct  help_data               HELP_DATA;
typedef struct  hunter_data             HUNTER_DATA;
typedef struct  item_max_load           ITEM_MAX_LOAD;
typedef struct  kill_data               KILL_DATA;
typedef struct  mob_action_data         MOB_ACTION_DATA;
typedef struct  mob_index_data          MOB_INDEX_DATA;
typedef struct  note_data               NOTE_DATA;
typedef struct  obj_action_data		OBJ_ACTION_DATA;
typedef struct  obj_data                OBJ_DATA;
typedef struct  obj_index_data          OBJ_INDEX_DATA;
typedef struct  offense_data            OFFENSE_DATA;
typedef struct  pc_data                 PC_DATA;
typedef struct  pkill_list_data         PKILL_LIST_DATA;
typedef struct  reset_data              RESET_DATA;
typedef struct  room_aff_data           ROOM_AFF_DATA;
typedef struct  room_index_data         ROOM_INDEX_DATA;
typedef struct  shop_data               SHOP_DATA;
typedef struct  teleport_room_data      TELEPORT_ROOM_DATA;
typedef struct  time_info_data          TIME_INFO_DATA;
typedef struct  weather_data            WEATHER_DATA;
typedef struct  were_form		WERE_FORM;
typedef struct  wiz_data                WIZ_DATA;
void unequip_char args( ( CHAR_DATA *ch, OBJ_DATA *obj ) );
int     ungetc          args( ( int c, FILE *stream ) );
int     ungetc          args( ( int c, FILE *stream ) );
void update_handler args( ( void ) );
void update_pkills args( ( CHAR_DATA *ch ) );
void update_pos args( ( CHAR_DATA *victim ) );
void update_relics args( ( void ) );
void update_wizlist args( ( CHAR_DATA *ch, int level ) );
void violence_update args( ( void ) );
void handle_web(void);
void init_web(int port);
void shutdown_web(void);
char * vuln_bit_name args( ( long vuln_flags) );
char * weapon_bit_name args( ( int weapon_flags ) );
char * wear_bit_name args( ( int wear_flags ) );
void wizinfo args( ( char *info, int level ) );
void write_maxload_file args( (void) );
void write_to_buffer args( ( DESCRIPTOR_DATA *d, const char *txt, int length ) );
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{
{       OFFENSE_DATA   *next;
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
};
}board_type;
#undef  CD
#undef  MID
#undef  OD
#undef  OID
#undef  RID
#undef  SF

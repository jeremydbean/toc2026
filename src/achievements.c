#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#include "merc.h"
#include "interp.h"
#include "magic.h"

#define HYRULE_DUNGEON_MASK 0x1FFUL
/* Staff by trust, as every command gate decides it: a staff kill, buy or
   walk is not play, so it earns none of the 2026-10-25 feats. */
#define ACH_STAFF(ch) IS_TRUSTED((ch), LEVEL_IMMORTAL)
#define HYRULE_SHARD_MASK   0x0FFUL

typedef enum
{
    ACH_CAT_CHARACTER = 0,
    ACH_CAT_COMBAT,
    ACH_CAT_ENCOUNTERS,
    ACH_CAT_QUESTS,
    ACH_CAT_EXPLORATION,
    ACH_CAT_COLLECTION,
    ACH_CAT_CRAFTING,
    ACH_CAT_MISADVENTURE,
    ACH_CAT_ECONOMY,
    ACH_CAT_HYRULE,
    ACH_CAT_COUNT
} ACHIEVEMENT_CATEGORY;

typedef enum
{
    ACH_REQ_LEVEL = 0,
    ACH_REQ_REMORTS,
    ACH_REQ_PLAYED,
    ACH_REQ_MOB_KILLS,
    ACH_REQ_PKILLS,
    ACH_REQ_QUESTS,
    ACH_REQ_QUEST_STREAK,
    ACH_REQ_DEATHS,
    ACH_REQ_BANK_BALANCE,
    ACH_REQ_CARRIED_MONEY,
    ACH_REQ_ALL_DENOMINATIONS,
    ACH_REQ_CASINO_WINNINGS,
    ACH_REQ_CASINO_LOSSES,
    ACH_REQ_ROOM,
    ACH_REQ_OBJECT,
    ACH_REQ_EVENT,
    ACH_REQ_HYRULE_DUNGEONS,
    ACH_REQ_HYRULE_MAPS,
    ACH_REQ_HYRULE_COMPASSES,
    ACH_REQ_HYRULE_KIT,
    ACH_REQ_TRIFORCE_SHARDS,
    ACH_REQ_BOSS,
    ACH_REQ_HYRULE_BOSSES,
    ACH_REQ_WORLD_BOSSES,
    ACH_REQ_RARE_ITEMS,
    ACH_REQ_CRAFTING_FEATS,
    ACH_REQ_MISADVENTURES,
    /* 2026-10-25 */
    ACH_REQ_COUNTER,            /* auxiliary: achievement_counter */
    ACH_REQ_SET,                /* auxiliary: achievement_set */
    ACH_REQ_COHORT,             /* auxiliary: cohort; target 0 means all */
    ACH_REQ_MASTERED_SKILLS,    /* abilities at 100% */
    ACH_REQ_MASTERED_WEAPONS,   /* weapon proficiencies at 100% */
    ACH_REQ_PSI_POWERS,         /* psionic powers known */
    ACH_REQ_HYRULE_SECRETS,     /* auxiliary: which secret bits */
    ACH_REQ_STASH_CEILING       /* stash bought to its ceiling */
} ACHIEVEMENT_REQUIREMENT;

typedef struct achievement_definition
{
    const char *key;
    const char *title;
    const char *description;
    ACHIEVEMENT_CATEGORY category;
    int points;
    bool hidden;
    ACHIEVEMENT_REQUIREMENT requirement;
    long target;
    int auxiliary;
} ACHIEVEMENT_DEFINITION;

static const char *const achievement_category_names[ACH_CAT_COUNT] =
{
    "Character",
    "Combat",
    "Encounters",
    "Quests",
    "Exploration",
    "Collection",
    "Crafting",
    "Misadventure",
    "Economy",
    "Hyrule"
};

static const int hyrule_dungeon_entrances[9] =
{
    30401, 30418, 30437, 30456, 30476,
    30501, 30527, 30562, 30590
};

/* Explicit lists a meta counts; see the cohort section below. */
enum
{
    ACH_COHORT_WORLD_BOSSES_V1 = 0,
    ACH_COHORT_RARE_ITEMS_V1,
    ACH_COHORT_CRAFTING_V1,
    ACH_COHORT_MISADVENTURES_V1,
    ACH_COHORT_HYRULE_BOSSES_V1,
    ACH_COHORT_LANDMARKS_V1,
    ACH_COHORT_DARK_TOWER,
    ACH_COHORT_PANTHEON,
    ACH_COHORT_HEAVENS_GATE,
    ACH_COHORT_NECROMANCY,
    ACH_COHORT_CRYSTALLINE,
    ACH_COHORT_DISASTERS,
    ACH_COHORT_HYRULE_TOOLS,
    ACH_COHORT_HYRULE_CHESTS,
    ACH_COHORT_HYRULE_BANDS,
    ACH_COHORT_TRIPLE_CRAFT,
    ACH_COHORT_GUARDIAN_ANGEL,
    ACH_COHORT_RARE_SIGHTINGS,
    ACH_COHORT_COUNT
};

/* Which bits of pcdata->hyrule_secrets an ACH_REQ_HYRULE_SECRETS row
   counts (bit layout at the top of hyrule.c's secrets section). */
#define ACH_SECRETS_MONEY_CAVES  0
#define ACH_SECRETS_BOMB_BAG_L5  1
#define ACH_SECRETS_BOMB_BAG_L7  2
#define ACH_SECRETS_BOMB_BAGS    3
#define ACH_SECRETS_TAKE_ANY     4

/* A boss row whose auxiliary is negative counts a death anywhere in the
   area of room -auxiliary: Prince Starfire is WIMPY and may flee his
   bedroom before he falls. */

static const ACHIEVEMENT_DEFINITION achievement_table[] =
{
    { "level-5", "Out of the Nest", "Reach level 5.", ACH_CAT_CHARACTER, 5, false, ACH_REQ_LEVEL, 5, 0 },
    { "level-10", "Finding Your Feet", "Reach level 10.", ACH_CAT_CHARACTER, 5, false, ACH_REQ_LEVEL, 10, 0 },
    { "level-15", "Road Tested", "Reach level 15.", ACH_CAT_CHARACTER, 5, false, ACH_REQ_LEVEL, 15, 0 },
    { "level-20", "Coming Into Your Own", "Reach level 20.", ACH_CAT_CHARACTER, 5, false, ACH_REQ_LEVEL, 20, 0 },
    { "level-25", "Seasoned Adventurer", "Reach level 25.", ACH_CAT_CHARACTER, 10, false, ACH_REQ_LEVEL, 25, 0 },
    { "level-30", "Halfway to Immortality", "Reach level 30.", ACH_CAT_CHARACTER, 10, false, ACH_REQ_LEVEL, 30, 0 },
    { "level-40", "Veteran of Chaos", "Reach level 40.", ACH_CAT_CHARACTER, 15, false, ACH_REQ_LEVEL, 40, 0 },
    { "level-50", "A Hero Rises", "Reach level 50.", ACH_CAT_CHARACTER, 20, false, ACH_REQ_LEVEL, 50, 0 },
    { "level-55", "Beyond Heroic", "Reach level 55.", ACH_CAT_CHARACTER, 25, false, ACH_REQ_LEVEL, 55, 0 },
    { "level-58", "One Step from the Summit", "Reach level 58.", ACH_CAT_CHARACTER, 35, false, ACH_REQ_LEVEL, 58, 0 },
    { "level-59", "Pinnacle of Mortal Power", "Reach level 59.", ACH_CAT_CHARACTER, 40, false, ACH_REQ_LEVEL, 59, 0 },
    { "first-remort", "Begin Again", "Complete your first remort.", ACH_CAT_CHARACTER, 15, false, ACH_REQ_REMORTS, 1, 0 },
    { "five-remorts", "Five Lives, One Legend", "Complete five remorts.", ACH_CAT_CHARACTER, 50, false, ACH_REQ_REMORTS, 5, 0 },
    { "day-played", "A Day in the Realms", "Accumulate 24 hours of play time.", ACH_CAT_CHARACTER, 10, false, ACH_REQ_PLAYED, 86400L, 0 },
    { "week-played", "No Place Like ToC", "Accumulate seven days of play time.", ACH_CAT_CHARACTER, 30, false, ACH_REQ_PLAYED, 604800L, 0 },

    { "first-kill", "First Blood", "Defeat your first mobile.", ACH_CAT_COMBAT, 5, false, ACH_REQ_MOB_KILLS, 1, 0 },
    { "hundred-kills", "Monster Hunter", "Defeat 100 mobiles.", ACH_CAT_COMBAT, 10, false, ACH_REQ_MOB_KILLS, 100, 0 },
    { "thousand-kills", "Slayer", "Defeat 1,000 mobiles.", ACH_CAT_COMBAT, 25, false, ACH_REQ_MOB_KILLS, 1000, 0 },
    { "ten-thousand-kills", "Scourge of the Realms", "Defeat 10,000 mobiles.", ACH_CAT_COMBAT, 60, false, ACH_REQ_MOB_KILLS, 10000, 0 },
    { "first-pkill", "A Worthy Opponent", "Earn your first qualifying player kill.", ACH_CAT_COMBAT, 10, false, ACH_REQ_PKILLS, 1, 0 },
    { "twenty-five-pkills", "Battle Tested", "Earn 25 qualifying player kills.", ACH_CAT_COMBAT, 30, false, ACH_REQ_PKILLS, 25, 0 },
    { "hundred-pkills", "Nemesis", "Earn 100 qualifying player kills.", ACH_CAT_COMBAT, 60, false, ACH_REQ_PKILLS, 100, 0 },
    { "farslay-kill", "Death from Afar", "Farslay another player without suffering the rite's backlash.", ACH_CAT_COMBAT, 25, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_FARSLAY_KILL, 0 },

    { "boss-tarrasque", "The World Still Stands", "Defeat the Tarrasque in the Forsaken Lands.", ACH_CAT_ENCOUNTERS, 75, false, ACH_REQ_BOSS, 15475, 15480 },
    { "boss-borg", "Resistance Was Not Futile", "Defeat the Borg at the end of the World.", ACH_CAT_ENCOUNTERS, 75, false, ACH_REQ_BOSS, 29410, 29498 },
    { "boss-korzath", "Cause and Effect", "Defeat Korzath in his throne room.", ACH_CAT_ENCOUNTERS, 75, false, ACH_REQ_BOSS, 29229, 29321 },
    { "boss-master-guardian", "No Master Above Me", "Defeat the Master Guardian beside Korzath.", ACH_CAT_ENCOUNTERS, 75, false, ACH_REQ_BOSS, 29228, 29321 },
    { "boss-white-light", "Into the Light", "Defeat the brilliant white light deep in the Crypt.", ACH_CAT_ENCOUNTERS, 60, false, ACH_REQ_BOSS, 24216, 24257 },
    { "boss-smaug", "There and Back Again", "Defeat Smaug beneath the Lonely Mountain.", ACH_CAT_ENCOUNTERS, 50, false, ACH_REQ_BOSS, 25001, 25022 },
    { "boss-minotaur-god", "No Thread Required", "Defeat the minotaur god in Tarin.", ACH_CAT_ENCOUNTERS, 50, false, ACH_REQ_BOSS, 5616, 5687 },
    { "boss-zeus", "Storm Warning", "Defeat Zeus on Mount Olympus.", ACH_CAT_ENCOUNTERS, 45, false, ACH_REQ_BOSS, 901, 910 },
    { "boss-odin", "Allfather, All Fallen", "Defeat Odin in Valhalla.", ACH_CAT_ENCOUNTERS, 45, false, ACH_REQ_BOSS, 914, 929 },
    { "boss-ra", "Sunset", "Defeat Ra the Sun God on Mount Olympus.", ACH_CAT_ENCOUNTERS, 45, false, ACH_REQ_BOSS, 919, 931 },
    { "boss-dagahze", "Dawn Goes Dark", "Defeat Dagahze of Lathander in Tritia.", ACH_CAT_ENCOUNTERS, 50, false, ACH_REQ_BOSS, 10204, 10270 },
    { "boss-lolth", "Web Cut", "Defeat Lolth in the Drow stronghold.", ACH_CAT_ENCOUNTERS, 45, false, ACH_REQ_BOSS, 5112, 5151 },
    { "boss-eilistraee", "Last Dance", "Defeat Eilistraee beneath the Mushroom Kingdom.", ACH_CAT_ENCOUNTERS, 50, false, ACH_REQ_BOSS, 25209, 25265 },
    { "boss-dracolich", "Dust to Dust", "Defeat the Dracolich in Azeroth.", ACH_CAT_ENCOUNTERS, 45, false, ACH_REQ_BOSS, 28124, 28127 },
    { "boss-ashen-herald", "Silence the Herald", "Defeat the Ashen Herald in the Ashen Wastes.", ACH_CAT_ENCOUNTERS, 50, false, ACH_REQ_BOSS, 26719, 26709 },
    { "boss-lord-british", "Regicide in Britannia", "Defeat Lord British in Ultima.", ACH_CAT_ENCOUNTERS, 50, false, ACH_REQ_BOSS, 7664, 7767 },
    { "boss-lanatir", "Icebreaker", "Defeat Lanatir in the Ice Keep.", ACH_CAT_ENCOUNTERS, 40, false, ACH_REQ_BOSS, 18002, 18073 },
    { "five-world-bosses", "Boss Hunter", "Defeat five listed world bosses.", ACH_CAT_ENCOUNTERS, 100, false, ACH_REQ_WORLD_BOSSES, 5, 0 },
    { "all-world-bosses", "Conqueror of Chaos", "Defeat every listed world boss.", ACH_CAT_ENCOUNTERS, 200, false, ACH_REQ_WORLD_BOSSES, 17, 0 },

    { "first-quest", "Answering the Call", "Complete your first quest.", ACH_CAT_QUESTS, 5, false, ACH_REQ_QUESTS, 1, 0 },
    { "ten-quests", "Reliable Help", "Complete 10 quests.", ACH_CAT_QUESTS, 10, false, ACH_REQ_QUESTS, 10, 0 },
    { "fifty-quests", "Quest Veteran", "Complete 50 quests.", ACH_CAT_QUESTS, 25, false, ACH_REQ_QUESTS, 50, 0 },
    { "hundred-quests", "Champion for Hire", "Complete 100 quests.", ACH_CAT_QUESTS, 40, false, ACH_REQ_QUESTS, 100, 0 },
    { "two-hundred-fifty-quests", "The Realm's Retainer", "Complete 250 quests.", ACH_CAT_QUESTS, 60, false, ACH_REQ_QUESTS, 250, 0 },
    { "five-hundred-quests", "The Realm Owes You", "Complete 500 quests.", ACH_CAT_QUESTS, 75, false, ACH_REQ_QUESTS, 500, 0 },
    { "five-quest-streak", "On a Roll", "Complete five quests in a row.", ACH_CAT_QUESTS, 10, false, ACH_REQ_QUEST_STREAK, 5, 0 },
    { "ten-quest-streak", "Unbroken Resolve", "Complete ten quests in a row.", ACH_CAT_QUESTS, 25, false, ACH_REQ_QUEST_STREAK, 10, 0 },
    { "twenty-five-quest-streak", "Unshakable", "Complete twenty-five quests in a row.", ACH_CAT_QUESTS, 50, false, ACH_REQ_QUEST_STREAK, 25, 0 },
    { "quest-rush", "Rush Delivery", "Complete a rush contract before its shortened timer expires.", ACH_CAT_QUESTS, 15, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_QUEST_RUSH, 0 },
    { "quest-emergency", "When It Could Not Wait", "Complete an emergency contract before its five-minute timer expires.", ACH_CAT_QUESTS, 40, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_QUEST_EMERGENCY, 0 },
    { "quest-last-minute", "Under the Wire", "Complete an automatic quest in its final minute.", ACH_CAT_QUESTS, 20, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_QUEST_LAST_MINUTE, 0 },
    { "quest-gamble-win", "Double or Nothing", "Win an automatic-quest double-or-nothing gamble.", ACH_CAT_QUESTS, 15, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_QUEST_GAMBLE_WIN, 0 },
    { "daily-first", "Daily Bread", "Complete a daily quest.", ACH_CAT_QUESTS, 5, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DAILY_QUEST, 0 },
    { "daily-full-day", "A Full Day's Work", "Complete all three daily quests in one day.", ACH_CAT_QUESTS, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DAILY_SET, 0 },
    { "daily-streak-week", "Seven Days Running", "Complete every daily quest seven days in a row.", ACH_CAT_QUESTS, 25, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DAILY_STREAK_WEEK, 0 },
    { "daily-streak-month", "A Month of Devotion", "Complete every daily quest thirty days in a row.", ACH_CAT_QUESTS, 60, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DAILY_STREAK_MONTH, 0 },
    { "daily-streak-hundred", "Clockwork", "Complete every daily quest a hundred days in a row.", ACH_CAT_QUESTS, 100, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DAILY_STREAK_HUNDRED, 0 },
    { "daily-train", "Earned the Hard Way", "Trade daily points for a train.", ACH_CAT_QUESTS, 30, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DAILY_TRAIN, 0 },
    { "well-rested", "Well Rested", "Come back to the game rested.", ACH_CAT_CHARACTER, 5, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_WELL_RESTED, 0 },
    { "quest-keepsake", "A Token of Esteem", "Acquire a questmaster's keepsake trophy.", ACH_CAT_QUESTS, 20, false, ACH_REQ_OBJECT, 20306, 0 },

    { "hyrule-arrival", "A Hero Awakens", "Be teleported into the First Quest entrance of Hyrule.", ACH_CAT_EXPLORATION, 10, false, ACH_REQ_ROOM, 30200, 0 },
    { "hyrule-cartographer", "Across Hyrule", "Discover the entrance to all nine Hyrule dungeons.", ACH_CAT_EXPLORATION, 30, false, ACH_REQ_HYRULE_DUNGEONS, 9, 0 },

    /* Every room below is the destination of a published route, so
       it is reachable on foot from the Oak Tree Square. Points
       follow the walk: the route walker puts Mud School six rooms
       out and Valhalla ninety-four. */
    { "visit-mud-school", "Back to School", "Find the entrance to Mud School.", ACH_CAT_EXPLORATION, 5, false, ACH_REQ_ROOM, 3700, 0 },
    { "visit-casino", "Feeling Lucky", "Step into the Lucky Dragon Casino.", ACH_CAT_EXPLORATION, 5, false, ACH_REQ_ROOM, 4810, 0 },
    { "visit-smurf", "Little Blue Trail", "Follow the dimly lit path into Smurf Village.", ACH_CAT_EXPLORATION, 5, false, ACH_REQ_ROOM, 101, 0 },
    { "visit-haon-dor", "Edge of the Forest", "Reach the edge of Haon Dor.", ACH_CAT_EXPLORATION, 5, false, ACH_REQ_ROOM, 6000, 0 },
    { "visit-gangland", "Wrong Side of Town", "Find the dark alleyway into Gangland.", ACH_CAT_EXPLORATION, 5, false, ACH_REQ_ROOM, 2101, 0 },
    { "visit-moria", "Into the Hills", "Reach the hills above Moria.", ACH_CAT_EXPLORATION, 10, false, ACH_REQ_ROOM, 4000, 0 },
    { "visit-thalos", "The Dwarf Forest", "Reach the dwarf forest outside Thalos.", ACH_CAT_EXPLORATION, 10, false, ACH_REQ_ROOM, 5261, 0 },
    { "visit-shire", "A Well Kept Path", "Find the well kept path into the Shire.", ACH_CAT_EXPLORATION, 10, false, ACH_REQ_ROOM, 1100, 0 },
    { "visit-astral", "Bottom of the Rainbow", "Stand at the bottom of the rainbow.", ACH_CAT_EXPLORATION, 15, false, ACH_REQ_ROOM, 7500, 0 },
    { "visit-drow-city", "Beneath the Surface", "Walk a street of the Drow City.", ACH_CAT_EXPLORATION, 15, false, ACH_REQ_ROOM, 5114, 0 },
    { "visit-wyvern", "The Long Road East", "Reach the main eastern road below Wyvern's Tower.", ACH_CAT_EXPLORATION, 15, false, ACH_REQ_ROOM, 1701, 0 },
    { "visit-solace", "Gateway to Solace", "Arrive at the gateway to Solace.", ACH_CAT_EXPLORATION, 15, false, ACH_REQ_ROOM, 13201, 0 },
    { "visit-arachnos", "Webbed Entrance", "Find the webbed entrance to Arachnos.", ACH_CAT_EXPLORATION, 15, false, ACH_REQ_ROOM, 6301, 0 },
    { "visit-pyramid", "The Great Eastern Desert", "Cross into the Great Eastern Desert.", ACH_CAT_EXPLORATION, 20, false, ACH_REQ_ROOM, 28000, 0 },
    { "visit-olympus", "Climbing to the Gods", "Reach the mountain of Olympus.", ACH_CAT_EXPLORATION, 20, false, ACH_REQ_ROOM, 901, 0 },
    { "visit-hell", "Stone Archway", "Pass under the stone archway of the Descent.", ACH_CAT_EXPLORATION, 25, false, ACH_REQ_ROOM, 13401, 0 },
    { "visit-abyss", "Lost in the Mountains", "Find your way to the Abyss.", ACH_CAT_EXPLORATION, 25, false, ACH_REQ_ROOM, 24501, 0 },
    { "visit-battleground", "Heroes Hall", "Reach Heroes Hall in the Battleground.", ACH_CAT_EXPLORATION, 30, false, ACH_REQ_ROOM, 29201, 0 },
    { "visit-valhalla", "The Undying Lands", "Reach the gateway to Valhalla, the furthest walk in the realms.", ACH_CAT_EXPLORATION, 50, false, ACH_REQ_ROOM, 9900, 0 },

    { "five-hundred-kills", "Blooded", "Defeat 500 mobiles.", ACH_CAT_COMBAT, 15, false, ACH_REQ_MOB_KILLS, 500, 0 },
    { "twentyfive-hundred-kills", "Butcher's Bill", "Defeat 2,500 mobiles.", ACH_CAT_COMBAT, 35, false, ACH_REQ_MOB_KILLS, 2500, 0 },
    { "five-thousand-kills", "Walking Calamity", "Defeat 5,000 mobiles.", ACH_CAT_COMBAT, 45, false, ACH_REQ_MOB_KILLS, 5000, 0 },
    { "ten-pkills", "Blood in the Water", "Earn 10 qualifying player kills.", ACH_CAT_COMBAT, 20, false, ACH_REQ_PKILLS, 10, 0 },
    { "fifty-pkills", "Feared", "Earn 50 qualifying player kills.", ACH_CAT_COMBAT, 45, false, ACH_REQ_PKILLS, 50, 0 },
    { "twofifty-pkills", "The Long War", "Earn 250 qualifying player kills.", ACH_CAT_COMBAT, 80, false, ACH_REQ_PKILLS, 250, 0 },

    { "relic-power-of-world", "The World in Your Hands", "Acquire the Power of the world from the Crypt.", ACH_CAT_COLLECTION, 50, false, ACH_REQ_OBJECT, 24225, 0 },
    { "relic-lifetaker", "Take a Life, Leave a Legacy", "Acquire the Satanic Lifetaker.", ACH_CAT_COLLECTION, 50, false, ACH_REQ_OBJECT, 29246, 0 },
    { "relic-starlight-sword", "Starlight, Star Bright", "Acquire Korzath's Starlight Sword.", ACH_CAT_COLLECTION, 50, false, ACH_REQ_OBJECT, 29250, 0 },
    { "relic-minotaur-claws", "By the Horns", "Acquire the claws of the minotaur god.", ACH_CAT_COLLECTION, 35, false, ACH_REQ_OBJECT, 5619, 0 },
    { "relic-aegis", "Under the Aegis", "Acquire the Aegis of Zeus.", ACH_CAT_COLLECTION, 35, false, ACH_REQ_OBJECT, 900, 0 },
    { "relic-thunder-bolt", "Lightning in a Bottle", "Acquire the Thunder Bolt of Zeus.", ACH_CAT_COLLECTION, 35, false, ACH_REQ_OBJECT, 901, 0 },
    { "relic-amulet-of-ra", "Eye of the Sun", "Acquire the Amulet of Ra.", ACH_CAT_COLLECTION, 35, false, ACH_REQ_OBJECT, 922, 0 },
    { "relic-sword-of-sun", "Daybreak", "Acquire the Sword of the Sun.", ACH_CAT_COLLECTION, 35, false, ACH_REQ_OBJECT, 923, 0 },
    { "relic-elfbane", "A Pointed Argument", "Acquire Elfbane from Lolth.", ACH_CAT_COLLECTION, 35, false, ACH_REQ_OBJECT, 5116, 0 },
    { "relic-lanatir-sphere", "Cold Comfort", "Acquire the Sphere of Lanatir.", ACH_CAT_COLLECTION, 30, false, ACH_REQ_OBJECT, 18008, 0 },
    { "relic-hammer-of-wrath", "Wrath Made Solid", "Acquire Lanatir's Hammer of Wrath.", ACH_CAT_COLLECTION, 35, false, ACH_REQ_OBJECT, 18010, 0 },
    { "relic-angels-heart", "Heart of an Angel", "Acquire an Angel's Heart from the Dracolich.", ACH_CAT_COLLECTION, 35, false, ACH_REQ_OBJECT, 28112, 0 },
    { "relic-british-crown", "Heavy Is the Head", "Acquire Lord British's crown.", ACH_CAT_COLLECTION, 40, false, ACH_REQ_OBJECT, 7664, 0 },
    { "relic-british-sceptre", "By Royal Decree", "Acquire Lord British's sceptre.", ACH_CAT_COLLECTION, 40, false, ACH_REQ_OBJECT, 7665, 0 },
    { "relic-british-amulet", "Royal Appointment", "Acquire Lord British's amulet.", ACH_CAT_COLLECTION, 40, false, ACH_REQ_OBJECT, 7666, 0 },
    { "relic-farslayer", "The Howl Before the Storm", "Acquire the black-hilted sword Farslayer.", ACH_CAT_COLLECTION, 40, false, ACH_REQ_OBJECT, 13404, 0 },
    { "relic-farslay-scroll", "Vengeance, Sealed", "Acquire a quest-master Scroll of Farslay.", ACH_CAT_COLLECTION, 25, false, ACH_REQ_OBJECT, 20305, 0 },
    { "five-rare-items", "Curio Collector", "Acquire five listed rare relics.", ACH_CAT_COLLECTION, 40, false, ACH_REQ_RARE_ITEMS, 5, 0 },
    { "ten-rare-items", "Relic Hunter", "Acquire ten listed rare relics.", ACH_CAT_COLLECTION, 100, false, ACH_REQ_RARE_ITEMS, 10, 0 },
    { "all-rare-items", "Museum of Chaos", "Acquire every listed rare relic.", ACH_CAT_COLLECTION, 200, false, ACH_REQ_RARE_ITEMS, 17, 0 },

    { "first-brew", "Steep Learning Curve", "Successfully brew an herbal tea.", ACH_CAT_CRAFTING, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_BREW, 0 },
    { "first-concoction", "Something Is Bubbling", "Successfully concoct a potion.", ACH_CAT_CRAFTING, 15, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_CONCOCT, 0 },
    { "first-scroll", "First Draft", "Successfully scribe a scroll.", ACH_CAT_CRAFTING, 15, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_SCRIBE, 0 },
    { "scribe-farslay-scroll", "Ink Blacker Than Night", "Successfully scribe a deadly black Farslay scroll.", ACH_CAT_CRAFTING, 50, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_FARSLAY_SCROLL, 0 },
    { "master-artisan", "Artisan of Chaos", "Complete every listed crafting feat.", ACH_CAT_CRAFTING, 75, false, ACH_REQ_CRAFTING_FEATS, 4, 0 },

    { "first-death", "Not Quite Immortal", "Suffer your first true death.", ACH_CAT_MISADVENTURE, 5, false, ACH_REQ_DEATHS, 1, 0 },
    { "ten-deaths", "Frequent Visitor", "Suffer ten true deaths.", ACH_CAT_MISADVENTURE, 15, false, ACH_REQ_DEATHS, 10, 0 },
    { "hundred-deaths", "Death Knows Your Name", "Suffer one hundred true deaths.", ACH_CAT_MISADVENTURE, 40, false, ACH_REQ_DEATHS, 100, 0 },
    { "death-by-deathtrap", "Mind the Step", "Die in a room marked as a death trap.", ACH_CAT_MISADVENTURE, 15, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DEATH_TRAP, 0 },
    { "death-by-puzzle-trap", "Read the Warning", "Die when a room-wide puzzle trap is triggered.", ACH_CAT_MISADVENTURE, 15, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_PUZZLE_TRAP, 0 },
    { "death-by-item", "Do Not Touch", "Die by activating a lethal action item.", ACH_CAT_MISADVENTURE, 15, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DEATH_ITEM, 0 },
    { "death-by-farslay", "Long-Distance Relationship", "Be killed by another player's Farslay rite.", ACH_CAT_MISADVENTURE, 25, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_FARSLAYED, 0 },
    { "death-by-farslay-backfire", "Return to Sender", "Die when your own Farslay rite turns against you.", ACH_CAT_MISADVENTURE, 30, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_FARSLAY_BACKFIRE, 0 },
    { "death-by-death-ray", "A Sickly Shade of Green", "Die to a death ray.", ACH_CAT_MISADVENTURE, 20, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DEATH_RAY, 0 },
    { "all-misadventures", "Death Becomes You", "Experience every listed unusual death.", ACH_CAT_MISADVENTURE, 75, true, ACH_REQ_MISADVENTURES, 6, 0 },

    { "first-deposit", "A Place to Keep It", "Make your first successful bank deposit.", ACH_CAT_ECONOMY, 5, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_BANK_DEPOSIT, 0 },
    { "bank-one-platinum", "Nest Egg", "Hold at least 1 platinum in the bank.", ACH_CAT_ECONOMY, 10, false, ACH_REQ_BANK_BALANCE, 1000000L, 0 },
    { "bank-hundred-platinum", "Sound Investment", "Hold at least 100 platinum in the bank.", ACH_CAT_ECONOMY, 20, false, ACH_REQ_BANK_BALANCE, 100000000L, 0 },
    { "bank-ten-thousand-platinum", "Vault of Plenty", "Hold at least 10,000 platinum in the bank.", ACH_CAT_ECONOMY, 40, false, ACH_REQ_BANK_BALANCE, 10000000000L, 0 },
    { "first-interest", "Money While You Sleep", "Receive your first bank-interest payment.", ACH_CAT_ECONOMY, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_BANK_INTEREST, 0 },
    { "week-interest", "Patient Capital", "Receive the maximum seven-day bank-interest catch-up payment.", ACH_CAT_ECONOMY, 15, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_BANK_WEEK_INTEREST, 0 },
    { "empty-account", "Every Last Copper", "Withdraw the final coin from your bank account.", ACH_CAT_ECONOMY, 5, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_BANK_EMPTIED, 0 },
    { "carry-one-platinum", "Walking Wallet", "Carry coins worth at least 1 platinum.", ACH_CAT_ECONOMY, 5, false, ACH_REQ_CARRIED_MONEY, 1000000L, 0 },
    { "carry-hundred-platinum", "Liquid Assets", "Carry coins worth at least 100 platinum.", ACH_CAT_ECONOMY, 20, false, ACH_REQ_CARRIED_MONEY, 100000000L, 0 },
    { "four-denominations", "Exact Change", "Carry platinum, gold, silver, and copper at the same time.", ACH_CAT_ECONOMY, 10, true, ACH_REQ_ALL_DENOMINATIONS, 1, 0 },
    { "slots-jackpot", "Lucky Sevens", "Hit three sevens on a casino slot machine.", ACH_CAT_ECONOMY, 20, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_SLOTS_JACKPOT, 0 },
    { "roulette-straight", "One Number, No Fear", "Win a straight-up roulette bet.", ACH_CAT_ECONOMY, 25, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_ROULETTE_STRAIGHT, 0 },
    { "poker-royal-flush", "Deal With Destiny", "Draw a royal flush at video poker.", ACH_CAT_ECONOMY, 40, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_POKER_ROYAL_FLUSH, 0 },
    { "casino-thousand-won", "Ahead of the House", "Accumulate 1,000 gold in casino winnings.", ACH_CAT_ECONOMY, 15, false, ACH_REQ_CASINO_WINNINGS, 1000, 0 },
    { "casino-hundred-thousand-won", "The House Notices", "Accumulate 100,000 gold in casino winnings.", ACH_CAT_ECONOMY, 50, false, ACH_REQ_CASINO_WINNINGS, 100000, 0 },
    { "casino-hundred-thousand-lost", "Tuition Paid", "Lose 100,000 gold at the casino.", ACH_CAT_ECONOMY, 20, true, ACH_REQ_CASINO_LOSSES, 100000, 0 },

    { "master-sword", "The Blade of Evil's Bane", "Claim the Master Sword.", ACH_CAT_HYRULE, 20, false, ACH_REQ_OBJECT, 30200, 0 },
    { "silver-arrow", "A Cold Glint of Silver", "Claim the Silver Arrow hidden in Death Mountain.", ACH_CAT_HYRULE, 20, false, ACH_REQ_OBJECT, 30218, 0 },
    { "first-triforce-shard", "A Fragment of Wisdom", "Claim your first Triforce shard.", ACH_CAT_HYRULE, 10, false, ACH_REQ_TRIFORCE_SHARDS, 1, 0 },
    { "all-triforce-shards", "Wisdom Restored", "Claim all eight Triforce shards.", ACH_CAT_HYRULE, 50, false, ACH_REQ_TRIFORCE_SHARDS, 8, 0 },
    { "all-dungeon-maps", "Never Lost", "Collect the map from every Hyrule dungeon.", ACH_CAT_HYRULE, 30, false, ACH_REQ_HYRULE_MAPS, 9, 0 },
    { "all-dungeon-compasses", "Eyes on the Prize", "Collect the compass from every Hyrule dungeon.", ACH_CAT_HYRULE, 30, false, ACH_REQ_HYRULE_COMPASSES, 9, 0 },
    { "fully-prepared", "Fully Prepared", "Collect all nine dungeon maps and all nine compasses.", ACH_CAT_HYRULE, 50, true, ACH_REQ_HYRULE_KIT, 18, 0 },
    { "complete-triforce", "Power, Wisdom, Courage", "Combine the nine Triforce pieces into The Triforce.", ACH_CAT_HYRULE, 50, true, ACH_REQ_OBJECT, 30286, 0 },

    { "hyrule-eagle", "The Eagle Falls", "Defeat Aquamentus in Level 1: The Eagle.", ACH_CAT_HYRULE, 15, false, ACH_REQ_BOSS, 30222, 30413 },
    { "hyrule-moon", "Smoke in the Moon", "Defeat Dodongo in Level 2: The Moon.", ACH_CAT_HYRULE, 15, false, ACH_REQ_BOSS, 30218, 30435 },
    { "hyrule-manji", "Cut Back the Manji", "Defeat Manhandla in Level 3: The Manji.", ACH_CAT_HYRULE, 20, false, ACH_REQ_BOSS, 30305, 30449 },
    { "hyrule-snake", "Sever the Snake", "Defeat Gleeok in Level 4: The Snake.", ACH_CAT_HYRULE, 20, false, ACH_REQ_BOSS, 30307, 30470 },
    { "hyrule-lizard", "Silence the Lizard", "Defeat Digdogger in Level 5: The Lizard.", ACH_CAT_HYRULE, 25, false, ACH_REQ_BOSS, 30309, 30489 },
    { "hyrule-dragon", "An Eye for the Dragon", "Defeat Gohma in Level 6: The Dragon.", ACH_CAT_HYRULE, 25, false, ACH_REQ_BOSS, 30223, 30519 },
    { "hyrule-demon", "The Demon Remembers", "Defeat ancient Aquamentus in Level 7: The Demon.", ACH_CAT_HYRULE, 30, false, ACH_REQ_BOSS, 30314, 30546 },
    { "hyrule-lion", "Ashes of the Lion", "Defeat ashen Gleeok in Level 8: The Lion.", ACH_CAT_HYRULE, 30, false, ACH_REQ_BOSS, 30316, 30574 },
    { "hyrule-death-mountain", "The Final Silver Light", "Defeat Ganon in Level 9: Death Mountain.", ACH_CAT_HYRULE, 50, false, ACH_REQ_BOSS, 30225, 30607 },
    { "hero-of-hyrule", "Hero of Hyrule", "Defeat the principal boss of every Hyrule dungeon.", ACH_CAT_HYRULE, 100, false, ACH_REQ_HYRULE_BOSSES, 9, 0 },
    { "zelda-rescued", "It's Dangerous to Go Alone", "Reach Princess Zelda beyond Ganon's chamber.", ACH_CAT_HYRULE, 40, false, ACH_REQ_ROOM, 30615, 0 },

    /* --- 2026-09-29: forty-two more, all of them reading state
       the game already keeps.  No new hook, no new saved field:
       the earned set is written by key, so the table can grow
       without touching anybody's player file. --- */

    { "level-35", "Into the Deep End", "Reach level 35.", ACH_CAT_CHARACTER, 10, false, ACH_REQ_LEVEL, 35, 0 },
    { "level-45", "Hardened by the Realms", "Reach level 45.", ACH_CAT_CHARACTER, 15, false, ACH_REQ_LEVEL, 45, 0 },
    { "two-remorts", "Twice Reborn", "Complete two remorts.", ACH_CAT_CHARACTER, 25, false, ACH_REQ_REMORTS, 2, 0 },
    { "three-remorts", "Third Life, New Road", "Complete three remorts.", ACH_CAT_CHARACTER, 35, false, ACH_REQ_REMORTS, 3, 0 },
    { "four-remorts", "Four Lives Deep", "Complete four remorts.", ACH_CAT_CHARACTER, 45, false, ACH_REQ_REMORTS, 4, 0 },
    { "month-played", "Resident of the Realms", "Accumulate thirty days of play time.", ACH_CAT_CHARACTER, 60, false, ACH_REQ_PLAYED, 2592000L, 0 },

    { "twentyfive-thousand-kills", "Nothing Left Standing", "Defeat 25,000 mobiles.", ACH_CAT_COMBAT, 80, false, ACH_REQ_MOB_KILLS, 25000, 0 },
    { "fifty-thousand-kills", "The Realms Remember You", "Defeat 50,000 mobiles.", ACH_CAT_COMBAT, 100, false, ACH_REQ_MOB_KILLS, 50000, 0 },
    { "fivehundred-pkills", "Legend of the Arena", "Earn 500 qualifying player kills.", ACH_CAT_COMBAT, 100, false, ACH_REQ_PKILLS, 500, 0 },

    { "thousand-quests", "Errand of a Lifetime", "Complete 1,000 quests.", ACH_CAT_QUESTS, 100, false, ACH_REQ_QUESTS, 1000, 0 },
    { "fifty-quest-streak", "Nothing Stops You", "Complete fifty quests in a row.", ACH_CAT_QUESTS, 75, false, ACH_REQ_QUEST_STREAK, 50, 0 },
    { "hundred-quest-streak", "Perfect Record", "Complete one hundred quests in a row.", ACH_CAT_QUESTS, 150, false, ACH_REQ_QUEST_STREAK, 100, 0 },

    { "twentyfive-deaths", "Hard Lessons", "Suffer twenty-five true deaths.", ACH_CAT_MISADVENTURE, 20, false, ACH_REQ_DEATHS, 25, 0 },
    { "fifty-deaths", "On a First-Name Basis", "Suffer fifty true deaths.", ACH_CAT_MISADVENTURE, 30, false, ACH_REQ_DEATHS, 50, 0 },
    { "fivehundred-deaths", "Unkillable Optimist", "Suffer five hundred true deaths.", ACH_CAT_MISADVENTURE, 75, false, ACH_REQ_DEATHS, 500, 0 },

    { "bank-thousand-platinum", "Old Money", "Hold at least 1,000 platinum in the bank.", ACH_CAT_ECONOMY, 30, false, ACH_REQ_BANK_BALANCE, 1000000000L, 0 },
    { "carry-ten-platinum", "Heavy Pockets", "Carry coins worth at least 10 platinum.", ACH_CAT_ECONOMY, 10, false, ACH_REQ_CARRIED_MONEY, 10000000L, 0 },
    { "carry-thousand-platinum", "Walking Treasury", "Carry coins worth at least 1,000 platinum.", ACH_CAT_ECONOMY, 35, false, ACH_REQ_CARRIED_MONEY, 1000000000L, 0 },
    { "casino-ten-thousand-won", "The Dealer Frowns", "Accumulate 10,000 gold in casino winnings.", ACH_CAT_ECONOMY, 25, false, ACH_REQ_CASINO_WINNINGS, 10000, 0 },
    { "casino-million-won", "Break the Bank", "Accumulate 1,000,000 gold in casino winnings.", ACH_CAT_ECONOMY, 75, false, ACH_REQ_CASINO_WINNINGS, 1000000, 0 },
    { "casino-ten-thousand-lost", "Just One More Hand", "Lose 10,000 gold at the casino.", ACH_CAT_ECONOMY, 10, true, ACH_REQ_CASINO_LOSSES, 10000, 0 },
    { "casino-million-lost", "The House Sends Its Thanks", "Lose 1,000,000 gold at the casino.", ACH_CAT_ECONOMY, 40, true, ACH_REQ_CASINO_LOSSES, 1000000, 0 },

    /* Twenty more walks.  Every vnum below is the published
       destination of a route in webadmin/directions.json, so all of
       them are reachable on foot from the Oak Tree Square, and the
       points follow how far out the route walker puts them. */
    { "visit-pet-shop", "Something Exotic", "Find the Pet Shop of Exotic Creatures.", ACH_CAT_EXPLORATION, 5, false, ACH_REQ_ROOM, 2562, 0 },
    { "visit-social-club", "Members Only", "Step into the Temple Boulevard Social Club.", ACH_CAT_EXPLORATION, 5, false, ACH_REQ_ROOM, 800, 0 },
    { "visit-froboz", "The Littered Road", "Find the littered road to the Froboz Factory.", ACH_CAT_EXPLORATION, 5, false, ACH_REQ_ROOM, 12000, 0 },
    { "visit-arena", "Blood on the Sand", "Find the dark alleyway to the Arena of ole Midgaard.", ACH_CAT_EXPLORATION, 5, false, ACH_REQ_ROOM, 2628, 0 },
    { "visit-chessboard", "Your Move", "Reach the stone door of the Chessboard.", ACH_CAT_EXPLORATION, 10, false, ACH_REQ_ROOM, 24300, 0 },
    { "visit-mob-factory", "Where Monsters Come From", "Find the entrance to the Mob Factory.", ACH_CAT_EXPLORATION, 10, false, ACH_REQ_ROOM, 9400, 0 },
    { "visit-prison", "Visiting Hours", "Reach the entrance to the Prison.", ACH_CAT_EXPLORATION, 10, false, ACH_REQ_ROOM, 20100, 0 },
    { "visit-emerald-forest", "Fog on the Trail", "Find the fog-shrouded trail into the Emerald Forest.", ACH_CAT_EXPLORATION, 10, false, ACH_REQ_ROOM, 20501, 0 },
    { "visit-ashen-wastes", "Gateway to Ash", "Reach the gateway to the Ashen Wastes.", ACH_CAT_EXPLORATION, 10, false, ACH_REQ_ROOM, 26700, 0 },
    { "visit-sands-of-sorrow", "A Long Tunnel", "Reach the long tunnel into the Sands of Sorrow.", ACH_CAT_EXPLORATION, 15, false, ACH_REQ_ROOM, 5000, 0 },
    { "visit-azeroth", "Watch Your Step", "Find the way into Azeroth.", ACH_CAT_EXPLORATION, 15, false, ACH_REQ_ROOM, 28161, 0 },
    { "visit-glitter-palace", "Before the Crystal Bridge", "Stand before the crystal bridge of the Glitter Palace.", ACH_CAT_EXPLORATION, 15, false, ACH_REQ_ROOM, 10000, 0 },
    { "visit-underdark", "The Trade Route", "Walk the trade route of the Underdark.", ACH_CAT_EXPLORATION, 15, false, ACH_REQ_ROOM, 25160, 0 },
    { "visit-new-thalos", "Outside the West Gate", "Reach the west gate of New Thalos.", ACH_CAT_EXPLORATION, 15, false, ACH_REQ_ROOM, 9669, 0 },
    { "visit-oz", "Off to See Someone", "Find the entrance to the Land of Oz.", ACH_CAT_EXPLORATION, 20, false, ACH_REQ_ROOM, 17700, 0 },
    { "visit-high-tower", "The Shadow Grove", "Reach the Shadow Grove below the High Tower of Sorcery.", ACH_CAT_EXPLORATION, 20, false, ACH_REQ_ROOM, 1300, 0 },
    { "visit-ultima", "Into Britannia", "Find the entrance to Ultima.", ACH_CAT_EXPLORATION, 25, false, ACH_REQ_ROOM, 7600, 0 },
    { "visit-korzath-fortress", "At the Fortress Gate", "Reach the entrance to Korzath's Fortress.", ACH_CAT_EXPLORATION, 30, false, ACH_REQ_ROOM, 29001, 0 },
    { "visit-ice-keep", "A Small Cold Trail", "Find the small trail to the Ice Keep.", ACH_CAT_EXPLORATION, 35, false, ACH_REQ_ROOM, 18138, 0 },
    { "visit-sea-of-serenity", "The Far Beach", "Reach the beach of the Sea of Serenity.", ACH_CAT_EXPLORATION, 40, false, ACH_REQ_ROOM, 6401, 0 },
    { "benchmark-champion", "Top of the Board", "Post the best standard benchmark anybody has run in the training yard.", ACH_CAT_COMBAT, 50, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DPS_CHAMPION, 0 },

    /* --- 2026-10-25: the expansion. Rare encounters. --- */
    { "goblin-kills-1", "Follow the Money I", "Be in at the kill of a treasure goblin.", ACH_CAT_ENCOUNTERS, 10, false, ACH_REQ_COUNTER, 1, ACH_CTR_GOBLIN_KILLS },
    { "goblin-kills-10", "Follow the Money II", "Be in at the kill of 10 treasure goblins.", ACH_CAT_ENCOUNTERS, 25, false, ACH_REQ_COUNTER, 10, ACH_CTR_GOBLIN_KILLS },
    { "goblin-kills-50", "Follow the Money III", "Be in at the kill of 50 treasure goblins.", ACH_CAT_ENCOUNTERS, 50, false, ACH_REQ_COUNTER, 50, ACH_CTR_GOBLIN_KILLS },
    { "goblin-portal-denied", "Portal Denied", "Land a blow on a treasure goblin while his escape portal opens, and collapse it.", ACH_CAT_ENCOUNTERS, 15, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_GOBLIN_PORTAL_DENIED, 0 },
    { "goblin-long-chase", "The Chase Is On", "Be in at a treasure goblin's kill after he has fled twelve times in that chase.", ACH_CAT_ENCOUNTERS, 25, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_GOBLIN_LONG_CHASE, 0 },
    { "dragon-kills-1", "Dragon Trouble I", "Be in at the kill of a Great Black Dragon.", ACH_CAT_ENCOUNTERS, 20, false, ACH_REQ_COUNTER, 1, ACH_CTR_DRAGON_KILLS },
    { "dragon-kills-5", "Dragon Trouble II", "Be in at the kill of 5 Great Black Dragons.", ACH_CAT_ENCOUNTERS, 35, false, ACH_REQ_COUNTER, 5, ACH_CTR_DRAGON_KILLS },
    { "dragon-kills-25", "Dragon Trouble III", "Be in at the kill of 25 Great Black Dragons.", ACH_CAT_ENCOUNTERS, 50, false, ACH_REQ_COUNTER, 25, ACH_CTR_DRAGON_KILLS },
    { "dragon-passenger", "You Picked the Wrong Passenger", "Be carried off by the black dragon, then help kill that same dragon.", ACH_CAT_ENCOUNTERS, 30, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DRAGON_PASSENGER, 0 },
    { "dragon-discretion", "Discretion Is an Option", "Walk away alive from the black dragon that carried you off, without striking it.", ACH_CAT_ENCOUNTERS, 15, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DRAGON_DISCRETION, 0 },
    { "vesh-visits-1", "Under the Counter I", "Buy from Vesh the Smuggler on one of his visits.", ACH_CAT_ECONOMY, 10, false, ACH_REQ_COUNTER, 1, ACH_CTR_VESH_VISITS },
    { "vesh-visits-10", "Under the Counter II", "Buy from Vesh the Smuggler on 10 different visits.", ACH_CAT_ECONOMY, 25, false, ACH_REQ_COUNTER, 10, ACH_CTR_VESH_VISITS },
    { "vesh-visits-25", "Under the Counter III", "Buy from Vesh the Smuggler on 25 different visits.", ACH_CAT_ECONOMY, 40, false, ACH_REQ_COUNTER, 25, ACH_CTR_VESH_VISITS },
    { "vesh-sold-out", "Sold Out", "Buy all five things from one of Vesh's full five-item stocks.", ACH_CAT_ECONOMY, 30, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_VESH_SOLD_OUT, 0 },
    { "vesh-items-5", "Unusual Inventory I", "Buy 5 different kinds of item from Vesh.", ACH_CAT_ECONOMY, 10, false, ACH_REQ_SET, 5, ACH_SET_VESH_ITEMS },
    { "vesh-items-15", "Unusual Inventory II", "Buy 15 different kinds of item from Vesh.", ACH_CAT_ECONOMY, 25, false, ACH_REQ_SET, 15, ACH_SET_VESH_ITEMS },
    { "vesh-items-30", "Unusual Inventory III", "Buy 30 different kinds of item from Vesh.", ACH_CAT_ECONOMY, 40, false, ACH_REQ_SET, 30, ACH_SET_VESH_ITEMS },

    /* More named bosses (verified 2026-10-25: killable, reset, mortal-reachable). */
    { "boss-moon-guardian", "By the Light of the Moon", "Defeat the Guardian of the Moon in Valhalla's moonlit courtyard.", ACH_CAT_ENCOUNTERS, 50, false, ACH_REQ_BOSS, 9915, 9982 },
    { "boss-archangel", "Beyond the Pearly Gates", "Defeat the archangel at the pearly white gates of the Crypt.", ACH_CAT_ENCOUNTERS, 50, false, ACH_REQ_BOSS, 24217, 24258 },
    { "boss-blaine", "Blaine Is a Pain", "Defeat Blaine the Mono in its control room in Lud.", ACH_CAT_ENCOUNTERS, 60, false, ACH_REQ_BOSS, 29513, 29544 },
    { "boss-roland", "The Gunslinger Falls", "Defeat Roland in his private cabin.", ACH_CAT_ENCOUNTERS, 55, false, ACH_REQ_BOSS, 29508, 29542 },
    { "boss-starfire", "The Prince Abdicates", "Defeat Crown Prince Augustus Starfire in the Glitter Palace.", ACH_CAT_ENCOUNTERS, 45, false, ACH_REQ_BOSS, 10000, -10176 },
    { "boss-headless-horseman", "Heads Will Roll", "Defeat the Headless Horseman when he rides into the Oak Tree Square.", ACH_CAT_ENCOUNTERS, 40, false, ACH_REQ_BOSS, 29910, 2401 },
    { "boss-father-winter", "The Thaw", "Defeat Father Winter when he comes to the Oak Tree Square.", ACH_CAT_ENCOUNTERS, 40, false, ACH_REQ_BOSS, 29911, 2401 },
    { "region-dark-tower", "All Things Serve the Beam", "Defeat the Borg, Korzath, the Master Guardian, Blaine and Roland.", ACH_CAT_ENCOUNTERS, 100, false, ACH_REQ_COHORT, 0, ACH_COHORT_DARK_TOWER },
    { "region-pantheon", "Twilight of the Gods", "Defeat Zeus, Odin, Ra and the Guardian of the Moon.", ACH_CAT_ENCOUNTERS, 90, false, ACH_REQ_COHORT, 0, ACH_COHORT_PANTHEON },
    { "region-heavens-gate", "Storming Heaven", "Defeat the white light, the archangel, Prince Starfire and Dagahze.", ACH_CAT_ENCOUNTERS, 90, false, ACH_REQ_COHORT, 0, ACH_COHORT_HEAVENS_GATE },

    /* Combat and teamwork. */
    { "rescue-1", "Not Today I", "Rescue a groupmate from a monster once.", ACH_CAT_COMBAT, 5, false, ACH_REQ_COUNTER, 1, ACH_CTR_RESCUES },
    { "rescue-25", "Not Today II", "Rescue a groupmate from a monster 25 times.", ACH_CAT_COMBAT, 15, false, ACH_REQ_COUNTER, 25, ACH_CTR_RESCUES },
    { "rescue-100", "Not Today III", "Rescue a groupmate from a monster 100 times.", ACH_CAT_COMBAT, 30, false, ACH_REQ_COUNTER, 100, ACH_CTR_RESCUES },
    { "disarm-1", "Empty Hands I", "Knock the weapon out of a monster's hands once.", ACH_CAT_COMBAT, 5, false, ACH_REQ_COUNTER, 1, ACH_CTR_DISARMS },
    { "disarm-25", "Empty Hands II", "Knock the weapon out of a monster's hands 25 times.", ACH_CAT_COMBAT, 15, false, ACH_REQ_COUNTER, 25, ACH_CTR_DISARMS },
    { "disarm-100", "Empty Hands III", "Knock the weapon out of a monster's hands 100 times.", ACH_CAT_COMBAT, 30, false, ACH_REQ_COUNTER, 100, ACH_CTR_DISARMS },
    { "heals-10", "Field Medic I", "Heal another player fighting a monster 10 times; overhealing does not count.", ACH_CAT_COMBAT, 10, false, ACH_REQ_COUNTER, 10, ACH_CTR_HEALS },
    { "heals-100", "Field Medic II", "Heal another player fighting a monster 100 times; overhealing does not count.", ACH_CAT_COMBAT, 20, false, ACH_REQ_COUNTER, 100, ACH_CTR_HEALS },
    { "heals-500", "Field Medic III", "Heal another player fighting a monster 500 times; overhealing does not count.", ACH_CAT_COMBAT, 40, false, ACH_REQ_COUNTER, 500, ACH_CTR_HEALS },
    { "cures-1", "Clear Eyes, Clean Blood I", "Cure another player of blindness, poison or disease once.", ACH_CAT_COMBAT, 5, false, ACH_REQ_COUNTER, 1, ACH_CTR_CURES },
    { "cures-25", "Clear Eyes, Clean Blood II", "Cure another player of blindness, poison or disease 25 times.", ACH_CAT_COMBAT, 15, false, ACH_REQ_COUNTER, 25, ACH_CTR_CURES },
    { "cures-100", "Clear Eyes, Clean Blood III", "Cure another player of blindness, poison or disease 100 times.", ACH_CAT_COMBAT, 30, false, ACH_REQ_COUNTER, 100, ACH_CTR_CURES },
    { "narrow-win-1", "By a Thread I", "Win a fight against a worthy monster on 5% of your hit points or less.", ACH_CAT_COMBAT, 10, false, ACH_REQ_COUNTER, 1, ACH_CTR_NARROW_WINS },
    { "narrow-win-10", "By a Thread II", "Win 10 fights against a worthy monster on 5% of your hit points or less.", ACH_CAT_COMBAT, 25, false, ACH_REQ_COUNTER, 10, ACH_CTR_NARROW_WINS },
    { "narrow-win-50", "By a Thread III", "Win 50 fights against a worthy monster on 5% of your hit points or less.", ACH_CAT_COMBAT, 45, false, ACH_REQ_COUNTER, 50, ACH_CTR_NARROW_WINS },
    { "servant-kills-1", "Faithful Servant I", "Have your pet or raised servant kill a monster.", ACH_CAT_COMBAT, 5, false, ACH_REQ_COUNTER, 1, ACH_CTR_SERVANT_KILLS },
    { "servant-kills-100", "Faithful Servant II", "Have your pet or raised servant kill 100 monsters.", ACH_CAT_COMBAT, 20, false, ACH_REQ_COUNTER, 100, ACH_CTR_SERVANT_KILLS },
    { "servant-kills-1000", "Faithful Servant III", "Have your pet or raised servant kill 1,000 monsters.", ACH_CAT_COMBAT, 40, false, ACH_REQ_COUNTER, 1000, ACH_CTR_SERVANT_KILLS },
    { "raise-skeleton", "Bare Bones", "Raise a skeleton to serve you.", ACH_CAT_COMBAT, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_RAISE_SKELETON, 0 },
    { "raise-wraith", "A Chill in the Air", "Raise a wraith to serve you.", ACH_CAT_COMBAT, 15, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_RAISE_WRAITH, 0 },
    { "raise-vampire", "Blood Pact", "Raise a vampire to serve you.", ACH_CAT_COMBAT, 20, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_RAISE_VAMPIRE, 0 },
    { "necromancy-all", "Night of the Living Dead", "Raise a skeleton, a wraith and a vampire.", ACH_CAT_COMBAT, 30, false, ACH_REQ_COHORT, 0, ACH_COHORT_NECROMANCY },
    { "guardian-angel", "Guardian Angel", "Earn Not Today III, Field Medic III and Clear Eyes, Clean Blood III.", ACH_CAT_COMBAT, 75, false, ACH_REQ_COHORT, 0, ACH_COHORT_GUARDIAN_ANGEL },

    /* Skills and crafting. */
    { "mastered-1", "Practice Makes Permanent I", "Bring an ability to 100%.", ACH_CAT_CHARACTER, 10, false, ACH_REQ_MASTERED_SKILLS, 1, 0 },
    { "mastered-5", "Practice Makes Permanent II", "Bring 5 different abilities to 100%.", ACH_CAT_CHARACTER, 25, false, ACH_REQ_MASTERED_SKILLS, 5, 0 },
    { "mastered-15", "Practice Makes Permanent III", "Bring 15 different abilities to 100%.", ACH_CAT_CHARACTER, 45, false, ACH_REQ_MASTERED_SKILLS, 15, 0 },
    { "weapons-1", "Weapons Scholar I", "Bring a weapon proficiency to 100%.", ACH_CAT_CHARACTER, 10, false, ACH_REQ_MASTERED_WEAPONS, 1, 0 },
    { "weapons-3", "Weapons Scholar II", "Bring 3 weapon proficiencies to 100%.", ACH_CAT_CHARACTER, 25, false, ACH_REQ_MASTERED_WEAPONS, 3, 0 },
    { "weapons-5", "Weapons Scholar III", "Bring 5 weapon proficiencies to 100%.", ACH_CAT_CHARACTER, 40, false, ACH_REQ_MASTERED_WEAPONS, 5, 0 },
    { "psi-four-disciplines", "Four Corners of the Mind", "Use a psionic power from each of the four disciplines.", ACH_CAT_CHARACTER, 30, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_PSI_ALL_DISCIPLINES, 0 },
    { "psi-all-powers", "An Open Mind", "Hold all seventeen psionic powers.", ACH_CAT_CHARACTER, 50, false, ACH_REQ_PSI_POWERS, 17, 0 },
    { "brew-25", "Kettle's On I", "Brew 25 herbal teas successfully.", ACH_CAT_CRAFTING, 15, false, ACH_REQ_COUNTER, 25, ACH_CTR_BREWS },
    { "brew-100", "Kettle's On II", "Brew 100 herbal teas successfully.", ACH_CAT_CRAFTING, 30, false, ACH_REQ_COUNTER, 100, ACH_CTR_BREWS },
    { "brew-500", "Kettle's On III", "Brew 500 herbal teas successfully.", ACH_CAT_CRAFTING, 50, false, ACH_REQ_COUNTER, 500, ACH_CTR_BREWS },
    { "concoct-25", "Cauldron Keeper I", "Concoct 25 potions successfully.", ACH_CAT_CRAFTING, 15, false, ACH_REQ_COUNTER, 25, ACH_CTR_CONCOCTIONS },
    { "concoct-100", "Cauldron Keeper II", "Concoct 100 potions successfully.", ACH_CAT_CRAFTING, 30, false, ACH_REQ_COUNTER, 100, ACH_CTR_CONCOCTIONS },
    { "concoct-500", "Cauldron Keeper III", "Concoct 500 potions successfully.", ACH_CAT_CRAFTING, 50, false, ACH_REQ_COUNTER, 500, ACH_CTR_CONCOCTIONS },
    { "scribe-25", "Scriptorium I", "Scribe 25 scrolls successfully.", ACH_CAT_CRAFTING, 15, false, ACH_REQ_COUNTER, 25, ACH_CTR_SCROLLS },
    { "scribe-100", "Scriptorium II", "Scribe 100 scrolls successfully.", ACH_CAT_CRAFTING, 30, false, ACH_REQ_COUNTER, 100, ACH_CTR_SCROLLS },
    { "scribe-500", "Scriptorium III", "Scribe 500 scrolls successfully.", ACH_CAT_CRAFTING, 50, false, ACH_REQ_COUNTER, 500, ACH_CTR_SCROLLS },
    { "recipes-5", "A Varied Recipe Book I", "Successfully craft 5 different recipes.", ACH_CAT_CRAFTING, 15, false, ACH_REQ_SET, 5, ACH_SET_RECIPES },
    { "recipes-10", "A Varied Recipe Book II", "Successfully craft 10 different recipes.", ACH_CAT_CRAFTING, 30, false, ACH_REQ_SET, 10, ACH_SET_RECIPES },
    { "recipes-20", "A Varied Recipe Book III", "Successfully craft 20 different recipes.", ACH_CAT_CRAFTING, 50, false, ACH_REQ_SET, 20, ACH_SET_RECIPES },
    { "craft-triple", "Jack of All Trades", "Earn Kettle's On I, Cauldron Keeper I and Scriptorium I.", ACH_CAT_CRAFTING, 30, false, ACH_REQ_COHORT, 0, ACH_COHORT_TRIPLE_CRAFT },
    { "wedding-cake", "A Slice of Progress", "Eat the Valhalla wedding cake and gain its train.", ACH_CAT_CHARACTER, 25, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_WEDDING_CAKE, 0 },
    { "training-food-1", "Seasoned Appetite I", "Gain a train from a training cake.", ACH_CAT_CHARACTER, 5, false, ACH_REQ_COUNTER, 1, ACH_CTR_TRAINING_FOODS },
    { "training-food-5", "Seasoned Appetite II", "Gain a train from 5 training cakes.", ACH_CAT_CHARACTER, 20, false, ACH_REQ_COUNTER, 5, ACH_CTR_TRAINING_FOODS },
    { "training-food-25", "Seasoned Appetite III", "Gain a train from 25 training cakes.", ACH_CAT_CHARACTER, 40, false, ACH_REQ_COUNTER, 25, ACH_CTR_TRAINING_FOODS },

    /* Quests and exploration. */
    { "rush-10", "Express Courier I", "Complete 10 rush contracts in time.", ACH_CAT_QUESTS, 15, false, ACH_REQ_COUNTER, 10, ACH_CTR_RUSH_QUESTS },
    { "rush-50", "Express Courier II", "Complete 50 rush contracts in time.", ACH_CAT_QUESTS, 30, false, ACH_REQ_COUNTER, 50, ACH_CTR_RUSH_QUESTS },
    { "rush-100", "Express Courier III", "Complete 100 rush contracts in time.", ACH_CAT_QUESTS, 50, false, ACH_REQ_COUNTER, 100, ACH_CTR_RUSH_QUESTS },
    { "emergency-5", "First Responder I", "Complete 5 emergency contracts in time.", ACH_CAT_QUESTS, 20, false, ACH_REQ_COUNTER, 5, ACH_CTR_EMERGENCY_QUESTS },
    { "emergency-25", "First Responder II", "Complete 25 emergency contracts in time.", ACH_CAT_QUESTS, 40, false, ACH_REQ_COUNTER, 25, ACH_CTR_EMERGENCY_QUESTS },
    { "emergency-50", "First Responder III", "Complete 50 emergency contracts in time.", ACH_CAT_QUESTS, 60, false, ACH_REQ_COUNTER, 50, ACH_CTR_EMERGENCY_QUESTS },
    { "daily-10", "Daily Grind I", "Complete 10 daily quests.", ACH_CAT_QUESTS, 10, false, ACH_REQ_COUNTER, 10, ACH_CTR_DAILY_QUESTS },
    { "daily-50", "Daily Grind II", "Complete 50 daily quests.", ACH_CAT_QUESTS, 25, false, ACH_REQ_COUNTER, 50, ACH_CTR_DAILY_QUESTS },
    { "daily-100", "Daily Grind III", "Complete 100 daily quests.", ACH_CAT_QUESTS, 45, false, ACH_REQ_COUNTER, 100, ACH_CTR_DAILY_QUESTS },
    { "quest-areas-5", "Work Takes Me Places I", "Complete quests whose target was in 5 different areas.", ACH_CAT_QUESTS, 10, false, ACH_REQ_SET, 5, ACH_SET_QUEST_AREAS },
    { "quest-areas-15", "Work Takes Me Places II", "Complete quests whose target was in 15 different areas.", ACH_CAT_QUESTS, 25, false, ACH_REQ_SET, 15, ACH_SET_QUEST_AREAS },
    { "quest-areas-30", "Work Takes Me Places III", "Complete quests whose target was in 30 different areas.", ACH_CAT_QUESTS, 45, false, ACH_REQ_SET, 30, ACH_SET_QUEST_AREAS },
    { "daily-every-kind", "A Complete Assignment", "Finish a daily of every kind: a hunt and a recovery.", ACH_CAT_QUESTS, 10, false, ACH_REQ_SET, 2, ACH_SET_DAILY_KINDS },
    { "areas-10", "Off the Beaten Path I", "Set foot in 10 different areas of the world.", ACH_CAT_EXPLORATION, 10, false, ACH_REQ_SET, 10, ACH_SET_AREAS },
    { "areas-25", "Off the Beaten Path II", "Set foot in 25 different areas of the world.", ACH_CAT_EXPLORATION, 25, false, ACH_REQ_SET, 25, ACH_SET_AREAS },
    { "areas-50", "Off the Beaten Path III", "Set foot in 50 different areas of the world.", ACH_CAT_EXPLORATION, 50, false, ACH_REQ_SET, 50, ACH_SET_AREAS },
    { "rooms-500", "Every Nook and Cranny I", "Walk into 500 different rooms of the world.", ACH_CAT_EXPLORATION, 10, false, ACH_REQ_SET, 500, ACH_SET_ROOMS },
    { "rooms-1500", "Every Nook and Cranny II", "Walk into 1,500 different rooms of the world.", ACH_CAT_EXPLORATION, 30, false, ACH_REQ_SET, 1500, ACH_SET_ROOMS },
    { "rooms-3000", "Every Nook and Cranny III", "Walk into 3,000 different rooms of the world.", ACH_CAT_EXPLORATION, 60, false, ACH_REQ_SET, 3000, ACH_SET_ROOMS },
    { "landmarks-10", "Sightseer", "Reach ten of the realm's landmarks.", ACH_CAT_EXPLORATION, 20, false, ACH_REQ_COHORT, 10, ACH_COHORT_LANDMARKS_V1 },
    { "landmarks-25", "Tour Guide", "Reach twenty-five of the realm's landmarks.", ACH_CAT_EXPLORATION, 40, false, ACH_REQ_COHORT, 25, ACH_COHORT_LANDMARKS_V1 },
    { "landmarks-all", "Seen It All", "Reach every one of the realm's landmarks.", ACH_CAT_EXPLORATION, 75, false, ACH_REQ_COHORT, 0, ACH_COHORT_LANDMARKS_V1 },

    /* Hyrule: actions and secrets. */
    { "hyrule-bomb-wall", "Blast Through", "Bomb open a cracked wall in Hyrule.", ACH_CAT_HYRULE, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_BOMB_WALL, 0 },
    { "hyrule-burn-bush", "Burning Bush", "Burn away a bush hiding a secret in Hyrule.", ACH_CAT_HYRULE, 10, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_BURN_BUSH, 0 },
    { "hyrule-push-block", "Push Comes to Shove", "Push a block aside to find the stairs beneath it.", ACH_CAT_HYRULE, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_PUSH_BLOCK, 0 },
    { "hyrule-move-armos", "Statue of Limitations", "Move a sleeping Armos statue.", ACH_CAT_HYRULE, 10, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_MOVE_ARMOS, 0 },
    { "hyrule-drain-lake", "Play It Again", "Drain the lake with the Recorder.", ACH_CAT_HYRULE, 15, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_DRAIN_LAKE, 0 },
    { "hyrule-feed-goriya", "Grumble, Grumble", "Feed the hungry Goriya.", ACH_CAT_HYRULE, 15, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_FEED_GORIYA, 0 },
    { "hyrule-money-caves-1", "Everybody's Secret I", "Claim the gold of a hidden money cave.", ACH_CAT_HYRULE, 5, false, ACH_REQ_HYRULE_SECRETS, 1, ACH_SECRETS_MONEY_CAVES },
    { "hyrule-money-caves-7", "Everybody's Secret II", "Claim the gold of seven hidden money caves.", ACH_CAT_HYRULE, 20, false, ACH_REQ_HYRULE_SECRETS, 7, ACH_SECRETS_MONEY_CAVES },
    { "hyrule-money-caves-all", "Everybody's Secret III", "Claim the gold of all fourteen hidden money caves.", ACH_CAT_HYRULE, 40, false, ACH_REQ_HYRULE_SECRETS, 14, ACH_SECRETS_MONEY_CAVES },
    { "hyrule-bomb-bag-5", "Room for More", "Buy the bigger bomb bag in Level 5.", ACH_CAT_HYRULE, 10, false, ACH_REQ_HYRULE_SECRETS, 1, ACH_SECRETS_BOMB_BAG_L5 },
    { "hyrule-bomb-bag-7", "Even More Room", "Buy the bigger bomb bag in Level 7.", ACH_CAT_HYRULE, 10, false, ACH_REQ_HYRULE_SECRETS, 1, ACH_SECRETS_BOMB_BAG_L7 },
    { "hyrule-bomb-bags", "Sixteen Bombs", "Own both bigger bomb bags.", ACH_CAT_HYRULE, 20, false, ACH_REQ_HYRULE_SECRETS, 2, ACH_SECRETS_BOMB_BAGS },
    { "hyrule-take-any-all", "Take Any One You Want", "Make your choice in all four take-any caves.", ACH_CAT_HYRULE, 25, false, ACH_REQ_HYRULE_SECRETS, 4, ACH_SECRETS_TAKE_ANY },
    { "hyrule-white-sword", "Master Using It", "Be given the White Sword for your hearts.", ACH_CAT_HYRULE, 20, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_WHITE_SWORD, 0 },
    { "hyrule-magical-sword", "Worthy of the Magical Sword", "Be given the Magical Sword for your hearts.", ACH_CAT_HYRULE, 30, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_MAGICAL_SWORD, 0 },
    { "hyrule-hint", "Pay Me and I'll Talk", "Pay an old woman for a real hint.", ACH_CAT_HYRULE, 10, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_HINT, 0 },
    { "hyrule-pols-arrow", "An Arrow Through the Ear", "Kill a Pols Voice with an arrow.", ACH_CAT_HYRULE, 15, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_POLS_ARROW, 0 },
    { "hyrule-boomerang-stun", "It Comes Back", "Stun an enemy with a boomerang and leave it standing.", ACH_CAT_HYRULE, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_BOOMERANG_STUN, 0 },
    { "hyrule-digdogger-recorder", "Cut Down to Size", "Shrink a Digdogger with the Recorder.", ACH_CAT_HYRULE, 15, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_DIGDOGGER_RECORDER, 0 },
    { "hyrule-dodongo-bomb", "Dodongo Dislikes Smoke", "Feed Dodongo a bomb.", ACH_CAT_HYRULE, 15, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_DODONGO_BOMB, 0 },
    { "hyrule-rod-fire", "Burn After Reading", "Loose the Book of Magic's fire with the Magical Rod.", ACH_CAT_HYRULE, 15, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_ROD_FIRE, 0 },
    { "hyrule-bait-calm", "Something to Chew On", "Calm Hyrule's enemies with bait.", ACH_CAT_HYRULE, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_BAIT_CALM, 0 },
    { "hyrule-tenth-bomb", "Untouchable Ten", "Earn a bomb by killing ten enemies in a row without a wound.", ACH_CAT_HYRULE, 15, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_TENTH_BOMB, 0 },
    { "hyrule-chest-1", "Eagle's Hoard", "Unlock and open the treasure chest of Level 1: The Eagle after defeating its guardian.", ACH_CAT_HYRULE, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_CHEST_FIRST + 0, 0 },
    { "hyrule-chest-2", "Under the Moon", "Unlock and open the treasure chest of Level 2: The Moon after defeating its guardian.", ACH_CAT_HYRULE, 13, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_CHEST_FIRST + 1, 0 },
    { "hyrule-chest-3", "Spoils of the Manji", "Unlock and open the treasure chest of Level 3: The Manji after defeating its guardian.", ACH_CAT_HYRULE, 16, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_CHEST_FIRST + 2, 0 },
    { "hyrule-chest-4", "The Snake's Coil", "Unlock and open the treasure chest of Level 4: The Snake after defeating its guardian.", ACH_CAT_HYRULE, 19, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_CHEST_FIRST + 3, 0 },
    { "hyrule-chest-5", "The Lizard's Cache", "Unlock and open the treasure chest of Level 5: The Lizard after defeating its guardian.", ACH_CAT_HYRULE, 22, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_CHEST_FIRST + 4, 0 },
    { "hyrule-chest-6", "The Dragon's Treasury", "Unlock and open the treasure chest of Level 6: The Dragon after defeating its guardian.", ACH_CAT_HYRULE, 25, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_CHEST_FIRST + 5, 0 },
    { "hyrule-chest-7", "The Demon's Vault", "Unlock and open the treasure chest of Level 7: The Demon after defeating its guardian.", ACH_CAT_HYRULE, 28, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_CHEST_FIRST + 6, 0 },
    { "hyrule-chest-8", "The Lion's Share", "Unlock and open the treasure chest of Level 8: The Lion after defeating its guardian.", ACH_CAT_HYRULE, 31, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_CHEST_FIRST + 7, 0 },
    { "hyrule-chest-9", "Ganon's Great Chest", "Unlock and open the treasure chest of Level 9: Death Mountain after defeating its guardian.", ACH_CAT_HYRULE, 35, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_CHEST_FIRST + 8, 0 },
    { "hyrule-band-1", "Fair Fight: The Eagle", "Defeat Aquamentus with nobody present above level 8.", ACH_CAT_HYRULE, 20, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_BAND_FIRST + 0, 0 },
    { "hyrule-band-2", "Fair Fight: The Moon", "Defeat Dodongo with nobody present above level 14.", ACH_CAT_HYRULE, 24, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_BAND_FIRST + 1, 0 },
    { "hyrule-band-3", "Fair Fight: The Manji", "Defeat Manhandla with nobody present above level 20.", ACH_CAT_HYRULE, 28, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_BAND_FIRST + 2, 0 },
    { "hyrule-band-4", "Fair Fight: The Snake", "Defeat Gleeok with nobody present above level 27.", ACH_CAT_HYRULE, 32, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_BAND_FIRST + 3, 0 },
    { "hyrule-band-5", "Fair Fight: The Lizard", "Defeat Digdogger with nobody present above level 33.", ACH_CAT_HYRULE, 36, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_BAND_FIRST + 4, 0 },
    { "hyrule-band-6", "Fair Fight: The Dragon", "Defeat Gohma with nobody present above level 40.", ACH_CAT_HYRULE, 40, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_BAND_FIRST + 5, 0 },
    { "hyrule-band-7", "Fair Fight: The Demon", "Defeat ancient Aquamentus with nobody present above level 46.", ACH_CAT_HYRULE, 44, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_BAND_FIRST + 6, 0 },
    { "hyrule-band-8", "Fair Fight: The Lion", "Defeat ashen Gleeok with nobody present above level 52.", ACH_CAT_HYRULE, 48, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_BAND_FIRST + 7, 0 },
    { "hyrule-band-9", "Fair Fight: Death Mountain", "Defeat Ganon with nobody present above level 59.", ACH_CAT_HYRULE, 60, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_HYRULE_BAND_FIRST + 8, 0 },
    { "hyrule-tools", "Tools of the Hero", "Master all ten of Hyrule's tool and puzzle feats, the secret ones included.", ACH_CAT_HYRULE, 50, false, ACH_REQ_COHORT, 0, ACH_COHORT_HYRULE_TOOLS },
    { "hyrule-all-chests", "Every Chest in Hyrule", "Open the treasure chest of all nine dungeons.", ACH_CAT_HYRULE, 60, false, ACH_REQ_COHORT, 0, ACH_COHORT_HYRULE_CHESTS },
    { "hyrule-all-bands", "By the Book", "Win every Fair Fight in Hyrule.", ACH_CAT_HYRULE, 100, false, ACH_REQ_COHORT, 0, ACH_COHORT_HYRULE_BANDS },

    /* Collection, services and world events. */
    { "relic-horseman-reaper", "Grim Harvest", "Acquire the Headless Horseman's Reaper.", ACH_CAT_COLLECTION, 25, false, ACH_REQ_OBJECT, 29920, 0 },
    { "relic-horseman-helm", "Keep Your Head", "Acquire the Horseman's cursed helm.", ACH_CAT_COLLECTION, 20, false, ACH_REQ_OBJECT, 29921, 0 },
    { "relic-frostbite", "Frostbitten", "Acquire Frostbite, Father Winter's blade.", ACH_CAT_COLLECTION, 25, false, ACH_REQ_OBJECT, 29922, 0 },
    { "relic-winter-mantle", "Wrapped for Winter", "Acquire the Winter Veil mantle.", ACH_CAT_COLLECTION, 20, false, ACH_REQ_OBJECT, 29923, 0 },
    { "relic-pumpkin-charm", "Jack of the Lantern", "Acquire a pumpkin-lantern charm.", ACH_CAT_COLLECTION, 10, false, ACH_REQ_OBJECT, 29924, 0 },
    { "relic-snowflake-pendant", "No Two Alike", "Acquire a snowflake pendant.", ACH_CAT_COLLECTION, 10, false, ACH_REQ_OBJECT, 29925, 0 },
    { "relic-clover-small", "Luck of the Draw", "Acquire the smaller lucky clover.", ACH_CAT_COLLECTION, 15, false, ACH_REQ_OBJECT, 9943, 0 },
    { "relic-clover-large", "Four Leaves", "Acquire the larger lucky clover.", ACH_CAT_COLLECTION, 20, false, ACH_REQ_OBJECT, 9944, 0 },
    { "relic-moonray", "Moonstruck", "Acquire the moonray sword.", ACH_CAT_COLLECTION, 30, false, ACH_REQ_OBJECT, 9923, 0 },
    { "relic-celestial-dagger", "Fallen Star", "Acquire the celestial dagger.", ACH_CAT_COLLECTION, 30, false, ACH_REQ_OBJECT, 9924, 0 },
    { "relic-flamberge", "A Wavy Edge", "Acquire the Flamberge from the Castellan of Valhalla.", ACH_CAT_COLLECTION, 30, false, ACH_REQ_OBJECT, 9921, 0 },
    { "crystalline-sceptre", "The Sceptre of Commanding", "Acquire the Crystalline Sceptre of Commanding.", ACH_CAT_COLLECTION, 20, false, ACH_REQ_OBJECT, 10000, 0 },
    { "crystalline-sword", "The Sword of Justice", "Acquire the Crystalline Sword of Justice.", ACH_CAT_COLLECTION, 20, false, ACH_REQ_OBJECT, 10001, 0 },
    { "crystalline-robe", "The Robe of Shielding", "Acquire the Crystalline Robe of Shielding.", ACH_CAT_COLLECTION, 20, false, ACH_REQ_OBJECT, 10003, 0 },
    { "crystalline-cloak", "The Royal Cloak", "Acquire the Crystalline Royal Cloak.", ACH_CAT_COLLECTION, 20, false, ACH_REQ_OBJECT, 10004, 0 },
    { "crystalline-crown", "The Crown of Perception", "Acquire the Crystalline Crown of Perception.", ACH_CAT_COLLECTION, 20, false, ACH_REQ_OBJECT, 10005, 0 },
    { "crystalline-set", "Crown Jewels of Glitter", "Acquire all five crystalline pieces Prince Starfire wears.", ACH_CAT_COLLECTION, 50, false, ACH_REQ_COHORT, 0, ACH_COHORT_CRYSTALLINE },
    { "stash-deposit", "Put It Somewhere Safe", "Put something in your stash.", ACH_CAT_ECONOMY, 5, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_STASH_DEPOSIT, 0 },
    { "stash-withdraw", "Right Where I Left It", "Take something back out of your stash.", ACH_CAT_ECONOMY, 5, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_STASH_WITHDRAW, 0 },
    { "stash-expand", "More Shelf Space", "Buy more room in your stash.", ACH_CAT_ECONOMY, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_STASH_EXPAND, 0 },
    { "stash-ceiling", "A Warehouse of One's Own", "Grow your stash to its full five hundred slots.", ACH_CAT_ECONOMY, 40, false, ACH_REQ_STASH_CEILING, 1, 0 },
    { "repairs-1", "Good as New I", "Pay to have a damaged item repaired.", ACH_CAT_ECONOMY, 5, false, ACH_REQ_COUNTER, 1, ACH_CTR_REPAIRS },
    { "repairs-25", "Good as New II", "Pay to have 25 damaged items repaired.", ACH_CAT_ECONOMY, 15, false, ACH_REQ_COUNTER, 25, ACH_CTR_REPAIRS },
    { "repairs-100", "Good as New III", "Pay to have 100 damaged items repaired.", ACH_CAT_ECONOMY, 30, false, ACH_REQ_COUNTER, 100, ACH_CTR_REPAIRS },
    { "wings-of-mercy", "Wings of Mercy", "Be found, badly hurt, by Herbie the angel and healed.", ACH_CAT_ENCOUNTERS, 15, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_WINGS_OF_MERCY, 0 },
    { "disaster-flood", "High Water", "Live through a flood to its end.", ACH_CAT_MISADVENTURE, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DISASTER_FIRST + 1, 0 },
    { "disaster-lightning", "Lightning Rod", "Live through a lightning storm to its end.", ACH_CAT_MISADVENTURE, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DISASTER_FIRST + 2, 0 },
    { "disaster-earthquake", "All Shook Up", "Live through an earthquake to its end.", ACH_CAT_MISADVENTURE, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DISASTER_FIRST + 3, 0 },
    { "disaster-tornado", "Not in Kansas Anymore", "Live through a tornado to its end.", ACH_CAT_MISADVENTURE, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DISASTER_FIRST + 4, 0 },
    { "disaster-sandstorm", "Sand in Everything", "Live through a sandstorm to its end.", ACH_CAT_MISADVENTURE, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DISASTER_FIRST + 5, 0 },
    { "disaster-fire", "Through the Fire", "Live through a wildfire.", ACH_CAT_MISADVENTURE, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DISASTER_FIRST + 6, 0 },
    { "disaster-tidal", "Riding the Wave", "Live through a tidal wave.", ACH_CAT_MISADVENTURE, 10, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_DISASTER_FIRST + 7, 0 },
    { "disaster-all", "Act of the Gods", "Live through every kind of disaster but the dragon.", ACH_CAT_MISADVENTURE, 50, false, ACH_REQ_COHORT, 0, ACH_COHORT_DISASTERS },
    { "rare-sightings", "Rare Sightings", "Earn Follow the Money I, Dragon Trouble I and Under the Counter I.", ACH_CAT_ENCOUNTERS, 30, false, ACH_REQ_COHORT, 0, ACH_COHORT_RARE_SIGHTINGS }
};

typedef char achievement_table_must_fit[
    (sizeof(achievement_table) / sizeof(achievement_table[0]) <= MAX_ACHIEVEMENTS) ? 1 : -1
];

static int achievement_table_count(void)
{
    return (int)(sizeof(achievement_table) / sizeof(achievement_table[0]));
}

static bool achievement_is_player(const CHAR_DATA *ch)
{
    return ch != NULL && !IS_NPC(ch) && ch->pcdata != NULL;
}

static bool achievement_can_announce(const CHAR_DATA *ch, bool announce)
{
    return announce && ch != NULL && ch->desc != NULL
        && ch->desc->connected == CON_PLAYING;
}

static int achievement_bit_count(unsigned long value)
{
    int count = 0;

    while (value != 0)
    {
        count += (int)(value & 1UL);
        value >>= 1;
    }

    return count;
}

static bool achievement_object_list_has_vnum(const OBJ_DATA *obj, int vnum)
{
    const OBJ_DATA *contained;

    for (; obj != NULL; obj = obj->next_content)
    {
        if (obj->pIndexData != NULL && obj->pIndexData->vnum == vnum)
            return true;

        contained = obj->contains;
        if (contained != NULL && achievement_object_list_has_vnum(contained, vnum))
            return true;
    }

    return false;
}

static bool achievement_has_object(const CHAR_DATA *ch, int vnum)
{
    return ch != NULL && achievement_object_list_has_vnum(ch->carrying, vnum);
}

static void achievement_note_object_vnum(CHAR_DATA *ch, int object_vnum)
{
    if (object_vnum >= 30480 && object_vnum <= 30488)
        ch->pcdata->achievement_hyrule_maps |= (1UL << (object_vnum - 30480));
    else if (object_vnum >= 30489 && object_vnum <= 30497)
        ch->pcdata->achievement_hyrule_compasses |= (1UL << (object_vnum - 30489));
    else if (object_vnum >= 30400 && object_vnum <= 30407)
        ch->pcdata->achievement_triforce_shards |= (1UL << (object_vnum - 30400));
}

static void achievement_scan_collection_objects(CHAR_DATA *ch, const OBJ_DATA *obj)
{
    for (; obj != NULL; obj = obj->next_content)
    {
        if (obj->pIndexData != NULL)
            achievement_note_object_vnum(ch, obj->pIndexData->vnum);
        if (obj->contains != NULL)
            achievement_scan_collection_objects(ch, obj->contains);
    }
}

static int achievement_index_by_key(const char *key)
{
    int index;

    if (key == NULL || key[0] == '\0')
        return -1;

    for (index = 0; index < achievement_table_count(); index++)
    {
        if (!str_cmp(key, achievement_table[index].key))
            return index;
    }

    return -1;
}

/* Whether a character holds the achievement with this key. Hyrule counts
   its NES hearts from the guardian achievements (hyrule_hearts in hyrule.c). */
bool achievement_has_key(const CHAR_DATA *ch, const char *key)
{
    int index = achievement_index_by_key(key);

    return index >= 0 && ch != NULL && ch->pcdata != NULL
        && ch->pcdata->achievement_earned[index] != 0;
}

/* ------------------------------------------------------------------
 * Counters and distinct-identity sets (2026-10-25)
 *
 * Both are saved by name, never by position, so either list may grow.
 * A counter only ever goes up and starts at zero: nothing before the
 * expansion is inferred from wealth, possessions or logs.
 * ------------------------------------------------------------------ */

static const char *const achievement_counter_names[ACH_CTR_COUNT] =
{
    "goblins", "dragons", "vesh-visits", "rescues", "disarms", "heals",
    "cures", "narrow-wins", "servant-kills", "brews", "concoctions",
    "scrolls", "training-foods", "rush-quests", "emergency-quests",
    "daily-quests", "repairs"
};

static const char *const achievement_set_names[ACH_SET_COUNT] =
{
    "vesh-items", "recipes", "quest-areas", "areas", "rooms",
    "daily-kinds", "psi-disciplines"
};

/* Bounds a corrupt or hostile file cannot push past. Rooms are the
   largest honest set: the world has under 8,000. */
static const int achievement_set_limits[ACH_SET_COUNT] =
{
    4096, 4096, 1024, 1024, 16384, 64, 16
};

/* The largest id each set can honestly hold (review, 2026-10-26: a saved
   "AchSet rooms 9223372036854775807" overflowed the loader's increment).
   Vnums are ints and an area's id is a 31-bit hash; a recipe is its
   method times 100000 plus a skill number; dailies and disciplines are
   small. Nothing outside these is ever stored, so no id plus one can
   overflow anywhere. */
static const long achievement_set_max_id[ACH_SET_COUNT] =
{
    INT_MAX,        /* vesh-items: object vnums */
    999999L,        /* recipes: method * 100000 + skill */
    INT_MAX,        /* quest-areas: achievement_area_id, 31 bits */
    INT_MAX,        /* areas */
    INT_MAX,        /* rooms: room vnums */
    63L,            /* daily-kinds */
    15L             /* psi-disciplines */
};

static int achievement_set_search(const CHAR_DATA *ch, int set, long id,
                                  bool *found)
{
    const long *values = ch->pcdata->achievement_set[set];
    int low = 0;
    int high = ch->pcdata->achievement_set_len[set] - 1;

    *found = false;
    while (low <= high)
    {
        int mid = low + (high - low) / 2;

        if (values[mid] == id)
        {
            *found = true;
            return mid;
        }
        if (values[mid] < id)
            low = mid + 1;
        else
            high = mid - 1;
    }
    return low;
}

bool achievement_set_has(const CHAR_DATA *ch, achievement_set set, long id)
{
    bool found;

    if (!achievement_is_player(ch) || (int)set < 0 || set >= ACH_SET_COUNT
        || ch->pcdata->achievement_set[set] == NULL)
        return false;
    achievement_set_search(ch, (int)set, id, &found);
    return found;
}

/* Adds id to the set; true if it was new. Never announces. */
static bool achievement_set_insert(CHAR_DATA *ch, int set, long id)
{
    PC_DATA *pc = ch->pcdata;
    bool found;
    int at;

    if (id < 0 || id > achievement_set_max_id[set]
        || pc->achievement_set_len[set] >= achievement_set_limits[set])
        return false;
    at = pc->achievement_set[set] == NULL ? 0
        : achievement_set_search(ch, set, id, &found);
    if (pc->achievement_set[set] != NULL && found)
        return false;

    if (pc->achievement_set_len[set] >= pc->achievement_set_cap[set])
    {
        int cap = pc->achievement_set_cap[set] < 16 ? 16
            : pc->achievement_set_cap[set] * 2;
        long *grown;

        if (cap > achievement_set_limits[set])
            cap = achievement_set_limits[set];
        grown = realloc(pc->achievement_set[set], (size_t)cap * sizeof(long));
        if (grown == NULL)
            return false;
        pc->achievement_set[set] = grown;
        pc->achievement_set_cap[set] = cap;
    }

    memmove(&pc->achievement_set[set][at + 1], &pc->achievement_set[set][at],
        (size_t)(pc->achievement_set_len[set] - at) * sizeof(long));
    pc->achievement_set[set][at] = id;
    pc->achievement_set_len[set]++;
    return true;
}

void achievement_free(CHAR_DATA *ch)
{
    int set;

    if (ch == NULL || ch->pcdata == NULL)
        return;
    for (set = 0; set < ACH_SET_COUNT; set++)
    {
        free(ch->pcdata->achievement_set[set]);
        ch->pcdata->achievement_set[set] = NULL;
        ch->pcdata->achievement_set_len[set] = 0;
        ch->pcdata->achievement_set_cap[set] = 0;
    }
}

/* A stable number for an area: its file name, hashed (FNV-1a, 31 bits).
   Area pointers and list order change with every boot. */
long achievement_area_id(const AREA_DATA *area)
{
    unsigned long hash = 2166136261UL;
    const char *p;

    if (area == NULL || area->file_name == NULL)
        return -1;
    for (p = area->file_name; *p != '\0'; p++)
    {
        hash ^= (unsigned char)LOWER(*p);
        hash = (hash * 16777619UL) & 0xFFFFFFFFUL;
    }
    return (long)(hash & 0x7FFFFFFFUL);
}

/* ------------------------------------------------------------------
 * Frozen cohorts
 *
 * The original metas counted "every earned achievement of this
 * requirement in this category", so adding a boss or a relic would have
 * quietly raised what "every listed world boss" means. Each meta now
 * counts an explicit list. The first five are frozen as they stood on
 * 2026-10-24 and must never change; test_achievement_expansion.py holds
 * them to that.
 * ------------------------------------------------------------------ */

static const char *const cohort_world_bosses_v1[] =
{
    "boss-tarrasque", "boss-borg", "boss-korzath", "boss-master-guardian",
    "boss-white-light", "boss-smaug", "boss-minotaur-god", "boss-zeus",
    "boss-odin", "boss-ra", "boss-dagahze", "boss-lolth",
    "boss-eilistraee", "boss-dracolich", "boss-ashen-herald",
    "boss-lord-british", "boss-lanatir", NULL
};

static const char *const cohort_rare_items_v1[] =
{
    "relic-power-of-world", "relic-lifetaker", "relic-starlight-sword",
    "relic-minotaur-claws", "relic-aegis", "relic-thunder-bolt",
    "relic-amulet-of-ra", "relic-sword-of-sun", "relic-elfbane",
    "relic-lanatir-sphere", "relic-hammer-of-wrath", "relic-angels-heart",
    "relic-british-crown", "relic-british-sceptre", "relic-british-amulet",
    "relic-farslayer", "relic-farslay-scroll", NULL
};

static const char *const cohort_crafting_v1[] =
{
    "first-brew", "first-concoction", "first-scroll",
    "scribe-farslay-scroll", NULL
};

static const char *const cohort_misadventures_v1[] =
{
    "death-by-deathtrap", "death-by-puzzle-trap", "death-by-item",
    "death-by-farslay", "death-by-farslay-backfire", "death-by-death-ray",
    NULL
};

static const char *const cohort_hyrule_bosses_v1[] =
{
    "hyrule-eagle", "hyrule-moon", "hyrule-manji", "hyrule-snake",
    "hyrule-lizard", "hyrule-dragon", "hyrule-demon", "hyrule-lion",
    "hyrule-death-mountain", NULL
};

/* The landmark walks as they stood on 2026-10-24: every visit-* key. */
static const char *const cohort_landmarks_v1[] =
{
    "visit-mud-school", "visit-casino", "visit-smurf", "visit-haon-dor",
    "visit-gangland", "visit-moria", "visit-thalos", "visit-shire",
    "visit-astral", "visit-drow-city", "visit-wyvern", "visit-solace",
    "visit-arachnos", "visit-pyramid", "visit-olympus", "visit-hell",
    "visit-abyss", "visit-battleground", "visit-valhalla",
    "visit-pet-shop", "visit-social-club", "visit-froboz", "visit-arena",
    "visit-chessboard", "visit-mob-factory", "visit-prison",
    "visit-emerald-forest", "visit-ashen-wastes", "visit-sands-of-sorrow",
    "visit-azeroth", "visit-glitter-palace", "visit-underdark",
    "visit-new-thalos", "visit-oz", "visit-high-tower", "visit-ultima",
    "visit-korzath-fortress", "visit-ice-keep", "visit-sea-of-serenity",
    NULL
};

/* The 2026-10-25 metas. Unlike the five above these are new lists, so
   they may be extended -- but a meta's list is what it means, and
   lengthening one later takes the meta away from nobody: an earned
   achievement is never revoked. */
static const char *const cohort_dark_tower[] =
{
    "boss-borg", "boss-korzath", "boss-master-guardian", "boss-blaine",
    "boss-roland", NULL
};

static const char *const cohort_pantheon[] =
{
    "boss-zeus", "boss-odin", "boss-ra", "boss-moon-guardian", NULL
};

static const char *const cohort_heavens_gate[] =
{
    "boss-white-light", "boss-archangel", "boss-starfire", "boss-dagahze",
    NULL
};

static const char *const cohort_necromancy[] =
{
    "raise-skeleton", "raise-wraith", "raise-vampire", NULL
};

static const char *const cohort_crystalline[] =
{
    "crystalline-sceptre", "crystalline-sword", "crystalline-robe",
    "crystalline-cloak", "crystalline-crown", NULL
};

static const char *const cohort_disasters[] =
{
    "disaster-flood", "disaster-lightning", "disaster-earthquake",
    "disaster-tornado", "disaster-sandstorm", "disaster-fire",
    "disaster-tidal", NULL
};

static const char *const cohort_hyrule_tools[] =
{
    "hyrule-bomb-wall", "hyrule-burn-bush", "hyrule-push-block",
    "hyrule-move-armos", "hyrule-drain-lake", "hyrule-feed-goriya",
    "hyrule-boomerang-stun", "hyrule-bait-calm",
    "hyrule-digdogger-recorder", "hyrule-rod-fire", NULL
};

static const char *const cohort_hyrule_chests[] =
{
    "hyrule-chest-1", "hyrule-chest-2", "hyrule-chest-3", "hyrule-chest-4",
    "hyrule-chest-5", "hyrule-chest-6", "hyrule-chest-7", "hyrule-chest-8",
    "hyrule-chest-9", NULL
};

static const char *const cohort_hyrule_bands[] =
{
    "hyrule-band-1", "hyrule-band-2", "hyrule-band-3", "hyrule-band-4",
    "hyrule-band-5", "hyrule-band-6", "hyrule-band-7", "hyrule-band-8",
    "hyrule-band-9", NULL
};

static const char *const cohort_triple_craft[] =
{
    "brew-25", "concoct-25", "scribe-25", NULL
};

static const char *const cohort_guardian_angel[] =
{
    "rescue-100", "heals-500", "cures-100", NULL
};

static const char *const cohort_rare_sightings[] =
{
    "goblin-kills-1", "dragon-kills-1", "vesh-visits-1", NULL
};

static const char *const *const achievement_cohorts[ACH_COHORT_COUNT] =
{
    cohort_world_bosses_v1,
    cohort_rare_items_v1,
    cohort_crafting_v1,
    cohort_misadventures_v1,
    cohort_hyrule_bosses_v1,
    cohort_landmarks_v1,
    cohort_dark_tower,
    cohort_pantheon,
    cohort_heavens_gate,
    cohort_necromancy,
    cohort_crystalline,
    cohort_disasters,
    cohort_hyrule_tools,
    cohort_hyrule_chests,
    cohort_hyrule_bands,
    cohort_triple_craft,
    cohort_guardian_angel,
    cohort_rare_sightings
};

static int achievement_index_by_key(const char *key);

static int achievement_cohort_size(int cohort)
{
    int count = 0;

    if (cohort < 0 || cohort >= ACH_COHORT_COUNT)
        return 0;
    while (achievement_cohorts[cohort][count] != NULL)
        count++;
    return count;
}

static int achievement_cohort_earned(const CHAR_DATA *ch, int cohort)
{
    int count = 0;
    int i;

    if (!achievement_is_player(ch) || cohort < 0 || cohort >= ACH_COHORT_COUNT)
        return 0;
    for (i = 0; achievement_cohorts[cohort][i] != NULL; i++)
    {
        int index = achievement_index_by_key(achievement_cohorts[cohort][i]);

        if (index >= 0 && ch->pcdata->achievement_earned[index] != 0)
            count++;
    }
    return count;
}

/* Abilities at 100%: anything that can be learned and used -- a spell
   with a real function, or a skill a command reads through its gsn --
   that some class can reach at or below the hero levels. dshield and
   baura (level 72 for all) and the dead spell_null entries never count. */
static bool achievement_ability_counts(int sn)
{
    int class_index;

    if (sn <= 0 || sn >= MAX_SKILL || skill_table[sn].name == NULL)
        return false;
    if (skill_table[sn].spell_fun == spell_null && skill_table[sn].pgsn == NULL)
        return false;
    for (class_index = 0; class_index < MAX_CLASS; class_index++)
        if (skill_table[sn].skill_level[class_index] <= LEVEL_HERO + 9)
            return true;
    return false;
}

static const sh_int *const achievement_weapon_gsns[] =
{
    &gsn_sword, &gsn_dagger, &gsn_mace, &gsn_axe, &gsn_flail, &gsn_whip,
    &gsn_polearm, &gsn_spear, NULL
};

static long achievement_mastered_count(const CHAR_DATA *ch, bool weapons)
{
    long count = 0;
    int sn;

    if (weapons)
    {
        int i;

        for (i = 0; achievement_weapon_gsns[i] != NULL; i++)
        {
            sn = *achievement_weapon_gsns[i];
            if (sn > 0 && sn < MAX_SKILL && ch->pcdata->learned[sn] >= 100)
                count++;
        }
        return count;
    }

    for (sn = 1; sn < MAX_SKILL; sn++)
    {
        if (skill_table[sn].name == NULL)
            break;
        if (ch->pcdata->learned[sn] >= 100 && achievement_ability_counts(sn))
            count++;
    }
    return count;
}

/* The four disciplines as HELP PSIONICS lists them. */
static const struct { const char *name; int discipline; } achievement_psi_powers[] =
{
    { "ego whip", 0 }, { "torment", 0 }, { "nightmare", 0 }, { "mindblast", 0 },
    { "astral walk", 1 }, { "shift", 1 }, { "project", 1 }, { "telekinesis", 1 },
    { "mindbar", 2 }, { "psionic armor", 2 }, { "psychic shield", 2 },
    { "transfusion", 2 },
    { "clairvoyance", 3 }, { "confuse", 3 }, { "mind leech", 3 },
    { "enervate", 3 }, { "pyrotechnics", 3 },
    { NULL, -1 }
};

static long achievement_psi_known(const CHAR_DATA *ch)
{
    long count = 0;
    int i;

    for (i = 0; achievement_psi_powers[i].name != NULL; i++)
    {
        int sn = skill_lookup(achievement_psi_powers[i].name);

        if (sn > 0 && ch->pcdata->learned[sn] > 0)
            count++;
    }
    return count;
}

/* A psionic power used successfully: which discipline it belongs to,
   or -1. Called from check_improve's success path. */
static int achievement_psi_discipline(int sn)
{
    int i;

    if (sn <= 0 || sn >= MAX_SKILL || skill_table[sn].name == NULL)
        return -1;
    for (i = 0; achievement_psi_powers[i].name != NULL; i++)
        if (!str_cmp(skill_table[sn].name, achievement_psi_powers[i].name))
            return achievement_psi_powers[i].discipline;
    return -1;
}

static unsigned long achievement_secret_mask(int which)
{
    switch (which)
    {
        case ACH_SECRETS_MONEY_CAVES: return 0x3FFFUL;           /* 0-13  */
        case ACH_SECRETS_BOMB_BAG_L5: return 1UL << 25;
        case ACH_SECRETS_BOMB_BAG_L7: return 1UL << 26;
        case ACH_SECRETS_BOMB_BAGS:   return (1UL << 25) | (1UL << 26);
        case ACH_SECRETS_TAKE_ANY:    return 0xFUL << 21;        /* 21-24 */
    }
    return 0;
}

static long achievement_played_seconds(const CHAR_DATA *ch)
{
    long played;

    if (ch == NULL)
        return 0;

    played = ch->played;
    if (ch->logon > 0 && current_time > ch->logon)
        played += (long)(current_time - ch->logon);

    return UMAX(0, played);
}

static long achievement_progress(const CHAR_DATA *ch, int index)
{
    const ACHIEVEMENT_DEFINITION *definition;

    if (!achievement_is_player(ch) || index < 0
        || index >= achievement_table_count())
        return 0;

    definition = &achievement_table[index];

    switch (definition->requirement)
    {
        case ACH_REQ_LEVEL:
            if (ch->pcdata->num_remorts > 0)
                return UMAX(ch->level,
                    UMIN(58, 53 + ch->pcdata->num_remorts));
            return ch->level;
        case ACH_REQ_REMORTS:
            return ch->pcdata->num_remorts;
        case ACH_REQ_PLAYED:
            return achievement_played_seconds(ch);
        case ACH_REQ_MOB_KILLS:
            return ch->pcdata->achievement_mob_kills;
        case ACH_REQ_PKILLS:
            return ch->pcdata->pkills_given;
        case ACH_REQ_QUESTS:
            return ch->pcdata->achievement_quests_completed;
        case ACH_REQ_QUEST_STREAK:
            return ch->queststreak;
        case ACH_REQ_DEATHS:
            return ch->pcdata->achievement_deaths;
        case ACH_REQ_BANK_BALANCE:
            return UMAX(0, ch->pcdata->bank);
        case ACH_REQ_CARRIED_MONEY:
            return coins_to_copper(ch);
        case ACH_REQ_ALL_DENOMINATIONS:
            return ch->new_platinum > 0 && ch->new_gold > 0
                && ch->new_silver > 0 && ch->new_copper > 0;
        case ACH_REQ_CASINO_WINNINGS:
            return UMAX(0, ch->pcdata->casino_winnings);
        case ACH_REQ_CASINO_LOSSES:
            return UMAX(0, ch->pcdata->casino_losses);
        case ACH_REQ_OBJECT:
            return achievement_has_object(ch, (int)definition->target) ? 1 : 0;
        case ACH_REQ_HYRULE_DUNGEONS:
            return achievement_bit_count(ch->pcdata->achievement_hyrule_dungeons);
        case ACH_REQ_HYRULE_MAPS:
            return achievement_bit_count(ch->pcdata->achievement_hyrule_maps);
        case ACH_REQ_HYRULE_COMPASSES:
            return achievement_bit_count(ch->pcdata->achievement_hyrule_compasses);
        case ACH_REQ_HYRULE_KIT:
            return achievement_bit_count(ch->pcdata->achievement_hyrule_maps)
                + achievement_bit_count(ch->pcdata->achievement_hyrule_compasses);
        case ACH_REQ_TRIFORCE_SHARDS:
            return achievement_bit_count(ch->pcdata->achievement_triforce_shards);
        /* The original metas count their frozen lists, not whatever
           else of that kind the table has grown since. */
        case ACH_REQ_HYRULE_BOSSES:
            return achievement_cohort_earned(ch, ACH_COHORT_HYRULE_BOSSES_V1);
        case ACH_REQ_WORLD_BOSSES:
            return achievement_cohort_earned(ch, ACH_COHORT_WORLD_BOSSES_V1);
        case ACH_REQ_RARE_ITEMS:
            return achievement_cohort_earned(ch, ACH_COHORT_RARE_ITEMS_V1);
        case ACH_REQ_CRAFTING_FEATS:
            return achievement_cohort_earned(ch, ACH_COHORT_CRAFTING_V1);
        case ACH_REQ_MISADVENTURES:
            return achievement_cohort_earned(ch, ACH_COHORT_MISADVENTURES_V1);
        case ACH_REQ_COUNTER:
            if (definition->auxiliary < 0 || definition->auxiliary >= ACH_CTR_COUNT)
                return 0;
            return ch->pcdata->achievement_counter[definition->auxiliary];
        case ACH_REQ_SET:
            if (definition->auxiliary < 0 || definition->auxiliary >= ACH_SET_COUNT)
                return 0;
            return ch->pcdata->achievement_set_len[definition->auxiliary];
        case ACH_REQ_COHORT:
            return achievement_cohort_earned(ch, definition->auxiliary);
        case ACH_REQ_MASTERED_SKILLS:
            return achievement_mastered_count(ch, false);
        case ACH_REQ_MASTERED_WEAPONS:
            return achievement_mastered_count(ch, true);
        case ACH_REQ_PSI_POWERS:
            return achievement_psi_known(ch);
        case ACH_REQ_HYRULE_SECRETS:
            return achievement_bit_count(ch->pcdata->hyrule_secrets
                & achievement_secret_mask(definition->auxiliary));
        case ACH_REQ_STASH_CEILING:
            return ch->pcdata->stash_max >= STASH_SLOTS_MAX ? 1 : 0;
        case ACH_REQ_ROOM:
        case ACH_REQ_BOSS:
        case ACH_REQ_EVENT:
            return 0;
    }

    return 0;
}

/* What an achievement asks for: its target, or for a cohort meta with
   no target, the whole list. */
static long achievement_target(int index)
{
    const ACHIEVEMENT_DEFINITION *definition = &achievement_table[index];

    if (definition->requirement == ACH_REQ_COHORT && definition->target <= 0)
        return achievement_cohort_size(definition->auxiliary);
    return definition->target;
}

static bool achievement_requirement_met(const CHAR_DATA *ch, int index)
{
    const ACHIEVEMENT_DEFINITION *definition;

    if (!achievement_is_player(ch) || index < 0
        || index >= achievement_table_count())
        return false;

    definition = &achievement_table[index];
    if (definition->requirement == ACH_REQ_OBJECT)
        return achievement_progress(ch, index) > 0;
    if (definition->requirement == ACH_REQ_COHORT)
        return achievement_progress(ch, index)
            >= achievement_target(index);
    if (definition->requirement == ACH_REQ_ROOM
        || definition->requirement == ACH_REQ_BOSS
        || definition->requirement == ACH_REQ_EVENT)
        return false;

    return achievement_progress(ch, index) >= definition->target;
}

int achievement_earned_count(const CHAR_DATA *ch)
{
    int count = 0;
    int index;

    if (!achievement_is_player(ch))
        return 0;

    for (index = 0; index < achievement_table_count(); index++)
    {
        if (ch->pcdata->achievement_earned[index] != 0)
            count++;
    }

    return count;
}

int achievement_catalog_count(void)
{
    return achievement_table_count();
}

int achievement_points(const CHAR_DATA *ch)
{
    int points = 0;
    int index;

    if (!achievement_is_player(ch))
        return 0;

    for (index = 0; index < achievement_table_count(); index++)
    {
        if (ch->pcdata->achievement_earned[index] != 0)
            points += achievement_table[index].points;
    }

    return points;
}

static int achievement_possible_points(void)
{
    int points = 0;
    int index;

    for (index = 0; index < achievement_table_count(); index++)
        points += achievement_table[index].points;

    return points;
}

/*
 * Is this row one of the 2026-10-25 expansion's, which staff never earn?
 * The table is append-only and the expansion began at goblin-kills-1, so
 * every row from there on is new. The hooks each asked ACH_STAFF, but the
 * login catch-up and the state checks did not, and a builder trusted to
 * 60 left with Weapons Scholar and Practice Makes Permanent (review,
 * 2026-10-26). Rows before it keep their old rule.
 */
static bool achievement_is_expansion(int index)
{
    static int first = -2;

    if (first == -2)
        first = achievement_index_by_key("goblin-kills-1");
    return first >= 0 && index >= first;
}

static bool achievement_unlock(CHAR_DATA *ch, int index, bool announce)
{
    char buf[MAX_STRING_LENGTH];
    const ACHIEVEMENT_DEFINITION *definition;
    time_t earned;

    if (!achievement_is_player(ch) || index < 0
        || index >= achievement_table_count()
        || ch->pcdata->achievement_earned[index] != 0)
        return false;

    /* Every award passes here, so the staff rule is kept here, by trust:
       what a character already earned is never taken away. */
    if (ACH_STAFF(ch) && achievement_is_expansion(index))
        return false;

    earned = current_time > 0 ? current_time : time(NULL);
    if (earned <= 0)
        earned = 1;
    ch->pcdata->achievement_earned[index] = earned;
    definition = &achievement_table[index];

    if (achievement_can_announce(ch, announce))
    {
        send_to_char("\n\r{0D=============================================================={00\n\r", ch);
        send_to_char("{0D                    ACHIEVEMENT EARNED{00\n\r", ch);
        snprintf(buf, sizeof(buf), "{0F%s{00  {0D+%d points{00\n\r",
            definition->title, definition->points);
        send_to_char(buf, ch);
        snprintf(buf, sizeof(buf), "%s\n\r", definition->description);
        send_to_char(buf, ch);
        snprintf(buf, sizeof(buf), "Total achievement points: {0D%d{00\n\r",
            achievement_points(ch));
        send_to_char(buf, ch);
        send_to_char("{0D=============================================================={00\n\r\n\r", ch);

        snprintf(buf, sizeof(buf),
            "{0D$n has earned the achievement '{0F%s{0D'!{00",
            definition->title);
        act(buf, ch, NULL, NULL, TO_ROOM);

        /* Inside the announce branch on purpose: a login can hand out
           a dozen catch-up awards silently, and a dozen toasts at the
           door is not a celebration. */
        gmcp_send_achievement( ch, definition->title,
                               definition->description, definition->points,
                               achievement_points(ch) );
    }

    return true;
}

static bool achievement_check_requirement_type(CHAR_DATA *ch,
                                                ACHIEVEMENT_REQUIREMENT requirement,
                                                bool announce)
{
    bool changed = false;
    int index;

    if (!achievement_is_player(ch))
        return false;

    for (index = 0; index < achievement_table_count(); index++)
    {
        if (achievement_table[index].requirement != requirement
            || ch->pcdata->achievement_earned[index] != 0)
            continue;
        if (achievement_requirement_met(ch, index)
            && achievement_unlock(ch, index, announce))
            changed = true;
    }

    return changed;
}

void achievement_check_economy(CHAR_DATA *ch, bool announce)
{
    int index;

    if (!achievement_is_player(ch))
        return;

    for (index = 0; index < achievement_table_count(); index++)
    {
        if (achievement_table[index].category != ACH_CAT_ECONOMY
            || ch->pcdata->achievement_earned[index] != 0)
            continue;
        if (achievement_requirement_met(ch, index))
            achievement_unlock(ch, index, announce);
    }
}

void achievement_check_state(CHAR_DATA *ch, bool announce)
{
    bool changed;
    int index;

    if (!achievement_is_player(ch))
        return;

    if (ch->pcdata->achievement_mob_kills < 0)
        ch->pcdata->achievement_mob_kills = 0;
    if (ch->pcdata->achievement_quests_completed < 0)
        ch->pcdata->achievement_quests_completed = 0;
    if (ch->pcdata->achievement_deaths < 0)
        ch->pcdata->achievement_deaths = 0;
    ch->pcdata->achievement_hyrule_dungeons &= HYRULE_DUNGEON_MASK;
    ch->pcdata->achievement_hyrule_maps &= HYRULE_DUNGEON_MASK;
    ch->pcdata->achievement_hyrule_compasses &= HYRULE_DUNGEON_MASK;
    ch->pcdata->achievement_triforce_shards &= HYRULE_SHARD_MASK;
    achievement_scan_collection_objects(ch, ch->carrying);

    do
    {
        changed = false;
        for (index = 0; index < achievement_table_count(); index++)
        {
            const ACHIEVEMENT_DEFINITION *definition = &achievement_table[index];

            if (ch->pcdata->achievement_earned[index] != 0)
                continue;
            if (definition->requirement == ACH_REQ_ROOM
                || definition->requirement == ACH_REQ_BOSS
                || definition->requirement == ACH_REQ_EVENT)
                continue;
            if (achievement_requirement_met(ch, index))
            {
                if (achievement_unlock(ch, index, announce))
                    changed = true;
            }
        }
    }
    while (changed);
}

/* Who a kill is credited to: the killer, or a pet's or servant's
   player master. */
static CHAR_DATA *achievement_credit(CHAR_DATA *killer)
{
    if (killer != NULL && IS_NPC(killer) && killer->master != NULL
        && !IS_NPC(killer->master))
        return killer->master;
    return killer;
}

/* A monster worth counting for the new combat feats: not somebody's
   charmed thing, not raised undead, and nothing an immortal killed. */
static bool achievement_worthy_victim(const CHAR_DATA *victim)
{
    return victim != NULL && IS_NPC(victim)
        && !IS_AFFECTED(victim, AFF_CHARM)
        && !IS_SET(victim->act, ACT_PET)
        && (victim->pIndexData == NULL
            || victim->pIndexData->vnum != MOB_VNUM_ANIMATE);
}

static bool achievement_boss_room_matches(const ACHIEVEMENT_DEFINITION *definition,
                                          const ROOM_INDEX_DATA *room)
{
    const ROOM_INDEX_DATA *home;

    if (room == NULL)
        return false;
    if (definition->auxiliary >= 0)
        return definition->auxiliary == room->vnum;
    home = get_room_index(-definition->auxiliary);
    return home != NULL && home->area != NULL && home->area == room->area;
}

/* Everyone a party award reaches: the credited player and their group
   standing in the room, mortals only -- an immortal's kill is not play. */
static bool achievement_party_member(CHAR_DATA *member, CHAR_DATA *credit)
{
    return achievement_is_player(member) && !ACH_STAFF(member)
        && (member == credit || is_same_group(member, credit));
}

void achievement_party_count(CHAR_DATA *killer, ROOM_INDEX_DATA *room,
                             achievement_counter counter)
{
    CHAR_DATA *credit = achievement_credit(killer);
    CHAR_DATA *member;

    if (!achievement_is_player(credit) || ACH_STAFF(credit) || room == NULL)
        return;
    for (member = room->people; member != NULL; member = member->next_in_room)
        if (achievement_party_member(member, credit))
            achievement_count(member, counter, 1);
}

void achievement_party_event(CHAR_DATA *killer, ROOM_INDEX_DATA *room,
                             achievement_event_type event)
{
    CHAR_DATA *credit = achievement_credit(killer);
    CHAR_DATA *member;

    if (!achievement_is_player(credit) || ACH_STAFF(credit) || room == NULL)
        return;
    for (member = room->people; member != NULL; member = member->next_in_room)
        if (achievement_party_member(member, credit))
            achievement_record_event(member, event, true);
}

/* Hyrule's level bands, from scripts/build_hyrule_manifest.py's
   LEVEL_BANDS (and wiki/hyrule-area.md): the top of each dungeon's band. */
static const int hyrule_band_ceiling[9] = { 8, 14, 20, 27, 33, 40, 46, 52, 59 };

/* A Fair Fight: every player in the guardian's room at the kill is at or
   below the dungeon's band, and no immortal is there. Anyone above it --
   in the group or merely standing by -- spoils it for everybody. */
static void achievement_hyrule_fair_fight(CHAR_DATA *credit, CHAR_DATA *victim,
                                          int dungeon)
{
    CHAR_DATA *member;

    if (dungeon < 0 || dungeon >= 9 || victim->in_room == NULL)
        return;
    for (member = victim->in_room->people; member != NULL;
         member = member->next_in_room)
    {
        if (IS_NPC(member))
        {
            /* Hired help counts at its own level: a level 50 pet in a
               Level 1 fight is overleveled assistance. */
            if ((IS_AFFECTED(member, AFF_CHARM) || IS_SET(member->act, ACT_PET))
                && member->level > hyrule_band_ceiling[dungeon])
                return;
            continue;
        }
        if (ACH_STAFF(member) || member->level > hyrule_band_ceiling[dungeon])
            return;
    }
    achievement_party_event(credit, victim->in_room,
        (achievement_event_type)(ACHIEVEMENT_EVENT_HYRULE_BAND_FIRST + dungeon));
}

void achievement_record_kill(CHAR_DATA *killer, CHAR_DATA *victim)
{
    CHAR_DATA *credit;
    CHAR_DATA *member;
    int mob_vnum;
    int boss_index = -1;
    int index;

    if (victim == NULL || !IS_NPC(victim) || victim->pIndexData == NULL)
        return;

    credit = achievement_credit(killer);

    if (!achievement_is_player(credit))
        return;

    if (credit->pcdata->achievement_mob_kills < LONG_MAX)
        credit->pcdata->achievement_mob_kills++;
    achievement_check_requirement_type(credit, ACH_REQ_MOB_KILLS, true);

    /* Faithful Servant: the blow was a pet's or a raised servant's. */
    if (killer != credit && killer != NULL && IS_NPC(killer)
        && (IS_AFFECTED(killer, AFF_CHARM) || IS_SET(killer->act, ACT_PET))
        && !ACH_STAFF(credit) && achievement_worthy_victim(victim))
        achievement_count(credit, ACH_CTR_SERVANT_KILLS, 1);

    /* By a Thread: standing there, on 5% or less, against something of
       about your own level or better. */
    if (!ACH_STAFF(credit) && achievement_worthy_victim(victim)
        && credit->in_room != NULL && credit->in_room == victim->in_room
        && credit->max_hit > 0 && credit->hit > 0
        && (long)credit->hit * 20L <= (long)credit->max_hit
        && victim->level >= credit->level - 5)
        achievement_count(credit, ACH_CTR_NARROW_WINS, 1);

    mob_vnum = victim->pIndexData->vnum;

    if (victim->in_room == NULL)
        return;

    for (index = 0; index < achievement_table_count(); index++)
    {
        const ACHIEVEMENT_DEFINITION *definition = &achievement_table[index];

        if (definition->requirement == ACH_REQ_BOSS
            && definition->target == mob_vnum
            && achievement_boss_room_matches(definition, victim->in_room))
        {
            boss_index = index;
            break;
        }
    }

    if (boss_index < 0)
        return;

    for (member = victim->in_room->people; member != NULL;
         member = member->next_in_room)
    {
        if (!achievement_is_player(member)
            || (member != credit && !is_same_group(member, credit)))
            continue;

        if (achievement_unlock(member, boss_index, true))
            achievement_check_state(member, true);
    }

    for (index = 0; cohort_hyrule_bosses_v1[index] != NULL; index++)
        if (!str_cmp(cohort_hyrule_bosses_v1[index],
                achievement_table[boss_index].key))
            achievement_hyrule_fair_fight(credit, victim, index);
}

/* Opening a dungeon's treasure chest counts only for someone who beat its
   guardian: picking the treasure out of a chest somebody else opened
   proves nothing. dungeon is 0 for Level 1 through 8 for Death Mountain. */
void achievement_record_hyrule_chest(CHAR_DATA *ch, int dungeon)
{
    if (!achievement_is_player(ch) || ACH_STAFF(ch) || dungeon < 0 || dungeon >= 9
        || !achievement_has_key(ch, cohort_hyrule_bosses_v1[dungeon]))
        return;
    achievement_record_event(ch,
        (achievement_event_type)(ACHIEVEMENT_EVENT_HYRULE_CHEST_FIRST + dungeon), true);
}

/* Healing another player in a fight with a monster, counted only for
   what the heal really restored. */
void achievement_record_heal(CHAR_DATA *ch, CHAR_DATA *victim, int before)
{
    if (!achievement_is_player(ch) || !achievement_is_player(victim)
        || ch == victim || ACH_STAFF(ch)
        || victim->hit <= before || victim->fighting == NULL
        || !IS_NPC(victim->fighting) || is_training_dummy(victim->fighting))
        return;
    achievement_count(ch, ACH_CTR_HEALS, 1);
}

/* Blindness, poison or disease lifted from another player. */
void achievement_record_cure(CHAR_DATA *ch, CHAR_DATA *victim)
{
    if (!achievement_is_player(ch) || !achievement_is_player(victim)
        || ch == victim || ACH_STAFF(ch))
        return;
    achievement_count(ch, ACH_CTR_CURES, 1);
}

/* A psionic power used successfully (check_improve's success path, which
   the training yard never reaches). */
void achievement_record_psionic(CHAR_DATA *ch, int sn)
{
    int discipline = achievement_psi_discipline(sn);

    if (!achievement_is_player(ch) || discipline < 0)
        return;
    if (achievement_set_insert(ch, ACH_SET_PSI_DISCIPLINES, discipline)
        && ch->pcdata->achievement_set_len[ACH_SET_PSI_DISCIPLINES] >= 4)
        achievement_record_event(ch, ACHIEVEMENT_EVENT_PSI_ALL_DISCIPLINES, true);
}

void achievement_record_quest(CHAR_DATA *ch)
{
    if (!achievement_is_player(ch))
        return;

    if (ch->pcdata->achievement_quests_completed < LONG_MAX)
        ch->pcdata->achievement_quests_completed++;
    achievement_check_requirement_type(ch, ACH_REQ_QUESTS, true);
    achievement_check_requirement_type(ch, ACH_REQ_QUEST_STREAK, true);
}

void achievement_record_death(CHAR_DATA *ch)
{
    if (!achievement_is_player(ch))
        return;

    if (ch->pcdata->achievement_deaths < LONG_MAX)
        ch->pcdata->achievement_deaths++;
    achievement_check_requirement_type(ch, ACH_REQ_DEATHS, true);
}

void achievement_record_event(CHAR_DATA *ch, achievement_event_type event,
                              bool announce)
{
    bool changed = false;
    int index;

    if (!achievement_is_player(ch))
        return;

    for (index = 0; index < achievement_table_count(); index++)
    {
        if (achievement_table[index].requirement != ACH_REQ_EVENT
            || achievement_table[index].target != (long)event)
            continue;

        if (achievement_unlock(ch, index, announce))
            changed = true;
    }

    if (changed)
        achievement_check_state(ch, announce);
}

/* Adds to a counter and awards whatever it now reaches. */
void achievement_count(CHAR_DATA *ch, achievement_counter counter, long amount)
{
    if (!achievement_is_player(ch) || (int)counter < 0 || counter >= ACH_CTR_COUNT
        || amount <= 0)
        return;
    if (ch->pcdata->achievement_counter[counter] > LONG_MAX - amount)
        ch->pcdata->achievement_counter[counter] = LONG_MAX;
    else
        ch->pcdata->achievement_counter[counter] += amount;
    if (achievement_check_requirement_type(ch, ACH_REQ_COUNTER, true))
        achievement_check_state(ch, true);
}

/* Records a distinct identity; true if it was new. */
bool achievement_note(CHAR_DATA *ch, achievement_set set, long id)
{
    if (!achievement_is_player(ch) || (int)set < 0 || set >= ACH_SET_COUNT)
        return false;
    if (!achievement_set_insert(ch, (int)set, id))
        return false;
    if (achievement_check_requirement_type(ch, ACH_REQ_SET, true))
        achievement_check_state(ch, true);
    return true;
}

/* Rooms and areas count toward exploration only where anybody can go:
   the shipped world, not built areas, staff rooms, the unreachable
   Quest Zone and Temple Despair, Limbo or a jail cell. */
static bool achievement_room_is_public(const ROOM_INDEX_DATA *room)
{
    const char *file;

    if (room == NULL || room->area == NULL)
        return false;
    file = room->area->file_name;
    if (file == NULL || !str_prefix("built/", file)
        || !str_cmp(file, "limbo.are") || !str_cmp(file, BUILDER_AREA_FILE))
        return false;
    if ((room->vnum >= 20301 && room->vnum <= 20313)
        || (room->vnum >= 26000 && room->vnum <= 26006))
        return false;
    if (IS_SET(room->room_flags, ROOM_IMP_ONLY)
        || IS_SET(room->room_flags, ROOM_GODS_ONLY)
        || IS_SET(room->room_flags, ROOM_JAIL))
        return false;
    return true;
}

void achievement_record_room_visit(CHAR_DATA *ch, ROOM_INDEX_DATA *room)
{
    bool changed = false;

    if (!achievement_is_player(ch) || ACH_STAFF(ch)
        || !achievement_room_is_public(room))
        return;
    if (achievement_set_insert(ch, ACH_SET_ROOMS, room->vnum))
        changed = true;
    if (achievement_set_insert(ch, ACH_SET_AREAS,
            achievement_area_id(room->area)))
        changed = true;
    if (changed && achievement_check_requirement_type(ch, ACH_REQ_SET, true))
        achievement_check_state(ch, true);
}

void achievement_record_room(CHAR_DATA *ch, int room_vnum, bool announce)
{
    int index;
    int dungeon;
    bool changed = false;
    unsigned long previous_dungeons;

    if (!achievement_is_player(ch))
        return;

    previous_dungeons = ch->pcdata->achievement_hyrule_dungeons;
    for (dungeon = 0; dungeon < 9; dungeon++)
    {
        if (hyrule_dungeon_entrances[dungeon] == room_vnum)
            ch->pcdata->achievement_hyrule_dungeons |= (1UL << dungeon);
    }

    for (index = 0; index < achievement_table_count(); index++)
    {
        const ACHIEVEMENT_DEFINITION *definition = &achievement_table[index];

        if (definition->requirement == ACH_REQ_ROOM
            && definition->target == room_vnum)
        {
            if (achievement_unlock(ch, index, announce))
                changed = true;
        }
    }

    if (previous_dungeons != ch->pcdata->achievement_hyrule_dungeons)
        changed = true;
    if (changed)
        achievement_check_state(ch, announce);
}

void achievement_record_object(CHAR_DATA *ch, int object_vnum, bool announce)
{
    bool relevant = false;
    int index;

    if (!achievement_is_player(ch))
        return;

    if ((object_vnum >= 30480 && object_vnum <= 30497)
        || (object_vnum >= 30400 && object_vnum <= 30407))
        relevant = true;
    for (index = 0; index < achievement_table_count(); index++)
    {
        if (achievement_table[index].requirement == ACH_REQ_OBJECT
            && achievement_table[index].target == object_vnum)
        {
            relevant = true;
            break;
        }
    }

    if (!relevant)
        return;

    achievement_note_object_vnum(ch, object_vnum);

    if (announce)
        achievement_check_state(ch, true);
}

void achievement_write_char(CHAR_DATA *ch, FILE *fp)
{
    int index;

    if (!achievement_is_player(ch) || fp == NULL)
        return;

    fprintf(fp, "AchKills %ld\n", ch->pcdata->achievement_mob_kills);
    fprintf(fp, "AchQuests %ld\n", ch->pcdata->achievement_quests_completed);
    fprintf(fp, "AchDeaths %ld\n", ch->pcdata->achievement_deaths);
    fprintf(fp, "AchExplore %lu\n", ch->pcdata->achievement_hyrule_dungeons);
    fprintf(fp, "AchMaps %lu\n", ch->pcdata->achievement_hyrule_maps);
    fprintf(fp, "AchCompass %lu\n", ch->pcdata->achievement_hyrule_compasses);
    fprintf(fp, "AchTriforce %lu\n", ch->pcdata->achievement_triforce_shards);

    for (index = 0; index < achievement_table_count(); index++)
    {
        if (ch->pcdata->achievement_earned[index] != 0)
        {
            fprintf(fp, "Achv %s %ld\n", achievement_table[index].key,
                (long)ch->pcdata->achievement_earned[index]);
        }
    }

    for (index = 0; index < ACH_CTR_COUNT; index++)
    {
        if (ch->pcdata->achievement_counter[index] > 0)
            fprintf(fp, "AchCount %s %ld\n", achievement_counter_names[index],
                ch->pcdata->achievement_counter[index]);
    }

    /* Sets go out sorted, a run of consecutive ids as "a-b": the rooms
       an explorer has walked are mostly runs, and this keeps the line
       short. */
    for (index = 0; index < ACH_SET_COUNT; index++)
    {
        const long *values = ch->pcdata->achievement_set[index];
        int len = ch->pcdata->achievement_set_len[index];
        int i = 0;

        if (values == NULL || len <= 0)
            continue;
        fprintf(fp, "AchSet %s", achievement_set_names[index]);
        while (i < len)
        {
            int run = i;

            /* values[run] < LONG_MAX: the next id is only asked for when
               it exists, so a corrupt set in memory cannot overflow. */
            while (run + 1 < len && values[run] < LONG_MAX
                   && values[run + 1] == values[run] + 1)
                run++;
            if (run > i)
                fprintf(fp, " %ld-%ld", values[i], values[run]);
            else
                fprintf(fp, " %ld", values[i]);
            i = run + 1;
        }
        fprintf(fp, " ~\n");
    }

    if (ch->pcdata->achievement_marks_spent > 0 || ch->pcdata->achievement_perks != 0)
        fprintf(fp, "AchSpent %ld %ld\n", ch->pcdata->achievement_marks_spent,
            ch->pcdata->achievement_perks);
}

void achievement_load_count(CHAR_DATA *ch, const char *name, long value)
{
    int index;

    if (!achievement_is_player(ch) || name == NULL || value <= 0)
        return;
    for (index = 0; index < ACH_CTR_COUNT; index++)
    {
        if (!str_cmp(name, achievement_counter_names[index]))
        {
            if (value > ch->pcdata->achievement_counter[index])
                ch->pcdata->achievement_counter[index] = value;
            return;
        }
    }
}

/* One number of an AchSet token: digits only -- no sign, no space, no
   letter -- and no larger than the set's largest id. *end is where the
   digits stopped. */
static bool achievement_set_number(const char *text, int set,
                                   const char **end, long *out)
{
    char *stop;
    long value;

    if (!isdigit((unsigned char)text[0]))
        return false;
    errno = 0;
    value = strtol(text, &stop, 10);
    if (errno == ERANGE || value < 0
        || (set >= 0 && value > achievement_set_max_id[set]))
        return false;
    *end = stop;
    *out = value;
    return true;
}

/* Parses "<id>" or "<first>-<last>"; false for anything else, which the
   loader skips rather than guessing at. */
bool achievement_set_token(const char *word, int set, long *first, long *last)
{
    const char *end;

    if (!achievement_set_number(word, set, &end, first))
        return false;
    *last = *first;
    if (*end == '\0')
        return true;
    if (*end != '-' || !achievement_set_number(end + 1, set, &end, last)
        || *end != '\0' || *last < *first)
        return false;
    return true;
}

/* Reads "AchSet <name> <id|a-b> ... ~". An unknown name is read through
   and dropped, so a file from a newer build still loads. Every token is
   read to the "~" -- stopping early would leave the rest for fread_char
   to misread as keys -- but only the first ACH_SET_LOAD_TOKENS are
   looked at, and no more than twice the set's limit of ids are tried in
   all, so a hostile file cannot make the load do unbounded work. */
#define ACH_SET_LOAD_TOKENS 20000
void achievement_load_set(CHAR_DATA *ch, FILE *fp)
{
    char name[MAX_INPUT_LENGTH];
    int set = -1;
    int index;
    int tokens = 0;
    long budget = 0;

    toc_strlcpy(name, fread_word(fp), sizeof(name));
    for (index = 0; index < ACH_SET_COUNT; index++)
        if (!str_cmp(name, achievement_set_names[index]))
            set = index;
    if (set >= 0)
        budget = 2L * achievement_set_limits[set];

    for (;;)
    {
        char *word = fread_word(fp);
        long first;
        long last;
        long id;

        if (word == NULL || word[0] == '\0' || !str_cmp(word, "~")
            || !str_cmp(word, "End"))
            break;
        if (++tokens > ACH_SET_LOAD_TOKENS || set < 0 || budget <= 0
            || !achievement_is_player(ch)
            || !achievement_set_token(word, set, &first, &last))
            continue;
        /* Never steps past last, so last may be the set's largest id. */
        for (id = first; budget > 0; id++)
        {
            budget--;
            if (!achievement_set_insert(ch, set, id)
                && ch->pcdata->achievement_set_len[set] >= achievement_set_limits[set])
            {
                budget = 0;
                break;
            }
            if (id == last)
                break;
        }
    }
}

void achievement_load_spent(CHAR_DATA *ch, FILE *fp)
{
    long spent = fread_long(fp);
    long perks = fread_long(fp);

    if (!achievement_is_player(ch))
        return;
    ch->pcdata->achievement_marks_spent = UMAX(0, spent);
    ch->pcdata->achievement_perks = perks;
}

void achievement_load_earned(CHAR_DATA *ch, const char *key, time_t earned)
{
    int index;

    if (!achievement_is_player(ch))
        return;

    index = achievement_index_by_key(key);
    if (index < 0)
        return;

    if (earned <= 0)
        earned = 1;
    if (ch->pcdata->achievement_earned[index] == 0
        || earned < ch->pcdata->achievement_earned[index])
        ch->pcdata->achievement_earned[index] = earned;
}

static void achievement_format_date(time_t earned, char *buf, size_t size)
{
    struct tm *local;

    if (buf == NULL || size == 0)
        return;

    if (earned <= 1)
    {
        toc_strlcpy(buf, "legacy", size);
        return;
    }

    local = localtime(&earned);
    if (local == NULL || strftime(buf, size, "%Y-%m-%d", local) == 0)
        toc_strlcpy(buf, "unknown", size);
}

static void achievement_append_entry(DString *output, const CHAR_DATA *ch,
                                     int index)
{
    char line[MAX_STRING_LENGTH];
    char date[32];
    const ACHIEVEMENT_DEFINITION *definition = &achievement_table[index];
    long current;
    long target;
    int percent;
    bool earned;

    earned = ch->pcdata->achievement_earned[index] != 0;
    if (!earned && definition->hidden)
    {
        snprintf(line, sizeof(line),
            "{08[???] Hidden achievement{00  {0D%d points{00\n\r"
            "      Its requirements are secret.\n\r", definition->points);
        dstring_append_cstr(output, line);
        return;
    }

    if (earned)
    {
        achievement_format_date(ch->pcdata->achievement_earned[index], date,
            sizeof(date));
        snprintf(line, sizeof(line),
            "{06[Earned %s]{00 {0F%s{00  {0D%d points{00\n\r"
            "      %s\n\r",
            date, definition->title, definition->points,
            definition->description);
        dstring_append_cstr(output, line);
        return;
    }

    current = achievement_progress(ch, index);
    target = achievement_target(index);
    if (definition->requirement == ACH_REQ_OBJECT
        || definition->requirement == ACH_REQ_ROOM
        || definition->requirement == ACH_REQ_BOSS
        || definition->requirement == ACH_REQ_EVENT)
        target = 1;
    else if (definition->requirement == ACH_REQ_PLAYED)
    {
        current /= 3600L;
        target /= 3600L;
    }
    if (current < 0)
        current = 0;
    if (current > target)
        current = target;
    percent = target > 0 ? (int)((current * 100L) / target) : 0;

    snprintf(line, sizeof(line),
        "{07[%3d%%]{00 {0F%s{00  {0D%d points{00\n\r"
        "      %s {08(%ld/%ld){00\n\r",
        percent, definition->title, definition->points,
        definition->description, current, target);
    dstring_append_cstr(output, line);
}

static int achievement_category_lookup(const char *argument)
{
    int category;
    int match = -1;

    if (argument == NULL || argument[0] == '\0')
        return -1;

    for (category = 0; category < ACH_CAT_COUNT; category++)
    {
        if (!str_cmp(argument, achievement_category_names[category]))
            return category;
    }

    for (category = 0; category < ACH_CAT_COUNT; category++)
    {
        if (!str_prefix(argument, achievement_category_names[category]))
        {
            if (match >= 0)
                return -1;
            match = category;
        }
    }

    return match;
}

static void achievement_show_summary(CHAR_DATA *ch)
{
    char output[MAX_STRING_LENGTH * 4];
    char line[MAX_STRING_LENGTH];
    bool selected[MAX_ACHIEVEMENTS] = { false };
    int category_counts[ACH_CAT_COUNT] = { 0 };
    int category_earned[ACH_CAT_COUNT] = { 0 };
    int category_points[ACH_CAT_COUNT] = { 0 };
    int category;
    int index;
    int shown;

    output[0] = '\0';
    snprintf(line, sizeof(line),
        "{0D========================= ACHIEVEMENTS ========================={00\n\r"
        "Points: {0F%d{00 / %d     Earned: {0F%d{00 / %d\n\r"
        "Marks to spend: {0F%ld{00 (see {0FREDEEM{00)\n\r\n\r",
        achievement_points(ch), achievement_possible_points(),
        achievement_earned_count(ch), achievement_table_count(),
        achievement_marks(ch));
    toc_strlcat(output, line, sizeof(output));

    for (index = 0; index < achievement_table_count(); index++)
    {
        category = (int)achievement_table[index].category;
        category_counts[category]++;
        if (ch->pcdata->achievement_earned[index] != 0)
        {
            category_earned[category]++;
            category_points[category] += achievement_table[index].points;
        }
    }

    toc_strlcat(output, "{0DProgress by category (earned/total, points):{00\n\r",
        sizeof(output));
    for (category = 0; category < ACH_CAT_COUNT; category += 2)
    {
        int right = category + 1;

        if (right < ACH_CAT_COUNT)
        {
            snprintf(line, sizeof(line),
                "  {0F%-12s{00 %3d/%-3d %4d pts   "
                "{0F%-12s{00 %3d/%-3d %4d pts\n\r",
                achievement_category_names[category],
                category_earned[category], category_counts[category],
                category_points[category], achievement_category_names[right],
                category_earned[right], category_counts[right],
                category_points[right]);
        }
        else
        {
            snprintf(line, sizeof(line),
                "  {0F%-12s{00 %3d/%-3d %4d pts\n\r",
                achievement_category_names[category],
                category_earned[category], category_counts[category],
                category_points[category]);
        }
        toc_strlcat(output, line, sizeof(output));
    }

    toc_strlcat(output, "\n\r{0DRecently earned:{00\n\r", sizeof(output));
    for (shown = 0; shown < 5; shown++)
    {
        int newest = -1;
        time_t newest_time = 0;

        for (index = 0; index < achievement_table_count(); index++)
        {
            time_t earned = ch->pcdata->achievement_earned[index];

            if (!selected[index] && earned != 0
                && (newest < 0 || earned > newest_time))
            {
                newest = index;
                newest_time = earned;
            }
        }

        if (newest < 0)
            break;
        selected[newest] = true;
        {
            char date[32];
            char recent[MAX_STRING_LENGTH];

            achievement_format_date(newest_time, date, sizeof(date));
            snprintf(recent, sizeof(recent), "  %s  %s ({0D%d{00 points)\n\r",
                date, achievement_table[newest].title,
                achievement_table[newest].points);
            toc_strlcat(output, recent, sizeof(output));
        }
    }
    if (shown == 0)
        toc_strlcat(output, "  None yet. Your first one is waiting.\n\r", sizeof(output));

    toc_strlcat(output,
        "\n\rTry {0FACHIEVEMENTS <category>{00, {0FEARNED{00, "
        "{0FINCOMPLETE{00,\n\r"
        "    {0FALL{00, or {0FACHIEVEMENTS <search>{00.  A long list comes in parts:\n\r"
        "    {0FACHIEVEMENTS ALL 2{00 is the second.\n\r",
        sizeof(output));
    page_to_char(output, ch);
}

/* A list view is cut into parts of at most this many bytes of raw text
   (colour tokens unconverted), each ending at an entry. Colour can make
   the text sent half as long again, and the pager holds at most 32,000
   bytes in one block, so a part stays well inside it however it is
   drawn. ACHIEVEMENTS ALL 2 shows the second part. */
#define ACHIEVEMENT_PART_BYTES 12000

static bool achievement_matches_search(const CHAR_DATA *ch, int index,
                                       const char *search)
{
    const ACHIEVEMENT_DEFINITION *definition = &achievement_table[index];

    if (search == NULL || search[0] == '\0')
        return true;
    /* A hidden achievement not yet earned is found by nothing: a search
       for its words would otherwise prove that it exists. */
    if (definition->hidden && ch->pcdata->achievement_earned[index] == 0)
        return false;
    return !str_infix(search, definition->key)
        || !str_infix(search, definition->title)
        || !str_infix(search, definition->description);
}

static void achievement_show_list(CHAR_DATA *ch, int category, int mode,
                                  const char *search, int part, const char *again)
{
    DString page;
    DString entry;
    char line[MAX_STRING_LENGTH];
    int index;
    int shown = 0;
    int parts = 1;
    size_t used = 0;

    if (part < 1)
        part = 1;
    dstring_init(&page);
    dstring_init(&entry);

    if (category >= 0)
        snprintf(line, sizeof(line), "{0D==================== %s ACHIEVEMENTS ===================={00\n\r",
            achievement_category_names[category]);
    else
        snprintf(line, sizeof(line), "{0D========================= ACHIEVEMENTS ========================={00\n\r");
    dstring_append_cstr(&page, line);

    for (index = 0; index < achievement_table_count(); index++)
    {
        const ACHIEVEMENT_DEFINITION *definition = &achievement_table[index];
        bool earned = ch->pcdata->achievement_earned[index] != 0;

        if (category >= 0 && (int)definition->category != category)
            continue;
        if (mode == 1 && !earned)
            continue;
        if (mode == 2 && earned)
            continue;
        if (!achievement_matches_search(ch, index, search))
            continue;

        dstring_clear(&entry);
        achievement_append_entry(&entry, ch, index);
        if (used > 0 && used + dstring_length(&entry) > ACHIEVEMENT_PART_BYTES)
        {
            parts++;
            used = 0;
        }
        used += dstring_length(&entry);
        shown++;
        if (parts == part)
            dstring_append_cstr(&page, dstring_cstr(&entry));
    }

    if (shown == 0)
        dstring_append_cstr(&page, "No achievements match that view.\n\r");
    else if (part > parts)
    {
        snprintf(line, sizeof(line), "That view has only %d part%s.\n\r",
            parts, parts == 1 ? "" : "s");
        dstring_append_cstr(&page, line);
    }
    else
    {
        snprintf(line, sizeof(line), "\n\rShowing %d achievement%s",
            shown, shown == 1 ? "" : "s");
        dstring_append_cstr(&page, line);
        if (parts > 1)
        {
            snprintf(line, sizeof(line), ", part %d of %d.", part, parts);
            dstring_append_cstr(&page, line);
            if (part < parts)
            {
                snprintf(line, sizeof(line),
                    "  {0FACHIEVEMENTS %s %d{00 shows the next part.", again, part + 1);
                dstring_append_cstr(&page, line);
            }
        }
        else
            dstring_append_cstr(&page, ".");
        dstring_append_cstr(&page, "\n\r");
    }

    dstring_append_cstr(&page,
        "Use {0FACHIEVEMENTS{00 for your summary and category totals.\n\r");
    page_to_char(dstring_cstr(&page), ch);
    dstring_free(&entry);
    dstring_free(&page);
}

/* Splits a trailing part number off a view: "all 2", "combat 3",
   "dragon trouble 2". A lone number is a search, not a part. */
static int achievement_take_part(char *text)
{
    char *last;
    int part;

    if (text == NULL)
        return 1;
    last = strrchr(text, ' ');
    if (last == NULL || !is_number(last + 1))
        return 1;
    part = atoi(last + 1);
    if (part < 1 || part > 99)
        return 1;
    *last = '\0';
    return part;
}

void do_achievements(CHAR_DATA *ch, char *argument)
{
    char view[MAX_INPUT_LENGTH];
    char first[MAX_INPUT_LENGTH];
    int category;
    int part;

    if (!achievement_is_player(ch))
    {
        send_to_char("Mobiles do not earn achievements.\n\r", ch);
        return;
    }

    achievement_check_state(ch, true);
    while (isspace((unsigned char)*argument))
        argument++;
    toc_strlcpy(view, argument, sizeof(view));
    part = achievement_take_part(view);
    one_argument(view, first);

    if (first[0] == '\0')
    {
        achievement_show_summary(ch);
        return;
    }

    if (strchr(view, ' ') == NULL)
    {
        category = achievement_category_lookup(first);
        if (category >= 0)
        {
            achievement_show_list(ch, category, 0, NULL, part,
                achievement_category_names[category]);
            return;
        }
        if (!str_cmp(first, "earned"))
        {
            achievement_show_list(ch, -1, 1, NULL, part, "EARNED");
            return;
        }
        if (!str_cmp(first, "incomplete"))
        {
            achievement_show_list(ch, -1, 2, NULL, part, "INCOMPLETE");
            return;
        }
        if (!str_cmp(first, "all"))
        {
            achievement_show_list(ch, -1, 0, NULL, part, "ALL");
            return;
        }
    }

    achievement_show_list(ch, -1, 0, view, part, view);
}


/* ------------------------------------------------------------------
 * REDEEM: achievement marks (owner, 2026-10-25)
 *
 * Points are a score and never go down. Every point earned is also a
 * mark, and marks are spent here on things that change how a character
 * looks or saves time -- never stats, coin, trains or gear power. Marks
 * held are points earned less marks spent, so nothing about them needs
 * migrating: a character who earned points before REDEEM existed has
 * those marks to spend. The spend is saved as AchSpent beside the earned
 * set and travels with it through a PRESTORE, so a rollback takes back
 * a purchase and its marks together.
 * ------------------------------------------------------------------ */

#define REDEEM_COST_RECALL   10
#define REDEEM_COST_TROPHY   25
#define REDEEM_COST_STASH    40
#define REDEEM_COST_RESTRING 100
#define OBJ_VNUM_ACHIEVEMENT_TROPHY 95

long achievement_marks(const CHAR_DATA *ch)
{
    long marks;

    if (!achievement_is_player(ch))
        return 0;
    marks = (long)achievement_points(ch) - ch->pcdata->achievement_marks_spent;
    return marks > 0 ? marks : 0;
}

static bool redeem_afford(CHAR_DATA *ch, long cost)
{
    char buf[MAX_STRING_LENGTH];

    if (achievement_marks(ch) >= cost)
        return true;
    snprintf(buf, sizeof(buf), "That costs %ld marks, and you have %ld.\n\r",
        cost, achievement_marks(ch));
    send_to_char(buf, ch);
    return false;
}

static void redeem_spend(CHAR_DATA *ch, long cost, const char *what)
{
    char buf[MAX_STRING_LENGTH];

    ch->pcdata->achievement_marks_spent += cost;
    snprintf(buf, sizeof(buf), "%s  You spend %ld marks; %ld remain.\n\r",
        what, cost, achievement_marks(ch));
    send_to_char(buf, ch);
    snprintf(buf, sizeof(buf), "Redeem: %s spent %ld marks (%s).", ch->name,
        cost, what);
    log_string(buf);
    save_char_obj(ch);
}

/* Finds an earned achievement by key, or by a word of its title. */
static int redeem_find_earned(const CHAR_DATA *ch, const char *words)
{
    int index;

    for (index = 0; index < achievement_table_count(); index++)
        if (ch->pcdata->achievement_earned[index] != 0
            && !str_cmp(words, achievement_table[index].key))
            return index;
    for (index = 0; index < achievement_table_count(); index++)
        if (ch->pcdata->achievement_earned[index] != 0
            && !str_infix(words, achievement_table[index].title))
            return index;
    return -1;
}

/* A new name for a weapon: plain printable ASCII, no colour, and still
   answering to one of its keywords so GET and WIELD find it. */
static bool redeem_name_ok(CHAR_DATA *ch, const OBJ_DATA *obj, const char *name)
{
    char word[MAX_INPUT_LENGTH];
    const char *rest = obj->name;
    size_t len = strlen(name);
    const char *p;

    if (len < 4 || len > 45)
    {
        send_to_char("A new name runs from 4 to 45 characters.\n\r", ch);
        return false;
    }
    for (p = name; *p != '\0'; p++)
    {
        if (*p < 32 || *p > 126 || *p == '{' || *p == '~')
        {
            send_to_char("Plain letters, digits and punctuation only -- no colour.\n\r", ch);
            return false;
        }
    }
    while (rest != NULL && *rest != '\0')
    {
        rest = one_argument((char *)rest, word);
        if (word[0] != '\0' && strlen(word) >= 3 && !str_infix(word, name))
            return true;
    }
    send_to_char("The new name has to keep one of its old keywords, so you can still\n\r"
                 "name it to GET and WIELD it.\n\r", ch);
    return false;
}

void do_redeem(CHAR_DATA *ch, char *argument)
{
    char arg[MAX_INPUT_LENGTH];
    char buf[MAX_STRING_LENGTH];

    if (!achievement_is_player(ch))
    {
        send_to_char("Only players hold achievement marks.\n\r", ch);
        return;
    }

    argument = one_argument(argument, arg);

    if (arg[0] == '\0')
    {
        snprintf(buf, sizeof(buf),
            "{0D======================= ACHIEVEMENT MARKS ======================={00\n\r"
            "Every achievement point you earn is also a mark to spend here.\n\r"
            "Spending marks never lowers your points.  You hold {0F%ld{00 marks.\n\r\n\r"
            "  {0FREDEEM RECALL{00                      %3d  move your recall point again now\n\r"
            "  {0FREDEEM TROPHY <achievement>{00        %3d  a keepsake trophy of one you earned\n\r"
            "  {0FREDEEM STASH{00                       %3d  %d more stash slots (to %d)\n\r"
            "  {0FREDEEM RESTRING <weapon> <name>{00    %3d  give a weapon you carry a new name\n\r",
            achievement_marks(ch), REDEEM_COST_RECALL, REDEEM_COST_TROPHY,
            REDEEM_COST_STASH, STASH_SLOTS_STEP, STASH_SLOTS_MAX,
            REDEEM_COST_RESTRING);
        send_to_char(buf, ch);
        return;
    }

    if (!str_prefix(arg, "recall"))
    {
        if (ch->pcdata->recall_set_at == 0
            || current_time - ch->pcdata->recall_set_at >= RECALL_MOVE_COOLDOWN)
        {
            send_to_char("You may move your recall point already; RECALL SET does it.\n\r", ch);
            return;
        }
        if (!redeem_afford(ch, REDEEM_COST_RECALL))
            return;
        ch->pcdata->recall_set_at = 0;
        redeem_spend(ch, REDEEM_COST_RECALL,
            "The gods will hear a new recall point from you at once.");
        return;
    }

    if (!str_prefix(arg, "stash"))
    {
        if (ch->pcdata->stash_max >= STASH_SLOTS_MAX)
        {
            send_to_char("Your stash is as large as a stash grows.\n\r", ch);
            return;
        }
        if (!redeem_afford(ch, REDEEM_COST_STASH))
            return;
        ch->pcdata->stash_max = UMIN(ch->pcdata->stash_max + STASH_SLOTS_STEP,
            STASH_SLOTS_MAX);
        snprintf(buf, sizeof(buf), "Your stash now holds %d.", ch->pcdata->stash_max);
        redeem_spend(ch, REDEEM_COST_STASH, buf);
        achievement_record_event(ch, ACHIEVEMENT_EVENT_STASH_EXPAND, true);
        achievement_check_state(ch, true);
        return;
    }

    if (!str_prefix(arg, "trophy"))
    {
        OBJ_INDEX_DATA *proto;
        OBJ_DATA *trophy;
        int index;

        while (isspace((unsigned char)*argument))
            argument++;
        if (argument[0] == '\0')
        {
            send_to_char("REDEEM TROPHY <achievement>: one you have earned, by key or title.\n\r", ch);
            return;
        }
        if ((index = redeem_find_earned(ch, argument)) < 0)
        {
            send_to_char("You have earned no achievement by that name.\n\r", ch);
            return;
        }
        if ((proto = get_obj_index(OBJ_VNUM_ACHIEVEMENT_TROPHY)) == NULL)
        {
            send_to_char("The trophy maker is away just now.\n\r", ch);
            return;
        }
        if (ch->carry_number + 1 > can_carry_n(ch))
        {
            send_to_char("Your hands are full.\n\r", ch);
            return;
        }
        if (!redeem_afford(ch, REDEEM_COST_TROPHY))
            return;
        trophy = create_object(proto, 0);
        snprintf(buf, sizeof(buf), "a trophy for '%s'", achievement_table[index].title);
        free_string(trophy->short_descr);
        trophy->short_descr = str_dup(buf);
        snprintf(buf, sizeof(buf),
            "A trophy for '%s', earned by %s, stands here.",
            achievement_table[index].title, ch->name);
        free_string(trophy->description);
        trophy->description = str_dup(buf);
        obj_to_char(trophy, ch);
        snprintf(buf, sizeof(buf), "You are handed a trophy for '%s'.",
            achievement_table[index].title);
        redeem_spend(ch, REDEEM_COST_TROPHY, buf);
        return;
    }

    if (!str_prefix(arg, "restring"))
    {
        char target[MAX_INPUT_LENGTH];
        OBJ_DATA *obj;

        argument = one_argument(argument, target);
        while (isspace((unsigned char)*argument))
            argument++;
        if (target[0] == '\0' || argument[0] == '\0')
        {
            send_to_char("REDEEM RESTRING <weapon> <new name>, for a weapon you carry.\n\r", ch);
            return;
        }
        if ((obj = get_obj_carry(ch, target)) == NULL)
        {
            send_to_char("You carry nothing by that name.\n\r", ch);
            return;
        }
        if (obj->item_type != ITEM_WEAPON)
        {
            send_to_char("Only a weapon can be given a new name.\n\r", ch);
            return;
        }
        if (!redeem_name_ok(ch, obj, argument))
            return;
        if (!redeem_afford(ch, REDEEM_COST_RESTRING))
            return;
        snprintf(buf, sizeof(buf), "%s is now called '%s'.", obj->short_descr, argument);
        free_string(obj->short_descr);
        obj->short_descr = str_dup(argument);
        redeem_spend(ch, REDEEM_COST_RESTRING, buf);
        return;
    }

    send_to_char("REDEEM alone lists what marks buy.\n\r", ch);
}

#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

#include "merc.h"
#include "interp.h"

#define HYRULE_DUNGEON_MASK 0x1FFUL
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
    ACH_REQ_MISADVENTURES
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
    "Hyrule"
};

static const int hyrule_dungeon_entrances[9] =
{
    30401, 30418, 30437, 30456, 30476,
    30501, 30527, 30562, 30590
};

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
    { "quest-last-minute", "Under the Wire", "Complete an automatic quest in its final minute.", ACH_CAT_QUESTS, 20, true, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_QUEST_LAST_MINUTE, 0 },
    { "quest-gamble-win", "Double or Nothing", "Win an automatic-quest double-or-nothing gamble.", ACH_CAT_QUESTS, 15, false, ACH_REQ_EVENT, ACHIEVEMENT_EVENT_QUEST_GAMBLE_WIN, 0 },
    { "quest-keepsake", "A Token of Esteem", "Acquire a questmaster's keepsake trophy.", ACH_CAT_QUESTS, 20, false, ACH_REQ_OBJECT, 20306, 0 },

    { "hyrule-arrival", "A Hero Awakens", "Be teleported into the First Quest entrance of Hyrule.", ACH_CAT_EXPLORATION, 10, false, ACH_REQ_ROOM, 30200, 0 },
    { "hyrule-cartographer", "Across Hyrule", "Discover the entrance to all nine Hyrule dungeons.", ACH_CAT_EXPLORATION, 30, false, ACH_REQ_HYRULE_DUNGEONS, 9, 0 },

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

    { "master-sword", "The Blade of Evil's Bane", "Claim the Master Sword.", ACH_CAT_HYRULE, 20, false, ACH_REQ_OBJECT, 30200, 0 },
    { "silver-arrow", "A Cold Glint of Silver", "Claim the Silver Arrow hidden in Death Mountain.", ACH_CAT_HYRULE, 20, false, ACH_REQ_OBJECT, 30218, 0 },
    { "first-triforce-shard", "A Fragment of Wisdom", "Claim your first Triforce shard.", ACH_CAT_HYRULE, 10, false, ACH_REQ_TRIFORCE_SHARDS, 1, 0 },
    { "all-triforce-shards", "Wisdom Restored", "Claim all eight Triforce shards.", ACH_CAT_HYRULE, 50, false, ACH_REQ_TRIFORCE_SHARDS, 8, 0 },
    { "all-dungeon-maps", "Never Lost", "Collect the map from every Hyrule dungeon.", ACH_CAT_HYRULE, 30, false, ACH_REQ_HYRULE_MAPS, 9, 0 },
    { "all-dungeon-compasses", "Eyes on the Prize", "Collect the compass from every Hyrule dungeon.", ACH_CAT_HYRULE, 30, false, ACH_REQ_HYRULE_COMPASSES, 9, 0 },
    { "fully-prepared", "Fully Prepared", "Collect all nine dungeon maps and all nine compasses.", ACH_CAT_HYRULE, 50, true, ACH_REQ_HYRULE_KIT, 18, 0 },
    { "complete-triforce", "Power, Wisdom, Courage", "Claim the complete Triforce beyond Ganon's chamber.", ACH_CAT_HYRULE, 50, true, ACH_REQ_OBJECT, 30286, 0 },

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
    { "zelda-rescued", "It's Dangerous to Go Alone", "Reach Princess Zelda beyond Ganon's chamber.", ACH_CAT_HYRULE, 40, false, ACH_REQ_ROOM, 30615, 0 }
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

static int achievement_earned_requirement_count(
    const CHAR_DATA *ch, ACHIEVEMENT_CATEGORY category,
    ACHIEVEMENT_REQUIREMENT requirement)
{
    int count = 0;
    int index;

    if (!achievement_is_player(ch))
        return 0;

    for (index = 0; index < achievement_table_count(); index++)
    {
        if (achievement_table[index].requirement == requirement
            && achievement_table[index].category == category
            && ch->pcdata->achievement_earned[index] != 0)
            count++;
    }

    return count;
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
        case ACH_REQ_HYRULE_BOSSES:
            return achievement_earned_requirement_count(ch, ACH_CAT_HYRULE,
                ACH_REQ_BOSS);
        case ACH_REQ_WORLD_BOSSES:
            return achievement_earned_requirement_count(ch, ACH_CAT_ENCOUNTERS,
                ACH_REQ_BOSS);
        case ACH_REQ_RARE_ITEMS:
            return achievement_earned_requirement_count(ch, ACH_CAT_COLLECTION,
                ACH_REQ_OBJECT);
        case ACH_REQ_CRAFTING_FEATS:
            return achievement_earned_requirement_count(ch, ACH_CAT_CRAFTING,
                ACH_REQ_EVENT);
        case ACH_REQ_MISADVENTURES:
            return achievement_earned_requirement_count(ch,
                ACH_CAT_MISADVENTURE, ACH_REQ_EVENT);
        case ACH_REQ_ROOM:
        case ACH_REQ_BOSS:
        case ACH_REQ_EVENT:
            return 0;
    }

    return 0;
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

static bool achievement_unlock(CHAR_DATA *ch, int index, bool announce)
{
    char buf[MAX_STRING_LENGTH];
    const ACHIEVEMENT_DEFINITION *definition;
    time_t earned;

    if (!achievement_is_player(ch) || index < 0
        || index >= achievement_table_count()
        || ch->pcdata->achievement_earned[index] != 0)
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

void achievement_record_kill(CHAR_DATA *killer, CHAR_DATA *victim)
{
    CHAR_DATA *credit;
    CHAR_DATA *member;
    int mob_vnum;
    int room_vnum;
    int boss_index = -1;
    int index;

    if (victim == NULL || !IS_NPC(victim) || victim->pIndexData == NULL)
        return;

    credit = killer;
    if (credit != NULL && IS_NPC(credit) && credit->master != NULL
        && !IS_NPC(credit->master))
        credit = credit->master;

    if (!achievement_is_player(credit))
        return;

    if (credit->pcdata->achievement_mob_kills < LONG_MAX)
        credit->pcdata->achievement_mob_kills++;
    achievement_check_requirement_type(credit, ACH_REQ_MOB_KILLS, true);

    mob_vnum = victim->pIndexData->vnum;
    room_vnum = victim->in_room != NULL ? victim->in_room->vnum : 0;

    if (victim->in_room == NULL)
        return;

    for (index = 0; index < achievement_table_count(); index++)
    {
        const ACHIEVEMENT_DEFINITION *definition = &achievement_table[index];

        if (definition->requirement == ACH_REQ_BOSS
            && definition->target == mob_vnum
            && definition->auxiliary == room_vnum)
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

static void achievement_append_entry(char *output, size_t size,
                                     const CHAR_DATA *ch, int index)
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
        toc_strlcat(output, line, size);
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
        toc_strlcat(output, line, size);
        return;
    }

    current = achievement_progress(ch, index);
    target = definition->target;
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
    toc_strlcat(output, line, size);
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
    int category;
    int index;
    int shown;

    output[0] = '\0';
    snprintf(line, sizeof(line),
        "{0D========================= ACHIEVEMENTS ========================={00\n\r"
        "Points: {0F%d{00 / %d     Earned: {0F%d{00 / %d\n\r\n\r",
        achievement_points(ch), achievement_possible_points(),
        achievement_earned_count(ch), achievement_table_count());
    toc_strlcat(output, line, sizeof(output));

    for (category = 0; category < ACH_CAT_COUNT; category++)
    {
        int category_count = 0;
        int category_earned = 0;
        int category_points = 0;

        for (index = 0; index < achievement_table_count(); index++)
        {
            if ((int)achievement_table[index].category != category)
                continue;
            category_count++;
            if (ch->pcdata->achievement_earned[index] != 0)
            {
                category_earned++;
                category_points += achievement_table[index].points;
            }
        }

        snprintf(line, sizeof(line), "  {0F%-12s{00 %2d/%-2d earned  %4d points\n\r",
            achievement_category_names[category], category_earned,
            category_count, category_points);
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
        "\n\rUse {0FACHIEVEMENTS <category>{00, {0FEARNED{00, "
        "{0FINCOMPLETE{00, or {0FALL{00.\n\r"
        "Categories: Character, Combat, Encounters, Quests, Exploration,\n\r"
        "Collection, Crafting, Misadventure, Hyrule.\n\r",
        sizeof(output));
    page_to_char(output, ch);
}

static void achievement_show_list(CHAR_DATA *ch, int category, int mode,
                                  const char *search)
{
    char output[MAX_STRING_LENGTH * 8];
    char line[MAX_STRING_LENGTH];
    int index;
    int shown = 0;

    output[0] = '\0';
    if (category >= 0)
        snprintf(line, sizeof(line), "{0D==================== %s ACHIEVEMENTS ===================={00\n\r",
            achievement_category_names[category]);
    else
        snprintf(line, sizeof(line), "{0D========================= ACHIEVEMENTS ========================={00\n\r");
    toc_strlcat(output, line, sizeof(output));

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
        if (search != NULL && search[0] != '\0'
            && str_infix(search, definition->key)
            && str_infix(search, definition->title)
            && str_infix(search, definition->description))
            continue;

        achievement_append_entry(output, sizeof(output), ch, index);
        shown++;
    }

    if (shown == 0)
        toc_strlcat(output, "No achievements match that view.\n\r", sizeof(output));
    else
    {
        snprintf(line, sizeof(line), "\n\rShowing %d achievement%s.\n\r",
            shown, shown == 1 ? "" : "s");
        toc_strlcat(output, line, sizeof(output));
    }

    toc_strlcat(output,
        "Use {0FACHIEVEMENTS{00 for your summary and category totals.\n\r",
        sizeof(output));
    page_to_char(output, ch);
}

void do_achievements(CHAR_DATA *ch, char *argument)
{
    char first[MAX_INPUT_LENGTH];
    int category;

    if (!achievement_is_player(ch))
    {
        send_to_char("Mobiles do not earn achievements.\n\r", ch);
        return;
    }

    achievement_check_state(ch, true);
    argument = one_argument(argument, first);

    if (first[0] == '\0')
    {
        achievement_show_summary(ch);
        return;
    }

    category = achievement_category_lookup(first);
    if (category >= 0)
    {
        achievement_show_list(ch, category, 0, NULL);
        return;
    }

    if (!str_cmp(first, "earned"))
    {
        achievement_show_list(ch, -1, 1, NULL);
        return;
    }
    if (!str_cmp(first, "incomplete"))
    {
        achievement_show_list(ch, -1, 2, NULL);
        return;
    }
    if (!str_cmp(first, "all"))
    {
        achievement_show_list(ch, -1, 0, NULL);
        return;
    }

    if (argument != NULL && argument[0] != '\0')
    {
        char search[MAX_INPUT_LENGTH];

        toc_strlcpy(search, first, sizeof(search));
        toc_strlcat(search, " ", sizeof(search));
        toc_strlcat(search, argument, sizeof(search));
        achievement_show_list(ch, -1, 0, search);
    }
    else
        achievement_show_list(ch, -1, 0, first);
}

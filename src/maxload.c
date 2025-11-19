/**************************************************************************
 * This Code has been written by Blackbird for Times Of Chaos.            *
 * armavirum@wxs.nl                                                       *
 * Times of Chaos has the rights to make any changes to this code for     *
 * their use. Handing this code out to any other mud, should have the     *
 * permission of Blackbird or the owners of the mud Times Of Chaos.       *
 **************************************************************************/

#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h> /* for bzero() */
#include <time.h>

#if defined(macintosh)
#include <types.h>
#else
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>
#endif

/*
 * In merc.h needs to be written the struct ITEM_MAX_LOAD
 * and the typedef to this struct.
 * Also all the prototypes of the following functions need to be written:
 * ITEM_MAX_LOAD * get_maxload_index  args( ( int vnum )              );
 * void            add_maxload_index  args( ( int vnum, int signval, int game_load ) );
 * int             do_maxload_item    args( ( int vnum )              );
 * void            read_maxload_file  args( ( void )                  );
 * void            write_maxload_file args( ( void )                  );
 */

#include "maxload.h"
#include "merc.h"
#include "interp.h"

/* -------------------------------------------------------------------------- */
/*                               GLOBAL STATE                                 */
/* -------------------------------------------------------------------------- */

/*
 * Hash table used to track the maximum allowed loads for unique items.
 * The table should be a prime-sized bucket array for even distribution.
 */
ITEM_MAX_LOAD *maxload_index_hash[MAXLOAD_KEY_HASH];

/* Total number of maxload entries currently in memory. */
int top_maxload;

/* -------------------------------------------------------------------------- */
/*                         INTERNAL UTILITY HELPERS                           */
/* -------------------------------------------------------------------------- */

/*
 * Look up a maxload entry by virtual number using the hash table.
 * Returns NULL when no entry exists.
 */
ITEM_MAX_LOAD *get_maxload_index(int vnum)
{
    ITEM_MAX_LOAD *pLoad;

    for (pLoad = maxload_index_hash[vnum % MAXLOAD_KEY_HASH]; pLoad != NULL;
         pLoad = pLoad->next)
    {
        if (pLoad->vnum == vnum)
        {
            return pLoad;
        }
    }

    return NULL;
}

/*
 * Determine how many copies of an item are sitting on player files.
 * This is done with a shell grep; failures simply return zero so the
 * command remains robust even when the external call fails.
 */
static int get_maxload_with_players(int vnum)
{
    FILE *fp;
    char buf[1000];
    int amount = 0;

    /* Build a grep command that counts occurrences of the vnum in player files. */
    snprintf(buf, sizeof(buf), "grep \"Vnum %d\\b\" ../player/* | grep -c :", vnum);

    fclose(fpReserve);

    if ((fp = popen(buf, "r")) == NULL)
    {
        log_string("Failed opening pipe in get_maxload_with_players");
        return 0;
    }

    /* Aggregate counts from the grep output. */
    while (!feof(fp))
    {
        amount += fread_number(fp);
        fread_to_eol(fp);
    }

    pclose(fp);
    fpReserve = fopen(NULL_FILE, "r");
    return amount;
}

/* -------------------------------------------------------------------------- */
/*                          PERSISTENCE MANAGEMENT                            */
/* -------------------------------------------------------------------------- */

/*
 * Persist the current maxload table to disk. The data is written to a
 * temporary file first and then renamed into place to avoid corruption.
 */
void write_maxload_file(void)
{
    FILE *fp1;
    ITEM_MAX_LOAD *pLoad;
    int i;
    struct stat file_stats;

    if ((fp1 = fopen(MAXLOADFILE ".tmp", "w")) == NULL)
    {
        log_string("Failed writing maxload file");
        perror("Failed writing maxload file");
        return;
    }

    /* Write each maxload entry. */
    for (i = 0; i < MAXLOAD_KEY_HASH; i++)
    {
        for (pLoad = maxload_index_hash[i]; pLoad != NULL; pLoad = pLoad->next)
        {
            fprintf(fp1, "ML %d %d %d\n", pLoad->vnum, pLoad->item_curr_load,
                    pLoad->item_max_load);
        }
    }

    /* Write sentinel marking the end of the file. */
    fprintf(fp1, "%s\n", "$");
    fclose(fp1);

    /* Validate the temporary file exists before renaming it into place. */
    if (stat(MAXLOADFILE ".tmp", &file_stats) != 0)
    {
        log_string("maxload: Maxloadfile is not there... (temp version) to be copied.");
        return;
    }

    rename(MAXLOADFILE ".tmp", MAXLOADFILE);
}

/* -------------------------------------------------------------------------- */
/*                          MAXLOAD MUTATION LOGIC                            */
/* -------------------------------------------------------------------------- */

/*
 * Adjust the counters for an item when it is loaded or removed.
 * signval > 0 indicates an addition, signval < 0 indicates removal.
 * The game_load flag distinguishes between server-side spawn and player activity.
 */
void add_maxload_index(int vnum, int signval, int game_load)
{
    ITEM_MAX_LOAD *pLoad;
    int modified = 0;
    char buf[1000];

    /* Log how the function is being used for traceability. */
    if (game_load)
    {
        snprintf(buf, sizeof(buf), "Called for vnum: %d to modify as: %d as gameload.",
                 vnum, signval);
    }
    else
    {
        snprintf(buf, sizeof(buf), "Called for vnum: %d to modify as: %d as playerload.",
                 vnum, signval);
    }
    log_string(buf);

    for (pLoad = maxload_index_hash[vnum % MAXLOAD_KEY_HASH]; pLoad != NULL;
         pLoad = pLoad->next)
    {
        if (pLoad->vnum != vnum)
        {
            continue;
        }

        /* Handle increments. */
        if (signval > 0)
        {
            if (game_load)
            {
                pLoad->item_game_load += 1;
                snprintf(log_buf, sizeof(log_buf),
                         "Vnum %d|Signval: %d|Gameload|Total: %d", vnum, signval,
                         pLoad->item_game_load);
                log_string(log_buf);
                break;
            }
            else
            {
                pLoad->item_game_load -= 1;
                pLoad->item_game_load = UMAX(0, pLoad->item_game_load);
                pLoad->item_curr_load += 1;
                modified = 1;
                snprintf(log_buf, sizeof(log_buf),
                         "Vnum %d|Signval: %d|!Gameload|Total: %d", vnum, signval,
                         pLoad->item_game_load);
                log_string(log_buf);
                break;
            }
        }

        /* Handle decrements. */
        if (signval < 0)
        {
            if (game_load)
            {
                pLoad->item_game_load -= 1;
                pLoad->item_game_load = UMAX(0, pLoad->item_game_load);
                snprintf(log_buf, sizeof(log_buf),
                         "Vnum %d|Signval: %d|Gameload|Total: %d", vnum, signval,
                         pLoad->item_game_load);
                log_string(log_buf);
                break;
            }
            else
            {
                pLoad->item_curr_load -= 1;
                pLoad->item_curr_load = UMAX(0, pLoad->item_curr_load);
                pLoad->item_game_load += 1;
                modified = 1;
                snprintf(log_buf, sizeof(log_buf),
                         "Vnum %d|Signval: %d|!Gameload|Total: %d", vnum, signval,
                         pLoad->item_game_load);
                log_string(log_buf);
                break;
            }
        }

        break;
    }

    /* Persist changes when player ownership counts were modified. */
    if (modified)
    {
        write_maxload_file();
    }
}

/* -------------------------------------------------------------------------- */
/*                             COMMAND HANDLERS                                */
/* -------------------------------------------------------------------------- */

/*
 * Staff command to fetch how many copies of an item are stored with players.
 */
void do_get_maxload_with_players(CHAR_DATA *ch, char *argument)
{
    char *strip;
    char buf[100];
    char arg0[MAX_INPUT_LENGTH];
    char arg1[MAX_INPUT_LENGTH];
    int vnum, amnt, i;

    strip = one_argument(argument, arg0);
    strip = one_argument(strip, arg1);

    if ((arg1[0] == '\0') || (strlen(arg1) > 5))
    {
        send_to_char("Command is maxload pla <vnum>\n\r", ch);
        return;
    }

    if (get_trust(ch) < MAX_LEVEL)
    {
        send_to_char("This is a REALLY restricted command.\n\r", ch);
        return;
    }

    for (i = 0; arg1[i] != '\0'; i++)
    {
        if (!isdigit(arg1[i]))
        {
            send_to_char("The vnum should be numeric.\n\r", ch);
            return;
        }
    }

    vnum = atoi(arg1);
    amnt = get_maxload_with_players(vnum);
    snprintf(buf, sizeof(buf), "With players: %d\n\r", amnt);
    send_to_char(buf, ch);
}

/*
 * Core command for setting maxload limits. Supports updating, removing,
 * or creating new entries while respecting existing counts in the world.
 */
void do_set_maxload(CHAR_DATA *ch, char *argument)
{
    ITEM_MAX_LOAD *pLoad;

    int i;
    char buf[100];
    char arg0[MAX_INPUT_LENGTH];
    char arg1[MAX_INPUT_LENGTH];
    char arg2[MAX_INPUT_LENGTH];
    char *strip;
    int vnum;
    int modify;

    strip = one_argument(argument, arg0);
    strip = one_argument(strip, arg1);
    strip = one_argument(strip, arg2);

    if ((arg1[0] == '\0') || (strlen(arg1) > 5) || (arg2[0] == '\0')
        || (strlen(arg2) > 5))
    {
        send_to_char(
            "Command is: maxload set <vnum> <num>,  if <num> == -1 then the maxload will be removed.\n\r",
            ch);
        return;
    }

    if (get_trust(ch) < MAX_LEVEL - 1)
    {
        send_to_char("This is a restricted command.\n\r", ch);
        return;
    }

    for (i = 0; arg1[i] != '\0'; i++)
    {
        if (!isdigit(arg1[i]))
        {
            send_to_char("The vnum should be numeric.\n\r", ch);
            return;
        }
    }

    for (i = 0; arg1[i] != '\0'; i++)
    {
        if (i == 0)
        {
            if (!isdigit(arg1[i]) && (arg1[i] != '-'))
            {
                send_to_char("The num should be -1, 0 or a positive number.\n\r",
                             ch);
                return;
            }
        }
        else
        {
            if (!isdigit(arg1[i]))
            {
                send_to_char("The num should be -1, 0 or a positive number.\n\r",
                             ch);
                return;
            }
        }
    }

    vnum = atoi(arg1);
    modify = atoi(arg2);

    if (get_obj_index(vnum) == NULL)
    {
        send_to_char("No such object in the game.\n\r", ch);
        return;
    }

    /* Removing an entry. */
    if (modify == -1)
    {
        i = vnum % MAXLOAD_KEY_HASH;
        pLoad = maxload_index_hash[i];

        if (pLoad == NULL)
        {
            send_to_char("No maxload set on this vnum.\n\r", ch);
            return;
        }

        if (pLoad->vnum == vnum)
        {
            ITEM_MAX_LOAD *tmp = maxload_index_hash[i];
            maxload_index_hash[i] = maxload_index_hash[i]->next;
            free(tmp);
            write_maxload_file();
            send_to_char("Ok.\n\r", ch);
            return;
        }

        if (pLoad->next == NULL)
        {
            send_to_char("No maxload set on this vnum.\n\r", ch);
            return;
        }

        for (; pLoad->next != NULL; pLoad = pLoad->next)
        {
            if ((pLoad == NULL) || (pLoad->next == NULL))
            {
                send_to_char("Yell at Blackbird for not doing maxload good.\n\r",
                             ch);
                return;
            }

            if (pLoad->next->vnum == vnum)
            {
                ITEM_MAX_LOAD *tmp = pLoad->next;
                pLoad->next = pLoad->next->next;
                free(tmp);
                write_maxload_file();
                send_to_char("Ok.\n\r", ch);
                return;
            }
        }

        send_to_char("No maxload set on this vnum.\n\r", ch);
        return;
    }

    /* Creating a new entry when none exists yet. */
    pLoad = get_maxload_index(vnum);
    if (pLoad == NULL)
    {
        int with_pla = 0;
        int in_game = 0;
        OBJ_DATA *obj;

        with_pla = get_maxload_with_players(vnum);

        /* Count how many of the item exist in the world. */
        for (obj = object_list; obj != NULL; obj = obj->next)
        {
            if (obj->pIndexData->vnum == vnum)
            {
                in_game++;
            }
        }

        /* Reject unsafe limits that are already lower than existing counts. */
        if ((modify != 0) && (with_pla + in_game > modify))
        {
            snprintf(buf, sizeof(buf),
                     "Current in game:  %d\n\rCurrent with pla: %d\n\rMinimum modi:     %d\n\r",
                     in_game, with_pla, in_game + with_pla);
            send_to_char(buf, ch);
            send_to_char("Modification rejected.\n\r", ch);
            return;
        }

        top_maxload++;
        i = vnum % MAXLOAD_KEY_HASH;
        pLoad = malloc(sizeof(*pLoad));
        pLoad->vnum = vnum;
        pLoad->item_game_load = in_game;
        pLoad->item_curr_load = with_pla;
        pLoad->item_max_load = modify;
        pLoad->next = maxload_index_hash[i];
        maxload_index_hash[i] = pLoad;
    }
    else
    {
        if (pLoad->item_game_load + pLoad->item_curr_load > modify)
        {
            snprintf(buf, sizeof(buf),
                     "Minimum value for modifcation is: %d\n\r",
                     pLoad->item_game_load + pLoad->item_curr_load);
            send_to_char(buf, ch);
            return;
        }

        pLoad->item_max_load = modify;
    }

    write_maxload_file();
    send_to_char("Ok\n\r", ch);
}

/*
 * Entry point for the "maxload" command hierarchy.
 */
void do_lst_maxload(CHAR_DATA *ch, char *argument)
{
    char buf[MAX_STRING_LENGTH];
    int i;
    ITEM_MAX_LOAD *pLoad;
    OBJ_INDEX_DATA *pObj;
    int prevent_overflow = 0;

    if (!IS_IMMORTAL(ch))
    {
        send_to_char("You should not even get this line.\n\r", ch);
        return;
    }

    if (argument[0] == '\0')
    {
        send_to_char("You have the commands: maxload set <vnum> <num>\n\r", ch);
        send_to_char("                       maxload list\n\r", ch);
        send_to_char("                       maxload pla <vnum>\n\r", ch);
        return;
    }

    if (!str_prefix("set", argument))
    {
        do_set_maxload(ch, argument);
        return;
    }

    if (!str_prefix("pla", argument))
    {
        do_get_maxload_with_players(ch, argument);
        return;
    }

    if (str_prefix("list", argument))
    {
        send_to_char("You have the commands: maxload set <vnum> <num>\n\r", ch);
        send_to_char("                       maxload list\n\r", ch);
        return;
    }

    /* Header. */
    snprintf(buf, sizeof(buf), "Listing of all items which have a %s set.\n\r",
             "maxload");
    strlcat(buf,
            "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n\r",
            sizeof(buf));

    {
        char line_buf[150];

        snprintf(line_buf, sizeof(line_buf), "       %-8s %-8s %-8s %-8s %-40s\n\r",
                 "VNUM", "IN_GAME", "WITH_PLA", "MAX", "DESCRIPTION");
        strlcat(buf, line_buf, sizeof(buf));
    }

    strlcat(buf,
            "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n\r",
            sizeof(buf));

    /* Body. */
    for (i = 0; i < MAXLOAD_KEY_HASH; i++)
    {
        for (pLoad = maxload_index_hash[i]; pLoad != NULL; pLoad = pLoad->next)
        {
            if (strlen(buf) < 4000)
            {
                size_t len = strlen(buf);

                snprintf(buf + len, sizeof(buf) - len,
                         "ML     %-8d %-8d %-8d %-8d %-40s\n\r", pLoad->vnum,
                         pLoad->item_game_load, pLoad->item_curr_load,
                         pLoad->item_max_load,
                         (((pObj = (get_obj_index(pLoad->vnum))) == NULL
                               ? "UNKNOWN"
                               : pObj->short_descr)));
            }
            else
            {
                prevent_overflow = 1;
                break;
            }
        }
    }

    if (prevent_overflow)
    {
        send_to_char("TRUNCATED INFORMATION\n\r", ch);
    }

    strlcat(buf,
            "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-\n\r",
            sizeof(buf));
    page_to_char(buf, ch);
}

/*
 * Determine whether an item can be loaded based on existing counts.
 * Returns 1 when loading is allowed, 0 when the max has been reached.
 */
int do_maxload_item(int vnum)
{
    ITEM_MAX_LOAD *pLoad;

    for (pLoad = maxload_index_hash[vnum % MAXLOAD_KEY_HASH]; pLoad != NULL;
         pLoad = pLoad->next)
    {
        if (pLoad->vnum == vnum)
        {
            if (pLoad->item_curr_load + pLoad->item_game_load < pLoad->item_max_load)
            {
                return 1;
            }

            return 0;
        }
    }

    /* If no entry exists, default to allowing the load. */
    return 1;
}

/* -------------------------------------------------------------------------- */
/*                           FILE LOADING UTILITIES                           */
/* -------------------------------------------------------------------------- */

/*
 * Read the maxload data from disk into memory. Invalid entries are logged
 * and skipped to avoid crashing on malformed data.
 */
void read_maxload_file(void)
{
    FILE *fp;
    ITEM_MAX_LOAD *pLoad;
    ITEM_MAX_LOAD *temp_load;

    char buf[1000];
    char *word;
    int i, vnum, max_load, curr_load;

    /* Reset state before loading. */
    for (i = 0; i < MAXLOAD_KEY_HASH; i++)
    {
        maxload_index_hash[i] = NULL;
    }
    top_maxload = 0;

    if ((fp = fopen(MAXLOADFILE, "r")) == NULL)
    {
        return;
    }

    for (;;)
    {
        word = fread_word(fp);
        if (word[0] == '\0')
        {
            continue;
        }
        if (word[0] == '$')
        {
            break;
        }
        if (strlen(word) != 2)
        {
            log_string("Error in read_max_load_file: Length command word <> 2");
            snprintf(buf, sizeof(buf), "Skipping line with word: %s", word);
            log_string(buf);
            fread_to_eol(fp);
            continue;
        }
        if ((UPPER(word[0]) != 'M') && (UPPER(word[1]) != 'L'))
        {
            log_string("Error in read_max_load_file: UPPER(word) <> ML");
            snprintf(buf, sizeof(buf), "Skipping line with word: %s", word);
            log_string(buf);
            fread_to_eol(fp);
            continue;
        }

        vnum = fread_number(fp);
        curr_load = fread_number(fp);
        max_load = fread_number(fp);

        if ((temp_load = get_maxload_index(vnum)) != NULL)
        {
            log_string("Error in read_max_load_file: Double entry");
            snprintf(buf, sizeof(buf), "For vnum %d", vnum);
            log_string(buf);
            continue;
        }
        if (max_load < 1)
        {
            log_string("Error in read_max_load_file:");
            snprintf(buf, sizeof(buf), "Maxload for vnum %d < 1", vnum);
            log_string(buf);
            continue;
        }

        top_maxload++;
        i = vnum % MAXLOAD_KEY_HASH;
        pLoad = malloc(sizeof(*pLoad));
        pLoad->vnum = vnum;
        pLoad->item_game_load = 0;
        pLoad->item_curr_load = curr_load;
        pLoad->item_max_load = max_load;
        pLoad->next = maxload_index_hash[i];
        maxload_index_hash[i] = pLoad;
    }

    fclose(fp);
    maxload_chain();
}

/*
 * Placeholder hook called after loading the maxload table. Currently a stub
 * but left in place for future extensions.
 */
int maxload_chain(void)
{
    return 1;
}


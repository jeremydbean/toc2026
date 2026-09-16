/**************************************************************************
 * SEGROMv2 was written and concieved by Eclipse<Eclipse@bud.indirect.com *
 * Soulcrusher <soul@pcix.com> and Gravestone <bones@voicenet.com> all    *
 * rights are reserved.  This is based on the original work of the DIKU   *
 * MERC coding team and Russ Taylor for the ROM2.3 code base.             *
 **************************************************************************/

#if defined(macintosh)
#include <types.h>
#else
#include <sys/types.h>
#endif
#include <stdio.h>
#include <time.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/time.h>
#include <errno.h>
#include <string.h>
#include <strings.h> /* for bzero() */
#include <stdlib.h>
#include "merc.h"
#include "interp.h"

#define PKILLFILE     "../area/pkilldata.txt"

PKILL_LIST_DATA *pkill_list;
PKILL_LIST_DATA *free_pkill;

void save_pkills(void)
/* Save the pkill table.
 *
 */
{ FILE *fp;
  struct stat file_stats;
  PKILL_LIST_DATA *ptr;

  fclose(fpReserve);
  if ((fp = fopen( PKILLFILE ".tmp", "w" ) ) == NULL )
  {  log_string("Failed writing pkiller file");
     perror("Failed writing pkiler file");
     fpReserve = fopen( NULL_FILE, "r" );
     return;
  }
  for (ptr = pkill_list; ptr != NULL; ptr = ptr -> next)
  {     fprintf(fp,"PK %s %ld %ld\n",
	    ptr->name,
	    ptr->pkills_received,
            ptr->pkills_given);
  }
  fprintf(fp,"%s\n","$");
  fclose(fp);
  fpReserve = fopen( NULL_FILE, "r");
  if ( stat( PKILLFILE ".tmp", &file_stats ) != 0 )
    log_string ( "PKILLFILE is not there... (temp version) to be copied." );
  else
    rename( PKILLFILE ".tmp", PKILLFILE );
}

void update_pkills(CHAR_DATA *ch)
{ int pcount, inserted;
  PKILL_LIST_DATA *pLoad, *pPrev, *pNext, *pNew;

  if (IS_NPC(ch)) return;

  /* First remove all existences in the pkill list of this char */
  pPrev = NULL;
  for (pLoad = pkill_list; pLoad != NULL; pLoad = pNext) 
  { pNext = pLoad -> next; 
    if (!str_cmp(ch->name,pLoad ->name))
    { if (pPrev == NULL) 
        pkill_list = pLoad -> next;
      else
        pPrev -> next = pLoad -> next;
      pLoad -> next = free_pkill;
      free_pkill = pLoad;
      free_string(pLoad -> name);
      pLoad -> pkills_received = 0;
      pLoad -> pkills_given = 0;
      /* pPrev still points to the previous of pLoad->next */
    }
    else 
      pPrev = pLoad;
  };
  pPrev = NULL;
  pcount = 0;
  inserted = 0;
  for (pLoad = pkill_list; pLoad != NULL; pLoad = pNext )
  { pNext = pLoad -> next;
    pcount += 1;
    if ((pLoad -> pkills_given - pLoad -> pkills_received) >=
       (ch->pcdata -> pkills_given - ch->pcdata->pkills_received))
    { pPrev = pLoad;
      continue;
    };
    if (free_pkill == NULL)
      pNew = alloc_perm(sizeof(*pNew));
    else
    { pNew = free_pkill;
      free_pkill = free_pkill -> next;
      pNew -> next = NULL;
    }
    pNew -> name = str_dup(ch->name);
    pNew -> pkills_given = ch->pcdata->pkills_given;
    pNew -> pkills_received = ch->pcdata->pkills_received;
    pNew -> next = pLoad;
    if (pPrev == NULL)
      pkill_list = pNew;
    else
      pPrev -> next = pNew;
    inserted = 1;
    break; 
  }
  if (!inserted) {
    if (free_pkill == NULL)
      pNew = alloc_perm(sizeof(*pNew));
    else
    { pNew = free_pkill;
      free_pkill = free_pkill -> next;
      pNew -> next = NULL;
    }
    pNew -> name = str_dup(ch->name);
    pNew -> pkills_given = ch->pcdata->pkills_given;
    pNew -> pkills_received = ch->pcdata->pkills_received;
    pNew -> next = pLoad;
    if (pPrev == NULL)
      pkill_list = pNew;
    else
      pPrev -> next = pNew;
  }
  pcount = 0;
  pPrev = NULL;
  for (pLoad = pkill_list;pLoad != NULL; pLoad = pNext )
  { pNext = pLoad->next;
    pcount += 1;
    if (pcount > MAX_PKILL_LIST) {
      if (pPrev == NULL) return;
      pPrev -> next = NULL;
      free_string(pLoad->name);
      pLoad->pkills_received = 0;
      pLoad->pkills_given = 0;
      if (pNext != NULL) {
        free_string(pNext->name);
        pNext->pkills_received = 0;
        pNext->pkills_given = 0;  
        while (pNext -> next != NULL) 
        { pNext = pNext -> next;
          free_string(pNext->name);
          pNext->pkills_received = 0;
          pNext->pkills_given = 0;  
        }
      }
      if (pNext == NULL) {
        pLoad->next = free_pkill;
        free_pkill = pLoad;
      }
      else
      { pNext -> next = free_pkill;
        free_pkill = pLoad;
      }
      save_pkills();
      return;
    }
   }
  save_pkills();
  return;
}

void do_topten( CHAR_DATA *ch, char *argument )
{ int i,boundary;
  UNUSED_PARAM(argument);
  char buf[MAX_STRING_LENGTH];
  PKILL_LIST_DATA *pkill;
 
  boundary = UMIN(MAX_PKILL_LIST,UMAX(10,MAX_PKILL_LIST-10));
  send_to_char("The top10 of pkillers:\n\r",ch);
  snprintf(buf, sizeof(buf), "Pos  %-15s%10s%10s%10s\n\r", "Player", "Received", "Given", "Total");
  send_to_char(buf, ch);
  send_to_char("--------------------------------------------------\n\r",ch);
  pkill = pkill_list;
  for (i=0;i<boundary;i++) 
  { if (pkill != NULL)
    {
     snprintf(buf, sizeof(buf), "[%2d] %-14s:%10ld%10ld%10ld\n\r", i + 1, pkill->name,
             pkill->pkills_received,
             pkill->pkills_given,
             pkill->pkills_given - pkill->pkills_received);
     send_to_char(buf, ch);
     pkill = pkill -> next;
    }
  };
  send_to_char("--------------------------------------------------\n\r",ch);
}

static bool parse_pkill_count(const char *text, long *value)
{
   char *endptr;
   long parsed;

   if (text == NULL || text[0] == '\0' || value == NULL)
      return false;

   errno = 0;
   parsed = strtol(text, &endptr, 10);
   if (errno == ERANGE || *endptr != '\0' || parsed < 0)
      return false;

   *value = parsed;
   return true;
}

void load_pkills(void)
/* Read in the pkill_file, specified in the variable PKILLFILE. */
{
   FILE *fp;
   int i;
   int c;
   int fields;
   PKILL_LIST_DATA *pLoad;
   PKILL_LIST_DATA *pLast;
   char line[1000];
   char command[3];
   char name[MAX_INPUT_LENGTH];
   char received_word[1000];
   char given_word[1000];
   char extra[2];
   long received;
   long given;
   bool found_end;

   pkill_list = NULL;
   pLast = NULL;

   if ( (fp = fopen( PKILLFILE, "r" ) ) == NULL )
      return;

   i = 0;
   found_end = false;
   while (fgets(line, sizeof(line), fp) != NULL)
   {
      if (strchr(line, '\n') == NULL && !feof(fp))
      {
         while ((c = getc(fp)) != '\n' && c != EOF)
            ;
         log_string("Skipping oversized line in pkill file.");
         continue;
      }

      fields = sscanf(line, " %2s %255s %999s %999s %1s",
                      command, name, received_word, given_word, extra);
      if (fields == 1 && !str_cmp(command, "$"))
      {
         found_end = true;
         break;
      }

      if (fields != 4 || str_cmp(command, "PK")
      ||  !parse_pkill_count(received_word, &received)
      ||  !parse_pkill_count(given_word, &given))
      {
         log_string("Skipping malformed line in pkill file.");
         continue;
      }

      if (i >= MAX_PKILL_LIST)
         break;

      pLoad = alloc_perm(sizeof(*pLoad));
      pLoad->name = str_dup(name);
      pLoad->pkills_received = received;
      pLoad->pkills_given = given;
      pLoad->next = NULL;

      if (pLast == NULL)
         pkill_list = pLoad;
      else
         pLast->next = pLoad;
      pLast = pLoad;
      i++;
   }

   if (!found_end && feof(fp))
      log_string("Pkill file ended without a terminator; valid records were retained.");
   fclose(fp);
}

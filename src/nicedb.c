#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "merc.h"

/* ------------------------------------------------------------------------
 *  nicedb main
 * ------------------------------------------------------------------------ */
int main(int argc, char *argv[]) {
    boot_db();
    return 0;
}

/* ------------------------------------------------------------------------
 *  boot_db -- load the area files
 * ------------------------------------------------------------------------ */
void boot_db(void) {
    chdir(AREA_DIR);
    // ... rest of implementation ...
}

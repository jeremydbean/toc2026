# Code review findings

## Web admin queue never processed on Unix builds
- The FastAPI web admin service writes actions to `/app/area/webadmin.queue`, but the main Unix game loop never calls `process_web_admin_queue()`. The hook exists only in the Mac/MSDOS loop, so Linux deployments (including Docker) will ignore all queued admin requests, leaving the dashboard nonfunctional.
  - Mac/MSDOS loop processes the queue after `update_handler()`.【F:src/comm.c†L614-L618】
  - Unix loop omits the call and immediately proceeds to output handling.【F:src/comm.c†L820-L843】

## Double fclose in area loading
- `do_areaload` closes `fp` immediately after the existence check and then calls `fclose(fp)` again after `load_area_file`, invoking `fclose` on an invalid pointer and invoking undefined behavior during area reloads.【F:src/edit.c†L90-L100】

## Flood disaster movement check is broken
- In `disaster_update`, the code compares the `rand_door` array name to zero instead of verifying the chosen index. The condition is always true, so the code can try to move characters with an uninitialized `door` when no exits were collected, risking out-of-bounds access during floods.【F:src/update.c†L2966-L2984】

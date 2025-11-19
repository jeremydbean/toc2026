# Scripting hook overview

ToC now emits a handful of high-level events so that a future embedded Lua 5.4
runtime can react to server activity without forcing the core C loop to include
Lua headers. The hooks live in `src/script_event.c` and are surfaced through the
API declared in `src/merc.h`.

## Event API

```c
void script_event_subscribe(script_event_type type,
                            script_event_callback callback,
                            void *context);
void script_event_unsubscribe(script_event_callback callback,
                              void *context);
void script_event_emit(script_event_type type, void *payload);
```

Each listener receives an opaque payload pointer that can be cast to the event-
specific struct listed below. Callbacks execute on the main game thread, so they
should return quickly.

| Event | Payload struct | Emitted from | Notes |
| ----- | -------------- | ------------ | ----- |
| `SCRIPT_EVENT_PRE_POLL` | `script_loop_prepoll_payload` | `game_loop_unix` right after `process_web_admin_queue` | Gives scripts a heartbeat just before the descriptor poll. Currently exposes the timestamp of the previous tick. |
| `SCRIPT_EVENT_INPUT_RECEIVED` | `script_input_event_payload` | `game_loop_unix` whenever `read_from_descriptor` succeeds | Provides the descriptor pointer, raw input buffer, and buffer length so Lua can inspect telnet text before it is tokenized. |
| `SCRIPT_EVENT_TIMER_TICK` | `script_timer_tick_payload` | `game_loop_unix` before `update_handler()` | Carries the elapsed microseconds/seconds for the loop iteration so scripts can schedule recurring work. |
| `SCRIPT_EVENT_CHAR_LOGIN` | `script_char_login_payload` | `nanny` when a player finishes MOTD | Indicates whether the player is brand new and whether they reconnected to an existing session. |
| `SCRIPT_EVENT_COMMAND_PREPARSE` | `script_command_payload` | `interpret` after alias expansion | Allows scripts to rewrite the command buffer or swallow the input entirely by setting `handled = true`. |
| `SCRIPT_EVENT_COMMAND_NOT_FOUND` | `script_command_payload` | `interpret` before falling back to socials | Gives Lua first chance to implement custom commands. Set `handled = true` to prevent the default "Huh?" reply. |
| `SCRIPT_EVENT_BEFORE_COMMAND` | `script_command_payload` | `interpret` immediately before the C `do_fun` executes | Scripts can veto (`handled = true`) or mutate the argument pointer before the command runs. |
| `SCRIPT_EVENT_AFTER_COMMAND` | `script_command_payload` | `interpret` right after the C command completes | Useful for logging or post-processing scripted effects. `handled` is preset to `true` to indicate the native handler ran. |

All payload structs live in `src/merc.h` so the eventual Lua bridge can safely
cast the `void *` pointer inside its callbacks.

## Example Lua bridge snippet

The following pseudo-code shows how to expose the existing `send_to_char` helper
to Lua 5.4 once the VM is linked into the binary. The Lua binding can be
registered when the scripting subsystem starts up and can use the event system
above to decide which characters should receive scripted output.

```c
#include <lua.h>
#include <lauxlib.h>

static int l_send_to_char(lua_State *L)
{
    CHAR_DATA *ch = (CHAR_DATA *)lua_touserdata(L, 1);
    const char *msg = luaL_checkstring(L, 2);

    if (ch == NULL)
        return luaL_error(L, "nil character");

    send_to_char(msg, ch);
    return 0;
}

void lua_register_game_api(lua_State *L)
{
    lua_pushcfunction(L, l_send_to_char);
    lua_setglobal(L, "send_to_char");
}
```

Lua usage:

```lua
function greet_player(ch)
    send_to_char("Welcome to the Tower of Chaos!\n\r", ch)
end
```

In practice the bridge would also subscribe to the login and command events so
Lua scripts can call `greet_player` (or similar helpers) whenever a character
enters the game or types a scripted command.

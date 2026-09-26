# Times of Chaos Game Client Guide

Times of Chaos supports traditional Telnet clients, a first-party browser
client, and an official Mudlet interface. Mudlet is the desktop option with an
automatic exploration map; the browser client prioritizes zero-install play.

## Mudlet And Automatic Mapping

Create a Mudlet profile for the game host on port `9000`. For the public host,
use `toc.jeremybean.com`; for local development, use `localhost`. Leave
**Enable GMCP** and **Allow server to install script packages** enabled. The
server advertises the official interface and the full-world map when GMCP
is negotiated, and a changed package version updates existing installations.

The interface includes HP, mana, movement, and experience gauges, character
status, room status, and an embedded mapper. `Room.Info` adds rooms as they are
visited and refreshes the room name, area, terrain, and visible directional
exits on later visits. If an exit is removed or retargeted by a world update,
the mapped room is reconciled the next time the client receives its data.
Same-room data changes are also sent without requiring the character to move.

The map deliberately does not reveal secret exits or rooms the character
cannot see. Portals, `enter` routes, teleports, and scripted movement may not
draw normal directional links. Deleted rooms that cannot be revisited may stay
in the local map. The game text, `exits`, and `search` remain authoritative.
Map data is saved in the Mudlet profile rather than the character file.

Mudlet provides these local aliases:

```text
tocgui status
tocgui off
tocgui on
```

They report package/GMCP status, hide the interface, and restore it. Mapping
continues while the interface is hidden. If the package does not appear,
confirm both profile options above and reconnect. Manual assets and build
instructions are in [the Mudlet directory](../mudlet/README.md).

The Times of Chaos web client is a first-party MUD client served by the same
private web service as the administration dashboard. It works in current
desktop and mobile browsers and does not download third-party scripts, fonts,
or terminal libraries.

## Open The Client

The automated installation starts the client at:

```text
http://127.0.0.1:9001/client
```

The dedicated Raspberry Pi LAN appliance starts the same client automatically
with `toc2026-web.service`. From another device on that private LAN, open:

```text
http://toc.local:9001/client
```

If mDNS is unavailable, use `http://PI_ADDRESS:9001/client`. Port `9001` is
required; a bare Pi address selects port 80 and will be refused.

The launchers can open it directly:

```powershell
.\toc.ps1 play
```

```bash
./toc.sh play
```

`open` remains an alias for `play`. Use `toc.ps1 admin` or `toc.sh admin` to
open the full operations dashboard.

Remote players must be able to reach the web service securely for the browser
client to work. Keep the administrative service private by default. If the
client is published, put it behind HTTPS and an access-controlled reverse
proxy; the game WebSocket uses the same origin as the page.

Traditional MUD clients can continue connecting directly to the game host and
port, normally `localhost:9000`.

The browser client does not currently include the Mudlet automatic mapper.

## Play Workspace

The client connects automatically when opened. The header reports Connecting,
Connected, Game unavailable, or Disconnected. Use **Connect** and
**Disconnect** to control the session manually. Unexpectedly closed sessions
reconnect when the Reconnect preference is enabled.

The terminal supports:

- standard and bright ANSI foreground colors
- classic ANSI background colors and text attributes
- Telnet ECHO negotiation for password fields
- output split across network frames
- server-driven paging for long command output
- bounded display and transcript buffers
- optional line wrapping and timestamps
- adjustable fixed terminal text size
- local command echo

The command line sends normal input when Enter is pressed. Up and Down move
through the current session's command history. Password input is masked and is
never added to history, local echo, aliases, or the downloaded transcript.
Submitting an empty command sends a single terminal newline without adding a
blank command to local echo, history, or the transcript.
Separate normal commands with semicolons to send them individually in order,
for example `look; north; get sword`. Empty segments are ignored, and a chain
may contain up to 50 commands. Semicolons inside matching single or double
quotes remain part of that command; use `\;` for a literal unquoted semicolon.
Password fields are never split. Command history stores the original chain as
one entry, while local echo shows each command actually sent.
Clicking the terminal focuses the command line for immediate typing. Selecting
terminal text keeps the selection active so it can still be copied.

The desktop command panel includes movement, character, and combat actions.
Mobile layouts keep a compact command strip beneath the input. Every quick
action uses the same command path as typed input.

## Routes

The Routes panel lists every published way to walk somewhere, named for the
zone with its builder in brackets -- `Moria (Alfa)` -- so the list reads and
sorts by destination rather than by whoever built it. The same list appears in
the dashboard's Routes view and both read the public `/api/directions`.

Clicking a set of directions sends it to the game. **Copy** puts it on the
clipboard instead, for pasting into another client.

Tick **Mudlet style** to separate the copied commands with `;;` instead of
`;`. Mudlet treats a single semicolon as ordinary text and needs two to break
one line into several commands, so directions copied without this ran as one
long nonsense command. The setting is remembered in the browser and changes
only what is shown and copied: the client's own send button always uses the
stored single-semicolon form, and `/api/directions` is unchanged, so anything
else reading the feed is unaffected.

## Aliases

Open **Session**, then use **Add** under Aliases. An alias contains:

| Field | Purpose |
|---|---|
| Alias | The first word typed in the command line |
| Command | The game command sent in its place |
| Pin | Adds a one-tap button above the command line |

Use `{args}` where arguments should be inserted. For example:

```text
Alias:    ca
Command:  cast 'armor' {args}
```

`ca Jeremy` sends `cast 'armor' Jeremy`. If a command has no `{args}` marker,
arguments are appended to it. Expansion occurs once; aliases do not expand
other aliases recursively.

Aliases and display preferences are stored only in that browser profile. They
are not written to character files or the server.

## Transcript

The download control in the header saves the current bounded session transcript
as UTF-8 text. ANSI control sequences, Telnet negotiation, and password input
are omitted. **Clear terminal** clears both the visible output and the current
download buffer.

## Administration

Open the command panel and select **Admin**. Default local installations unlock
this panel automatically through an HttpOnly browser session; the permanent
admin token is not exposed to client JavaScript. Remote deployments and local
installations with `WEB_ADMIN_LOCAL_UNLOCK=0` use the server's
`WEB_ADMIN_TOKEN`. Manual token entry uses session storage by default;
**Remember on this browser** uses local storage until the token is cleared.

The embedded admin workspace provides:

- game reachability, player-save count, area warnings, and room totals
- live, filterable Server Info and WizInfo activity with bounded history
- protected player lookup with character, resource, combat, and equipment data
- level-targeted WizInfo announcements
- validated immortal command queueing
- authenticated live logs and bounded log snapshots
- backup creation and recent backup archive status
- atomic dashboard area-data refresh
- confirmed game shutdown

Manual tokens are sent in `X-Admin-Token` headers or as the first message on the
protected log and server-activity WebSockets. Local auto-unlock uses an
HttpOnly, SameSite=Strict
cookie. Neither form is included in a URL. Select **Lock** to clear the current
session and browser token storage. Reloading a loopback page can establish a
new local session while local auto-unlock remains enabled.

Use **Dashboard** inside the admin panel for full world search, area maps,
health findings, gear analysis, and the complete operations interface,
including **Update ToC** on configured appliances.

## Client Security

- The game and log WebSockets accept same-origin browsers. Native clients
  without an Origin header remain compatible.
- Additional trusted browser origins require `WEB_ALLOWED_ORIGINS`, as a
  comma-separated list of complete origins such as `https://mud.example.com`.
- Oversized and binary browser-to-game frames are rejected by the bridge.
- Server output is rendered through text nodes. ANSI data is parsed into fixed
  CSS classes and is never treated as HTML.
- Administrative routes remain disabled when `WEB_ADMIN_TOKEN` is unset.

Do not publish the administration listener directly to the Internet. Use TLS,
network access controls, and a reverse proxy or VPN when remote access is
required.

## Troubleshooting

### Game Unavailable

Check the full dashboard's game status, then confirm `MUD_HOST` and `MUD_PORT`
for the web service. In Docker, the web service and game normally share one
container and use internal port `9000`.

### The Page Loads But The WebSocket Fails

Confirm the reverse proxy forwards WebSocket upgrades for `/ws`, `/ws/logs`,
and `/ws/events`.
The public page and WebSocket must use the same host. Add a deliberately
different trusted origin to `WEB_ALLOWED_ORIGINS` only when the deployment
requires it.

### Admin Unlock Is Rejected

Read `WEB_ADMIN_TOKEN` from the host's private `.env` file. Restart the web
service after changing it. A missing token disables protected administration;
an incorrect token is rejected. For local automatic access, also confirm
`WEB_ADMIN_LOCAL_UNLOCK=1`, `WEB_ADMIN_BIND=127.0.0.1`, and that the page was
opened with a loopback hostname rather than a LAN address.

The Raspberry Pi LAN profile deliberately sets `WEB_ADMIN_LOCAL_UNLOCK=0`, so
manual token entry is expected. The token survives reboot and automatic update
because `/home/toc/toc2026/.env` is preserved. On macOS, copy it without
printing it to the terminal:

```bash
ssh toc "sed -n 's/^WEB_ADMIN_TOKEN=//p' /home/toc/toc2026/.env" | pbcopy
```

Paste it into the authentication dialog. **Remember on this browser** keeps it
in that browser profile until **Lock**, browser-data clearing, or token rotation.

### The Pi Address Refuses The Browser

Use `http://PI_ADDRESS:9001/` for the dashboard or
`http://PI_ADDRESS:9001/client` for play. If those fail, confirm the service and
listener on the Pi:

```bash
systemctl status toc2026-web
ss -ltn 'sport = :9001'
```

The LAN profile should show `0.0.0.0:9001`. The generic Docker/default profile
shows `127.0.0.1:9001` and requires a local browser or SSH tunnel.

### Colors Look Wrong

Use the game's color settings to enable ANSI output. The client accepts the
classic 16-color palette; unsupported terminal cursor-control sequences are
ignored.

The admin dashboard's **Game console** also renders ANSI colors and text
attributes, including sequences split across incoming network messages. Refresh
the admin page after a web asset update. Clear removes visible scrollback without
changing the current game color; reconnecting resets terminal decoding state.

The C server converts its internal `{HH}` color markers before sending output;
the browser client intentionally parses ANSI only. Seeing literal markers such
as `{0D` or `{0F` indicates an outdated server binary or a server output path
that bypassed `send_to_char()`/`page_to_char()`. Rebuild and restart first, then
report the exact command if the markers remain.

## Related Guides

- [Player Guide](player-guide.md)
- [Web Admin Guide](web-admin-guide.md)
- [Hosting Guide](hosting-guide.md)
- [Operator Guide](operator-guide.md)
- [Security Policy](../SECURITY.md)

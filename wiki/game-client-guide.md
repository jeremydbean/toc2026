# Times of Chaos Web Client Guide

The Times of Chaos web client is a first-party MUD client served by the same
private web service as the administration dashboard. It works in current
desktop and mobile browsers and does not download third-party scripts, fonts,
or terminal libraries.

## Open The Client

The automated installation starts the client at:

```text
http://127.0.0.1:9001/client
```

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
- bounded display and transcript buffers
- optional line wrapping and timestamps
- adjustable fixed terminal text size
- local command echo

The command line sends one command at a time. Up and Down move through the
current session's command history. Password input is masked and is never added
to history, local echo, aliases, or the downloaded transcript.
Submitting an empty command sends a single terminal newline without adding a
blank command to local echo, history, or the transcript.
Clicking the terminal focuses the command line for immediate typing. Selecting
terminal text keeps the selection active so it can still be copied.

The desktop command panel includes movement, character, and combat actions.
Mobile layouts keep a compact command strip beneath the input. Every quick
action uses the same command path as typed input.

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
health findings, gear analysis, and the complete operations interface.

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

### Colors Look Wrong

Use the game's color settings to enable ANSI output. The client accepts the
classic 16-color palette; unsupported terminal cursor-control sequences are
ignored.

## Related Guides

- [Player Guide](player-guide.md)
- [Web Admin Guide](web-admin-guide.md)
- [Hosting Guide](hosting-guide.md)
- [Operator Guide](operator-guide.md)
- [Security Policy](../SECURITY.md)

# Changelog — Times of Chaos (ToC)

All notable changes to this project are documented in this file.

Format loosely follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Fixed

- **One player quitting disconnected every other player online.** `do_quit`
  ends with a loop meant to close a duplicate login of the same character,
  comparing `CHAR_DATA.id`. Nothing in the codebase ever assigns that field
  -- the only line touching it was the comparison -- so every character's
  id was 0, the test was `0 == 0`, and the loop extracted and closed every
  connected descriptor. `delete` routes through `do_quit`, so it behaved
  the same way. It was reported as "snooping someone who deletes
  disconnects the immortal", which was simply the case where somebody was
  watching closely enough to notice. The loop now matches on name, copied
  out before `extract_char` frees `ch`.

- **The Makefile never rebuilt anything when a header changed.** Its
  pattern rules depended only on the `.c` file, so editing `merc.h`
  recompiled nothing -- not a stale build but a silently corrupt one.
  `MAX_INPUT_LENGTH` sizes three arrays inside `DESCRIPTOR_DATA`, so
  changing it rebuilt only the touched translation units with the new
  struct layout while the rest kept the old; the linker joins that without
  complaint and the program then reads and writes past the fields it thinks
  it is addressing. It surfaced as a long paste wedging a connection under
  `make` while the identical source handled it correctly under CMake, which
  tracks headers properly. Fixed with `-MMD -MP` and `-include`: touching
  `merc.h` now schedules 35 recompiles where it scheduled none. Production
  was never affected -- `deploy/toc2026-update` runs `make clean` first.
  **When Make and CMake disagree on behaviour, suspect the build.**

- Nine permission gates read `ch->trust` directly instead of calling
  `get_trust()`. `trust` is 0 unless somebody explicitly assigns one, which
  is the normal state, so each gate compared 0 against its threshold and
  refused everybody including implementors: `stat room`, `gather` from the
  world and by name, `advance`, `mset qp` above 100, `oset` on portals and
  on item types, switched-immortal visibility in `who`/`whois`, and `order`
  against a charmed immortal (which compared two raw trusts, so `0 >= 0`
  refused every such order). The three gated at exactly 70 widen access
  rather than restore it, which is what the comparison was written to mean.

- Twenty-two immortal commands refused when `get_trust(victim) >=
  get_trust(ch)`. At MAX_LEVEL that reads `70 >= 70`, so an implementor
  could not point any of them at another implementor -- the people those
  commands mostly exist for. `rank_protects()` in `handler.c` now states
  the exemption once. Below MAX_LEVEL nothing changes, and `victim == ch`
  guards are untouched: rank is not what those are about.

- `say` truncated itself at `MAX_INPUT_LENGTH - 100`, or 156 characters,
  silently, and no other channel did. The limit is 510 now, and overrunning
  it trims the line, delivers it, and says how much was used. Overflowing
  the accumulation buffer used to return FALSE from `read_from_descriptor`,
  which the caller treats as a hangup -- so pasting something long cost you
  the connection and everything you had typed.

- A multi-word alias lost its argument. The expansion joins the alias body
  to whatever follows as `"%s %s"`, so used bare it produced `"goto 4108 "`
  with a trailing space; `do_goto` hands its whole argument to
  `find_location` without tokenising, `is_number("4108 ")` is false because
  of the space, and it stops treating the argument as a vnum. Single-word
  aliases were unaffected. The composed line is trimmed now.

- `prompt` with no argument turned prompts *off*, so the obvious way to ask
  what your prompt was set to was also the way to lose it. The help file
  has described the opposite for years; the code now matches it.

- `WIZINFO` opened a colour and never closed it, so cyan ran on into
  whatever printed next. It was the only coloured channel in the codebase
  missing its `{00`, and it fires on every login.

- Both strings of berries in the newbie pack are `ITEM_NODROP`, so a newbie
  given the pack could not put them down. Cleared on the copies the pack
  makes rather than on vnums 5776 and 5780, which exist elsewhere in the
  world where the flag is deliberate.

- New characters got recall at 1%. `group_add()` grants every starting
  skill at 1%, which is fine for skills you practise up and wrong for the
  one that gets a level one character out of trouble. Two other places
  already set it (50 on a legacy file upgrade, 100 on reroll) and neither
  covered creation, which is why it went unnoticed.

- Hyrule's hand-written mobs did not answer to the words describing them:
  `look old` and `look man` both missed "a gambling old man", whose
  keywords were `hyrule money game elder`. The generator now folds the
  short description into the keywords, so the rule holds for future mobs
  rather than for the eleven that were wrong.

- `Sock.sinaddr` and `EOF encountered on read` fired for every connection
  including the healthcheck's loopback probe every two minutes -- roughly
  1,400 lines a day burying everything else. Both are now skipped for
  loopback only.

- The dashboard displayed `127.0.0.1:9000` as the game endpoint. That is
  where the web service dials, not anywhere a player can reach.

- `parse_login_journal`'s docstring claimed newest-first while the function
  returns file order, oldest first.

### Added

- **Hermie**, a standing spellup desk and Herbie's girlfriend (mob vnum 98).
  `spellup` plants her; she casts on whoever talks to her from a menu she
  reads out, every spell pinned to 30 ticks and logged. `spellpurge` clears
  every copy in the world; she deliberately carries no `ACT_NOPURGE` so an
  ordinary `purge` clears the one in front of you. There is no speech hook
  in this codebase -- spec_funs run on a pulse and never see what a player
  said -- so `do_say` calls her directly. She answers only when addressed,
  or she would paste her menu over every conversation in her room.

- `DNS` is implemented; it was a stub answering "not available". It
  reports and toggles hostname resolution, lists what the resolver made of
  everyone connected beside their numeric address, and looks up one
  address. The toggle matters: `getnameinfo` runs in a single-threaded loop
  on every connection, so a slow resolver stalls the game mid-login.

- `GRANTPSI` works on a character who is not logged in, using the same
  load / modify / save / extract shape as `do_undeny`. An offline grant is
  always deferred -- "now" would apply to a copy about to be discarded.

- `SET` reaches the fields it could not: `hitroll damroll armor wimpy move
  maxmove exp` on characters, `name short long condition material` on
  objects, `name description` on rooms. The room text fields sit *before*
  the numeric check, which would otherwise reject them. Its help is
  rewritten and now lists every room flag, object extra flag, wear flag,
  item type and sector number -- they previously existed only in `merc.h`.

- `wizhelp` lists every command the character can use, sorted. The table
  hoists a few entries to the front for prefix matching, so the listing
  opened with `at`, `goto`, `iportal`, `sockets` and nothing was where you
  would look for it -- `smash` and `iportal` both read as missing when they
  had been there all along.

- `purge <object>` works, on portals or anything else, and says when the
  thing it removed was flagged nopurge. Purging a *player* now severs their
  link and leaves them linkdead rather than extracting the character.

- `holylight` carries the room vnum, and `prompt room on|off` adds or
  removes it for staff. `%R` is staff-only: `do_exits` already hid vnums
  from mortals and the prompt was the one place they leaked.

- `HELP NEW` lists everything a player can change about how the game reads,
  linked from the text shown at character creation. `damagenumbers` is
  documented and now **off** by default -- it was on with no help entry at
  all.

- The player web client has a searchable **Help** tab needing no login. It
  reads the area files rather than keeping a copy, so the site cannot drift
  from what the game serves to `HELP`. Only level 0 and below is exposed,
  filtered at parse time, since that is the whole security model for an
  unauthenticated endpoint.

- Server activity, the log terminal and login history page 50 at a time
  with arrows. Activity pages client-side deliberately -- its filters run
  over the whole history, so paging the fetch would filter within a page.
  `/api/logs/page` and `/api/events?paged=1` are new.

- The admin panel reports players online by name, and game uptime beside
  the host's: a deploy restarts the game and not the hardware.

- `WIZINFO` now reports empower, titanic, spellup, spellpurge, grantpsi and
  trust, saying whether a grant is permanent. Trust also tells the player
  being trusted. A mob catching lycanthropy from a dice roll no longer
  reports anything.

- `~/bin/toc-deploy` (developer machine, not in the repo) holds a deploy
  when a player other than Killuminati is connected. The updater restarts
  the game; before this existed a real player was disconnected twice in one
  afternoon.

### Changed

- Bank interest is 0.25% a day, down from 1% -- which compounds to roughly
  3700% a year and made a balance a better income than playing. `score`
  shows a lifetime interest total, since the payment arrives while you are
  offline and the notice scrolls past on login.

- Carry weight is half again the base for every player. It was briefly a
  newbie-only bonus, which just moved the wall further along.

- The newbie pack carries an endless snack pack and endless water jug in
  place of ten pot pies and a water jug, everything in it is level 1
  including the pack, and it holds 100 platinum.

- Every class starts its issued weapon at 40% instead of 1%.

- Announcements are upper-cased regardless of how they were typed, with a
  blank line and an indent so the text reads as the message rather than as
  part of the frame.

- `MAX_INPUT_LENGTH` is 512, giving 510 usable characters -- about six
  lines at 80 columns.

- The dashboard's local-admin unlock no longer trusts the `Host` header. It
  gated on `request.url.hostname`, which the caller writes, so a request from
  anywhere carrying `Host: 127.0.0.1` was issued an admin session cookie that
  opens every protected endpoint. It now gates on the peer address, the one
  part of a request a remote caller cannot choose. The unlock's other guard
  read `WEB_ADMIN_BIND` while uvicorn bound whatever `--host` said, and the
  production unit passes `--host 0.0.0.0` with no such variable set, so the
  guard believed it was loopback-bound; the bound address is now recorded at
  startup. Not exploitable in production, where the unlock is off, but one
  environment variable away from being so.

- Fixed the Python area parser losing a line on the seven shipped area files
  written with a blank line between every record line (hood, haven, wyvern,
  arena, firenewt, valley, trollden). It skipped blanks before the
  area/flags/sector line but not before the room name, so the blank became
  the name and the first line of the description was then read as the flags
  line. Around 300 rooms had an empty name and a word of prose stored as
  their sector type, which the dashboard displayed and which would have made
  the new world map unreadable. The C loader was always fine, so only
  Python-side consumers were affected. Blank room names go from ~300 to zero;
  world totals and every area-health baseline are unchanged.
- The Mudlet mapper now spirals outwards for a free square when the room it
  would place is already occupied. Placing each new room one step from the
  room walked in from assumes a grid, and one-way exits, up/down loops and
  teleports routinely put two rooms on the same square, where Mudlet drew
  them on top of each other.
- Fixed a blank line at the name prompt silently closing the connection.
  Stock ROM hangs up there without a word, which drops any player who simply
  presses Enter and any client that probes the login prompt with an empty
  line -- the reason a clean Mudlet profile could install the interface and
  then lose its first connection to the bundled generic mapper. The prompt is
  now reissued instead. The behaviour that made the hangup defensible is
  kept: a connection that sends nothing but blank lines is still dropped,
  after `MAX_BLANK_LOGIN_LINES` of them.
- Fixed three ragged rows in the `score` sheet, which is a fixed 62-column
  box built from independent format strings. The bank shared the Constitution
  row, where its four denominations needed nine more columns than the
  carried-coin cell beside them even at minimum field widths, and a balance
  past 999 platinum widened it further -- a real account holding 1,078,289
  platinum pushed that border thirteen columns past every other row. The bank
  now has a full-width row of its own, which keeps all four denominations and
  cannot be widened out of the box by any balance a long can hold. The
  achievements row was one column short and the Pkiller flag row two. A live
  test now asserts every row closes at exactly 62 columns, using the same
  balance that exposed the misalignment.
- Preserve link-dead characters and switched immortals during SIGTERM/SIGINT
  shutdown by saving all live player characters, not only connected descriptors.
- Preserve streaming ANSI colors and Telnet password state in the admin console;
  bound scrollback and render server text without interpreting it as HTML.
- Keep extensionless Unix deployment scripts LF-only on Windows checkouts.
- Make Mudlet package 1.0.2 reproducible across operating systems and zlib
  versions using LF source assets and deterministic stored ZIP entries.

- Allowed the sandboxed Pi updater to write only the system script and unit
  directories used by its checked-in self-refresh step. `ProtectSystem=full`
  previously blocked `/usr/local/sbin` before the validated update could
  restart either live service.

- The official Mudlet mapper now reconciles every standard direction against
  the latest `Room.Info`: removed exits are deleted, retargeted exits are
  replaced, and obsolete stubs are cleared when a room is revisited. The game
  also detects changed room data while a character remains in the same room,
  and package version 1.0.1 triggers automatic delivery of the fix.

- Fixed password input becoming visible in Telnet and browser clients. The
  modern option parser rejected the client's acknowledgement of the server's
  echo-suppression request, immediately cancelling it; the acknowledgement is
  now accepted and normal echo resumes only after password entry finishes.
- Fixed native macOS startup failing at `SO_LINGER` with "Numerical argument
  out of domain" by using a portable, bounded 30-second linger interval, and
  stopped the validator from requesting unsupported LeakSanitizer behavior on
  Darwin.
- Fixed `compare` overvaluing damroll and Strength by applying enhanced damage
  after damroll and by multiplying damroll into the backstab estimate; `one_hit`
  adds damroll last, after both. This could invert weapon recommendations,
  most sharply for thieves.
- Fixed projected equipment removal in `compare` erasing flight, invisibility,
  and detect-invisibility even when a spell still supplied the effect, where
  `unequip_char` preserves it.
- Fixed `compare` reporting weapons as usable by a monk under `steel fist`,
  which `wear` refuses.
- Fixed `bomb` accepting any object whose keyword merely began with "bomb",
  and `burn` accepting a candle carried unlit in inventory rather than the lit
  candle the help text documents.
- Hoisted a NULL check in `spell_cause_madness()` that sat after three
  dereferences of the pointer it guarded, so it could never have fired.
  `TAR_CHAR_DEFENSIVE` targeting means the pointer is the caster when no
  target is named, so NULL was not reachable, but a guard placed after the
  dereferences it protects is worse than no guard. Found by `-fanalyzer`.
- `coins_to_copper()` now saturates instead of overflowing. The obvious
  formulation multiplies the platinum count by 1,000,000 unguarded, which is
  undefined behaviour above roughly 9.2 trillion platinum. Normal play cannot
  reach that because `copper_to_breakdown()` only distributes totals that
  already fit, but a hand-edited or corrupted player file can, and pfile
  numbers are exactly what AGENTS.md requires validating before multiplying.
- Strengthened Telekinesis, which was capped at a 50% success rate even at
  100% skill because it rolled against `chance / 2`; no other psionic power
  halves its own learned percentage. It now rolls against the full skill.
  It also charged its whole 50-mana cost before searching, so a mistyped
  item name cost a full casting: the full cost is now paid only when an item
  is actually retrieved, and a fruitless search costs only the effort. A
  match that is merely too heavy to carry is now reported as such instead of
  being folded into "you couldn't find it".
- Astral Walk no longer uses the generic `saves_spell()` curve against
  mobiles, which pinned its resist roll at the 95 ceiling for the
  high-level targets the power exists to reach. It now uses the shared
  psionic ward check: an immune mind cannot be fixed upon, a resistant mind
  may shrug off the pull, and an ordinary mind cannot resist.
- Astral Walk and Shift now tell the caster that the crossing leaves them
  stunned. The stun itself is deliberate balance -- it denies a free opening
  turn so neither power can be used to jump a player and act first -- but it
  previously happened silently, with nothing explaining why the character
  could not act. Documented in help and the psionics guide, and pinned by a
  test so it is not softened by mistake.
- Fixed a use-after-free in the character/object list iterator that could
  corrupt memory or crash the server whenever something died inside a
  world-list loop. `extract_char()` removes the very element a
  `FOR_EACH_CHARACTER` loop is standing on, but `list_remove()` freed the
  node immediately while the iterator cursor still aliased that node's
  `next` field. Sixteen loops were exposed, including `violence_update()`,
  `aggr_update()`, `char_update()`, `mobile_update()`, `do_mindblast()`,
  `spell_earthquake()`, `spell_blizzard()` and `spell_call_lightning()`.
  Because `next` is the last field of `LIST_NODE`, a freed chunk usually
  still held a readable pointer, so the defect surfaced as rare
  unreproducible corruption rather than a dependable crash - which is why it
  survived a previous iterator fix. Removal now tombstones the node and
  defers the free until `flush_container_lists()` runs at the top of the game
  loop, where no iteration is in progress, and the iterator skips tombstones
  so an already extracted element is never handed back to a caller.
  AddressSanitizer confirms the old code faulted and the new code is clean;
  `tests/test_list_iterator.c` reproduces all four removal orderings and now
  runs under ASan/UBSan as part of both validation suites.
- Fixed Mind Leech and Enervate being silently halved against most targets.
  The same psionics pass that broke Confuse added the generic `saves_spell()`
  curve to both drains, and because that curve is driven by the target's
  (usually negative) saving throw rather than by any psionic defense, a
  mastered drain gave up half its effect on nearly every use. Both now share
  the Confuse ward model through a single `psionic_ward_check()` helper:
  mental immunity blocks the drain outright, mental resistance halves it on a
  bounded roll, and an ordinary mind cannot resist. Mindbar, Psionic Armor,
  and Psychic Shield still apply on top through
  `psionic_reduce_mental_drain()`, so real psionic defenses keep working.
  Confuse was refactored onto the same helper, so the resist band is tuned in
  one place (`PSI_RESIST_BASE`/`MIN`/`MAX`).
- Fixed Confuse failing almost every attempt. The psionics pass added the
  generic `saves_spell()` curve as a second gate, and that curve clamps to a
  95% resist rate against the negative saving throws most mobiles carry, so a
  100%-skill power was blocked nearly every cast. Confuse now gates only on
  the caster's concentration roll and the target's mental ward: a mind immune
  to mental damage is never confused, a mentally resistant mind gets one
  bounded resist roll (25% base, shifted by level difference, clamped to
  5-50%), and a normal or vulnerable mind cannot resist at all.
- Hardened carried-money conversion, bank deposits and withdrawals, shop and
  sacrifice payouts, group splits, gifts, theft, dropped piles, NPC corpse
  coins, and casino accounting against signed overflow, narrowing, partial
  mutation, and silent currency loss.
- Fixed partial money pickups leaving stale pile descriptions and values,
  loose piles being treated as 50 times heavier than carried coins,
  future-dated interest timestamps blocking accrual, consumed no-payout days
  not being saved, and 64-bit casino totals being truncated while loading.
- Fixed malformed or unterminated PK leaderboard data making every server boot
  and native area validation spin forever at end-of-file; valid records now
  load through a bounded line parser and malformed records are skipped.
- Corrected bank help to document the actual default platinum denomination and
  casino help to document the real 100,000-gold Hi/Lo and roulette limits.
- Fixed Hyrule mobile resets using a population cap of 1,000, which could
  duplicate Ganon and every other surviving NPC whenever an empty area reset
  ran after a player disconnected. Generated limits now match each mobile's
  intended population.

### Added

- The Mudlet package now ships a full-world map: all 7,781 rooms across 92
  areas, each area laid out offline with no two rooms sharing a square, and
  every exit resolved. It replaces the 25-room Mud School starter map.
  Mud School keeps area id 1 so an existing profile is not reshuffled, and
  area names are generated to match exactly what `Room.Info` sends, since the
  package looks areas up by name and a mismatch would silently duplicate
  every one of them. Package version 1.0.3 delivers it automatically.
- `tocgui atlas` pulls that world map into a profile on demand (package
  version 1.0.4). Mudlet only downloads the server's map into a profile
  that does not already have one, so every profile that connected before
  the atlas shipped would otherwise keep its old partial map forever. The
  command replaces the profile's saved map, so it is never automatic.
- Added boot-time local discovery for the Raspberry Pi appliance. Every
  NetworkManager Ethernet and Wi-Fi profile now explicitly sends `toc` as its
  IPv4 and IPv6 DHCP hostname, while Avahi publishes `toc.local` over mDNS.
  The configuration never cycles an active connection, so applying an update
  cannot interrupt SSH.

- Added in-game `MAP`, `MUDLET`, `GMCP`, and `WEBCLIENT` help covering automatic
  mapping, package controls, protocol data, browser capabilities, update
  behavior, persistence, troubleshooting, and intentional mapping limits.

- Added a native, low-memory Raspberry Pi appliance deployment with headless
  systemd boot, game/dashboard crash recovery, graceful SIGTERM player saves,
  capped journald storage, encrypted six-hour GitHub player snapshots, and an
  weekly guarded `origin/main` updater. The protected dashboard now includes
  **Update ToC**, which requests the same backup, fast-forward, one-job build,
  native area validation, restart, and health-check workflow. A private-LAN
  profile publishes the browser client and dashboard on port 9001 while keeping
  operational routes behind the persistent admin token.

- Added a sandboxed, timer-driven Namecheap Dynamic DNS updater for the Pi
  appliance. It detects and validates the public IPv4 address, keeps the
  `toc.jeremybean.com` A record current approximately every ten minutes, stores
  its domain-specific credential outside Git, and runs without a resident
  daemon.

- Added a low-duty-cycle Raspberry Pi ACT LED status indicator. It flashes
  briefly every two seconds while the MUD service is running, turns off when
  the game stops, and follows systemd boot and crash recovery automatically.

- Added first-class Mudlet support: `IAC GA` prompt framing, `Char.Vitals`,
  `Char.Status`, and `Room.Info` GMCP messages, automatic `Client.Map` and
  `Client.GUI` delivery, a 25-room Mud School MMP map, and a self-updating
  Mudlet package with gauges and an embedded mapper.
- Added deterministic Mudlet asset generation and tests plus a live handshake
  probe that verifies negotiation, package/map advertisement, ping handling,
  prompt framing, and isolation of GMCP data from login names.
- Added combat effects for the `flaming`, `frost`, `vampiric`, `sharp`, and
  `vorpal` weapon flags, which 135 of 623 weapons carried with no mechanical
  effect. Elemental flags add damage and convert the damage school so immunity
  and resistance apply; vampiric drains to the wielder; sharp and vorpal are
  damage procs scaled by weapon skill. Effects are folded into the single
  `damage()` call rather than added as a second call, and `compare` credits
  them. See `notes/weapon_flags_plan.md` for the balance notes.
- Added money-conservation and persistence tests to the live suite. Currency
  is four denominations backed by a single copper total plus a bank balance,
  so every operation is a conversion and a chance to lose or duplicate value;
  the tests assert that convert, deposit, withdraw, and drop/get all conserve
  it exactly, and that hostile amounts (zero, negative, overflowing, and
  non-numeric) move nothing. Persistence is checked by round trip rather than
  by reading the save code: every autolist toggle is flipped, saved, and
  re-read after a reconnect.
- Added `patch_player_file()` and `make_funded_character()` test helpers for
  state a fresh character cannot reach (coins, a bank balance, a starting
  room). They edit a character's own saved file, so no host `crypt(3)`
  binding is needed -- Python removed the `crypt` module in 3.13.
- Added MCCP2 output compression, negotiated per client and off by default.
  Compression is applied in `write_to_descriptor()`, the single choke point
  for descriptor output, so every existing caller benefits without knowing
  about it; GMCP and other protocol writes go through the same path and are
  compressed too. The handshake is sent uncompressed and the deflate stream
  armed only afterwards, since everything following the acknowledgement is
  deflate output. A failed deflate falls back to plain output rather than
  dropping the session, and the stream is released when the descriptor
  closes. Builds now link `libz`: `zlib1g-dev` to build, `zlib1g` at runtime
  (the Docker runtime stage previously shipped neither).
- Added telnet option handling. The input path had no IAC handling at all,
  so any client that negotiated options fed protocol bytes to the command
  interpreter as garbage, which is why none of the modern MUD options were
  supported. A single state machine in `src/telnet_proto.c` now consumes
  negotiation and subnegotiation, and three options are built on it:
  - **MSSP** reports name, player count, uptime, and codebase to crawlers, so
    the game can be indexed and kept current on MUD listing sites. Only
    already-public facts are exposed; nothing operational.
  - **NAWS** records the client's window size. It deliberately does not
    change the page length on its own, because `lines == 0` means the player
    turned paging off on purpose; `scroll` now reports the detected size and
    `scroll auto` opts in to it.
  - **GMCP** sends `Char.Vitals` alongside the prompt for clients that ask
    for it, so Mudlet-style gauges track without scraping prompt text.
  A plain Telnet client that negotiates nothing is unaffected, which is
  covered by its own test.
- Added per-address login throttling. Nothing counted failed password
  attempts before: a wrong password closed the socket, which cost an attacker
  only a reconnect, against hashes where just the first eight password bytes
  are effective. Five failures now refuse the address at accept() time with an
  escalating backoff from 30 seconds to a 15-minute cap; a success clears it
  and old history decays. The table is a fixed 64 entries so it cannot be used
  to exhaust memory. Loopback is exempt by default because the browser client
  bridges through the dashboard and every web player shares 127.0.0.1;
  `TOC_THROTTLE_LOOPBACK=1` opts it in.
- Added end-to-end gameplay tests that boot a real server, connect over
  Telnet, create a character, play, save, and reconnect. Every other test in
  the suite asserts on source text, so this is the first layer that can catch
  a change which compiles and reads correctly but does not actually work.
  Data is fully isolated: the game resolves its mutable paths relative to the
  working directory, so the harness runs each server from a throwaway `area/`
  copy and real `player/`, `gods/`, and `heroes/` data is never touched.
  Skipped automatically where there is no built binary or on Windows.
- Added an AddressSanitizer/UndefinedBehaviorSanitizer CI job that boots the
  full world, runs the list-iterator regression test, and performs a live
  startup smoke run. The normal suite cannot see memory errors, which is how
  the iterator use-after-free survived a previous fix.
- Added an authenticated dashboard operations snapshot with game reachability,
  queue depth, backup freshness, recent player saves, runtime-file activity,
  searchable Server Info/WizInfo history, and a compact expandable backup list.
- Added a guaranteed random Ganon relic drop alongside his fixed progression
  loot: the level 54-58 Hero's Tunic, Blue Ring, Red Ring, Mirror Shield, and
  Pegasus Boots. Their unique kill-healing, damage-ward, magic-ward, and travel
  effects are implemented in gameplay and modeled explicitly by `compare`.
- Added bounded semicolon command chaining to both browser game consoles, with
  ordered sends, quote and escape handling, single-entry history, and password
  protection.
- Added a WoW-style permanent character achievement system with 127 cataloged
  accomplishments, points, earned dates, ten categories, hidden discoveries,
  progress views, nearby unlock announcements, retroactive state checks, and
  save-compatible stable keys.
- Added sixteen Economy achievements for banking, interest, carried wealth,
  denominations, lifetime casino results, jackpots, straight-up roulette wins,
  and royal flushes.
- Added verified world-boss, rare-relic, crafting, unusual-death, Farslay, and
  expanded level achievements, including group boss credit and collection,
  crafting, encounter, and misadventure meta achievements.
- Fixed the player-scribed deadly black Farslay scroll recipe so it contains
  the Vengence spell instead of an invalid legacy skill name.
- Added complete Hyrule achievement tracking for dungeon discovery, maps,
  compasses, Triforce shards, signature items, all nine bosses, grouped boss
  credit, Ganon, Princess Zelda, and campaign-wide meta achievements.
- Added idempotent one-command installers and fresh-machine bootstraps for
  Windows, macOS, Debian/Ubuntu, and Raspberry Pi OS; installers now obtain
  prerequisites, generate private configuration, start Docker, build, launch,
  health-check, and preserve completed work across required OS restarts.
- Added PowerShell/Bash lifecycle launchers with start, build, stop, restart,
  status, logs, doctor, update, and dashboard-open actions, plus double-click
  Windows and macOS install/start entry points.
- Added an advanced in-game `compare` command with player-specific gear
  profiles, focus modes for damage, spells, defense, leveling, and utility,
  full-loadout projections, usability warnings, and percentage recommendations.
- Added a generated Hyrule First Quest area (`30200-30799`) with a teleport-only
  Campus entry, the 128-screen overworld, all nine source-derived dungeon
  layouts, a complete level 1-70 gear curve, and two return routes.
- Added data-driven `burn`, `bomb`, `play`, and `feed` puzzle commands for
  candle bushes, cracked walls, Recorder interactions, and the hungry Goriya.
- Added Hyrule progression tests for every gear level, dungeon entrances,
  boss drops, shard sources, canonical items, puzzles, and room reachability.
- Added a unique readable map and functional boss compass to each Hyrule
  dungeon, including route guidance through legacy portal and stair links.
- Added all First Quest regular, deluxe, and Letter-gated potion shops; 14
  rupee secrets; nine one-time door-repair charges; five money-making games;
  and the four-location Power Bracelet warp network.
- Added the Hyrule `gamble` command, bomb combat against Dodongo, reusable
  Magical Key behavior, consumable dungeon keys, automatic shutters, and
  signature Like Like, Bubble, Wallmaster, Gohma, and Ganon mechanics.
- Added `merc --check-area` / `merc --validate` startup mode for loading the full area database and exiting without opening a listening socket.
- Added reusable area-health linting in `webadmin/area_health.py`, the `scripts/area_lint.py` CLI, a web admin Area Health view, and the `/api/area_health` endpoint.
- Added cross-platform validation runners: `scripts/validate.ps1` for Windows/WSL and `scripts/validate.sh` for Linux, macOS, WSL, and CI.
- Added GitHub Actions validation in `.github/workflows/validate.yml`.
- Added Python unit tests for area-health summaries and key web-admin API behavior.
- Added the immortal `diagnostics` command for boot time, world totals, descriptor/list counts, active mobs, and backup schedule visibility.

### Changed

- Moved 25 unreferenced one-off scripts out of the repository root into
  `archive/tools/` with a README explaining each group. They were retired
  help-rewriting passes, bulk area fixers, typo sweeps, and abandoned
  dashboard prototypes that nothing in the runtime, build, validation suite,
  or CI referenced, and they sat beside the four checkers validation does
  run. Several perform the unbounded global `.are` replacement the area
  guide warns against, so they should not be mistaken for current tooling.
- Added ignore rules for CMake/build output (`bin/`, `build/`,
  `build-sanitize/`) and Python virtual environments (`.venv/`, `venv/`), so
  a documented `python3 -m venv .venv` no longer shows up as untracked work.
- Web-admin API tests now report why the test client is unavailable instead
  of always blaming a missing `fastapi`. starlette raises a `RuntimeError`
  when `httpx2` is absent, and these tests need both
  `webadmin/requirements.txt` and `scripts/requirements.txt`.
- Psionic travel, scouting, retrieval, control, draining, healing, and defense
  powers now share consistent room protection, saving throw, mana, lag, skill
  improvement, and combat-start behavior.
- Replaced contradictory psionics help with an accurate 17-power player guide,
  real remort selection rules, command costs, defense values, and restrictions.
- Docker Compose now binds both ports to loopback by default, supports explicit
  host bind/port variables, persists god/hero/corpse state, and reports game
  readiness through a container health check. Public install mode exposes only
  the game port.
- Docker image builds now exclude private runtime state, logs, backups, and
  `.env` from their context and create empty runtime mount points instead.
- Container startup now maps its unprivileged `toc` account to configured host
  UID/GID values before dropping privileges, allowing fresh Linux bind mounts
  to remain writable without running the game or dashboard as root.
- Area-health source tracking now follows `P` reset chains back to a real room
  or mobile source, without hiding objects inside unreachable containers.
- Expanded web admin configuration with `AREA_PATH`, `BACKUP_PATH`, `--area-path`, and `--backup-path`.
- Web admin reloads now validate a complete replacement parser, reject critical issues with HTTP 422, preserve the last known-good data on failure, and list recent backup archives.
- Operational web-admin endpoints are disabled until `WEB_ADMIN_TOKEN` is configured; queue payloads are bounded and restricted to one protocol-safe line.
- Player-save snapshots now use bounded native path construction and directory creation instead of shell-built `mkdir` commands.
- Backup archive creation now verifies shell command return codes, creates the backup directory when needed, and logs success only after archive creation succeeds.
- Rebuilt the repository documentation around dedicated player, command,
  hosting, operator, developer, contributing, and security guides; the README
  is now an accurate project front door instead of a mixed-audience manual.
- Corrected documented build paths, player/immortal level boundaries, remort
  thresholds, current world totals, web API routes, Docker restart behavior,
  dashboard exposure, legacy DES/Telnet limitations, and bow/run/speedwalk help.
- Replaced obsolete install/startup/cleanup/refresh instructions that used
  hard-coded paths, permissive modes, binary copies, and broad process kills
  with current prerequisite helpers and safe compatibility wrappers.
- Added `.env` Git/Docker exclusions, a safe `.env.example`, and ignore rules
  that prevent newly created player/god/hero files from being staged by
  accident; documented that already tracked legacy hashes remain exposed.
- Hyrule documentation now records source provenance, coordinate conversion,
  generated vnum ranges, progression, secrets, runtime rules, fidelity limits,
  regeneration, and regression coverage.

### Fixed

- Invalid portals no longer consume gold or charges, crystal-ball entry now
  replies to the player, successful Riding improves correctly, saddles use
  normal equipment hooks, and stale or invisible mount state no longer crashes
  or broadcasts uninitialized text.
- Monk buffs no longer consume mana when already active, ghost-blocked attacks
  no longer consume mana or movement, and a failed Crane Dance now uses its
  documented 30 mana while recording a failed skill attempt.
- Bulk `put` now rolls concealment independently for every item and reports an
  empty match; lycanthropy checks every weather tick, avoids reinfecting tagged
  mobiles, bounds restored were-form inventory, and skips stale object vnums.
- Immortal were-form editing now rejects negative indexes instead of reading
  before the form table.
- Dashboard view changes now return to the top instead of carrying a long
  Operations-page scroll offset into Overview or another section.
- Fixed `AUTOGOLD` searching the room instead of the defeated mobile's corpse,
  and made `AUTOSAC` preserve every corpse that still contains money, boss
  drops, or loot the player could not carry.
- Repaired normal bow shooting through closed or secret exits, silent immunity
  on `NOPURGE` mobiles, unsupported player targeting, missing Archery skill
  improvement, unsafe pursuit through one-way/transport exits, and potentially
  lethal anti-cheese backlash.
- Restored city guards' unreachable innocent-protection behavior, prevented an
  NPC cleric using Mana Convert from dereferencing player-only data, and fixed
  shield reflection leaving a one-hit-point attacker marked dead.
- Applied the Red Ring, Blue Ring, and Mirror Shield wards to reflected fire and
  frost damage so those effects match their player-facing descriptions.
- Made Ganon's Silver Arrow finale an explicit `shoot ganon` action, available
  at level 54 without Archery skill, while preserving the Arrow's boosted
  normal damage and preventing normal attacks from delivering the final blow.
- Ganon's one-hit-point phase now ends combat for every attacker, turns his
  room appearance bright red, announces the Silver Arrow opening, and repeats
  that instruction when players look at him.
- Lowered Hyrule's required Silver Arrow from the immortal-only level 68 range
  to the maximum mortal level 59, restoring a mortal path to defeating Ganon.
- Fixed paged commands exposing raw `{0D` color tokens instead of terminal
  colors, and compacted the achievement summary into paired category columns
  so its normal overview fits within the default page length.
- Fixed Telekinesis bypassing take, corpse-looting, bound quest-item, and
  no-teleport rules; Confuse requiring 139 mana instead of its actual cost;
  Clairvoyance counting remote views as physical exploration; astral travel
  charging before target validation; and Project possessing the wrong ghost.
- Fixed Enervate healing from resisted damage, empty or duplicate defensive
  casts consuming full mana, Transfusion allowing ineffective casts without
  lag or skill improvement, and invalid `grantpsi` lists unlocking no powers.
- Fixed psionic special mobiles overwhelmingly selecting Torment, restored
  reliable self-defense casting, and added fair use of newer combat powers.
- Reworked automatic quests to choose suitable live targets, credit nearby
  group members and pet-assisted kills, accept turn-ins at any questmaster,
  bind and clean up recovery tokens, find tokens inside containers, and save
  cooldown and timeout transitions immediately. Protected service mobiles,
  explicitly unkillable targets, and ghosts are no longer selected.
- Fixed active-quest logout preserving streaks, heroes being unable to abort,
  object quests having a different cooldown, practice rewards disagreeing with
  their advertised range, malformed gamble percentages, reward additions
  overflowing the quest-point balance, and remort preserving a high-level
  quest after returning the player to level 3.
- Replaced the quest shop's mislabeled translucent-key "trophy" with a real
  questmaster keepsake, hardened missing reward prototypes, and added quest
  achievements for 250 completions, a 25-win streak, rushes, final-minute
  turn-ins, gamble wins, and acquiring the keepsake.
- Fixed `lore` allowing negative research fees to pay repeatable gold, omitting
  its value estimate, hiding later spells, and miscalculating negative affects
  and weapon averages.
- Fixed Raise Dead destroying belongings the revived player could not carry,
  ambiguous player matching, and unsaved recoveries; heavy items now remain in
  the corpse and the spell requires the exact online owner.
- Fixed soul trapping overlooking later empty bottles, unsaved soul capture and
  release, Water Burst wasting all water, Geyser destroying its container, and
  Transfusion allowing its user to remain standing at zero hit points.
- Kept skeletons, wraiths, and vampires charmed for their full summoned lives,
  rather than allowing them to roam uncontrolled after an early charm expiry.
- Fixed multi-race equipment being wearable by no race, repaired the slots and
  advertised powers of five signature relics, and preserved invisibility,
  detect-invisibility, and flight when another worn, racial, or spell source
  still grants the effect.
- Prevented pending automatic-quest gamble rewards from being overwritten,
  bounded practice and quest-streak rewards, persisted quest state promptly,
  cleared rush state on abort, and allowed the hero experience exchange at the
  exact required experience threshold.
- Fixed fire, frost, and death-shroud shield state checks so mutually exclusive
  shields cannot stack, and capped energy-drain healing at maximum hit points.
- Made `concoct` and `scribe` recipes ingredient-order independent, removed
  failed-craft object leaks, preserved ingredients for unknown recipes, saved
  consumed rare components immediately, and corrected their player help.
- Fixed stale seasonal-vendor pointers that could crash timed despawns, restored
  event-boss defeat announcements, moved holiday rewards into corpses, and
  guaranteed each event boss awards at least one primary rare item.
- Bounded Hero Quest item lookups, saved each recovered relic, removed temporary
  magic immunity and no-follow state on every exit, and safely floored abandon
  penalties while keeping current and maximum health consistent.
- Fixed death ray falsely announcing Ganon's death before his protected reform,
  and documented the permanent training reward on the two rare holiday foods.
- Fixed the advertised quest-shop Potion of Power, Potion of the Giant, and
  Scroll of Farslay never appearing in `AQUEST LIST` or being purchasable.
- Fixed Farslay scrolls consuming themselves without a target, leaking or
  removing the reader's holy-light setting, and resolving duplicate Farslay
  slots as repeated deaths and permanent penalties.
- Bounded Farslay's permanent resource and attribute costs, protected NPC
  casters from player-data access, and stopped protected Ganon attempts from
  falsely announcing and logging his death.
- Fixed Herbie's automatic rescue choosing an arbitrary wounded player due to
  integer division, being blocked by invalid or link-dead candidates, moving
  away while fighting, flooding recipients with hundreds of heal messages,
  and returning to a hard-coded room instead of his actual origin.
- Fixed ordinary seasonal candy corn and spiced cider using the rare training-
  food type, which let inexpensive vendor snacks grant permanent trains.
- Prevented training-food rewards from overflowing the 16-bit train counter,
  saved them immediately after consumption, corrected their displayed type,
  and exposed the type accurately in the web area browser.
- Fixed `remort <password> ...` and `resetpwd <player> <newpassword>` being
  registered as `LOG_ALWAYS`, which wrote plaintext password arguments to game
  logs and snoop output; added a regression test for all credential commands.
- Fixed off-hand attacks using main-hand proficiency, secondary wield bypassing
  item restrictions, and failed weapon swaps removing the equipped weapon.
- Fixed comparison estimates for off-hand proficiency, low-skill unarmed damage,
  two-handed no-remove conflicts, and engine-applied experience bonuses.
- Fixed Hyrule's inactive Raft gate, two nonlethal dead ends, mismatched armor
  slots, held Recorder use, and Recorder effects weakening unrelated NPCs.
- Fixed incorrect overworld locations for Levels 8 and 9, the White and Master
  Swords, Princess Zelda's Letter, and the Power Bracelet.
- Fixed legacy Hyrule shopkeeper vnums being shared with dungeon elders and
  combat mobiles; generated vendors now use dedicated prototypes and stock.
- Fixed dungeon maps and compasses remaining readable while blind or in darkness.
- Fixed inferred dungeon wall links by deriving all 56 First Quest bomb walls
  from the paired NESMaps room markers, including Death Mountain's 19 pairs.
- Fixed single-item gear comparisons matching unrelated worn objects through
  the universal `ITEM_TAKE` flag instead of an actual shared equipment slot.
- Fixed the CMake/C17 build using unavailable BSD `strlcpy`/`strlcat` calls
  instead of the repository's portable bounded string helpers.
- Fixed the PowerShell startup smoke test treating a healthy timeout-driven
  server shutdown as a validation failure.
- Fixed Unix game-loop web-admin queue processing so queued dashboard actions are handled on Linux/Docker builds.
- Fixed a web-admin queue race that could lose actions appended while the game loop read and deleted the queue file.
- Fixed player saves reporting success and creating snapshots after failed writes or failed atomic replacement.
- Fixed player restore overwriting the live file before its snapshot copy completed; restores now force a pre-change snapshot and atomically replace from a temporary file.
- Fixed null-stream crashes in corpse history and `areasave` failure paths, and bounded corpse-history item counts read from disk.
- Fixed shared text readers hanging or mishandling EOF when a data file ends without a newline.
- Fixed repeated area-parser and wizlist loads retaining stale state or using an invalid list tail.
- Fixed stale review/documentation notes for the previously resolved `areaload` double-close and flood movement checks.

---

## [2026.04 (April 2026)] — Area Content & Stability

### Fixed — Spelling & Grammar in World Files (Rounds 1–30)

A comprehensive audit of all 132 `.are` files was performed, correcting over 400 spelling, grammar, and article errors. Areas modified across all 30 rounds:

**Rounds 1–10** (various .are files):
- `alot` → `a lot` across many files
- there/their/they're errors
- `immediatly` → `immediately` (multiple areas)
- `strangly` → `strangely`
- Apostrophe errors in contractions and possessives
- Double-word errors (`the the`, `in in`, etc.)
- `erradicate` → `eradicate`
- `heros` → `heroes`

**Rounds 11–20**:
- Continued systematic scan across remaining areas
- Corrected verb agreement and pluralization errors
- Various jumbled/transposed word fixes

**Rounds 21–30** (specific, documented):
- `Round 21` — `kerofk.are`: Removed redundant `potatoe` keyword; fixed `potatoe^H` (literal backspace control character artifact)
- `Round 22` — 14 files: `forboding`→`foreboding` (nether, despair, scult, prison, abyss); `amazment`→`amazement` (gcult); `unconsious`→`unconscious` (glitter); `preperation`→`preparation` (nethril1); `beneith`→`beneath`, `pedistal`→`pedestal` (tarin); `pedastal`→`pedestal` (mountain ×2); `stalagtites`→`stalactites` (horde); `Persistant`→`Persistent` (camelot); `apparant`→`apparent` (newthalo); `boundries`→`boundaries` (world)
- `Round 23` — 9 files: `Calender`→`Calendar` (korzath2); `unfamilar`→`unfamiliar` (dresden, dresden_halloween, dresden_xmas); `equipement`→`equipment` (highland); `nonexistance`→`nonexistence` (crypt); `harrasing`→`harassing` ×4 each (limbo, limbo_xmas, limbo_halloween)
- `Round 24` — 11 files: `headress`→`headdress` ×5 (northsea), ×2 (arac); `a animal`→`an animal` (horde); `a ever/emerald/even/orderly/even/orange/object/alchemy` → `an` article fixes (valhalla, mountain, ultima, solace, commands, dresden×3)
- `Round 25` — 6 files: `a elder`→`an elder` (nether); `a iron handle`→`an iron handle` (camelot); `a oak door`→`an oak door` ×2 (solace); `a east-north`→`an east-north` (moria); `a incessant`→`an incessant` ×2 (canyon); `a everlasting`→`an everlasting` (sewer)
- `Round 26` — 7 files: `terrrifying`→`terrifying` (valhalla); `apperance`→`appearance` (ag); `Sacraficial`→`Sacrificial` ×2 (abyss); `decend`→`descend` ×4 (sea), ×1 each (nether, horde, connect)
- `Round 27` — 3 files: `parliment`→`parliament` (connect); `throught`→`through` ×6, `wich`→`which` (mid_ruin); `throught`→`through` (astral)
- `Round 28` — 4 files: `crouds`→`crowds` ×3 (limbo, limbo_xmas, limbo_halloween); `maintenence`→`maintenance` ×2 (lud)
- `Round 29` — 4 files: `inscripted`→`inscribed` ×2 (ofcol), ×1 (plains); `Dispite`→`Despite` (solace); `indiscernable`→`indiscernible` (istari); `infititely`→`infinitely` (istari)
- `Round 30` — `mid_ruin.are`: `remains fo the southern` → `remains of the southern`

---

### Added — New Content

- **`area/ashen_wastes.are`** — New grinding zone "The Ashen Wastes" (vnums 26700–26799): scorched post-apocalyptic landscape with progressive difficulty mobs and rare material drops

- **Quest shop items** — Three new items purchasable with quest points:
  - Potion of Power (+str/dex/con temporarily)
  - Potion of the Giant (+str/size)
  - Scroll of Farslay (ranged damage spell)

- **Seasonal area system** — Framework for holiday events, weather-tied spawns, and seasonal bosses:
  - `dresden_halloween.are`, `limbo_halloween.are` — Halloween variants
  - `dresden_xmas.are`, `limbo_xmas.are`, `midennir_halloween.are` — Christmas/holiday variants
  - Wandering seasonal vendors appear during events
  - Holiday area portals open/close based on in-game date

- **Pyrotechnics overhaul** — `spell_pyrotechnics` fully rewritten as a psi-class area attack with proper scaling and status effects

- **Heated gear mechanic** — Objects can gain a `heated` flag (from fire magic, traps, environment); wearing heated gear deals passive burn damage; cooling happens over time via `update.c`

### Added — Immortal Commands (11 new)

Implemented in `src/act_wiz.c`:

| Command | Level | Description |
|---------|-------|-------------|
| `mute` | L65 | Toggle all speech: sets COMM_MUTE + NOCHANNELS/NOTELL/NOSHOUT/NOEMOTE |
| `drag` | L66 | Pull any online PC to your current room |
| `duel` | L64 | Force two online PCs into PK combat (transports p2 to p1's room) |
| `weather` | L65 | Set global weather: sunny/cloudy/rain/storm |
| `lights` | L65 | Toggle ROOM_DARK flag on current room |
| `seal` | L65 | Toggle EX_WIZLOCKED on a room exit by direction |
| `finger` | L65 | Player info lookup (online: live stats; offline: saved file scan) |
| `trail` | L67 | Show last `TRAIL_LEN` rooms visited (ring buffer in `pc_data`) |
| `petrify` | L65 | Apply timed 'stone' affect blocking ALL commands |
| `empower` | L64 | Apply sanctuary + haste + fly + passdr + protect + regen + divprot + stat boosts |
| `colossus` | L64 | Apply 500% HP/mana/move boost, heal to full (`gsn_titanic` affect) |

Infrastructure changes for new commands:
- `MAX_SKILL` bumped 228 → 231
- `COMM_MUTE` added to comm flags
- `TRAIL_LEN 10` constant; `int trail[TRAIL_LEN]` + `sh_int trail_head` in `pc_data`
- `gsn_empower`, `gsn_titanic`, `gsn_petrify` globals added
- `petrify` affect blocks ALL commands in interpreter (`interp.c`)

---

### Fixed — Crash & Stability Bugs

A systematic use-after-free (UAF) and NULL-dereference audit was performed across the entire C source tree:

- **`src/fight.c`** — Fixed UAF in `damage()` autoloot block after `raw_kill`; fixed UAF in `fatality()` autoloot block
- **`src/magic.c` / `src/magic2.c`** — Fixed 7 spell bugs; chain lightning UAF (death-check each arc target); missile/skeletal_hands loop UAF
- **`src/update.c`** — Fixed `component_update()` infinite loops (random-vnum `for(;;)` loops now bounded to 200 attempts); fixed misindented `component_update()` calls in `weather_update()` causing stack corruption; fixed UAF in river room sweep; `char_update`, `dtrap_update`, `hit_gain`, `mana_gain` NULL guards
- **`src/skills.c`** — Fixed out-of-bounds and UAF in skill loops
- **`src/special.c`** — Fixed `spec_black_dragon` character scan NULL deref; fixed `spec_whine` NULL deref; fixed `spec_healer` NULL deref (`most_hurt` in-room check)
- **`src/save.c`** — Fixed NULL deref crashes in player save/load
- **`src/act_wiz.c`** — Fixed NULL deref crashes
- **`src/quest.c`** — Added `in_room` NULL guard before questmaster search in `do_quest`
- **`src/trap.c`** (via fight/update) — Fixed guardian trap UAF; fixed `do_manipulate` trap case 3 send-after-free
- **`src/magic.c`** — Restored `spell_rope_trick` which was accidentally disabled; fixed `spell_haven` infinite loop
- Fixed 5 bugs flagged by GCC static analysis (`-Wduplicated-cond`, `-Wlogical-op`, `-Wnull-dereference`)
- Fixed 3 bugs in arena/death/fight code (arena exit, death inventory handling)
- All `for(;;)` random-vnum loops bounded to max 200 attempts (prevents game freeze)

---

### Changed — Build System & Infrastructure

- **`src/act_wiz.c`**: `fgets()` magic number `80` replaced with `sizeof(arg)` for maintainability
- **`webadmin/server.py`**: Added `WEB_ADMIN_TOKEN` environment variable; mutating API endpoints now require `X-Admin-Token` header when token is set
- **`area/resolve.c`**: Moved to `archive/resolve.c` — dead code (legacy ident resolver, not compiled)
- **`webadmin/server.py`**: Removed duplicate import block (lines 13–24 were identical to lines 1–12)
- **`src/act_info.c`**: Two remaining `strcat()` calls converted to `strlcat()` with `sizeof(buf)` bounds

---

## [2025.11 (November 2025)] — String Safety & Infrastructure Overhaul

### Added — String Safety Infrastructure (PRs #11–27)

A comprehensive string safety refactor replacing all unbounded string functions (`strcpy`, `strcat`, `sprintf`) with bounded equivalents throughout the codebase:

- **`src/string_safe.c`**: New module providing OpenBSD-style `strlcpy()` and `strlcat()` implementations with guaranteed null-termination
- **`src/merc.h`**: Added `strlcpy`/`strlcat` prototypes; `UNUSED_PARAM(x)` macro for clean unused-parameter suppression; `#ifndef __APPLE__` guards for `<crypt.h>` include; modernized `bool` and integer types

**Modules converted (PR by PR):**
- `src/act_comm.c` — All `sprintf`/`strcpy`/`strcat` → `safe_strcpy`/`safe_strcat` wrappers
- `src/act_wiz.c` — Fully converted to `snprintf`/`strlcpy`/`strlcat`; `clamp_sh_int` helper for wizard-set commands
- `src/comm.c` — `safe_strcpy`/`safe_strcat` throughout; port validation before `htons`; widened descriptor handles to `int`
- `src/handler.c` — Flag/bit-name builders from repeated `strcat` → bounded `strlcat`
- `src/wizlist.c` — Formatting converted to `snprintf`
- `src/magic.c` — Fully converted; cleaned signed/unsigned comparisons; `spell_heat_metal` reorganized
- `src/act_obj.c` — `snprintf` for all formatted messages
- `src/db.c` — Area file names, socials, default room text, bug logging bounded; `fread_sh_int`/clamp helpers added
- `src/save.c` — No unsafe functions detected in audit
- `src/hunt.c` — Bounded buffer for secret-door door commands
- `src/magic2.c` — `do_lore` flow tidied; trap direction/keyword formatting capped; damage table bounds aligned
- `src/skills.c`, `src/special.c`, `src/update.c`, `src/quest.c`, `src/pkill.c` — All converted

### Added — Modern Build Systems

- **`CMakeLists.txt`** (PR #4–7): CMake build system targeting C17 standard with:
  - Explicit source file list (reproducible builds)
  - Optional AddressSanitizer + UBSanitizer via `-DENABLE_SANITIZERS=ON`
  - Output to `bin/rom` (separate from Makefile's `merc`)
  - clang-format configuration (`.clang-format`)

- **`Dockerfile`** (PR #8): Multi-stage Docker build:
  - Build stage: `debian:bookworm-slim` + build-essential + cmake
  - Runtime stage: minimal with only `libcrypt1` + Python 3 + FastAPI/uvicorn
  - Non-root `toc` user for container security
  - `EXPOSE 9000`

- **`docker-compose.yml`** (PR #3): Multi-service orchestration:
  - `game` service: MUD server on 9000/9001
  - `middleware` service: Python bridge on 8000
  - Volume mounts for `player/`, `log/`, `area/`

### Added — Network & Socket Modernization (PR #10)

- Socket handling in `src/comm.c` modernized to use POSIX-standard APIs
- `O_NONBLOCK` set via `fcntl` (replacing deprecated flags)
- `socklen_t` used consistently for address length parameters

### Added — Web Admin

- **`webadmin/server.py`**: FastAPI web administration panel:
  - `QueueWriter` class for IPC to game via `area/webadmin.queue`
  - Dashboard HTML (self-contained, no external CDN dependencies)
  - WebSocket `/ws/logs` for real-time log streaming
  - `/api/health` — checks merc and uvicorn process status
  - Player browser, area browser (mobs/objects/rooms), best gear finder
  - `docker-entrypoint.sh` starts uvicorn automatically

### Added — Setup Scripts

- `scripts/setup_windows.ps1` — Chocolatey-based Git + Docker Desktop installer
- `scripts/setup_mac.sh` — Homebrew-based installer (Intel + Apple Silicon aware)
- `scripts/setup_linux.sh` — apt-based Docker + git installer

### Fixed — Compiler Warnings

Extended warning set (`-Wall -Wextra -Wshadow -Wsign-compare -Wformat-overflow=2 -Wunused-parameter -Wstrict-prototypes -Wold-style-definition -Wmissing-prototypes -Wcast-qual`) builds cleanly:

- `UNUSED_PARAM` macro applied across all command/spell stubs
- Renamed shadowing locals in `act_wiz.c`, `comm.c`, `db.c`, `magic.c`, `save.c`, `special.c`, `update.c`
- `int_app` fixed: both `learn` and `mana_gain` fields now initialized
- `race_type` sentinel fills every field
- `hunt_victim` uses bounded buffer
- `act_new`/`act_public` const-correct; `is_name` works on local copies
- `-Wconversion` hotspots: `sh_int` clamping in `act_comm.c`, `act_info.c`, `act_move.c`, `act_obj.c`, `act_wiz.c`, `comm.c`, `db.c`, `fight.c`, `handler.c`

---

## [Initial] — 2025-11-18 (Initial Commit)

- Initial repository created from legacy ToC codebase
- 132 area files loaded and compiling
- Basic Makefile with gnu89 build flags
- Existing MUD engine code (Merc/ROM derivative with ToC customizations)

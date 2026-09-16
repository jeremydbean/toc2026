# Raspberry Pi appliance runbook

This deployment runs the native game and single-worker web dashboard under
systemd. The game listens on the LAN on TCP 9000. The dedicated LAN appliance
profile in `deploy/pi.env.example` also publishes the browser client and admin
dashboard on TCP 9001. Keep the Pi on a trusted private network and do not
forward TCP 9001 from the router.

Both pages are served by `toc2026-web.service`; there are no separate browser
processes to launch on the headless Pi. Enabling that service makes the client
and dashboard available automatically after every boot.

## Status

```bash
ssh toc
systemctl status toc2026-game toc2026-web
systemctl status toc2026-player-backup.timer toc2026-update.timer \
  toc2026-namecheap-ddns.timer
systemctl status toc2026-led.service toc2026-stable.service
curl http://127.0.0.1:9001/api/health
```

After unlocking the dashboard, **Host status** provides the same appliance
overview without a shell: game/web/recovery/update/backup/DDNS/LED service
state, scheduled timers, recent boot and shutdown ranges, root filesystem use,
memory/load/temperature, deployed Git state, and a bounded operational journal.
`WEB_ADMIN_HOST_STATUS=1` in the Pi profile enables the route. The web service
runs as `toc` with read-only `systemd-journal` group membership; it has no sudo
permission and cannot execute browser-supplied commands or read arbitrary root
paths.

## Logs

```bash
sudo journalctl -u toc2026-game -u toc2026-web -n 200 --no-pager
sudo journalctl -u toc2026-game -f
sudo journalctl -u toc2026-player-backup -n 100 --no-pager
sudo journalctl -u toc2026-update -n 100 --no-pager
sudo journalctl -u toc2026-namecheap-ddns -n 100 --no-pager
sudo journalctl -u toc2026-recovery -u toc2026-stable -n 100 --no-pager
```

## Restart

```bash
sudo systemctl restart toc2026-game toc2026-web
```

Stopping the game sends `SIGTERM`; the game saves connected players before
exiting. systemd starts it automatically after crashes and during every boot.
The MUD also sends a main-loop watchdog heartbeat; a process that freezes is
killed and restarted even if it still exists in the process table.

## ACT LED status

On a Raspberry Pi with `/sys/class/leds/ACT`, the onboard green ACT LED gives a
physical game-status signal. Three seconds on followed by one second off means
`toc2026-game.service` is healthy. A rapid 100 ms on/off blink means normal
systemd restarts did not restore it and host-level recovery is running or has
stopped for diagnosis. The LED turns off during an ordinary stop.

```bash
systemctl status toc2026-led.service
sudo /usr/local/sbin/toc2026-led status
```

This replaces the board's normal `actpwr` activity indication. Disable the
status light and return to the default trigger with:

```bash
sudo systemctl disable --now toc2026-led.service
echo actpwr | sudo tee /sys/class/leds/ACT/trigger
```

## Automatic failure recovery

The game service restarts a crash after 10 seconds and the 45-second main-loop
watchdog also recovers a frozen process. If the restarted service still cannot
become active, `toc2026-recovery.service` escalates in bounded stages:

1. On the first persistent failure, wait briefly for normal restart handling,
   then reboot the Pi.
2. If failure returns after that reboot, fetch `origin/main`, make an encrypted
   player backup, rebuild with one compiler process, validate, and redeploy. If
   it is still broken, reboot once more.
3. After the third persistent failure, retry the forced validated deployment,
   leave the Pi online with the rapid failure blink, and stop automatic reboots
   so the appliance cannot enter an endless boot loop or thrash the SD card.

After the MUD stays up for ten minutes, `toc2026-stable.service` clears the
persistent recovery count. Inspect the reason and recovery history with:

```bash
systemctl status toc2026-game toc2026-recovery toc2026-stable
sudo journalctl -u toc2026-game -u toc2026-recovery -u toc2026-update \
  -b --no-pager
sudo cat /var/lib/toc2026/recovery-count
```

The count file is absent during normal operation. A failed forced deployment
does not discard local runtime data or mark an unverified commit as deployed.

## Deploy an update

```bash
ssh toc
cd /home/toc/toc2026
./deploy/update-pi.sh
```

The same check runs automatically once per week on Sunday at about 4:00 AM in
the Pi's local time, with a randomized delay of up to 30 minutes. If the Pi is
off at that time, the persistent timer runs the missed check after the next
boot. It does nothing when the deployed commit already matches `origin/main`.
When an update exists, it first pushes an encrypted player snapshot, refuses to
discard non-runtime changes, fast-forwards, rebuilds with one compiler process,
validates the world, refreshes binary Python dependencies, then gracefully
restarts and health-checks both services. A failed build leaves the existing
processes running and is retried at the next scheduled or manually requested
run.

Automatic recovery can force this same guarded build even when Git is already
at the deployed commit, which covers a damaged binary or interrupted local
build without weakening the backup, fast-forward, dirty-tree, or validation
checks.

The protected Operations page also has an **Update ToC** button. It writes a
request under `/run`; a systemd path unit launches the same root-owned updater,
so the job continues while the dashboard restarts. Watch progress with:

```bash
sudo journalctl -u toc2026-update -f
```

## Browser client

On the same LAN, open:

- Browser client: `http://toc.local:9001/client`
- Admin dashboard: `http://toc.local:9001/`

Use the Pi's current IP address if mDNS is unavailable, for example
`http://192.168.1.235:9001/client`. The protected admin operations require the
`WEB_ADMIN_TOKEN` stored in the Pi's private `.env`.

In the dashboard, select **Host status** for read-only appliance telemetry.
Select **Operations** only when you intend to queue a state-changing game,
backup, reload, update, broadcast, or shutdown action.

Do not omit `:9001`: `http://192.168.1.235` uses port 80, where the appliance
does not run a web server.

### Admin token

The random token in `/home/toc/toc2026/.env` remains unchanged across service
restarts, reboots, Git updates, and rebuilds. It changes only when an operator
rotates it or replaces the private `.env`. On a Mac, copy it directly from the
Pi to the clipboard without printing it:

```bash
ssh toc "sed -n 's/^WEB_ADMIN_TOKEN=//p' /home/toc/toc2026/.env" | pbcopy
```

Paste it into **Admin token** and enable **Remember on this browser** to retain
it in that browser profile. Clearing browser storage, selecting **Lock**, or
rotating the server token requires entering it again. Direct LAN access uses
`WEB_ADMIN_LOCAL_UNLOCK=0`; only loopback deployments may auto-unlock.

An SSH tunnel remains available when direct LAN access is disabled:

```bash
ssh -L 9001:127.0.0.1:9001 toc
```

Then open `http://127.0.0.1:9001/client`. A MUD client can connect directly to
`toc.local:9000` or the Pi's current LAN address on port 9000.

## Public hostname

`toc2026-namecheap-ddns.timer` refreshes `toc.jeremybean.com` through
Namecheap shortly after boot and approximately every ten minutes. It asks
Namecheap for the Pi's public IPv4 address and verifies Namecheap's XML success
response. The small one-shot service uses a dynamic system user, a 32 MiB memory
limit, and no resident daemon.

Namecheap must use BasicDNS, PremiumDNS, or FreeDNS; Dynamic DNS must be enabled
for `jeremybean.com`; and host `toc` must be an **A + Dynamic DNS Record**. Copy
`deploy/namecheap-ddns.env.example` to the Pi without placing the real password
in Git:

```bash
sudo install -m 0600 deploy/namecheap-ddns.env.example \
  /etc/toc2026/namecheap-ddns.env
sudoedit /etc/toc2026/namecheap-ddns.env
sudo systemctl enable --now toc2026-namecheap-ddns.timer
sudo systemctl start toc2026-namecheap-ddns.service
```

Use the domain's Dynamic DNS password, not the Namecheap account password.
Confirm the last result without exposing the credential:

```bash
sudo systemctl status toc2026-namecheap-ddns.service
sudo journalctl -u toc2026-namecheap-ddns -n 20 --no-pager
getent ahostsv4 toc.jeremybean.com
```

DDNS changes only the public DNS record. Internet players still need router/NAT
forwarding for TCP 9000 to this Pi and a public IPv4 address not blocked by
carrier-grade NAT. Never forward the admin/dashboard port 9001.

## Player backups

The timer creates an encrypted player snapshot approximately every six hours
and force-refreshes the dedicated GitHub backup branch. View the next run with:

```bash
systemctl list-timers toc2026-player-backup.timer
```

The age recovery key is stored off the Pi. To restore after installing `age`:

```bash
age --decrypt -i /path/to/recovery-key \
  player-latest.tar.gz.age | tar -xzf -
```

Never commit the recovery key, `.env`, or a decrypted player archive.

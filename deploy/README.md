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
systemctl status toc2026-player-backup.timer toc2026-update.timer
curl http://127.0.0.1:9001/api/health
```

## Logs

```bash
sudo journalctl -u toc2026-game -u toc2026-web -n 200 --no-pager
sudo journalctl -u toc2026-game -f
sudo journalctl -u toc2026-player-backup -n 100 --no-pager
sudo journalctl -u toc2026-update -n 100 --no-pager
```

## Restart

```bash
sudo systemctl restart toc2026-game toc2026-web
```

Stopping the game sends `SIGTERM`; the game saves connected players before
exiting. systemd starts it automatically after crashes and during every boot.

## Deploy an update

```bash
ssh toc
cd /home/toc/toc2026
./deploy/update-pi.sh
```

The same check runs automatically about once per hour, with a randomized delay.
It does nothing when the deployed commit already matches `origin/main`. When an
update exists, it first pushes an encrypted player snapshot, refuses to discard
non-runtime changes, fast-forwards, rebuilds with one compiler process,
validates the world, refreshes binary Python dependencies, then gracefully
restarts and health-checks both services. A failed build leaves the existing
processes running and is retried later.

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

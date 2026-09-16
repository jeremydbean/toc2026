# Raspberry Pi appliance runbook

This deployment runs the native game and single-worker web dashboard under
systemd. The game listens on the LAN on TCP 9000. The dashboard remains on
Pi loopback TCP 9001 and is reached through an SSH tunnel.

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

From another computer, open a tunnel:

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

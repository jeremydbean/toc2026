#!/bin/sh
set -eu

sudo systemctl start toc2026-update.service
sudo systemctl status toc2026-update.service --no-pager
sudo journalctl -u toc2026-update.service -n 100 --no-pager

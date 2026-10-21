# Times of Chaos: the game and its web client/dashboard in one image.
#
# Ubuntu 24.04 is what the production host runs, so the image builds the
# game against the same compiler and libraries players already depend on.
# Prebuilt images for amd64 and arm64 are published to
# ghcr.io/jeremydbean/toc2026 by .github/workflows/docker-image.yml; the
# installers pull one and fall back to building this file.

ARG BASE_IMAGE=ubuntu:24.04

# ---- the game -------------------------------------------------------------
FROM ${BASE_IMAGE} AS build

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    build-essential \
    libcrypt-dev \
    zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY . .

# Runtime state is excluded from the build context (.dockerignore), so no
# player file, log or report can be baked into an image. The world is
# loaded once here: an image whose areas do not boot is never produced.
RUN make -j"$(nproc)" \
 && mkdir -p log player gods heroes corpse backups \
 && cd area && ../merc --check-area

# ---- the dashboard's Python, kept out of the runtime image's pip -----------
FROM ${BASE_IMAGE} AS python

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv \
 && rm -rf /var/lib/apt/lists/*
COPY webadmin/requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv \
 && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

# ---- runtime --------------------------------------------------------------
FROM ${BASE_IMAGE} AS runtime

ARG TOC_VERSION=dev
LABEL org.opencontainers.image.title="Times of Chaos" \
      org.opencontainers.image.description="Times of Chaos ROM MUD with its web client and dashboard" \
      org.opencontainers.image.source="https://github.com/jeremydbean/toc2026" \
      org.opencontainers.image.licenses="NOASSERTION" \
      org.opencontainers.image.revision="${TOC_VERSION}"

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    ca-certificates \
    gosu \
    libcrypt1 \
    python3 \
    rsync \
    zlib1g \
 && rm -rf /var/lib/apt/lists/*

COPY --from=python /opt/venv /opt/venv
COPY --from=build /src/merc /usr/local/bin/merc
# The world as shipped. The entrypoint brings the live world in /app/area
# (a volume) up to date from this on every start, keeping what the game
# wrote there -- notes, reports, max-load counts, builders' areas.
COPY --from=build /src/area /app/dist/area
COPY --from=build /src/webadmin /app/webadmin
COPY scripts/toc_sync_area.sh /usr/local/bin/toc-sync-area
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh /usr/local/bin/toc-sync-area \
 && chmod +x /usr/local/bin/docker-entrypoint.sh /usr/local/bin/toc-sync-area \
 && rm -f /app/dist/area/shutdown.txt /app/dist/area/webadmin.queue \
 && (getent passwd 1000 >/dev/null && userdel -r "$(getent passwd 1000 | cut -d: -f1)" || true) \
 && groupadd --system toc \
 && useradd --system --gid toc --home-dir /app --no-create-home toc \
 && mkdir -p /app/area /app/player /app/gods /app/heroes /app/corpse /app/log /app/backups \
 && chown -R toc:toc /app

ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PORT=9000 \
    TOC_VERSION=${TOC_VERSION}

WORKDIR /app/area
EXPOSE 9000 9001
VOLUME ["/app/area", "/app/player", "/app/gods", "/app/heroes", "/app/corpse", "/app/log", "/app/backups"]

# The entrypoint starts as root only long enough to give the toc account
# the host's user and group IDs for bind-mounted state, then drops to it.
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD []

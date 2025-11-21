# Multi-stage build for the ToC MUD server
FROM debian:bookworm-slim AS build

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN make

FROM debian:bookworm-slim AS runtime

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    libcrypt1 \
    python3 \
    python3-pip \
    valgrind \
 && rm -rf /var/lib/apt/lists/*

ENV PIP_BREAK_SYSTEM_PACKAGES=1
RUN pip install --no-cache-dir fastapi "uvicorn[standard]"

WORKDIR /app/area

COPY --from=build /app/merc /usr/local/bin/merc
COPY --from=build /app/area /app/area
COPY --from=build /app/gods /app/gods
COPY --from=build /app/heroes /app/heroes
COPY --from=build /app/log /app/log
COPY --from=build /app/player /app/player
COPY --from=build /app/webadmin /app/webadmin
COPY --from=build /app/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
 && chmod +x /usr/local/bin/docker-entrypoint.sh

RUN addgroup --system toc \
 && adduser --system --ingroup toc --home /app toc \
 && chown -R toc:toc /app

USER toc

EXPOSE 9000
ENV PORT=9000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD []

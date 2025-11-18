# Multi-stage build for the ToC MUD server
FROM ubuntu:24.04 AS build
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential make \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN make \
 && cp merc area/merc

FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app/area
RUN apt-get update \
 && apt-get install -y --no-install-recommends libcrypt1 python3 python3-pip \
 && rm -rf /var/lib/apt/lists/*

ENV PIP_BREAK_SYSTEM_PACKAGES=1
RUN pip install --no-cache-dir fastapi "uvicorn[standard]"

COPY --from=build /app /app
COPY --from=build /app/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 9000
ENV PORT=9000
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD []

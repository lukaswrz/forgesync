FROM docker.io/alpine:latest

ENV SOURCE_TOKEN=
ENV TARGET_TOKEN=
ENV MIRROR_TOKEN=

RUN apk add uv
RUN mkdir -p /usr/src

WORKDIR /usr/src
COPY . .

RUN uv sync --compile-bytecode
RUN echo -e '#!/bin/sh\n\nuv run --no-sync --directory /usr/src forgesync "$@"' > /usr/bin/forgesync && chmod +x /usr/bin/forgesync

ENTRYPOINT ["/usr/bin/forgesync"]

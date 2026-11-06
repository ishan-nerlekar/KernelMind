ARG BASE_IMAGE=golang:1.24-bookworm
FROM ${BASE_IMAGE}
ENV GOTOOLCHAIN=local GOFLAGS=-mod=mod CGO_ENABLED=1
WORKDIR /app
COPY app/ /app/
# One timestamp for every file, so modification times don't reveal which files the task changed.
RUN find /app -exec touch -h -d @1746700000 {} +
COPY history.bundle /tmp/history.bundle
RUN git init -q -b main && git fetch -q --update-head-ok /tmp/history.bundle 'refs/heads/*:refs/heads/*' 'refs/tags/*:refs/tags/*' \
    && git reset -q && { [ ! -d debug ] || echo 'debug/' > .git/info/exclude; } && rm /tmp/history.bundle
# Warm the build cache so neither the agent nor the verifier pays for a cold compile.
RUN go build ./... && go test -count=1  -run '^$' ./... > /dev/null
# A single baseline commit lets the harness record the agent's diff. Tasks with [[history]] ship
# their own repository instead.
RUN [ -d .git ] || (git init -q && git add -A && git -c user.email=kernelmind@local -c user.name=kernelmind commit -qm baseline)

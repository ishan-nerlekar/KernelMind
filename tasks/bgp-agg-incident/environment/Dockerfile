ARG BASE_IMAGE=golang:1.24-bookworm
FROM ${BASE_IMAGE}
ENV GOTOOLCHAIN=local GOFLAGS=-mod=mod CGO_ENABLED=1
WORKDIR /app
COPY app/go.mod app/go.sum /app/
RUN go mod download
COPY app/ /app/
# One timestamp for every file, so modification times don't reveal which files the task changed.
RUN find /app -exec touch -h -d @1746700000 {} +
# Warm the build cache so neither the agent nor the verifier pays for a cold compile.
RUN go build ./... && go test -count=1  -run '^$' ./internal/pkg/table/... ./pkg/packet/... ./pkg/apiutil/... ./pkg/zebra/... ./cmd/gobgp/... ./pkg/config/oc/... > /dev/null
# A single baseline commit lets the harness record the agent's diff. No project history is included.
RUN git init -q && git add -A && git -c user.email=kernelmind@local -c user.name=kernelmind commit -qm baseline

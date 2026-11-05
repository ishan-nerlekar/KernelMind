ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}
RUN command -v git >/dev/null || (apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*)
WORKDIR /app
COPY app/ /app/
# A single baseline commit lets the harness record the agent's diff. No project history is included.
RUN git init -q && git add -A && git -c user.email=kernelmind@local -c user.name=kernelmind commit -qm baseline

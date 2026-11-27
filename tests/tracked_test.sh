#!/usr/bin/env bash
# PDF tracked-change detection needs pdfplumber, which has no Debian package: runs tests/score_tracked.py in the chat-env-v2 image
# (built when missing). Usage, from the repo root: bash tests/tracked_test.sh OUTDIR
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$(mkdir -p "$1" && cd "$1" && pwd)"
docker image inspect rule-check:chat-env-v2 >/dev/null 2>&1 \
  || docker build -q -f "$REPO/dev/docker/chat-env-v2.Dockerfile" -t rule-check:chat-env-v2 "$REPO/dev/docker" >/dev/null
docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges --read-only --tmpfs /tmp --user "$(id -u):$(id -g)" \
  -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1 -v "$REPO":/skill:ro,z -v "$OUT":/work:z -w /work rule-check:chat-env-v2 \
  python3 /skill/tests/score_tracked.py /work/run

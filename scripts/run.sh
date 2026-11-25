#!/usr/bin/env bash
# Runs every skill script inside Docker (nothing is installed on the host).
# Usage: run.sh python3 /skill/scripts/extract.py document.pdf -o out/
#        run.sh pdftotext -v
# The current directory is mounted as /work; the skill directory as /skill (read-only).
# RULE_CHECK_TARGET=test uses the image that also has the fixture-generation libraries (tests only).
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${RULE_CHECK_TARGET:-base}"
IMG="rule-check:$([ "$TARGET" = base ] && echo local || echo "$TARGET")"
# The image is rebuilt automatically when docker/ changes (label = hash of the build inputs).
WANT="$(cat "$SKILL_DIR"/docker/Dockerfile | sha256sum | cut -c1-16)"
HAVE="$(docker image inspect "$IMG" --format '{{ index .Config.Labels "docker.sha" }}' 2>/dev/null || true)"
if [ "$WANT" != "$HAVE" ]; then
  docker build --target "$TARGET" --label "docker.sha=$WANT" -t "$IMG" "$SKILL_DIR/docker" >&2
fi
# Hardening: documents are untrusted input to PDF parsers, so no network, no capabilities, read-only root fs.
# :z (lowercase) = shared SELinux label (Fedora); do not use :Z, it would lock your home directory.
exec docker run --rm --network none --cap-drop ALL --security-opt no-new-privileges --read-only --tmpfs /tmp \
  --user "$(id -u):$(id -g)" -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$SKILL_DIR":/skill:ro,z -v "$PWD":/work:z -w /work "$IMG" "$@"

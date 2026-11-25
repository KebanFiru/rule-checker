# Mimics the chat/sandbox environment: NO Docker wrapper, scripts are called directly with `python3 scripts/x.py`.
# Contains ONLY: python3, pypdf, PyYAML, poppler-utils (no python-is-python3, no fonts, no test libraries).
FROM debian:trixie-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pypdf python3-yaml poppler-utils \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work

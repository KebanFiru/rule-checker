# Closer replica of the Claude chat sandbox (measured: Python 3.13.18, pypdf 6.17.0, PyYAML 6.0.3, pdfplumber 0.11.10,
# poppler 24.02.0, LibreOffice present). NO Docker wrapper inside: scripts are called as `python3 scripts/x.py`.
# Ubuntu 24.04 gives poppler-utils 24.02; Python 3.13 comes from uv's managed builds; the packages live in a venv.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates poppler-utils fonts-dejavu-core \
    && (apt-get install -y --no-install-recommends libreoffice-writer-nogui \
        || apt-get install -y --no-install-recommends libreoffice-writer) \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_LINK_MODE=copy UV_CACHE_DIR=/tmp/uv-cache
RUN uv python install 3.13 \
    && uv venv --python 3.13 /opt/venv \
    && uv pip install --python /opt/venv/bin/python pypdf==6.17.0 pyyaml==6.0.3 pdfplumber==0.11.10 \
    && rm -rf /tmp/uv-cache
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /work

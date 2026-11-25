# No PyPI packages at all: everything comes from Debian packages (security-patched by Debian).
#   runtime: python3 + PyYAML (python3-yaml) + pypdf (python3-pypdf) + poppler-utils (only pdftotext is used) + DejaVu fonts
#   test:    + Pillow and ReportLab (only to generate the synthetic fixtures)
FROM debian:trixie-slim AS base
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python-is-python3 python3-yaml python3-pypdf poppler-utils fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work

FROM base AS test
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-pil python3-reportlab \
    && rm -rf /var/lib/apt/lists/*

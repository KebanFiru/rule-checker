# Third-party software

This repository's own code is MIT-licensed (see `LICENSE`). It vendors no third-party code and uses **no PyPI packages**:
the scripts need only the Python standard library plus PyYAML (process-model files), pypdf (pure-Python PDF engine) and the
poppler `pdftotext` command, all installed from Debian packages when the Docker image is built (`docker/Dockerfile`). Licenses are as published
by Debian/upstream at the time of writing; verify before redistributing an image.

| Component | Used for | License | Where |
|---|---|---|---|
| Python 3 (Debian 13 `python3`) | interpreter, standard library (zipfile/ElementTree read DOCX) | PSF-2.0 | runtime image |
| PyYAML (`python3-yaml`) | process model / invariants files | MIT | runtime image |
| pypdf (`python3-pypdf` 5.4.0) | pure-Python PDF text extraction (`--engine pypdf`, also the independent second opinion) | BSD-3-Clause | runtime image |
| poppler-utils (only `pdftotext` is used) | PDF text extraction, run as a **separate process** (not needed for DOCX/TXT input) | GPL-2.0 or GPL-3.0 | runtime image |
| fonts-dejavu-core | fonts for the generated test PDFs/images | Bitstream Vera / DejaVu free license | runtime image |
| Debian 13 `debian:trixie-slim` | base image | various (Debian) | base image |
| Pillow (`python3-pil`) | generates the test screenshots | HPND (MIT-CMU) | test image only |
| pdfplumber 0.11.10 | optional `--tables` (cell-level PDF tables) | MIT | `chat-env-v2` image only; the default image does not install it (the feature falls back to `-layout` rows) |
| pdfminer.six 20260107 | pdfplumber dependency | MIT | `chat-env-v2` image only |
| pypdfium2 5.15.2 | pdfplumber dependency (native PDFium) | BSD-3-Clause, Apache-2.0 (+ bundled dependency licenses) | `chat-env-v2` image only |
| Pillow 13.0.0, charset-normalizer 3.5.3, cryptography 50.0.2, cffi 2.1.1, pycparser 3.12 | pdfplumber/pdfminer dependencies | MIT-CMU; MIT; Apache-2.0 OR BSD-3-Clause; MIT-0; BSD-3-Clause | `chat-env-v2` image only |
| LibreOffice Writer (`libreoffice-writer-nogui` 24.2.7, Ubuntu 24.04) | optional DOCX→PDF conversion (`docx_to_pdf.py`), run as a separate process | MPL-2.0 (some Apache-2.0 material) | `chat-env-v2` image only |
| uv / CPython 3.13.18 (uv-managed) | builds the chat-environment replica | MIT or Apache-2.0 (uv) / PSF-2.0 (CPython) | `chat-env-v2` image only |
| ReportLab (`python3-reportlab`) | generates the test PDFs | BSD-3-Clause | test image only |

## Notes
- The licenses of the optional/pdfplumber packages above were read from the package metadata (`importlib.metadata`) inside the `chat-env-v2` image, not copied from memory; LibreOffice's from its Debian copyright file.
- `chat-env-v2` is a test replica of the Claude chat sandbox; the default image (`docker/Dockerfile`) does not contain pdfplumber, LibreOffice or any PyPI package.
- poppler is GPL, but the scripts call it only through the command line (`subprocess`), so it does not affect the MIT
  license of this repository. If you redistribute a Docker image built from this repo, the image contains GPL software
  (poppler) and you must comply with the GPL for that part (Debian provides the corresponding source).

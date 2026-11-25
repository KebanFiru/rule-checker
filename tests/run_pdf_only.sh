#!/usr/bin/env bash
# Reads every PDF in PDFDIR with every engine/mode combination and runs id_index + xref_check on the result.
# Used to show that PDFs produced elsewhere (LibreOffice) give the same findings in different environments.
# Usage: run_pdf_only.sh PDFDIR OUTDIR
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; IN="$(cd "$1" && pwd)"; OUT="$(mkdir -p "$2" && cd "$2" && pwd)"; cd "$OUT"
for pdf in "$IN"/*.pdf; do stem="$(basename "$pdf" .pdf)"
  for eng in pdftotext pypdf; do for mode in layout reading; do
    ro=(); [ "$mode" = reading ] && ro=(--reading-order); d="${eng}_${mode}"
    python3 "$REPO/scripts/extract.py" "$pdf" --engine "$eng" "${ro[@]}" -o "ex/$d" >/dev/null
    mkdir -p "res/$d"
    python3 "$REPO/scripts/id_index.py" "ex/$d/$stem.txt" -o "res/$d/${stem}_id_index.json" >/dev/null
    python3 "$REPO/scripts/xref_check.py" "ex/$d/$stem.txt" --numbers -o "res/$d/${stem}_xref.md" >/dev/null
  done; done
done
echo "read $(ls "$IN"/*.pdf | wc -l) PDF(s) x 4 engine/mode combinations"
[ -f "$IN/stress.pdf" ] && python3 "$REPO/tests/check_stress_ligatures.py" ex/pdftotext_layout ex/pypdf_layout ex/pdftotext_reading ex/pypdf_reading | sed 's/^/  /'

#!/usr/bin/env bash
# Host-side driver (only Docker commands run on the host). Builds the two chat-environment images, runs both scenarios in each
# with each primary PDF engine by calling `python3 scripts/x.py` directly (tests/run_deterministic.sh), then prints a version
# table, the scorer results, and a classified comparison. Run from the repo root: bash tests/chat_env_test.sh
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO"
OUT=tests/_out; rm -rf "$OUT"; mkdir -p "$OUT"
IMAGES=(chat-env chat-env-v2); ENGINES=(pdftotext pypdf)
for i in "${IMAGES[@]}"; do
  f="docker/$i.Dockerfile"; [ "$i" = chat-env ] && f="docker/chat-env.Dockerfile"
  docker image inspect "rule-check:$i" >/dev/null 2>&1 || docker build -q -f "$f" -t "rule-check:$i" docker >/dev/null || exit 1
done
FLAGS="--rm --network none --cap-drop ALL --security-opt no-new-privileges --read-only --tmpfs /tmp --user $(id -u):$(id -g) -e HOME=/tmp -e PYTHONDONTWRITEBYTECODE=1"
echo "== version table (target = measured in the Claude chat sandbox) =="
printf '%-12s %-12s %-14s %-14s\n' component target chat-env chat-env-v2
envj() { docker run --rm --network none -v "$REPO":/skill:ro,z "rule-check:$1" python3 /skill/scripts/env_check.py --json /tmp/e.json >/dev/null && docker run --rm --network none -v "$REPO":/skill:ro,z "rule-check:$1" sh -c "python3 /skill/scripts/env_check.py --json /tmp/e.json >/dev/null; python3 -c \"import json;e=json.load(open('/tmp/e.json'));L=e['libraries'];T=e['tools'];print('|'.join([e['python'],L['pypdf'] or '-',L['PyYAML'] or '-',L['pdfplumber'] or '-',(T['pdftotext']['version'] or '-').split()[-1],(T['soffice']['version'] or '-')]))\""; }
A=$(envj chat-env); B=$(envj chat-env-v2); IFS='|' read -r -a a <<<"$A"; IFS='|' read -r -a b <<<"$B"
t=(3.13.18 6.17.0 6.0.3 0.11.10 24.02.0 present); n=(python pypdf PyYAML pdfplumber poppler LibreOffice)
for k in 0 1 2 3 4 5; do printf '%-12s %-12s %-14s %-14s\n' "${n[$k]}" "${t[$k]}" "${a[$k]:0:14}" "${b[$k]:0:14}"; done
echo; echo "== runs (scripts called directly with python3, hardened container, no network) =="
for i in "${IMAGES[@]}"; do for e in "${ENGINES[@]}"; do
  d="$OUT/${i}_$e"; mkdir -p "$d"
  docker run $FLAGS -e ENGINE=$e -v "$REPO":/skill:ro,z -v "$REPO/$d":/work:z -w /work "rule-check:$i" bash /skill/tests/run_deterministic.sh /work > "$d.log" 2>&1
  printf '%-22s exit=%s  scenario summaries FULL: %s/2  ✗ lines: %s  DOCX visual: %s\n' "$i/$e" $? "$(grep -c 'SUMMARY: FULL' "$d.log")" "$(grep -c '✗' "$d.log")" "$(grep -E 'Visual pass: DOCX|visual pass skipped' "$d.log" | head -1 | cut -c1-70)"
done; done
cmp() { echo; echo "== $1 vs $2 =="; python3 tests/compare_runs.py "$OUT/$1" "$OUT/$2" --log-a "$OUT/$1.log" --log-b "$OUT/$2.log"; }
cmp chat-env_pdftotext chat-env-v2_pdftotext
cmp chat-env_pypdf chat-env-v2_pypdf
cmp chat-env-v2_pdftotext chat-env-v2_pypdf
echo; echo "== LibreOffice-made PDFs (built in v2) read by BOTH images: 2 PDFs x 2 engines x 2 modes, plus id_index/xref_check =="
mkdir -p "$OUT/lo_pdfs"; cp "$OUT/chat-env-v2_pdftotext/s1docx/pdf/target_srs.pdf" "$OUT/chat-env-v2_pdftotext/s1docx/stress/pdf/stress.pdf" "$OUT/lo_pdfs/" 2>/dev/null
for i in "${IMAGES[@]}"; do mkdir -p "$OUT/lo_$i"
  docker run $FLAGS -v "$REPO":/skill:ro,z -v "$REPO/$OUT":/work:z -w /work "rule-check:$i" bash /skill/tests/run_pdf_only.sh /work/lo_pdfs /work/lo_$i | sed "s/^/  $i: /"; done
python3 tests/compare_runs.py "$OUT/lo_chat-env" "$OUT/lo_chat-env-v2"
echo; echo "== engine-disagreement warnings (PDFs with a second opinion) =="
python3 - <<'PY'
import sys; sys.path.insert(0, "tests")
from compare_runs import engine_warnings
import pathlib
for d in sorted(pathlib.Path("tests/_out").iterdir()):
    if d.is_dir() and not d.name.startswith("lo_pdfs"):
        n, k = engine_warnings(d); print(f"  {d.name:24s} PDFs checked: {n:2d}  disagreement warnings: {k}")
PY

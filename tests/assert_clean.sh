#!/usr/bin/env bash
# Fails (exit 1) if a run log shows any failure marker or fewer than the expected number of FULL scenario summaries.
# Usage: assert_clean.sh LOG [EXPECTED_FULL=4]
log="$1"; want="${2:-4}"; rc=0
for pat in '✗' '^FAIL' 'SUMMARY: GAPS' 'Traceback' 'VERIFICATION FAILED' 'ATTENTION'; do
  if grep -q -- "$pat" "$log"; then echo "assert_clean: found '$pat' in $log"; grep -n -- "$pat" "$log" | head -5; rc=1; fi
done
n=$(grep -c 'SUMMARY: FULL' "$log")
[ "$n" -ge "$want" ] || { echo "assert_clean: only $n FULL scenario summaries in $log (expected $want)"; rc=1; }
[ $rc -eq 0 ] && echo "assert_clean: OK ($n FULL summaries, no failure markers) — $log"
exit $rc

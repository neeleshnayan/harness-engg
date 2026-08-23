#!/usr/bin/env bash
# Run the FULL suite the moment the belt lock clears and RAM allows.
# Capped per the chair's dispatch notice: do not wait more than ~28 minutes,
# then report the suite OWED rather than blocking the bundle.
CH="C:/Users/user/Documents/Krypton Fund/ClarkHarness"
WT="C:/Users/user/AppData/Local/Temp/claude/C--Users-user-Documents-Krypton-Fund/bbc88cbf-5b81-4236-8781-b009121ec21f/scratchpad/d23"
PY="C:/Users/user/Documents/Krypton Fund/ClarkHarness/venv/Scripts/python.exe"
RAM="C:/Users/user/AppData/Local/Temp/claude/C--Users-user-Documents-Krypton-Fund/bbc88cbf-5b81-4236-8781-b009121ec21f/scratchpad/adv23/ram.ps1"
OUT="C:/Users/user/AppData/Local/Temp/claude/C--Users-user-Documents-Krypton-Fund/bbc88cbf-5b81-4236-8781-b009121ec21f/scratchpad/d29/suite.txt"

for i in $(seq 1 28); do
  free=$(powershell -NoProfile -File "$RAM" | sed 's/ GB free.*//')
  if [ ! -e "$CH/.belt_running" ] && [ ! -e "$CH/.suite_running" ]; then
    ok=$(awk -v f="$free" 'BEGIN{print (f+0 >= 1.5) ? "yes" : "no"}')
    if [ "$ok" = "yes" ]; then
      echo "lock clear at attempt $i, ${free} GB free — taking .suite_running" > "$OUT"
      echo "d29 suite $(date -u +%FT%TZ)" > "$CH/.suite_running"
      cd "$WT" || exit 1
      PYTHONIOENCODING=utf-8 "$PY" -m pytest -q >> "$OUT" 2>&1
      rc=$?
      rm -f "$CH/.suite_running"
      echo "SUITE_RC=$rc" >> "$OUT"
      exit 0
    fi
    echo "attempt $i: lock clear but only ${free} GB free" >> "$OUT"
  else
    echo "attempt $i: belt lock still held (${free} GB free)" >> "$OUT"
  fi
  sleep 60
done
echo "TIMED OUT after 28 attempts — full suite OWED" >> "$OUT"
exit 3

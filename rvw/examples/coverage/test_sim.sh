#!/usr/bin/env bash
set -euo pipefail
bash "$SCRIPTS/create_mutated.sh" -o mutated.v
iverilog -g2012 -s tb -o sim mutated.v "$PRJDIR/tb.sv"
if vvp sim > sim.log 2>&1; then
  grep -q '^PASS$' sim.log
  echo '1 PASS' > output.txt
elif grep -q 'MISMATCH' sim.log; then
  echo '1 FAIL' > output.txt
else
  cat sim.log >&2
  exit 1
fi

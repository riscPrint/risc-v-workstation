#!/usr/bin/env bash
set -euo pipefail
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
iverilog -g2012 -s tb -o "$tmp/sim" tiny.sv tb.sv
vvp "$tmp/sim" | tee "$tmp/result"
grep -q '^PASS$' "$tmp/result"

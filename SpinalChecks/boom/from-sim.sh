#!/usr/bin/env bash
# BOOM: simulate with the checks (asserts + monitors, formal included) and a full-state FST, then start a
# bounded proof of the generated checks from cycle N of rv64ui-p-add. Takes the machine-wide boom lock.
#   SpinalChecks/boom/from-sim.sh [cycle] [depth] [outDir]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
cycle="${1:-1500}"; depth="${2:-4}"; out="${3:-out/fs-small}"
: "${ENV_SH:?Set ENV_SH to the BOOM environment setup script}"
[ -f "$ENV_SH" ] || { echo "ENV_SH is not a file: $ENV_SH" >&2; exit 2; }
source "$ENV_SH"
export SPINAL_MAKE_CMD="$here/../scripts/make-j4.sh"
tests="${RISCV_TESTS:-}"
if [ -z "${SKIP_SIM:-}" ]; then
  : "${RISCV_TESTS:?Set RISCV_TESTS to the built ISA test directory}"
  [ -d "$tests" ] || { echo "RISCV_TESTS is not a directory: $tests" >&2; exit 2; }
fi
bench="${BENCH_DIR:-$here/../../examples/boom/out/arch/bench}"   # built by `rvw arch build`
rvw="$here/../../rvw/.venv/bin/rvw"
cd "$here"
"$here/../../scripts/with-lock.sh" boom bash -c '
set -euo pipefail
out=$1; cycle=$2; depth=$3; engine=$4; timeout=$5; tests=$6; bench=$7; rvw=$8; here=$9
if [ -z "${SKIP_SIM:-}" ]; then
  # sbt parses its command string itself. Refuse paths that could alter that command.
  for path in "$out" "$tests" "$bench"; do
    [[ "$path" =~ ^[a-zA-Z0-9_./+@%,=:~-]+$ ]] || { echo "unsupported sbt path: $path" >&2; exit 2; }
  done
  "$here/../../scripts/with-lock.sh" sbt nice -n 10 sbt -J-Xmx8g -batch "run run small $out --formal --mode both --wave --locations --seed 1 --max-cycles 13500 $tests/rv64ui-p-add $bench/qsort.riscv"
fi
shopt -s nullglob
rtl=("$out"/sim/small_wave/rtl/*.v)
[ "${#rtl[@]}" -gt 0 ] || { echo "no replay RTL under $out" >&2; exit 2; }
wave=$(find "$out/sim/small_wave" -path "*rv64ui-p-add*" -name wave.fst -print -quit)
[ -n "$wave" ] || { echo "no replay waveform under $out" >&2; exit 2; }
ls -la "$wave"
/usr/bin/time -l "$rvw" formal from-sim --verilog "${rtl[@]}" --top BoomSimTop --trace "$wave" --cycle "$cycle" --depth "$depth" \
  --checks "$out/BoomSimTop.checks.json" --engine "$engine" --timeout "$timeout" \
  --tie io_mem_d_valid=0 --tie io_mem_b_valid=0 --tie io_interrupts_debug=0 --tie io_interrupts_mtip=0 \
  --tie io_interrupts_msip=0 --tie io_interrupts_meip=0 --tie io_interrupts_seip=0 \
  --out "$out/from-sim-c$cycle-d$depth"
' bash "$out" "$cycle" "$depth" "${ENGINE:-smtbmc:yices,smtbmc:bitwuzla}" "${TIMEOUT:-3600}" "$tests" "$bench" "$rvw" "$here"

#!/usr/bin/env bash
# BOOM with SpinalChecks (Monitor mode): build once, run rv64ui-p-* and a few benchmarks.
#   SpinalChecks/boom/run-suite.sh [preset] [outDir]      (takes the machine-wide boom lock)
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
preset="${1:-small}"; out="${2:-out/suite-$preset}"
: "${ENV_SH:?Set ENV_SH to the BOOM environment setup script}"
[ -f "$ENV_SH" ] || { echo "ENV_SH is not a file: $ENV_SH" >&2; exit 2; }
source "$ENV_SH"
export SPINAL_MAKE_CMD="$here/../scripts/make-j4.sh"
tests="${RISCV_TESTS:?Set RISCV_TESTS to the built ISA test directory}"
[ -d "$tests" ] || { echo "RISCV_TESTS is not a directory: $tests" >&2; exit 2; }
bench="${BENCH_DIR:-$here/../../examples/boom/out/arch/bench}"   # built by `rvw arch build`
elfs=$(ls "$tests"/rv64ui-p-* | grep -v '\.dump$')
for b in ${BENCHES:-median qsort towers dhrystone}; do elfs="$elfs $bench/$b.riscv"; done
cd "$here"
exec "$here/../../scripts/with-lock.sh" boom sbt -J-Xmx8g -batch \
  "run run $preset $out --locations --max-cycles 3000000 ${EXTRA:-} $(echo $elfs)"

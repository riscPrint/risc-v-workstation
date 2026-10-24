#!/usr/bin/env bash
# End-to-end demo of SpinalChecks and `rvw formal` on the small demo designs (no BOOM, no lock needed).
#   SpinalChecks/scripts/demo.sh            # everything, results under SpinalChecks/out/
# Needs: source spinal-boom/env.sh (JDK, Verilator, yosys, sby), rvw installed in rvw/.venv.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
cd "$here"
rvw="${RVW:-$here/../rvw/.venv/bin/rvw}"

echo "== 1. generated checks in simulation (Verilator, Monitor mode): each planted bug fires only its check"
sbt -J-Xmx4g -batch "testOnly spinalchecks.ChecksDemoSpec" | grep -E "^\[info\] -|Tests:"

echo "== 2. the same checks as SymbiYosys assertions: BMC from reset, one Verilog per planted bug"
args=()
for b in clean:none hold:hold stable:stable mem:mem vec:vec enum:enum hang:hang xvalid:xvalid; do
  args+=("runMain spinalchecks.demo.GenDemo verilog checks out/demo/${b%%:*} ${b#*:}")
done
sbt -J-Xmx4g -batch "${args[@]}" | grep -E "SpinalChecks:"
for v in clean hold stable mem vec enum hang; do
  echo "-- $v"
  "$rvw" formal bmc --verilog out/demo/$v/ChecksDemo.v --top ChecksDemo --checks out/demo/$v/ChecksDemo.checks.json \
    --depth 25 --out out/formal/bmc_$v | grep -v "trace:" || true
done

echo "== 3. X-propagation on stream/flow valid, ready and payload-while-valid (from the checks report)"
for v in clean xvalid; do
  echo "-- $v"
  "$rvw" formal xprop --verilog out/demo/$v/ChecksDemo.v --top ChecksDemo --checks out/demo/$v/ChecksDemo.checks.json \
    --outputs --payload --depth 12 --out out/formal/xprop_$v || true
done

echo "== 4. a bug 7700 cycles deep: random simulation misses it, BMC from reset cannot reach it,"
# (bitwuzla: ~40x faster than yices on this design; yices is faster on ChecksDemo. See README.)
echo "      BMC from the simulation state at cycle 7680 finds it"
sbt -J-Xmx4g -batch "runMain spinalchecks.demo.GenDemo sim-deep out/deep 9000 7" | grep -E "served|spinalchecks\]"
v=out/deep/sim/deep/rtl/DeepBugDemo.v
"$rvw" formal bmc --verilog $v --top DeepBugDemo --checks out/deep/DeepBugDemo.checks.json --depth 30 --engine smtbmc:bitwuzla \
  --out out/formal/deep_bmc_reset | grep -v "trace:" || true
"$rvw" formal from-sim --verilog $v --top DeepBugDemo --trace out/deep/sim/deep/test/wave.fst --cycle 7680 --depth 30 --engine smtbmc:bitwuzla \
  --checks out/deep/DeepBugDemo.checks.json --out out/formal/deep_from_sim || true
"$rvw" formal from-sim --verilog $v --top DeepBugDemo --trace out/deep/sim/deep/test/wave.fst --cycle 3000 --depth 30 --engine smtbmc:bitwuzla \
  --checks out/deep/DeepBugDemo.checks.json --out out/formal/deep_from_sim_3000 || true

# PicoRV32 architectural-state monitor

Use pinned PicoRV32 `ef203c2b0a3fb793280f5114941416c425c5b461` outside
this repository. Run these commands with the workstation environment loaded:

```sh
rvw/.venv/bin/python examples/picorv32/formal/prepare.py \
  --source "$PICORV32" --riscv-formal "$RISCV_FORMAL" --out "$CAPTURE"
rvw/.venv/bin/rvw formal state-generate "$CAPTURE/state-map.json" --out "$MONITOR"
rvw/.venv/bin/python examples/picorv32/formal/compare.py --capture "$CAPTURE"
```

`prepare.py` checks the revision and clean source. It captures the source and
adds retirement-aligned register snapshots. It does not edit PicoRV32. The map
uses the captured snapshots, instruction events and memory transactions. It
never maps native RVFI outputs back into the generated monitor. The example
uses RV32I, no IRQ, no compressed instructions, no PCPI and zero register reset
state. Native RVFI remains in the captured source for comparison only.
The generated monitor supports the core's active-low reset and halt output.

Run the comparison under a private lock and `nice -n 10`:

```sh
cd "$CAPTURE"
iverilog -g2012 -s tb -o sim miter.sv monitor.sv tb.sv
vvp sim +program=0
vvp sim +program=1
vvp sim +program=2
sby -f miter.sby check
sby -f miter.sby cover
```

The three programs cover dependent arithmetic, memory operations, shifts and
branches. Each simulation compares the base RVFI fields for 30 retirements.
Formal compares validity on every active cycle and the base fields on a valid cycle.
Optional CSR channels are not part of this profile.
The monitor also checks the architectural register frame. Reachability asks
for a fourth retirement. Source reset and memory-service restrictions remain
visible in the generated SBY model.

## Measured outcomes

Native run on 2026-11-13 used Icarus, Yosys, SBY and Bitwuzla.

| Check | Outcome |
| --- | --- |
| Map exposure and monitor generation | generated; not a proof |
| Arithmetic, memory and branch simulation | 3 programs, 30 retirements each, no stream mismatch |
| Full bounded stream equivalence, depth 35 | FAIL at cycle 10 |
| Fourth-retirement cover | reached at cycle 18 |

The counterexample contains instruction `0xfeeff76f`, a JAL with a misaligned
target. Native RVFI retains the destination write on the trap. The architectural
monitor suppresses destination writes on a trap and detects the changed register
frame. This is an unresolved difference. The kit does not certify PicoRV32's
RVFI or the state map as equivalent. The simulation matches do not remove it.

### Simulation failure checks

The generated monitor stops simulation with a nonzero exit code for a failed
x0 or register-frame assertion. The comparison stops on a validity mismatch,
including an unknown validity bit. Plain Icarus assertions could previously
print an error and still return zero.

The corrected comparison was run on the same pin. Programs 0, 1 and 2 each
matched 30 retirements. Program 3 places the counterexample JAL at address zero.
It returned exit code 1 on the first retirement. Both the register-frame
check and the destination-address comparison failed. Native RVFI reported
x14 with value 4. The monitor suppressed that trapping write. Run this
negative control with `vvp sim +program=3`. Its expected result is failure.
This reproduces the mismatch in simulation. It does not resolve it.

Nine small simulation tests cover legal writes, x0 changes, unrelated register
writes, trap writes, unknown state and both validity mismatch directions.
Private evidence: `pico-state-sim-fatal-v1` under the worker's evidence tree.

Private evidence is stored in `pico-state-source-v1` and
`pico-state-monitor-v1` under the worker's private evidence directory. The
formal source snapshot is retained under `miter_check/src`; generated comparison
source can later differ. The source revision and hash are in `source.json`.
The native runs held `vex-conn` and used `nice -n 10`.

## Trap decision

The failing comparison is a trap-write difference, not a missing IRQ-state
binding. This profile disables IRQ. The saved misaligned JAL writes the link
value 4 to physical x14 before the terminal trap is reported. Native RVFI
retains rd=x14 and that value. The independent post-state snapshot sees the
same register change. The strict architectural monitor expects a trapping
instruction to preserve the register frame and suppresses the destination.
Thus the frame assertion and stream comparison fail together.

Decision: retain the strict trap-frame rule and the failed equivalence result.
Do not copy native RVFI destination fields into the state map. Do not suppress
trap comparisons or assume away the counterexample. The current kit cannot
certify full PicoRV32 RVFI equivalence on this profile. Its demonstrated
simulation matches apply to the specific nontrapping programs only. A kit
that reports observed writes on terminal traps needs a separate explicit
contract; it must not be described as proof of precise architectural traps.
The program-3 negative control remains a required failure.

## Full RV32UI simulation comparison

`suite.py` compares all base RVFI fields on every retirement until the final
`tohost` store retires. It also checks the register frame. The simulation
waits one time unit after the completion retirement so the comparison can
finish before `$finish`. It returns 0 only when every selected test matches.
Failed comparisons return 1. Missing completion or a time limit returns 3
when there is no separate failed comparison.

```sh
scripts/with-lock.sh vex-conn nice -n 10 rvw/.venv/bin/python \
  examples/picorv32/formal/suite.py --source "$PICORV32" \
  --riscv-formal "$RISCV_FORMAL" --tests "$RISCV_TESTS/isa/rv32ui" \
  --out "$CAPTURE" --prefix riscv64-unknown-elf-
```

Without `--tests`, the helper selects the 37 RV32UI tests bundled with the
pinned PicoRV32 source. The external upstream directory has 42 tests at
revision `d7e86f701b929b5d801f8cda1a4871ab05f452bb`. The generated receipt
records the selected source-file hashes. It does not certify the complete
transitive preprocessor source closure.

The harness uses one MiB of zero-filled RAM, reset PC `0x80000000`, zero
register reset state, immediate memory service, no interrupts and no PCPI.
The ELF uses the existing project linker script and no-CSR test environment.
The assembler enables Zifencei so `fence_i` can build. This does not add that
extension to the RTL. Each test has a one-million-cycle RTL limit and a
90-second host limit. A terminal trap without a test completion gets a separate diagnosis.
It is not a stream match.

### Measured upstream result

The 2026-11-13 native run selected all 42 upstream RV32UI sources. It used
Icarus and the unchanged strict monitor. Forty programs reached completion
with matching base RVFI streams and register frames. `fence_i` and `ma_data`
did not complete before the configured limits. Both remain inconclusive.
No test was silently removed from the denominator.

The separately replayed `0xfeeff76f` negative control returned exit 1 at its
first retirement, time 115000 ps. Native RVFI reported x14=4. Both the frame
assertion and destination-address comparison failed. This confirms the trap
limit above. No new bounded equivalence pass is claimed.

See [suite-results.json](suite-results.json) for every selected test, source
hash, ELF hash, retirement count and outcome. The ELF hashes were added to
the receipt from the retained run artifacts. The helper now emits those
hashes directly on future runs. Private native evidence is in
`pico-upstream-final` under the local run directory. The earlier 37-program
bundled-test run stopped at the completion bus request, before the final
store retired. It is not substituted for the final upstream run.


### Terminal-trap diagnosis

The two timeouts were replayed with the same retained ELFs and strict miter on
2026-11-13. The harness now stops one simulation time unit after a terminal trap.
It waits for the monitor assertions before it stops. It records PC, instruction,
source operand and retirement count. It does not report a trap as a match.

| Program | Terminal PC | Instruction | Retirements | Result |
| --- | --- | --- | --- | --- |
| fence_i | 0x80000050 | 0x0000100f, FENCE.I | 20 | unsupported profile |
| ma_data | 0x80000010 | 0x00141383, LH at x8+1 | 4 | unsupported profile |

PicoRV32 decodes FENCE with funct3=0. It does not implement Zifencei in this
profile. The source operand for the LH was 0x80000580. The effective address
was 0x80000581. CATCH_MISALIGN=1 traps that access. The upstream ma_data test
expects misaligned loads and stores to complete. This harness has no trap
emulator. These are profile limits, not solver timeouts or monitor mismatches.
No RTL feature was enabled and no comparison was weakened.

The suite count stays 42: 40 earlier stream matches and two unsupported
programs. Its overall result stays inconclusive. The 40 matching programs
were not rerun for this diagnosis. suite-results.json retains the original
timeout outcomes under previous_attempt. Adjacent terminal-trap logs record
these two native retries. The exact trap-write negative-control limit above
is unchanged. Other terminal traps remain inconclusive unless the observed
instruction and operand establish one of these profile limits.

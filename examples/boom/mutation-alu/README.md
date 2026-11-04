# BOOM RocketALU mutation example

This recipe tests one emitted `RocketALU` module from BOOM. It does not build or
change the core. Use an emitted `BoomSimTop.v` from the private EDA checkout.
The script copies the exact module into a fresh project outside Git.

```sh
export PATH="$HOME/opt/oss-cad-suite/bin:$PATH"
python3 examples/boom/mutation-alu/prepare.py /path/to/BoomSimTop.v /tmp/alu-mcy
scripts/with-lock.sh boom nice -n 10 rvw/.venv/bin/rvw cov mutate /tmp/alu-mcy \
  --run --baseline /tmp/alu-mcy/check-original.sh --jobs 1 --timeout 180 \
  --test add_sub --out /tmp/alu-mutation.json --json
```

The fixed seed is `20261103`. MCY selects 12 entries, including its unmutated
control. One job runs at a time. Each rvw stage has a 180-second limit.
The test applies all 64 operand pairs from eight fixed 64-bit values to ADD and
SUB. It checks `io_out` and `io_adder_out`. The expected values use unsigned
64-bit addition and subtraction, with modulo-2^64 wrap. These operations follow
RV64I ADD and SUB semantics. The test does not use another DUT output as its oracle.
It does not test 32-bit mode, compare, shifts, bit counts, or rotations.

The mutation script writes RTLIL, then Verilog with automatic internal renaming.
MCY's default `write_verilog -norename` can emit function calls that Icarus cannot
compile. A compiler failure is a test error. It is never a kill.

## Review and close rule

Keep the report and MCY work directory outside Git. Record the parent RTL hash,
module hash, exact command, tool versions, control result and every survivor in
the issue comment. A killed mutant must fail a completed detection test after its
unmutated control passes. A pending mutant has no detection result.

For each survivor, identify the affected logic. Either add a missing stimulus,
prove equivalence in a separate equivalence test, or record a justified scope
limit with the next test needed. Do not label an untested operation equivalent.
Close the review issue when the bounded run completes, the report is reviewed,
and every survivor has a disposition. This rule does not claim full ALU coverage.

## Decisions and limits

Core names and stimulus stay in this project example. MCY generates mutations.
The generic runner classifies results. This example supplies no proof result.
The input declaration `[]` means all design and test inputs are in this project.
Installed tool runtimes remain external dependencies of the execution environment.

# Replay formal timeouts

The idle-machine capacity table is NOT yet measured. The current machine
runs other native jobs. A remaining timeout cannot establish a real capacity
limit. A newly closed check establishes closure under the stated conditions.
It does not establish that host load caused the earlier timeout.

Run the retained jobs with one command:

```sh
export RUN_ROOT=/path/to/retained/runs
scripts/with-lock.sh vex-formal2 nice -n 5 rvw/.venv/bin/python \
  -m rvw.formal.timeout_rerun examples/formal/isa-timeouts.json \
  --time-limit 30m --out /path/to/new-comparison
```

Source the native-tool environment first. The manifest selects VexRiscv
first. Set each `jobs` path to the matching original capture. The example
paths describe the retained run layout. They do not download missing captures.
Keep output outside the repository. Missing SBY files remain error rows.
The module writes `result.json` and `comparison.md` after each check.
It preserves the original mode, depth, scripts, defines and listed source
bytes. It replaces the engine list with a two-engine portfolio and removes
an old SBY timeout so the requested wall limit applies. Each check runs in
sequence under nice priority 5. The whole SBY process tree has the stated cap.
One added `write_json` command records the elaborated property and assumption
cells. It does not change logic. A missing model or empty property set cannot
earn a native pass. Cover success also requires a witness trace. Each result
lists the elaborated assumptions and the condition-model hash. These
assumptions remain proof conditions. The replay does not discharge them.

The manifest has a `cores` array. Each row gives `name`, `previous` and
`jobs`. Paths are relative to the manifest. Environment variables are allowed.
`previous_pointer` selects a nested report with a JSON pointer. `job_pattern`
defaults to `{check}.sby`. It can also use `{instruction}` for an RVFI check.
An optional `checks` map overrides a check's path.
Its value can be a path or `{"sby":"job.sby","task":"check"}`. SBY selects
that task through `--dumpcfg` before capture. Record each machine task under
`CHECK:check` or `CHECK:cover` to match its `native_attempts` timeout.

Only aggregate timeout outcomes are selected. A losing engine's timeout does
not select a check that another engine proved or refuted. Failed checks stay
failed in the source receipt. Instruction activation timeouts are separate
`CHECK-activation` jobs. The source receipt hash and listed input hashes stay
in each result. The script does not infer transitive input closure, observer
equivalence or instruction activation from an engine pass.

The bundled manifest covers the recorded 37 restricted VexRiscv instruction
checks, the timed-out machine checks, three Sail M campaigns, the VexiiRiscv
observer selection and the ooo-mini ISA selection. The Sail receipts must
come from the retained native runs. Missing receipts produce explicit
inventory errors. They do not produce an empty successful core selection.
PicoRV32's retained state-map failure is not a timeout. Its two former program
timeouts now have unsupported-profile diagnoses. Neither is selected for a
formal timeout retry. Add separate core rows for alternative-abstraction
receipts. Use explicit per-check
paths when those captures have different layouts. Do not substitute current
RTL for a missing historical capture and call the result a fair comparison.

The table reports depth, first engine, elapsed seconds, limit, native result
and load at the start and end. Depth is the retained SBY depth. It can differ from the instruction
assertion cycle in the source receipt. Jobs with a nonzero SBY `skip` use
two SMT engines because ABC BMC does not support that option.
`closed_after_retry` does not mean full ISA
signoff. A `pass` in prove mode is a native unbounded result conditional on
all source assumptions. `bounded_pass` stays finite. Remaining timeouts stay
`still_unresolved`. Low load at both endpoints does not certify low load
throughout a job. Exit 1 means a counterexample. Exit 3 preserves incomplete
ISA signoff, including an empty selection.

## Small native control run

On 2026-11-13, three synthetic replay controls used a 20-second limit per
check. The prior timeout receipts were synthetic. They test execution and
classification, not recovery of a core timeout.

| Control | Mode and depth | First engine | Seconds | Result | One-minute load start / end |
| --- | --- | --- | --- | --- | --- |
| Matching toggling state | BMC 5 | abc:bmc3 | 0.992 | bounded pass | 141.85 / 141.06 |
| Matching toggling state | Prove 5 | abc:pdr | 0.804 | native inductive pass | 141.06 / 141.06 |
| False assertion | BMC 5 | abc:bmc3 | 1.684 | expected failure | 141.06 / 141.06 |

Both matching state bits start at zero and toggle on each clock. The
assertion compares them on each clock. No environmental assumption was added.
The false-assertion control asserts zero on each clock. No core ISA claim
depends on these controls. Raw data stays in the private control-tests-final run.

Regenerate the controls with native tools on PATH:

```sh
rvw/.venv/bin/python -m pytest rvw/tests/formal/test_timeout_rerun_native.py \
  --basetemp "$RUN_ROOT/control-tests" -q
```

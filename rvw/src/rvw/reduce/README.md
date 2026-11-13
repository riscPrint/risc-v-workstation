# Failure reduction

`rvw reduce RUN` preserves a C1 failure signature while it reduces cycles,
seeds, memory latency, instruction ranges or stimulus. Inconclusive runs do
not reproduce a failure. See `rvw reduce --help` for each mode.

## Strict Spike mismatch predicate

A C1 pass can still differ from Spike. Select the reference predicate with:

```sh
rvw --project PROJECT reduce RUN --cosim-platform PLATFORM.json \
  --modes cycles --budget 1 --out NEW_DIRECTORY --json
```

The original C1 result must be conclusive. A strict Spike mismatch must have
at least one differing field. Every trial requests C2 and must pass C1 before
it can reproduce that mismatch. Complete unmasked, unsynchronized matches are
non-reproductions. Missing traces, reference errors, incomplete comparisons,
masked comparisons and synchronized comparisons are inconclusive.

The signature is `cosim:` followed by the sorted differing field names.
This preserves the observable mismatch class. It does not prove that every
candidate has the same root cause. Review the recorded full comparisons.
Each trial retains its independent reference result. The report also records
the original comparison and captured platform. The existing capture verifies
each ELF against its C1 hash. The predicate does not change C1 status.

Use `--modes instructions --instruction-symbol NAME` for a sized executable
ELF symbol. NOP replacement preserves addresses. The result can be one-minimal
under the selected predicate and trial budget. It is not a global minimum.
The default C1 predicate remains available when no platform is supplied.
MCP `reduce_run` accepts the same `cosim_platform` option.

Native check, 2026-11-13: the VexRiscv negative control
`examples/vexriscv/rvw/random/uninitialized-scratch.S` passed C1 at 17 cycles.
`--modes cycles --budget 1` kept the signature `cosim:csr[0x340]`. Its one trial
passed C1 and again mismatched Spike. The run took 3.5 minutes at load 140,
including one Verilator build. Use a core copy without Git submodules; the
debug input capture refuses submodule entries. The project needs `[debug]`.

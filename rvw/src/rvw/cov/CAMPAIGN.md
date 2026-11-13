# Bounded stimulus execution

`rvw cov campaign --settings loop.json --work-dir out --json` runs the integer
candidate loop. `cov_campaign` uses the same API. Add `--resume` to read the
last sealed state. Each invocation has a total attempt limit. Raise this limit
only in a new campaign because settings are part of resume identity.

The project owns these JSON settings. Paths are relative to the settings file.

```json
{
  "schema": "rvw.stimulus-loop/1",
  "manifest": "isa.json",
  "source_root": "/opt/riscv-opcodes",
  "project": "rvw.toml",
  "config": "small",
  "registers": [5, 6, 7],
  "runtime": "runtime.S.in",
  "linker": "link.ld",
  "platform": "platform.json",
  "compiler": "riscv64-unknown-elf-gcc",
  "isa": "rv64i",
  "abi": "lp64",
  "attempts": 32,
  "seed": 1,
  "timeout_s": 60,
  "max_cycles": 100000,
  "timeout_ms": 1000
}
```

The runtime is a complete assembly program with one literal `{payload}` marker.
It must place that marker in executable code and terminate through the adapter's
pass contract. The three registers must be writable at that point. Runtime and
linker inputs must be self-contained. External includes are not captured.

The loop selects an unhit supported goal in stable order. It tries each goal
once. It compiles the candidate and checks its ELF payload word and symbols.
It runs C1 without cache reuse and compares the full C2 trace with strict Spike
checks. Only complete, nonempty matching execution with C1 pass earns payload
observations. Incidental hits remove later goals. Failures keep zero credit.
A mismatch or core failure stops the loop.

Payload reports use a separate plan identity. Setup and termination are excluded.
The loop records source, ELF, C1 and trace hashes. It records every attempt's wall
time, controller CPU time, and reaped-child CPU time. Descendant completeness on
macOS is not qualified. CPU-hour metrics remain null. This command does not run
a paired random baseline and does not establish a comparative closure rate.

State uses immutable C8 generations. Resume checks settings, declared input
hashes, pinned opcode data, and saved attempt artifacts. An interrupted attempt
is not reused. Hard-kill cost is unknown. Raw attempts remain beside the state
store; they are hash-checked but are not copied into its sealed generation.
Transitive project/native dependency closure and cross-host replay remain
unqualified. The campaign status stays inconclusive unless a checked defect
makes it fail. No C4 acceptance follows from coverage.

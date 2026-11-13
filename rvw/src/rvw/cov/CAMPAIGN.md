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

## Measured RTL feedback

Add `rtl_plan` and `recipes` paths together to select RTL feedback. The sampling
plan is an existing `rvw.rtl-plan/1` plan. Its design ID must equal the C1
`rtl_sha256`. Recipes use this shape:

```json
{
  "schema":"rvw.event-recipes/1",
  "plan_id":"<exact rtl.identity(plan) hash>",
  "design":"<generated RTL SHA-256>",
  "recipes":[{"goal":"sem_add_rs1:[\"zero\"]","targets":["queue-full"]}]
}
```

Targets must name declared event or sequence IDs. Signal paths stay in project
data. The controller uses a UCB policy over measured new events. It explores
untried recipes first and keeps trying pending recipes within the attempt bound.
Integer candidates vary free operands with the recorded seed. The requested
semantic predicate remains fixed. This is a bounded search over the existing
candidate families. It cannot synthesize arbitrary core stress programs.

The core adapter must attach `rtl_samples` to C1. It must also write a
`details.rtl_samples` receipt with exactly `elf_sha256`, `rvfi_sha256`,
`samples_sha256`, `plan_id` and `rtl_sha256`. These hashes bind the sample
file to that ELF, full C2 trace, sampling plan and generated RTL. Missing or
mismatching receipts are unsupported. Full execution must first pass
strict Spike qualification. The existing RTL sampler checks exact plan/design
identity and complete sampling. Reused sample hashes earn no new reward.
Missing hooks, stale samples and unqualified runs remain unsupported. History
and sample hashes are part of resume state. ISA hits and RTL events stay separate.
No native feedback campaign or gain over random generation is claimed.

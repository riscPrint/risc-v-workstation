# OoO Mini

This core-owned example targets SpinalHDL 1.15.0 and Scala 2.13.14.
It implements one-wide rename and commit with oldest-ready out-of-order issue.
The default configuration has eight ROB slots and 48 physical registers.
The `rob16` configuration has sixteen ROB slots. Both use the same RTL.

The ROB slots also hold the issue queue and load/store queue. Source tags use
physical register ready bits for wakeup. Loads wait for all older store addresses
and data. Per-byte forwarding selects the youngest older matching store. Stores
reach memory only at commit. A commit redirect discards all younger work and
restores the committed map, including the redirecting instruction's destination.
A sixteen-entry bimodal predictor and tagged BTB predict fetch addresses.

There are no caches, address translation, compressed instructions or interrupts.
The memory ports require zero-latency RAM. They support unaligned scalar accesses.
Machine CSRs are a limited subset. Multiplication completes after three cycles.
Restoring division computes one quotient bit per cycle and completes after 32 cycles.

## Build and run

Set `RVW_HOME` to the workstation checkout. Source its native tool environment.
Run from this directory:

```sh
../../scripts/with-lock.sh sbt-mem nice -n 10 sbt compile 'runMain ooomini.Generate'
mkdir -p rvw/out/programs
riscv64-unknown-elf-gcc -march=rv32im -mabi=ilp32 -nostdlib \
  -T rvw/link.ld rvw/smoke.S -o rvw/out/programs/smoke
rvw regress run --tier quick
```

The native C1 adapter uses the workstation's generic ELF loader, result writer,
RVFI sampler and C2 writer. Retirement signals come from the RTL ROB head.
Unsupported observation modes fail explicitly. Input identity is not qualified.
Build the ISA programs with `rvw/build-isa.py PATH_TO_RISCV_TESTS`.
Then run `rvw regress run --suite isa --rvfi-trace`.
Run `rvw/compare-isa.py RUN_DIRECTORY` for strict Spike comparison.
The tested riscv-tests revision is `d7e86f701b929b5d801f8cda1a4871ab05f452bb`.

## Evidence status

The native core passes all 50 RV32UI/M programs, including `ma_data`.
All 50 C2 traces strictly match Spike with zero synchronizations.
The suite retired 18,154 instructions. The separate multiply/divide unit test
passes 456 directed and seeded random vectors. See [the result table](isa-results.json)
for per-program cycles and instruction counts and the tested source hashes.

Formal proof, timing correlation, fault results and a committed gate remain
unqualified. No whole-core proof is claimed.


## Decisions

The core uses committed-map recovery instead of branch checkpoints. Branches
resolve at issue but recover at commit. This keeps traps precise and limits the
state needed for recovery. It increases branch penalties. Predictor training
occurs at commit so squashed branches do not change predictor state.

The tiny OoO fixture supplied the committed-map recovery pattern. Its four-slot,
two-register interface cannot execute RISC-V instructions and is not instantiated
as a core component.

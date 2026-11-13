# Retirement observer alignment

The current observer targets the single-lane RV32 cacheless profile. It retains
register and memory results by full micro-op ID. Dispatch clears reused slots.
A same-cycle result can bypass its table. Emission requires a matching tag.
The observer asserts on missing data or a completion-slot collision.

A normal commit supplies the preceding instruction's next PC. A trap boundary
ends that chain at xepc. The observer captures the faulting instruction at the
trap stage. It records the actual trap redirect and emits a separate synchronous
fault record. The core issues that redirect before its architectural trap pulse.
The first handler instruction carries the RVFI interrupt-boundary flag. MRET is
a normal instruction record. It is not a second synchronous fault record.
Privilege mode is captured with each instruction.

The memory observer uses the upstream WhiteboxerPlugin load and store events.
It retains address, data, size-derived byte masks and the micro-op tag. It does
not replace memory data with register results. CSR immediate fields do not become
register-source indices. FENCE and privileged control instructions do not invent
a destination register.

## Directed alignment check

```sh
scripts/with-lock.sh vex-conn nice -n 15 rvw/.venv/bin/python \
  examples/vexiiriscv/formal/observer_smoke.py \
  --rtl BUILD/VexiiRiscv.v --out SMOKE
scripts/with-lock.sh vex-conn nice -n 15 rvw/.venv/bin/python \
  examples/vexiiriscv/formal/observer_checks.py \
  --rtl BUILD/VexiiRiscv.v --riscv-formal "$RISCV_FORMAL" \
  --out CHECKS --timeout 20
rvw formal isa --project CHECKS/project --out SIGNOFF --timeout 20
```

The directed program checks a dependent store/load, arithmetic, ECALL, handler
entry and MRET. It checks retirement order through the return. The positive run
matched 15 records. The negative control forces the observer store-data output
to zero. It returned nonzero at the store mismatch. These are finite simulation
results. They are not formal observer equivalence or full ISA qualification.

The first run exposed an observer error. It waited for a trap redirect after
the trap pulse. That lost the ECALL record and later emitted a duplicate MRET
fault. The correction retains the preceding actual redirect. The regression
keeps the original failure and the successful retry in observer-results.json.

## Formal scope

The helper first runs ADD at depth 12. It then selects ADD, LUI, BEQ, LW and SW
at depth 60 through the ISA kit. Each native task has a 20-second limit. The
result retains assertion, retirement-cover and instruction-activation outcomes.
All unselected instruction and machine rows remain unsupported. Interrupt and
bus-error inputs are zero. Other bus inputs remain unconstrained. In particular,
this is not a qualified bus-ID or response-order model. A diagnostic assertion
failure needs attribution before it can be called a core defect.

Interrupt entry, I/O, compressed instructions, overlapping trap/commit events,
multiple lanes and full independent observer equivalence remain unqualified.
A final normal commit still waits for the next commit or trap boundary to
supply its next PC. The finite check does not establish observer liveness.
The fault-completion slot is checked for overflow. No assumption waives it.

## Build the profile

Use the source pins and example build below. Set RVW_HOME to this workstation.
Set VEXIIRISCV to the private checkout. Hold sbt-conn for compilation and vex-conn
for native core work. Use nice priority 15. The measured continuation compiled
the observer with the already-built pinned example classpath. It did not rebuild
all core and Spinal sources. The emitted RTL digest binds each measured run.

From examples/vexiiriscv/rvw:

```sh
"$RVW_HOME/scripts/with-lock.sh" sbt-conn nice -n 15 \
  sbt '++2.13.14!' compile
"$RVW_HOME/scripts/with-lock.sh" vex-conn nice -n 15 \
  sbt '++2.13.14!' 'runMain rvwvexii.FormalRvfi BUILD'
```

The historical prototype and its results follow. Its limits describe that older
export. They do not erase the later measured results or qualify the current one.

# Historical hardware observer prototype

`rvwvexii.FormalRvfi` is an opt-in elaboration entry point. It adds the
project-owned `FormalRvfiPlugin`. It does not change VexiiRiscv sources or the
default simulation elaboration. Use a private copy at the example's pinned
revision, with its pinned SpinalHDL and rvls dependencies.

The observer reads the execute lane at the trap stage through
`ExecuteLaneService`. It reads register operands from the lane payloads. It
tracks register-writer results by micro-op ID. Dispatch clears each reused ID.
A same-cycle writer bypasses the result table. An assertion requires a known
write for a committed nonzero destination.

The observer buffers one committed instruction. The next commit supplies its
next PC. This has a known limit: a trap between these commits can change that
PC relationship. It is not a qualified trap observer. A memory commit raises
an observer assertion. Memory effects are not replaced with invented data.
The exported trap, halt and interrupt fields are zero for the supported normal
commit stream. A final commit has no output until another commit follows it.

This prototype must not be used for ISA signoff. It needs a completion queue,
trap boundaries and retirement-aligned memory transactions before full
instruction campaigns can earn results. Compiler or elaboration success alone
does not qualify the observer. Native results will be recorded below.

The result table has 64 slots and retains the full micro-op ID in each slot.
A collision cannot select an old result without failing the ready check.
This capacity is an observation limit, not an assumption about the core.

From `examples/vexiiriscv/rvw`, run the elaboration with the private source
variables set, under the private core lock and the shared sbt lock:

```sh
sbt '++2.13.14!' 'runMain rvwvexii.FormalRvfi OUT'
```

Set `VEXII_RVFI_RTL` to `OUT/VexiiRiscv.v`. Set `RISCV_FORMAL` to the private
pinned riscv-formal checkout. `formal/binding.json` selects diagnostic ADD and
LUI checks at cycle 60 plus retirement cover. Its bus and interrupt inputs are
unconstrained. This is a diagnostic environment, not a qualified bus contract.

```sh
rvw formal rvfi-generate examples/vexiiriscv/formal/binding.json --out PROJECT
rvw formal riscv --project PROJECT --out RESULTS --timeout 150
```

Native compilation passed. The final hardware elaboration passed in 4.925 s.
The first elaboration placed plugin creation outside the Spinal context. The
second used an oversized result table and failed width checks. Its diagnostic
retry exhausted the 3 GiB heap. The final table uses tagged slots.
Core revision: `9f70315deb3390b283995c5b8f1bd38215ecf52b`.
SpinalHDL revision: `de72faf6062206a89b445e5cc07e32ed982712c8`.
rvls revision: `847ce99fd2b28a5c0ccb1ec2683311cf97a9fefc`.

## Native diagnostic results

| Check | Outcome | Bound or target |
| --- | --- | --- |
| insn_add_ch0 | timeout | 60 cycles |
| insn_lui_ch0 | timeout | 60 cycles |
| cover | pass | 60 cycles |

No instruction proof closed. Retirement cover reached cycle 60. The prototype
remains unsupported for ISA signoff. Full instruction, memory and trap campaigns
were NOT RUN. Each check had a 150-second limit. The native job used the private
source copy, `vex-conn`, and `nice -n 10`.

RTL SHA-256: `6e1460ca602ed78dcd9190a2c9b359bb0fcb1888b79928b8c52425464ff4fb09`.

Evidence directories: `vexii-rvfi-v3`, `vexii-project-v1`, and `vexii-checks-v1`
in the worker private evidence tree.

## Continuation receipts

See [observer-results.json](formal/observer-results.json) and the
[signoff inventory](formal/observer-signoff.md). The
[first failed stream](formal/observer-initial-failure.log),
[final positive stream](formal/observer-positive.log) and
[store-data negative control](formal/observer-negative.log) retain the native
observations. All five selected depth-60 assertion and activation tasks timed
out. General retirement cover also timed out. No instruction proof closed.

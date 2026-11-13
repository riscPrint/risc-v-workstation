# Hardware RVFI observer prototype

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

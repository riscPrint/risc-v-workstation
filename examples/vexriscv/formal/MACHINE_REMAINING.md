# RV32IM machine history checks

`machine_remaining.py` accepts only the measured `FormalMTop` export hash
recorded in [MACHINE_M.md](MACHINE_M.md). It captures a source copy and writes
an `rvw.machine-checks/1` manifest. It does not edit the external core.

```sh
rvw/.venv/bin/python examples/vexriscv/formal/machine_remaining.py \
  --rtl BUILD/VexRiscv.v --out CAPTURE
rvw formal machine-checks --manifest CAPTURE/machine.json \
  --out RESULTS --run --timeout 180
rvw formal isa --project examples/vexriscv \
  --machine CAPTURE/machine.json --out SIGNOFF --timeout 180
```

Hold `vex-conn` and use `nice -n 10` for native runs. Select at most three
parallel jobs. The generic `isa` command prints the machine rows. It keeps
missing instruction checks and missing machine rows visible as unsupported.

## Observation scope

The CSR row uses `mscratch` from the shared CSR catalog, with all 32 bits
writable. It captures the before value, operand, operation, actual CSR read
bus, access-failure state and mode at a CSR read-enabled transaction. The
after value comes from updated storage. This covers register and immediate
read/modify/write forms. CSRRW with rd=x0 suppresses the read and is excluded.
Other CSRs require separate masks and WARL or hardware-update models. This
single row does not certify the whole CSR bank or catalog.

The instruction-memory row tracks accepted instruction-command PCs in an
eight-entry FIFO. A response uses the oldest accepted PC. The environment
assumes ordered responses, at least one cycle of latency, no unsolicited
responses and no instruction-bus errors. The checker asserts FIFO capacity.
The generic property assumes an immutable symbolic 32-bit memory word at
that response address. It compares that word with the instruction at the
same retired PC. This profile has no compressed instructions. Self-modifying
code and instruction-access errors are outside this check.

The kill-history row carries a separate live bit through decode, execute,
memory and writeback. A removed instruction cannot transfer a live history.
A normal retirement requires live writeback history and no current removal.
The proof concerns this in-order four-stage profile. It does not certify a
reorder buffer or an instruction-ID map for another core.

The PC-chain row retains a controller trap redirect until the next normal
retirement. It compares that retirement PC with the retained target. Without
a trap redirect it checks the previous retirement's next PC. This adds
post-trap retirement alignment to the local controller checks in MACHINE_M.
Terminal formal-halt records are excluded from normal retirement in all three
history checks. No terminal-halt event is presented as a machine trap return.

## Initial native outcomes

Native runs on 2026-11-13 use Bitwuzla, bound 25 and a 180-second limit
for each assertion or cover task. They share the captured source hash
`999f3a4f104a73ea54d770a8cda051fae9427ab31b3b7c8c055409627dd9ae14`.

The PC-chain check fails at step 13 with a reached retirement cover. Its
witness has an MRET redirect payload `0x80000005` at PC `0x80000000`.
The next normal retirement is at `0x80000004`. Both the remembered redirect
and the previous RVFI next PC hold `0x80000005`. Thus the local controller
payload and the retired PC disagree on the low bit. This is separate from
the MPP finding. The check retains FAIL. It does not silently mask the PC
or constrain MEPC writes to aligned values. A directed replay and CSR WARL
review are still required before attributing this witness to the core.

The CSR row is deliberately limited to `mscratch`. Counter CSRs, MSTATUS,
MEPC, MTVEC, MCAUSE and interrupt state are not certified by that row.

| Check | Bound | Assertion outcome | Trigger cover |
| --- | --- | --- | --- |
| mscratch read-enabled CSR transactions | 25 | timeout at 180 s | reached |
| Instruction-memory pairing | 25 | timeout at 180 s | reached |
| Live pipeline history at normal retirement | 25 | bounded PASS | reached |
| PC chain across controller redirects | 25 | FAIL at step 13 | reached |

These outcomes do not complete item 2 or machine signoff. The full CSR-bank
model and PC-chain counterexample attribution remain open. See
[machine-remaining-results.json](machine-remaining-results.json) for the
native rows. Private job trees are under `machine-remaining` in the local
run directory. They retain source copies, hashes, SBY manifests and traces.

The two timeout retries used the same source hash and environment, bound 15
and a 180-second task limit. Both `mscratch` CSR consistency and instruction
memory returned bounded PASS with reached covers. The depth-25 timeouts remain
inconclusive attempts. These lower-bound results do not replace them. Pass
`--depth 15` to the capture helper to reproduce the retry bound.

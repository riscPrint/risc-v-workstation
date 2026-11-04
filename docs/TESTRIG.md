# TestRIG RVFI-DII integration design

Status: bounded RVFI-DII v1 socket transport and replay are implemented.
Native core injection remains in each core adapter. The ELF adapters have no
DII hook. A transport pass is not a core equivalence result.

The upstream [RVFI-DII specification](https://github.com/CTSRD-CHERI/TestRIG/blob/master/RVFI-DII.md)
requires instruction injection over a socket, pipeline retirement packets,
repeatable reset and a defined memory window. Fetch and prediction must be
bypassed. RVFI output alone is not enough. Pin a TestRIG revision and protocol
version before implementation; the linked document describes the original
8-byte instruction and 88-byte execution packets.

## Adapter boundary

`RiscvSim/src/main/scala/riscvsim/Model.scala` defines an ELF-based `RunJob`.
`CoreAdapter.run` executes that job. The BOOM adapter loads sparse memory and
observes retirement. It has no instruction-injection port. Replacing bytes in
ELF memory cannot implement DII when fetch, prediction and speculation remain
active. This path needs a simulation-only core hook. Core changes are outside
this repository's ownership. Keep that hook optional and off by default.

## Workstation transport

`rvw.cosim.dii` implements little-endian 8-byte input and 88-byte output
packets. It pins the v1 layout to TestRIG commit
`70717956d9a0445a11ac9a070387d119c523d60f`. QCVEngine commit
`5e15965a819ca1be9f14d2e8e319e98fd89a557f` supplies the wire encoder and
version negotiation reference. The server answers the initial `VERS` command
with a v1 halt packet. It rejects other commands and v2 packets.

A core-owned Python factory implements `Hook.reset()` and
`Hook.execute(tokens, timeout)`. Execute must preserve injection timing,
bypass fetch and prediction, drain the pipeline, and return retirements in
order. It must honor the cooperative execution timeout. Reset must clear
registers, CSRs and the 64 KiB memory window at `0x80000000`. The transport
resets before the first stream, after each stream and on errors. It sends a
separate halt delimiter after pipeline drain. It does not map C2 `irq` to
RVFI `intr`. Hook execution runs inside the server process; use an outer
process-group deadline to bound a hook that does not return.

Start the hook server and a native Sail server in separate processes:

```sh
rvw cosim dii serve --hook my_core.dii:make_hook --listen 127.0.0.1:5001 \
  --max-streams 100 --timeout 30 --json
sail_riscv_sim --rvfi-dii 5000
QCVEngine -a 5000 -b 5001 -r rv64i -n 50 -L 20 --strict-comparison
```

Use a Sail configuration that matches the selected core. Pin both model and
vengine builds in the external result package. The vengine owns generation,
comparison and reduction. `serve` reports only transport completion. A vengine
exit or an open socket alone does not establish equivalence. Native vengine
execution needs its own Haskell build; Python socket tests do not supply it.

Replay one saved binary stream (instruction packets followed by EndOfTrace):

```sh
rvw cosim dii replay --tokens /tmp/stream.dii \
  --core-endpoint 127.0.0.1:5001 --sail-endpoint 127.0.0.1:5000 \
  --timeout 30 --json
RVW_TEST_DII_SAIL=/absolute/path/sail_riscv_sim \
  rvw/.venv/bin/python -m pytest rvw/tests/cosim/test_dii_native.py -q
```

Replay uses strict packet-field equality. It does not relax unused register
fields or synchronize counters. A strict mismatch can therefore need semantic
review. A match requires one retirement per injected token on both endpoints,
increasing order, and a halt delimiter. Early halts are inconclusive. This
conservative rule does not establish equivalence for streams that terminate
early on traps. Save packets, ISA configurations and tool revisions externally.

## Scope limits

Core injection cannot proceed as an ELF-only change. Track the core hook separately
from transport work and [generator ownership #33](https://github.com/riscPrint/risc-v-workstation/issues/33).
TestRIG cannot replace fetch/cache tests when its injection path bypasses them.
Keep U/S/M trap-priority, illegal-encoding, FP, compressed-boundary, Zb, crypto,
ABI and configuration-matrix campaigns separate. Each needs independent checks
and declared coverage. A random stream count does not close those requirements.

## Limit ownership

TestRIG integration: [#48](https://github.com/riscPrint/risc-v-workstation/issues/48). Observation streams: [#189](https://github.com/riscPrint/risc-v-workstation/issues/189).

Retained limit: Only the documented stream subset is supported. Malformed or incomplete evidence cannot become a match.

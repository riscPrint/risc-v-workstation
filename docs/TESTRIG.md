# TestRIG RVFI-DII integration design

Status: design only. No TestRIG execution or protocol support is claimed.

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

## Proposed implementation

Use a separate adapter mode. Keep C1 ELF runs unchanged. A reusable transport
library can parse bounded packets, buffer one input stream and enforce socket
and execution deadlines. Put injection signals and retirement mappings in each
core adapter. Reset registers, CSRs and memory between streams. Preserve packet
timing and retirement order across multiple commit slots.

Before a BOOM implementation, agree the hook and reset behavior with its owner.
Check that no wrong-path instruction consumes a token. Test redirects, compressed
instructions, stalls, traps and reset during an incomplete stream. Compare each
stream against an independently configured TestRIG model. Save input packets,
configuration, revisions, execution packets and reduced failures externally.

Do not translate C2 `irq` level events into RVFI's trap-handler flag. Review
trap and memory semantics against the pinned protocol. Add explicit contract
text and compatibility tests if a new public mode or artifact is introduced.
Return error or inconclusive for malformed, truncated or unsupported streams.
A timeout must not become an equivalence pass.

## Scope limits

This work cannot proceed as an ELF-only change. Track the core hook separately
from transport work and [generator ownership #33](https://github.com/riscPrint/risc-v-workstation/issues/33).
TestRIG cannot replace fetch/cache tests when its injection path bypasses them.
Keep U/S/M trap-priority, illegal-encoding, FP, compressed-boundary, Zb, crypto,
ABI and configuration-matrix campaigns separate. Each needs independent checks
and declared coverage. A random stream count does not close those requirements.

## Limit ownership

TestRIG integration: [#48](https://github.com/riscPrint/risc-v-workstation/issues/48). Observation streams: [#189](https://github.com/riscPrint/risc-v-workstation/issues/189).

Retained limit: Only the documented stream subset is supported. Malformed or incomplete evidence cannot become a match.

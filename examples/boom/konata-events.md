# BOOM pipeline event mapping

The generic SpinalKonata API supports stall causes, explicit replay causes,
dependency edges and physical commit kinds. The present BOOM adapter does not
emit these events. Its existing R records retain unknown architectural semantics.
This file describes the required core probe changes. It does not claim that they
have been implemented or measured on BOOM.

## Required core changes

`KonataProbe` in `boom/system/BoomSimTop.scala` exports `comValid` from
`rob.io.commit.valids`. Add an optional per-slot architectural valid signal from
`rob.io.commit.arch_valids`, beside the physical valid and `comRobIdx` signals.
The adapter must emit `Commit(id, predicatedOff = !archValid)` only for each
physical commit. Preserve the physical R record. Keep predicated-off commits out
of the architectural count. Do not infer the flag from C1 counter differences.
Keep probe construction optional and off by default.

Add explicit reason signals and stable instruction IDs where the core can
observe them. Bind signals to these generic events in this project adapter:

| Probe evidence required | Generic event |
|---|---|
| Issue entry cannot issue because required operands are not ready | `Stall("issue", StallCause.OperandWait)` |
| A ready operation cannot use a required execution resource | `Stall("issue", StallCause.Structural)` |
| A waiting operation is blocked by an observed load miss | `Stall("memory", StallCause.LoadMiss)` |
| Dispatch cannot proceed because ROB allocation is full | `Stall("dispatch", StallCause.RobFull)` |
| Dispatch cannot proceed because LSQ allocation is full | `Stall("dispatch", StallCause.LsqFull)` |
| A replay pulse with an explicit reason and live fetch ID | `Replay(id, cause)` |
| A consumer/producer relation with both fetch IDs known | `Dependency(consumer, producer)` |

A full bit alone is not a blocked handshake. A repeated `Is` stage or a long
`Iq` visit does not measure a cause. Multiple reason bits must emit multiple
samples. Give lanes or threads distinct scopes when needed. Mark estimates as
`inferred`. Keep fetch-ID matching and mismatch checks in the BOOM adapter.
If an ID cannot be matched, report the mismatch instead of attributing the event
to another instruction. No core sources were changed for this tool increment.

# Stream cancellation review

Refs: #5. Related core report: riscPrint/spinal-boom#7.

The corrected generic rule is on main in `dc08c527`. It retains the stalled
valid and payload obligations except when a reviewed cancellation is active.
It discovers Spinal Stream helpers from their assignments. BOOM's Chisel
Queue and branch-kill queue are separate implementations. The recognizer
does not infer their cancellation signals from their names.

Run `python3 SpinalChecks/boom/stream-dispositions.py` to regenerate the
source review. This does not elaborate BOOM, run checks or run formal.

The historical issue reports 24 fired check IDs. The source review now has
24 named dispositions. One is the later FetchBuffer alias. The other 23
have historical names. One original ID is still absent from the available
inventory. Equal row counts do not establish a complete historical mapping.

Five reviewed IDs have an explicit Queue `io_flush` binding in `BoomChecks`:
f3, f3_bpd_queue, f4, f4_bpd_queue and stq_execute_queue dequeue valid.
`ChiselUtil.scala:39-44` clears occupancy on the flush edge. The binding
uses the previous sample. These five no longer have a blanket valid waiver
in `streams.txt`. Checks remain active outside cancellation. Payload rules
remain active unless a separate exact disposition already exists.

Thus the generic helper recognizer alone explains 0 of 24 historical
firings. The five source bindings explain the documented cancellation
mechanism for 5 of 24. This is a source result, not a measured reduction in
firings. Elaboration, binding-name validation and simulation are NOT RUN.
Branch-mask mutation and replacement of an unaccepted offer need separate
channel semantics. Cancellation does not justify removing those checks.

## Conditional obligations

Each report row now separates the source mechanism, candidate cancel condition,
sample timing and binding validation. These fields are source proposals. They
do not establish a bound or passing check in an elaborated BOOM design.

The five queue bindings use `io_flush` from the previous sample.
`rocketchip/util/ChiselUtil.scala:39-42` clears queue occupancy after that edge.
The frontend connections are in `boom/ifu/frontend.scala:318-326,533-539`.
The f4 BPD queue uses f3_clear. The store execute queue is flushed by
`boom/lsu/lsu.scala:917-920,1518-1524` and rebuilt from the store queue.

The branch-kill queues need the head-entry kill or flush guard from the previous
sample. The buffered form uses out_uop in `boom/util/util.scala:373-385`.
The unbuffered form uses the indexed head uop at lines 404-436. These are
expressions, not an assumed signal named flush. They still need a named
observation or elaboration recognizer. The four payload rules also observe
live branch-mask updates while the entry remains valid. A kill-only exception
cannot explain those payload changes. An immutable-field check would need a
separate reviewed projection.

FetchBuffer clears occupancy in `boom/ifu/fetch-buffer.scala:185-189`.
`frontend.scala:679` connects its dequeue to io_cpu_fetchpacket. Those two IDs
are aliases of one transfer. The proposed guard is the previous io.clear.
Neither source proposal changes the separate payload obligation.

The exception-PC request, metadata arbiter and LSU requests are per-cycle
unaccepted offers. TileLink A also permits pre-acceptance replacement under
its protocol. These cases are not all registered flushes. The review keeps
them separate from cancellation, and keeps accepted-burst checks and retained
TileLink findings active. Issue #5 and riscPrint/spinal-boom#7 remain open.

## Internal TileLink A stage

The [original core issue](https://github.com/riscPrint/spinal-boom/issues/7)
names `stream.payload_stable:arbiter.ups_0_a`. This is a separate stage from
`arbiter.io_ups_0_a`. Spinal 1.15.0 `Arbiter.scala:35-50` creates internal
`ups` from `io.ups` through `Bus.withSourceOffset`.
`Bus.scala:456-465` forwards the handshake and payload, then replaces the
source field. Port zero has offset zero. The receiver forwards the current
selected A payload on acceptance. The BOOM producer uses `TLArbiter` in
`mshrs.scala:719`, which can replace an offer before acceptance.

This supports a source disposition for legal pre-acceptance replacement.
It does not permit an accepted burst to change. The disposition adds no
entry to `streams.txt` or `waivers.txt`. It claims no new native check pass.
The exact historical inventory remains incomplete. Refs: #5.

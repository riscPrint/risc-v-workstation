# Stream cancellation review

Refs: #5. Related core report: riscPrint/spinal-boom#7.

The corrected generic rule is on main in `dc08c527`. It retains the stalled
valid and payload obligations except when a reviewed cancellation is active.
It discovers Spinal Stream helpers from their assignments. BOOM's Chisel
Queue and branch-kill queue are separate implementations. The recognizer
does not infer their cancellation signals from their names.

Run `python3 SpinalChecks/boom/stream-dispositions.py` to regenerate the
source review. This does not elaborate BOOM, run checks or run formal.

The historical issue reports 24 fired check IDs. The committed reviewed
stream file identifies 20. Three more IDs are in the TileLink waiver list. One historical
ID is not mapped by these files.
The report retains that gap. It does not invent a complete firing inventory.

Five of the 23 have an explicit Queue `io_flush` binding in `BoomChecks`:
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

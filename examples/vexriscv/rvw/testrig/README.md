# Core-side instruction injection sample

`port.json` binds the existing split fetch bus for `rv32im`. The generic
harness drives this port while the adapter disables its RAM instruction
responder. It keeps the data responder active.

Both native software runs passed C1. The matching feed produced a complete
strict Spike match with 6 retirements. The changed feed produced the
expected mismatch at instruction 1: x5 received 8 instead of 7. The reference
ELF still contains `addi x5,zero,7`. No masks or synchronization were used.

See [the results](results.json) for receipts and hashes. Responses include
speculative fetches. Missing feed addresses generate fetch faults. The first
preflight stopped before retirement because it read an inaccessible reset
object. The fixed driver uses Spinal's simulation reset API. That preflight
earned no execution credit. Raw files remain under
`rvw/out/dv/injection-v2-vexriscv`.

Build `program.S` with the example's random-stimulus linker. Generate its feed
with `rvw regress instruction-feed`. Run the adapter with `--rvfi-trace`,
`--instruction-port port.json`, and `--instruction-feed feed.json`. Use private
core copies and locks `vex-dv` and `sbt-dv` for worker runs.

This is the fetch hook and offline input path. Live TestRIG transport and its
packet protocol remain unimplemented. No physical or C4 qualification follows.

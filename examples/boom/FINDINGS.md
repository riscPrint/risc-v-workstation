# BOOM findings

## Generated checks, 2026-11-13

Private core revision `0cb0b69`, preset `small`, seed 1, randomized memory
latency. No core RTL or waiver file was changed. The quick tier selects
174 programs. All 174 instrumented runs fail because checks fire. This
is separate from their architectural tohost outcome. The run inserts
519 checks and leaves 101 existing checks waived or disabled.

| Firing group | Distinct IDs | Programs | First monitor cycle | Representative wave window |
|---|---:|---:|---:|---|
| TileLink A request legality | 2 | 174 | 3 | add, times 180 to 200 |
| TileLink D response legality | 6 | 2 | 878 | icache-alias, times 8930 to 8950 |
| Frontend TLB request valid hold | 1 | 2 | 446 | ae_ptw, times 4600 to 4640 |
| MSHR 0 replay queue valid hold | 1 | 1 | 1245 | ae_ptw, times 12550 to 12620 |

Wave times are raw FST timestamps. The clock period is 10. Separate wave
reruns reproduce all 10 IDs. Raw waves and build outputs remain local.
None of the 24 IDs in `SpinalChecks/boom/stream-dispositions.json` fires
in this run. The source review still records an incomplete mapping to
the original historical inventory. This does not close issue #5.

The two A IDs are `tilelink.request_legal:io_mem_a` and
`tilelink.request_legal:arbiter.io_down_a`. The first accepted reset fetch
at time 190 is Get, address `0x80000000`, size 6, mask `0x00`.
This is a core interface difference. A reset fetch alone reproduces it;
no particular retired instruction is needed. TileLink Get requires the
size-aligned mask, which is `0xff` on this eight-byte bus for size 6.
The monitor remains active. No CPU ISA or Spike conclusion follows from
this bus violation.

The six D IDs are `tilelink.response_legal:` at `io_mem_d`,
`tile.io_dmem_d`, `tile.dcache.io_mem_d`, `arbiter.io_down_d`,
`arbiter.io_ups_0_d` and `arbiter.ups_0_d`. The wave at time 8940
has an accepted ReleaseAck, size 6, source 2, param 1, denied 0 and
corrupt 0. TileLink requires ReleaseAck param 0. This is a simulation
platform defect, not a core response. SpinalHDL's `MemoryAgent.onC`
constructs `TransactionD(c)`, which copies the Release param, and changes
only the opcode before scheduling D. The private BOOM harness uses that
agent. Its external dependency still needs a generic fix and test.
No local response mask or replacement memory agent was added.

The frontend ID is `stream.valid_hold:tile.frontend.tlb.io_req`.
In ae_ptw, valid/ready is 1/0 at time 4610 and 0/0 at 4620.
`io_kill` is 0. `ifu/frontend.scala:95` forms valid from the current
stage-1 fetch, replay, clear and SFENCE conditions. This port does not
retain every offer until ready. This is a platform check-binding finding:
the strict Stream obligation does not describe this cancellable request.
A reviewed cancellation condition is still needed. The firing is retained.

The replay ID is `stream.valid_hold:tile.dcache.mshrs.mshrs_0.rpq.io_deq`.
In ae_ptw, valid/ready is 1/0 from time 12550, then 0/0 at 12610.
The branch-killable queue can remove speculative work without acceptance.
See `util.scala:377-436` and `lsu/mshrs.scala:135-142,273-299`.
This is a platform check-binding finding. The wave has flush=1 at time 12600 and valid=0 at 12610, with
branch mispredict mask zero. The cancellation follows the flush edge.
A binding must also retain the `uses_ldq` condition from `flush_fn`.
No broad flush exemption or waiver was added.

Rules: [TileLink 1.8.1, Get and ReleaseAck](https://starfivetech.com/uploads/tilelink_spec_1.8.1.pdf).
The two stream rules are the retained `stream.valid_hold` contract in
SpinalChecks. They are not RISC-V ISA rules. Spike has no internal stream
or TileLink response for comparison.

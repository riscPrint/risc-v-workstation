# Closed internal equivalence partitions

```sh
rvw formal equiv-partitions --gold old.v --gate new.v --top Unit \
  --reset reset --timeout 120 --max-partitions 16 --out internal-checks
```

This command first runs the existing closed whole-output equivalence flow.
It uses that flow's equal-width register-name and unique-leaf matching to select
internal observation points. It then projects each matched register pair to a
single output and proves that pair in a separate closed cone. It retains each
full state cone. It adds no assumptions that an internal boundary agrees.
MCP tool: `formal_equiv_partitions`.

`equivalent` requires the output proof and every matched internal observation
proof to close. `output_equivalence` records the original output result separately.
A failed internal relation makes the combined request inconclusive. It does not
turn an output proof into an output counterexample. Each partition records its
matched names, width, verdict and result path. Unmatched state remains inventoried.

The timeout covers the output proof, projection exports and all internal proofs.
`--max-partitions` is in 1..64. The default is 16. If more pairs match, the result
records the omitted count and stays inconclusive. All selected proofs run in
sequence. Native commands use `nice -n 10`. Give the CLI itself the same priority
when invoking it directly.

## Limits

These are independent closed state-cone proofs. They do not assume abstract
cutpoints or solve a cyclic cut-point dependency graph. They can repeat logic
and cost more than one whole-output proof. They require same-cycle register
relations after the declared reset and settle clocks. Retimed or recoded state
can fail that stronger relation while output equivalence still holds.

This increment accepts exported synchronous RTL. It does not add revision export,
memory abstraction, state recoding, clock gating, asynchronous reset or trusted
blackbox models. Use the existing `formal equiv` controls for those separate
supported contracts. A missing match is not an assumed state relation.

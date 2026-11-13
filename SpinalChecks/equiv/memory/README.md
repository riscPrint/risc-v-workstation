# Logical memory refinement

`rvw formal equiv --memory-spec` compares physical storage RTL with an
explicit logical word-memory model. The physical design can use arrays,
vectors or banks. Both sides use exact finite-memory lowering. The proof
compares their complete observable behavior after reset. It does not assume
that independent initial RAM contents are equal.

```sh
rvw formal equiv --memory-spec SpinalChecks/equiv/memory/spec.json \
  --gate SpinalChecks/equiv/memory/banked.v --top Banked \
  --out /path/to/new-refinement --timeout 60
```

The JSON contract states word width, address width, read latency, unwritten
word behavior, reset polarity and all seven interface ports. The generated
abstract memory keeps storage uninitialized. Reset clears only its per-word
valid bits. Each unwritten word reads as zero until written. Each write sets
that word's valid bit and stores all data bits. The candidate must implement
this same observable behavior. No state equality is inserted to force a pass.

Read latency zero is asynchronous. It sees the updated storage after a write
edge. Read latency one registers the old data at that edge. Reset clears the
registered read result in latency-one mode. Writes during reset are ignored.
The contract owns the clock and reset port names. `--reset-cycles` still sets
the harness reset duration.

The command writes `spec.json`, `abstract.v` and the usual equivalence proof
under `proof/`. The outer result is `rvw.memory-refinement/1`. It retains the
specification, model hashes and complete proof result. Only an underlying
`equivalent` result can earn `equivalent`. Inconclusive and negative results
stay distinct. MCP `formal_equiv` accepts the `memory_spec` path.

## Measured cases

All cases use eight logical words with eight bits per word. The native EQY
unbounded proof ran with `vex-equiv` and nice 10.

| Physical storage | Read latency | Result | Time |
| --- | --- | --- | --- |
| Two banks selected by low address bit | 0 | Equivalent | 4.268 s |
| One packed 64-bit vector | 0 | Equivalent | 4.271 s |
| Two banks with inverted read bank selector | 0 | Not equivalent | 4.251 s |
| Two banks with a registered read output | 1 | Equivalent | 5.028 s |

`results.json` records compact receipts. The original positive sources remain beside this README. To reproduce the
negative case, invert `ra[0]` in the final read-bank selector. To reproduce
the synchronous case, put a resettable read register around `Banked` and set
`read_latency` to 1 in a copied specification.

## What this flow can and cannot show

This proves refinement of the declared finite logical memory. It covers all
write/read addresses and data within that contract. It can find bank-selection,
packing, write-enable and read-latency errors. The storage implementation can
have different state names and layouts. Port declaration order is immaterial;
names, direction, width and signedness must match.

The current model supports one full-word write port, one read port, 1..64 data
bits and 1..8 address bits. It supports zero or one read clock of latency.
Other fields are rejected. Byte enables, multiple writes, arbitrary unwritten
read values, external coherence, ECC fault behavior and unbounded address
spaces are not modeled. Exact lowering can time out on larger memories.
This is a behavioral abstraction model, not a watched-address solver
abstraction for a large RAM. It does not qualify an entire core or replace
separate ISA and integration checks.

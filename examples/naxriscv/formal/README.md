# NaxRiscv arithmetic helper checks

`units.py` exports the pinned `DivRadix4` component and a multiplier built
with the core's `MulSpliter` and `AdderAggregator` helpers. It retains source
and selected-component hashes. It removes simulation entry points and
unrelated service definitions. It uses Scala 2.12.18 and released SpinalHDL
1.15.0. This does not qualify the complete core with its pinned development
SpinalHDL dependency.

```sh
rvw/.venv/bin/python examples/naxriscv/formal/units.py \
  --source /path/to/private/NaxRiscv --out /path/to/new-run --timeout 45
```

Source revision: `9f452d50560d02fb391bc8039f5453c54e0911af`.
Each generated module gets a database and a proposal with port-match evidence.
The runner explicitly confirms the reviewed canonical word interface.
`NaxMul` checks unsigned low-word multiplication. `NaxDiv` checks unsigned
quotient, including zero divisors. The transaction holds operands stable
and requires completion within `width/2+4` clocks. No divider source is changed.
Native steps use `vex-equiv`, `sbt-equiv` and nice 10. Each proof has its own
time budget. Proofs run in sequence.

| Word width | MUL | DIVU |
| --- | --- | --- |
| 8 | Proved, 2.290 s | Proved, 2.705 s |
| 16 | Inconclusive, 45 s timeout | Inconclusive, 45 s timeout |
| 32 | Inconclusive, 45 s timeout | Inconclusive, 45 s timeout |

Both eight-bit cases cover every operand pair in that configuration.
They do not prove the core's 32-bit units. The ledger is `results.json`.
Signed divide, remainder, high products, pipeline control, stalls and
whole-core ISA integration were not checked.

## Unsigned 32-bit transaction certificate

The separate [compositional proof](../../../SpinalChecks/c2rtl/README-composition.md)
now closes unrestricted unsigned quotient and remainder for the re-elaborated
32-bit helper. Run `step-invariant.py --complete` with that export. It checks
actual reset, base, active-step and progress logic, response and clock bindings,
and all arithmetic and prefix lemmas. It covers the first response after one
request with stable operands and no intervening reset or flush. Divide by zero
is included. The CBMC timeouts above remain unchanged. Signed conversion and
complete core integration remain outside this certificate.

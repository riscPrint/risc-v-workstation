# Native datapath binding proposals

The existing kit was run on databases built from the real multiplier export in
`MUL_UNIT.md`. Yosys built both databases. No fixture database rows were inserted.
The source revision was `9f70315deb3390b283995c5b8f1bd38215ecf52b`.
The arithmetic adapter used the documented eight-bit operand projection.

```sh
rvw query build-hdl /path/to/native/mul/dut.v --top dut --out /path/to/raw.db
rvw formal datapath --unit mul --db /path/to/raw.db --out /path/to/proposal --json
```

The kit found the actual `VexiiMul` helper component. It proposed the physical
ports `a`, `b` and `y`. These ports have widths 33, 33 and 64.
The result correctly records `width_consistent: false`.
A M-model word adapter is still required. See `native-kit-results.json`.

The word adapter's top was also renamed from `dut` to `VexiiMulLow` for
navigation. Its logic did not change. This exposes a multiplication name hint
for the kit's documented heuristic:

```sh
rvw query build-hdl /path/to/mul-low.v --top VexiiMulLow --out /path/to/word.db
rvw formal datapath --unit mul --db /path/to/word.db --width 32 \
  --out /path/to/word-proposal --json
```

The kit proposed `a`, `b` and `y` on that 32-bit interface with no missing
required roles. It rejected those widths for the wide child component.
See `adapter-kit-results.json`.

Both results are `needs_confirmation`. Both record `proof_ran: false`.
Neither proposal confirms the operation, signedness, operand projection, result
slice or reference model. A designer must review those details before using
the binding. The separate native arithmetic proofs remain in
`default-unit-results.json`.

This does not establish automatic extraction of an inline core pipeline area
or a complete core binding. The kit uses names and port structure.

The original native proof input SHA-256 is
`d3cdb037ef9a510012ef57f8043214ff8d135c9ba27e5204c0dc7d2279d0f354`.
The renamed adapter input SHA-256 is
`83eedc09be49611fb62d45cff93f13f5a1ab2d4baadfaeabb3f858034c3d8604`.
The databases remain in the private run directory.

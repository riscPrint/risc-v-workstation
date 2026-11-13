# Arithmetic composition lemmas

## Unrestricted split multiplier

`examples/vexiiriscv/formal/mul-composition.py` checks the real `VexiiMul`
helper from the pinned export in `MUL_UNIT.md`. It covers every signed 33-bit
operand pair and the complete result modulo 2^64. That domain includes both
signed and unsigned 32-bit instruction operands after their proper extension.
Instruction decode and result selection remain separate obligations.

The checker requires four exact RTL `$mul` bindings. It checks both operand
bit vectors, constant extension bits, signedness and result widths:

- Low 17 by low 17, unsigned, 34-bit product.
- Low 17 by signed high 16, 34-bit product.
- Signed high 16 by low 17, 34-bit product.
- Signed high 16 by signed high 16, 32-bit product.

Z3 closes the three product-range lemmas and the distributive expansion.
The mixed products fit signed 33 bits. Their 34-bit RTL results therefore
have equal top two bits. Those are the only assumptions in the composition
miter. They follow from the closed range lemma and the checked operand slices.
Yosys SAT checks the actual exported adder network with symbolic partial
products. It compares every output bit with the weighted signed sum.
The composition closes. A one-bit result mutant produces a counterexample.

This is an unrestricted RTL word-operator proof. It trusts the specified
signed and unsigned `$mul` semantics. It does not prove the multiplier gates
from a technology mapping or qualify a synthesis implementation. It does not
turn the earlier CBMC gate-level timeout into a gate-level pass.

```sh
rvw/.venv/bin/python examples/vexiiriscv/formal/mul-composition.py \
  --rtl /path/to/export/VexiiMul.v --out /path/to/new-composition --timeout 60
```

## Iterative divider invariant

`examples/naxriscv/formal/step-invariant.py` maps the actual `DivRadix4`
export. It requires and removes exactly the eight known synchronous state
cells. Each Q vector becomes an explicit input to a local transition lemma.
Each D expression remains the actual source logic. It refuses missing,
aliased or additional state. No initial-state equality is assumed.

The 32-bit native check closes these obligations:

- Reset clears busy and done.
- An idle request initializes the divisor, its triple and the quotient.
- Leading-zero skipping preserves the original numerator and starts remainder zero.
- An active nonzero-divisor step preserves `trial = digit * divisor + remainder`.
- The next remainder stays below the divisor.
- Numerator and quotient shift by two bits.
- Divisor and its triple stay fixed during an active step.
- The counter advances and completion occurs at its last value.
- The zero-divisor step appends quotient digit 3 and shifts the remainder.

The nonzero step preconditions are explicit: busy, not done, no reset or
flush, a nonzero 32-bit divisor, remainder below divisor, and a correct stored
triple. The base and reset obligations are checked separately in the same
miter. A one-bit remainder mutant produces a counterexample.

`division-invariant.smt2` separately closes the radix-4 prefix recurrence,
quotient width bound and uniqueness of Euclidean quotient and remainder.
These lemmas support the invariant `prefix = quotient * divisor + remainder`.

The result remains `step_proved`. The checker does not yet construct and
verify the complete transaction-level composition certificate. It therefore
does not report unrestricted 32-bit DIVU proved. The earlier complete 32-bit
CBMC run remains inconclusive. Zero-divisor transaction composition, signed
conversion and plugin writeback also remain open.

```sh
rvw/.venv/bin/python examples/naxriscv/formal/step-invariant.py \
  --rtl /path/to/export/DivRadix4.v --width 32 --out /path/to/new-step
z3 -smt2 SpinalChecks/c2rtl/division-invariant.smt2
```

All recorded native proofs used `vex-equiv` and nice 10. No proof exceeded
60 seconds. `arithmetic-composition.json` records source hashes, status,
preconditions, trusted primitives and negative controls. These receipts do
not establish whole-core correctness.

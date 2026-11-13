# C model to RTL checks

This native flow checks a small combinational RTL unit against a C reference.
It compiles and runs the C model for every input pair. It converts that complete
truth table to a Verilog reference. SymbiYosys checks one equality assertion with
free inputs. This is exhaustive enumeration, not C synthesis or symbolic C execution.

## Contract

Declare this contract before a run:

| Item | Supported value |
|---|---|
| RTL interface | One self-contained file; top `dut`; only `a`, `b`, `y` ports |
| Width and signedness | All three ports unsigned, same width; 1 to 4 bits |
| C interface | Pure, deterministic `uint32_t reference(uint32_t a, uint32_t b)` |
| C types | Driver supplies `uint32_t`; no model includes or external dependencies |
| Input domain | Every pair from 0 through `2**width - 1`; no excluded inputs |
| Output domain | 0 through `2**width - 1`; out-of-range results are refused |
| Overflow | Model must explicitly mask or reduce its output; RTL truncates to width |
| Latency | Zero cycles; no registers, latches, clocks or reset |
| Handshake | None; output must be valid for every input pair |
| Constraints | RTL assumptions, assertions and unsupported cells are refused |
| Bound | BMC depth 1; one combinational evaluation, not a sequential proof |

The examples use width 4. `add` returns `(a+b) mod 16`. `mul` returns
`(a*b) mod 16`. `shl` returns `(a << (b mod 4)) mod 16`.
All intermediate values fit in `uint32_t`. Shift counts stay below 32.
There is no signed overflow, signed shift or host floating-point arithmetic.
These C files are the reference. They are independent of the RTL implementation.

The caller must review the C model for purity and defined behavior. The flow uses
Clang UndefinedBehaviorSanitizer with recovery disabled on every enumerated call.
This detects common undefined operations, including invalid shifts. It does not
prove arbitrary C memory safety, initialization, purity or compiler correctness.
A proof compares RTL with the table produced by this reviewed native C program.
Do not use an unreviewed C program as an oracle.

## Run

Use the workstation Python environment and native `clang`, `yosys`, `sby`,
`yosys-smtbmc`, `yosys-witness` and `yices-smt2` on PATH.
The existing pinned OSS CAD Suite installer supplies the formal tools:
`scripts/install.sh --with-formal`. This flow adds no tool installation.

From the workstation root:

```sh
rvw/.venv/bin/python SpinalChecks/c2rtl/check.py \
  --model SpinalChecks/c2rtl/examples/add.c \
  --rtl SpinalChecks/c2rtl/examples/add.v --width 4 \
  --timeout 30 --out /tmp/c2rtl-add-new
```

Repeat with `shl` or `mul`. Use a new output directory for each run.
The command writes one JSON document to stdout and saves `result.json`.
It keeps the source copies, SHA-256 identities, native tool paths and hashes,
tool versions, command logs, C table, generated miter and SBY job.
`check/engine_*/trace*` holds a counterexample when the solver emits one.
`--timeout` is a per-command wall limit. Timeout and cancellation stop child processes.
Output reuse is refused. This experimental result cannot grant a regression gate
acceptance or cached C8 result reuse. Tool libraries and launcher payloads remain
trusted installed dependencies; their complete trees are not captured.

| Status | Exit | Meaning |
|---|---|---|
| `proved` | 0 | SBY PASS with exit 0 for all pairs, after interface and state checks |
| `counterexample` | 1 | SBY FAIL with exit 2 and a generated witness testbench |
| `inconclusive` | 3 | Missing tool, timeout, invalid model, unsupported RTL or incomplete evidence |

For zero-state RTL, the depth-1 assertion covers all input valuations. It does not
establish pipeline timing, protocol behavior or correctness in an enclosing core.
The tests change add to XOR, remove the shift-count mask, and offset the product.
Each mutant must produce a counterexample. Other tests refuse invalid C shifts,
out-of-range C outputs, state, assumptions, signed ports, undriven outputs,
black boxes and timeouts.

```sh
nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests/test_c2rtl.py -q
```

## Decisions and limits

- Use SymbiYosys as the fallback when a native EBMC/HW-CBMC build is unavailable.
  Upstream provides [native source build instructions](https://github.com/diffblue/hw-cbmc/blob/main/COMPILING.md).
  Do not install an unqualified or unpinned compiler through the workstation installer.
- Truth-table conversion gives a complete reference for this small domain. It has
  exponential cost. Widths above 4 are deliberately refused.
- SoftFloat starts at binary16. Two unrestricted operands need `2**32` table rows.
  This fallback does not support that domain. FP is not run and is not proved.
  Future support needs symbolic C translation or a native HW-CBMC backend. It must
  declare rounding mode, NaNs, subnormals, signed zero, flags and latency first.
- This is the first increment of epic #19. There is no BOOM binding, sequential
  datapath support, signed model support, `rvw formal` subcommand or MCP endpoint.

### Oracle type and FP boundary

The driver requires the exact C function pointer type with a C11 static assertion.
It refuses signed, wider and floating-point results and different argument types
before it runs the model. Division by zero, signed overflow and a negative signed
left shift have independent negative tests. Each must stop before SBY starts.
An output mask does not make an undefined intermediate operation valid.

FP arithmetic remains unsupported. A future SoftFloat adapter must declare the
format and operation, a rounding mode for each call, tininess detection before or
after rounding, subnormal handling, signed zero, NaN payload and signaling NaN
rules, and the five exception flags. The RTL must return both result bits and
flags. It must use the same declared latency and handshake contract. Host C
floating-point types cannot supply this oracle. No FP rounding result is claimed.

## Symbolic real-width backend

`rvw formal datapath` uses Yosys `techmap` and CBMC. The flow converts the
closed Boolean netlist to C. It gives the same symbolic operands to this model
and the C reference. CBMC bit-blasts both models. It checks result equality,
C safety and loop unwinding. No truth table is built. Install CBMC with
`brew install cbmc`. Native validation used CBMC 6.11.0 and Yosys 0.70.

```sh
rvw formal datapath --rtl mul.v --model SpinalChecks/c2rtl/models/mul32.c \
  --reference-tree SpinalChecks/c2rtl/models --reference-include . \
  --width 32 --out /tmp/mul-check
```

The top must be `dut`. It has unsigned `a`, `b`, `y` ports of width 8, 16, 32
or 64. Optional ports are `c` of the same width, `rm` of width 3 and `flags`
of width 5. The reference has this exact type:
`uint64_t reference(uint64_t a, uint64_t b, uint64_t c, uint8_t rm, uint8_t *flags)`.
It must return an in-range result. It must have defined behavior. It must not
constrain symbolic inputs, call nondeterministic functions or use host FP.
The reference source and its dependencies are trusted specification inputs.

For a sequential transaction, set `--latency N`. The DUT must also have scalar
`clk`, `reset`, `start`, `done` ports. Reset is synchronous and active high.
The harness holds operands stable, resets for one clock and pulses start for
one clock. It checks that done is false before N clocks and true at N clocks.
It checks the result at N clocks. Iterative units can use this contract.
Back-to-back requests and arbitrary initial transactions are outside this contract. Registers start unconstrained.
Generated clocks, latches, memories, blackboxes, RTL assumptions and unsupported
cells are refused. The Boolean translator refuses combinational loops.

`--unwind` limits C loops. Unwinding assertions remain on. A safety or unwinding
failure makes the result inconclusive. Only complete success for every property
can produce `proved`. Only result, flag or completion failures can produce
`counterexample`. Results and traces are in `cbmc.log` and `result.json`.
The MCP tool is `formal_datapath`.

The `models/` directory contains independent RISC-V MUL, MULH, MULHSU, MULHU,
DIV, DIVU, REM and REMU specifications for XLEN 32 and 64. They include division
by zero and signed overflow behavior. The same operations also exist at widths
8 and 16 (`mul8.c` ... `remu16.c`) for width-reduced proofs. CBMC does not
finish a 32-bit gate-level multiplier or divider equivalence in minutes. Write
the unit with a width parameter, prove the 8- or 16-bit instance, and keep
32-bit simulation and co-simulation evidence. A reduced-width proof covers the
generator at that width only. It is not a proof of the 32-bit instance. Unsigned arithmetic avoids C signed
integer overflow. They use CBMC's 128-bit integer support for high products.

SoftFloat wrappers cover F/D add, multiply, fused multiply-add, divide and
square root. Each sets after-rounding tininess and clears flags before the
call. `--rounding 0..4` selects the RISC-V rounding mode. NaNs are canonical.
Subnormals and signed zeros use SoftFloat behavior. Bind the `flags` output.
`--case` splits on operand a: all, finite, normal, nan, infinity, zero or subnormal.
A case proof applies only to that case. It is not a whole-domain result.
Fetch SoftFloat outside the repository and pin revision
`07ebd29db0cfb55723a79fbbffe99103ef38e305` from
<https://github.com/ucb-bar/berkeley-softfloat-3>.
Use `--reference-tree` for its root, `--reference-source` for each C dependency,
and `--reference-include` for each include directory. The flow copies and hashes
the tree before the run. The `softfloat.py ROOT OPERATION` helper prints the dependency arguments and
writes a CBMC platform header in the external tree. It checks the pinned revision
and selects the RISC-V specialization. Conversion wrappers cover F32/F64 format
changes and signed/unsigned integer conversions at the same width. F32/F64 format
changes use the 64-bit interface; F32 occupies the low 32 bits.
Native FP DUT qualification remains open.

### Variable-latency transactions and project bindings

Use `--max-latency N` instead of `--latency` for iterative units. The check resets
for one clock and pulses start for one clock. Operands remain stable. The check
compares result bits and optional flags at the first sampled done. It also proves
that done occurs within N clocks. N must be 1..256. This is one transaction.
It does not check throughput, backpressure or overlapping requests.

A project can keep its module and port names. Pass `--binding unit.json`:

```json
{"top":"Multiplier", "ports":{"clk":"clock", "reset":"rst", "start":"go",
 "done":"valid", "a":"lhs", "b":"rhs", "y":"result"}}
```

Omitted ports retain their canonical names. Every port still passes the existing
width and direction checks. Only explicitly listed constant input ports can be removed. Other ports remain
subject to the same interface checks.
The `rvw.formal.datapath_binding.bind` function supplies the same rename operation
for Python callers. `formal_datapath` accepts `binding` and `max_latency`.

### Bit manipulation and scalar hash models

`models/riscv_zb.h` supplies 32-bit and 64-bit models for `andn`, `orn`, `xnor`,
`rol`, `ror`, `cpop`, `clz`, `ctz`, signed and unsigned min/max, `rev8`, `orcb`,
`clmul`, `clmulh`, `clmulr`, `sextb`, `sexth` and `zexth`. Use the named width
wrapper, for example `andn32.c`, with `--reference-tree models --reference-include .`.
These names select a unit operation. They are not instruction decoders.

`riscv_hash.h` supplies SHA-256 sigma/sum and SM3 P0/P1 at XLEN 32 and 64.
It supplies SHA-512 sigma/sum at XLEN 64. The SHA-256 and SM3 RV64 wrappers
sign-extend the low-word result. The source is the
[RISC-V scalar crypto 1.0.1 specification](https://docs.riscv.org/reference/isa/v20240411/unpriv/scalar-crypto.html).
Use wrappers such as `sha256sig0_32.c` or `sha512sum0_64.c`.
Additional AES, SM4 and RV32 split SHA-512 models are described below.
Functional models do not check execution time.

SoftFloat compare wrappers add `f32_eq`, `f32_lt`, `f32_le` and their F64 forms.
The result is 0 or 1 in the selected datapath width. Exception flags come from
SoftFloat. EQ uses quiet comparison. LT and LE use signaling comparison.
These wrappers do not use host floating-point arithmetic.

The compare model tests use `RVW_TEST_SOFTFLOAT` for the pinned external tree.
They check F32/F64 EQ/LT/LE on signed zeros, infinities, NaNs, subnormals and
exception flags. A native symbolic F32 EQ fixture checks result and flags over
all operand bits. An invalid-flag mutant must produce a counterexample.
This fixture does not qualify project FPU add, multiply, FMA, divide, square root
or conversion RTL. Those operations retain their separate proof obligations.

### AES, SM4 and split SHA-512 references

The model library adds AES32ESI/ESMI/DSI/DSMI for each byte selector 0..3.
It adds AES64ES/ESM/DS/DSM, inverse MixColumns, KS2 and KS1I for each legal
round immediate 0..10. The AES S-box uses arithmetic over GF(2^8). These models
use no host cryptographic library. Native reference tests compose AES32 and
AES64 instructions into full AES-128 encryption and decryption. They compare
known vectors and independent OpenSSL results.

SM4ED and SM4KS have each byte selector at XLEN 32 and 64. The RV64 forms
sign-extend the 32-bit result. Reference tests compose encryption, decryption
and key expansion against the standard SM4 vector. Split SHA-512 RV32 models
cover SIG0H/L, SIG1H/L and SUM0R/1R. Tests reconstruct the 64-bit transforms.
These definitions follow the scalar crypto specification linked above.

Select fixed-immediate wrappers such as `aes32esmi_bs0.c`, `aes64ks1i_r9.c`,
`sm4ed_64_bs2.c` and `sha512sig0h.c`. Reserved opcode/immediate decoding is
outside these functional models. The KS1I wrappers do not expose reserved
immediates 11..15. Timing and whole-core crypto qualification remain separate.

A project binding can select an opcode or byte selector without an RTL wrapper:

```json
{"top":"CryptoUnit", "ports":{"a":"rs1", "b":"rs2", "y":"result"},
 "constants":{"operation":3, "byte_selector":0}}
```

Use the project's numeric control encodings. Constants must name input ports.
Values must fit their widths. The binding replaces those input bits throughout
the mapped model. It retains every other interface and driver check. The proof
applies to the recorded constant controls, not all opcodes. The captured binding
hash records that scope. It does not remove state, hide assumptions or change
output widths. The normalized model must still provide required reference and handshake ports.

For a unary unit with no second operand, declare `"unused_inputs":{"b":64}`
in the binding. The width must match the chosen reference width. Only reference
operands `b` and `c` can be added this way. They stay unconstrained reference
arguments and connect to no DUT logic. A reference that depends on an omitted
hardware operand still produces a counterexample. This feature does not set an
operand to zero or reduce the reference input domain.

### Additional bit-manipulation forms

The Zb library also supplies `bset`, `bclr`, `binv`, `bext`, `sh1add`, `sh2add`,
`sh3add`, `xperm4`, `xperm8`, `pack`, `packh` and `brev8` at XLEN 32 and 64.
ZIP/UNZIP references are RV32-only. RV64 references add unsigned-word ADD and
shift/add forms, SLLI.UW, ROLW/RORW, CPOPW/CLZW/CTZW and PACKW. Word rotates
and PACKW sign-extend their 32-bit result. Unsigned-word arithmetic discards
the upper source word before the operation.

Use files such as `bset32.c`, `sh1add_uw64.c`, `rolw64.c` and `zip32.c`.
Register/immediate forms with the same functional transform share a reference.
The bit index or rotation count uses its defined low bits. Instruction and
reserved-immediate decoding remain project obligations.

XPERM selectors outside the element count produce zero. Native symbolic tests
check complete 32-bit nibble and 64-bit byte permutation units. Selector mutants
must produce counterexamples. Integer/polynomial tests also check all model
families against independent Python expressions. These are functional checks.
They do not establish instruction timing or complete core-extension compliance.

### Mixed-width ports and source format cases

A binding can adapt a physical unit to the reference word size. This example
checks a physical F32 input against an F64 output with `--width 64`:

```json
{
  "top": "Convert",
  "ports": {"a": "operand", "y": "result", "flags": "flags"},
  "unused_inputs": {"b": 64},
  "input_widths": {"a": 64}
}
```

The extra high input bits remain symbolic. The C reference must ignore them.
For `f32_to_f64`, the SoftFloat wrapper casts `a` to F32. No input bits are
truncated or constrained by this adapter. Use `--case-width 32` to split on the
F32 input when the reference word has width 64. Case `normal` selects finite
nonzero normal inputs. Other existing cases keep their meaning.

A one-bit comparison result can use `"output_widths": {"y": 32}` with
`--width 32`. The adapter pads the result with zeros. It does not change its
physical width. Input widening supports only `a`, `b` and `c`. Output widening
supports only `y`. Flag and handshake widths remain fixed.

### Definedness before comparison

The Boolean C backend tracks literal X/Z values through each mapped gate and
register update. It proves that observed result, flag and completion bits are
defined before it can return either `proved` or `counterexample`. Controlling
values can mask unknown inputs. Unobservable unknown branches do not block a
proof when the propagation rules establish defined outputs. A reachable unknown
or an incomplete definedness check makes the result inconclusive. The result
records `rtl_definedness` and retains each CBMC definedness assertion.

This propagation is conservative at reconvergent logic. It can refuse a circuit
whose outputs are defined. Initial registers keep their existing arbitrary
binary state. Use the separate initialization security app to check whether
uninitialised state can reach outputs after reset. The datapath check is not a
four-state simulation.

Native small fixtures now check F32-to-F64 conversion, one-bit F32 comparison,
source-format cases and signaling-NaN flags against the pinned SoftFloat tree.
They do not qualify a project's FPU. The SoftFloat dependency helper includes
the exception handler used by RISC-V NaN conversion macros.

## Real HardFloat units

Use [the native HardFloat runner](README-hardfloat.md) for binary16/binary32 unit
exports against pinned SoftFloat. It checks result bits, rounding and flags.
Case restrictions, transaction bounds and inconclusive runs stay explicit.

## Confirmed example bindings

`rvw formal datapath --unit ... --confirm` now runs one reviewed proposal.
See [binding review and evidence](../../rvw/src/rvw/formal/README-datapath-kit.md).
These native runs use actual exported or extracted arithmetic boundaries.
All listed passes include definedness. No proposal alone earns a pass.

| Core | Boundary and input domain | Compared result | Result |
| --- | --- | --- | --- |
| VexRiscv | Extracted product, 8-bit unsigned operands | Low 8 bits | Proved |
| VexRiscv | Extracted divider, all 32-bit dividends, divisor zero | All 32 bits | Proved |
| VexiiRiscv | Helper multiplier, signed 8-bit operand projection | All 32 bits | Proved |
| VexiiRiscv | Default DivRadix, all 32-bit dividends, divisor zero | All 32 bits | Proved |
| NaxRiscv | Standalone 8-bit helper configurations, all operands | 8-bit MUL and DIVU | Proved |
| NaxRiscv | Standalone 16- and 32-bit helper configurations, all operands | Word MUL and DIVU | Inconclusive, 45 s each |

The VexRiscv product-cell and divider extraction runners remain under
`examples/vexriscv/formal/`. The VexiiRiscv export runners remain under
`examples/vexiiriscv/formal/`. Generate those arithmetic adapters first.
For proposal discovery, give the adapter module an arithmetic name such as
`VexMulLow` or `VexDiv`; a module rename changes no arithmetic logic. Build
its database with `rvw query build-hdl`. Review `--unit` output, then use
`--component '' --confirm` on the root word adapter with its generated C model.
Use its documented latency bound. The explicit edited-binding interface can
also bind a module without name hints.

See `confirmed-bindings.json` for the reviewed Vex bindings and proof-input
hashes. See [NaxRiscv's runner and width ledger](../../examples/naxriscv/formal/README.md).
These checks do not cover instruction decode or complete core pipelines.
Unrestricted 32-bit arithmetic remains open. The optional VexiiRiscv bitpasta
IPC fault remains a confirmed counterexample in the separate findings.

## Arithmetic composition

The [composition checks](README-composition.md) now close the unrestricted
VexiiRiscv split-multiplier composition at RTL word-operator level. This trusts
RTL `$mul` semantics. It is separate from the CBMC gate-level timeout.
The actual NaxRiscv 32-bit divider base, active-step and progress lemmas close.
Its complete transaction composition remains open. Negative result and
remainder mutants produce counterexamples. No complete-core pass follows.

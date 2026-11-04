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

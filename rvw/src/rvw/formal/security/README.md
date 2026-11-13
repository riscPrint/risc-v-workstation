# Hardware leakage checks

This increment targets #20. It uses a hardware threat model separate from C8.
Assets are secret input registers. The attacker controls public inputs and sees
selected digital observations. The trusted boundary contains the reference model,
reset procedure and observation adapter. Keys, analog power, noise and tool-input
attacks are outside this model.

The IFT transform accepts a flattened Yosys JSON netlist after `techmap; simplemap`.
It adds `__t` ports and value-sensitive taint transfer logic. It tracks data and
mux control flow through Boolean gates and rising-edge registers. Clock is public.
Apply a public reset before observation. No implicit state initialization or
implicit declassification occurs. Unsupported cells, blackboxes, X/Z constants,
multiple clocks and undriven bits cause an error. No structural path is a proof.
Reconvergent paths can overtaint because the transform loses correlations.

Two implementations use the same gate transfer rules: the native Yosys
`rvw_ift` pass in `SpinalChecks/security/`, and a JSON reference transform.
Neither implementation is the upstream CellIFT pass. This first increment
uses Boolean gates rather than CellIFT word-level shadow cells.

## Commands

```sh
yosys -p 'read_verilog design.v; hierarchy -top top; proc; flatten; techmap; simplemap; write_json mapped.json'
rvw formal security ift mapped.json --top top --out top_ift.v
rvw formal security contract campaign.json --out run-security
```

The contract manifest contains `elf`, `platform` (a Spike platform JSON), `shim`,
`stop_pc`, `max_steps`, `adapter_tree`, `adapter_command`, `secret_registers`,
`observations`, `unmodeled_channels`, and `cases`. Paths are relative to the manifest.
`adapter_command` is an argv list. `{tree}`, `{case}` and `{out}` select its
captured source tree, case request and response. `timeout` defaults to 30 seconds
per adapter run and must not exceed 300 seconds. See `examples/security/adapter.py`.
Cases contain `registers` (decimal register strings to XLEN integers) and a
`public_key` for shared context. The checker also groups all nonsecret registers.
It assumes equal initial memory and reset state from one captured ELF.

Spike runs each case independently to the explicit stop PC. The contract exposes
retired PCs and architectural memory addresses, but hides operand data. Equal
contract traces form comparison classes. Different selected RTL observations
inside one class are a violation. This is a sequential address contract in the
style of Revizor. It does not emulate speculative execution in Spike. RTL adapters
must observe transient effects beyond retirement to detect those effects.

Adapters return `complete`, `effects`, `cycles` and `observations`. Effects include
`pc`, `insn`, `rd`, `rd_wdata`, `mem_addr`, `mem_rmask`, `mem_wmask`, `mem_wdata`.
They must equal the independent reference for that input. Cycles are strictly
increasing positive retirement cycle numbers from reset release. Observations
must include exactly the declared channels as nonnegative integers. Each adapter
must define reset, observation sampling and simulation tool identity. The generic
runner captures the manifest, platform, ELF, shim and adapter source tree. It does
not certify external adapters or automatically capture all adapter dependencies.

Timing checks currently cover integer ADD only. They compare elapsed cycles from
the previous retirement, within the same public context and address contract.
This can find a data-dependent latency witness. Pipeline stalls can also affect
this measurement. A clean sample is not full Zkt compliance. No branch, load or
store is silently classified as covered. `zkt_verdict` is inconclusive if no ADD
comparison occurs. Contract `no_violation` applies only to the named observations.

Exit codes are 0 for sampled `no_violation`, 1 for a witnessed `violation`, 3 for
`inconclusive`, and 2 for IFT input errors. Missing or mismatched RTL evidence is
inconclusive. A violation can coexist with incomplete cases; `errors` preserves
those cases. No comparison class gives inconclusive. No proof result is produced.

Source policy is set by the `__t` input bits in the IFT testbench. Sink policy is
set by the `__t` outputs it checks after reset. There is no declassification API.
Public reset clears taint only when the actual logic resets that register.

## Basis and limits

- [Revizor contracts](https://microsoft.github.io/side-channel-fuzzer/latest/topics/contracts/): executable leakage contracts and equal-trace comparison classes.
- [CellIFT](https://github.com/comsec-group/cellift-yosys): value-sensitive gate taint instrumentation. This transform is a small independent implementation.
- [RISC-V scalar cryptography specification](https://github.com/riscv/riscv-crypto/blob/main/doc/scalar/riscv-crypto-scalar-zkt.adoc): data-independent execution latency. ADD is the initial tested subset.

The current native experiment has four explicit leak seeds and one clean control.
It does not estimate detection on arbitrary designs. It has no noise model beyond
deterministic simulation. Cache coherence, real predictors, physical timing,
analog effects, DMA, debug authentication, lifecycle, Smepmp, and power/reset
crossings remain unmodeled. Issues #20, #138, #195 and #198 remain open.

## Two-copy formal contracts and reset analysis

`rvw formal security pair --manifest pair.json --out pair-proof` checks a
project-owned `rvw.security-pair/1` description. MCP tool: `formal_security_pair`.

```json
{"schema":"rvw.security-pair/1", "kind":"noninterference", "top":"Unit",
 "rtl":"unit.v", "clock":"clk", "reset":"reset",
 "ports":{"clk":{"direction":"input","width":1},
          "reset":{"direction":"input","width":1},
          "secret":{"direction":"input","width":32},
          "pc":{"direction":"output","width":32},
          "cache_hit":{"direction":"output","width":1}},
 "secrets":["secret"], "architectural":["pc"], "observations":["cache_hit"],
 "adversary":"controls input data", "unmodeled_channels":["power","analog noise"]}
```

The check instantiates two copies. Secret inputs are independent. All other
inputs, including clock and reset, are shared. State starts under each copy's
RTL initialization rules. The existing proof flow holds reset for one clock.
At each later rising edge, equal architectural observation prefixes require
equal current observation samples. Once the architectural prefixes differ, the
pair has no further obligations. Architectural sample timing is part of this
contract. This is a causal prefix contract. It does not align retirement events
or infer a sequential ISA contract. Use the existing Spike campaign for that.

For a declared Zkt unit, use `kind: "constant_time"`, list its `operations`,
leave `architectural` empty, and select only timing outputs in `observations`.
The proof checks the bound unit for all shared public input sequences. Operation
names document the binding. They do not validate instruction decoding or select
an instruction subset inside the DUT. No physical leakage result is implied.

Use `kind: "initialization"` with empty `secrets` and `architectural` lists to
check initial-state independence after reset. Both copies then receive identical
inputs. A counterexample shows that a declared output can still differ. This
checks uninitialized-state effects without the conservative IFT transfer rules.

Optional `reset_values` maps output names to unsigned expected values. Assertions
check both copies at the sample after each reset edge. `reset_coverage` records
declared bits, total declared output bits and proved bits. Proved bits are zero
unless the complete proof passes. These are output reset checks. They do not
count all internal registers or establish reset coverage for the whole design.

The command captures the plan and self-contained RTL. It rejects DUT assertions,
assumptions and nondeterministic cells. The existing single-clock proof flow
checks the generated wrapper and records native evidence under `proof/`.
Missing tools, a timeout or incomplete evidence cannot produce `pass`.

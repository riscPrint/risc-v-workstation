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
implicit declassification occurs. The JSON transform models X/Z constants as
conservatively tainted bits. The native plugin refuses X/Z constants. Unsupported
cells, blackboxes, multiple clocks and undriven bits cause an error. No structural path is a proof.
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

## Digital entropy interface

The existing `rvw formal apps` command and `formal_apps` MCP tool accept an
`entropy` property. It binds `seed` (32/64-bit output), `illegal` (scalar output),
and scalar input events `access`, `write`, `allowed`, `refill`, `fatal`.
The project must expose a continuous seed word and clock-sampled control events.
`write` identifies a read-write CSR operation. `allowed` is the independently
bound access policy. `refill` means fresh entropy was accepted on that edge.
`fatal` reports the project health interface's fatal event.

Example property inside an `rvw.formal-apps/1` plan:

```json
{"id":"seed_protocol", "kind":"entropy", "seed":"seed_word",
 "access":"csr_access", "write":"csr_write", "allowed":"access_allowed",
 "illegal":"illegal", "refill":"fresh_word", "fatal":"health_failure"}
```

The monitor checks an illegal response for read-only or denied access. It checks
zero entropy bits outside ES16 and zero upper bits for RV64. It checks that a
successful poll consumes ES16 unless fresh entropy is accepted on that edge.
It retains BIST until a poll and requires DEAD after a fatal event. DEAD persists
until reset. Custom and reserved bits are not constrained. Equal successive
entropy values are allowed. The monitor does not measure randomness or check
that a refill event represents independent physical entropy.

The digital rules use the
[seed CSR contract in scalar crypto 1.0.1](https://docs.riscv.org/reference/isa/v20240411/unpriv/scalar-crypto.html#_the_seed_csr).
CSR address decoding, privilege-policy generation, ignored write data, physical
health tests and entropy certification retain separate proof obligations.

## Dynamic PMP and ePMP access safety

The formal app kind `pmp` checks grants against a declared PMP CSR-bank binding.
Use the existing `rvw formal apps` command or `formal_apps` MCP tool. Example:

```json
{"id":"pmp_access", "kind":"pmp", "address":"access_address",
 "request":"request", "grant":"grant", "size":"log2_bytes",
 "privilege":"effective_privilege", "operation":"access_kind",
 "mml":"mml", "mmwp":"mmwp", "latency":1,
 "entries":[{"config":"pmpcfg0_byte0", "address":"pmpaddr0_field"}]}
```

The physical address width is 4..64 bits. Each config is eight bits. Each PMP
address field is physical width minus two bits. Entries appear in priority order.
The monitor handles OFF, TOR, NA4 and NAPOT with four-byte PMP granularity.
`size` is a two-bit log2 byte count. `operation` is read=0, write=1, execute=2.
`privilege` is the effective U=0, S=1 or M=3 mode. Reserved values are denied.
Bind effective privilege after any project MPRV logic.

The check includes full-access containment, first-touch priority, locked base
PMP permissions, MMWP default deny and the MML shared-region permission table.
The ePMP table follows
[Smepmp 1.0](https://docs.riscv.org/reference/isa/v20240411/priv/smepmp.html).
Base PMP reserved R=0/W=1 encodings must not be exposed as active legal rules.
The monitor treats an enforced reserved encoding as denied.

Config and address ports can change each clock. With `latency: 0`, the check uses
current policy. With latency 1..64, it stores the request-time permission and
valid bit for each response slot. Later CSR changes cannot grant access to an
old denied request. This is a fixed-latency interface contract. It does not track
transaction IDs or permit variable response reordering. It checks grant safety,
not that every legal request eventually completes. An always-denying unit can
satisfy this safety property.

The CSR bank is an explicit trusted observation binding. The monitor does not
prove CSR address decoding, WARL legalization, MML/MMWP stickiness, RLB or locked
write suppression. It does not check DMA/debug initiators unless the project
binds their requests and effective policy. Those remain separate obligations.
## Prove an exported RTL policy

```sh
rvw formal security prove --rtl unit.v --top top \
  --policy examples/security/policies/secure-path.json --out /tmp/secure-proof
```

This command maps self-contained RTL with Yosys, applies the Boolean IFT pass,
binds a policy and runs the existing unbounded ABC PDR assertion flow.
It checks data and control taint through reset and sequential state.
The policy names public `clock` and active-high synchronous `reset` inputs.
`sources` must be input ports. `sinks` must be output ports. Both lists must be
nonempty. `adversary` describes input control. `unmodeled_channels` lists the
channels outside the proof. The result retains this policy and the C7 proof.
MCP tool: `formal_security_prove`.

A `declassifier` can name a scalar public input. Sink taint is permitted while
this input is high. It is checked again when the input goes low. A release pulse
does not permit data to stay in the sink after release. The policy owner must
justify release authorization. This command does not prove that authorization.
Unsupported cells, memories, blackboxes and unknown state models remain errors.
The JSON transform models literal X/Z as tainted bits. Reconvergent taint can produce a conservative false alarm.

Use `kind: constant_time` and list `operations` to declare a Zkt operation subset.
Name timing control outputs such as done and ready as sinks. The proof checks
these outputs on every cycle, for all source values. Result data is not a timing
sink. The project must bind the declared operations to this unit. This does not
certify full Zkt, physical timing, resource scheduling or enclosing core behavior.

### Static access isolation

`kind: isolation` checks an independent resolved access policy. It does not use
taint. `signals` maps `request`, `grant`, `write`, `execute`, `privilege`, `master`
and `address` to top ports. `privilege` has two bits. The request, grant, write
and execute signals each have one bit. `access_bytes` declares a fixed access
size. `regions` is a priority-ordered list of byte intervals with inclusive
`start` and exclusive `end`. Each region has `permissions`, a list of objects
with numeric `master`, numeric `privilege` and Boolean `read`, `write`, `execute`.
Unlisted permissions deny access. Execute and write together are refused.
The first region touched by a request must contain the full request. This catches
partial boundary overlaps and address wrap. A grant for an unpermitted request
fails the proof. Reset is public and synchronous, as in the IFT flow.

The project must resolve PMP/ePMP configuration into this independent policy.
This proves static observed access isolation only. It does not check CSR decode,
Smepmp rule derivation, policy updates with outstanding requests or unbound bus
masters. Those obligations remain open. No whole-system security claim follows.

## Bounded real-core checks

Set `"mode": "bmc", "depth": 8` in a two-copy manifest to use a small bound.
The result records `proof_kind` and `depth`. A bounded pass covers only that
bound. The default remains an unbounded ABC PDR proof.

`examples/vexriscv/formal/pair-smoke.py` prepares two checks from a supplied
VexTop export. The memory check treats `dBus_rsp_data` as secret and compares
bus-valid observations while the declared architectural prefixes agree. The
initialization check gives both copies the same inputs and independent initial
state. It compares fetch-valid, fetch-PC and data-command-valid observations.
Both checks use one public reset clock. No bus protocol assumptions are added.
These are bounded controls on the supplied export. They do not certify the
source revision or establish core security. See the example's recorded limits.

## Internal state sources and bounded taint

A secure-path policy can name synchronous register nets in `internal_sources`.
Each selected Q bit has taint one on every sample, including after public reset.
The original value register and its next-state logic stay unchanged. This is an
ongoing secret-state model. It does not model a one-time CSR write or secret
erasure. A source must resolve entirely to synchronous register Q bits.
Missing nets, non-register nets and repeated names cause an error.
Input sources can be empty when the policy names internal state sources.

Set `mode` to `bmc` and `depth` to an integer from 1 through 128 for a bounded
taint check. Results record `proof_kind: bounded` and the depth. The default
remains unbounded. A bounded pass says nothing about later samples or source
activation. No bus fairness or program constraints are inferred.

Set `memory_map: true` to lower finite memories with Yosys before instrumentation.
This preserves every memory word as register state. It is not a memory abstraction.
Region-specific source alignment is unsupported and causes an error.

# Literal UPF safety subset

```sh
rvw formal upf --source SpinalChecks/upf/isolation.upf --bindings SpinalChecks/upf/bindings.json --out generated
```

MCP: `formal_upf`. The supported source starts with `upf_version 2.1`.
It accepts literal `create_power_domain NAME -elements {PATHS}` declarations.
It accepts one `set_isolation` per domain with explicit `-domain`,
`-applies_to outputs`, binary `-clamp_value`, `-isolation_signal` and high/low
`-isolation_sense`. These command options follow the
[OpenROAD UPF command documentation](https://openroad.readthedocs.io/en/latest/main/src/upf/README.html).
The importer does not invoke Tcl. It rejects substitutions, command separators,
nested lists, unknown commands, unknown options and unsupported strategies.
Line continuation and full-line comments are supported. Supply networks,
level shifting, clock gating and general Tcl are refused.
This is an explicit subset, not general IEEE 1801 compatibility.

`rvw.upf-bindings/1` supplies the top module and each declared domain's monitor
signals. Use `event_model=always_on_sampled`. The clock must stay active when the
domain powers off. Reset is sampled active high. Bind `power_good` to an
independent availability observation. Pack all monitored isolated output bits
into `value`. Declare its width. Bind raw output validity and consumer use.
The UPF control path supplies `isolate`. No signal discovery or completeness
proof is claimed. The example is a fixture binding, not an actual core binding.

Generated immediate assertions check the selected clamp, isolation before power
loss, invalid raw outputs while off, and safe consumer use. Off-state internal
storage remains unconstrained. Load `monitors.sv` and `binds.sv` with the DUT in a
frontend that supports SystemVerilog bind. `result.json` records source/binding
hashes, normalized intent and domains with no generated monitor. No monitor
means `no_checks`, exit 3. Generation returns 0 when a monitor is generated.
No compilation, verification or physical-power result is implied.

## Retention and supply-state tables

`set_retention` accepts exactly `-domain`, `-retention_power_net`,
`-retention_ground_net`, `-save_signal {PATH high|low}` and
`-restore_signal {PATH high|low}`. All names must be literal. This is a sampled
level-control subset. Edge controls and retention supply availability modeling
are not supported. See the [Accellera low-power overview](https://accellera.org/images/resources/videos/Low_Power_with_UPF_2013.pdf)
for the retention concepts. The importer does not implement all UPF semantics.

The optional `retention` binding table maps every strategy name to `width`,
`clk`, `reset`, `power_good`, `functional_use` and `state`. Controls come from UPF.
The monitor requires save while powered, a saved value before power loss, no
functional use before restore, and the saved value one sample after restore.
Off-state storage is unconstrained. Retention supplies are recorded as names.
Use `retention.upf` and `retention-bindings.json` as a small fixture example.

`create_pst NAME -supplies {SUPPLIES}` and
`add_pst_state STATE -pst NAME -state {STATE_NAMES}` define legal supply tuples.
Each tuple has one literal state name per supply. The optional `psts` binding
table maps each table to `clk`, `reset` and `supplies`. Each supply has `signal`
and an explicit `states` map from labels to unique unsigned integer codes.
The generated monitor checks membership in the declared tuples. It does not
infer voltage, state transitions or physical retention from those codes.
Native SBY tests prove good retention/table fixtures and reject seeded faults.

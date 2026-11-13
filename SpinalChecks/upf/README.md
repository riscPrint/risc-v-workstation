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
The importer does not invoke Tcl. It accepts literal quoted or braced words,
semicolon and newline command separators, line continuation, and comments at
command starts. A comment after a command needs a separator first. Separators
inside quoted or braced words remain part of the word. These lexical rules
follow the [Tcl command syntax](https://www.tcl-lang.org/man/tcl8.6/TclCmd/Tcl.htm).
It rejects substitutions, nested braced lists, other backslash escapes, unknown
commands, unknown options and unsupported strategies. Supply networks,
level shifting, clock-gating Tcl commands and general Tcl are refused.
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

## Power-switch gating

`create_power_switch` accepts a declared domain, one input supply port, one
output supply port, one control port and one on-state. Port arguments are
`{LOCAL_NAME RTL_NET}`. The on-state is `{STATE INPUT_PORT CONTROL}` or the
single negation `!CONTROL`. General Boolean expressions are refused.
The [OpenROAD UPF reference](https://openroad.readthedocs.io/en/latest/main/src/upf/README.html#create-power-switch)
describes these command options.

The optional `switches` binding map has one entry per switch. Each entry names
`clk`, `reset`, independent `input_good` and `output_good` observations and a
positive `settle_cycles` bound. The monitor checks output availability after
that many consecutive samples of the requested supply state. It permits
transients before that bound. The control path and sense come from UPF.
The observation clock must remain active. This checks a project settling
contract. It does not model analog power ramps or physical gating cells.
Clock-gating Tcl commands remain unsupported. See the companion bindings below.

## Literal command examples

The following source has the same supported domain semantics as the braced form:

```tcl
upf_version "2.1"; # comment starts after a command separator
create_power_domain PD -elements "core bus"
```

Each command still passes the UPF command and option checks. A trailing
`source`, `puts`, variable substitution or command substitution is not executed.
Unrepresented syntax is an error. This change adds lexical forms only. It adds
no clock-gate import, dynamic Tcl evaluation, new UPF strategy, or physical check.

## Explicit clock-gate companion bindings

The optional `clock_gates` binding map adds sampled gate checks beside declared
UPF domains. This imports project gate observations. It does not add a UPF Tcl
command. Each gate declares `domain`, `wake_cycles`, `clk`, `reset`, `enable`,
`source_low`, `clock_edge`, `work_pending` and `wakeup`. Paths must be literal.
Use an always-on observation clock and a positive wake bound up to 1024 samples.
The existing clock-gate monitor checks source-low enable changes, no edges or
pending work while disabled, and bounded wakeup. These are declared sampled
contracts. They do not establish glitch freedom between samples.

Use `clock-gates.upf` with `clock-gates-bindings.json` as a fixture example.
The report lists imported gate names. Six binding/generation tests passed.
Four native Icarus cases passed: a legal wake sequence and three detected
faults for enable phase, edges while off and late wake. No core or physical
gate binding was tested. Clock-gating Tcl commands remain unsupported.

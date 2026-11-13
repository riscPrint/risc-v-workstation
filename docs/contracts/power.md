# Power intent contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Sampled power intent generation

`rvw.power-intent/1` declares project domains, initial supply states, legal
transitions, selected checks, data widths, wake bounds and DFT access constraints.
It requires `always_on_sampled` observation semantics. See
`SpinalChecks/power/README.md` for each module's transaction and reset contract.
`rvw.power-generation/1` reports `generated`, state encodings and DFT binding
inventory. A resolved path confirms presence only. Neither format supplies C7
proof, physical-power, scan-coverage or ATPG evidence. UPF import is unsupported.

## Literal UPF isolation import

`rvw.upf-subset/1` preserves literal domain elements and explicit output isolation
strategies from the supported UPF 2.1 command subset. `rvw.upf-bindings/1` maps
monitor inputs and complete output vectors with an always-on sampled clock.
`rvw.upf-generation/1` records input hashes, normalized intent and unmonitored
domains. Generation is not proof or physical power evidence. No generated monitor
returns `no_checks`, exit 3. Unsupported commands and Tcl constructs are errors.
Clock-gating import and physical supply modeling remain unsupported.

## Literal retention and supply tables

`rvw.upf-subset/1` can also retain `retention` and `psts` declarations.
`rvw.upf-bindings/1` has optional maps with the same names. Every imported
retention strategy and power-state table needs a binding. Retention uses
sampled high/low save and restore controls. Supply tables compare declared
integer state codes against legal tuples. Neither feature infers analog
availability or voltage semantics. Generation retains the existing hashes,
limitations and no_checks behavior.

## Literal power-switch gating

`rvw.upf-subset/1` can include `switches` from single-control
`create_power_switch` declarations. The optional `switches` map in
`rvw.upf-bindings/1` names sampling clock/reset, independent input/output
availability and positive `settle_cycles`. After that many stable request
samples, output availability must match input availability and the declared
control sense. Names of supply ports do not establish physical connectivity.
No analog ramp, glitch or clock-gating semantics are inferred.

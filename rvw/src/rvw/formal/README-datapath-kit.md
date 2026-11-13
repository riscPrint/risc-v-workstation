# Datapath binding kit

```sh
rvw formal datapath --unit mul --db design.db --width 32 --out binding-proposal
rvw formal datapath --unit fpu-add --db design.db --out fp-proposal --json
```

This mode reads a captured SpinalDB database. It searches component paths,
module names, class names and Area names for arithmetic unit hints. It then
checks component port names, directions and optional widths. It writes
`proposal.json`. It does not elaborate RTL or run a solver.

The result is `needs_confirmation` when candidates exist, or `no_candidates`.
Every candidate includes the source ports, matched hints, proposed `binding`,
missing roles, ambiguous roles and unbound ports. No candidate is approved.
Review operation and signedness, formats, reset, protocol, latency and extra
ports. Confirm the reference model. FP bindings also require rounding and flags.

Copy the chosen `binding` object to a binding file after review. Supply missing
ports, constants and unused reference operands as the real unit requires. Use
the existing proof command with `--rtl`, `--model`, `--width` and `--binding`.
Choose `--latency` or `--max-latency` from the actual protocol. Proposal mode
rejects proof inputs. It cannot run a guessed binding.

Units include `mul`, `mulh`, `mulhu`, `mulhsu`, `div`, `divu`, `rem`, `remu`,
`fpu-add`, `fpu-mul`, `fpu-fma`, `fpu-div`, `fpu-sqrt` and `fpu-convert`.
MCP tool: `formal_datapath_kit`. The existing `formal_datapath` tool runs proofs.

## Limits

Names and port shapes cannot establish arithmetic semantics. An integrated plugin
can appear as an Area inside a core. Such a candidate may have no usable module
boundary. Extract that boundary before binding it. The kit does not cut internal
signals or invent a transaction adapter. Mixed-width conversions need explicit
format and binding review. Components with unrelated arithmetic names can be
candidates. The report retains those hints for the designer to inspect.

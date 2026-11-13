# Datapath binding kit

```sh
rvw formal datapath --unit mul --db design.db --width 32 --out binding-proposal
rvw formal datapath --unit mul --db design.db --width 32 --component cpu.mul \
  --confirm --rtl unit.v --model mul32.c --out confirmed
```

This mode reads a captured SpinalDB database. It searches component paths,
module names, class names and Area names for arithmetic hints. Each proposed
port match prints its name, direction, width, source path and matching rule.
`proposal.json` retains the same evidence as `port_matches`. Names and port
shapes do not establish operation, signedness or protocol semantics.

Without `--confirm`, the result is `needs_confirmation` or `no_candidates`.
No solver runs. Review operation and signedness, formats, reset, protocol,
latency, extra ports and the C model. FP bindings need rounding and flags.

After review, use `--confirm` with RTL, a C model and width. Select one
candidate with `--component` when needed. Use `--component ''` for the root
module. Missing or ambiguous roles require an edited binding. The command
writes `confirmed-binding.json`, then runs the existing datapath proof under
`proof/`. It preserves the proof exit code. Confirmation alone is not a pass.
The proposed evidence and confirmed binding are printed on stderr in JSON
mode, so stdout retains one proof result.

To edit a proposal, copy its `binding` object to a file. Add the ports,
constants and unused reference operands that the real unit requires. Supply
that file with `--binding`. Use `--unit ... --confirm --binding edited.json`
to retain proposal evidence, or use the existing proof interface with
`--rtl`, `--model`, `--width` and `--binding`. The proof validates the binding
against mapped RTL. An edited binding is not replaced by name hints.
Choose `--latency` or `--max-latency` from the actual unit protocol.

MCP tool `formal_datapath_kit` accepts `confirm`, `component`, `binding`,
`rtl`, `model`, width and latency settings. `formal_datapath` remains the
explicit binding proof interface.

## Limits

An integrated plugin can appear as an Area without a module boundary.
Extract that boundary before binding it. The kit does not cut internal
signals or invent a transaction adapter. Mixed-width conversions need
explicit format review. Unbound ports remain proof obligations. Confirmation
does not constrain them or waive arithmetic or definedness checks.

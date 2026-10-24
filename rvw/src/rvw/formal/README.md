# rvw formal

`rvw formal bmc` checks assertions from reset. `from-sim` checks them from a VCD or FST
state. `xprop` checks whether unknown state can reach selected signals. See
[SpinalChecks](../../../../SpinalChecks/README.md) for commands and limits.

Every flow requires one rising-edge clock and synchronous state controls. Asynchronous
reset/load/set/clear controls and latches are refused. A result applies only to the selected depth,
input ties, assumptions, and reset settings. Missing replay state starts free and can cause
spurious failures. Exit 0 means `pass`. Other written results exit 1. Invalid input exits 2.

## Decisions

- Xprop validates `--filter` before elaboration. A malformed regex exits 2 with
  the filter and parser error. MCP reports that input error. No result is written.
- Each flow copies RTL, include files, checks JSON and replay VCD/FST before the first
  probe. `inputs/original/` holds the shared `Capture.file` copies. `inputs/frontend/` holds RTL copies
  whose literal include paths point to copied includes. Nested includes, absolute paths
  and symlink targets are copied. Missing or ambiguous includes, macro-computed include
  paths and file-reading system tasks such as `$readmemh` are refused. Comments and string
  literals do not count as task calls. A macro-built file read is refused by the frontend
  dependency check below. This conservative scan also checks inactive branches, so their
  include files must be available.
- Input capture keeps `..` until after symlink resolution. The selected lookup path,
  resolved source, literal symlink targets, byte count and hash come from the capture record.
  `result.json` includes that record as `input_capture`. Later source edits and link changes
  cannot redirect the proof.
- Every flow captures Yosys, SymbiYosys, the selected solvers and replay converters before
  elaboration. Reachability also pins Yices. Subprocesses use absolute command bindings.
  SymbiYosys gets explicit Yosys, SMTBMC, witness and selected ABC paths. Solver lookup
  uses private command bindings and the saved environment. The supported oss-cad-suite
  launchers retain their runtime settings but keep these bindings first on PATH, including
  the Python launcher. Each command binding restores the caller's captured Python
  environment before dispatch, then the release launcher applies its own settings.
  Unknown SMTBMC shell launchers are refused.
- `Capture.tool` requires a successful `--version`. `yosys-smtbmc`, `yosys-witness` and
  `yosys-abc` do not provide it. Local adapters report the captured content hash for these
  commands. Their underlying files and detected release payloads also get byte and metadata
  checks. The shared API has no option for a tool with another version interface.
  `tools`, `tool_bindings` and `input_capture` use start-of-command capture identities.
  No version command runs after the proof. Before publication, tool verification checks
  hashes, inode identity and change timestamps. Replacement or edit-and-revert produces
  `unknown` with an `input_not_captured:tool:...` cause. Missing tools refuse the command.
- Supported proof engines are `smtbmc` with Yices, Z3, Bitwuzla, Boolector, CVC4, CVC5
  or MathSAT, and `abc`. `smtbmc:abc` is refused before proof, including in portfolios
  and with extra options. The installed Yosys 0.64+174 ABC SMT parser crashes on an
  ordinary counter. The refusal names the captured Yosys version and ABC hash.
  This engine remains unsupported on other releases until it is validated.
  `abc:bmc3` requires a sequential model. Optimization can remove all state, even
  from clocked RTL. If ABC reports a combinational network and the run errors,
  the command refuses with exit 2 and no `result.json`. The message directs the
  user to rerun with `--engine smtbmc:yices`. No proof or pass is inferred from
  that ABC error. A portfolio can still earn a pass through another engine.
  Other engines refuse capture because their executable dependencies are not defined here.
  No formal result is cached.
- Replay converts its sealed state VCD to FST with the pinned converter before Yosys
  loads it. This prevents an internal converter lookup from changing the selected tool.
- The first frontend run reports its file dependencies with Yosys `-E`. Every file it reads
  must be a copied input. A missing or unsupported report, or a read of any other file
  (also one built by a macro), causes exit 2 with no `result.json`. That run applies the
  proof's defines and writes one RTLIL model after `hierarchy -check -top` and `proc`.
  Port and state-control checks describe that model. Clock and target probes, replay
  state loading, undriven-bit handling and the proof all read that same model.
  Later probes do not preprocess live RTL again.
- `result.json` records `input_snapshot.files` and `input_snapshot.artifacts`.
  Each file records its original lookup path, resolved target, copied path and SHA-256
  from the captured bytes. Rewritten frontend copies also record their paths and SHA-256
  values. Artifacts record the model, generated wrapper and replay proof inputs, each hashed
  once before a tool reads it. The run does not hash its private copies again: it owns
  `--out` under its lock (C8 threat model). A result applies to these copied bytes. Edits
  to live inputs after the copy do not change the proven design. A new run is needed to
  check those edits.
- All three flows check state cells in every elaborated module after `hierarchy -check -top`
  and `proc`, before `prep`, flattening, ties or state loading can remove them. The check
  uses the proof's defines. Async flip-flops, latches and unsupported state cell types,
  including fine-grained gate cells, cause exit 2 with no `result.json`. A tied inactive
  reset or unused state does not bypass this check. Asynchronous memory reads remain
  supported; memory async reset ports must be tied to zero. `rvw cov prove` uses the same
  classification (`async_state_problems` in `common.py`). `multiclock off` cannot model
  state events between clock edges, so converting asynchronous state with `async2sync`
  cannot earn a pass.
- Xprop runs `setundef -undriven -undef` after flattening and before X instrumentation.
  Unwritten registers, undriven wires and undriven bus bits become explicit X values.
  Real inputs keep their input status. Driven flip-flops keep Yosys xprop's initial-state
  model: a bit without a known initializer starts X until a write defines it. Reset and
  initial values still define state where the RTL supplies them.
- BMC and replay use two-state formal values. An undriven bit can take either value;
  these flows do not prove that a signal is X-clean. Replay state missing from the waveform
  remains free, including registers with RTL initializers. Use xprop to check X propagation.
- Port direction, width and signedness come from Yosys JSON after `hierarchy -check -top`
  and `proc`, in the first elaboration with the proof's defines (`SYNTHESIS` for xprop).
  Wrappers keep all elaborated input bits free, except explicit ties and clock/reset controls.
  Packed dimensions and integer types use their full bit count. Port offsets and ascending
  ranges are normalized at instance connections, which preserve bit order. Unreadable metadata,
  failed probes, multi-bit clock/reset ports and inout ports are refused.
- Xprop target widths also come from Yosys JSON after flattening and exposure. No Verilog
  text parser sets proof widths. The remaining Verilog text reader maps failed assertions to
  source/check labels only. RTLIL readers count assertions, report replay state coverage, and
  change memory INIT values for the explicit replay memory mode. They do not infer port types.
- Failure mapping first matches the solver's full path to a copied RTL file. A basename
  maps only when it names one copied file. An ambiguous basename leaves the failure's
  module, check and source unset. Summary and engine failures are merged by full path
  and line, so one file cannot hide another file's failure at the same line.
- Failure cycles use the first elaboration's property metadata. A known rising-edge
  assertion has `cycle = replay_offset + step - 1`. Unclocked properties, missing metadata
  and mixed property types on one source line have `cycle: null`. The solver step remains.
- Replay removes design register and memory initial values before loading the waveform.
  It also removes design time-zero assumptions. Current Yosys represents these as zero-width
  triggered `$check` cells. Older Yosys uses `$initstate` and `$assume`. The flow handles both
  before it creates its own assertion samplers. The transitive `$initstate` selection can also
  remove runtime assumptions derived from `$initstate`. This broadens the replay environment.
  `removed_initial_assumptions.txt` and `result.json` list the removed cells.
- A proof engine's pass needs a separate bounded reachability check. This applies to BMC,
  replay, X-propagation, and engine portfolios. The check uses the actual prepared proof model,
  keeps its initial values and assumptions, removes assertions and design covers, and adds
  one cover enabled only at the final checked step. It uses `smtbmc:yices` regardless of the
  proof engine. Thus Yices is required to earn a pass with ABC too. `reachability/` holds the
  separate solver evidence. An unreachable final step or missing reachability evidence gives
  `unknown`, exit 1. A timeout or solver error cannot earn a pass.
- Reachability means at least one path satisfies the assumptions through this bound. It does
  not show that each assertion's enable condition is reachable. It does not establish
  satisfiability after the selected bound.
- VCD has whitespace-separated tokens. Line breaks do not delimit value changes. The parser
  validates the complete header and the body through the selected timestamp. It preserves
  binary X and Z values. It supports nested scopes, equal-width aliases, memory scope
  hoisting, `$dumpvars`, `$dumpall`, and `$dumpon`. It refuses dump gaps (`$dumpoff`), real,
  event and string data, malformed or unsupported commands, conflicting alias widths,
  duplicate variable paths before or after memory hoisting, ranges that disagree with widths,
  backward times, and unknown clocks or multiple edges at one time when counting cycles.
  Timescales must be explicit and have multiplier 1. Other multipliers are refused because
  Yosys replay takes an absolute time with one unit. An ambiguous default scope needs `--scope`.
- FST conversion runs with `rvw.common.proc.run_group`. It first writes a temporary VCD and
  checks the converter exit status. This needs space for the decoded trace, but prevents a
  failed conversion from supplying partial replay evidence. VCD parsing itself reads only
  the required prefix.
- `--out` is validated before taking the directory lock or deleting old evidence. An invalid
  output path leaves existing files intact. Once a valid directory is locked, a new run removes
  the old `result.json`, so a failed run cannot expose an earlier result as its own.

## Validation limits

- Tests use small Verilog designs with real Yosys, SymbiYosys, Yices, ABC, Verilator, Icarus,
  VCD and FST tools. No BOOM simulation or proof was repeated for the current flow. Earlier
  BOOM timings and results do not validate it.
- Regressions keep these review cases:
  - an async-reset design that gave a false pass at depth 8 (all three flows now refuse it);
  - an unwritten register that xprop counted as X-clean (Icarus shows the X after six clocks);
    BMC and replay tests check that undriven or missing state cannot pass by taking only zero;
  - a live RTL or include edit between probes that changed the proven width (each run proves
    its copy; a new run on the edited input fails);
  - two modules with the same RTL basename (only the failing module's check is reported);
  - a macro-built `$readmemh` (refused by the frontend dependency check);
  - ABC's combinational-network error after optimization (exit 2 with a Yices retry command;
    a portfolio keeps another engine's verdict).
- Other tests cover traced and missing registers, contradictory assumptions, assumptions that
  become unsatisfiable at later steps, and positive reachability evidence; integer, packed,
  parameterized, signed and non-ANSI ports, proof defines, replay ties, unreadable port metadata
  and failed probes; async loads, set/clear controls, latches, tied and unused child state,
  fine-grained cells, memory async reset controls and asynchronous memory reads; nested and
  symlink includes and refused dependencies; tool replacement, edit-and-revert and PATH changes
  after capture; Python forwarding wrappers for Yosys and Yices; the `smtbmc:abc` refusal; and
  the BOOM replay script's shell arguments.
- Installed interpreter libraries, shared libraries and tool data remain trusted runtime
  inputs. This capture does not copy or sandbox a complete installed toolchain.

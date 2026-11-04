# Porting notes

## Mapping from Tywaves to SpinalHDL

| Tywaves/Chisel concept | SpinalWaves implementation |
| --- | --- |
| Chisel/CIRCT HGLDD production | Post-RTL walk of `SpinalReport.toplevel`; JSON matches `tywaves-rs/src/hgldd/spec.rs` |
| HGL modules | Final `Component.definitionName`, after Spinal's RTL module deduplication |
| Module instances | Final child `getName()` and emitted child `definitionName` |
| Bundle/record | HGLDD struct object, referenced by `type_name`; `'{` value operands contain physical RTL leaves |
| Vec | `unpacked_range`, with ascending logical indices represented by operand order; packed range describes each ground element |
| Area | Struct grouping derived from Spinal's ownership chain; no RTL scope is introduced |
| ChiselEnum | `SpinalEnumCraft.getEncoding` after inference; one enum ID per definition/encoding pair |
| Scala source locations | Two elaborations, second with all component classes in `debugComponents`; first retained `ScalaLocated` frame |
| Constructor parameters | Scala primary-constructor reflection and matching stored fields; primitive/string field values only |
| TyVcd and VCD rewriting | Vendored tywaves-rs, exercised by `tools/spinalwaves-check` |
| Waveform UI | Vendored surfer-tywaves using the local Rust dependency |

## Scala implementation

`HglNaming` is the shared API for SpinalTrace. Bundle names and Vec decimal indices come from the Data tree, with Area boundaries from Spinal's ownership chain. RTL paths always use actual signal and instance names. Fixed-point raw members have empty field names in Spinal; the naming helper follows their Data owner transparently.

The emitter groups component instances by the final definition name, producing one module object for each RTL definition. Each child instance also carries explicit `port_vars`, `children` and source type information. This preserves distinct Scala shapes and constructor parameters when Spinal deduplicates physically identical RTL from different Scala components. The Rust patch honors these instance overrides without sharing mutable scope trees between instances. Struct names are allocated uniquely, including paths whose underscore-joined spellings collide. Vec operands and fields are ordered numerically, including indices above 9. Named declarations reported as pruned, zero-width leaves, and unnamed leaves are omitted. Surviving fields of a partially pruned Bundle remain a struct. A Vec with pruned indices or unequal surviving element shapes becomes a struct with decimal field names, preserving lookup paths without inventing missing traces.

Bool, Bits, UInt and SInt retain their widths and natural Scala type names. Bundle class names, Vec element types, Stream payload types and Flow payload types are included in `source_lang_type_info`. Direction is shown where all leaves agree; register roots carry `Reg`. Enum maps use the actual resolved encoding, including custom and one-hot codes. Enum values outside signed 64-bit range fall back to ground signals without an enum map because the upstream schema stores enum keys as `i64`.

SFix, UFix and AFix are represented by their raw ground signals, with descriptive fixed-point type metadata. SFix/UFix have simulation regressions; AFix metadata has no separate runtime fixture. Surfer's default display remains raw binary/integer; scaling and signed decimal rendering are not added by this port.

`SpinalWaves.elaborateWithLocations` runs the generator and configured transformation phases twice. The discovery pass stops before reflection naming and the RTL backend using the public `phasesInserters` hook. This avoids a discarded backend pass renaming shared singleton enums. Only the second pass generates RTL. It does not force line comments or change signal retention. Regressions compare the generated Verilog byte for byte with ordinary elaboration under deterministic header settings, including a singleton enum.

Spinal's backend may append enum element suffixes when it allocates names for multiple encodings. HGLDD uses reflected source val names where available and the actual inferred encoding's values. This keeps labels such as `Idle` stable without editing RTL. Spinal 1.15.0 can emit duplicate localparams when a non-native enum default is combined with another encoding; the multi-encoding example uses a native default and explicit encodings. Same-width assignments between differently encoded enum signals can become direct RTL aliases in stock Spinal, so the example drives independent state registers with explicit enum literals.

The simulation wrapper retains generated RTL and runtime assets under the configured workspace root's `tmp/spinalwaves-rtl-*` directories, matching SpinalSim's lifetime requirements for report paths and initialization files. These are removed when the caller cleans that workspace, rather than before the first simulation.

## Source location limits

Locations come from Spinal's first retained stack frame. Stack traces carry a line but no column, so columns are `1`. Default lookup roots are `src/main/scala` and `src/test/scala`, relative to the process working directory. Add roots explicitly for external source trees. `SourceLocator` falls back to the bare file name when it cannot find a source file; HGLDD canonicalizes that fallback to an absolute path, which may not exist. Library-created signals can point into Spinal library sources or Java reflection frames rather than the caller's declaration, as the contract retains Spinal's first filtered frame. Duplicate bare source filenames use the first root and sorted matching path.

## Known limitations

- The location/elaboration helper supports Verilog and SystemVerilog and preserves the selected mode. Only Verilator with VCD is supported by the simulation wrapper. FST and other simulation backends are outside this port.
- A typed root includes only named leaves that survive Spinal RTL pruning. It does not preserve absent state by modifying RTL.
- Memory arrays, memories' contents, blackbox internals and arbitrary generated backend temporaries have no special typed model. Ordinary named scalar leaves remain visible where emitted.
- Struct objects describe the surviving shape, rather than promising that every field of the original Scala class is present.
- Constructor parameter values are best effort. Unstored parameters and nonprimitive values can have names/types without values. Module definitions use a representative instance; per-instance source types, fields and parameters are carried by instance overrides.
- The generator must be deterministic across the two elaborations. Classes introduced only by custom/backend phases after the discovery cutoff cannot be discovered, so their source stack traces may be unavailable.
- The simulation helper follows SpinalSim's allocated test name, configured test directory and waveform prefix, including directories outside the compilation workspace. `SimLayout` requires a unique VCD scope matching the top module name and reports ambiguity explicitly.
- The viewer build and command-line startup are tested headlessly. Interactive rendering has not been manually validated.

## Third-party sources and patches

- `third_party/tywaves-rs`, origin `jarlb/tywaves-rs` at `215ff16f41742bffa8185cc5996741b13f498bb4`, retains Apache-2.0. `TyVcd::find_trace` now resolves typed root/field paths after consuming real scopes.
- The same library now honors the HGLDD schema's existing `Instance.port_vars` and `Instance.children` overrides. `Instance.source_lang_type_info` is a compatible optional schema extension for instance class names and parameters. Overrides apply after canonical module expansion on deep-copied scope trees, so shared RTL definitions can retain distinct per-instance Scala shapes. Explicit empty overrides stay empty. No other library algorithms were changed.
- `surfer-tywaves`, origin `jarlb/surfer-tywaves` at `5a8755b5e06f37884b166e0302547f07a51e1106`, retains EUPL-1.2 and all vendored submodule licenses. Only the Cargo dependency path and lockfile change to use the local tywaves-rs. Its rendering/source code is unchanged.
- `tools/spinalwaves-check` and `scripts/install.sh` are new tools, rather than upstream patches. The checker additionally detects silent drops and missing traces that upstream rewriting tolerates.

The full patch rationale, submodule origins, build evidence and upstream behaviors are in [docs/RUST_PORTING.md](docs/RUST_PORTING.md). Original imports are committed separately from local changes so the patch boundary can be reviewed with git. In particular, upstream Surfer rewrites to `<top-module>.vcd` in its current directory; run it from a directory where that file is disposable.

## Post-review fixes (2026-10-19)

- `SourceLocator` skips JVM frames (`java.`, `jdk.`, `sun.`, `javax.`) and the SpinalWaves/SpinalTrace entry
  points, so the toplevel's default `clk`/`reset` point at the user code that compiled the design instead of
  `DirectConstructorHandleAccessor.java` or `SpinalWavesSim.scala`. When a file name exists in several
  packages, the file under the frame's package directory wins. Source roots are indexed once.
- HGLDD `hgl_loc.file` indexes are 1-based into `file_info`, as CIRCT emits them (they were 0-based).
- `SpinalWavesSim.doSim` arms Spinal's `SimTimeout` (`SimGuard`, default 10,000,000 sim time units, i.e. 1M cycles at
  `forkStimulus(10)`; `simTimeout = None` or env `SPINAL_SIM_TIMEOUT=0` disables). A hung testbench otherwise keeps the
  clock running and writes an unbounded VCD (an orphaned test run once wrote >200 GB).

## Limit ownership

Interactive validation: [#83](https://github.com/riscPrint/risc-v-workstation/issues/83). Vendored backend behavior: [#120](https://github.com/riscPrint/risc-v-workstation/issues/120). Database integration: [#69](https://github.com/riscPrint/risc-v-workstation/issues/69).

Retained limit: The listed pruning, deterministic two-pass generation, source lookup, parameter reflection and typed-model restrictions remain in force. FST viewer support does not imply FST support in the simulation wrapper.

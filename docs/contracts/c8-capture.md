# C8. Input capture and result generations

### Threat model (2026-10-24)

The tools protect against honest mistakes in normal work. A result must never grant a pass,
match, accept or exclusion without enough evidence.

- Gate accept requires committed base and candidate revisions. A clean checkout at a commit
  counts as that commit. An otherwise passing dirty candidate gives `tests: "pass"`,
  `verdict: "inconclusive"` and `not_accepted_reason: "uncommitted"`, with compatibility
  cause `candidate_not_committed`. A rejecting dirty candidate stays `reject`.
  Commit the change, then run the gate again.
- Inputs, tools and caches stay stable during a command. Mid-run edits, edit-and-revert races,
  tool swaps, cache tampering and hostile inputs are outside this threat model.
- Normal mistakes remain in scope: stale files, wrong options, missing tools, interrupted
  builds, resume, cancellation, and concurrent runs with separate outputs.
- Unknown or incomplete evidence gives `inconclusive` with
  `input_not_captured:<name>`. It cannot earn passing-result reuse.

1. **Capture once.** Read each file input once. Save its bytes and compute SHA-256 from those
   bytes. Parse and run tools on the saved copy. Capture gzip and FST bytes before conversion.
2. **Bind claims.** Report paths, hashes, revisions and tool identities from the saved record.
   Do not replace captured claims with later reads of the source.
3. **Identify tools once.** Resolve each tool name and hash its executable at command start.
   Invoke the selected executable. Keep its invocation name when this changes its mode, as
   with `clang++`. Verify tools once before each publication. A cheap file stat check is
   sufficient under the stable-tool rule. A detected change refuses publication.
4. **Identify designs.** Use a commit plus a verified clean checkout, private captured sources,
   or the complete generated RTL input described below. Raw file bytes and the Git index
   determine cleanliness. `git status` alone does not detect `--assume-unchanged` edits.
   Missing dependencies or exceeded capture limits refuse the identity.
5. **Use complete keys.** Cache keys include all result-changing inputs, run options and saved
   environment values. Unknown dependencies disable reuse. `Capture.cache_key(options)`
   returns no key unless the caller sets `complete=True` and capture succeeds. Bump the key
   namespace when an identity contract changes. Old keys become misses.
6. **Publish generations.** Write a result set in a fresh directory. Publish it with one atomic
   pointer or rename. Never modify a published generation. Readers pin one generation and
   refuse missing members. Resume writes a new generation. C4 records its input generation IDs.

The Python APIs are `rvw.common.capture.Capture` and
`rvw.results.generation.publish` / `open_current`. See `rvw/src/rvw/common/README.md`.
`rvw.capture/1` records files, trees, Git refs, tools, environment and problems. File records
hold source and resolved paths, private copies, SHA-256, size, execute bits and symlink targets.
Tree records also hold directories and tracked deletions. Broken links and unreadable inputs
refuse capture. Private copy names do not enter keys. Keys use strict canonical JSON with
sorted string keys. `CaptureError` cannot be ignored to grant a verdict.

RiscvSim identifies a design with `rtl_sha256`, the SHA-256 of the exact generated Verilog
file used by Verilator. It includes RVFI monitor RTL in this file. External include and memory
data files are unsupported. The launcher holds the `boom` lock through sbt and JVM exit. It runs sbt offline for each
launch. It does not freeze
or identify the sbt classpath. Changes to sources, dependencies and elaboration tools that
change the design also change the emitted RTL.

The simulation identity also includes the RiscvSim repository commit and dirty flag, captured
ELF bytes, model and run options, native toolchain identity, and relevant environment values
such as `SPINAL_VERILATOR_FLAGS`. Dirty harness sources cannot earn passing-result caching.
Native cache keys use a new namespace and Spinal's RTL-based key. Native entries need a
verification receipt. An interrupted build cannot leave a reusable entry. Tools are identified
once at start and checked before each native receipt or C1 result publication.

### Regression input declarations

`input_complete=true` declares that the adapter inputs, stimulus files, environment and tools
cover the run. The default is false. Unknown dependencies give
`input_not_captured:adapter_dependencies`. Identity output alone does not prove completeness.

BOOM accept requires clean committed checkouts. Dirty candidates run in place and can reject.
Shared checkout execution is serialized.
Its adapter identity records generated RTL and native build digests. Every C1 result must
match those digests before it can count as evidence. Stored plans retain declared stimulus
file identities and reject changed file bytes, even when option path strings stay the same.
Base and candidate commit IDs identify report revisions. RTL digests identify equal designs.

Regression job identity version 10 can reuse conclusive results across core commits and dirty
flags when the complete `/2` adapter document claims all of: a 64-hex `rtl_sha256`, a full
committed `source.tools_rev`, `source.tools_dirty: false` and a 64-hex
`tools.native_build.sha256`. These claims must match each C1 result. Source-specific
`source.core_*` claims prevent this mode. All other adapter document fields, harness bytes,
ELF bytes, declared files, tools, environment and options still enter the key. The core source
fields and captured Git ref selectors are report metadata in this mode. They do not enter the
model key. Other adapters retain source-based keys. Dirty harness sources cannot cache results.
Reused C1 results keep their original source in `reused_from_source` and publish the selected
source in `source`. C3 names the selected source. Old job keys miss the cache.
With this complete RTL identity, conclusive failures can also enter the cache. Reuse retains
the original failure status, signature and source. It cannot turn a failure into a pass or
waive a new failure. Incomplete results are never cached. Source-based keys still cache only
passes. Use `--no-cache` to request fresh simulations.
RTL identity elaboration still runs. Reuse skips simulation for cached jobs.
The runner sets `RVW_CAPTURE_SOURCE_ENV` to the configured `source_env` name.
RiscvSim native identity namespace `native-inputs-v27` excludes that declared checkout selector
from native build environment keys. The RTL hash covers the selected design. Without this
selector declaration, environment values stay in the native key. Other build environment
values remain inputs. Source provenance retains the selected checkout path.

Regression executes the selected adapter and core checkout in place. `source_env` selects
the execution tree. `RVW_CAPTURE_SOURCE` supplies its C1 descriptor. Capture records retain
file and tool evidence. Declared stimulus paths keep their original values during execution.
`identity_capture=true` calls `identity --config NAME --options JSON` once per model.
The response uses `rvw.adapter-capture/2`: a complete source descriptor and nonempty
dotted C1 `result_claims`. Each result must carry the claimed values. RiscvSim claims its RTL,
harness and native digests. `/1` identities and old job keys require a rerun. The protocol does
not replace the completeness declaration. Computed paths, interpreter libraries and external
data need declared coverage. Missing or changed stored plans, source mismatches and incomplete
pooled results remain inconclusive.

### Mutation input declarations

`rvw cov mutate --run` captures the full MCY project. A project file named
`rvw-external-inputs` can declare all other inputs as a JSON list of file or directory paths.
Relative paths start at the project directory. An explicit `[]` declares no external inputs.
Use the captured resolved project directory as the base. Non-leading `..` components refuse
capture because they can cross a symlink. Directory captures retain their lookup layout.
The declaration itself and every listed input use the shared capture layer. Missing inputs,
invalid lists and overlapping input roots refuse capture. Execution uses a mirrored private
layout and redirects literal absolute paths in captured UTF-8 text to the corresponding copies.
Raw capture hashes and relocated execution hashes are recorded separately.

With a declaration, `rvw.mutation/2` records `dependency_complete: true` and
`dependency_declaration` with `claim: "declared complete by the user"`, the declared `paths`,
the captured manifest identity and external input identities. A successful fresh run can report
earned kills and equivalence. Inspection of its pinned generation retains this claim.
The literal-path scan refuses obvious undeclared absolute paths. Interpreter shebangs,
device streams and pinned tools are runtime exceptions. This check is not a sandbox or proof
of completeness. Computed paths and hidden tool dependencies remain the user's responsibility.

Without a declaration, a fresh run writes `/1` observations and returns `inconclusive` with
`input_not_captured:mcy_dependencies` and a stderr note that explains how to declare.
Earned outcome counts are zero; `observed_counts` and `observed_state` retain observations.
A failed MCY run also remains inconclusive. Declarations do not enable cache keys or resume.
Existing and interrupted projects still require a fresh run directory.
Raw databases and all saved `rvw.mutation/1` results provide observations only. This includes
`/1` records with `dependency_complete: true`. A fresh `/2` writer must attach and validate
its declaration, capture and tool evidence before it classifies outcomes. Saved-result role,
failed-run and mutation-control checks still apply. All selected equivalence
checks must return PASS before a mutation can be equivalent. Missing checks
stay pending. Conflicting equivalence PASS and FAIL results are errors.

### Result generation layout

The generation store has this layout:

```text
OUT/current                       # rvw.generation-pointer/1: id, manifest_sha256
OUT/generations/<id>/generation.json  # rvw.generation/1: id, files, directories
OUT/generations/<id>/...           # sealed artifacts
```

IDs are unique 32-character lowercase hexadecimal strings. `current` is a regular JSON file
replaced atomically. It binds the generation ID to the manifest SHA-256. The manifest binds
all artifact paths, SHA-256 hashes, sizes, execute bits and directories. Artifact paths stay
inside the generation. Symlinks, hardlinks and special files refuse publication. Readers
validate the full manifest when opening. `Generation.read_bytes` checks the exact returned
bytes against that manifest. `Generation.path` pins and checks the directory identity; direct
filesystem reads still require content verification. Files and directories are read-only after
publication. These permissions do not sandbox another process with the same user ID.

The builder must stop all writers before it returns. An exception in the builder preserves the
previous pointer. A process stop after sealing can leave an unpublished directory. Concurrent
publishers can finish in either order; the last pointer switch wins. Old generations remain
available. Garbage collection and crash durability are outside this API. A reader never falls
back to a newer generation when its pinned evidence vanishes.

# SpinalWaves Rust side: tywaves-rs, surfer-tywaves, spinalwaves-check

This file covers the Rust parts of SpinalWaves: where the vendored code comes from, what we
changed, how to build it, and how to use the checker. The Scala side and the shared interfaces
are in `docs/CONTRACT.md`.

## Layout and origins

| Path | Origin | Commit | Licence |
|---|---|---|---|
| `third_party/tywaves-rs/` | github.com/jarlb/tywaves-rs (copy of `ref/tracing/jarlb_tywaves-rs`) | `215ff16f41742bffa8185cc5996741b13f498bb4` | Apache-2.0 (`LICENSE`) |
| `surfer-tywaves/` | github.com/jarlb/surfer-tywaves (copy of `ref/tracing/jarlb_surfer-tywaves`) | `5a8755b5e06f37884b166e0302547f07a51e1106` | EUPL-1.2 (`LICENSE-EUPL-1.2.txt`) |
| `surfer-tywaves/f128/` | github.com/jkarns275/f128 (git submodule, flattened) | `7f971c34568dd6ae4e97a602bf15c23137b2cad5` | MIT (Cargo.toml; no licence file upstream) |
| `surfer-tywaves/ftr_parser/` | github.com/christiandattinger/ftr_parser (submodule) | `34715f0744f06e27a5740eb6aef2f3b244b828fa` | EUPL-1.2 |
| `surfer-tywaves/fzcmd/` | gitlab.com/TheZoq2/fzcmd (submodule) | `1ae2b2c2e50ce7b99809dc7e2dd64749a51fd4f2` | MIT OR Apache-2.0 |
| `surfer-tywaves/instruction-decoder/` | github.com/ics-jku/instruction-decoder (submodule) | `f016312216a88157d7594fabb6bc53d3d08c0999` | MIT |
| `tools/spinalwaves-check/` | new (this port) | — | Apache-2.0 |

The submodule commits are the ones pinned by surfer-tywaves `5a8755b`. The `tywaves-rs`
submodule of surfer-tywaves (also pinned at `215ff16`) is not copied; surfer uses
`third_party/tywaves-rs` instead. Copies exclude `.git` and build output; nothing else was
removed at import. This checkout does not retain pristine import commits.
To inspect local changes, compare each directory with its upstream revision in
the table above. The sections below describe the local patches.

## Patches

### third_party/tywaves-rs

1. **`find_trace` resolves typed field paths** (`src/tyvcd/spec.rs`, test
   `tests/spinal_field_path.rs`). Upstream `TyVcd::find_trace(path)` treats every element but
   the last as a scope, and the last as a variable name or a leaf's trace (signal) name. So
   `find_trace([TOP, Gcd, sub, io, a, b, 3])` returned `None`, although `docs/CONTRACT.md`
   requires it to find the leaf. The patch walks scopes while they match, then resolves the
   rest as `<variable name>.<field>...` (struct fields by name, vector elements by decimal
   index) with the new `ScopeDef::find_field_path`. Only paths that upstream returned `None`
   for take the new branch, so Surfer's lookups are unchanged.

2. **Per-instance overrides for deduplicated modules** (`src/tyvcd/builder.rs`,
   `src/tyvcd/spec.rs`, `src/hgldd/spec.rs`, test `tests/spinal_instance_overrides.rs`).
   SpinalHDL deduplicates components with identical RTL, so one HGLDD module object (one RTL
   definition, real `module_name`) can stand for instances whose Scala types differ (e.g.
   `FlatChild` with `io.a_b` and `NestedChild` with `io.a.b`, both RTL `io_a_b`). The HGLDD
   `Instance` already has `port_vars` and `children`, but upstream ignored them. Changes:
   - `Instance` gets an optional `source_lang_type_info` (serde optional, so old files still
     parse and serialize the same).
   - `TyVcdBuilder::build` runs `apply_instance_overrides` after the canonical
     `fill_tyvcd_subscopes`. If no instance has any of the three fields, nothing changes.
     Otherwise every top scope is deep-copied (`ScopeDef::deep_clone_under`: no shared
     subscopes, scope paths recomputed), then the instance templates are applied recursively
     from each root's module object:
     - `port_vars: Some(v)` replaces the instance's variables (`Some([])` = no variables).
       They are built with `create_variable`, using the struct objects of the HGLDD file that
       owns the instance and the global enum map. Variables without a value are skipped, as
       for module variables.
     - `children: Some(c)` replaces the instance's subscopes (`Some([])` = none). A child with
       the same name as a canonical child starts from that canonical copy, otherwise it is
       filled from the module definition named by its `obj_name`. Its own overrides apply next.
     - `children: None` keeps the canonical subscopes and recurses with the `children`
       templates of the module object the scope was filled from.
     - `source_lang_type_info` replaces the type name and constructor params of this instance.
     - Trace names (instance names) are never changed.
   - An instance `obj_name` should name an existing module object (the canonical one).
     Otherwise its scope has no base variables, only its overrides.

No other tywaves-rs change. All upstream tests still pass.

### surfer-tywaves

1. `surfer-tywaves/surfer-tywaves/Cargo.toml`: `tywaves-rs` path dependency points to
   `../../third_party/tywaves-rs`. `Cargo.lock` was updated by cargo (the dev-only dependencies
   of tywaves-rs are no longer listed). No source change.

## Upstream behaviour to keep in mind (not patched)

These are tywaves-rs/surfer-tywaves behaviours the Spinal HGLDD emitter has to respect. The
checker reports the ones marked *(checked)*.

- **Extra scopes**: `with_extra_artifact_scopes(extra, top)` renames the HGLDD object whose
  `obj_name` or `module_name` equals `top` to the *last* extra scope and wraps it in the others.
  So pass the full VCD prefix including the DUT (`TOP Gcd`). If `top` matches no module object
  the extra scopes are silently ignored *(checked: `top_module_not_found`)*. With no extra
  scopes the root scope key is the HGLDD `obj_name`, which then has to equal the VCD scope name.
- **Variables without a `value` expression are dropped silently** by the builder, both module
  `port_vars` and instance override `port_vars` *(checked: `dropped_no_value`)*.
- **Missing signals are silent**: the VCD rewriter fills missing leaves with `x` and never
  reports them *(checked: `missing_trace`, `missing_scope`)*. A width mismatch between HGLDD and
  VCD makes the rewrite fail with `UpdateValueError` *(checked earlier: `width_mismatch`)*.
- **Ground leaf with an operator value** (e.g. a concatenation) has no trace name; the rewriter
  renders it as 0 *(checked: `unsupported_expression`)*.
- **Vectors**: `unpacked_range` must be `[hi, lo]` per dimension (`lo..hi` order underflows a
  `u32` and panics). Element names are the operand positions, so list element 0 first.
- **Structs**: a `type_name` is looked up by `obj_name` among the objects of the *same* HGLDD
  document (first match wins), so struct `obj_name`s must be unique per field layout. A struct
  value needs at least as many operands as the struct has fields (otherwise the builder panics;
  the checker reports the panic as an error, exit 2).
- **Enums**: `enum_defs` are collected while modules are walked in file order, before that
  module's variables. An `enum_def_ref` must point to a definition in the same module object or
  an earlier one. Keys are the encoded values (as decimal strings).
- **Rewritten VCD** contains only typed variables (signals not in the HGLDD are dropped), and
  string/real value changes are ignored. Values are expected at full width (Verilator writes
  full width; VCD leading-zero compression is not expanded).
- **Surfer output file**: surfer-tywaves writes the rewritten VCD as `<--top-module>.vcd` in the
  *current directory* (`.vcd` if no top module is given) and overwrites it on each start. Do not
  start it from a directory that holds a wave file named `<top>.vcd`, or that file is replaced.
  Spinal writes `wave.vcd`, so the default layout is safe. Kept as upstream on purpose.
- **Surfer `--hgldd-dir`** must be a directory (all `*.dd` files in it are loaded).
- **Surfer features**: the tywaves translators are only registered when Surfer is built with
  the `spade` feature (on by default; the `--hgldd-dir` branch sits under `#[cfg(feature =
  "spade")]`). Build with default features.

## spinalwaves-check

Loads the HGLDD with tywaves-rs, builds the TyVcd with the given extra scopes / top module,
checks every typed leaf, rewrites the VCD with tywaves-rs `VcdRewriter` (as surfer-tywaves
does), and re-checks the rewritten file.

```
spinalwaves-check <VCD> --hgldd <FILE.dd|DIR> [--extra-scopes SCOPE...] [--top-module NAME]
                  [-o OUT.vcd] [--no-rewrite] [--json REPORT.json] [--allow-dropped]
                  [--list-uncovered] [--fail-on-uncovered] [-v] [--max-report N] [-q]
```

| Option | Meaning |
|---|---|
| `<VCD>` or `--vcd FILE` | input VCD. Put the positional VCD *before* `--extra-scopes` (that flag takes several values) |
| `--hgldd`, alias `--hgldd-dir` | one `*.dd` file or a directory of them |
| `--extra-scopes S...` | VCD scopes above the HGLDD toplevel, outermost first, including the DUT (`TOP Gcd`). Needs `--top-module` |
| `--top-module NAME` | HGLDD module (`obj_name` or `module_name`) that the last extra scope replaces. Needs `--extra-scopes` |
| `-o, --out FILE` | rewritten VCD, must end in `.vcd`. Default `<vcd dir>/<vcd stem>.tywaves.vcd` |
| `--no-rewrite` | check only |
| `--json FILE` | write the full report as JSON |
| `--allow-dropped` | report variables without a value as warnings, not errors |
| `--list-uncovered` / `--fail-on-uncovered` | list / fail on VCD variables in typed scopes that no typed leaf uses |
| `-v` | print every leaf: typed path, trace, width, status |
| `--max-report N` | max errors/warnings printed (default 50; JSON has all) |
| `-q` | print only errors and PASS/FAIL |

Example (the GCD integration test):

```
spinalwaves-check spinalwaves/target/integration/gcd/Gcd/gcd/wave.vcd \
  --hgldd-dir spinalwaves/target/integration/gcd/Gcd/spinalwaves/hgldd \
  --top-module Gcd --extra-scopes TOP Gcd
```

**Exit codes**: `0` all checks passed; `1` verification failed; `2` usage error, unreadable or
unparsable input, or a tywaves-rs builder error/panic.

**Checks** (error `kind` in the report):

- `top_module_not_found`: `--top-module` matches no HGLDD module object.
- `dropped_no_value`: a module or instance-override variable has no `value` (the builder would
  drop it). The typed path is `<module obj_name>.<instance>....<var>`.
- `missing_scope`: a typed scope (module instance) is not in the VCD.
- `missing_trace`: a typed leaf's signal is not in the VCD (or its scope is missing).
- `width_mismatch`: HGLDD leaf width differs from the VCD variable width.
- `unsupported_expression`: a ground leaf has an operator value.
- `find_trace_failed` / `find_trace_mismatch`: tywaves-rs `find_trace(scopes ++ var ++ fields)`
  does not return this leaf (the CONTRACT naming rule).
- `no_typed_leaves`: the HGLDD produced zero typed leaves (empty dataset is a failure).
- `rewrite_failed`: `VcdRewriter` returned an error or panicked.
- `rewritten_missing` / `rewritten_lookup_failed`: after the rewrite, a module variable is not in
  the new VCD, or `find_trace(scopes ++ [reference])` (Surfer's lookup) does not find it.
- `uncovered`: only with `--fail-on-uncovered`.

Warnings (do not fail): `external` (variable without `type_name`), `empty_aggregate`, and
`dropped_no_value` with `--allow-dropped`.

**JSON report**: `{ ok, hgldd, vcd, extra_scopes, top_module, rewritten_vcd, counts: {
hgldd_objects, scopes, scopes_missing, variables, leaves, resolved, constant, missing,
width_mismatch, unsupported, find_trace_failed, dropped, uncovered }, errors: [{ kind,
typed_path, vcd_path?, detail }], warnings: [...], uncovered: [...] }`. Typed paths are the VCD
scope path plus variable and field names, `.` separated (`TOP.Gcd.io.v.1.e`).

## surfer-tywaves usage

```
surfer-tywaves <wave.vcd> --hgldd-dir <W>/spinalwaves/hgldd --extra-scopes TOP Gcd --top-module Gcd
```

Put the wave file first (`--extra-scopes` takes several values). This writes `Gcd.vcd` (the
rewritten file) in the current directory and opens it. `surfer-tywaves
--help` prints the options without opening a window.

## Build and test

Toolchain: Homebrew Rust 1.98.1 (cargo 1.98.1), macOS arm64. Network is needed for the first
build (crates.io and the `spade` git dependency from gitlab.com).

```
scripts/install.sh [--prefix DIR] [--only check|surfer] [--test] [--copy]
```

Builds both release binaries and symlinks them into `--prefix` (default `$SPINALWAVES_BIN` or
`~/.local/bin`). `--test` first runs `cargo test` for `third_party/tywaves-rs` and
`tools/spinalwaves-check`. Single commands:

```
cargo test  --manifest-path third_party/tywaves-rs/Cargo.toml
cargo test  --manifest-path tools/spinalwaves-check/Cargo.toml
cargo build --release --manifest-path tools/spinalwaves-check/Cargo.toml
cargo build --release --manifest-path surfer-tywaves/Cargo.toml -p surfer-tywaves
```

Results on 2026-10-19:

- `third_party/tywaves-rs`: `cargo test` passes (upstream unit, integration and doc tests plus
  `spinal_field_path` and `spinal_instance_overrides`: same RTL module as `FlatChild`
  `io.a_b` / `NestedChild` `io.a.b` with different constructor params, a nested grandchild
  override, an explicit-empty instance, no leak to the sibling, with and without extra scopes).
- `tools/spinalwaves-check`: `cargo test` 8/8 pass (`tests/cli.rs`: Vec of Bundles with an
  enum field + 2-D Vec pass and rewrite, missing trace, width mismatch, wrong top module /
  scopes, dropped variable, empty dataset, unreadable input, deduplicated module with instance
  overrides incl. a value-less override variable). On the GCD integration artifacts: 12/12
  leaves resolved, PASS.
- `surfer-tywaves`: `cargo build --release -p surfer-tywaves` passes with default features
  (first build 8m16s including dependency download, rebuild after a tywaves-rs change about
  3m30s). Only upstream warnings, plus a cargo future-incompatibility note for `block v0.1.6`.
  `surfer-tywaves --version` prints `surfer-tywaves 0.3.0-dev` and `--help` lists `--hgldd-dir`,
  `--extra-scopes`, `--top-module`. Both run headless (no window). The GUI was not started here.
- `scripts/install.sh --prefix /tmp/sw-bin --test` passes end to end (3m38s with a warm cache).

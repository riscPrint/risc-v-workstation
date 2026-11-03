# Vendored typed-viewer limits

This table assigns the TODOs cited by #120. Line numbers refer to the pinned
vendor manifest. Paths under `src/` in the first column are relative to
`third_party/tywaves-rs/`, unless the row names the viewer.
Tests listed here are existing source evidence. They were not rerun for this
triage. Headless checker tests do not validate interactive display (#83).

| Source | Supported path and test | Disposition and owner |
| --- | --- | --- |
| Viewer `tywaves_translator.rs:261` | `translate_variable` labels values Normal, including x/z. `IntegrationSpec` checks typed lookup, not display colors. | Tywaves upstream: unknown/high-impedance value classification. GUI test remains under #83. |
| Viewer `tywaves_translator.rs:304,311,321` | Ground, Struct and Vector reach `convert_kind2info`. `IntegrationSpec` covers nested Bundle/Vec metadata, not rendered subfields. | Tywaves upstream: ground bit expansion and compound type/value agreement. Keep current behavior until a GUI regression exists (#83). |
| Viewer `tywaves_translator.rs:395` | File reload reaches an empty translator reload hook. No supported reload test exists. | Explicit unsupported scope: after changing HGLDD, restart the viewer. Tywaves upstream owns a reload implementation. |
| `src/hgldd/spec.rs:249` | Emitter uses signal names and aggregate `'{` operands. `IntegrationSpec` tests nested aggregates. | Other expression forms are unsupported. Schema extensions belong to tywaves-rs upstream. |
| `src/tyvcd/builder.rs:167` | Scope builder uses `name_id` even when `hdl_obj_name` exists. Emitter uses actual instance names; `ReviewRegressionSpec` checks deduplicated instances. | Alternate HDL object names are unsupported. Tywaves upstream owns generic HGLDD compatibility. |
| `src/tyvcd/builder.rs:210` | Missing source type falls back to `na`. `IntegrationSpec` checks natural type names from our emitter. | Fallback for third-party HGLDD is upstream scope. Supported emitter supplies type metadata. |
| `src/tyvcd/builder.rs:331` | Clone of variable kind has no new input behavior. | Unrelated cleanup: tywaves-rs upstream. |
| `src/tyvcd/builder.rs:634,646,687` | Operators are treated as operand concatenations. Missing expressions are skipped. `HglddEmitter.expression` emits only `'{`; `EmitterSpec` checks pruning. | Arithmetic operators and computed values are unsupported. Tywaves upstream must evaluate opcodes before claiming these values. |
| `src/tyvcd/spec.rs:345` | Trace names can come from variable names during rewrite. `spinal_field_path.rs` and `spinal_instance_overrides.rs` cover local name lookup. | Tywaves upstream owns generic trace-name fallback. The local checker refuses missing physical traces. |
| `src/tyvcd/spec.rs:441,518` | External kind panics in value rendering and reports width zero. Emitter emits named ground/struct/vector types. | External values are unsupported. Tywaves upstream should return an explicit error. Do not use zero width as validity evidence. |
| `src/tyvcd/spec.rs:454,455` | `Variable::get_trace_path` is unimplemented. Local field lookup uses `find_trace` instead. | Direct Variable trace-path calls are unsupported. Tywaves upstream owns the missing trait method. |
| `src/vcd_rewrite.rs:289,291` | ChangeString and ChangeReal updates are silently skipped. The Spinal wrapper uses hardware bit-vector VCD only. `IntegrationSpec` covers that path. | Real/string typed rewriting is unsupported. Tywaves upstream should reject or preserve these records. Generic `rvw wave` has separate real/string tests in `test_wave.py` and `test_wave_index.py`. |
| Viewer `README.md:121,136` | Experimental remote server and WSL bridge are not used by the local wrapper. | Explicit unsupported scope. The viewer links `surver`, but the installer does not build its standalone binary. No remote-server validation is claimed. |
| Viewer `f128/README.md:1` | Optional `f128` feature is absent from default features. `test_waves_package.py` checks the package path. | Explicit unsupported scope: quad precision and nightly f128. The README's nightly remark is advice, not an enabled feature. No nightly toolchain is required by this package. |

No upstream issues were posted. Proposed upstream reports are drafts in the PR
for this change. #43 covers package delivery. #83 covers interactive validation.
This triage does not claim that the supported viewer paths have passed a GUI test.

# Typed viewer package

The supported viewer remains the pinned Tywaves fork. Its origin is
`jarlb/surfer-tywaves@5a8755b5e06f37884b166e0302547f07a51e1106`.
`vendor-lock.json` pins the file contents, including local patches and Cargo locks.
The installer checks these hashes before build. It uses `cargo --locked` for each
build and test. It does not track a moving branch or update dependencies.

```sh
cd SpinalWaves
./scripts/install.sh --only surfer --copy --prefix "$HOME/.local/bin"
python3 scripts/package-source.py --out /tmp/spinalwaves-source.tar.gz
```

The installer puts EUPL-1.2, the vendor manifest and a deterministic source archive
in `PREFIX/../share/spinalwaves/`. The archive includes the viewer, its flattened
submodules, the patched tywaves-rs dependency, the checker and their notices.
Keep this directory with the binary when distributing it. The license choice for
the whole workstation remains an owner decision (#37). No license was changed.
The archive is reproducible. Native binaries can differ with the Rust compiler,
SDK and target. This does not claim byte-identical native builds.

## Upstream plugin assessment

Surfer 0.7.0 documents native WASM plugins through Extism:
[translator API](https://docs.surfer-project.org/translator_docs/index.html) and
[optional hooks](https://docs.surfer-project.org/translator_docs/optional/index.html).
These support compound values, file reads, source-name information, reload and
wave-source notifications. The old vendored README's unchecked WASM item does
not describe current upstream Surfer.

The existing path in `surfer-tywaves/src/translation/tywaves_translator.rs`
uses `vcd_rewrite()` to create typed aggregate signals from several physical
signals before loading. The emitter's `HglddEmitter.expression` emits a `'{`
operand tree. The documented plugin `translate` receives one variable and one
value. It does not supply a waveform hierarchy replacement or values for other
signals at the current time. Thus a translator-only replacement cannot preserve
this path. The fork stays packaged for this increment.

A future plugin can use the checker to rewrite the VCD first, then load its
metadata in a WASM translator. That requires a separate startup integration and
runtime tests for enums, compound values and source jumps. It is not implemented
or validated here. This choice does not close interactive validation #83 or
vendored-limit triage #120. See [VENDORED_LIMITS.md](VENDORED_LIMITS.md).

## Tests and limits

`rvw/tests/test_waves_package.py` checks hash rejection, archive determinism,
source notices, and installer Cargo arguments with a stub Cargo executable.
These are packaging tests. They do not establish a native build or GUI result.
The remote server is outside the supported local viewer path. The installer
builds only `-p surfer-tywaves`, not the standalone `surver` binary. The viewer
still links its server library. Optional `f128` is off in the default features;
this package does not enable nightly Rust or quad precision.

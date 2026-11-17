# Managed verification inputs

The workstation acquires pinned ACT4, riscv-tests and riscv-formal source trees.
It installs Sail from the checksum-pinned native archive manifest. A sibling
`ref/` directory is not required.

```sh
scripts/install.sh --with-act4 --with-riscv-tests --with-riscv-formal --with-sail
rvw doctor --resolve riscv-tests --json
rvw regress riscv-tests-build --out out/isa-tests --xlen 64 --targets rv64ui-p-add,rv64ui-v-add
```

`rvw doctor --resolve NAME` checks the local cache and returns the selected path.
It does not download files. Add `--acquire` to allow acquisition on a cache miss.
A missing or invalid cache entry gives an error. A changed published entry is
not replaced because another job can still use it.

Sources use `RVW_SRC_CACHE`, or `~/.cache/rvw/src`. Native archives use
`RVW_NATIVE_CACHE`, or `~/.cache/rvw/native`. Source pins are in the packaged
`doctor/tools.json` inventory. Sail archive pins are in
`scripts/native-manifest.json`. Git sources have independent object stores and
pinned submodules. They do not borrow objects from a reference checkout.

Explicit overrides remain available: `ACT4_SOURCE`, `RISCV_TESTS_SRC`,
`RISCV_TESTS_SOURCE`, `RISCV_FORMAL`, and `RVW_SAIL`. An invalid override gives
an error. It does not select a different source. `RVW_SAIL` names an executable.
The other variables name source roots. Build commands can apply stricter source
revision and clean-tree checks.

ISA builds write ELFs to `OUT/isa` and source, compiler and ELF identities to
`OUT/manifest.json`. Use a new output directory for each build. Select targets
with `--targets` or use the upstream ISA target set. `--environments` selects
physical and virtual environments. These builds do not run a DUT.

ACT4 keeps its project profile and expected Sail signatures. Source acquisition
does not qualify a core or replace the ACT4 build environment. Ruby, uv, GCC and
native Z3 must be available for the selected host. Formal execution keeps checker
inputs in a private run tree. The source cache is not a formal output directory.

Warm source resolution works offline. A warm ACT4 build also needs its Python,
Ruby and UDB packages. Do not equate cached Git source with a complete offline
build environment.

Sail native receipts now include installed payload identities. Older direct
installs without that record must be installed in a fresh cache prefix. Existing
Sail native bundles must be repackaged after the installer script changes, as
bundle identity includes that script. No old bundle is silently accepted.

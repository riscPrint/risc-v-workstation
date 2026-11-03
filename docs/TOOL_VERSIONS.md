# Tool versions and install policy

The table separates prior tool use from clean-install support. A version probe
alone does not test a tool flow. Clean-install results belong in
[issue #17](https://github.com/riscPrint/risc-v-workstation/issues/17).
No complete pinned combination is qualified yet. The native Ubuntu installer
workflow tests each flag and the quickstart combination. Fedora needs a native
runner. The shared macOS host is not a clean-install host.

| Tool | Version in the check table | Source selection | Qualification |
|---|---|---|---|
| Verilator | 5.052 | Host package manager | Local version probe; full combination pending |
| Yosys | 0.70 | OSS CAD Suite 2026-10-22 | Local version probe; pinned archive flow pending |
| SymbiYosys | 0.70 | OSS CAD Suite 2026-10-22 | Local version probe; pinned archive flow pending |
| Yices | 2.7.0 | OSS CAD Suite 2026-10-22 | Local version probe; pinned archive flow pending |
| Spike | 1.1.1-dev | Linux source `75fb7ef0aa89ae1f9ee361eb84d47753bc8349f8`; macOS Homebrew | Prior arm64 Homebrew co-simulation; Linux pin pending |
| Sail RISC-V model | 0.15 | `549e723031b34b5ffea5bbb56367be15c7a38a9e` | Prior co-simulation; separate archive installer pending |
| gem5 | 25.1.0.1 | `c8222cc67a399bfc01e8658dd14b30d5bfd634f9` | Existing architecture flow; clean install pending |
| JDK | 21.0.13 | Host packages; fallback Temurin 21.0.9+10 | Local version probe; fallback warns |
| sbt | 1.11.7 | Homebrew; Linux archive 1.10.7 | Local version probe; Linux selection warns |
| RISC-V GCC sources | 2025.01.20 | Fedora `a33dac0251d17a7b74d99bd8fd401bfce87d2aed` and its recorded submodules | Clean source build pending |

`--check` warns for versions outside the check table. It also warns for
Verilator 5.049: FSM coverage can crash. Keep FSM coverage disabled with that
version. A warning does not mean the flow passed. Versions below the installer's
minimum, JDK outside major 21, and gem5 outside 25.1.0.1 or without RISC-V support
are refused. Missing or unusable tools also fail the check. An unknown version
fails the check. Other versions at or above the minimum warn and remain usable.
Sail is checked when `RVW_SAIL` is set. It is not part of `--all`.

The main installer consumes `rvw/uv.lock` with `uv sync --locked`. It does not
resolve newer Python packages. Use `uv lock` to update the lock in a reviewed
change. Development setup uses `uv sync --locked --extra dev --extra mcp`.
Use uv 0.13.6 or later to read this lock format. The lock contains package hashes. The editable project's build backend is pinned
in `pyproject.toml`.

Linux Spike and Fedora GCC fetch exact commits. Existing source trees must
match their pins and have no tracked changes. GCC submodules use the commits in
the pinned parent. gem5 verifies its exact commit before building. OSS CAD Suite,
Temurin, sbt and Sail archives use fixed URLs and committed SHA-256 values.
The values come from upstream release metadata or the upstream checksum file.
Homebrew and OS repository versions can drift. These packages, build libraries,
and the host compiler are not a complete tool bundle. This installer does not
claim bit-for-bit native builds. Record actual versions with each result.

SpinalWaves builds and tests use `cargo --locked`. A stale or missing lock is an
error. Update Cargo locks in a separate reviewed change. SpinalWaves,
SpinalTrace GUI, the VS Code extension and Sail each need a separate setup step.
See their READMEs. `scripts/install-sail.sh` downloads the pinned Sail model,
checks its archive hash, and extracts it under `.tools/sail-0.15`. Set `RVW_SAIL`
to the extracted executable. This separate setup path is not yet qualified.

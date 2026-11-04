# Native tool bundles

`scripts/install.sh` installs the workstation. See the
[installation guide](../docs/BRING_YOUR_OWN_CORE.md).

## Build private artifacts

Run the **Native tool bundles** workflow manually. Select one tool and one
host first. Select `all` only when you need every tool or host. The workflow
has no push, pull request or scheduled trigger. It uses two build jobs at most.
Each native build uses two compiler jobs. Source and build trees are cached by
host, tool and build inputs. Jobs stop after 180 minutes. Artifacts expire after
30 days. There is no public release and no container.

The hosts are Ubuntu 24.04 x86-64, Ubuntu 24.04 arm64 and macOS 14 arm64.
GitHub lists these native runners for private repositories in its
[runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
Runner access and billable minutes depend on the repository plan.

Verilator, Spike, gem5 and bare-metal GCC build from the immutable revisions in
`install.sh`. GCC uses RV64GC, LP64D and no multilib. The Sail job packages the
SHA-256 checked Sail 0.15 upstream native archive from `install-sail.sh`. It does
not build the Sail compiler or model from source. Spike includes installed headers,
static libraries and a shim bound to the current shim source. Its build identity
stays unchanged when the installer updates the manifest's installed library path.

Each artifact contains `TOOL-HOST.tar.gz` and its `.sha256` file. The archive has
an identity manifest and a separate prefix for one tool. Each job installs its
archive in a second checkout and runs `install.sh --check` before upload. These
checks test startup and identity. They do not qualify reference semantics or RTL.

## Install artifacts

Use a trusted successful Actions run from this private repository. Authenticate
`gh` with read access to its Actions artifacts. No token is stored by the installer.

```sh
scripts/install.sh --from-bundle --bundle-run RUN_ID --with-riscv-gcc --with-cosim
source env.sh
scripts/install.sh --from-bundle --check --with-riscv-gcc --with-cosim
```

Use `--with-sim` for bundled Verilator, `--with-gem5` for gem5 and `--with-sail`
for Sail. JDK, sbt and the host compiler remain normal installer prerequisites.
`--with-formal` still uses the separate OSS CAD Suite download. `--all` does not
select Sail. Bundle mode does not rebuild a missing bundled Spike shim.

For local artifact use, save each selected artifact's two files in one directory:

```sh
gh run download RUN_ID --repo riscPrint/risc-v-workstation --name gcc-linux-x86_64 --dir /media/native
scripts/install.sh --from-bundle --bundle-dir /media/native --with-riscv-gcc
source env.sh
scripts/install.sh --from-bundle --check --with-riscv-gcc
```

`--bundle-dir` makes no artifact network requests. `--check` never downloads.
The checksum detects damaged transfers. It is not a signature from an independent
publisher. The installer also refuses archives with a different host, pin or
Spike shim source. Use artifacts from the same workstation revision.

## Decisions and limits

These are native tool artifacts, not a complete offline workstation installer.
Use the same host OS and architecture as the build runner. Runtime libraries
from the runner's package manager remain prerequisites. Each archive includes
`share/rvw/dependencies.txt`. On Ubuntu the build uses Boost, GMP, MPFR, MPC,
Expat, zlib, protobuf, libpng, gperftools and Python development packages. On
macOS it uses matching Homebrew libraries and the Xcode command line tools.
Their versions are not pinned by these artifacts. A different Python or Homebrew
library ABI can prevent gem5 from starting. The installer must report that failure.

Python, uv, JDK, sbt, the Python environment, system libraries, QEMU and OSS CAD
Suite are not bundled. A complete offline installation with result queries is
still open under #71. `UV_OFFLINE=1` can reuse a populated uv cache. It does not
supply missing system packages. Clean-host qualification remains under #17.
See [tool versions](../docs/TOOL_VERSIONS.md) and #40 for pin policy.

Archives retain the upstream installed license files where supplied. This work
does not decide the project license or grant redistribution rights. The workflow
publishes only private Actions artifacts. Source offers, complete dependency
packaging and redistribution review remain open before wider distribution.

Native builds and relocated native checks must run in GitHub Actions. Local
fixture tests cover packing, checksums, pin checks and installation paths. They
do not establish that these native builds pass on the three hosts.

## Native yosys-slang

`install.sh --with-formal` builds yosys-slang against the selected `yosys-config`.
It sets `RVW_SLANG` in `env.sh`. An explicit `RVW_SLANG` selects an existing plugin.
The build needs Python 3.11.8+, CMake, make and a C++20 compiler. It uses two jobs.
`scripts/yosys-slang-sources.json` pins the frontend, slang, fmt and regex archives
by commit and SHA-256. CMake network fetching is disabled. A checksum error stops
before compilation. The helper extracts fresh sources on each build.

The frontend is now named [sv-elab](https://github.com/povik/sv-elab).
The local build adds one call to `driver.optionallyWriteDepFiles()` after parsing.
The pinned upstream entry point accepts `--all-deps` but does not call it.
This patch lets `rvw formal` check the frontend's file closure. It adds no SVA lowering.
Run a separate build with:

```sh
python3 scripts/build-yosys-slang.py --prefix /absolute/native-prefix \
  --yosys-config /absolute/oss-cad-suite/bin/yosys-config
```

This is a native source build. Existing formal bundles do not contain this plugin.

## Local checks

`ci-local.sh` runs the same fast checks as the macOS self-hosted CI job.
It uses a new temporary work directory and venv, machine-wide locks and
`nice -n 10`. See [Local CI](../CONTRIBUTING.md#local-ci) for commands and
prerequisites. The `nightly-python`, `nightly-scala` and `messages` modes
serve the other local Actions jobs. `messages` needs a GitHub event file.

## Native install qualification

Run one case on a native macOS or Linux host. Install Python 3.11+, Git and uv
0.13.6+ first. macOS also needs Homebrew and the Xcode command line tools.
Commit source changes first. Use a new output directory outside this checkout.
The command can ask for sudo through the installer. It approves the installer's
package commands with `--yes`. It does not upgrade the whole host.

```sh
python3 scripts/qualify-install.py --case quickstart --cold-scala --out /tmp/rvw-quickstart
```

Use `--case core|sim|gcc|cosim|formal|gem5|quickstart|all` to select a case.
Run each case separately on a fresh host to establish independent clean-install
support. A sequence on one host records package reuse. Use the same command on
Ubuntu and Fedora. Other apt/dnf systems can run it, but need their own results.
No Actions runner or container is required. A full source build can take hours.
`--timeout` bounds each step, including lock waits (default six hours).

The command clones the committed workstation into the output directory. It
runs the exact case's install and `--check` first. It then adds the GCC and
simulation tools needed by the runtime harness as a separate step. GCC builds
an actual pinned riscv-tests ELF. Simulation runs the pinned public VexRiscv
smoke program offline. Cosim compares that complete passing trace with Spike. It also runs the native
reference policy tests from a locked development environment. Any skipped native
test stops qualification.
Formal runs an eight-cycle counter BMC. gem5 builds and runs the median
benchmark with `rvw arch`. These are bounded smoke checks. They do not establish
whole-core correctness or a release verdict. The gem5 case uses the BOOM model
data but needs no private BOOM sources.

`--cold-scala` selects fresh sbt boot, global, Ivy and Coursier directories.
The command first runs `root/update` online. It then invokes the normal offline
launcher. This distinguishes dependency fetching from offline startup. Offline
startup with empty caches cannot work. The script does not download a JDK or
sbt launcher into those caches before this step.

Each step saves its command, exit code, duration and log. `report.json` remains
inconclusive until all required steps pass. An error, missing result or timeout
stops the case. There is no skip-as-pass path. Attach reports and relevant logs
to #17 and #40. Record whether the machine was clean before starting. The script
cannot attest to a clean host. Inspect logs before sharing them. Retain the
output until review; it includes cloned sources and native build outputs.

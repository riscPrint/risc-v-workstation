# Native VexRiscv example history

This recipe runs `rvw bisect` on real workstation history. Each trial compiles
that revision's actual `VexTop.scala`. It uses the same private VexRiscv
library at `a62c145aa042a5de874344e0a7683bd7c8c8c870` and SpinalHDL 1.15.0.
It does not bisect upstream VexRiscv source. `legacy.sh` accepts the older
M/S/U configuration. `m_only.sh` accepts the M-only configuration. Each
adapter checks that its selected configuration is present. Port bindings come
from that revision's generated RTL. All declared inputs start at zero.
The older core has `externalInterruptS`. The newer core does not.

The program intentionally expects supervisor scratch CSR access. It passes
before the M-only configuration change and writes failure through `tohost`
after that change. This is an intentional compatibility transition. It is not
a claim that the newer M-only core has a bug. Both endpoints are executed.
The known first changed commit is
`6c891a7615b843308e94efb4b4ff5551177f3bda`. Its parent is
`78ba8c540cb0f81030936cefce2faaf6abd65fd7`.

## Prepare

First compile the current example with the private VexRiscv copy, JDK 21 and
the required locks. Its exported runtime classpath contains the private core
classes. Keep that classpath and its class files unchanged during the campaign.
Supply the cached Scala 2.13.14 compiler, library and reflect jars and the
SpinalHDL 1.15.0 compiler plugin. Run from the workstation root:

```sh
nice -n 10 rvw/.venv/bin/python examples/vexriscv/rvw/history/prepare.py \
  --out /path/to/new-history \
  --classpath examples/vexriscv/rvw/target/streams/runtime/fullClasspath/_global/streams/export \
  --compiler-jars /path/to/scala-compiler-2.13.14.jar \
    /path/to/scala-library-2.13.14.jar /path/to/scala-reflect-2.13.14.jar \
  --plugin /path/to/spinalhdl-idsl-plugin_2.13-1.15.0.jar
```

Preparation makes an independent clone, captures project adapter templates
and builds the small RV32 ELF with the installed cross compiler. It writes
machine-specific classpath data only outside the repository. Native builds
use private output directories and direct `scalac` invocation. They do not
write to shared sbt outputs or require a shared VexRiscv lock.

## Run

Set `RVW_HOME`, `RVW_PYTHON` and `RVW_CIRCT` to the current tools and pinned
CIRCT installation. Set `RVW_VEX_LOCK=vex-NAME` to the private worker lock.
Set `RVW_HISTORY_SOURCE` to `/path/to/new-history/source`.
Run the initial bad case with the captured `harness/m_only.sh`:

```sh
/path/to/new-history/harness/m_only.sh run \
  --elf /path/to/new-history/csr-transition.elf \
  --out /path/to/new-history/bad-run --seed 7 --config rv32im --rvfi-trace --json
```

Exit code 1 is expected. C1 must report `fail`, not a build error or timeout.
Then run the real bisect under the private lock:

```sh
RVW_CORE_CONFIG=/path/to/new-history/harness/debug.toml RVW_NO_LOCK=1 \
  scripts/with-lock.sh vex-NAME nice -n 10 rvw/.venv/bin/rvw bisect \
  /path/to/new-history/bad-run \
  --good 78ba8c540cb0f81030936cefce2faaf6abd65fd7 \
  --bad 6c891a7615b843308e94efb4b4ff5551177f3bda \
  --workdir /path/to/new-history/bisect --timeout 120 --json
```

Here `RVW_NO_LOCK=1` prevents an additional generic core-name lock. The outer
private lock and the project launcher still serialize native work. Do not use
that setting without the outer private lock. Use a fresh bisect output path.
The C8 launcher supplies each trial's captured source path and adapter identity.
The project driver preserves that identity in C1. The shared scalar engine
probe emits actual trap events for this program. Its default trap refusal
remains in place for ordinary smoke runs.

## Measured evidence and limits

On 2026-11-13, `rvw bisect` found the exact expected first changed commit.
The legacy endpoint passed: 13 retirements, 38 cycles, 5.5 seconds of adapter
run time. The M-only endpoint reproduced `fail:1`: 9 retirements, 36 cycles,
5.9 seconds. Both recorded their correct project adapter selection in C1.
The shared C2 parser validates both complete traces, including trap records.
[measurements.json](measurements.json) records the new sample. It replaces
the earlier sample that had incomplete trace headers.
There were no skipped endpoints. The two revisions are adjacent, so no
intermediate search trial was needed. The report contains the real Git IDs,
C8 source capture, generated RTL hashes, commands, C1 files and C2 files.
Cache keys remain disabled. Captured trees retain the existing dirty flag.

An initial later CSR-cleanup pair failed this compatibility test on both sides.
It did not earn a guilty-commit result. A first adapter invocation also refused
the standard `--mem-latency 1` replay option; that parser gap was fixed before
the successful run. Unsupported revisions still fail explicitly.

This does not qualify BOOM history, regression gates across old revisions or
a core-side interface-stability policy. Native compiler dependencies still
require the supplied local classpath. This is not a portable binary bundle or
C4 acceptance result.

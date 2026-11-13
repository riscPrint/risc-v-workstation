# Native adapter and persistent-server speed

The VexRiscv loop profile found 525,969 individual port reads and 401,655
individual port writes. Under cProfile, their own times were about 0.79 s
and 0.83 s. The 120,497 evaluation calls took about 0.24 s. This identifies
Python/native port calls as a limit in this adapter. It does not isolate the
generated model's kernel time. See [the profile](profile.json).

The native model now takes one settled-port snapshot after each evaluation.
Scalar Verilator reads use that buffer. Arcilator reads use one copy of its
state bytes. Input writes invalidate the snapshot. The next evaluation
refreshes it. Wide Verilator values still use the explicit byte interface.
`port_snapshot=False` selects the control. The project engine probe exposes
that control as `--no-port-snapshot`.

`campaign.py` runs a warm pair and then four alternating pairs on the same
Verilator RTL and ELF. Every run must pass and produce identical complete C2
bytes. The measured interval includes bus/RVFI handling and C2 write/validation.
It excludes compilation. Run from the workstation root:

```sh
scripts/with-lock.sh vex-simsrv nice -n 10 rvw/.venv/bin/python \
  examples/vexriscv/rvw/native-speed/campaign.py --rtl /path/to/VexTop.v \
  --elf /path/to/loop.elf --out /tmp/new-port-comparison
```

`persistent-isa.py` compares the 49 aligned RV32UI/UM ELFs in `rvw/out/isa`.
Build them with the example's `rvw/build-tests.sh`. Compile the example once
with its normal launcher before the comparison. This comparison starts JVMs
directly from that compiled classpath. Tool and source capture occur once.
A passing warm run fills the native cache outside both measured intervals.
The script then runs the complete suite in one server and in 49 separate JVMs.
Every complete C2 file must match across the two modes.

```sh
scripts/with-lock.sh vex-simsrv nice -n 10 rvw/.venv/bin/python \
  examples/vexriscv/rvw/native-speed/persistent-isa.py --out /tmp/new-isa-comparison
```

Set `RVW_HOME` and private `VEXRISCV` first. Set `RISCVSIM_WORK` inside the
private workspace. `--classpath-prefix` selects an isolated compiled adapter
when the shared sbt queue is busy. It does not compile or copy core sources.
This is one warmed suite comparison. It excludes Scala compilation and common
tool/source capture. It does not establish a general core speed gain.

The first port-snapshot campaign had large wall-time variation. Its four
measured pairs gave mixed directions. The median ratio alone did not qualify
a wall-time gain. That complete sample stays in
[the noisy wall sample](port-wall-noisy.json). The follow-up also records
process CPU time, so descheduling is separate from measured CPU cost.

On 2026-11-13, the warmed 49-test ISA suite passed in both JVM modes. All 49
complete C2 files were equal. The server took 16.84 s and the separate JVMs
took 422.41 s, a throughput ratio of 25.08. This is one suite sample on a shared
macOS arm64 host. It demonstrates process reuse for this suite. It is not an
isolated Verilator kernel speedup. See [the suite sample](persistent-results.json).

The follow-up ran a warm pair and three measured alternating pairs. Complete
C2 bytes matched across all eight runs. Median CPU throughput rose from
16,449 to 20,094 instructions per CPU second, a ratio of 1.222. All measured
pairs used less CPU time with snapshots. Wall throughput was 8,263 against
7,126 instructions/s, ratio 0.862. This sample does not qualify a wall-time
gain. Both results remain in [the follow-up](port-results.json).
The default snapshot path reduces measured CPU cost in this adapter. The
direct-read control stays available. No Verilator thread profile is qualified.

The ISA suite retired 17,735 instructions. Whole-suite wall throughput was
41.99 instructions/s in separate JVMs and 1,053.09 instructions/s in the
persistent server. These figures include startup and elaboration. They must
not be used as isolated core execution rates.

# Native fabrics and a CPU with DMA traffic

`rvwsoc.NativeAxiCrossbar` uses the SpinalHDL 1.15.0 per-master decoder and
per-target arbiter. It accepts N masters and M disjoint, aligned power-of-two
windows. Target addresses stay global. IDs include the originating master.
`NativeTileLinkCrossbar` uses the native TileLink decoder and arbiter. It
supports Get/Put without BCE. Targets receive local window offsets. Source
IDs include the originating master. Unmapped requests reach an error slave.

`AxiDataWidth` supports 32, 64 and 128 data bits. It preserves the original
IDs and burst framing through SDK ID and burst adapters. Its downstream
interface has one ordered ID. Exclusive accesses are excluded. It retains an
early narrow error until the corresponding wide response completes.
Conversion does not promise maximum throughput.

## Run

Use a private VexRiscv checkout and the environment from the Vex example.
Run these commands from the workstation root. Set VEXRISCV to that checkout.

```sh
cd SpinalSoc
../scripts/with-lock.sh sbt-soc nice -n 10 sbt -Drvw.soc.vex=true compile
# Use the full classpath exported by the private build.
../scripts/with-lock.sh vex-soc nice -n 10 java -cp "$SOC_CLASSPATH" rvwsoc.NativeFabricGenerate out/fabric-rtl
cd ..
rvw/.venv/bin/python SpinalSoc/examples/fabric/configure.py --rtl SpinalSoc/out/fabric-rtl --out SpinalSoc/out/fabric-benches
# Repeat for tl, down and up.
rvw regress cocotb SpinalSoc/out/fabric-benches/axi.json --out SpinalSoc/out/fabric-axi --seed 31 --json
scripts/with-lock.sh vex-soc nice -n 10 rvw/.venv/bin/python SpinalSoc/examples/fabric/build-cpu.py --out SpinalSoc/out/cpu-dma
scripts/with-lock.sh vex-soc nice -n 10 rvw/.venv/bin/rvw regress cocotb SpinalSoc/out/cpu-dma/bench.json --out SpinalSoc/out/cpu-dma-run --seed 31 --json
```

The CPU example uses the real VexRiscv wrapper and a DMA-style RTL traffic
generator. They share a native two-master AXI crossbar before the composer
memory and peripheral ingress. DMA writes and reads 32 data words, then a
marker. The CPU waits for the marker, checks all data and writes the finisher.

## Measured results

SpinalHDL 1.15.0 and Verilator ran these cases on 2026-11-13 at seed 31.
Every case passed with assertions enabled and zero skipped cocotb tests.
Independent VIP byte models check both ends of each fabric.

| Case | Client transactions | Target transactions | Other observations |
|---|---:|---:|---|
| AXI4, 2 masters, 2 targets, 32 bits | 34 + 34 | 36 + 32 | 1,048 stalled response cycles; 16 parallel target-read cycles |
| TileLink, 2 masters, 2 targets, 32 bits | 24 + 24 | 24 + 24 | 42 parallel target-request cycles; unmapped read denied |
| AXI4, 64 to 32 bits | 36 | 247 | 431 stalled response cycles; early read and write errors retained |
| AXI4, 32 to 64 bits | 36 | 124 | 476 stalled response cycles; read and write errors returned |
| Composed CPU and DMA | 33 DMA writes + 33 reads | Shared RAM | 2,135 cycles; 236 CPU retirements; finisher 1 |

AXI traffic covers FIXED, INCR and WRAP bursts, byte strobes, high byte lanes,
concurrent masters and response stalls. TileLink uses transfers through 64
bytes. A generated RTL mutation which discards the early narrow read error
fails `EARLY_NARROW_READ_ERROR_LOST`.

The Python wide-agent tests also cover 128-bit lanes. Native 128-bit conversion,
exclusive AXI accesses, TileLink atomics/BCE/coherence, fairness proofs and
hardware timing were NOT RUN. CPU completion is component simulation evidence,
not C1 acceptance or a whole-core proof.

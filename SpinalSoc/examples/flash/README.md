# SPI flash boot

This example boots the composed RV32IM VexRiscv core from a ROM stub. The
stub copies a payload from a read-only SPI NOR model into RAM. It checks a
byte sum, then jumps to the RAM entry. Only the RAM payload reports success.
The ROM reports finisher code 3 for a bad image.

| Region | Base | Size | Initial contents |
|---|---|---|---|
| Boot ROM | `0x80000000` | 4 KiB | ROM stub ELF |
| Application RAM | `0x80010000` | 64 KiB | Zero; no payload preload |
| SPI controller | `0x10000000` | 256 bytes | Spinal APB SPI controller |
| Finisher | `0x10001000` | 256 bytes | Zero |

The payload starts at flash byte `0x100`. The stub uses command `0x03` with
three address bytes. The controller uses SPI mode 0 and active-low select.
Its command, response-valid and FIFO-availability fields follow the pinned
[SpinalHDL 1.15.0 controller](https://github.com/SpinalHDL/SpinalHDL/blob/v1.15.0/lib/src/main/scala/spinal/lib/com/spi/SpiMasterCtrl.scala).
All reads cross real SPI pins. The host does not write the payload into RAM.
A separate read-only observation port checks RAM word zero before and after
boot. The generated RAM constructor is also checked for an empty image.

Use the private VexRiscv checkout from the Vex example. Set `VEXRISCV` and
put RISC-V GCC and native tools on PATH. Run from the repository root:

```sh
scripts/with-lock.sh vex-soc nice -n 10 rvw/.venv/bin/python \
  SpinalSoc/examples/flash/build.py --out SpinalSoc/out/flash-session
scripts/with-lock.sh vex-soc nice -n 10 rvw/.venv/bin/rvw regress cocotb \
  SpinalSoc/out/flash-session/bench.json --out SpinalSoc/out/flash-run \
  --seed 31 --timeout 120 --json
```

The build uses the private `sbt-soc` lock. It composes and compiles the real
core, decoder, ROM, RAM, SPI and finisher. It captures the core revision,
program hashes and generated memory-image hashes. The cocotb run checks those
memory files and the flash-image hash before it starts the CPU.

`rvw.vip.spi_flash.ReadOnlyNor` supplies the device model. It supports `0x03`,
`0x0b` with one dummy byte, status reads and an explicit project-supplied
JEDEC identity. Addresses have 24 bits. Unwritten and out-of-image bytes
return `0xff`. Program and erase commands raise an explicit unsupported
command error. The model is a read-only boot-image profile. It does not
model flash wear, program/erase timing, quad SPI or a physical device.
The existing SPI agent independently monitors the wire words.

## Measured results

Both native runs used seed 31 on 2026-11-13. The private core revision was
`baf7dc82f855eddaf5b0a20a6802c526f127e38a`.

| Image | CPU cycles | Retired instructions | Flash bytes | SPI words | Finisher |
|---|---:|---:|---:|---:|---:|
| Unchanged payload | 5,150 | 573 | 16 | 20 | 1; pass |
| One corrupted payload bit | 5,130 | 569 | 16 | 20 | 3; rejected |

RAM word zero was observed as zero before each run. The successful run ended
with the expected payload word. Each run used one flash select transaction.
The positive cocotb test passed. The deliberately corrupted run failed its
success expectation and retained the failure record. Use
`RVW_FLASH_CORRUPT=1` on the run command to reproduce that negative case.

The flash model's five Python tests passed. They cover normal/fast reads,
address restart, erased bytes, identity/status, missing identity input,
unsupported writes and partial words. The native `LegacyErrorSmoke` also
passed. It checks partial-write rejection and full accesses to an APB target
which omits `PSLVERROR`. The real SPI peripheral has this configuration.

This is development simulation evidence from a working tree. The simulation
uses the component C3 runner. It does not establish C1 gate acceptance,
Spike co-simulation, XIP, a production bootloader or hardware boot.

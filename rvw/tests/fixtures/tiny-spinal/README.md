# Tiny Spinal integration fixture

This sequential RV32I core tests project setup with a core outside the BOOM and
VexRiscv integrations. It has one valid-ready memory bus and one RVFI channel.
It does not implement CSRs, interrupts, misaligned accesses or trap handling.
It is not a production core or a full ISA compliance claim.

The native test copies this project into a temporary directory. It calls init,
builds and runs the generated smoke program with seed 7, checks its C2 trace
against Spike, builds a database and queries the PC.

With JDK 21, sbt, Verilator, RISC-V GCC and the current Spike shim installed:

```sh
RVW_TEST_TINY_SPINAL=1 nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests/test_init_spinal_native.py -q
```

The test takes the `vex-vexii` core lock and the shared sbt lock. A command has
a 120-second timeout. Wait for shared native jobs to finish before starting it.
The normal fast set skips this opt-in native test.

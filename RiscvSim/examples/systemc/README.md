# SystemC and TLM memory example

This example builds `MemoryMaster.sv` with Verilator `--sc`. A SystemC bridge
converts its requests to TLM-2 blocking memory transactions. The generic target
is [TlmMemory.h](../../src/main/cpp/TlmMemory.h). No RISC-V signal is in that
header.

Use an installed SystemC development library and native Verilator. Set
`SYSTEMC_HOME` to the library prefix, or provide `systemc.pc` through
`pkg-config`. On Homebrew, use `SYSTEMC_HOME=$(brew --prefix systemc)`.
Source the native Verilator environment, then run from the repository root:

```sh
nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests/test_systemc_tlm.py -q
```

The test runs the real Verilator `--sc --exe --build` command. It builds with
two jobs. The native model writes `0x12345678` to address zero, reads it back
and checks the returned value in RTL. A mismatch sets the RTL error output.
The host checks completion, transaction counts and stored bytes.
It also checks repeated byte masks, out-of-range accesses, unsupported bursts
and annotated delay. Missing native tools produce a skip, not native evidence.

On 2026-11-13, Verilator 5.049 and SystemC 3.0.2 passed the native test on
macOS ARM64. The complete compile and test command took 18.90 seconds.
This is an example integration result, not a simulator performance comparison.

## Time and ordering

The target is loosely timed. It applies bytes at `b_transport` call time and
adds its configured latency to the annotation. It does not call `wait`.
The caller must consume the delay. The example bridge has one initiator and
one outstanding transaction. It consumes the two-nanosecond delay before
asserting the response. The RTL clock period is ten nanoseconds. The response
arrives before the next rising edge. The bridge samples requests on falling
edges. The single SystemC kernel orders these calls. No host threads access
the target.

## Decisions and limits

The target supports blocking reads and writes, byte enables and range checks.
Data bytes have no implicit endian conversion. The bridge packs little-endian
32-bit words. Streaming widths smaller than the data length are refused.
DMI, atomics, nonblocking transport, multiple initiators, temporal decoupling,
interrupt delivery, plugin ABI binding and checkpoint restore are not supplied.
The example's fixed delay is not measured device timing. The target alone is
not a cycle-accurate memory model. A different bridge must define its own
request sampling and response timing. This does not qualify a whole core.

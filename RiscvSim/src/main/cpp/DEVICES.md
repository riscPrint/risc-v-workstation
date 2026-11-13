# Project device libraries

Compile a project shared library that exports:

```cpp
extern "C" const riscvsim::DeviceApiV1* rvw_device_plugin_v1();
```

Include `DevicePlugin.h`. Return ABI 1 and all callbacks. `create` receives
project JSON and a seed. Keep device maps, clock units and interrupt routing
in project data. Each handle has independent device state. The harness owns
the library and handle lifetime. It must serialize calls at settled boundaries.
Use relative byte offsets, access sizes of 1 to 8 bytes, little-endian values
and byte-lane write masks. Return a nonzero status on failed operations.

`tick` receives an absolute simulation cycle. Project configuration must state
the cycle period. Models must not use host time for deterministic deadlines.
`interrupts` returns model output bits. Project bindings route these bits to
core inputs. The API does not infer an ISA interrupt map.

`snapshot(nullptr, 0)` returns the exact byte size. Return zero if external
state cannot be restored. At a stopped boundary, a second call fills that many
bytes. Snapshot data must include pending transactions, interrupts, timer
deadlines, RNG and stimulus positions. Version the payload in the project.
`restore` must reject unknown or corrupt payloads. Save plugin identity and
payload under the native envelope's `devices` component. Include library,
configuration and transitive inputs in the native/harness identity. Never
serialize pointers or host descriptors. Discard a device after restore failure.

Compile `DeviceDpi.cpp` into the project native harness for DPI-C bindings.
These declarations belong in the project testbench:

```systemverilog
import "DPI-C" function chandle rvw_device_open(input string library_path,
    input string config_json, input longint unsigned seed);
import "DPI-C" function void rvw_device_close(input chandle device);
import "DPI-C" function int rvw_device_read(input chandle device,
    input longint unsigned offset, input int unsigned bytes,
    output longint unsigned value);
import "DPI-C" function int rvw_device_write(input chandle device,
    input longint unsigned offset, input int unsigned bytes,
    input longint unsigned value, input longint unsigned mask);
import "DPI-C" function int rvw_device_tick(input chandle device,
    input longint unsigned cycle, output longint unsigned interrupts);
```

Refuse a null open handle or nonzero operation status. DPI functions catch C++
exceptions and return failure. Do not continue simulation after a device error.
Close each handle once. The native C++ wrapper provides snapshot/restore for
adapter-owned checkpoint capture. Raw DPI handles cannot be restored.

This interface permits project UART, CLINT, PLIC, block-device and SystemC
models. It does not implement those devices or a TLM synchronization policy.
There is no VPI callback binding or Linux-boot qualification. The native smoke
loads a small fixture shared library and checks independent handles, MMIO,
ticks, interrupts, snapshot/restore and DPI failure status. A second smoke compiles and runs a tiny Verilator testbench
with actual DPI-C imports for open, close, MMIO, ticks and interrupts. Use a pinned compiler and include the plugin library digest
in every native run that loads it.

## Standard models through CPython

`PythonDevices.cpp` exports the same ABI. It calls `rvw.sim.devices.Device`.
Build it with `RiscvSim/scripts/build-devices.py --out LIB`. The script
compiles in the interpreter home and this workstation's `rvw/src`, and the
library starts an isolated interpreter: it ignores `PYTHONHOME`,
`PYTHONPATH` and the user site. Leave both variables unset, so native
identity capture stays complete; the library bytes record both paths. A
library built without these defines still reads the environment. Keep the interpreter alive until process exit. Calls acquire the
GIL. This is a reference bridge, with no throughput claim.

The JSON `model` selects `ns16550`, `clint`, `aclint`, `plic`,
`htif-console` or `simple-block`. Timer `map` uses `TimerMap` fields. PLIC `map`
uses `PlicMap` fields. All map addresses are relative to this plugin's base.
Map integers are JSON integers or decimal/`0x` strings, as in `rvw.sim-map/1`.
A float is refused. Hosts that keep JSON numbers as doubles (Scala `ujson`)
round 64-bit values such as an all-ones `reset_mtimecmp`. Write those as `0x` strings.
The project supplies `cycles_per_tick` for timers. PLIC `levels` can contain
ordered `{cycle, source, level}` events at positive cycles. The harness must
call `tick` before accesses at each cycle. Output bit zero is UART TX IRQ.
Timers return software and timer bits for each hart in successive bit pairs.
PLIC returns one bit per context. The project routes each output to the core.
The ABI has no live gateway input callback. Interactive gateway routing needs
an adapter extension. The Python composition API also exposes `set_level`.

The UART supports polling output, divisor, scratch and TX IRQ registers.
RX, modem input, FIFO operation and baud timing remain unsupported.
CLINT/ACLINT provide MTIMER and MSWI registers. No supervisor software
interrupt block is supplied. PLIC uses level gateways, claim and completion.
The HTIF console accepts device 1, command 1 writes at offset 0 and
acknowledges through offset 8. Other HTIF host calls fail.
`simple-block` is a RAM disk byte window initialized by `image_hex`.
It has no virtio transport, DMA, command queue or persistent host writes.
All models require full byte masks. A partial device write fails without a
read-modify-write because a read can acknowledge an interrupt.

Console output and disk writes stay in model state. They cause no host output
or file writes. Their complete state is in versioned JSON snapshots. Include
the Python modules, Python library and configuration in the run identity.
Snapshots are trusted same-build state, not a portable untrusted input format.
The native test compiles the shared library and restores a fresh stopped UART
state through `DevicePlugin`. It also tests timer, PLIC, HTIF and disk state in
Python. This does not qualify a Linux RTL adapter.

Build with the selected rvw Python environment:

```sh
rvw/.venv/bin/python RiscvSim/scripts/build-devices.py --out /tmp/new-devices.so
```

The helper refuses an existing output. It uses the interpreter's library and
headers. On macOS it corrects the portable CPython library install name.

## Scala host binding

`riscvsim.PluginDevice` calls DeviceApiV1 through JNA. It uses the same plugin
shared library as the C++ and DPI wrappers. The project supplies the library,
configuration JSON, seed, address map and interrupt routing. Call `tick` before
MMIO at each sampled cycle. Close each handle after its run. Libraries remain
loaded for the JVM lifetime because CPython has process-global state.

The binding checks the ABI, required callbacks, initialization and operation
status. It refuses accesses after close. It has no checkpoint binding.
Include the shared library, configuration and transitive Python modules in
C1 input capture before using it in a cacheable regression.

The builder accepts standard shared-library and macOS Python framework layouts.
It uses the selected interpreter's sysconfig paths. A missing library is refused.

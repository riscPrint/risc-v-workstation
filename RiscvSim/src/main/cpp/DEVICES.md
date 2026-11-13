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

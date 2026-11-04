# Native Yosys IFT pass

`rvw_ift.cc` registers the `rvw_ift` synthesis pass. It instruments a flattened,
mapped design in place. It adds `__t` ports for data ports. It uses a public
rising-edge clock and the design's own public reset logic. No declassification
is supported. Value-sensitive transfer logic includes mux control taint.
The JSON implementation in `rvw.formal.security.ift` is a separate reference.

Build against the headers of the Yosys executable that will load the plugin.
Use `yosys-config --build rvw_ift.so rvw_ift.cc` on a matching native install.
Some OSS CAD Suite macOS releases give an unavailable cross-compiler path.
For that case, use the installed native compiler and matching headers:

```sh
clang++ -std=c++17 -O1 -fPIC -D_YOSYS_ -DYOSYS_ENABLE_PLUGINS \
  -I "$HOME/opt/oss-cad-suite/share/yosys/include" \
  -undefined dynamic_lookup -shared rvw_ift.cc -o /tmp/rvw_ift.so
yosys -m /tmp/rvw_ift.so -p 'read_verilog design.v; hierarchy -top top; proc; flatten; techmap; simplemap; rvw_ift; write_verilog instrumented.v'
```

The pass accepts NOT, AND, OR, XOR, MUX and positive-edge DFF cells only.
It refuses unsupported cells, memories, processes, blackboxes, initial-state
attributes, X/Z constants, undriven bits and multiple drivers. It requires
one public scalar clock for sequential designs. It validates before mutation.
It leaves functional logic in place and adds shadow state and shadow logic.
Taint can overestimate flow where paths reconverge. It is not a formal proof.
Do not observe state before the public reset has reached all relevant registers.

The native tests enumerate the full value/taint truth tables for all supported
Boolean gates. They also test sequential control flow, masked flow and public
reset on both implementations. See `rvw/tests/test_security.py`.
See [the hardware threat model](../../rvw/src/rvw/formal/security/README.md).

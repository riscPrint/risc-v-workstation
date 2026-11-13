# Verilator context-time probe

The old SpinalHDL wrapper advances its callback time. It does not advance
`VerilatedContext` time. `-DVL_TIME_CONTEXT` can therefore leave HDL `$time`
at zero. This can disable an assertion guarded by `noAssertAtTimeZero`.

Run from the workstation root with Verilator on PATH. Set `RUN_ROOT` to an
empty output directory outside the source folders. No core is built.

```bash
mkdir -p "$RUN_ROOT"
case_root="$PWD/RiscvSim/tests/repro/verilator-context-time"
for mode in callback context; do
  flags=()
  if [ "$mode" = context ]; then flags=(-CFLAGS -DVL_TIME_CONTEXT); fi
  nice -n 10 verilator --cc --exe --build -j 2 --top-module clock_probe \
    --timescale 1ns/1ns --Mdir "$RUN_ROOT/$mode" "${flags[@]}" \
    "$case_root/clock_probe.sv" "$case_root/main.cpp"
  "$RUN_ROOT/$mode/Vclock_probe"
done
```

The installed Verilator 5.049 prints `17` for `callback` and `0` for
`context`. This is a tool compatibility result. It is not core validation.

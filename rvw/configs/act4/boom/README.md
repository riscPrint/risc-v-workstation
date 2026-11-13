# Bundled BOOM ACT4 profile

This is the same `rvw.act4/1` suite description used by external core
projects. The bundled `rvw/configs/boom.toml` selects its manifest-bound
ELFs as `act4-project`. The legacy `act4` suite stays available.

The profile uses RV64IMAFDC, Zba/Zbb/Zbs, Zicsr/Zifencei and Zicntr/Zihpm.
This is the ISA in the bundled comparison platform's `reference_isa`.
It declares M/S/U, Sv39, 32 physical address bits, eight usable PMP entries
and the BOOM harness memory map. The local comparison platform has no
CSR output masks. A future strict comparison can report real differences.

The UDB parameters, model macros and map come from the existing BOOM port
flow at `spinal-boom/act4/boom-rv64gc`. `source.json` records the input
file hashes and changes. Extra hint and Zicc property extensions in that
legacy flow are outside this selection. The local Sail configuration
disables those extra instruction features. The linker adds actual reset
instructions to clear mscratch and mtvec before the standard bootstrap.
The Sail IO regions and CLINT size match the bundled platform map.
The standard bootstrap and signature checks remain enabled.

## Selection and future execution

From the workstation root, inspect selection with:

```sh
rvw regress plan --act4 rvw/configs/act4/boom/profile.json --json
```

For a future authorized run, use a new output directory:

```sh
rvw regress act4-build --profile rvw/configs/act4/boom/profile.json \
  --checkout "$ACT4_CHECKOUT" --out rvw/out/act4-boom
rvw regress run --core boom --suite act4-project --rvfi-trace \
  --out /tmp/act4-boom-run
rvw regress cosim /tmp/act4-boom-run \
  --platform rvw/configs/act4/boom/platform.json
```

Set `ACT4_PROJECT_OUT` to select another build directory. Set `SPINAL_BOOM`
to the private core checkout. Use the required core lock. The manifest
must verify the complete ELF set before suite filters apply.

## Evidence limit

Only configuration loading, selection and unit tests were run for this
profile. ACT4 compilation, BOOM elaboration, BOOM simulation and BOOM
reference comparison were NOT RUN. There are no new BOOM pass counts or
certification claims. Historical results from the separate BOOM flow do
not qualify this profile.

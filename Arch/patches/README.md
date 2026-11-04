# Pinned gem5 patches

`0001-bac-branch-fallthrough.patch` applies to gem5 v25.1.0.1 at
`c8222cc67a399bfc01e8658dd14b30d5bfd634f9`. It keeps the decoded branch
length when BAC constructs a not-taken fetch target. The BTB search step can
be smaller than this length. The untrained path keeps the search step.

The patch is optional. The installer does not apply it. The native regression
in `rvw/tests/test_arch_ftq.py` fails on the unpatched release. It compares
BAC's predicted not-taken address with the next FTQ start address. It also
checks complete exits, equal retired ROI counts and FTQ activity in both modes.

Apply and build in a clean pinned source checkout. Hold the machine-wide
`gem5` lock for the entire apply and native build. Use the same Python and
SCons environment as the original native build. Limit SCons to two jobs.
For the shared reference checkout, restore the source with `git apply -R`
after the build. Keep the patch and binary hash with the experiment inputs.
The patched binary still reports version 25.1.0.1. Its SHA-256 identifies it.

Run the native regression from the workstation checkout:

```sh
RVW_TEST_GEM5_FTQ=1 \
RVW_GEM5=/absolute/path/to/patched/gem5.opt \
RVW_TEST_RISCV_TESTS=/absolute/path/to/riscv-tests/benchmarks \
RVW_RISCV_CC=/absolute/path/to/riscv64-unknown-elf-gcc \
nice -n 10 rvw/.venv/bin/python -m pytest rvw/tests/test_arch_ftq.py -q
```

The test takes the `gem5` lock itself. Do not wrap it in the same lock. It
builds one small ELF. It does not run RTL or establish hardware fidelity.

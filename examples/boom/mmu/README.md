# Directed Sv39 example

Use the native cross compiler and Spike. Run from the workstation root:

```sh
rvw regress mmu build examples/boom/mmu/scenarios.json --out /tmp/mmu-elfs --json
rvw regress mmu reference /tmp/mmu-elfs --timeout 10 --json
RVW_MMU_ELFS=/tmp/mmu-elfs rvw regress run --core boom --suite mmu-priv --jobs 1 --max-cycles 30000 --timeout 120 --rvfi-trace --no-cache --out /tmp/mmu-rtl --json
rvw regress mmu check /tmp/mmu-elfs --results /tmp/mmu-rtl --platform rvw/src/rvw/cosim/configs/boom.json --model spike --json
```

`--out` for build must be empty. Hold the BOOM lock for direct adapter runs.
`rvw regress run` holds it itself. Limit the whole command with a process-group
timeout if the shared machine is busy. A lock wait gives no RTL evidence.

`scenarios.json` selects Svade for A/D faults. `hardware-ad.json` is a separate
Svadu reference campaign. Do not merge those policies into one RTL suite unless
the core supports changing that policy. The generator is generic. This directory
holds BOOM's selected scenarios. Other S-mode projects can supply their own
JSON and an `elf-dir` suite. See the [regress README](../../../rvw/src/rvw/regress/README.md)
for requirements, PMA declarations, oracle checks and limits.

The known BOOM ACT4 Sv39 exception failures remain open. These directed tests
do not waive them. A Spike self-check pass is reference evidence only. It does
not establish a BOOM result or page-walk bus coverage.

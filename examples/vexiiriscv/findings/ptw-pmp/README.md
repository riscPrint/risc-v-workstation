# Finding: page-table reads bypass PMP

Disposition: core defect in the pinned cacheless supervisor profiles.
The workstation does not change the core. This is one cause in 19 programs:
11 Sv39 programs and 8 Sv32 programs, not 19 Sv32 programs.

[The retained records](triage.json) give each failing walk, its trace hash,
the independently built reference result and the comparison errors.
The matrix contributes two denied data walks per profile. The fault matrix
contributes three access types at each level: nine Sv39 and six Sv32 cases.
Every DUT walk succeeds. The reference stops at the denied PTE with an access
fault. No case in this group needs a superpage or an A/D update.

The privileged specification, Machine-Level ISA 1.13, section
[Physical Memory Protection and Paging](https://docs.riscv.org/reference/isa/v20260120/priv/machine.html#_physical_memory_protection_and_paging),
requires PMP checks on implicit page-table accesses with effective privilege S.
The programs write PMP before `satp`, then execute `sfence.vma x0, x0`.
The denied entries are TOR regions with no read permission. The final data
region permits the explicit access. MPRV does not permit the walker to ignore
PMP. The same rule applies to the S-mode fetch cases.

## Directed reproduction

`load.S` and `link.ld` isolate one RV64 load. They deny all page-table pages.
They expect load access fault 5, `mtval=0x40000000` and `mepc=access`.

```sh
riscv64-unknown-elf-gcc -march=rv64ima_zicsr_zifencei -mabi=lp64 \
  -nostdlib -nostartfiles -T link.ld load.S -o load.elf
spike --isa=rv64ima_zicsr_zifencei --priv=msu --pmpregions=8 \
  --pmpgranularity=16 --instructions=2000 -m0x80000000:0x1000000 \
  --pc=0x80000000 -l load.elf
rvw/run64.sh run --config rv64imasu --elf load.elf --out out \
  --rvfi-trace --wave --seed 1 --mem-latency 0 --json
```

Run the adapter from the project root. Use the private source and lock setup
in the example README. The shell commands above assume the reproduction files
are in the working directory.

On 2026-11-13 Spike raised `trap_load_access_fault` at `0x80000078` with
`tval=0x40000000`. The fresh RTL run completed the load, reached `tohost=3`
and reported C1 fail. See `directed.json` for the captured identities.

[The short wave window](walk-window.vcd) retains the walker request, accepted
PTE reads, PTE responses, completion and PMP entries from the minimal directed
capture. Time is in ps. It includes the state at the start of the window.
The three PTE reads return without a bus error. The walker reports success.
This agrees with C2. The probe did not turn an access fault into success.
The source connects the walker through `DBusAccessService.newDBusAccess`.
The load's normal execution path has a PMP port. The accepted walker reads in
this configuration do not receive the required PMP denial.

## Checker correction

The reference planner previously omitted fetch-fault scenarios. It now builds
plans for bounded `pte_fault_level` and `walk_deny_level` fetch tests. Tests
check the stopping level and result in Sv32 and Sv39. General fetch programs
still need their own access plan. Failed C1 runs stay inconclusive in the
coverage report. The direct forensic comparison here does not earn coverage
or convert a failed run into a pass.

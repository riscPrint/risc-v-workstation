# Bounded formal increment

The M/U PMP core has no closed ISA instruction proof. No result below is an
unbounded proof or full-core qualification.

## Generated rule cones and helper goals

The project selects seven checks from Core.checks.json. The helper copies the
captured RTL, removes other assertions and binds one selected fail signal per
job. It keeps a separate declared-trigger cover. Reset is active for two initial
samples. Other inputs remain arbitrary. No unproved helper is assumed.

| Check | Depth | BMC, 15-second limit | Declared-trigger cover, 15-second limit |
|---|---:|---|---|
| ROB occupancy bound | 8 | timeout | timeout |
| Rename x0 mapping | 8 | timeout | timeout |
| Generated queue occupancy rule | 8 | timeout | timeout |
| Issue operand readiness | 8 | timeout | timeout |
| Free-list conservation | 8 | timeout | timeout |
| Committed x0 mapping helper | 8 | timeout | reached |
| x0 not-free helper | 8 | timeout | reached |

A reached trigger cover does not prove its property or establish universal
activation. The helper goals did not close as invariants and were not used as
assumptions. No failure trace was produced. Timeout is not bounded pass.

## Instruction checks and measured depth

The native smoke run records 17 commits with stage IDs and PCs. Matching each
ID at rename, issue and commit gives a maximum rename-to-commit span of 35
cycles and an issue-to-commit span of 33 cycles. The divide has the latter span.
These include ROB residence. They are not isolated functional-unit service time.

The selected instruction-check depth is 40: the observed 35-cycle span, two
reset edges, one boot edge and two margin edges. This is a budget choice based
on the sample. It does not certify a maximum latency for arbitrary programs.
The instruction wrapper holds interrupt inputs low and leaves RAM data arbitrary.
It does not prove the memory system, privilege state or interrupt entry.

| riscv-formal check | Depth | Limit | Outcome |
|---|---:|---:|---|
| ADD | 40 | 15 s | timeout, inconclusive |
| LUI | 40 | 15 s | timeout, inconclusive |
| Retirement cover | 40 | 15 s | timeout, inconclusive |

The riscv-formal checkout is c992aa61fdfe0846c5ed90324c596202a1c69b76.
The tool recorded one-minute load above 56 during the ISA runs. It suggested a
longer retry at lower load. A retry with a limit of 1,800 seconds was NOT RUN because the worker
brief prohibits long formal runs. No counterexample or proof is inferred from
this limit.

## Reproduce

Generate the RTL first as described in the README. Use fresh output paths:

```sh
python3 rvw/prepare-formal.py
nice -n 10 rvw formal regress rvw/out/formal-jobs/regress.toml \
  --out rvw/out/formal --jobs 2 --timeout 15
rvw formal isa --project formal.toml --out rvw/out/isa-formal --timeout 15
```

The preparation step refuses an existing formal-jobs directory. Preserve or
remove only your own old generated directory before a new preparation.

Regenerate the measured stage sample with the native launcher:

```sh
rvw/run.sh run --elf rvw/out/programs/smoke --out rvw/out/latency-probes \
  --rvfi-trace --probes --seed 17 --wall-timeout 115
```

The probe header gives field order and stage IDs. Match the instruction ID in
rename, issue and commit records. Subtract their cycle fields. Raw captures,
formal jobs, logs and results stay under rvw/out and are not committed.

# Instruction portfolio campaign

The campaign selects every instruction in the FormalSimple project. It uses
upstream unbounded checkers. It restricts the four declared pipeline stage
valid bits to at most one active bit. Fetch queue state is not included in
that restriction. This is a conditional model, not an invariant proof.

The RAM abstraction retains word zero. The other 31 regfile words are free
per-step inputs. The RTLIL retry preserves formal cells and source assumptions.
PDR and Bitwuzla race on each check. Checks run in sequence, so at most two
proof engines are active. Each engine has a short limit. Each check also runs
a concrete retirement cover under the pipeline restriction.

```sh
export RISCV_FORMAL=PRIVATE_RISCV_FORMAL
scripts/with-lock.sh vex-conn nice -n 15 rvw/.venv/bin/python \
  examples/vexriscv/formal/portfolio_campaign.py \
  --out OUT --timeout 15 --budget 40
```

Use `--checks insn_add_ch0,insn_lui_ch0` to select a smaller retry. Keep the
project and manifest defaults to reproduce the measured profile. This is the
older FormalSimple RV32IC snapshot. It is not the FormalMTop RV32IM profile.
The historical bounded results in GENERATED_RESULTS.md apply to that same
snapshot. No M-profile result is substituted for them.

`portfolio-results.json` records the new attempts. `portfolio-table.md` gives
one row per instruction. A native proof of the restricted abstract model would
remain conditional. It would not promote the historical bounded result to
full-pipeline unbounded signoff. The earlier all-word LUI conditional proof in
ABSTRACT_RESULTS.md remains separate. Its RAM model differs from this campaign.

The bounded column is historical. It is not a new BMC run on the RAM-cut
model. The older generated wrapper and this campaign's project wrapper are
separate captures. The matching core RTL hash does not make their environments
identical. Keep the original result's wrapper and settings hashes when using
that bounded evidence. This campaign constrains instruction and data bus errors
to zero through the project wrapper. No new full-pipeline bound is claimed.

The retained historical receipt has a general retirement cover. This campaign
does not revalidate each historical instruction's activation. Run `rvw formal
isa` on a selected project to obtain the current activation checks and the full
gap inventory. A reached general cover alone does not prove that a selected
instruction executed. The new concrete covers in this campaign are retirement
covers, not independent instruction-activation certificates.

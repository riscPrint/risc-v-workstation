# Generated VexRiscv check results

Initial native run: 2026-11-13. The generated project selected 44 checks. Each check had a 110-second limit. The run used the upstream FormalSimple RTL snapshot. It did not build the workstation simulation variant.

Outcome: 42 bounded PASS, one assertion FAIL, one timeout. All 37 instruction checks returned bounded PASS. No unbounded proof or adapter-conformance pass is claimed. The C4 verdict is reject because liveness failed.

The generated wrapper has unconstrained auxiliary inputs. It has no bus fairness assumptions. Its liveness failure is an environment-scoped counterexample. It does not establish an unbounded core deadlock. The forward-PC check timed out. Later forward-PC retries are recorded below. This table retains the initial campaign outcomes.

RTL SHA-256: `545c0864dec04e72a7b74480464866c8af876c21ff7833f8f7d67dba6aa9e7c1`.
Checker SHA-256: `f5ea12d7167f0f3e2e4c3848b0667add6ddd6439c17ff6585d9c9ed306fbc0f9`.
Settings SHA-256: `59d46d365adb0555d038d8f865d42e4af52a1e527ef23b885e2d4e2771f3dbf6`.

Evidence: `/tmp/conn-vex-generated-checks/results.json`, `verdict.json`, and the per-check SBY trees. The source tree was read-only. No BOOM build or simulation ran.

| Check | Native outcome | Cycles | Engine | Wall seconds |
| --- | --- | --- | --- | --- |
| insn_add_ch0 | bounded PASS | [20] | abc bmc3 | 52.7 |
| insn_addi_ch0 | bounded PASS | [20] | abc bmc3 | 16.5 |
| insn_and_ch0 | bounded PASS | [20] | abc bmc3 | 12.7 |
| insn_andi_ch0 | bounded PASS | [20] | abc bmc3 | 15.1 |
| insn_auipc_ch0 | bounded PASS | [20] | abc bmc3 | 21.7 |
| insn_beq_ch0 | bounded PASS | [20] | abc bmc3 | 28.1 |
| insn_bge_ch0 | bounded PASS | [20] | abc bmc3 | 27.7 |
| insn_bgeu_ch0 | bounded PASS | [20] | abc bmc3 | 49.3 |
| insn_blt_ch0 | bounded PASS | [20] | abc bmc3 | 47.0 |
| insn_bltu_ch0 | bounded PASS | [20] | abc bmc3 | 55.0 |
| insn_bne_ch0 | bounded PASS | [20] | abc bmc3 | 75.0 |
| insn_jal_ch0 | bounded PASS | [20] | abc bmc3 | 57.8 |
| insn_jalr_ch0 | bounded PASS | [20] | abc bmc3 | 17.9 |
| insn_lb_ch0 | bounded PASS | [20] | abc bmc3 | 40.0 |
| insn_lbu_ch0 | bounded PASS | [20] | abc bmc3 | 40.6 |
| insn_lh_ch0 | bounded PASS | [20] | abc bmc3 | 39.3 |
| insn_lhu_ch0 | bounded PASS | [20] | abc bmc3 | 98.4 |
| insn_lui_ch0 | bounded PASS | [20] | abc bmc3 | 26.9 |
| insn_lw_ch0 | bounded PASS | [20] | abc bmc3 | 86.0 |
| insn_or_ch0 | bounded PASS | [20] | abc bmc3 | 11.6 |
| insn_ori_ch0 | bounded PASS | [20] | abc bmc3 | 21.0 |
| insn_sb_ch0 | bounded PASS | [20] | abc bmc3 | 43.0 |
| insn_sh_ch0 | bounded PASS | [20] | abc bmc3 | 49.9 |
| insn_sll_ch0 | bounded PASS | [20] | abc bmc3 | 36.5 |
| insn_slli_ch0 | bounded PASS | [20] | abc bmc3 | 18.6 |
| insn_slt_ch0 | bounded PASS | [20] | abc bmc3 | 25.0 |
| insn_slti_ch0 | bounded PASS | [20] | abc bmc3 | 29.6 |
| insn_sltiu_ch0 | bounded PASS | [20] | abc bmc3 | 26.0 |
| insn_sltu_ch0 | bounded PASS | [20] | abc bmc3 | 22.8 |
| insn_sra_ch0 | bounded PASS | [20] | abc bmc3 | 29.2 |
| insn_srai_ch0 | bounded PASS | [20] | abc bmc3 | 25.9 |
| insn_srl_ch0 | bounded PASS | [20] | abc bmc3 | 29.5 |
| insn_srli_ch0 | bounded PASS | [20] | abc bmc3 | 23.0 |
| insn_sub_ch0 | bounded PASS | [20] | abc bmc3 | 19.8 |
| insn_sw_ch0 | bounded PASS | [20] | abc bmc3 | 19.2 |
| insn_xor_ch0 | bounded PASS | [20] | abc bmc3 | 15.5 |
| insn_xori_ch0 | bounded PASS | [20] | abc bmc3 | 15.2 |
| reg_ch0 | bounded PASS | [15, 20] | abc bmc3 | 10.7 |
| pc_fwd_ch0 | timeout | [10, 30] | btor btormc | 110.1 |
| pc_bwd_ch0 | bounded PASS | [10, 30] | abc bmc3 | 32.8 |
| liveness_ch0 | assertion FAIL | [1, 10, 30] | abc bmc3 | 56.2 |
| unique_ch0 | bounded PASS | [1, 10, 30] | abc bmc3 | 25.9 |
| causal_ch0 | bounded PASS | [10, 30] | abc bmc3 | 39.8 |
| cover | bounded PASS | [1, 20] | smtbmc bitwuzla | 9.2 |

## Forward-PC retries

| Attempt | Cycles | Engine | Limit seconds | Native outcome |
| --- | --- | --- | --- | --- |
| Initial campaign | [10, 30] | btor btormc | 110 | timeout |
| ABC retry | [10, 20] | abc bmc3 | 110 | timeout |
| BTORMC retry | [5, 15] | btor btormc | 90 | bounded PASS |

The BTORMC retry passed forward-PC in 15.8 wall seconds. Its retirement cover
passed at cycles [1,20] in 11.2 wall seconds. The captured RTL, wrapper and
checker hashes equal those in the initial campaign. Settings hashes differ.
The generated example now selects the [5,15] forward-PC bound.

Selected outcomes across these attempts are 43 bounded PASS and one liveness
assertion FAIL. This combines different explicit cycle bounds. It is not a
fresh uniform-depth campaign or an unbounded proof. Earlier timeouts remain
inconclusive attempts. The liveness failure and C4 reject are retained.

Retry evidence: `/tmp/conn-vex-pcfwd-abc20/results.json` and
`/tmp/conn-vex-pcfwd-btor15/results.json`.

## Generated fair bus rerun

The 2026-11-13 rerun uses `binding.json` with explicit `stream-response`
environments. Each bus accepts commands within two stalled samples and returns
one read response within two pending samples. Responses are ordered, have at
least one cycle of latency, and cannot appear without a pending read. Writes
need no response. Bus errors are constrained to zero. Instruction data and traps
are not constrained. Each bus has an asserted eight-request capacity limit.

| Check | Native outcome | Cycles | Engine |
| --- | --- | --- | --- |
| liveness_ch0 | bounded PASS | [1, 10, 30] | abc bmc3 |
| cover | reached | [1, 20] | smtbmc bitwuzla |

Liveness took 21.9 wall seconds. Retirement cover took 5.6 wall seconds.
The liveness job checks both progress and the environment tracker capacity.
This result replaces the unconstrained environment failure only for this explicit
finite-service environment. It does not establish unbounded progress, full bus
compliance, or liveness on the workstation simulation variant.
The C4 verdict remains inconclusive because these checks are bounded.

Evidence: `/tmp/conn-fair-live/results.json`, `verdict.json` and SBY trees.
The source revision is `c992aa61fdfe0846c5ed90324c596202a1c69b76`.
RTL SHA-256: `545c0864dec04e72a7b74480464866c8af876c21ff7833f8f7d67dba6aa9e7c1`.
Generated wrapper SHA-256: `992bb0e03f0d4e82004670350c67c5c29c3e3943adb15cb073d93f77daf1b4ad`.
Settings SHA-256: `b46dc49a83368f98bab27fdaaec76aaed6908aac4d0998aa579e50d31fcbb4c1`.
The run used a private source copy and `scripts/with-lock.sh vex-conn nice -n 10`.

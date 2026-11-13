# Supervisor coverage review

The stable corpus has 717 observed traces and 447 qualified traces.
It includes 270 ACT4 cases, 49 riscv-tests, four generated random privilege
programs and 394 generated PMP programs. All generated programs were run
again on the private VexiiRiscv supervisor target. All 398 pass C1 and have
complete strict Spike matches. The 270 ACT4 cases fail before their bodies.

Qualification requires C1 pass and a complete strict Spike match.
The 49 riscv-tests retain their saved qualification and exact raw C2 hashes.
New ACT4 and generated traces have fresh reference checks. No IRQ device
corpus, generated MMU corpus, or other ISA context enters this merge.

## Remaining instruction holes by extension

The bins come from pinned riscv-opcodes, not a list of core test names.
This measures instruction encodings seen anywhere in the trace, including
bootstrap and signatures. ECALL and EBREAK always trap; this instruction
domain excludes trapping instructions. Their instruction-bin holes do not
prove missing trap tests. Inspect the trap groups separately.
It does not prove functional completion of an
extension. Operand, privilege, trap and memory holes remain in the JSON.

| Extension | Qualified instruction bins | Missing instructions |
|---|---:|---|
| A | 0/11 | `amoadd.w`, `amoand.w`, `amomax.w`, `amomaxu.w`, `amomin.w`, `amominu.w`, `amoor.w`, `amoswap.w`, `amoxor.w`, `lr.w`, `sc.w` |
| I | 38/40 | `ebreak`, `ecall` |
| M | 8/8 | None in this domain |
| ZICSR | 4/6 | `csrrci`, `csrrsi` |
| ZIFENCEI | 1/1 | None in this domain |

Sm, S, U and Sv32 do not have complete instruction-only domains in this
plan. The random and PMP runs reach privilege transitions and protection
cases. They do not qualify the blocked ACT4 privileged bodies. Full Sv32
translation, interrupt devices and environment CSR behavior remain open.

## Fixed-domain holes

| Group | Observed holes | Qualified holes |
|---|---:|---:|
| branch | 0 | 0 |
| class_mode | 13 | 14 |
| csr | 0 | 0 |
| dependency | 0 | 0 |
| handler_entry | 1 | 1 |
| interrupt_cause_mode | 0 | 0 |
| memory | 10 | 10 |
| mnemonic_mode | 0 | 0 |
| rd_x0 | 0 | 0 |
| sem_add_rs1 | 0 | 1 |
| sem_add_rs2 | 1 | 1 |
| sem_addi_imm12 | 0 | 0 |
| sem_addi_rs1 | 0 | 0 |
| sem_amoadd.w_rs1 | 7 | 7 |
| sem_amoadd.w_rs2 | 7 | 7 |
| sem_amoand.w_rs1 | 7 | 7 |
| sem_amoand.w_rs2 | 7 | 7 |
| sem_amomax.w_rs1 | 7 | 7 |
| sem_amomax.w_rs2 | 7 | 7 |
| sem_amomaxu.w_rs1 | 7 | 7 |
| sem_amomaxu.w_rs2 | 7 | 7 |
| sem_amomin.w_rs1 | 7 | 7 |
| sem_amomin.w_rs2 | 7 | 7 |
| sem_amominu.w_rs1 | 7 | 7 |
| sem_amominu.w_rs2 | 7 | 7 |
| sem_amoor.w_rs1 | 7 | 7 |
| sem_amoor.w_rs2 | 7 | 7 |
| sem_amoswap.w_rs1 | 7 | 7 |
| sem_amoswap.w_rs2 | 7 | 7 |
| sem_amoxor.w_rs1 | 7 | 7 |
| sem_amoxor.w_rs2 | 7 | 7 |
| sem_and_rs1 | 4 | 4 |
| sem_and_rs2 | 4 | 4 |
| sem_andi_imm12 | 3 | 3 |
| sem_andi_rs1 | 3 | 4 |
| sem_beq_rs1 | 2 | 2 |
| sem_beq_rs2 | 2 | 2 |
| sem_bge_rs1 | 2 | 3 |
| sem_bge_rs2 | 2 | 3 |
| sem_bgeu_rs1 | 2 | 2 |
| sem_bgeu_rs2 | 2 | 2 |
| sem_blt_rs1 | 1 | 2 |
| sem_blt_rs2 | 2 | 3 |
| sem_bltu_rs1 | 2 | 2 |
| sem_bltu_rs2 | 1 | 2 |
| sem_bne_rs1 | 0 | 0 |
| sem_bne_rs2 | 0 | 0 |
| sem_csrrc_access | 1 | 1 |
| sem_csrrc_exception | 1 | 1 |
| sem_csrrc_rs1 | 6 | 6 |
| sem_csrrci_access | 2 | 2 |
| sem_csrrci_exception | 1 | 1 |
| sem_csrrs_access | 0 | 0 |
| sem_csrrs_exception | 1 | 1 |
| sem_csrrs_rs1 | 5 | 5 |
| sem_csrrsi_access | 2 | 2 |
| sem_csrrsi_exception | 1 | 1 |
| sem_csrrw_access | 0 | 1 |
| sem_csrrw_exception | 1 | 1 |
| sem_csrrw_rs1 | 2 | 2 |
| sem_csrrwi_access | 1 | 1 |
| sem_csrrwi_exception | 1 | 1 |
| sem_div_rs1 | 2 | 2 |
| sem_div_rs2 | 2 | 2 |
| sem_divu_rs1 | 2 | 2 |
| sem_divu_rs2 | 2 | 2 |
| sem_ebreak_exception | 1 | 1 |
| sem_ecall_exception | 1 | 1 |
| sem_fence.i_imm12 | 4 | 4 |
| sem_fence_rs1 | 6 | 6 |
| sem_jalr_imm12 | 1 | 3 |
| sem_jalr_rs1 | 6 | 6 |
| sem_lb_exception | 1 | 1 |
| sem_lb_imm12 | 2 | 2 |
| sem_lb_rs1 | 6 | 6 |
| sem_lbu_exception | 1 | 1 |
| sem_lbu_imm12 | 2 | 2 |
| sem_lbu_rs1 | 6 | 6 |
| sem_lh_exception | 2 | 2 |
| sem_lh_imm12 | 2 | 2 |
| sem_lh_rs1 | 6 | 6 |
| sem_lhu_exception | 2 | 2 |
| sem_lhu_imm12 | 2 | 2 |
| sem_lhu_rs1 | 6 | 6 |
| sem_lr.w_rs1 | 7 | 7 |
| sem_lw_exception | 2 | 2 |
| sem_lw_imm12 | 2 | 2 |
| sem_lw_rs1 | 6 | 6 |
| sem_mul_rs1 | 1 | 1 |
| sem_mul_rs2 | 2 | 2 |
| sem_mulh_rs1 | 1 | 1 |
| sem_mulh_rs2 | 2 | 2 |
| sem_mulhsu_rs1 | 1 | 1 |
| sem_mulhsu_rs2 | 2 | 2 |
| sem_mulhu_rs1 | 1 | 1 |
| sem_mulhu_rs2 | 2 | 2 |
| sem_or_rs1 | 4 | 4 |
| sem_or_rs2 | 3 | 4 |
| sem_ori_imm12 | 3 | 3 |
| sem_ori_rs1 | 4 | 4 |
| sem_privilege_transition | 0 | 0 |
| sem_rem_rs1 | 2 | 2 |
| sem_rem_rs2 | 2 | 2 |
| sem_remu_rs1 | 2 | 2 |
| sem_remu_rs2 | 2 | 2 |
| sem_sb_exception | 1 | 1 |
| sem_sb_rs1 | 6 | 6 |
| sem_sb_rs2 | 3 | 3 |
| sem_sc.w_rs1 | 7 | 7 |
| sem_sc.w_rs2 | 7 | 7 |
| sem_sh_exception | 2 | 2 |
| sem_sh_rs1 | 6 | 6 |
| sem_sh_rs2 | 5 | 5 |
| sem_sll_rs1 | 3 | 3 |
| sem_sll_rs2 | 3 | 3 |
| sem_slli_rs1 | 3 | 3 |
| sem_slt_rs1 | 1 | 1 |
| sem_slt_rs2 | 2 | 2 |
| sem_slti_imm12 | 0 | 0 |
| sem_slti_rs1 | 1 | 1 |
| sem_sltiu_imm12 | 0 | 0 |
| sem_sltiu_rs1 | 1 | 1 |
| sem_sltu_rs1 | 1 | 1 |
| sem_sltu_rs2 | 2 | 2 |
| sem_sra_rs1 | 2 | 2 |
| sem_sra_rs2 | 2 | 2 |
| sem_srai_rs1 | 2 | 2 |
| sem_srl_rs1 | 1 | 2 |
| sem_srl_rs2 | 2 | 2 |
| sem_srli_rs1 | 2 | 2 |
| sem_sub_rs1 | 0 | 0 |
| sem_sub_rs2 | 2 | 2 |
| sem_sw_exception | 2 | 2 |
| sem_sw_rs1 | 6 | 6 |
| sem_sw_rs2 | 3 | 4 |
| sem_xor_rs1 | 4 | 4 |
| sem_xor_rs2 | 4 | 4 |
| sem_xori_imm12 | 3 | 3 |
| sem_xori_rs1 | 4 | 4 |
| trap_cause_mode | 0 | 0 |

The JSON files retain every bin and hole, the pinned opcode inputs and
raw trace hashes. The corpus ledger retains each C1 and qualification
decision. Default domains include unsupported or unreachable cases. A hole
does not by itself prove a core defect. A hit does not qualify an extension.

Historical `corpus.json`: {"scope":"ACT4 plus riscv-tests plus four generated random privilege programs and 394 PMP programs; other generated families are not included","observed":717,"qualified":447}.
Raw records are no longer tracked. Regenerate outside the repository:
`rvw cov functional TRACE_PATHS --platform PLATFORM --json`. Use the pinned inputs and options from [PR #1198](https://github.com/riscPrint/risc-v-workstation/pull/1198).

Historical `observed.json`: {"groups":{"entries":316},"notes":{"records":8},"retired":369607,"traces":{"entries":717},"unknown_encodings":{"entries":0}}.
Raw records are no longer tracked. Regenerate outside the repository:
`rvw cov functional TRACE_PATHS --platform PLATFORM --json`. Use the pinned inputs and options from [PR #1198](https://github.com/riscPrint/risc-v-workstation/pull/1198).

Historical `qualified.json`: {"groups":{"entries":316},"notes":{"records":8},"retired":52750,"traces":{"entries":447},"unknown_encodings":{"entries":0}}.
Raw records are no longer tracked. Regenerate outside the repository:
`rvw cov functional TRACE_PATHS --platform PLATFORM --json`. Use the pinned inputs and options from [PR #1198](https://github.com/riscPrint/risc-v-workstation/pull/1198).

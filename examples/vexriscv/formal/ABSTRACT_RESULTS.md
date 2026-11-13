# Conditional instruction abstraction results

The 2026-11-13 attempts use the older FormalSimple RV32IC snapshot, not the
new RV32IM Sail profile. They capture upstream unbounded instruction checkers.
The check input is arbitrary. The source is not a fixed-cycle BMC property.

The project map lists decode, execute, memory and writeback validity. Their
sum is constrained to at most one. Fetch queues are not included in this
restriction. The RAM abstraction frees register-file word state. This is an
overapproximation of RAM behavior. Source reset and checker assumptions remain.
Each engine had a 180-second limit. Each concrete restricted source also had
an instruction cover with depth 20. All three concrete covers reached in each
campaign. These covers do not certify every assumption or the RVFI adapter.

| Variant | Instruction | Native outcome | Scope |
| --- | --- | --- | --- |
| All 32 words abstract, RTLIL | ADD | PDR engine ERROR | Counterexample witness conversion failed |
| All 32 words abstract, RTLIL | AND | PDR engine ERROR | Counterexample witness conversion failed |
| All 32 words abstract, RTLIL | LUI | PDR PASS, 107.4 seconds | Unbounded conditional RAM overapproximation |
| All 32 words abstract, RTLIL | ADD | SMT FAIL | Abstract counterexample |
| All 32 words abstract, RTLIL | AND | SMT FAIL | Abstract counterexample |
| All 32 words abstract, RTLIL | LUI | SMT inconclusive | No second proof closed |
| Word zero retained, 31 words abstract | ADD | PDR timeout | 180 seconds |
| Word zero retained, 31 words abstract | AND | PDR timeout | 180 seconds |
| Word zero retained, 31 words abstract | LUI | PDR timeout | 180 seconds |

The ADD SMT trace gives abstract x0 storage a nonzero value. The RTLIL retry
can retain selected concrete words through `keep_words`. It uses the real
driver and initial state. It does not assume the word is zero. The retained-word
retry timed out. No abstract counterexample is reported as a core defect.

The LUI native proof closed for the all-word abstraction under the declared
single-flight restriction. The top-level result stays inconclusive because
full pipeline behavior, source assumption activation and adapter conformance
are not established. The later timeout does not replace that earlier native
proof. It is a different model and an explicit additional attempt.

## Representation and backend limits

The first shared RAM runner attempt exported `$initstate` and `$anyseq` as
internal Verilog cells. The portfolio reader could not resolve them. No engine
proof ran in that attempt. The integration retry uses the cut JSON netlist and
RTLIL. It preserves the formal cells and assumptions.

PDR found abstract ADD and AND counterexamples. Its witness conversion then
failed on `IBusSimplePlugin_predictor_history` memory metadata. The final
native status is ERROR. The SMT runs produced usable abstract counterexamples.
The tool does not substitute an error for a pass or call it a core failure.

## Reproduction

```sh
rvw formal riscv-abstract --project examples/vexriscv/formal \
  --manifest examples/vexriscv/formal/abstract.json \
  --checks insn_add_ch0,insn_and_ch0,insn_lui_ch0 --out OUT --timeout 180 --budget 400
```

The checked-in map retains word zero. Use a separate manifest without
`keep_words` to repeat the all-word abstraction. Use
`--engines smtbmc:yices` for the SMT attempt. Keep at most three native proof
jobs active. Use a private source copy, `vex-conn` and `nice -n 10`.

Private evidence directories are `abstract-insn_*_ch0-v1` through
`abstract-insn_*_ch0-v4` under the worker's existing private evidence tree.
Version 1 records the export failure. Version 2 is the all-word PDR retry.
Version 3 is the all-word SMT retry. Version 4 retains word zero.
Each directory keeps capture manifests, source hashes, RAM netlists, native
engine results and concrete cover traces. The original RTL hash is
`545c0864dec04e72a7b74480464866c8af876c21ff7833f8f7d67dba6aa9e7c1`.

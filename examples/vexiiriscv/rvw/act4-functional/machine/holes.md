# Functional coverage holes

Observed traces: 107. Qualified traces: 107.

The observed merge includes failed prefixes, boot and signature checks.
The qualified stream requires C1 pass and a complete strict Spike match.
Neither stream establishes ACT4 body coverage or certification.
Default domains do not assert ISA support or reachability.
Groups without declared bins have no completeness percentage.

| Group | Observed hit / expected | Qualified hit / expected |
|---|---:|---:|
| branch | 2 / 6 | 2 / 6 |
| class_mode | 10 / 36 | 10 / 36 |
| csr | 16 observed, no fixed domain | 16 observed, no fixed domain |
| dependency | 18 observed, no fixed domain | 18 observed, no fixed domain |
| handler_entry | 1 / 3 | 1 / 3 |
| interrupt_cause_mode | 0 observed, no fixed domain | 0 observed, no fixed domain |
| memory | 6 / 16 | 6 / 16 |
| mnemonic_mode | 54 observed, no fixed domain | 54 observed, no fixed domain |
| rd_x0 | 16 observed, no fixed domain | 16 observed, no fixed domain |
| trap_cause_mode | 2 observed, no fixed domain | 2 observed, no fixed domain |

## Observed holes

branch: 4 holes.

- `[false, "S"]`
- `[false, "U"]`
- `[true, "S"]`
- `[true, "U"]`

class_mode: 26 holes.

- `["alu", "S"]`
- `["alu", "U"]`
- `["atomic", "M"]`
- `["atomic", "S"]`
- `["atomic", "U"]`
- `["branch", "S"]`
- `["branch", "U"]`
- `["csr", "S"]`
- `["csr", "U"]`
- `["divide", "S"]`
- `["divide", "U"]`
- `["fence", "S"]`
- `["fence", "U"]`
- `["float", "M"]`
- `["float", "S"]`
- `["float", "U"]`
- `["jump", "S"]`
- `["jump", "U"]`
- `["load", "S"]`
- `["load", "U"]`
- `["multiply", "S"]`
- `["multiply", "U"]`
- `["store", "S"]`
- `["store", "U"]`
- `["system", "S"]`
- `["system", "U"]`

handler_entry: 2 holes.

- `["S"]`
- `["U"]`

memory: 10 holes.

- `["read", 1, "misaligned"]`
- `["read", 2, "misaligned"]`
- `["read", 4, "misaligned"]`
- `["read", 8, "aligned"]`
- `["read", 8, "misaligned"]`
- `["write", 1, "misaligned"]`
- `["write", 2, "misaligned"]`
- `["write", 4, "misaligned"]`
- `["write", 8, "aligned"]`
- `["write", 8, "misaligned"]`

Unknown encodings: `{}`.

## Qualified holes

branch: 4 holes.

- `[false, "S"]`
- `[false, "U"]`
- `[true, "S"]`
- `[true, "U"]`

class_mode: 26 holes.

- `["alu", "S"]`
- `["alu", "U"]`
- `["atomic", "M"]`
- `["atomic", "S"]`
- `["atomic", "U"]`
- `["branch", "S"]`
- `["branch", "U"]`
- `["csr", "S"]`
- `["csr", "U"]`
- `["divide", "S"]`
- `["divide", "U"]`
- `["fence", "S"]`
- `["fence", "U"]`
- `["float", "M"]`
- `["float", "S"]`
- `["float", "U"]`
- `["jump", "S"]`
- `["jump", "U"]`
- `["load", "S"]`
- `["load", "U"]`
- `["multiply", "S"]`
- `["multiply", "U"]`
- `["store", "S"]`
- `["store", "U"]`
- `["system", "S"]`
- `["system", "U"]`

handler_entry: 2 holes.

- `["S"]`
- `["U"]`

memory: 10 holes.

- `["read", 1, "misaligned"]`
- `["read", 2, "misaligned"]`
- `["read", 4, "misaligned"]`
- `["read", 8, "aligned"]`
- `["read", 8, "misaligned"]`
- `["write", 1, "misaligned"]`
- `["write", 2, "misaligned"]`
- `["write", 4, "misaligned"]`
- `["write", 8, "aligned"]`
- `["write", 8, "misaligned"]`

Unknown encodings: `{}`.

# Functional coverage holes

Observed traces: 319. Qualified traces: 49.

The observed merge includes failed prefixes, boot and signature checks.
The qualified stream requires C1 pass and a complete strict Spike match.
Neither stream establishes ACT4 body coverage or certification.
Default domains do not assert ISA support or reachability.
Groups without declared bins have no completeness percentage.

| Group | Observed hit / expected | Qualified hit / expected |
|---|---:|---:|
| branch | 4 / 6 | 4 / 6 |
| class_mode | 16 / 36 | 14 / 36 |
| csr | 34 observed, no fixed domain | 11 observed, no fixed domain |
| dependency | 17 observed, no fixed domain | 17 observed, no fixed domain |
| handler_entry | 1 / 3 | 1 / 3 |
| interrupt_cause_mode | 0 observed, no fixed domain | 0 observed, no fixed domain |
| memory | 6 / 16 | 6 / 16 |
| mnemonic_mode | 75 observed, no fixed domain | 60 observed, no fixed domain |
| rd_x0 | 14 observed, no fixed domain | 14 observed, no fixed domain |
| trap_cause_mode | 3 observed, no fixed domain | 2 observed, no fixed domain |

## Observed holes

branch: 2 holes.

- `[false, "S"]`
- `[true, "S"]`

class_mode: 20 holes.

- `["alu", "S"]`
- `["atomic", "M"]`
- `["atomic", "S"]`
- `["atomic", "U"]`
- `["branch", "S"]`
- `["csr", "S"]`
- `["csr", "U"]`
- `["divide", "M"]`
- `["divide", "S"]`
- `["fence", "S"]`
- `["float", "M"]`
- `["float", "S"]`
- `["float", "U"]`
- `["jump", "S"]`
- `["load", "S"]`
- `["multiply", "M"]`
- `["multiply", "S"]`
- `["store", "S"]`
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

branch: 2 holes.

- `[false, "S"]`
- `[true, "S"]`

class_mode: 22 holes.

- `["alu", "S"]`
- `["atomic", "M"]`
- `["atomic", "S"]`
- `["atomic", "U"]`
- `["branch", "S"]`
- `["csr", "S"]`
- `["csr", "U"]`
- `["divide", "M"]`
- `["divide", "S"]`
- `["fence", "M"]`
- `["fence", "S"]`
- `["float", "M"]`
- `["float", "S"]`
- `["float", "U"]`
- `["jump", "S"]`
- `["load", "M"]`
- `["load", "S"]`
- `["multiply", "M"]`
- `["multiply", "S"]`
- `["store", "S"]`
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

# RV32 F/C ACT4 profile

| Check | Result |
|---|---|
| ISA groups | F, Zca and Zcf; C metadata is also declared |
| Reference build | 110 self-checking ELFs: F 80, Zca 26, Zcf 4 |
| DUT run and strict Spike comparison | NOT RUN |

Use the RV64 profile commands with `32` in place of `64`. This profile has
FLEN 32 and no D. It uses the same reduced CSR bootstrap and private cache
requirements. No certification or F/C qualification is claimed.

# RV64 machine ACT4 profile

The profile selects I, M, Zmmul, Zaamo, Zalrsc, Zicsr and Zifencei at RV64.
It uses the same reduced CSR bootstrap as the RV32 instruction profile.
It does not claim standard Sm compatibility.

Native results: 98 built, 98 self-check passes and 98 complete strict Spike
matches. No synchronization or output mask was used. Core sources were
unchanged. See [per-test hashes and extension counts](results.json).

The first campaign crossed a tools revision change. Its 49 affected records
remain inconclusive. A stable run replaced each of them before qualification.
No invalid record is counted as a match.

From the example project, use `rvw regress act4-build --profile
rvw/act4-64m/profile.json --checkout "$ACT4_CHECKOUT" --out
rvw/out/act4-rv64m`. Select `rvw64m.toml` for `rvw regress run --suite
act4-rv64 --rvfi-trace`. Compare with `rvw/platform64m.json` in strict mode.
The setup requirements in docs/ACT4.md apply.

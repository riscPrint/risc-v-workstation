# Debug module and sessions contracts

Part of the [platform contracts](../PLATFORM_CONTRACTS.md).

## Debug session (`rvw.debug-session/1`)

`rvw wave session save` writes JSON with `schema`, `artifacts` (map of role to `path`, `name`,
`size`, `sha256`; roles `wave`, `database`, `result`, `extraN`), `signals` (full wave names),
`cursors` (sorted non-negative wave times), `queries` (embedded `rvw.wave-query/1` objects as
saved) and `note`. `session open` returns `status` (`complete` or `incomplete`), per-role
`artifacts` status (`ok`, `changed`, `missing`), `missing_signals`, and the saved fields. A
session binds file bytes only; it is not a run identity or verdict.

## Local integrated debug session

`python -m rvw.query.session --db DESIGN --wave SNAPSHOT.rvwi` holds one C6
database capture until exit. Stdio carries one JSON object per line. Requests
have integer `id` and `op`: `open`, `select`, `source` or `trace`. Responses echo
`id`. Success includes `result`, `database` (the capture record) and
`elapsed_ms` (backend time). Failure includes `error` and `status: inconclusive`.
`select` uses `signal`, decimal string `time` and optional decimal string `end`.
It returns the preceding value and at most 500 changes, with a truncation flag.
Change times are decimal strings. `source` uses `file` and integer `line` and
returns all candidates, without choosing among ambiguous mappings. `trace` uses
`signal` and `time`. It exports database PDG/HGLDD, checks the original VCD hash
and invokes SpinalTrace. Static drivers remain distinct from dynamic evidence.
The selected database and wave identities do not establish a shared C1 run.
The loopback web host exposes the same requests at `POST /api`. These are local
UI transport operations. They issue no simulation or acceptance verdict.

## Progress-possibility app

`rvw.deadlock-app/1` reports reachable states, states with no progress path,
terminal states and states without an admissible fair infinite continuation.
The explicit finite graph supplies the state and edge universe. Fairness uses
state justice. A pass establishes progress possibility in that graph only.
Infeasible fairness remains inconclusive. No RTL translation claim is added.

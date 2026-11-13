| Construct | Corpus | Scope |
|---|---|---|
| `first_match` | positive and negative native case | finite, single clock |
| `throughout` | positive and negative native case | finite, single clock |
| `within` | positive and negative native case | finite, single clock |
| `intersect` | positive and negative native case | finite, single clock |
| `$past depth` | positive and negative native case | finite, single clock |
| `$past nested` | positive and negative native case | finite, single clock |
| `$past signed` | positive and negative native case | finite, single clock |
| `$past unsigned` | positive and negative native case | finite, single clock |
| `$past` | positive and negative native case | finite, single clock |
| `$rose` | positive and negative native case | finite, single clock |
| `$fell` | positive and negative native case | finite, single clock |
| `$stable` | positive and negative native case | finite, single clock |
| `$changed` | positive and negative native case | finite, single clock |
| `local variables` | positive and negative native case | finite, single clock |
| `local assignment flow` | positive and negative native case | finite, single clock |
| `s_eventually` | positive and negative native case | infinite trace, single clock; `formal liveness` |
| `until` | positive and negative native case | infinite trace, single clock; `formal liveness` |
| `until_with` | positive and negative native case | infinite trace, single clock; `formal liveness` |
| `s_until` | positive and negative native case | infinite trace, single clock; `formal liveness` |
| `s_until_with` | positive and negative native case | infinite trace, single clock; `formal liveness` |
| `##[M:$]` | positive and negative native case | infinite trace, single clock; `formal liveness` |
| `[*M:$]` | positive and negative native case | infinite trace, single clock; `formal liveness` |
| `[*]` | positive and negative native case | infinite trace, single clock; `formal liveness` |
| `[->N]` | positive and negative native case | infinite trace, single clock; `formal liveness` |
| `[=N]` | positive and negative native case | infinite trace, single clock; `formal liveness` |
| `strong / weak` | positive and negative native case | infinite trace, single clock; `formal liveness` |
| `unbounded first_match` | positive and negative native case | infinite trace, single clock; `formal liveness` |
| `multi-clock overlapped implication` | positive and negative native case | finite native timed replay; two clocks |
| `multi-clock nonoverlapped implication` | positive and negative native case | finite native timed replay; two clocks |
| `liveness $past` | positive and negative native case | single-clock liveness; sampled history |
| `liveness $rose` | positive and negative native case | single-clock liveness; sampled history |
| `liveness $fell` | positive and negative native case | single-clock liveness; sampled history |
| `liveness $stable` | positive and negative native case | single-clock liveness; sampled history |
| `liveness $changed` | positive and negative native case | single-clock liveness; sampled history |
| `goto/nonconsecutive count ranges` | positive and negative native case | infinite trace, single clock; literal ranges |
| `unbounded throughout` | positive and negative native case | infinite trace, single clock; Boolean guard |
| `native eventual response observations` | positive and negative native case | finite witness, failure and pending counts; both simulators |
| `native until observations` | positive and negative native case | finite witness, failure and pending counts; both simulators |

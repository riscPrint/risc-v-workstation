# rvw bugmem

Bug-pattern memory. Store each understood failure with its signature, root cause, fix and
verified scope. Match a new failure report against the store to find similar past failures.

```sh
rvw bugmem add   REPORT --cause TEXT [--fix TEXT] [--scope TEXT] [--label CLASS]
rvw bugmem match REPORT [--top 5] [--min-score 0.2]
rvw bugmem list
rvw bugmem evaluate [--top 3]
```

`REPORT` is an `rvw bundle` `summary.json` (`rvw.bundle/1`), a bundle directory, a C1
`result.json` or a run directory. All commands take `--json` and `--store PATH`. MCP:
`bugmem_add`, `bugmem_match`, `bugmem_list`, `bugmem_evaluate`.

## Signature features

Weighted features from the report: C3 `signature` (weight 4), assertion source file (3),
suspected unit, oldest unretired instruction class, trap causes and channels stalled more than
100 cycles (2 each), status, last retired function, spin loop and old open requests (1 each),
and message words without numbers or addresses (0.5 each). The score is the weighted Jaccard
similarity of two feature sets. `match` lists candidates at or above `--min-score` with the
shared features and the stored cause, fix and scope. Status is `candidates` or `no_match`.

## Store

A JSON-lines file (`rvw.bugmem/1` records) outside the repository: `--store`, `RVW_BUGMEM`, or
`~/.local/share/rvw/bugmem.jsonl`. Each record keeps the features, cause, fix, scope, label and
the report's path, SHA-256 and recorded source/core/config/ELF identity. Adding the same report
bytes twice is refused. Do not commit stores of historical failures to this repository.

## Decisions

- A candidate is a lead to check, not a diagnosis. The output says so and never claims that two
  failures have the same root cause.
- A cause is required to store a failure. Fix and scope are optional and printed as stored.
- `evaluate` runs leave-one-out over labelled records of this store: top-1 and top-k accuracy.
  Labels that occur once cannot be found and count as `unmatchable`, not as misses. The result
  makes no claim beyond the stored defects.

## Limits

- Features come only from fields the report has. A C1 result alone gives status, signature and
  message words.
- No automatic import from bisect results or issue trackers.
- Fixed weights; not tuned on a held-out defect set yet.

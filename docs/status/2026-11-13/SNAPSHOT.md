# Collection record

Hourly refresh collected at 2026-11-13T08:21:26.898955+00:00: 80 additional merged PRs; 563 merged PRs in total; 213 current open issues; 7 currently closed issues closed since midnight. The 218-issue midnight census and separate new issues #722 and #723 are unchanged. Earlier collection text below is historical. The refresh notes take precedence for current state. No project tests, builds, simulations or proofs ran.

Snapshot collected at 2026-11-13T07:16:42.340567+00:00. PR merge window starts at 2026-11-13T00:00:00Z. This is a reading audit. No tests, builds, simulations or proofs ran for this report. PR bodies report the evidence. Their artifacts were not independently rerun.

Raw JSON is outside the repository at `/tmp/rvw-status-2026-11-13`.

```json
{
  "collectedAt": "2026-11-13T07:16:42.340567+00:00",
  "mergeWindowStart": "2026-11-13T00:00:00Z",
  "mainHead": "e8f60458fe47d5c25dc2c0426449349c98378a39",
  "mergedPRs": 483,
  "openIssues": 206,
  "closedToday": 14,
  "midnightIssues": 218,
  "newToday": [
    722,
    723
  ],
  "rawLocation": "/tmp/rvw-status-2026-11-13",
  "rawSha256": {
    "prs.json": "4679e6f8d315add5c987c1f2370d4c763d1f07b675076221480ae4f92eb464da",
    "open.json": "90aa097f0abbb58110a3579083bbdd8e753cb1ad889b60faa5c72271485f213d",
    "381.json": "8541edc10f5be28554a214e69cdd338fa071389f2e502bc43c321e66da2baeca",
    "timelines.json": "2e094074170b4121f1cc32c8deb3d315537fa09d7802e8bd9fd684a85a7b020b",
    "closed.json": "e5c4dcd0a65c536d280ab56d5d8ade8576c8298bd20aab46bc0fae3115d7be81",
    "381-files.json": "ae526c04595d3f74ea92963396c9335fc90965b1daf0e6187b8630aa50e2ec72"
  }
}
```

Queries used `gh pr list --state merged --search "merged:>=2026-11-13" --limit 1000 --json number,title,body,mergedAt,files` and `gh issue list` for open and closed issues. All commands selected `riscPrint/risc-v-workstation`. Issue collection also requested creation and closure dates. GraphQL collected closure/reopen events. PR #381 body, file list and diff were saved separately. PR file lists are discovery aids; they can be truncated by GitHub for large PRs. PR bodies are the evidence source.

## Refresh collection

```json
{
  "collectedAt": "2026-11-13T08:21:26.898955+00:00",
  "baseHead": "be8cb7286c831f9e3c0f7697ecd46a06e7670dbe",
  "previousMergedPRs": 483,
  "additionalMergedPRs": 80,
  "mergedPRs": 563,
  "openIssues": 213,
  "currentlyClosedSinceMidnight": 7,
  "issuesWithClosureEventSinceMidnight": [
    64,
    70,
    85,
    87,
    106,
    118,
    127,
    133,
    153,
    156,
    161,
    185,
    206,
    296,
    349,
    379
  ],
  "midnightIssues": 218,
  "newToday": [
    722,
    723
  ],
  "rawLocation": "/tmp/rvw-status-2026-11-13/refresh",
  "rawSha256": {
    "milestone-map.json": "b2699a6e8528f2126e77e4aca2a01e78053d7311f3d08b4e8979128024ab8474",
    "prs.json": "a702c830099f4fc4c1457a931229611bc0dbd79d925971a9b329543c94d4e63b",
    "open.json": "a2bf189b3562f2b152b67641271e134e426021a2c214779dd72069424d4ae901",
    "timelines.json": "984e8dd64b5c730ab06d8652fe3c473186297f98806cac482c7715dfd011e69b",
    "closed.json": "cb2edc1d346403fdec931bc318d4f7785050a32ac115e4a34dbf1892dd1a5a81",
    "delta.json": "5541edd4c1ad9edf56b41f5734bb350ccb7873242dab50d0cdeee8097ac79e4c",
    "reviewed-labels.json": "91c9afe6acc8ddaf6af8c2bfe09ca5a89931e9d47e4cf9031982e1bf90c4c210"
  }
}
```

The refresh repeats the original explicit-repository PR/open/closed queries with a limit of 1000. Results are below the limit. All 220 collected issues have closure/reopen timelines; every hasNextPage flag is false. The closure-event set includes reopened issues. The current closed set contains seven issues. Historical 14-closure collection is retained above. Current open and closed sets partition the same 220 issues. The 218 midnight issue IDs are preserved, not reconstructed from a later state. PR bodies were read before the external reviewed-labels map was written. Existing generation helpers were inspected but not run. Original hand-reviewed text and sheriff fixes remain.

### Closure and reopen events since midnight

| Issue | Event | UTC time | Current state |
|---|---|---|---|
| [#64](https://github.com/riscPrint/risc-v-workstation/issues/64) | ClosedEvent | 2026-11-13T04:57:44Z | open |
| [#64](https://github.com/riscPrint/risc-v-workstation/issues/64) | ReopenedEvent | 2026-11-13T07:19:36Z | open |
| [#70](https://github.com/riscPrint/risc-v-workstation/issues/70) | ClosedEvent | 2026-11-13T07:26:23Z | closed |
| [#85](https://github.com/riscPrint/risc-v-workstation/issues/85) | ClosedEvent | 2026-11-13T03:05:20Z | open |
| [#85](https://github.com/riscPrint/risc-v-workstation/issues/85) | ReopenedEvent | 2026-11-13T07:19:31Z | open |
| [#87](https://github.com/riscPrint/risc-v-workstation/issues/87) | ClosedEvent | 2026-11-13T01:56:34Z | open |
| [#87](https://github.com/riscPrint/risc-v-workstation/issues/87) | ReopenedEvent | 2026-11-13T07:19:34Z | open |
| [#106](https://github.com/riscPrint/risc-v-workstation/issues/106) | ClosedEvent | 2026-11-13T06:34:31Z | closed |
| [#118](https://github.com/riscPrint/risc-v-workstation/issues/118) | ClosedEvent | 2026-11-13T02:29:03Z | closed |
| [#127](https://github.com/riscPrint/risc-v-workstation/issues/127) | ClosedEvent | 2026-11-13T02:14:59Z | open |
| [#127](https://github.com/riscPrint/risc-v-workstation/issues/127) | ReopenedEvent | 2026-11-13T07:19:28Z | open |
| [#133](https://github.com/riscPrint/risc-v-workstation/issues/133) | ClosedEvent | 2026-11-13T02:14:59Z | open |
| [#133](https://github.com/riscPrint/risc-v-workstation/issues/133) | ReopenedEvent | 2026-11-13T07:19:25Z | open |
| [#153](https://github.com/riscPrint/risc-v-workstation/issues/153) | ClosedEvent | 2026-11-13T02:14:59Z | open |
| [#153](https://github.com/riscPrint/risc-v-workstation/issues/153) | ReopenedEvent | 2026-11-13T07:19:23Z | open |
| [#156](https://github.com/riscPrint/risc-v-workstation/issues/156) | ClosedEvent | 2026-11-13T02:15:00Z | open |
| [#156](https://github.com/riscPrint/risc-v-workstation/issues/156) | ReopenedEvent | 2026-11-13T07:19:20Z | open |
| [#161](https://github.com/riscPrint/risc-v-workstation/issues/161) | ClosedEvent | 2026-11-13T02:20:49Z | open |
| [#161](https://github.com/riscPrint/risc-v-workstation/issues/161) | ReopenedEvent | 2026-11-13T07:19:17Z | open |
| [#185](https://github.com/riscPrint/risc-v-workstation/issues/185) | ClosedEvent | 2026-11-13T02:51:50Z | closed |
| [#206](https://github.com/riscPrint/risc-v-workstation/issues/206) | ClosedEvent | 2026-11-13T04:20:35Z | closed |
| [#296](https://github.com/riscPrint/risc-v-workstation/issues/296) | ClosedEvent | 2026-11-13T03:10:42Z | open |
| [#296](https://github.com/riscPrint/risc-v-workstation/issues/296) | ReopenedEvent | 2026-11-13T07:19:15Z | open |
| [#349](https://github.com/riscPrint/risc-v-workstation/issues/349) | ClosedEvent | 2026-11-13T07:42:26Z | closed |
| [#379](https://github.com/riscPrint/risc-v-workstation/issues/379) | ClosedEvent | 2026-11-13T04:29:55Z | closed |

# Collection record

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

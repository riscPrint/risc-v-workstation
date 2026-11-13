# Collection record

Implementation review uses a separate collection at 2026-11-13T14:16:50.600662+00:00: 772 midnight merges, including 229 since 08:00 UTC. Its 209 additions to the earlier 563-record ledger are all included in the newer 775-record collection below. Keep the newer census and source records. The afternoon review sections add scope corrections for MCP, CSR, verdicts and native evidence. No native artifact was rerun for this document audit. Document checks and the fast unit set are reported in this PR.

Hourly refresh collected at 2026-11-13T14:22:26.916089+00:00: 212 additional merged PRs; 775 merged PRs in total; 213 current open issues; 7 currently closed issues closed since midnight. The 218-issue midnight census and separate new issues #722 and #723 are unchanged. Earlier collection text below is historical. The latest refresh notes take precedence for current state. No project tests, builds, simulations or proofs ran.

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

## Latest collection at 2026-11-13T14:22:26.916089+00:00

```json
{
  "collectedAt": "2026-11-13T14:22:26.916089+00:00",
  "mainHeadAtDocumentWrite": "298f3598542c72a9aadee7a0103c56b229bd22d7",
  "previousMergedPRs": 563,
  "additionalMergedPRs": 212,
  "mergedPRs": 775,
  "openIssues": 213,
  "currentlyClosedSinceMidnight": 7,
  "midnightIssues": 218,
  "newToday": [
    722,
    723
  ],
  "rawLocation": "/tmp/rvw-status-2026-11-13/refresh-1420",
  "timelinePaginationComplete": true,
  "rawSha256": {
    "milestone-map.json": "457344db2919d876262b3e887841fafac6109b8a6881bde467a0476689d0f3f7",
    "rvw-audit-open.json": "a40f284d0c49e52d319da00874dfbfa4faf5a76e61e447c247276686f8c35216",
    "timelines.json": "9409908038fec01a13d1876d9428434de8acf40ddc6de1948c51dc96cf6e4d69",
    "rvw-audit-delta.json": "cee209687e8bfacbd74195ddaa9feb44a6c6e5116ace5399d7fffddbe2705d87",
    "rvw-audit-closed.json": "3be110b0b55385d8859fc5c13245d868afbe7b5ceff913862945096c15e8fcbe",
    "reviewed-labels.json": "b7a3b924e995ca684fad13559c38a78c1628ebba58c7b973413a08485770e1ad",
    "rvw-audit-prs.json": "50d86e392f6d4403101ee17f763181833182a2e26786d7ca633e7e66dc9eb48f"
  }
}
```

Collection used explicit repository `riscPrint/risc-v-workstation`, merged PRs since midnight and open/closed issue queries with limit 1000. All results are below that limit. Delta membership uses the 563 PR headings in the previous source ledger, not PR-number order. The latest included merge is 2026-11-13T14:17:33Z. Later merges are outside this collection. All 220 issue timelines were fetched with first:100 and all pagination flags are false. Raw bodies, metadata, reviewed label map, milestone map and this document-only helper remain outside the repository.

The requested original helper directory was absent. The nearby `rvw-status-2026-11-13-agent` directory contained raw JSON and a diff, but no generation helpers. Those files were inspected as historical inputs. No old generator was run. The retained issue appendix supplied the exact census and PR #381 milestone map. The worktree was clean before fetch and detached checkout. A later clean external checkout moved HEAD again; the recorded head above identifies the document base.

### Current closure/reopen events since midnight

| Issue | Event | UTC time |
|---|---|---|
| [#64](https://github.com/riscPrint/risc-v-workstation/issues/64) | ClosedEvent | 2026-11-13T04:57:44Z |
| [#64](https://github.com/riscPrint/risc-v-workstation/issues/64) | ReopenedEvent | 2026-11-13T07:19:36Z |
| [#70](https://github.com/riscPrint/risc-v-workstation/issues/70) | ClosedEvent | 2026-11-13T07:26:23Z |
| [#85](https://github.com/riscPrint/risc-v-workstation/issues/85) | ClosedEvent | 2026-11-13T03:05:20Z |
| [#85](https://github.com/riscPrint/risc-v-workstation/issues/85) | ReopenedEvent | 2026-11-13T07:19:31Z |
| [#87](https://github.com/riscPrint/risc-v-workstation/issues/87) | ClosedEvent | 2026-11-13T01:56:34Z |
| [#87](https://github.com/riscPrint/risc-v-workstation/issues/87) | ReopenedEvent | 2026-11-13T07:19:34Z |
| [#106](https://github.com/riscPrint/risc-v-workstation/issues/106) | ClosedEvent | 2026-11-13T06:34:31Z |
| [#118](https://github.com/riscPrint/risc-v-workstation/issues/118) | ClosedEvent | 2026-11-13T02:29:03Z |
| [#127](https://github.com/riscPrint/risc-v-workstation/issues/127) | ClosedEvent | 2026-11-13T02:14:59Z |
| [#127](https://github.com/riscPrint/risc-v-workstation/issues/127) | ReopenedEvent | 2026-11-13T07:19:28Z |
| [#133](https://github.com/riscPrint/risc-v-workstation/issues/133) | ClosedEvent | 2026-11-13T02:14:59Z |
| [#133](https://github.com/riscPrint/risc-v-workstation/issues/133) | ReopenedEvent | 2026-11-13T07:19:25Z |
| [#153](https://github.com/riscPrint/risc-v-workstation/issues/153) | ClosedEvent | 2026-11-13T02:14:59Z |
| [#153](https://github.com/riscPrint/risc-v-workstation/issues/153) | ReopenedEvent | 2026-11-13T07:19:23Z |
| [#156](https://github.com/riscPrint/risc-v-workstation/issues/156) | ClosedEvent | 2026-11-13T02:15:00Z |
| [#156](https://github.com/riscPrint/risc-v-workstation/issues/156) | ReopenedEvent | 2026-11-13T07:19:20Z |
| [#161](https://github.com/riscPrint/risc-v-workstation/issues/161) | ClosedEvent | 2026-11-13T02:20:49Z |
| [#161](https://github.com/riscPrint/risc-v-workstation/issues/161) | ReopenedEvent | 2026-11-13T07:19:17Z |
| [#185](https://github.com/riscPrint/risc-v-workstation/issues/185) | ClosedEvent | 2026-11-13T02:51:50Z |
| [#206](https://github.com/riscPrint/risc-v-workstation/issues/206) | ClosedEvent | 2026-11-13T04:20:35Z |
| [#296](https://github.com/riscPrint/risc-v-workstation/issues/296) | ClosedEvent | 2026-11-13T03:10:42Z |
| [#296](https://github.com/riscPrint/risc-v-workstation/issues/296) | ReopenedEvent | 2026-11-13T07:19:15Z |
| [#349](https://github.com/riscPrint/risc-v-workstation/issues/349) | ClosedEvent | 2026-11-13T07:42:26Z |
| [#379](https://github.com/riscPrint/risc-v-workstation/issues/379) | ClosedEvent | 2026-11-13T04:29:55Z |

The currently closed set is [#70](https://github.com/riscPrint/risc-v-workstation/issues/70), [#106](https://github.com/riscPrint/risc-v-workstation/issues/106), [#118](https://github.com/riscPrint/risc-v-workstation/issues/118), [#185](https://github.com/riscPrint/risc-v-workstation/issues/185), [#206](https://github.com/riscPrint/risc-v-workstation/issues/206), [#349](https://github.com/riscPrint/risc-v-workstation/issues/349), [#379](https://github.com/riscPrint/risc-v-workstation/issues/379). Closure events do not establish acceptance. No issue was closed or commented on. No project code, test, build, simulation, proof or MCP discovery ran. ROADMAP.md and TODO.md were not edited. No schedule was created.

## Implementation review collection

```json
{
  "collectedAt": "2026-11-13T14:16:50.600662+00:00",
  "mainHead": "86bc98d4a6e30f86e36f4b0bb8570f4879e8aa2c",
  "mergeWindowStart": "2026-11-13T08:00:00Z",
  "mergedPRs": 772,
  "since0800PRs": 229,
  "openIssues": 213,
  "currentlyClosedSinceMidnight": 7,
  "midnightIssues": 218,
  "newToday": [
    722,
    723
  ],
  "timelinePages": 258,
  "timelinePaginationComplete": true,
  "additionalLedgerPRs": 209,
  "previousLedgerPRs": 563,
  "rawLocation": "/tmp/rvw-status-2026-11-13-agent",
  "rawSha256": {
    "381.diff": "a52f467ec6755c3c9e9373c6b26a0ef85a4782cb0f380eb0398a80737849242d",
    "381.json": "b472041f8aa70255b516c358ebfc18a095f382d22c5cca8ff13bfda04924b452",
    "collection.json": "e7810c7df06e7f3981d924a381f9eaa9cd8a668650daf8dbec7ad5802cb69e66",
    "issues.json": "e6cc7d65df265bec5aa13ebed3f6bd54810e315db6f3beb7f01179b7620cd65e",
    "midnight-prs.json": "39dc3b6724b077726b8d8b8062e6cbedb938ab0973ada8de91d5ad832fc66566",
    "novel-prs.json": "80ef211fe6f3f04e08c239f423820c7caf2a37c257ef425e593c78d153c432b7",
    "prs.json": "d5161d4072ce10bc7b26348f1c5975f131087768b5dd3fbf155387e001e240a1",
    "reviewed-labels.json": "923f817ab48c9bb3048f79c799fb234a2c32b8e950b4609e0dabea9c69707bde",
    "timelines.json": "93bd92fdbeddd7158c39aa50fce91b7894e350bb3f55c1be457b20c76c737e12"
  }
}
```

The explicit-repository query used `gh pr list --state merged --search "merged:>=2026-11-13T08:00:00Z" --limit 1000 --json number,title,body,mergedAt,files,url`. A separate midnight query supplied the total. Neither reached the limit. The all-state issue query collected 258 issues, including older closed issues. Closed/reopened GraphQL events were collected for each issue. Every pagination flag is false. Reversing events after midnight reproduces the same 218-issue census. The 213 open issues and seven currently closed issues from today partition that census plus issues #722 and #723.

The newer collection has 775 unique source records. All 772 records from this review collection are present. Of 229 merges since 08:00 UTC, 20 were already in the earlier ledger. This review read the other 209 source bodies. PR #381 acceptance and milestone sources remain unchanged. No issue was edited, closed or commented on. Root ROADMAP.md and TODO.md were not edited. The union rebase duplicated source records and table rows; they were reconciled against the newer main collection rather than retained twice.

# Bounded release scan

Use the development Python environment:

```sh
rvw/.venv/bin/python scripts/scan-release.py --since 2026-11-13
```

The command reuses the release-hygiene scanner. It checks tracked working-tree
bytes, symlink targets and locally reachable commit/tag messages. It reports
finding locations and identity counts. It does not print credential values.
It lists personal-path findings in files touched since the requested date.
No Git history is rewritten. Required upstream attribution is preserved.

A clean result is a bounded scan. It is not proof that no secrets exist.
Remote caches, unreachable objects, archive expansion and arbitrary encodings
are outside scope. See [the contract](contracts/install.md).

Identity publication approval remains an owner decision under #79. This task
does not infer permission to publish names or email addresses. #39 remains the
separate remote cache/history task. No publication or cache deletion ran.

## Recorded scan on 2026-11-13

The local scan reviewed 1,497 file names touched since UTC midnight and all
tracked working-tree bytes. It found zero tracked credential findings, zero
tracked personal-path findings and zero commit/tag message findings. No path
replacement was needed in the current tree. Untracked `rvw/out/` was excluded.

Local refs exposed 1,445 commits and one tag. Identity counts were two authors,
two committers and one tagger. These counts are observations, not publication
approval. They can change when refs are fetched. The complete report stays
outside the repository because it is a local audit result.

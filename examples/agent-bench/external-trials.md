# Scripted external fixture trials

Run all fifteen public tasks through the existing bounded external MCP runner:

```sh
nice -n 15 rvw/.venv/bin/python examples/agent-bench/run-scripted-trials.py --out /path/outside/repository/new-trial
```

Measured on 2026-11-13. Each client had 30 seconds and 32 tool calls.
The client used the runner's loopback SSE MCP transport. No LLM was used.
All clients exited zero. Full transcripts remain outside the repository.
These scores measure the fixture harness. Native tools, source repair and
native independent checks were NOT RUN in these trials. The evidence solver
uses a different tool surface and is not supported by the fixture trial runner.
Client seconds exclude server startup and shutdown. Root-cause time uses the
session clock and can start before the client clock.

| Task | Complete | Correct fix | False fix | Inconclusive preserved | Calls | Client seconds |
|---|---|---|---|---|---:|---:|
| task-01 | True | 1 | 0 | 0 | 4 | 2.833 |
| task-02 | True | 1 | 0 | 0 | 4 | 2.445 |
| task-03 | True | 1 | 0 | 0 | 5 | 3.197 |
| task-04 | True | 1 | 0 | 0 | 5 | 3.266 |
| task-05 | True | 1 | 0 | 0 | 4 | 2.655 |
| task-06 | True | 1 | 0 | 0 | 5 | 2.882 |
| task-07 | True | 1 | 0 | 0 | 5 | 2.925 |
| task-08 | True | 1 | 0 | 0 | 4 | 2.563 |
| task-09 | True | 1 | 0 | 0 | 5 | 3.045 |
| task-10 | True | 1 | 0 | 0 | 5 | 2.677 |
| misleading-rtl_sha256 | True | 0 | 0 | 1 | 3 | 2.772 |
| misleading-elf_sha256 | True | 0 | 0 | 1 | 3 | 2.770 |
| misleading-unsupported_fields | True | 0 | 0 | 1 | 3 | 2.426 |
| misleading-coverage | True | 0 | 0 | 1 | 3 | 3.935 |
| misleading-completion | True | 0 | 0 | 1 | 3 | 3.179 |

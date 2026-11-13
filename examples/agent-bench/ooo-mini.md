# OoO Mini seeded task inputs

The task pack pins the example to workstation commit
`4a8757808d344f6db4660ce2e08ae88465f6e27a`. It uses the default configuration.
Changes to the live example do not change this source pin. Use a private clone
at that commit as `--source`. The adapter accepts the nested example path.
Build programs with the example's `rvw/build-isa.py`, then run:

```sh
nice -n 15 rvw/.venv/bin/rvw agent-bench native-qualify \
  --pack examples/agent-bench/ooo-mini.json --source /path/to/private/pinned/clone \
  --out /path/outside/repository/new-ooo-run
```

Native jobs use `vex-agentbench` and `sbt-agentbench`. Run one campaign at a
time. Set `JAVA_TOOL_OPTIONS=-XX:ActiveProcessorCount=2` to bound JVM processors.
The pack limits native make jobs to two. All source changes stay in the
qualification copy. Source round trips are tested against Git objects at the
pin. They do not establish compilation, activation or test detection.

| Task | Mutation | Named workload | Native detection |
|---|---|---|---|
| wakeup-race | Drop integer wakeup when long-latency completion is simultaneous | mul | Not measured |
| freelist-leak | Omit retired-tag release | add | Not measured |
| recovery-map | Restore architectural numbers instead of committed tags | beq | Not measured |
| store-age | Reverse store-age forwarding test | lw | Not measured |
| flush-valid | Retain valid entries on recovery | beq | Not measured |
| operand-ready | Issue with only one ready operand | add | Not measured |
| rename-source | Read rs1's mapping for rs2 | sub | Not measured |
| mul-wakeup | Drop long-latency result wakeup | mul | Not measured |
| mul-flush | Keep long-latency execution on recovery | div | Not measured |
| lsq-order | Reverse unresolved-store load interlock | lw | Not measured |

Each task uses the short `agent-control` program. Copy it from the benchmark
builder output into the private ISA program directory before qualification. Named workloads are proposed detectors.
They are not qualified detectors. Some mutations can cause a hang without an
architectural mismatch. Such a result cannot earn the first-mismatch claim.
Generated monitor detection and additional generated or random workloads need
native observations. No check activation is inferred from a source rule name.

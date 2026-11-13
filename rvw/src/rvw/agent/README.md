# Agent playbook

`rvw agent guide` prints the workflows an agent follows with the workstation.
Each workflow is an ordered list of `rvw` commands and their MCP tools, with
decision points that name the next step, another workflow, `done` or `stop`.

```sh
rvw agent guide                       # one line per step
rvw agent guide --workflow test-fails --json
rvw agent guide --markdown --write docs/AGENT_SETUP.md
```

MCP: tool `agent_guide` (argument `workflow`), resources `rvw://agent/guide` and
`rvw://agent/guide/<workflow>`. The workflows are `bring-up`, `test-fails`,
`add-coverage`, `prove-property` and `performance-question`.

The data is `playbook.json` (`rvw.agent-guide/1`). `docs/AGENT_SETUP.md` holds the
generated Markdown between the guide markers. Edit the JSON, then run the
`--write` command above. `rvw/tests/test_agent_guide.py` checks that every step's
command parses with the real CLI, that every MCP tool exists, that every decision
target exists and that the document block equals the generated text.

## Decisions and limits

- One data file feeds the CLI, MCP and the setup document, so they cannot drift.
- Angle-bracket values are placeholders. The guide does not fill them in.
- A step with `manual: true` is work the agent does in the core repository.
- The guide names tools and decisions. It is not evidence: every verdict still
  comes from the named command's own result and exit code.

The bring-up workflow follows [the integration guide](../../../../docs/INTEGRATION_GUIDE.md).
The failure workflow checks artifact identities before cause analysis. It requires
a reproduced failure, repair runs and a committed gate result. Missing dynamic
evidence leaves the cause unknown.

## End-to-end bring-up check

```sh
rvw agent bringup-check --out /tmp/bringup      # MCP: agent_bringup_check (long job)
```

The check copies a tiny multi-cycle RV32I Spinal core (`bringup/core`, one memory
port, RVFI outputs, four self-checking programs) into a new Git repository and
seeds a `sub` defect in the copy. It then walks the guide:

- `bring-up`: `rvw doctor` before any project file, `rvw init` (plan, then write,
  with `--wire-build`, `--linker-script` and `--db-top`), doctor again, the manual
  mapping step (it copies `bringup/CoreAdapter.scala`, builds the programs, reviews
  `rvw/cosim.json` and commits), the doctor smoke run, `regress list`, the quick tier,
  `cosim check`, the committed gate and `query build`;
- `test-fails`: the failing `arith` run, `bundle`, `cosim check` (first difference),
  `query drivers`, the one-line fix and the gate on the fixed revision.

`report.json` (`rvw.agent-bringup/1`) lists each step with its command, exit code,
the outcome the guide expects, what happened (`works` or `rough_edge`) and its log.
Exit 0 means every step worked. The check needs sbt, Verilator, the RISC-V compiler
and the Spike shim; the tiny core runs under the `tinycore` lock. It is a setup test,
not core evidence.

## MCP workflow calls

Every MCP tool belongs to a profile and an optional tool set in a guide workflow. The core profile includes each named bring-up call and stays at most 40 tools. Install tools through the CLI. Map the core adapter in the core project. Load another profile when a decision enters another workflow.

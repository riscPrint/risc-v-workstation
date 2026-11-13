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

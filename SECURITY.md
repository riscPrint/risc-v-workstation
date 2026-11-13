# Security

## Report a problem

Use [GitHub private vulnerability reporting](https://github.com/riscPrint/risc-v-workstation/security/advisories/new).
Open the repository's Security tab, select Advisories, then Report a vulnerability.
If the private report form is unavailable, ask the repository owner to enable
private reporting. Do not put vulnerability details in a public issue.
Maintainers can use a private security advisory to assess and coordinate a fix.
No response time or supported-version policy is set here.

Include the affected revision and package versions, tool and core config,
reproduction commands, expected and actual behavior, and the possible effect.
Remove credentials and private design data from reports.

## C8 scope

[C8](docs/contracts/c8-capture.md)
protects against honest mistakes in normal work. Results must not grant a pass,
match, accept or exclusion without enough evidence. Normal mistakes include
stale files, wrong options, missing tools, interrupted builds, resume,
cancellation and concurrent runs with separate outputs.
Unknown or incomplete evidence cannot earn passing-result reuse.
Gate accept requires committed base and candidate revisions.

C8 assumes inputs, tools and caches stay stable during a command.
Mid-run edits, edit-and-revert races, tool swaps, cache tampering and hostile
inputs are outside this threat model. This scope does not promise safe execution
of untrusted projects, adapters, build scripts or artifacts.
You can still report a concern through the private route above.

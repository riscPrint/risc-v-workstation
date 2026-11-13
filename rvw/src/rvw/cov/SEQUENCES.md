# Bounded retirement sequences

`rvw cov actions --goal 'sequence:["RAW",2]' --registers 5,6,7 --work-dir candidate --json`
emits a bounded action graph and assembly source. `cov_actions` has the same API.
The distance is the number of retirement steps between the two actions.
Supported distances default to 1, 2 and 4. `--distances` declares another bounded
set. Each distance must be between 1 and 256.

Supported goals are RAW, WAW, WAR, branch-after-load, all load/store pairs, and
all branch/jump pairs from the existing sequence observer. Filler instructions
write x0. Branches and jumps go to the next payload instruction. Memory actions
require `--memory`. This declares support for writable aligned program data.
The source allocates eight bytes of scratch data. It does not select a device
address. The runtime must support that data section and M-mode execution.

The candidate records preconditions, exact payload words, an ordered action
graph, source hash and payload symbols. Generation earns no measured hit.
The existing retirement observer must measure the pair after a complete
qualified run. A retirement pair does not measure a pipeline stall or hazard.
These bounded recipes do not implement the PSS language.

To include sequence goals in `cov campaign`, add `"sequences":{"distances":[1,2,4]}`
to its settings. Optional `kinds` restricts the declared kinds. Add `"memory":true`
only when the runtime supports the program data section. The full denominator
includes all declared pairs, including unsupported memory goals. The verifier
checks every payload word in the ELF. It measures pairs through the existing
sequence observer with the same payload sampling policy and full Spike check.

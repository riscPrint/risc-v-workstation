# VexRiscv RTL event coverage

Generate plain VexTop RTL and its matching HGLDD as described in the parent
README. Keep the PDG naming phase off for these inputs. Then run from the
workstation root:

```sh
scripts/with-lock.sh vex nice -n 10 rvw/.venv/bin/python \
  examples/vexriscv/rvw/coverage/sample.py \
  /path/to/rtl/VexTop.v /path/to/VexTop.dd /tmp/fresh-vex-coverage
```

Use Verilator 5.052 or later. The output directory must be new. The example
builds with line, toggle and FSM coverage. It samples the fetch interface
before each rising edge for 64 cycles. It returns NOP instructions with a
one-cycle response delay and adds request backpressure every fourth cycle.
It collects accepted requests, stalled requests and responses as speculative
RTL event bins. A bounded request-to-response sequence counts activations
and completions separately. Reset clears sequence history.

`plan.json` records the RTL content hash, exact top-level signal paths and
source links from HGLDD. Missing Scala links stay null. `samples.jsonl` is the
reusable sampling contract. `events.json` reports its bins and sequences.
`coverage.dat` contains native Verilator points. `summary.json` compares
Scala-mapped point counts with and without HGLDD. `build.log` keeps tool output.
This fetch-interface exercise is not an ELF execution or an ISA check.
Its denominator contains only the declared interface events. It does not
measure all internal events or prove unreachable bins.

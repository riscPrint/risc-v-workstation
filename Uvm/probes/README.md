# Measured engine probes

Run these small probes with the engine that will run the project:

```sh
nice -n 10 rvw/.venv/bin/python Uvm/probes/run.py --out /tmp/uvm-probes-new
```

The output records engine version, exact compile command and build/run logs.
A timeout is inconclusive. A compile refusal is not a conformance pass.
Ignored feature warnings prevent a checked result, even if a test exits zero.
Warnings remain in the log. Nonfatal warnings let runtime checks proceed.

Native result on 2026-11-13, Verilator 5.049 devel
`v5.048-26-g25d4827bd (mod)`:

- The 4-bit `randc` probe checked one complete 16-value cycle. It passed.
- The `(0 => 1 => 2)` transition cover bin produced `COVERIGN` warnings.
  It failed the 100% coverage check after sampling 0, 1 and 2. This is a
  measured transition-bin gap in that installed engine.

These probes do not establish every cyclic random or coverage construct.
A failure on this version does not establish a gap in all Verilator versions.
The UVM suite's basic covergroup result applies only to its own engine and
profile. The Python path below avoids reliance on SV transition coverage.

## Solver and functional coverage path

Install `z3-solver==4.15.4.0` in the rvw Python environment. Install pyuvm 4
and cocotb 2. `rvw.uvm.constraints.ConstraintSolver` accepts bounded integer
fields and a callable that builds Z3 constraints. It uses seeded preferences.
It does not claim uniform sampling. Unsatisfiable constraints and solver
unknown results are errors. No unconstrained transaction is returned.

`FunctionalCoverage` takes explicit finite domains. Sample only observed
transactions after independent checks pass. All declared bins, including
zero-count bins, remain in the export. For transition coverage, track the
observed history in the project monitor and sample the declared history tuple.
Generated stimulus alone is not coverage evidence.

```sh
nice -n 10 rvw/.venv/bin/rvw regress cocotb Uvm/pyuvm/constraint-bench.json \
 --out /tmp/python-constraints-new --timeout 110 --json
rvw cov exchange /tmp/python-constraints-new/functional.json \
 --destination /tmp/python-constraints.ucis --format ucis
rvw cov exchange /tmp/python-constraints.ucis \
 --destination /tmp/python-constraints.json --format import-ucis
```

Native fixture result on the same engine: 1 passed, 0 skipped, 72 RTL checks,
36 transactions, 108 simulated ns. All eight declared write/read-address bins
were hit. The solver uses seed 3. The cocotb simulator seed is recorded by C3.
UCIS export and import retained all eight counts. This is a memory fixture,
not CPU qualification, complete SV constraint support or C4 acceptance.

# Small hardware leakage reference

`slice.v` is a two-instruction RV32 slice. It retires a taken BEQ and an ADD.
It does not execute general programs. It models a skipped load as a transient
cache update. This is a deliberate leak seed, not a discovered CPU defect.
`program.S` gives Spike the same architectural path.

Four separate seeds expose transient cache state, ADD latency, a disabled trace
output, or a test output. Seed zero is the negative control. Registers x1 and x2
hold secret and public operands. Register x4 selects the seed in the experiment.
Each run starts with public reset. No reset secret or retained initial state is
allowed. Trace and test seeds are small digital controls for #195 and #198;
they do not verify a production trace unit, scan chain or authentication system.
No Smepmp policy is implemented (#138).

`adapter.py CASE OUT` builds and runs native Icarus RTL. It reads no Spike
results. It exports retirement effects, retirement cycles and final observations.
The parent checks retirement effects against Spike before comparing leakage.
A failed build, missing observation or architectural difference is inconclusive.
The adapter records source and executable hashes. The native tests build the ELF
and run the CLI with this captured adapter tree.

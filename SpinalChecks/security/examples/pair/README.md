# Two-copy security examples

These self-contained fixtures use `rvw formal security pair`. Run one with:

```sh
rvw formal security pair \
  --manifest SpinalChecks/security/examples/pair/speculation-1-safe.json \
  --out /tmp/speculation-safe --timeout 60
```

The safe fixtures must prove. The leaky fixtures must fail with a trace. Use a
new output directory for each run. The manifests declare every observed port,
secret, public reset and omitted channel. The tool captures the source and
manifest with each result.

## Squashed-load observation

`speculation.v` models a small fixed-program fetch/resolve pipeline. Its ROM has
`beq x0,x0,+8`, a younger wrong-path `lw x1,0(x10)`, and `addi x0,x0,0`.
Branch resolution squashes the younger instruction before retirement. The
architectural channel contains retirement validity, instruction PC and word.
The cache channel contains request activity and an operand-derived address.

The safe version blocks the younger cache request when the branch resolves.
The leaky version permits that request. Its two executions can have equal
architectural observations and different cache addresses. Seeds 1 and 7 select
two fixed address mappings. Both use the same small program. Use manifests
`speculation-{1,7}-{safe,leaky}.json` to check them.

This is a bounded-size pipeline model with an unbounded native contract proof.
It is not a general RISC-V core. It does not execute arbitrary programs, verify
ISA semantics, implement memory, or qualify BOOM/VexRiscv security. The result
applies to these declared digital channels.

## Declared Zkt unit timing

`zkt.v` implements the SHA-256 small-sigma-zero Boolean expression. The unit
accepts a public start input and exposes busy and completion. The fixed unit
has two busy clocks after acceptance. The mutant can add one clock from an
operand bit. Manifests `zkt-fixed.json` and `zkt-leaky.json` declare the operand
secret and compare busy/completion without an architectural guard.

The timing check does not compare the data result. Functional datapath checks
are separate. The operation label is a project declaration. It does not prove
that a core decoder selects this unit for a Zkt instruction. Inputs can change
at every clock. The fixed timing result therefore does not require stable
secret operands. Physical timing and analog leakage remain outside the model.

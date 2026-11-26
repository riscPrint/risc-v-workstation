# Two-Week Vertical Spike: Agent-Native RTL to Lean 4 (`FV` v2)

## 1. Objective & Thesis

Instead of expanding black-box commercial-clone SAT/BMC portfolios, `risc-v-workstation` tests whether an **AI-driven deductive formal pipeline** — lowering elaborated Verilog/RTLIL from SpinalHDL (`spinal-boom` `giga` and `small` presets) into Lean 4 `BitVec` state-transition systems anchored on Sail RISC-V — can:

1. Verify unbounded invariants on OoO control structures where bounded model checking stops at depth bounds.
2. Find subtle RTL bugs faster or with cleaner compositional specs than standalone SBY harnesses.
3. Let an agent repair Lean 4 proofs cheaply across real Scala/SpinalHDL refactors.

This document is the 14-day spike plan before committing platform-wide engineering effort. Nothing in this spike alters `spinal-boom` RTL permanently, and proposed Lean tooling stays isolated until the Day-14 Go/No-Go gate passes.

## 2. Target Architecture

```text
SpinalHDL (BOOM small / giga)
   │  (existing Verilog emission)
   ▼
Yosys (proc; opt -nodffe; write_json)
   │  (flat bit-level RTLIL + module ports + cell types)
   ▼
lean_import.py  ──(hierarchy & Scala spans via `rvw query` / SpinalDB)──▶ Lean 4 `State` + `step` FSM (`BitVec n`)
   │                                                                           │
   ├── Differential fuzz (>=1,000 cycles vs Verilator `#eval` parity) ◄───────┤
   └── Compositional proofs (`bv_decide` CaDiCaL LRAT + `omega` + induction) ──► Anchored to `sail-riscv` Lean 4 RVFI slice
```

### Why Verilog/Yosys JSON -> Lean 4 (not SpinalHDL AST -> Lean 4)

- **Single source of hardware truth:** SpinalHDL elaboration (implicit `When` priority trees, `Mux1H`, width extension, `Reg` reset insertion, dedup, `FixedPipeline` delays) already lowers deterministically to Verilog and Verilator. Translating at `yosys` `proc; opt -nodffe; write_json` avoids re-implementing Scala/SpinalHDL elaboration semantics in Lean 4 while guaranteeing bit-exact parity with what Verilator simulates.
- **Reuses existing workstation infrastructure:** `rvw` already parses Yosys JSON in `rvw/src/rvw/formal/security/ift.py`, inspects elaborated hierarchy/source locations in `SpinalDB` (`rvw/src/rvw/query/`), and pins OSS CAD Suite (`yosys 0.64+174`, `sby`, `verilator`, `bitwuzla`, `z3`, `cvc5`).
- **Proof automation fit:** Lean 4's kernel-checked `bv_decide` (backed by CaDiCaL LRAT proof checking) solves combinational/one-step `BitVec` obligations quickly, while Lean `omega` + structural induction handle unbounded `Nat`/index/population-count invariants across arbitrary step counts.

### Structural & Scaling Strategy

- **Compositional module boundaries via `SpinalDB`:** Large modules are not flattened into one monolithic Lean term. Use `SpinalDB` module hierarchies, port widths, clock/reset metadata, and Scala source locations to assign assume-guarantee contracts at sub-module interfaces (`RenameFreeList`, `RenameMapTable`, `IssueSlot`, `BoomMSHR`).
- **Memory & large-array fallback rule:** If any target instantiates multi-kilobit `$mem_v2` arrays (e.g., physical register files or cache data/tag RAMs), Yosys `write_json` must **not** bit-blast them into flip-flops; abstract SRAM arrays behind uninterpreted `Array (BitVec addrW) (BitVec dataW)` read/write axioms with explicit single-port/multi-port semantics. (All four spike targets below are primarily register/snapshot/FSM structures.)

## 3. Baseline Local Environment (Day 0 Setup)

Already verified present locally in OSS CAD Suite:
- `yosys` (`0.64+174` — supports `proc`, `opt -nodffe`, `write_json`, `$dff`/`$sdff`)
- `sby`, `verilator`, `bitwuzla`, `z3`, `cvc5`, `yosys-smtbmc`, `yosys-abc`, `btormc`, `btorsim`, `yices-smt2`

Needs installation on Day 0:
1. `elan` + pinned Lean 4 toolchain (`lean`, `lake`, bundled `bv_decide` / `cadical` LRAT checker) — create a self-contained workspace scratch Lake project (`lean-spike/` outside `rvw` core until validated).
2. `sail-riscv` Lean 4 model export (pinned commit/release capable of running via `lake build` and exporting RV64GC decode/execute pure Lean definitions).

## 4. Two-Week Execution Schedule

### Phase 0 (Days 1–3): Translator Prototype & Differential Equivalence

**First RTL target:** `RenameFreeList` (`boom/exu/rename/rename-freelist.scala`).
- **Why this module:** Pure single-clock state machine with high verification value (`free_list`, `spec_alloc_list`, `br_alloc_lists` indexed up to `maxBrCount`, `r_valid`/`r_sel` per `allocWidth` lane, `alloc_masks` `scanRight`, `io.brupdate.b2.mispredict`, `io.rollback`, plus the upstream safety assertion `!(io.debug_freelist & dealloc_mask).orR`). Fits bitvector state directly with zero external memory blackboxes.

**Day-by-day tasks:**
- **Day 1 — Elaborate & inspect Yosys JSON IR:** Elaborate standalone `RenameFreeList` (both `small` parameters first, then `giga` parameters `numPregs=128`, `allocWidth=4`) with Verilog emission and run `yosys -p "read_verilog ...; hierarchy -top RenameFreeList; proc; flatten; opt -nodffe; write_json freelist.json"`. Catalog every emitted Yosys cell type (`$_NOT_`, `$_AND_`, `$_OR_`, `$_XOR_`, `$_MUX_`, `$dff`, `$sdff`, `$eq`, `$add`, `$sub`, `$mux`, `$pmux`).
- **Day 2 — Implement `lean_import.py`:** Build a clean Python translator taking Yosys JSON (`netnames`, `ports`, `cells`, constant bits `0`/`1`/`x`) -> topological combinational wire equations + next-state update function over `BitVec` in Lean 4:
  - Generate `structure Inputs`, `structure State`, `structure Outputs`, `def resetState : State`, and `def step (s : State) (i : Inputs) : State × Outputs`.
  - Fail explicitly on unsupported latches, multi-clock cells, async reset ambiguities (if outside synchronous subset), or `x`/`z` undriven bits — matching the honesty rules used elsewhere in `rvw`.
- **Day 3 — Bit-exact differential fuzzing vs Verilator:**
  - Add a tiny Lean `#eval` runner reading hex input vectors and printing state + output vectors per cycle.
  - Drive **>= 1,000 randomized + adversarial cycles** (multi-lane allocations `io.reqs`, simultaneous commits `io.dealloc`, `io.despec`, branch snapshots `io.ren_br_tags`, `io.brupdate.b2.mispredict`, full `io.rollback`) into both compiled Verilator C++ harness and Lean `step`.
  - **Phase 0 exit check:** **0 bit mismatches** across all 1,000+ cycles (`free_list`, `spec_alloc_list`, `io.alloc_pregs`, `io.debug_freelist`). Stop and fix the translator before writing proofs if even 1 bit differs.

### Phase 1 (Days 4–8): Unbounded Proofs, Bug Injection & Refactor Repair

**Day 4 — Unbounded `RenameFreeList` invariants:**
Using `bv_decide` for one-step `step` transitions and structural induction over cycle count `k : Nat`, prove (first on `small`-width parameters, then measuring `giga` `128`-bit width scaling):
1. **No double-free / live-free disjointness:** `(free_list &&& spec_alloc_list) == 0` under reset + transition preservation given valid commit/despec assumptions.
2. **Same-cycle multi-lane uniqueness:** If `allocWidth >= 2` and multiple lanes allocate (`sel_fire`), no two lanes emit the same physical register index.
3. **Physical register conservation:** Define the architectural/allocated mask induced by `io.dealloc` + `spec_alloc_list` + `free_list` + pending `io.alloc_pregs`; prove `popCount` total remains constant across alloc, commit, branch mispredict, and rollback.

**Days 5–6 — `RenameMapTable` (`boom/exu/rename/rename-maptable.scala`):**
Translate `RenameMapTable` (`map_table`, `com_map_table`, `br_snapshots`, combinational same-cycle `bypass` forwarding across `plWidth` lanes) and prove:
1. **Intra-group bypass soundness:** For lane `i`, if `bypass` is enabled and an older lane `k < i` remaps `ldst == lrs1`, output `prs1` equals `remap_reqs(k).pdst` from the latest matching lane; otherwise `map_table[lrs1]`.
2. **Rollback & branch snapshot consistency:** On `io.rollback` (with `!mispredict`), next `map_table` equals `com_map_table`; on valid branch snapshot + later mispredict with zero intervening snapshot overwrite on that tag, `map_table` recovers the captured `remap_table` snapshot.
3. **Zero duplicate destination aliasing:** Under distinct allocated `pdst` assumptions matching `RenameFreeList`, the upstream duplicate assertion holds inductively.

**Day 7 — 3-Bug Injection Benchmark:**
Seed 3 realistic RTL mutations into standalone BOOM copies (kept strictly in scratch space, never committed) and measure wall time + counterexample clarity:
1. Swap priority of `io.brupdate.b2.mispredict` vs `io.rollback` in `RenameMapTable` (`rename-maptable.scala`).
2. Omit `~com_deallocs` in `isImm` branch snapshot update in `RenameFreeList` (`rename-freelist.scala`).
3. Corrupt `scanRight` lane mask accumulation order in `RenameFreeList` (double-allocating `p` across lanes `0` and `1`).
Record whether Lean `bv_decide` fails cleanly with a minimal reproducible bitvector counterexample on all 3 bugs and compare turnaround time against `rvw formal bmc`.

**Day 8 — 3-Refactor Proof-Repair Benchmark:**
Apply 3 realistic Scala refactors (e.g., parameterizing width/helper extraction, bundling control signals so Yosys renames intermediate wires, increasing `allocWidth` / lane reordering) and measure how cleanly an AI coding agent repairs the broken Lean proof scripts (target: >= 2/3 repaired within <= 5 agent turns without weakening assumptions).

### Phase 2 (Days 9–14): Deeper Control/Memory Composition & Sail Anchor

**Days 9–10 — `IssueSlot` Assume-Guarantee Contract (`boom/exu/issue-units/issue-slot.scala`):**
Lower single `IssueSlot` (`slot_valid`, `slot_uop`, `killed = IsKilledByBranch(...)`, wakeup matching `prs1/2/3_wakeups`, `child_rebusys`, `iss_ready`/`agen_ready`/`dgen_ready`) and prove:
1. **Kill & flush annihilation:** Whenever `io.kill || killed` is true, next `slot_valid = false`.
2. **Issue request readiness & single-issue safety:** `io.request` implies `slot_valid && !slot_uop.iw_issued`, and none of the active ready conditions hold when an un-bypassed busy operand matches (including `ppred_busy` / speculative child rebusy predicate checks).
3. Record exact solver runtime for wide `MicroOp` BitVec packing; test pruning/projecting unused `MicroOp` debug fields (`inst`, `pc` debug slices) if `bv_decide` saturates on full `MicroOp` bitwidth.

**Days 11–12 — `BoomMSHR` FSM Reachability & Mutual Exclusion (`boom/lsu/mshrs.scala`):**
Extract the 18-state `state` control skeleton (`s_invalid..s_prefetch`), `req_pri_rdy`, `req_sec_rdy`, and `req_needs_wb` from `BoomMSHR` (abstracting SRAM line buffers as interfaces) and draft/prove:
1. `state` stays within valid enum encodings `0..17` across all transitions.
2. `req_pri_rdy` holds only in `s_invalid` (or permitted prefetch replacement states) and never simultaneously accepts conflicting primary/secondary tag mismatches.

**Day 13 — `sail-riscv` Lean 4 Retirement Anchor:**
Connect one compositional pipeline contract cleanly to `sail-riscv` Lean 4 definitions on a single RV64GC ALU instruction retirement slice: show how a proved `RenameMapTable` + `IssueSlot` state obligation maps to decoded Sail register indices (`rs1`, `rs2`, `rd`) and an RVFI retirement obligation (`rd_wdata`), documenting every abstraction assumption made at fetch/execute/LSU boundaries.

**Day 14 — Compile Metrics & Decision Report:**
Measure translation size (Lean LOC per Verilog LOC), `bv_decide` SAT wall times across widths (`small` vs `giga` `numPregs=128`), bug/repair benchmark scores, and publish Go/No-Go decision + Phase 3 design note (how Lean export/check tooling would slot into `rvw` CLI/MCP if Go).

## 5. Quantitative Go / No-Go Criteria

| Metric | Pass (Go) Threshold | Stop / Pivot (No-Go) Signal |
|---|---|---|
| Translator bit-exactness | **0 / >=1,000 cycles** Verilator vs Lean `#eval` mismatch across all 4 targets | Structural Verilog/Yosys construct cannot match Verilator semantics cleanly |
| `bv_decide` proof latency | **< 30 s per lemma**, **< 2 min per module** on `small`; tractable (< 5 min) or cleanly parameterized on `giga` 128-preg widths | Super-linear SAT blowup on unabstracted `MicroOp` or 128-bit masks that cannot be mitigated by field slicing or `omega` |
| Seeded bug detection | **3 / 3** injected rename bugs rejected with actionable counterexamples | Counterexamples unreadable or masked by over-strong environment axioms |
| Agent refactor repair | **>= 2 / 3** refactors re-proved in **<= 5 turns** without strengthening `sorry` / axioms | Translating wire renames breaks >80% of proof steps requiring manual Lean internals |
| Sail composability | Clean theorem signature linking at least 1 `IssueSlot`/`RenameMapTable` contract to Sail Lean RVFI step | Type mismatch or Lean version incompatibility between `sail-riscv` and `bv_decide` toolchain |

## 6. If Go: Platform Integration Shape (Post-Spike)

Only after Day 14 passes, integrate cleanly behind generic workstation seams:
- New `rvw/src/rvw/lean/` package + `rvw/tests/` unit/differential suite.
- Lean export subcommand (lowering via Yosys JSON + `SpinalDB` span/hierarchy enrichment) and bounded/inductive checker subcommand emitting standard `rvw` verdict JSON (`pass` / `fail` / `inconclusive`).
- Optional `--with-lean` installation group in `scripts/install.sh` and `rvw/src/rvw/doctor/tools.json`.

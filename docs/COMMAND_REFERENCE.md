# CLI and MCP reference

Generated from the command parsers and built-in MCP declarations.
Run `rvw/.venv/bin/python scripts/command-reference.py` to update it.
Run the same command with `--check` to check it.

Use `rvw COMMAND --help` for argument details and defaults.
See the tool READMEs for examples, contracts and limits.
An entry here states availability. It does not qualify a native flow.

## CLI commands

### `rvw`

```text
usage: rvw [-h] [--version] [--project PROJECT]
    {agent-bench,arch,bisect,bundle,cosim,cov,debug,doctor,farm,formal,init,lint,mcp,memory,ooo,perf,privilege,query,reduce,regress,speed-compare,speed-sweep,backends,uvm,uvm-ral,uvm-cpu,hdl,cocotb,soc,verification-plan,wave,workloads}
    ...
```

### `rvw agent-bench`

```text
usage: rvw agent-bench [-h] [--project PROJECT] {dry-run,serve} ...
```

### `rvw agent-bench dry-run`

```text
usage: rvw agent-bench dry-run [-h] --pack PACK --out OUT [--agent
    {scripted,careless}] [--project PROJECT]
```

### `rvw agent-bench serve`

```text
usage: rvw agent-bench serve [-h] --pack PACK --out OUT --task TASK [--project
    PROJECT]
```

### `rvw arch`

```text
usage: rvw arch [-h] [--project PROJECT]
    {ooo-calibrate,ooo-predict,ooo-score,warmup-bias,sample,sched-generate,sched-measure,search,predict,score-prediction,memory-extract,pareto,memory-report,sweep,build,run,calibrate,compare,fit,inspect,measure,linux}
    ...
```

### `rvw arch ooo-calibrate`

```text
usage: rvw arch ooo-calibrate [-h] --out OUT [--json] [--project PROJECT] plan
```

### `rvw arch ooo-predict`

```text
usage: rvw arch ooo-predict [-h] --out OUT [--json] [--project PROJECT]
    calibration config trace
```

### `rvw arch ooo-score`

```text
usage: rvw arch ooo-score [-h] --out OUT [--json] [--project PROJECT]
    prediction c1
```

### `rvw arch warmup-bias`

```text
usage: rvw arch warmup-bias [-h] --out OUT [--json] [--project PROJECT] plan
```

### `rvw arch sample`

```text
usage: rvw arch sample [-h] --out OUT [--interval INTERVAL] [--clusters
    CLUSTERS] [--warmup WARMUP] [--json] [--project PROJECT] trace
```

### `rvw arch sched-generate`

```text
usage: rvw arch sched-generate [-h] --out OUT [--json] [--project PROJECT]
    description_path
```

### `rvw arch sched-measure`

```text
usage: rvw arch sched-measure [-h] --out OUT [--json] [--count COUNT]
    [--timeout TIMEOUT] [--cc CC] [--mca MCA] [--project PROJECT]
    description_path
```

### `rvw arch search`

```text
usage: rvw arch search [-h] --out OUT [--json] [--project PROJECT] plan
```

### `rvw arch predict`

```text
usage: rvw arch predict [-h] --out OUT [--json] [--project PROJECT] candidate
```

### `rvw arch score-prediction`

```text
usage: rvw arch score-prediction [-h] --out OUT [--json] [--project PROJECT]
    prediction rtl
```

### `rvw arch memory-extract`

```text
usage: rvw arch memory-extract [-h] [--json] [--project PROJECT] mapping
```

### `rvw arch pareto`

```text
usage: rvw arch pareto [-h] [--json] [--project PROJECT] plan
```

### `rvw arch memory-report`

```text
usage: rvw arch memory-report [-h] [--json] [--project PROJECT] observations
```

### `rvw arch sweep`

```text
usage: rvw arch sweep [-h] --out OUT [--bench BENCH] [--json] [--project
    PROJECT] spec
```

### `rvw arch build`

```text
usage: rvw arch build [-h] [--json] [--bench BENCH] [--project PROJECT]
```

### `rvw arch run`

```text
usage: rvw arch run [-h] [--json] [--bench BENCH] --out OUT [--timeout
    TIMEOUT] [--project PROJECT]
```

### `rvw arch calibrate`

```text
usage: rvw arch calibrate [-h] [--json] [--bench BENCH] --out OUT [--timeout
    TIMEOUT] [--project PROJECT]
```

### `rvw arch compare`

```text
usage: rvw arch compare [-h] [--json] [--project PROJECT] base candidate
```

### `rvw arch fit`

```text
usage: rvw arch fit [-h] [--json] [--project PROJECT] plan
```

### `rvw arch inspect`

```text
usage: rvw arch inspect [-h] [--json] --elf ELF --isa ISA --kind KIND
    [--project PROJECT]
```

### `rvw arch measure`

```text
usage: rvw arch measure [-h] [--json] [--repeats REPEATS] [--bench BENCH]
    --out OUT [--timeout TIMEOUT] [--project PROJECT]
```

### `rvw arch linux`

```text
usage: rvw arch linux [-h] --out OUT [--platform PLATFORM] [--images IMAGES]
    [--source SOURCE] [--timeout TIMEOUT] [--jobs JOBS] [--llvm]
    [--cross-compile CROSS_COMPILE] [--json] [--project PROJECT]
    {firmware,build,prebuilt,prepare,boot}
```

### `rvw bisect`

```text
usage: rvw bisect [-h] --good GOOD [--bad BAD] [--core-repo CORE_REPO]
    [--core-env CORE_ENV] [--workdir WORKDIR] [--signature SIGNATURE] [--other
    {skip,good,bad}] [--max-cycles MAX_CYCLES] [--hang-cycles HANG_CYCLES]
    [--no-verify] [--remove-clone] [--timeout TIMEOUT] [--json] [--project
    PROJECT] run_dir
```

### `rvw bundle`

```text
usage: rvw bundle [-h] [--out OUT] [-n RETIRED] [--cut-cycles CUT_CYCLES]
    [--no-rerun] [--rerun-window RERUN_WINDOW] [--konata] [--core-config
    CORE_CONFIG] [--pdg PDG] [--trace-wave TRACE_WAVE] [--trace-cycles
    TRACE_CYCLES] [--no-spinaltrace] [--timeout TIMEOUT] [--json] [--project
    PROJECT] run_dir
```

### `rvw cosim`

```text
usage: rvw cosim [-h] [--project PROJECT] {dii,check,generate,live} ...
```

### `rvw cosim dii`

```text
usage: rvw cosim dii [-h] [--project PROJECT] {replay,serve} ...
```

### `rvw cosim dii replay`

```text
usage: rvw cosim dii replay [-h] --tokens TOKENS --core-endpoint CORE_ENDPOINT
    --sail-endpoint SAIL_ENDPOINT [--timeout TIMEOUT] [--json] [--project
    PROJECT]
```

### `rvw cosim dii serve`

```text
usage: rvw cosim dii serve [-h] [--listen LISTEN] --hook HOOK [--max-streams
    MAX_STREAMS] [--timeout TIMEOUT] [--json] [--project PROJECT]
```

### `rvw cosim check`

```text
usage: rvw cosim check [-h] --elf ELF [--core CORE] [--platform PLATFORM]
    [--json] --trace TRACE [--model {spike,sail}] [--history HISTORY]
    [--strict] [--strict-sync KINDS] [--sail SAIL] [--sail-config SAIL_CONFIG]
    [--timeout TIMEOUT] [--project PROJECT]
```

### `rvw cosim generate`

```text
usage: rvw cosim generate [-h] --elf ELF [--core CORE] [--platform PLATFORM]
    [--json] --out OUT [--max-instructions MAX_INSTRUCTIONS] [--project
    PROJECT]
```

### `rvw cosim live`

```text
usage: rvw cosim live [-h] --elf ELF [--core CORE] [--platform PLATFORM]
    [--json] --out OUT --simulator ... [--model {spike,sail}] [--history
    HISTORY] [--strict] [--strict-sync KINDS] [--sail SAIL] [--sail-config
    SAIL_CONFIG] [--timeout TIMEOUT] [--project PROJECT]
```

### `rvw cov`

```text
usage: rvw cov [-h] [--project PROJECT]
    {generate,merge,report,rank,select,closure,isa-diff,isa-check,functional,rtl,prove,mutate}
    ...
```

### `rvw cov generate`

```text
usage: rvw cov generate [-h] --manifest MANIFEST --source-root SOURCE_ROOT
    --goal GOAL --work-dir WORK_DIR --registers REGISTERS [--seed SEED]
    [--timeout-ms TIMEOUT_MS] [--json] [--out OUT] [--project PROJECT]
```

### `rvw cov merge`

```text
usage: rvw cov merge [-h] [--source-root SOURCE_ROOT] [--design-db DESIGN_DB]
    [--scala-root SCALA_ROOT] [--revision REVISION] [--source-map SOURCE_MAP]
    [--hgldd HGLDD] [--dat DAT] [--json] [--out OUT] [--project PROJECT]
    inputs [inputs ...]
```

### `rvw cov report`

```text
usage: rvw cov report [-h] [--exclusions EXCLUSIONS] [--annotate ANNOTATE]
    [--json] [--out OUT] [--project PROJECT] database
```

### `rvw cov rank`

```text
usage: rvw cov rank [-h] [--exact] [--json] [--out OUT] [--project PROJECT]
    database
```

### `rvw cov select`

```text
usage: rvw cov select [-h] --diff DIFF [--repo REPO] [--json] [--out OUT]
    [--project PROJECT] database
```

### `rvw cov closure`

```text
usage: rvw cov closure [-h] --candidates CANDIDATES [--exclusions EXCLUSIONS]
    [--json] [--out OUT] [--project PROJECT] database
```

### `rvw cov isa-diff`

```text
usage: rvw cov isa-diff [-h] --old-source-root OLD_SOURCE_ROOT --source-root
    SOURCE_ROOT [--json] [--out OUT] [--project PROJECT] before after
```

### `rvw cov isa-check`

```text
usage: rvw cov isa-check [-h] [--json] [--out OUT] [--project PROJECT]
    manifest
```

### `rvw cov functional`

```text
usage: rvw cov functional [-h] [--manifest MANIFEST] [--source-root
    SOURCE_ROOT] [--config CONFIG] [--platform PLATFORM] [--json] [--out OUT]
    [--project PROJECT] traces [traces ...]
```

### `rvw cov rtl`

```text
usage: rvw cov rtl [-h] --config CONFIG [--json] [--out OUT] [--project
    PROJECT] traces [traces ...]
```

### `rvw cov prove`

```text
usage: rvw cov prove [-h] --config CONFIG --work-dir WORK_DIR [--timeout
    TIMEOUT] [--json] [--out OUT] [--project PROJECT] database
```

### `rvw cov mutate`

```text
usage: rvw cov mutate [-h] [--run] [--baseline BASELINE] [--timeout TIMEOUT]
    [--jobs JOBS] [--test TEST] [--equivalence-test EQUIVALENCE_TEST] [--json]
    [--out OUT] [--project PROJECT] project
```

### `rvw debug`

```text
usage: rvw debug [-h] [--project PROJECT] {openocd,ingress,etrace} ...
```

### `rvw debug openocd`

```text
usage: rvw debug openocd [-h] --config CONFIG [--openocd OPENOCD] --log LOG
    [--timeout TIMEOUT] [--project PROJECT]
```

### `rvw debug ingress`

```text
usage: rvw debug ingress [-h] --rvfi RVFI --out OUT [--project PROJECT]
```

### `rvw debug etrace`

```text
usage: rvw debug etrace [-h] --reference REFERENCE --packets PACKETS
    --static-config STATIC_CONFIG --user-config USER_CONFIG --toolchain
    TOOLCHAIN --rvfi RVFI --out OUT [--loss] [--timeout TIMEOUT] [--project
    PROJECT]
```

### `rvw doctor`

```text
usage: rvw doctor [-h] [--features FEATURES] [--smoke-elf SMOKE_ELF]
    [--smoke-options SMOKE_OPTIONS] [--smoke-platform SMOKE_PLATFORM]
    [--install FEATURES] [--yes] [--dry-run] [--json] [--project PROJECT]
```

### `rvw farm`

```text
usage: rvw farm [-h] [--project PROJECT]
    {run,cancel,notifications,classify,recover,dashboard} ...
```

### `rvw farm run`

```text
usage: rvw farm run [-h] --hosts HOSTS --manifest MANIFEST --adapter ADAPTER
    --identity-command IDENTITY_COMMAND --identity IDENTITY --out OUT [--jobs
    JOBS] [--timeout TIMEOUT] [--project PROJECT]
```

### `rvw farm cancel`

```text
usage: rvw farm cancel [-h] --out OUT [--project PROJECT]
```

### `rvw farm notifications`

```text
usage: rvw farm notifications [-h] --out OUT [--project PROJECT]
```

### `rvw farm classify`

```text
usage: rvw farm classify [-h] [--project PROJECT] reports [reports ...]
```

### `rvw farm recover`

```text
usage: rvw farm recover [-h] --out OUT [--project PROJECT]
```

### `rvw farm dashboard`

```text
usage: rvw farm dashboard [-h] --root ROOT --out OUT [--core CORE] [--suite
    SUITE] [--config CONFIG] [--gate GATE] [--run RUN] [--project PROJECT]
```

### `rvw formal`

```text
usage: rvw formal [-h] [--project PROJECT]
    {csr,rtl-grid,rtl-refine,relation-strengthen,engines,engine-race,engine-bench,model-grid,security,regress,properties,sva-lower,template,contracts,strengthen,proof-core,apps,autocheck,bench,cex,sby-history,sby-regress,prove,depth-search,riscv,connectivity,equiv,bmc,from-sim,swarm,xprop,x-context,x-sweep}
    ...
```

### `rvw formal csr`

```text
usage: rvw formal csr [-h] --model MODEL --out OUT [--project PROJECT]
```

### `rvw formal rtl-grid`

```text
usage: rvw formal rtl-grid [-h] --manifest MANIFEST --out OUT [--json]
    [--hosts HOSTS] [--timeout TIMEOUT] [--workers WORKERS] [--project
    PROJECT]
```

### `rvw formal rtl-refine`

```text
usage: rvw formal rtl-refine [-h] --manifest MANIFEST --out OUT [--json]
    [--timeout TIMEOUT] [--budget BUDGET] [--max-cuts MAX_CUTS] [--project
    PROJECT]
```

### `rvw formal relation-strengthen`

```text
usage: rvw formal relation-strengthen [-h] --manifest MANIFEST --out OUT
    [--json] [--budget BUDGET] [--engine ENGINE] [--depth DEPTH] [--project
    PROJECT]
```

### `rvw formal engines`

```text
usage: rvw formal engines [-h] --out OUT [--json] [--project PROJECT]
```

### `rvw formal engine-race`

```text
usage: rvw formal engine-race [-h] --manifest MANIFEST --out OUT [--json]
    [--timeout TIMEOUT] [--cross-check] [--project PROJECT]
```

### `rvw formal engine-bench`

```text
usage: rvw formal engine-bench [-h] --manifest MANIFEST --out OUT [--json]
    [--timeout TIMEOUT] [--project PROJECT]
```

### `rvw formal model-grid`

```text
usage: rvw formal model-grid [-h] --manifest MANIFEST --out OUT [--json]
    [--hosts HOSTS] [--timeout TIMEOUT] [--workers WORKERS] [--method
    {induction,cegar}] [--max-k MAX_K] [--max-refinements MAX_REFINEMENTS]
    [--project PROJECT]
```

### `rvw formal security`

```text
usage: rvw formal security [-h] [--project PROJECT] {ift,contract} ...
```

### `rvw formal security ift`

```text
usage: rvw formal security ift [-h] --top TOP --out OUT [--project PROJECT]
    netlist
```

### `rvw formal security contract`

```text
usage: rvw formal security contract [-h] --out OUT [--project PROJECT]
    manifest
```

### `rvw formal regress`

```text
usage: rvw formal regress [-h] --out OUT [--jobs JOBS] [--timeout TIMEOUT]
    [--json] [--project PROJECT] [manifest]
```

### `rvw formal properties`

```text
usage: rvw formal properties [-h] [--channels CHANNELS] --out OUT [--project
    PROJECT] spec
```

### `rvw formal sva-lower`

```text
usage: rvw formal sva-lower [-h] --out OUT [--project PROJECT] source
```

### `rvw formal template`

```text
usage: rvw formal template [-h] [--entries ENTRIES] [--width WIDTH] --out OUT
    [--project PROJECT]
    {rob,freelist,rename,issue,lsq,credit,hpm,initialized_read,axi_lite}
```

### `rvw formal contracts`

```text
usage: rvw formal contracts [-h] --out OUT [--budget BUDGET] [--depth DEPTH]
    [--engine ENGINE] [--json] [--project PROJECT] manifest
```

### `rvw formal strengthen`

```text
usage: rvw formal strengthen [-h] --out OUT [--budget BUDGET] [--depth DEPTH]
    [--engine ENGINE] [--json] [--project PROJECT] manifest
```

### `rvw formal proof-core`

```text
usage: rvw formal proof-core [-h] --smt2 SMT2 --mapping MAPPING [--db DB]
    [--solver SOLVER] [--timeout TIMEOUT] --out OUT [--json] [--project
    PROJECT]
```

### `rvw formal apps`

```text
usage: rvw formal apps [-h] --out OUT [--depth DEPTH] [--engine ENGINE]
    [--timeout TIMEOUT] [--mode {bmc,prove}] [--event-model] [--async-reset]
    [--json] [--project PROJECT] manifest
```

### `rvw formal autocheck`

```text
usage: rvw formal autocheck [-h] --out OUT [--max-properties MAX_PROPERTIES]
    [--depth DEPTH] [--engine ENGINE] [--timeout TIMEOUT] [--mode {bmc,prove}]
    [--xprop] [--json] [--project PROJECT] manifest
```

### `rvw formal bench`

```text
usage: rvw formal bench [-h] --out OUT [--timeout TIMEOUT] [--json] [--project
    PROJECT] manifest
```

### `rvw formal cex`

```text
usage: rvw formal cex [-h] --result RESULT [--trace-index TRACE_INDEX] [--edit
    EDIT] [--timeout TIMEOUT] --out OUT [--json] [--hgldd HGLDD] [--pdg PDG]
    [--criterion CRITERION] [--at-time AT_TIME] [--minimize] [--max-checks
    MAX_CHECKS] [--emit-testbench] [--db DB] [--signal SIGNAL] [--open]
    [--project PROJECT]
```

### `rvw formal sby-history`

```text
usage: rvw formal sby-history [-h] [--project PROJECT] paths [paths ...]
```

### `rvw formal sby-regress`

```text
usage: rvw formal sby-regress [-h] --out OUT [--timeout TIMEOUT] [--json]
    [--project PROJECT] manifest
```

### `rvw formal prove`

```text
usage: rvw formal prove [-h] [--verilog VERILOG [VERILOG ...]] [--top TOP]
    [--clock CLOCK] [--reset RESET] [--reset-active {high,low}] [--checks
    CHECKS] [--depth DEPTH] [--engine ENGINE] [--timeout TIMEOUT] --out OUT
    [--json] [--tie PORT=VALUE] [--memory-model {auto,array,map}]
    [--proof-cache PROOF_CACHE] [--abstraction ABSTRACTION] [--cut CUT]
    [--reset-cycles RESET_CYCLES] [--free-reset] [--first-failure] [--project
    PROJECT]
```

### `rvw formal depth-search`

```text
usage: rvw formal depth-search [-h] [--verilog VERILOG [VERILOG ...]] [--top
    TOP] [--clock CLOCK] [--reset RESET] [--reset-active {high,low}] [--checks
    CHECKS] [--depth DEPTH] [--engine ENGINE] [--timeout TIMEOUT] --out OUT
    [--json] [--tie PORT=VALUE] --max-depth MAX_DEPTH --budget BUDGET
    [--reset-cycles RESET_CYCLES] [--free-reset] [--first-failure] [--project
    PROJECT]
```

### `rvw formal riscv`

```text
usage: rvw formal riscv [-h] --out OUT [--timeout TIMEOUT] [--json] [--project
    PROJECT]
```

### `rvw formal connectivity`

```text
usage: rvw formal connectivity [-h] --db DB --out OUT [--max-nodes MAX_NODES]
    [--json] [--run] [--clock CLOCK] [--reset RESET] [--depth DEPTH] [--engine
    ENGINE] [--timeout TIMEOUT] [--project PROJECT] manifest
```

### `rvw formal equiv`

```text
usage: rvw formal equiv [-h] [--gold GOLD [GOLD ...]] [--gate GATE [GATE ...]]
    [--gold-rev GOLD_REV] [--gate-rev GATE_REV] [--config CONFIG] --top TOP
    [--clock CLOCK] [--reset RESET] [--reset-active {high,low}]
    [--reset-cycles RESET_CYCLES] [--settle SETTLE] [--dsec] [--pair
    GOLD=GATE] [--latency LATENCY] [--unmatched-state {refuse,prove}]
    [--timeout TIMEOUT] --out OUT [--json] [--project PROJECT]
```

### `rvw formal bmc`

```text
usage: rvw formal bmc [-h] [--verilog VERILOG [VERILOG ...]] [--top TOP]
    [--clock CLOCK] [--reset RESET] [--reset-active {high,low}] [--checks
    CHECKS] [--depth DEPTH] [--engine ENGINE] [--timeout TIMEOUT] --out OUT
    [--json] [--tie PORT=VALUE] [--memory-model {auto,array,map}]
    [--proof-cache PROOF_CACHE] [--frontend {verilog,slang,temporal}]
    [--abstraction ABSTRACTION] [--cut CUT] [--event-clock PORT]
    [--event-model] [--clock-schedule PORT=BITS] [--async-reset]
    [--reset-cycles RESET_CYCLES] [--free-reset] [--first-failure] [--project
    PROJECT]
```

### `rvw formal from-sim`

```text
usage: rvw formal from-sim [-h] [--verilog VERILOG [VERILOG ...]] [--top TOP]
    [--clock CLOCK] [--reset RESET] [--reset-active {high,low}] [--checks
    CHECKS] [--depth DEPTH] [--engine ENGINE] [--timeout TIMEOUT] --out OUT
    [--json] [--tie PORT=VALUE] --trace TRACE (--cycle CYCLE | --time TIME)
    [--scope SCOPE] [--memories {trace,free,zero}] [--first-failure]
    [--project PROJECT]
```

### `rvw formal swarm`

```text
usage: rvw formal swarm [-h] [--verilog VERILOG [VERILOG ...]] [--top TOP]
    [--clock CLOCK] [--reset RESET] [--reset-active {high,low}] [--checks
    CHECKS] [--depth DEPTH] [--engine ENGINE] [--timeout TIMEOUT] --out OUT
    [--json] [--tie PORT=VALUE] --trace TRACE [--start-cycle START_CYCLE]
    --end-cycle END_CYCLE [--samples SAMPLES] --budget BUDGET [--scope SCOPE]
    [--memories {trace,free}] [--first-failure] [--project PROJECT]
```

### `rvw formal xprop`

```text
usage: rvw formal xprop [-h] [--verilog VERILOG [VERILOG ...]] [--top TOP]
    [--clock CLOCK] [--reset RESET] [--reset-active {high,low}] [--checks
    CHECKS] [--depth DEPTH] [--engine ENGINE] [--timeout TIMEOUT] --out OUT
    [--json] [--tie PORT=VALUE] [--reset-cycles RESET_CYCLES] [--settle
    SETTLE] [--outputs] [--payload] [--signal SIGNAL] [--filter FILTER]
    [--x-inputs] [--combinational] [--replay {icarus}] [--first-failure]
    [--project PROJECT]
```

### `rvw formal x-context`

```text
usage: rvw formal x-context [-h] [--verilog VERILOG [VERILOG ...]] [--top TOP]
    [--clock CLOCK] [--reset RESET] [--reset-active {high,low}] [--checks
    CHECKS] [--depth DEPTH] [--engine ENGINE] [--timeout TIMEOUT] --out OUT
    [--json] [--tie PORT=VALUE] [--reset-cycles RESET_CYCLES] --signal SIGNAL
    [--project PROJECT]
```

### `rvw formal x-sweep`

```text
usage: rvw formal x-sweep [-h] [--verilog VERILOG [VERILOG ...]] [--top TOP]
    [--clock CLOCK] [--reset RESET] [--reset-active {high,low}] [--checks
    CHECKS] [--depth DEPTH] [--engine ENGINE] [--timeout TIMEOUT] --out OUT
    [--json] [--tie PORT=VALUE] [--module MODULE] [--module-timeout
    MODULE_TIMEOUT] [--campaign-timeout CAMPAIGN_TIMEOUT] [--replay {icarus}]
    [--first-failure] [--project PROJECT]
```

### `rvw init`

```text
usage: rvw init [-h] [--isa ISA] [--xlen {32,64}] [--name NAME] [--wire-build]
    [--sbt-project SBT_PROJECT] [--linker-script LINKER_SCRIPT] [--ram-region
    RAM_REGION] [--reset-pc RESET_PC] [--db-top DB_TOP] [--dry-run] [--force]
    [--json] [--project PROJECT] [path]
```

### `rvw lint`

```text
usage: rvw lint [-h] [--settings SETTINGS] [--benchmark BENCHMARK] [--protocol
    PROTOCOL] [--out OUT] [--depth DEPTH] [--engine ENGINE] [--timeout
    TIMEOUT] [--simulate SAMPLES] [--seed SEED] [--mode {bmc,prove}] [--emit
    DIR] [--sarif PATH] [--json] [--project PROJECT]
```

### `rvw mcp`

```text
usage: rvw mcp [-h] [--list] [--only ONLY] [--json] [--project PROJECT]
```

### `rvw memory`

```text
usage: rvw memory [-h] [--project PROJECT] {images,check} ...
```

### `rvw memory images`

```text
usage: rvw memory images [-h] --hart-image HART=ELF [--project PROJECT]
```

### `rvw memory check`

```text
usage: rvw memory check [-h] --trace TRACE --reference REFERENCE [--project
    PROJECT]
```

### `rvw ooo`

```text
usage: rvw ooo [-h] [--max-cycles MAX_CYCLES] [--effective-config
    EFFECTIVE_CONFIG] [--json] [--project PROJECT] config trace
```

### `rvw perf`

```text
usage: rvw perf [-h] [--json] [--window WINDOW] [--isa {none,riscv}] [--lane
    LANE] [--queue-stage QUEUE_STAGE] [--issue-stage ISSUE_STAGE]
    [--head-stage HEAD_STAGE] [--in-order-retirement] [--result RESULT]
    [--tolerance TOLERANCE] [--top TOP] [--project PROJECT] paths [paths ...]
```

### `rvw privilege`

```text
usage: rvw privilege [-h] [--project PROJECT] {build,reference,check} ...
```

### `rvw privilege build`

```text
usage: rvw privilege build [-h] --out OUT [--gcc GCC] [--json] [--project
    PROJECT] description
```

### `rvw privilege reference`

```text
usage: rvw privilege reference [-h] [--spike SPIKE] [--timeout TIMEOUT]
    [--json] [--project PROJECT] directory
```

### `rvw privilege check`

```text
usage: rvw privilege check [-h] --results RESULTS --platform PLATFORM
    [--timeout TIMEOUT] [--json] [--project PROJECT] directory
```

### `rvw query`

```text
usage: rvw query [-h] [--project PROJECT]
    {build,build-hdl,info,where,drivers,loads,fanin,fanout,path,search,hierarchy,component,regs,export,diff}
    ...
```

### `rvw query build`

```text
usage: rvw query build [-h] [--config CONFIG] [--out OUT] [--json] [--project
    PROJECT]
```

### `rvw query build-hdl`

```text
usage: rvw query build-hdl [-h] --top TOP --out OUT [--yosys YOSYS] [--timeout
    TIMEOUT] [--json] [--project PROJECT] sources [sources ...]
```

### `rvw query info`

```text
usage: rvw query info [-h] [--db DB] [--json] [--project PROJECT]
```

### `rvw query where`

```text
usage: rvw query where [-h] [--db DB] [--json] [--project PROJECT] signal
```

### `rvw query drivers`

```text
usage: rvw query drivers [-h] [--db DB] [--json] [--project PROJECT] signal
```

### `rvw query loads`

```text
usage: rvw query loads [-h] [--db DB] [--json] [--limit LIMIT] [--project
    PROJECT] signal
```

### `rvw query fanin`

```text
usage: rvw query fanin [-h] [--db DB] [--json] [--depth DEPTH]
    [--stop-at-regs] [--kind {blackbox,cond,data,init,sel}] [--limit LIMIT]
    [--include-clock] [--project PROJECT] signal
```

### `rvw query fanout`

```text
usage: rvw query fanout [-h] [--db DB] [--json] [--depth DEPTH]
    [--stop-at-regs] [--kind {blackbox,cond,data,init,sel}] [--limit LIMIT]
    [--include-clock] [--project PROJECT] signal
```

### `rvw query path`

```text
usage: rvw query path [-h] [--db DB] [--json] [--comb-only] [--data-only]
    [--max-paths MAX_PATHS] [--project PROJECT] a b
```

### `rvw query search`

```text
usage: rvw query search [-h] [--db DB] [--json] [--kind
    {reg,wire,port,mem,component}] [--regex] [--scope SCOPE]
    [--include-generated] [--limit LIMIT] [--project PROJECT] pattern
```

### `rvw query hierarchy`

```text
usage: rvw query hierarchy [-h] [--db DB] [--json] [--depth DEPTH] [--project
    PROJECT] [path]
```

### `rvw query component`

```text
usage: rvw query component [-h] [--db DB] [--json] [--project PROJECT] [path]
```

### `rvw query regs`

```text
usage: rvw query regs [-h] [--db DB] [--json] [-r] [--include-generated]
    [--project PROJECT] [path]
```

### `rvw query export`

```text
usage: rvw query export [-h] [--db DB] [--json] [--project PROJECT] artifact
    out
```

### `rvw query diff`

```text
usage: rvw query diff [-h] [--json] [--scope SCOPE] [--limit LIMIT]
    [--no-connections] [--project PROJECT] old new
```

### `rvw reduce`

```text
usage: rvw reduce [-h] [--out OUT] [--signature SIGNATURE] [--modes MODES]
    [--seeds SEEDS] [--seed-start SEED_START] [--latencies LATENCIES]
    [--symbol SYMBOL] [--instruction-symbol INSTRUCTION_SYMBOL] [--monotone]
    [--exhaustive] [--margin MARGIN] [--hang-cycles HANG_CYCLES] [--jobs JOBS]
    [--batch BATCH] [--budget BUDGET] [--timeout TIMEOUT] [--json] [--project
    PROJECT] run_dir
```

### `rvw regress`

```text
usage: rvw regress [-h] [--project PROJECT]
    {speed-compare,speed-sweep,backends,uvm,uvm-ral,uvm-cpu,hdl,cocotb,random,privilege,mmu,vector,run,compare,gate,known,history,list}
    ...
```

### `rvw regress speed-compare`

```text
usage: rvw regress speed-compare [-h] --pair BASELINE CANDIDATE --out OUT
    [--min-seconds MIN_SECONDS] [--resamples RESAMPLES] [--seed SEED]
    [--project PROJECT]
```

### `rvw regress speed-sweep`

```text
usage: rvw regress speed-sweep [-h] --adapter ADAPTER --elf ELF --config
    CONFIG --lock LOCK [--threads THREADS [THREADS ...]] [--repeats REPEATS]
    [--max-cycles MAX_CYCLES] [--timeout TIMEOUT] [--min-seconds MIN_SECONDS]
    [--seed SEED] --out OUT [--project PROJECT]
```

### `rvw regress backends`

```text
usage: rvw regress backends [-h] [--backend {verilator,icarus} | --hdl]
    [--json] [--project PROJECT]
```

### `rvw regress uvm`

```text
usage: rvw regress uvm [-h] --out OUT [--archive ARCHIVE] [--suite SUITE]
    [--verilator VERILATOR] [--seed SEED] [--seeds SEEDS] [--timeout TIMEOUT]
    [--json] [--project PROJECT]
```

### `rvw regress uvm-ral`

```text
usage: rvw regress uvm-ral [-h] --map MAP --out OUT [--project PROJECT]
```

### `rvw regress uvm-cpu`

```text
usage: rvw regress uvm-cpu [-h] --out OUT --elf ELF --platform PLATFORM
    --archive ARCHIVE (--run-dir RUN_DIR | --adapter ADAPTER) [--config
    CONFIG] [--lock LOCK] [--seed SEED] [--max-cycles MAX_CYCLES] [--verilator
    VERILATOR] [--timeout TIMEOUT] [--json] [--project PROJECT]
```

### `rvw regress hdl`

```text
usage: rvw regress hdl [-h] [--backend
    {icarus,verilator-timing,ghdl-yosys-icarus}] --out OUT [--timeout TIMEOUT]
    [--json] [--project PROJECT] manifest
```

### `rvw regress cocotb`

```text
usage: rvw regress cocotb [-h] --out OUT [--seed SEED] [--timeout TIMEOUT]
    [--json] [--project PROJECT] manifest
```

### `rvw regress random`

```text
usage: rvw regress random [-h] [--settings SETTINGS] --out OUT [--seeds SEEDS]
    [--seed-base SEED_BASE] [--core CORE] [--config CONFIG] [--json]
    [--project PROJECT]
```

### `rvw regress privilege`

```text
usage: rvw regress privilege [-h] [--project PROJECT] {build,reference,check}
    ...
```

### `rvw regress privilege build`

```text
usage: rvw regress privilege build [-h] --out OUT [--gcc GCC] [--json]
    [--project PROJECT] description
```

### `rvw regress privilege reference`

```text
usage: rvw regress privilege reference [-h] [--spike SPIKE] [--timeout
    TIMEOUT] [--json] [--project PROJECT] directory
```

### `rvw regress privilege check`

```text
usage: rvw regress privilege check [-h] --results RESULTS --platform PLATFORM
    [--timeout TIMEOUT] [--json] [--project PROJECT] directory
```

### `rvw regress mmu`

```text
usage: rvw regress mmu [-h] [--project PROJECT] {build,reference,check,report}
    ...
```

### `rvw regress mmu build`

```text
usage: rvw regress mmu build [-h] --out OUT [--pma PMA] [--gcc GCC] [--json]
    [--project PROJECT] description
```

### `rvw regress mmu reference`

```text
usage: rvw regress mmu reference [-h] [--spike SPIKE] [--timeout TIMEOUT]
    [--json] [--project PROJECT] directory
```

### `rvw regress mmu check`

```text
usage: rvw regress mmu check [-h] --results RESULTS --platform PLATFORM
    [--model {spike,sail}] [--timeout TIMEOUT] [--sail SAIL] [--json]
    [--project PROJECT] directory
```

### `rvw regress mmu report`

```text
usage: rvw regress mmu report [-h] --results RESULTS [--checked CHECKED]
    [--json] [--project PROJECT] directory
```

### `rvw regress vector`

```text
usage: rvw regress vector [-h] --elf-dir ELF_DIR --results RESULTS [--platform
    PLATFORM] [--json] [--project PROJECT]
```

### `rvw regress run`

```text
usage: rvw regress run [-h] [--core CORE] (--suite SUITE | --tier TIER)
    [--config CONFIG] [--out OUT] [--rev REV] [--source SOURCE] [--fresh]
    [--no-index] [--dry-run] [--jobs JOBS] [--seeds SEEDS] [--seed-base
    SEED_BASE] [--random-seeds] [--filter FILTER] [--max-cycles MAX_CYCLES]
    [--timeout TIMEOUT] [--replay-max-bytes REPLAY_MAX_BYTES] [--rvfi-trace]
    [--no-cache] [--json] [--project PROJECT]
```

### `rvw regress compare`

```text
usage: rvw regress compare [-h] [--core CORE] [--known KNOWN]
    [--perf-tolerance PERF_TOLERANCE] [--allow-missing] [--seed-policy
    {auto,exact,count}] [--out OUT] [--json] [--project PROJECT] base
    candidate
```

### `rvw regress gate`

```text
usage: rvw regress gate [-h] [--core CORE] [--tier TIER] [--base-rev BASE_REV]
    [--base BASE] [--cand-rev CAND_REV] [--cand CAND] [--config CONFIG]
    [--known KNOWN] [--perf-tolerance PERF_TOLERANCE] [--allow-missing]
    [--seed-policy {auto,exact,count}] [--budget-cpu-seconds
    BUDGET_CPU_SECONDS] [--budget-wall-seconds BUDGET_WALL_SECONDS]
    [--budget-job-count BUDGET_JOB_COUNT] [--cost-report COST_REPORT] [--jobs
    JOBS] [--seeds SEEDS] [--seed-base SEED_BASE] [--random-seeds] [--filter
    FILTER] [--max-cycles MAX_CYCLES] [--timeout TIMEOUT] [--replay-max-bytes
    REPLAY_MAX_BYTES] [--rvfi-trace] [--no-cache] [--json] [--project PROJECT]
```

### `rvw regress known`

```text
usage: rvw regress known [-h] [--project PROJECT] {add,list,remove} ...
```

### `rvw regress known add`

```text
usage: rvw regress known add [-h] [--core CORE] [--file FILE] [--from FROM_]
    [--suite SUITE] [--id ID] [--signature SIGNATURE] [--config CONFIG]
    --reason REASON [--rev REV] [--json] [--project PROJECT]
```

### `rvw regress known list`

```text
usage: rvw regress known list [-h] [--core CORE] [--file FILE] [--json]
    [--project PROJECT]
```

### `rvw regress known remove`

```text
usage: rvw regress known remove [-h] [--core CORE] [--file FILE] --suite SUITE
    --id ID [--signature SIGNATURE] [--json] [--project PROJECT]
```

### `rvw regress history`

```text
usage: rvw regress history [-h] [--core CORE] [--rev REV] [--tier TIER]
    [--limit LIMIT] [--json] [--project PROJECT]
```

### `rvw regress list`

```text
usage: rvw regress list [-h] [--core CORE] [--suite SUITE] [--json] [--project
    PROJECT]
```

### `rvw speed-compare`

```text
usage: rvw speed-compare [-h] --pair BASELINE CANDIDATE --out OUT
    [--min-seconds MIN_SECONDS] [--resamples RESAMPLES] [--seed SEED]
    [--project PROJECT]
```

### `rvw speed-sweep`

```text
usage: rvw speed-sweep [-h] --adapter ADAPTER --elf ELF --config CONFIG --lock
    LOCK [--threads THREADS [THREADS ...]] [--repeats REPEATS] [--max-cycles
    MAX_CYCLES] [--timeout TIMEOUT] [--min-seconds MIN_SECONDS] [--seed SEED]
    --out OUT [--project PROJECT]
```

### `rvw backends`

```text
usage: rvw backends [-h] [--backend {verilator,icarus} | --hdl] [--json]
    [--project PROJECT]
```

### `rvw uvm`

```text
usage: rvw uvm [-h] --out OUT [--archive ARCHIVE] [--suite SUITE] [--verilator
    VERILATOR] [--seed SEED] [--seeds SEEDS] [--timeout TIMEOUT] [--json]
    [--project PROJECT]
```

### `rvw uvm-ral`

```text
usage: rvw uvm-ral [-h] --map MAP --out OUT [--project PROJECT]
```

### `rvw uvm-cpu`

```text
usage: rvw uvm-cpu [-h] --out OUT --elf ELF --platform PLATFORM --archive
    ARCHIVE (--run-dir RUN_DIR | --adapter ADAPTER) [--config CONFIG] [--lock
    LOCK] [--seed SEED] [--max-cycles MAX_CYCLES] [--verilator VERILATOR]
    [--timeout TIMEOUT] [--json] [--project PROJECT]
```

### `rvw hdl`

```text
usage: rvw hdl [-h] [--backend {icarus,verilator-timing,ghdl-yosys-icarus}]
    --out OUT [--timeout TIMEOUT] [--json] [--project PROJECT] manifest
```

### `rvw cocotb`

```text
usage: rvw cocotb [-h] --out OUT [--seed SEED] [--timeout TIMEOUT] [--json]
    [--project PROJECT] manifest
```

### `rvw soc`

```text
usage: rvw soc [-h] [--project PROJECT]
    {generate,import-ipxact,capture-check,check} ...
```

### `rvw soc generate`

```text
usage: rvw soc generate [-h] --out OUT [--json] [--project PROJECT] map
```

### `rvw soc import-ipxact`

```text
usage: rvw soc import-ipxact [-h] --template TEMPLATE --out OUT [--json]
    [--project PROJECT] source
```

### `rvw soc capture-check`

```text
usage: rvw soc capture-check [-h] --capture CAPTURE --result RESULT [--json]
    [--project PROJECT] map
```

### `rvw soc check`

```text
usage: rvw soc check [-h] --bindings BINDINGS --db DB [--transactions
    TRANSACTIONS] [--json] [--project PROJECT] map
```

### `rvw verification-plan`

```text
usage: rvw verification-plan [-h] [--project PROJECT] {generate,check} ...
```

### `rvw verification-plan generate`

```text
usage: rvw verification-plan generate [-h] --out OUT [--project PROJECT]
    declaration
```

### `rvw verification-plan check`

```text
usage: rvw verification-plan check [-h] --out OUT [--project PROJECT] plan
    observations
```

### `rvw wave`

```text
usage: rvw wave [-h] [--project PROJECT]
    {index,verify,list,changes,sample,cut,find,edges,why,seq,txn,diff,info}
    ...
```

### `rvw wave index`

```text
usage: rvw wave index [-h] -o OUT [--reader {auto,vcd,wellen}] [--json]
    [--project PROJECT] wave
```

### `rvw wave verify`

```text
usage: rvw wave verify [-h] [--source SOURCE] [--json] [--project PROJECT]
    index
```

### `rvw wave list`

```text
usage: rvw wave list [-h] [--json] [--period PERIOD] [--clock CLOCK]
    [--indexed] [--project PROJECT] wave [regex]
```

### `rvw wave changes`

```text
usage: rvw wave changes [-h] [--json] [--period PERIOD] [--clock CLOCK]
    [--indexed] [--from T0] [--to T1] [--limit LIMIT] [--dec] [--project
    PROJECT] wave regex
```

### `rvw wave sample`

```text
usage: rvw wave sample [-h] [--json] [--period PERIOD] [--clock CLOCK]
    [--indexed] --at AT [--dec] [--project PROJECT] wave regex
```

### `rvw wave cut`

```text
usage: rvw wave cut [-h] [--json] [--period PERIOD] [--clock CLOCK]
    [--indexed] --from T0 [--to T1] [--signals SIGNALS] [--rebase] -o OUT
    [--project PROJECT] wave
```

### `rvw wave find`

```text
usage: rvw wave find [-h] [--json] [--period PERIOD] [--clock CLOCK]
    [--indexed] [--from T0] [--to T1] [--limit LIMIT] [--project PROJECT] wave
    expr
```

### `rvw wave edges`

```text
usage: rvw wave edges [-h] [--json] [--period PERIOD] [--clock CLOCK]
    [--indexed] [--from T0] [--to T1] [--project PROJECT] wave regex
```

### `rvw wave why`

```text
usage: rvw wave why [-h] [--json] [--period PERIOD] [--clock CLOCK]
    [--indexed] --at AT [--db DB] [--depth DEPTH] [--max-nodes MAX_NODES]
    [--project PROJECT] wave signal
```

### `rvw wave seq`

```text
usage: rvw wave seq [-h] [--json] [--period PERIOD] [--clock CLOCK]
    [--indexed] [--from T0] [--to T1] [--limit LIMIT] [--project PROJECT] wave
    sequence
```

### `rvw wave txn`

```text
usage: rvw wave txn [-h] [--json] [--period PERIOD] [--clock CLOCK]
    [--indexed] [--valid VALID] [--ready READY] [--payload PAYLOAD] [--stream
    STREAM] [--db DB] [--from T0] [--to T1] [--limit LIMIT] [--project
    PROJECT] wave
```

### `rvw wave diff`

```text
usage: rvw wave diff [-h] [--json] [--period PERIOD] [--clock CLOCK]
    [--indexed] [--signals SIGNALS] [--from T0] [--to T1] [--offset OFFSET]
    [--map MAP] [--on-clock] [--all] [--limit LIMIT] [--project PROJECT] wave
    other
```

### `rvw wave info`

```text
usage: rvw wave info [-h] [--json] [--period PERIOD] [--clock CLOCK]
    [--indexed] [--project PROJECT] wave
```

### `rvw workloads`

```text
usage: rvw workloads [-h] [--project PROJECT] {list,build,verify} ...
```

### `rvw workloads list`

```text
usage: rvw workloads list [-h] [--json] [--manifest MANIFEST] [--project
    PROJECT]
```

### `rvw workloads build`

```text
usage: rvw workloads build [-h] [--json] [--manifest MANIFEST] --source SOURCE
    --out OUT [--cc CC] [--bench BENCH] [--project PROJECT]
```

### `rvw workloads verify`

```text
usage: rvw workloads verify [-h] [--json] --build BUILD --out OUT [--oracle
    ORACLE] [--trace] [--timeout TIMEOUT] [--project PROJECT]
```

## MCP tools

The default server exposes 112 built-in tools, including the four job tools.
`--only` filters packages. `RVW_MCP_PLUGINS` can add tools.
`rvw mcp --list --json` returns full input schemas.
CLI commands without an MCP entry are CLI-only.
Isolated calls can return a job after the sync timeout, even when
they do not start a background job at once.

### `arch_build`

Locate native gem5 and build bare-metal benchmarks with local GCC.

Arguments: `project`, `bench`.

Starts a background job: yes.

### `arch_calibrate`

Run the same captured ELFs through C1 and native gem5. Report the ROI gap without an acceptance verdict.

Arguments: `project`, `bench`, `out` (required), `timeout`.

Starts a background job: yes.

### `arch_compare`

Compare saved architecture runs. Refuse unequal ELFs, instruction counts or missing evidence.

Arguments: `base` (required), `candidate` (required).

Starts a background job: yes.

### `arch_fit`

Select saved model candidates on training events and score the winner on held-out workloads.

Arguments: `plan` (required), `project`.

Starts a background job: yes.

### `arch_inspect`

Check ELF layout and report CPU/ISA compatibility. Static only; unsupported combinations stay blocked.

Arguments: `elf` (required), `isa` (required), `kind` (required), `project`.

Starts a background job: yes.

### `arch_measure`

Repeat RTL and gem5 measurements and report confidence intervals.

Arguments: `project`, `bench`, `out` (required), `timeout`, `repeats`.

Starts a background job: yes.

### `arch_memory_extract`

Extract exact project counter mappings from native gem5 ROI stats.

Arguments: `mapping` (required), `project`.

Starts a background job: yes.

### `arch_memory_report`

Report declared memory observations. Missing metrics stay unobserved.

Arguments: `observations` (required), `project`.

Starts a background job: yes.

### `arch_pareto`

Compare model cycles with optional user-supplied area and power inputs.

Arguments: `plan` (required), `project`.

Starts a background job: yes.

### `arch_predict`

Store a timestamped model prediction before RTL measurement.

Arguments: `candidate` (required), `out` (required), `project`.

Starts a background job: yes.

### `arch_run`

Run native gem5 with the selected project description. The output directory must be new.

Arguments: `project`, `bench`, `out` (required), `timeout`.

Starts a background job: yes.

### `arch_sample`

Select instruction-weighted BBV phases from complete C2. No restore or fidelity claim.

Arguments: `trace` (required), `out` (required), `project`, `interval`, `clusters`, `warmup`.

Starts a background job: yes.

### `arch_score_prediction`

Score a stored prediction against later RTL evidence.

Arguments: `prediction` (required), `rtl` (required), `out` (required), `project`.

Starts a background job: yes.

### `arch_search`

Run bounded Bayesian fitting and score the selected point on held-out workloads.

Arguments: `plan` (required), `out` (required), `project`.

Starts a background job: yes.

### `arch_sweep`

Run a bounded serial gem5 sweep. Retain model-only identities and SQLite results.

Arguments: `spec` (required), `out` (required), `project`, `bench`.

Starts a background job: yes.

### `arch_warmup_bias`

Compare saved fixed-ROI warmup observations after architectural suffix checks.

Arguments: `plan` (required), `out` (required), `project`.

Starts a background job: yes.

### `bisect_run`

Find the core revision introducing a failure signature, testing revisions in a private clone. Writes bisection reports. Returns a job; adapter runs take the core lock.

Arguments: `project`, `run_dir` (required), `good` (required), `bad`, `core_repo`, `core_env`, `workdir`, `signature`, `other`, `max_cycles`, `hang_cycles`, `no_verify`, `remove_clone`, `timeout`.

Starts a background job: yes.

### `bundle_make`

Build a failure bundle with retirement history, waveform window and suspected unit. May re-run the adapter and invoke SpinalTrace. Returns a job; re-runs take the core lock.

Arguments: `run_dir` (required), `out`, `retired`, `cut_cycles`, `no_rerun`, `rerun_window`, `konata`, `core_config`, `project`, `pdg`, `trace_wave`, `trace_cycles`, `no_spinaltrace`, `timeout`.

Starts a background job: yes.

### `cosim_check`

Check a recorded C2 RVFI trace against Spike or Sail to locate the first architectural mismatch. Preserves synchronization scope and matching-prefix/end status. A match does not mean the program passed: check end_status. The Sail executable comes from RVW_SAIL on the server. Large traces run as a cancellable job.

Arguments: `project`, `elf` (required), `core`, `platform`, `trace` (required), `model`, `history`, `strict`, `strict_sync`, `sail_config`, `timeout`.

Starts a background job: yes.

### `cosim_generate`

Generate a C2 trace from Spike for an ELF, for reference fixtures or later comparison. Writes out (refused if out is the ELF or an existing file that is not a C2 trace) and returns reproduction metadata; runs as a cancellable job.

Arguments: `project`, `elf` (required), `core`, `platform`, `out` (required), `max_instructions`.

Starts a background job: yes.

### `cov_closure`

List unhit bins with project-declared candidate tests. Suggestions are not hits.

Arguments: `database` (required), `candidates` (required), `exclusions`, `out`.

Starts a background job: yes.

### `cov_functional`

Report RVFI functional coverage bins and holes from C2 traces or saved functional reports. Use config for a declarative coverage plan; large traces run as a job.

Arguments: `traces` (required), `config`, `manifest`, `source_root`, `platform`.

Starts a background job: yes.

### `cov_generate`

Solve one declared pinned integer ISA goal with Z3. Emits a bounded payload and solver evidence. A generated candidate earns no coverage hits and is not a core correctness result.

Arguments: `manifest` (required), `source_root` (required), `goal` (required), `work_dir` (required), `registers` (required), `seed`, `timeout_ms`, `out`.

Starts a background job: yes.

### `cov_merge`

Merge per-test coverage.dat or C1/C3 results into a coverage database before reporting/ranking. Retains source attribution and rejects incompatible point universes; large inputs run as a job.

Arguments: `inputs` (required), `source_root`, `scala_root`, `revision`, `source_map`, `design_db`, `hgldd`, `dat`, `out`.

Starts a background job: yes.

### `cov_mutate`

Read historical MCY outcomes, or run a captured project with run=true after baseline validation. To earn kills or equivalence, declare all external inputs in the project's rvw-external-inputs JSON list; [] declares none. Legacy databases and saved runs without complete dependency captures stay inconclusive with zero earned counts and retained observations. Inspection uses saved detection and equivalence roles unless explicitly overridden. The job holds the machine heavy-job lock ($RVW_HEAVY_LOCK, or `lock`; empty for none).

Arguments: `project` (required), `run`, `baseline`, `timeout`, `jobs`, `test`, `equivalence_test`, `lock`, `out`.

Starts a background job: yes.

### `cov_prove`

Run bounded cover and unbounded safety proofs for reviewed coverage-point expressions. Use a fresh work_dir; exclusions retain assumptions and hashes. The job holds the machine heavy-job lock ($RVW_HEAVY_LOCK, or `lock`; empty for none).

Arguments: `database` (required), `config` (required), `work_dir` (required), `timeout`, `lock`, `out`.

Starts a background job: yes.

### `cov_rank`

Rank test contributions and choose a deterministic coverage-preserving test set. exact proves minimum cardinality only for at most 20 tests. Runs as a job.

Arguments: `database` (required), `exact`.

Starts a background job: yes.

### `cov_report`

Inspect hit rates, source attribution and never-hit coverage points; optionally apply proof exclusions to measured hit rates. Large databases run as a job.

Arguments: `database` (required), `exclusions`.

Starts a background job: yes.

### `cov_rtl`

Sample typed RTL bins and bounded sequences from exact-instance samples. Incomplete traces stay inconclusive. Unobserved bins are not unreachable.

Arguments: `traces` (required), `config` (required), `out`.

Starts a background job: yes.

### `cov_select`

Select regression tests covering Scala changes in BASE..HEAD. Uses BASE-side mappings and falls back to all tests when coverage cannot justify omissions. Runs as a job.

Arguments: `database` (required), `diff` (required), `repo`.

Starts a background job: yes.

### `farm_cancel`

Cancel shards and confirm host process-group cleanup.

Arguments: `out` (required).

Starts a background job: yes.

### `farm_classify`

Classify identity-bound recorded repeats. Retain every DUT failure.

Arguments: `reports` (required).

Starts a background job: yes.

### `farm_dashboard`

Write filtered C3/C4 history. Missing evidence remains visible.

Arguments: `root` (required), `out` (required), `core`, `suite`, `config`, `gate`, `run`.

Starts a background job: yes.

### `farm_notifications`

Export notification events. No external delivery is attempted.

Arguments: `out` (required).

Starts a background job: yes.

### `farm_recover`

Read crash checkpoints. Missing final collection stays inconclusive.

Arguments: `out` (required).

Starts a background job: no.

### `farm_run`

Run native SSH shards. Complete is transport completeness, not a gate verdict.

Arguments: `hosts` (required), `manifest` (required), `adapter` (required), `identity_command` (required), `identity` (required), `out` (required), `jobs`, `timeout`.

Starts a background job: yes.

### `formal_apps`

Run reviewed connectivity, CSR, bounded progress, UNR and FSM monitor contracts.

Arguments: `manifest` (required), `out` (required), `depth`, `engine`, `timeout`, `mode`, `event_model`, `async_reset`.

Starts a background job: yes.

### `formal_autocheck`

Check per-bit constants, declared dead code and FSM coverage. Optional output X propagation.

Arguments: `manifest` (required), `out` (required), `max_properties`, `depth`, `engine`, `timeout`, `mode`, `xprop`.

Starts a background job: yes.

### `formal_bmc`

Bounded model check of a design's assertions from reset (SymbiYosys). Use for shallow bugs; failures are named by SpinalChecks id and Scala line when `checks` is given. Runs as a job.

Arguments: `project`, `verilog`, `top`, `out` (required), `clock`, `reset`, `reset_active`, `checks`, `depth`, `engine`, `timeout`, `tie`, `reset_cycles`, `free_reset`, `first_failure`, `clock_schedule`, `event_model`, `event_clock`, `async_reset`.

Starts a background job: yes.

### `formal_cex`

Replay a captured failing BMC witness with edited inputs through Yosys sim. Not a proof.

Arguments: `result` (required), `out` (required), `trace_index`, `edit`, `hgldd`, `pdg`, `criterion`, `at_time`, `open`, `minimize`, `max_checks`, `emit_testbench`, `db`, `signal`, `timeout`.

Starts a background job: yes.

### `formal_csr`

Generate CSR monitors, directed assembly and coverage. Does not run verification.

Arguments: `model` (required), `out` (required).

Starts a background job: yes.

### `formal_engine_bench`

Measure all engine and pinned case pairs.

Arguments: `out` (required), `manifest` (required), `timeout`.

Starts a background job: yes.

### `formal_engine_race`

Race native engines on pinned RTL. Bounded success is inconclusive.

Arguments: `out` (required), `manifest` (required), `timeout`, `cross_check`.

Starts a background job: yes.

### `formal_engines`

Report installed and missing native engine dependencies.

Arguments: `out` (required).

Starts a background job: yes.

### `formal_from_sim`

Bounded model check starting from cycle N (or time T) of a Verilator FST/VCD of the same Verilog: finds bugs too deep for BMC from reset. Memories come from the trace by default. Runs as a job.

Arguments: `project`, `verilog`, `top`, `out` (required), `clock`, `reset`, `reset_active`, `checks`, `depth`, `engine`, `timeout`, `tie`, `trace` (required), `cycle`, `time`, `scope`, `memories`, `first_failure`.

Starts a background job: yes.

### `formal_model_grid`

Prove properties of an explicit finite model. No RTL translation claim.

Arguments: `out` (required), `manifest` (required), `hosts`, `timeout`, `workers`, `method`, `max_k`, `max_refinements`.

Starts a background job: yes.

### `formal_proof_core`

Extract a deletion-minimal solver core for one named SMT query. Not an RTL proof.

Arguments: `smt2` (required), `mapping` (required), `db`, `solver`, `timeout`, `out` (required).

Starts a background job: yes.

### `formal_properties`

Generate SVA for common intents and typed Stream/Flow channels. Does not run a proof.

Arguments: `spec` (required), `channels`, `out` (required).

Starts a background job: yes.

### `formal_regress`

Run declared SBY property tasks with a CPU worker cap. Return conditional C3 and JUnit observations.

Arguments: `manifest`, `project`, `out` (required), `jobs`, `timeout`.

Starts a background job: yes.

### `formal_relation_strengthen`

Mine relational trace candidates and independently prove each helper before use.

Arguments: `out` (required), `manifest` (required), `budget`, `depth`, `engine`.

Starts a background job: yes.

### `formal_rtl_grid`

Split pinned exported RTL properties across local and farm workers.

Arguments: `out` (required), `manifest` (required), `hosts`, `timeout`, `workers`.

Starts a background job: yes.

### `formal_rtl_refine`

Automatically cut internal RTL state and RAM read outputs, then restore drivers after abstract failures.

Arguments: `out` (required), `manifest` (required), `budget`, `timeout`, `max_cuts`.

Starts a background job: yes.

### `formal_sva_lower`

Lower finite clocked SVA to native Yosys assertions. Unsupported constructs give named errors.

Arguments: `source` (required), `out` (required).

Starts a background job: yes.

### `formal_template`

Generate a project-bound safety monitor. No verification run.

Arguments: `kind` (required), `out` (required), `entries`, `width`.

Starts a background job: yes.

### `formal_x_sweep`

Bounded per-module X inventory with native Icarus replay. Not an acceptance gate.

Arguments: `project`, `verilog`, `top`, `out` (required), `clock`, `reset`, `reset_active`, `checks`, `depth`, `engine`, `timeout`, `tie`, `module`, `module_timeout`, `campaign_timeout`, `replay`.

Starts a background job: yes.

### `formal_xprop`

X-propagation: can an uninitialized register or memory make a checked signal (outputs, stream valid/ready, payload while valid) X after reset? Runs as a job.

Arguments: `project`, `verilog`, `top`, `out` (required), `clock`, `reset`, `reset_active`, `checks`, `depth`, `engine`, `timeout`, `tie`, `reset_cycles`, `settle`, `outputs`, `payload`, `signal`, `filter`, `x_inputs`, `combinational`, `replay`.

Starts a background job: yes.

### `job_cancel`

Cancel a background job: SIGTERM its process groups, SIGKILL after a grace period. Returns the status (`cancelling` while a handler has not stopped yet).

Arguments: `job_id` (required).

Starts a background job: no.

### `job_list`

All background jobs of this server and their status.

Arguments: none.

Starts a background job: no.

### `job_log`

Last lines of a background job's log.

Arguments: `job_id` (required), `tail`.

Starts a background job: no.

### `job_status`

Status of a background job started by a long-running tool; includes the result when done. Pass wait_s (max 60) to block until it finishes.

Arguments: `job_id` (required), `wait_s`.

Starts a background job: no.

### `lint_report`

Run native lint and structural CDC/RDC. Retain waivers and unrun checks. No signoff.

Arguments: `settings` (required).

Starts a background job: yes.

### `memory_check`

Check C2/2 serialized memory against independent stimulus bytes. No RVWMO proof.

Arguments: `trace` (required), `reference` (required).

Starts a background job: no.

### `memory_images`

Prepare pinned per-hart ELF inputs. Does not run a DUT.

Arguments: `hart_images` (required).

Starts a background job: no.

### `ooo_calibrate`

Report saved OoO timing evidence without a fidelity verdict.

Arguments: `plan` (required), `out` (required), `project`.

Starts a background job: yes.

### `ooo_predict`

Report saved OoO timing evidence without a fidelity verdict.

Arguments: `calibration` (required), `config` (required), `trace` (required), `out` (required), `project`.

Starts a background job: yes.

### `ooo_run`

Predict committed-path OoO timing. Accuracy remains inconclusive.

Arguments: `config` (required), `trace` (required), `max_cycles`, `effective_config`.

Starts a background job: yes.

### `ooo_score_prediction`

Report saved OoO timing evidence without a fidelity verdict.

Arguments: `prediction` (required), `c1` (required), `out` (required), `project`.

Starts a background job: yes.

### `perf_compare`

Compare two pipeline logs or rvw.perf/1 reports to find performance changes above tolerance. Analysis settings must match; differences are magnitudes, not statistical significance. Runs as a job.

Arguments: `base` (required), `candidate` (required), `window`, `isa`, `lane`, `queue_stage`, `issue_stage`, `head_stage`, `in_order_retirement`, `tolerance`.

Starts a background job: yes.

### `perf_report`

Measure pipeline stage residence, IPC windows, discarded work and inferred retirement bubbles from a Kanata 0004 log (or load a saved report). Large logs run as a job. Stage names are explicit options.

Arguments: `path` (required), `window`, `isa`, `lane`, `queue_stage`, `issue_stage`, `head_stage`, `in_order_retirement`, `result`.

Starts a background job: yes.

### `query_build_db`

Elaborate a design and write its design database (minutes for a CPU). Either `design` (a Spinal component class with a no-argument constructor, on the classpath of `sbt_dir`, default SpinalDB/spinaldb) or `entry` plus `config`: a named entry of SpinalDB/build-db.sh (here: boom) and its configuration. An entry holds the machine lock it declares. Returns a job id.

Arguments: `project`, `out` (required), `design`, `entry`, `config`, `sbt_dir`, `test_classpath`, `options`.

Starts a background job: yes.

### `query_component`

One component: ports, interfaces (Stream/Flow/bundles), children, registers, memories, Areas, counts.

Arguments: `project`, `db`, `path`.

Starts a background job: no.

### `query_diff`

What changed in the elaborated hardware between two databases (e.g. before and after a Scala edit): components, ports, registers, memories, signals, connections between named signals, and the logic of each changed signal.

Arguments: `old` (required), `new` (required), `scope`, `limit`, `connections`.

Starts a background job: no.

### `query_drivers`

What drives a signal: every assignment with its source expression, when/switch conditions, enables, Scala location; for registers the clock, reset signal/kind/value; for memories the ports. Assignments are in elaboration order (later wins).

Arguments: `project`, `db`, `signal` (required).

Starts a background job: no.

### `query_export`

Write an artifact stored in the database to a file: `blocks` (SpinalBlocks diagram JSON), `pdg` (SpinalTrace PDG JSON), `hgldd` (SpinalWaves HGLDD for Surfer).

Arguments: `project`, `db`, `artifact` (required), `out` (required).

Starts a background job: no.

### `query_fanin`

Transitive drivers of a signal or interface up to `depth`, through logic (compiler temporaries are transparent). Lists signals, edges, registers and ports reached.

Arguments: `project`, `db`, `signal` (required), `depth`, `stop_at_regs`, `kinds`, `include_clock`, `limit`.

Starts a background job: no.

### `query_fanout`

Transitive readers of a signal or interface up to `depth` (see query_fanin).

Arguments: `project`, `db`, `signal` (required), `depth`, `stop_at_regs`, `kinds`, `include_clock`, `limit`.

Starts a background job: no.

### `query_hierarchy`

Component tree below `path` (default: toplevel): instance names, Verilog modules, Scala classes, source locations.

Arguments: `project`, `db`, `path`, `depth`.

Starts a background job: no.

### `query_info`

What a design database holds: toplevel, configuration, counts, clock domains, artifacts (blocks, pdg, hgldd), RTL files, warnings.

Arguments: `project`, `db`.

Starts a background job: no.

### `query_loads`

What reads a signal: reader signals with how (data, cond, sel), the statements and the conditions that use it.

Arguments: `project`, `db`, `signal` (required), `limit`.

Starts a background job: no.

### `query_path`

Shortest dependency paths from `a` (read) to `b` (driven): each hop with the statement linking it and its Scala location, and the number of register stages. comb_only stops at registers, memories and synchronous read state; data_only ignores conditions and selects.

Arguments: `project`, `db`, `a` (required), `b` (required), `comb_only`, `data_only`, `max_paths`.

Starts a background job: no.

### `query_regs`

Registers of a component (recursive: of its subtree) with width, clock, reset value and Scala location.

Arguments: `project`, `db`, `path`, `recursive`, `include_generated`.

Starts a background job: no.

### `query_search`

Find signals and components by name: substring, glob (*, ?) or regex; filter by kind (reg, wire, port, mem, component) and scope (component path).

Arguments: `project`, `db`, `pattern` (required), `kind`, `regex`, `scope`, `include_generated`, `limit`.

Starts a background job: no.

### `query_where`

Where a signal (or bundle/Area) is: Scala source line, Verilog module/name/line, waveform path, Spinal path, type, width, clock domain and reset value.

Arguments: `project`, `db`, `signal` (required).

Starts a background job: no.

### `reduce_run`

Shrink a failing C1 run while preserving its signature. Tries cycles, seeds, latencies and optional integer data symbols. Returns a job; simulations take the core lock. The result's `reproduced` is false when no trial matched; a timeout matches only as a hang (no retirement in the last hang_cycles cycles, from an RVFI trace). A symbol's `smallest_failing` is the smallest tested failing value, or null when the original value did not reproduce in this search. It is `exact` only with monotone or exhaustive after the failing upper bound is confirmed.

Arguments: `project`, `run_dir` (required), `out`, `signature`, `modes`, `seeds`, `seed_start`, `latencies`, `instruction_symbol`, `symbol`, `margin`, `hang_cycles`, `jobs`, `batch`, `budget`, `timeout`, `monotone`, `exhaustive`.

Starts a background job: yes.

### `regress_compare`

Decide accept/reject/inconclusive from stored base and candidate results, known failures and performance tolerance. C4 /2 separates tests (pass/fail/incomplete) from verdict. Accept requires clean committed source identities on both sides. Inconclusive means harness errors, wall-clock timeouts or no shared tests: rerun, do not accept. Writes verdict.json beside the candidate unless out is given. Inputs accept directories, run IDs/prefixes or latest.

Arguments: `project`, `core`, `known`, `perf_tolerance`, `allow_missing`, `seed_policy`, `base` (required), `candidate` (required), `out`.

Starts a background job: no.

### `regress_gate`

Gate a change by running a tier on base/candidate revisions or comparing stored runs. base and base_rev are mutually exclusive; cand and cand_rev are mutually exclusive. Use base_rev or base; candidate defaults to HEAD when clean. Dirty trees run but cannot accept: C4 /2 reports tests separately and not_accepted_reason=uncommitted. Commit (a scratch branch is fine) and rerun; complete RTL identities reuse passing results. Returns a job; the runner takes the core lock.

Arguments: `project`, `core`, `known`, `perf_tolerance`, `allow_missing`, `seed_policy`, `jobs`, `seeds`, `seed_base`, `random_seeds`, `filter`, `max_cycles`, `timeout`, `rvfi_trace`, `no_cache`, `replay_max_bytes`, `budget_cpu_seconds`, `budget_wall_seconds`, `budget_job_count`, `cost_report`, `tier`, `config`, `base_rev`, `base`, `cand_rev`, `cand`.

Starts a background job: yes.

### `regress_history`

Find stored runs and their status before comparing or resuming; filter core, revision prefix or tier.

Arguments: `project`, `core`, `rev`, `tier`, `limit`.

Starts a background job: no.

### `regress_known_add`

Record an understood failure with a reason. Give suite/id/signature, or from_ for failures in stored results. Indexed imports are scoped by core; explicit result paths must also match that core. Imports keep result configs; config filters results. from_ and signature are mutually exclusive. Updates the known-failures TOML selected by file or core.

Arguments: `project`, `core`, `file`, `from_`, `suite`, `id`, `signature`, `config`, `reason` (required), `rev`.

Starts a background job: no.

### `regress_known_list`

Inspect recorded known failures before triage or gating; choose file or core config.

Arguments: `project`, `core`, `file`.

Starts a background job: no.

### `regress_known_remove`

Remove a resolved or obsolete known-failure entry by suite and test ID, optionally signature.

Arguments: `project`, `core`, `file`, `suite` (required), `id` (required), `signature`.

Starts a background job: no.

### `regress_list`

Discover a core's suites, tiers and configurations before running; pass suite to list test IDs.

Arguments: `project`, `core`, `suite`.

Starts a background job: no.

### `regress_privilege_build`

Build self-checking privilege ELFs from project data.

Arguments: `description` (required), `out` (required), `gcc`.

Starts a background job: no.

### `regress_privilege_check`

Check C1 results and strict Spike traces by functional group.

Arguments: `directory` (required), `results` (required), `platform` (required), `timeout`.

Starts a background job: no.

### `regress_privilege_reference`

Run short Spike self-checks. Does not earn DUT coverage.

Arguments: `directory` (required), `spike`, `timeout`.

Starts a background job: no.

### `regress_random`

Generate pinned riscv-dv programs, compile project runtime, run C1 and compare complete C2 with Spike. Only qualified runs earn functional coverage. Generator, compiler, adapter and comparison errors remain separate.

Arguments: `project`, `core`, `settings`, `out` (required), `config`, `seeds`, `seed_base`.

Starts a background job: yes.

### `regress_run`

Run suites or a tier through the core adapter, resume/cache results, or preview with dry_run. source and rev are mutually exclusive. Use regress_compare or regress_gate for an accept/reject decision. Returns a job; the runner takes the core lock.

Arguments: `project`, `core`, `jobs`, `seeds`, `seed_base`, `random_seeds`, `filter`, `max_cycles`, `timeout`, `rvfi_trace`, `no_cache`, `replay_max_bytes`, `suite`, `tier`, `config`, `out`, `rev`, `source`, `fresh`, `no_index`, `dry_run`.

Starts a background job: yes.

### `rvw_doctor`

Read-only setup checks. No native build/run conformance claim. Installation is CLI-only.

Arguments: `project`, `features`.

Starts a background job: no.

### `verification_plan_check`

Compare supplied observations with separately authored reference vectors as bounded C3 evidence.

Arguments: `plan` (required), `observations` (required), `out` (required).

Starts a background job: no.

### `verification_plan_generate`

Generate unrun extension and envcfg cases from explicit versioned obligations.

Arguments: `declaration` (required), `out` (required).

Starts a background job: no.

### `wave_changes`

Read changes of matching signals within a time window. Returns {changes, truncated, limit}; limit defaults to 10000 (0 = no limit) and truncated says more matched.

Arguments: `wave` (required), `indexed`, `regex` (required), `period`, `clock`, `t0`, `t1`, `limit`, `dec`.

Starts a background job: no.

### `wave_cut`

Write a self-contained waveform window, optionally keeping selected signals and rebasing time.

Arguments: `wave` (required), `indexed`, `period`, `clock`, `t0` (required), `t1`, `out` (required), `signals`, `rebase`.

Starts a background job: no.

### `wave_diff`

Compare two waves (signals paired by name, optional prefix map and time offset) and report the first divergence time and the differing signals; status match/diverged/no_points.

Arguments: `wave` (required), `indexed`, `period`, `clock`, `t0`, `t1`, `other` (required), `signals`, `offset`, `map`, `on_clock`, `all`, `limit`.

Starts a background job: no.

### `wave_edges`

Count value changes, rising and falling edges and x/z transitions per matching signal.

Arguments: `wave` (required), `indexed`, `regex` (required), `period`, `clock`, `t0`, `t1`.

Starts a background job: no.

### `wave_find`

Find when an expression over several signals holds: first time, last interval and all intervals in a window. Syntax: && || ! == < + & bit selects sig[7:0], rose(s), fell(s), changed(s), stable(s), known(s); x/z make the result unknown, which never counts as true.

Arguments: `wave` (required), `indexed`, `period`, `clock`, `t0`, `t1`, `expr` (required), `limit`.

Starts a background job: no.

### `wave_index`

Build an identity-bound .rvwi index of a VCD/FST wave for fast window, sample and search queries.

Arguments: `wave` (required), `out` (required), `reader`.

Starts a background job: no.

### `wave_index_verify`

Check a .rvwi index against its source wave by full SHA-256 (fresh true/false).

Arguments: `index` (required), `source`.

Starts a background job: no.

### `wave_info`

Inspect timescale, signal count, time range and clock period of a waveform.

Arguments: `wave` (required), `indexed`, `clock`.

Starts a background job: no.

### `wave_list`

List waveform signal paths, widths, kinds and codes, optionally matching a regex.

Arguments: `wave` (required), `indexed`, `regex`.

Starts a background job: no.

### `wave_sample`

Read matching signal values at a wave time, cycle Nc, or end.

Arguments: `wave` (required), `indexed`, `regex` (required), `period`, `clock`, `at` (required), `dec`.

Starts a background job: no.

### `wave_seq`

Match a clocked sequence 'a ##1 b ##[1:3] c' (SVA-like delays, ##[n:$] open) at each rising clock edge where the first expression holds; returns matches, failures and pending starts.

Arguments: `wave` (required), `indexed`, `period`, `clock`, `t0`, `t1`, `sequence` (required), `limit`.

Starts a background job: no.

### `wave_txn`

Extract handshake transfers of a Stream (valid/ready) or Flow (valid) at rising clock edges: payload per transfer, wait cycles, stalls, payload_changed and valid_dropped issues. Give valid/ready/payload names, or stream (bundle path) with a design database.

Arguments: `wave` (required), `indexed`, `period`, `clock`, `t0`, `t1`, `valid`, `ready`, `payload`, `stream`, `db`, `limit`.

Starts a background job: no.

### `wave_why`

Explain why a signal has its value at a time: database assignments, which one was active (from condition signal values), values of the read signals, walking back through registers to their last change. Needs a SpinalDB database (db or RVW_DESIGNDB).

Arguments: `wave` (required), `period`, `clock`, `signal` (required), `at` (required), `db`, `depth`, `max_nodes`.

Starts a background job: no.

# Commercial features and issue map

The feature inventory defines comparison scope. It is a plan, not evidence of parity.
Exact issue body, checklist and comment import remains D27.c2 work before implementation.
Organisation clauses belong in [organisation.md](organisation.md). They are not tool gates.

## Commercial feature inventory

Every feature row is COVER unless its disposition is explicitly EXCLUDE. The omitted repeated COVER field expands before parsing.

Each feature record is ID | feature | owner, or ID | feature | EXCLUDE | reason. All COVER records inherit D27.c5 implementation, at least 50 positive/50 negative semantic controls and feature comparisons. D27.c6 closes only the whole relevant inventory conjunction. Intersections are strata, never the denominator. Whole-scope NI needs all endpoint gates; superiority also needs the fixed primary benefit and NI elsewhere. Full support keeps every named benefit cell. No per-feature superiority is implied.

Two independent enumerators reconcile version-pinned licensed manuals, options/apps, release notes, standards and task inventories under D27.c2/c6. Public catalogues do not certify completeness. Missing source access leaves scope OPEN. Compound features expand to every applicable clause. New relevant clauses become required, even when implementation is absent. RL24 governs frozen release intake. These are required comparator audit frames, not installed-capability qualification.

Stable IDs retain narrow exclusions: EX-PPA physical power/timing/area/frequency and analog leakage; EX-HW hardware emulation/FPGA; EX-CPU only the printed irrelevance reason. Owner exclusions cannot remove functional clock/reset/power-state control, digital isolation, real-number boundaries, software virtual platforms, logical faults, digital security or functional test-mode isolation. Candidate-only features remain independently tested.

### Inventory H01: VCS

|H01.001|Verilog/SystemVerilog RTL|D07.c1|
|H01.002|four-state resolution|D07.c1|
|H01.003|event-region race semantics|D07.c1|
|H01.004|timing delays and specify|D07.c1|
|H01.005|SystemVerilog classes and interfaces|D07.c1|
|H01.006|dynamic arrays queues and associative containers|D07.c1|
|H01.007|constrained random solving|D07.c1|
|H01.008|functional covergroups and crosses|D07.c1|
|H01.009|simulation assertions|D07.c1|
|H01.010|DPI C integration|D07.c1|
|H01.011|VPI callback integration|D07.c1|
|H01.012|SystemC co-simulation|D31.c6|
|H01.013|mixed VHDL simulation|D31.c5|
|H01.014|thread partitioning and multicore|D07.c3|
|H01.015|profile-guided compilation|D07.c3|
|H01.016|incremental compilation|D07.c3|
|H01.017|hierarchical compilation|D07.c3|
|H01.018|activity-aware execution|D07.c3|
|H01.019|live save restore|D08.c1|
|H01.020|deterministic replay|D08.c1|
|H01.021|selective/full visibility dumping|D07.c8|
|H01.022|full SV UVM unchanged benches|D13.c2|
|H01.023|protocol verification IP integration|D13.c2|
|H01.024|X-propagation analysis|D15.c2p3|
|H01.025|logical fault injection and safety campaigns|D28.c4|
|H01.026|code coverage|D14.c3|
|H01.027|assertion coverage|D14.c3|
|H01.028|coverage merge and exclusions|D14.c3|
|H01.029|scripted batch APIs|D26.c2|
|H01.030|externally supplied digital gate-netlist and SDF replay|D31.c3|
|H01.031|power estimation and physical power signoff|EXCLUDE|EX-PPA: power estimation and physical power signoff|
|H01.032|hardware emulation and FPGA acceleration|EXCLUDE|EX-HW: hardware emulation and FPGA acceleration|
|H01.033|functional power-state/isolation/retention control semantics|D37.c90|

### Inventory H02: Xcelium

|H02.001|SV/Verilog runtime|D07.c1|
|H02.002|VHDL runtime|D31.c4|
|H02.003|SystemC/TLM interoperability|D31.c6|
|H02.004|e-language testbench interoperability|D31.c1, D31.c2|
|H02.005|four-state resolution|D07.c1|
|H02.006|delay and event scheduling|D07.c1|
|H02.007|constraint solver|D07.c1|
|H02.008|assertions|D07.c1|
|H02.009|functional covergroups|D07.c1|
|H02.010|DPI/VPI/VHPI foreign interfaces|D07.c1, D31.c4, D31.c5|
|H02.011|full UVM benches|D13.c2|
|H02.012|verification IP integration|D13.c2|
|H02.013|multicore single-job simulation|D07.c3|
|H02.014|incremental and parallel build|D07.c3|
|H02.015|partition and profile optimization|D07.c3|
|H02.016|save restart and replay|D08.c1|
|H02.017|ML-assisted test compression and test selection|D14.c2|
|H02.018|code coverage|D14.c3|
|H02.019|functional/assertion coverage|D14.c3|
|H02.020|database merge and exclusions|D14.c3|
|H02.021|serial/concurrent logical fault simulation|D28.c4|
|H02.022|source/wave debug integration|D18.c1|
|H02.023|external digital netlist and timing annotation|D31.c3|
|H02.024|continuous analog circuit solving beyond declared digital or real-number boundary|EXCLUDE|EX-CPU: continuous analog circuit solving beyond declared digital or real-number boundary|
|H02.025|power estimation and physical signoff|EXCLUDE|EX-PPA: power estimation and physical signoff|
|H02.026|emulation and FPGA execution|EXCLUDE|EX-HW: emulation and FPGA execution|
|H02.027|functional power-state/isolation/retention control semantics|D37.c90|

### Inventory H03: JasperGold-apps

|H03.001|property verification and engine portfolio|D15.c4|
|H03.002|assume-guarantee abstraction|D15.c4|
|H03.003|bounded and unbounded safety|D15.c4|
|H03.004|liveness/fairness proof|D15.c4|
|H03.005|proof depth and capacity reporting|D15.c4|
|H03.006|static/conditional/temporal connectivity|D15.c2p1|
|H03.007|CSR spec import and behavior proof|D15.c2p2|
|H03.008|X propagation|D15.c2p3|
|H03.009|sequential equivalence|D15.c2p4|
|H03.010|hierarchical equivalence|D15.c2p4|
|H03.011|functional clock-enable equivalence|D15.c2p4|
|H03.012|stimuli/checker coverage|D15.c2p7|
|H03.013|COI and proof cores|D15.c2p7|
|H03.014|overconstraint detection|D15.c2p7|
|H03.015|mutation coverage|D15.c2p8|
|H03.016|coverage unreachability and exclusions|D15.c2p9|
|H03.017|Superlint and automatic structural properties|D15.c2p10|
|H03.018|C/C++ to RTL datapath validation|D15.c3, D15.c10|
|H03.019|integer/FP arithmetic proofs|D15.c3|
|H03.020|Visualize quiet CEX and what-if debug|D15.c8|
|H03.021|assertion synthesis|D15.c9|
|H03.022|proof grid and shared proof reuse|D15.c5|
|H03.023|simulation-seeded proof swarm|D15.c6|
|H03.024|security confidentiality|D34.c2|
|H03.025|security integrity|D34.c3|
|H03.026|logical safety fault analysis|D28.c4|
|H03.027|digital CDC/RDC app obligations|D37.c3|
|H03.028|AI formal planning and testbench authoring|D25.c7|
|H03.029|power estimation and physical power intent signoff|EXCLUDE|EX-PPA: power estimation and physical power intent signoff|
|H03.030|emulation and FPGA execution|EXCLUDE|EX-HW: emulation and FPGA execution|
|H03.031|manufacturing scan/DFT signoff beyond digital functional test-mode isolation|EXCLUDE|EX-CPU: manufacturing scan/DFT signoff beyond digital functional test-mode isolation|
|H03.032|functional power-state/isolation/retention control semantics|D37.c90|

### Inventory H04: VC-Formal-apps

|H04.001|FPV safety engine portfolio|D15.c4|
|H04.002|unbounded liveness|D15.c4|
|H04.003|abstraction and decomposition|D15.c4|
|H04.004|proof depth/capacity|D15.c4|
|H04.005|AEP automatic extracted checks|D15.c2p10|
|H04.006|FCA unreachable coverage|D15.c2p9|
|H04.007|FXP X source and propagation|D15.c2p3|
|H04.008|CC guarded connectivity|D15.c2p1|
|H04.009|FRV registers|D15.c2p2|
|H04.010|SEQ sequential equivalence|D15.c2p4|
|H04.011|FSV confidentiality|D34.c2|
|H04.012|FSV integrity|D34.c3|
|H04.013|FTA formal environment quality|D15.c2p7|
|H04.014|proof core and overconstraint checks|D15.c2p7|
|H04.015|DPV C/C++ transaction-level datapath equivalence|D15.c10|
|H04.016|RMA regression acceleration and grid|D15.c5|
|H04.017|property mining|D15.c9|
|H04.018|AIP protocol assertions|D13.c2, D17.c3, D37.c2|
|H04.019|FuSa logical fault analysis|D28.c4|
|H04.020|Verdi CEX and what-if debug|D15.c8|
|H04.021|from-simulation state exploration|D15.c6|
|H04.022|FLP physical low-power intent signoff and power estimation|EXCLUDE|EX-PPA: FLP physical low-power intent signoff and power estimation|
|H04.023|functional power-controller and isolation-state protocol checks|D37.c90|
|H04.024|emulation and FPGA execution|EXCLUDE|EX-HW: emulation and FPGA execution|

### Inventory H05: Verdi

|H05.001|FSDB/VCD waveform ingest|D18.c1|
|H05.002|typed four-state values|D18.c1|
|H05.003|source/hierarchy linking|D18.c1|
|H05.004|large-design database indexing|D18.c1|
|H05.005|driver/load tracing|D18.c2|
|H05.006|signal query|D18.c2|
|H05.007|event/time search|D18.c2|
|H05.008|schematic navigation|D18.c2|
|H05.009|memory/array inspection|D18.c2|
|H05.010|dynamic source causality and backward slicing|D19.c1, D18.c2|
|H05.011|transaction/protocol debug|D18.c5|
|H05.012|transaction-to-source joins|D18.c5|
|H05.013|performance transaction analysis|D18.c5|
|H05.014|assertion debug and failure browsing|D18.c9|
|H05.015|UVM class/object/sequence inspection|D18.c8|
|H05.016|root-cause ranking|D19.c1|
|H05.017|verified repair workflows|D19.c4|
|H05.018|checkpoint replay and intervention|D08.c1|
|H05.019|coverage hole/source inspection|D14.c3|
|H05.020|fault-result debug|D28.c4|
|H05.021|batch/scripting APIs|D25.c5|
|H05.022|headless query parity|D25.c5|
|H05.023|unified cross-tool workspace|D29.c5|
|H05.024|power estimation waveform analysis|EXCLUDE|EX-PPA: power estimation waveform analysis|
|H05.025|hardware emulator and FPGA debug|EXCLUDE|EX-HW: hardware emulator and FPGA debug|

### Inventory H06: vManager-IMC

|H06.001|verification plans and requirement links|D23.c1|
|H06.002|campaign scheduling|D23.c1|
|H06.003|run/seed/config identity|D23.c1|
|H06.004|result ingestion|D23.c1|
|H06.005|failure classification|D23.c1, D23.c5|
|H06.006|waivers and triage|D23.c1|
|H06.007|dashboards and history|D23.c1|
|H06.008|test selection|D23.c2|
|H06.009|flake diagnosis|D23.c2|
|H06.010|farm resource scheduling|D24.c6|
|H06.011|distributed orchestration|D24.c1|
|H06.012|worker failure recovery|D24.c1|
|H06.013|durable resume|D24.c1|
|H06.014|multi-user authorization and quotas|D24.c7|
|H06.015|code coverage merge|D14.c3|
|H06.016|functional coverage merge|D14.c3|
|H06.017|assertion coverage merge|D14.c3|
|H06.018|cross-run/config coverage semantics|D14.c3|
|H06.019|UCIS interchange|D14.c3|
|H06.020|coverage exclusion tracking|D14.c3|
|H06.021|formal unreachability integration|D15.c2p9|
|H06.022|verification closure analytics and expert workflow|D24.c5|
|H06.023|query/export/script APIs|D25.c5|
|H06.024|logical safety campaign result tracking|D28.c4|
|H06.025|physical power/synthesis signoff tracking|EXCLUDE|EX-PPA: physical power/synthesis signoff tracking|
|H06.026|emulator/FPGA farm jobs|EXCLUDE|EX-HW: emulator/FPGA farm jobs|
|H06.027|analog-only regression metrics beyond CPU digital contracts|EXCLUDE|EX-CPU: analog-only regression metrics beyond CPU digital contracts|

### Inventory H07: SpyGlass-CDC

|H07.001|clock-domain inference|D37.c1|
|H07.002|constraint generation and checking|D37.c1|
|H07.003|synchronizer recognition|D37.c1|
|H07.004|multibit/Gray crossings|D37.c1|
|H07.005|handshake protocols|D37.c1|
|H07.006|reconvergent paths|D37.c1|
|H07.007|FIFO crossings|D37.c1|
|H07.008|hierarchical abstract models|D37.c1|
|H07.009|reset-domain interactions|D37.c3|
|H07.010|waiver provenance and expiry|D37.c3|
|H07.011|path clustering and severity|D37.c3|
|H07.012|metastability digital injection|D37.c7|
|H07.013|functional protocol checking|D37.c7|
|H07.014|X optimism controls|D37.c7|
|H07.015|static lint and structural rules|D06.c2|
|H07.016|ML-assisted setup and triage|D25.c7|
|H07.017|physical timing closure|EXCLUDE|EX-PPA: physical timing closure|
|H07.018|analog metastability MTBF|EXCLUDE|EX-PPA: analog metastability MTBF|
|H07.019|physical low-power signoff|EXCLUDE|EX-PPA: physical low-power signoff|
|H07.020|functional isolation and clock-mode changes|D37.c90|
|H07.021|hardware emulation and FPGA execution|EXCLUDE|EX-HW: hardware emulation and FPGA execution|

### Inventory H08: Questa-CDC

|H08.001|clock/reset inference|D37.c1|
|H08.002|constraint correctness|D37.c1|
|H08.003|synchronizer classification|D37.c1|
|H08.004|multibit coherence|D37.c1|
|H08.005|reconvergence|D37.c1|
|H08.006|async FIFO protocols|D37.c1|
|H08.007|hierarchical crossing models|D37.c1|
|H08.008|blackbox crossing contracts|D37.c1|
|H08.009|reset crossing interactions|D37.c3|
|H08.010|waiver lifecycle|D37.c3|
|H08.011|crossing reports and source navigation|D37.c3|
|H08.012|metastability simulation injection|D37.c7|
|H08.013|formal crossing protocol checks|D37.c7|
|H08.014|perturbation coverage|D37.c7|
|H08.015|ML setup/constraint assistance|D25.c7|
|H08.016|physical CDC signoff and MTBF estimation|EXCLUDE|EX-PPA: physical CDC signoff and MTBF estimation|
|H08.017|functional power-state crossing behavior|D37.c90|
|H08.018|emulation and FPGA execution|EXCLUDE|EX-HW: emulation and FPGA execution|

### Inventory H09: Sigasi

|H09.001|SV/Verilog semantic parsing|D05.c1|
|H09.002|VHDL semantic parsing|D05.c1|
|H09.003|error-as-you-type|D05.c1|
|H09.004|type-aware completion|D05.c1|
|H09.005|definition/reference navigation|D05.c1|
|H09.006|hierarchy browsing|D05.c1|
|H09.007|live elaboration preview|D05.c5|
|H09.008|block/FSM diagrams|D05.c5|
|H09.009|hover/type inspection|D05.c5|
|H09.010|parameter browsing|D05.c5|
|H09.011|semantic highlighting|D05.c5|
|H09.012|project/build-file import|D05.c5|
|H09.013|safe rename/refactor|D06.c1|
|H09.014|formatting|D06.c1|
|H09.015|templates and snippets|D06.c1|
|H09.016|quick fixes|D06.c1|
|H09.017|documentation generation|D06.c1|
|H09.018|semantic design diff|D06.c1|
|H09.019|lint and custom rule checks|D06.c2|
|H09.020|UVM/OSVVM/UVVM/VUnit/cocotb authoring integration|D06.c10, D13.c2|
|H09.021|CLI/headless CI checks|D25.c5|
|H09.022|agent/LSP access|D25.c5|
|H09.023|VS Code project workflow|D29.c10|
|H09.024|UPF physical power signoff|EXCLUDE|EX-PPA: UPF physical power signoff|
|H09.025|FPGA board/prototype deployment|EXCLUDE|EX-HW: FPGA board/prototype deployment|

### Inventory H10: DVT

|H10.001|SV/VHDL semantic compile|D05.c1|
|H10.002|multi-language libraries|D05.c1|
|H10.003|preprocessor/include configuration|D05.c1|
|H10.004|type-aware completion|D05.c1|
|H10.005|definition/reference navigation|D05.c1|
|H10.006|class/module hierarchy|D05.c1|
|H10.007|UVM class/sequence diagrams|D05.c5|
|H10.008|design hierarchy/schematic|D05.c5|
|H10.009|constraint inspection|D05.c5|
|H10.010|PSS/e-language authoring|D05.c5|
|H10.011|parameter and macro expansion|D05.c5|
|H10.012|safe rename/refactor|D06.c1|
|H10.013|quick fixes|D06.c1|
|H10.014|format/style rules|D06.c1|
|H10.015|documentation|D06.c1|
|H10.016|code generation templates|D06.c1|
|H10.017|semantic structural diff|D06.c1|
|H10.018|lint integration|D06.c2|
|H10.019|headless batch analysis|D25.c5|
|H10.020|tool launch/debug integration|D25.c5|
|H10.021|agent API access|D25.c5|
|H10.022|VS Code/Eclipse-equivalent workbench task support|D29.c10|
|H10.023|UPF/CPF physical power intent signoff|EXCLUDE|EX-PPA: UPF/CPF physical power intent signoff|
|H10.024|FPGA/emulator deployment|EXCLUDE|EX-HW: FPGA/emulator deployment|

### Inventory H11: Breker

|H11.001|PSS DSL model|D14.c7|
|H11.002|PSS C++ model|D14.c7|
|H11.003|graph/action composition|D14.c7|
|H11.004|constraint resolution|D14.c7|
|H11.005|resource/pool scheduling|D14.c7|
|H11.006|data/state flow|D14.c7|
|H11.007|concurrent activity scheduling|D14.c7|
|H11.008|scenario coverage|D14.c7|
|H11.009|C test realization|D14.c7|
|H11.010|SV/UVM realization|D14.c7|
|H11.011|multicore synchronized tests|D14.c7|
|H11.012|HSI memory map/BFM services|D14.c7|
|H11.013|expected results generation|D14.c7|
|H11.014|runtime scenario visualization|D14.c7|
|H11.015|coverage-directed generation|D14.c2|
|H11.016|test synthesis amplification|D14.c2|
|H11.017|coherency SystemVIP scenarios|D17.c3|
|H11.018|memory ordering scenarios|D17.c2|
|H11.019|RISC-V ISA scenario obligations|D10.c1p1, D10.c1p2, D10.c1p3, D10.c1p4, D10.c1p5, D10.c1p6, D10.c1p7, D10.c1p8, D10.c1p9, D10.c1p10, D10.c1p11, D10.c1p12, D10.c1p13, D10.c1p14, D10.c1p15, D10.c1p16, D10.c1p17, D10.c1p18, D10.c1p19, D10.c1p20|
|H11.020|system security scenarios|D34.c3|
|H11.021|cross-unit interaction coverage|D14.c6|
|H11.022|TrekSoC-Si emulation and FPGA execution|EXCLUDE|EX-HW: TrekSoC-Si emulation and FPGA execution|
|H11.023|post-fabrication production test services|EXCLUDE|EX-CPU: post-fabrication production test services|

### Inventory H12: STING

|H12.001|bare-metal test generation|D14.c2|
|H12.002|directed/random instruction streams|D14.c2|
|H12.003|portable runtime generation|D14.c2|
|H12.004|ISA/extension coverage|D10.c1p1, D10.c1p2, D10.c1p3, D10.c1p4, D10.c1p5, D10.c1p6, D10.c1p7, D10.c1p8, D10.c1p9, D10.c1p10, D10.c1p11, D10.c1p12, D10.c1p13, D10.c1p14, D10.c1p15, D10.c1p16, D10.c1p17, D10.c1p18, D10.c1p19, D10.c1p20|
|H12.005|privilege/trap scenarios|D10.c1p1, D10.c1p2, D10.c1p3, D10.c1p4, D10.c1p5, D10.c1p6, D10.c1p7, D10.c1p8, D10.c1p9, D10.c1p10, D10.c1p11, D10.c1p12, D10.c1p13, D10.c1p14, D10.c1p15, D10.c1p16, D10.c1p17, D10.c1p18, D10.c1p19, D10.c1p20|
|H12.006|FP/vector scenarios|D10.c1p1, D10.c1p2, D10.c1p3, D10.c1p4, D10.c1p5, D10.c1p6, D10.c1p7, D10.c1p8, D10.c1p9, D10.c1p10, D10.c1p11, D10.c1p12, D10.c1p13, D10.c1p14, D10.c1p15, D10.c1p16, D10.c1p17, D10.c1p18, D10.c1p19, D10.c1p20|
|H12.007|multihart concurrency|D12.c1|
|H12.008|cache/coherence stimulus|D12.c1|
|H12.009|MMU/PMP/interrupt scenarios|D10.c90|
|H12.010|SoC interface/device interactions|D12.c1, D21.c1, D37.c2|
|H12.011|coverage feedback and reporting|D14.c3|
|H12.012|reference-model self-check and comparison|D11.c6|
|H12.013|repeatable configurable campaigns|D14.c5|
|H12.014|debug/replay of failures|D14.c5, D08.c1, D18.c3|
|H12.015|emulation/FPGA test execution|EXCLUDE|EX-HW: emulation/FPGA test execution|
|H12.016|portable tests and result capture on existing silicon targets|D30.c7|

### Inventory H13: JasperGold-SPV

|H13.001|confidentiality information flow|D34.c2|
|H13.002|allowed declassification|D34.c2|
|H13.003|relational noninterference|D34.c2|
|H13.004|secret/public path constraints|D34.c2|
|H13.005|protected-state integrity|D34.c3|
|H13.006|privilege/access boundaries|D34.c3|
|H13.007|transient/timing observations|D33.c1|
|H13.008|security rule authoring and comparison|D33.c2|
|H13.009|counterexample security debug|D33.c2|
|H13.010|hierarchical policy composition|D33.c2|
|H13.011|security assumption/nonvacuity coverage|D15.c2p7|
|H13.012|software security contract export|D34.c4|
|H13.013|physical power/EM leakage|EXCLUDE|OWNER-DEFERRED: physical power and EM leakage, owner decision 2026-11-04|
|H13.014|emulator/FPGA execution|EXCLUDE|EX-HW: emulator/FPGA execution|

### Inventory H14: Radix

|H14.001|information-flow instrumentation|D33.c3|
|H14.002|tag propagation|D33.c3|
|H14.003|security policy specification|D33.c3|
|H14.004|simulation security assertions|D33.c3|
|H14.005|source-to-sink path visualization|D33.c3|
|H14.006|formal confidentiality and declassification|D34.c2|
|H14.007|integrity rules and access control|D34.c3|
|H14.008|hierarchical security debug|D33.c2|
|H14.009|coverage and violation reporting|D33.c2|
|H14.010|composed system policies|D33.c2|
|H14.011|software-consumable security assumptions|D34.c4|
|H14.012|physical power/EM/toggle power-proxy leakage|EXCLUDE|OWNER-DEFERRED: physical power, EM and toggle power-proxy leakage, owner decision 2026-11-04|
|H14.013|hardware emulation/FPGA execution|EXCLUDE|EX-HW: hardware emulation/FPGA execution|

### Inventory H15: Platform-Architect

|H15.001|SystemC/TLM component models|D01.c2|
|H15.002|processor traffic models|D01.c2|
|H15.003|memory/interconnect topology|D01.c2|
|H15.004|cache coherence models|D01.c2|
|H15.005|contention and arbitration|D01.c8|
|H15.006|latency/bandwidth models|D01.c8|
|H15.007|DRAM service models|D01.c8|
|H15.008|chiplet-link digital transaction timing|D01.c8|
|H15.009|manycore performance models|D01.c3b|
|H15.010|trace-driven calibration|D02.c1|
|H15.011|uncertainty propagation|D02.c1|
|H15.012|architecture parameter sweeps|D35.c3|
|H15.013|hardware/software mapping|D35.c3|
|H15.014|design-space optimization|D35.c3|
|H15.015|transaction trace analysis|D18.c5|
|H15.016|automated model APIs|D25.c5|
|H15.017|power/area/frequency optimization|EXCLUDE|EX-PPA: power/area/frequency optimization|
|H15.018|physical multi-die analysis|EXCLUDE|EX-PPA: physical multi-die analysis|
|H15.019|hardware emulation/FPGA platforms|EXCLUDE|EX-HW: hardware emulation/FPGA platforms|

### Inventory H16: Fast-Models

|H16.001|functional programmer-view execution|D01.c2|
|H16.002|extensible CPU/system components|D01.c2|
|H16.003|SystemC/TLM export|D01.c2|
|H16.004|OS/firmware/driver bring-up|D01.c2|
|H16.005|virtual peripherals and memory|D01.c2|
|H16.006|debugger connection|D18.c10, D11.c5|
|H16.007|register/memory inspection|D18.c10, D11.c5|
|H16.008|checkpoint/replay|D08.c1|
|H16.009|automated CI/farm deployment|D24.c1|
|H16.010|scriptable model control|D25.c5|
|H16.011|cross-ISA useful-work validation|D36.c3|
|H16.012|Arm proprietary instruction semantics as a RISC-V compliance target|EXCLUDE|EX-CPU: Arm proprietary instruction semantics as a RISC-V compliance target|
|H16.013|Arm-specific proprietary IP implementation|EXCLUDE|EX-CPU: Arm-specific proprietary IP implementation|
|H16.014|physical power models|EXCLUDE|EX-PPA: physical power models|
|H16.015|hardware-assisted emulation and FPGA execution|EXCLUDE|EX-HW: hardware-assisted emulation and FPGA execution|

### Inventory H17: Imperas-DV

|H17.001|configurable RISC-V reference model|D11.c6|
|H17.002|retirement lockstep|D11.c6|
|H17.003|asynchronous events|D11.c6|
|H17.004|first-divergence debug|D11.c6|
|H17.005|reference integration APIs|D11.c6|
|H17.006|ISA versions and profiles|D10.c1p1, D10.c1p2, D10.c1p3, D10.c1p4, D10.c1p5, D10.c1p6, D10.c1p7, D10.c1p8, D10.c1p9, D10.c1p10, D10.c1p11, D10.c1p12, D10.c1p13, D10.c1p14, D10.c1p15, D10.c1p16, D10.c1p17, D10.c1p18, D10.c1p19, D10.c1p20|
|H17.007|scalar/FP/vector/extensions|D10.c1p1, D10.c1p2, D10.c1p3, D10.c1p4, D10.c1p5, D10.c1p6, D10.c1p7, D10.c1p8, D10.c1p9, D10.c1p10, D10.c1p11, D10.c1p12, D10.c1p13, D10.c1p14, D10.c1p15, D10.c1p16, D10.c1p17, D10.c1p18, D10.c1p19, D10.c1p20|
|H17.008|privileged/hypervisor behavior|D10.c1p1, D10.c1p2, D10.c1p3, D10.c1p4, D10.c1p5, D10.c1p6, D10.c1p7, D10.c1p8, D10.c1p9, D10.c1p10, D10.c1p11, D10.c1p12, D10.c1p13, D10.c1p14, D10.c1p15, D10.c1p16, D10.c1p17, D10.c1p18, D10.c1p19, D10.c1p20|
|H17.009|MMU/PMP/interrupt behavior|D10.c90|
|H17.010|custom instruction model authoring|D11.c7|
|H17.011|multihart model observations|D12.c1|
|H17.012|test/stimulus integration|D14.c2|
|H17.013|architectural functional coverage|D14.c3|
|H17.014|instruction/state trace debug|D18.c1, D18.c10, D11.c5|
|H17.015|model qualification and independent reference cross-check|D28.c1|
|H17.016|ZeBu/HAPS emulation and FPGA execution|EXCLUDE|EX-HW: ZeBu/HAPS emulation and FPGA execution|
|H17.017|non-RISC-V ISA catalogue as a RISC-V compliance requirement|EXCLUDE|EX-CPU: non-RISC-V ISA catalogue as a RISC-V compliance requirement|

Primary vendor source links. Exact qualified versions remain execution manifest fields:

- [VCS feature source](https://www.synopsys.com/verification/simulation/vcs.html).
- [Xcelium feature source](https://www.cadence.com/en_US/%68ome/tools/system-design-and-verification/simulation-and-testbench-verification/xcelium-simulator.html).
- [JasperGold-apps feature source](https://www.cadence.com/en_US/%68ome/tools/system-design-and-verification/formal-and-static-verification/jasper-core-formal-apps.html).
- [VC-Formal-apps feature source](https://www.synopsys.com/verification/static-and-formal-verification/vc-formal.html).
- [Verdi feature source](https://www.synopsys.com/verification/debug/verdi.html).
- [vManager-IMC feature source](https://login.cadence.com/content/cadence-www/global/en_US/%68ome/resources/datasheets/vmanager-ds.html).
- [SpyGlass-CDC feature source](https://www.synopsys.com/verification/static-and-formal-verification/vc-spyglass/vc-spyglass-cdc.html).
- [Questa-CDC feature source](https://static.sw.cdn.siemens.com/siemens-disw-assets/public/78487/en-US/Siemens-SW-Questa-Clock-Domain-Crossing-FS-78487-C3.pdf).
- [Sigasi feature source](https://www.sigasi.com/).
- [DVT feature source](https://eda.amiq.com/products/dvt-ide).
- [Breker feature source](https://brekersystems.com/products/).
- [STING feature source](https://www.synopsys.com/verification/sting.html).
- [JasperGold-SPV feature source](https://www.cadence.com/en_US/%68ome/tools/system-design-and-verification/formal-and-static-verification.html).
- [Radix feature source](https://www.cadence.com/content/dam/cadence-www/global/en_US/documents/solutions/aerospace-and-defense/aerospace-and-defense-security-wp.pdf).
- [Platform-Architect feature source](https://www.synopsys.com/verification/virtual-prototyping/platform-architect.html).
- [Fast-Models feature source](https://www.arm.com/products/development-tools/simulation/fast-models).
- [Imperas-DV feature source](https://www.synopsys.com/verification/imperasdv.html).

Additional counter-method sources: [Apple CPU counter architecture](https://github.com/apple-oss-distributions/xnu/blob/main/doc/observability/cpu_counters.md), [Apple Instruments CPU Counters](https://developer.apple.com/documentation/xcode/addressing-cpu-bottlenecks). D36.c4 qualifies actual interface on each OS/CPU; these sources are not measurement receipts.

Implementation note: reuse current native result/import/engine modules first. D27.c5 extends their runtime, solver, debug or API boundaries per feature; it is not report-only coverage exercise. Candidate/vendor build recipes, semantic witnesses, independent checkers and full task outputs are deliverables.

New cells inherit owning category's accountable owner/checker, size XL, priority P0 and issue NEW unless issue is printed. This includes full vendor features, language stages, compiler security and whole-scope claim audits. Feature discovery is not discretionary later scope choice.

### Inventory H18: Questa-Processor-OneSpin

|H18.001|ISA state and instruction refinement|D09.c2, D16.c4|
|H18.002|privilege traps interrupts and CSR proof|D09.c2, D16.c4|
|H18.003|RVV and extension proof configuration|D10.c1p1, D10.c1p2, D10.c1p3, D10.c1p4, D10.c1p5, D10.c1p6, D10.c1p7, D10.c1p8, D10.c1p9, D10.c1p10, D10.c1p11, D10.c1p12, D10.c1p13, D10.c1p14, D10.c1p15, D10.c1p16, D16.c4|
|H18.004|pipeline memory abstraction and composition|D16.c3, D16.c4|
|H18.005|proof debug coverage and vacuity|D15.c4, D16.c4|

### Inventory H19: Axiomise-formalISA

|H19.001|instruction and architectural state proof|D09.c2, D16.c4|
|H19.002|privileged ISA exception and memory semantics|D09.c2, D16.c4|
|H19.003|custom extension proof and configuration|D10.c1p1, D10.c1p2, D10.c1p3, D10.c1p4, D10.c1p5, D10.c1p6, D10.c1p7, D10.c1p8, D10.c1p9, D10.c1p10, D10.c1p11, D10.c1p12, D10.c1p13, D10.c1p14, D10.c1p15, D10.c1p16, D16.c4|
|H19.004|proof completeness vacuity and debug|D15.c4, D16.c4|

### Inventory H20: VSO.ai

|H20.001|AI regression and stimulus selection|D14.c5, D23.c2|
|H20.002|coverage prediction closure and unreachable holes|D14.c5|
|H20.003|feature extraction training drift and cold start|D14.c5|
|H20.004|campaign orchestration reproducibility and cost|D14.c5, D24.c5|

### Inventory H21: Verisium

|H21.001|AI coverage closure and test ranking|D14.c5|
|H21.002|failure classification and root cause|D23.c5, D19.c1|
|H21.003|cross-run data management and campaign orchestration|D24.c5|
|H21.004|model drift provenance and human override|D14.c5, D24.c5|

### Inventory H22: Verisium-Debug

|H22.001|source wave pipeline and transaction joins|D18.c1|
|H22.002|causal and cross-run diagnosis|D19.c1, D19.c4|
|H22.003|X-origin and assertion debug|D18.c4, D18.c9|
|H22.004|large-trace search and indexing|D18.c2|
|H22.005|repair and replay workflow|D19.c4|

### Inventory H23: SimVision

|H23.001|mixed-language source wave and transaction debug|D18.c1|
|H23.002|assertion X and driver diagnosis|D18.c4, D18.c9|
|H23.003|trace indexing and temporal search|D18.c2|

### Inventory H24: VC-Execution-Manager

|H24.001|campaign scheduling monitoring and recovery|D24.c1, D24.c6|
|H24.002|coverage-driven resource and test planning|D24.c5|

### Inventory H25: Verdi-Planner

|H25.001|verification plan requirement and coverage linkage|D23.c1, D23.c3, D24.c2|
|H25.002|closure prioritization and campaign decisions|D24.c5|

ISA feature mapping: H11.019, H12.004-006 and H17.006-008 also cover D10.c1p17, D10.c1p18, D10.c1p19 and D10.c1p20. Expand these IDs as typed whole-feature children; no crypto, bit manipulation or floating-point extension may close by the earlier sixteen-family subset.

### Commercial agent pin register

The product names below come from official vendor sources. These pins identify published product generations, not executable build versions. Exact licensed build IDs are not published in these sources. No executable version is invented here. Before any comparison, freeze the installed product release, build ID, binary SHA-256, agent service revision, model revision, backend EDA build, prompt and skill hashes, date and feature manifest under R08. A missing field blocks that comparison. A changed service revision requires new confirmation. Current executable pin status for all three entries is OPEN. This is the version-pinning contract, not a completed licensed benchmark.

|Product|Published generation pin|Source|
|---|---|---|
|Cadence ChipStack AI Super Agent|Launch generation dated 2026-02-10|[Cadence launch](https://www.cadence.com/en_US/%68ome/company/newsroom/press-releases/pr/2026/cadence-unleashes-chipstack-ai-super-agent-pioneering-a-new.html.html)|
|Synopsys AgentEngineer solutions on the Synopsys Autopilot Platform|Announcement generation dated 2026-09-28|[Synopsys announcement](https://news.synopsys.com/2026-09-28-Synopsys-Powers-Autonomous-Engineering-with-a-Broad-Portfolio-of-Long-Horizon-Agents-and-Autopilot-Platform)|
|Synopsys.ai Copilot|Expanded capability generation dated 2025-09-03|[Synopsys announcement](https://news.synopsys.com/2025-09-03-Synopsys-Announces-Expanding-AI-Capabilities-for-its-Leading-EDA-Solutions)|

Only digital design and verification tasks are admitted to these comparisons. Product scope outside the owner remit cannot add obligations. JedAI is an AI data platform and is not silently treated as an autonomous agent. Verisium selection remains a distinct comparator from ChipStack agent workflows.
### Inventory H26: ChipStack-agent


| H26.001 | Cadence ChipStack AI Super Agent engineering workflows |D25.c3a, D25.c6, D25.c10|
### Inventory H27: AgentEngineer


| H27.001 | Synopsys AgentEngineer solutions and Synopsys Autopilot Platform workflows |D25.c3a, D25.c6, D25.c10|
### Inventory H28: Copilot


| H28.001 | Synopsys.ai Copilot assistant workflows |D25.c3a, D25.c6, D25.c10|

All 405 feature rows require a semantic subject witness before validated import. Licensed-manual enumeration and independent semantic checks remain required. MX24 must reject reverse-execution latency as evidence for failure bucketing or causal diagnosis.

H05.010 requires causality. H17.014 requires architectural trace views. H11.018 requires RVWMO. H06.005 includes failure bucketing. H12.014 includes replay evidence. H21.002 requires causal root evidence, not classification alone. Apply independent wrong-subject controls to every listed mapping.




## Issue ownership

Each open issue has one milestone owner. Select the milestone where the main tool deliverable is accepted. A source-specific issue ledger is an intake obligation, not the final delivery gate. The additional cells below identify the main acceptance work. Keep their phases unchanged.
An owner closes the in-scope tool work or records an explicit owner deferral.
GUI clauses in mixed issues are optional. Issues #23 and #51 are owner deferrals only. Issues #37 and #39 are organisation tasks only. M7 tracks their disposition without making them release capability gates.
This is the frozen issue-ownership ledger from 2026-11-04. Live issue state was checked on 2026-11-17.
TODO.md lists all 213 live issues and their delivery status. Closed issue scope remains a regression duty in the cells.
Issues #722 and #723 are later additions. Their milestone and acceptance-cell assignments require an owner decision.

| Issue | Milestone | Acceptance cells or disposition |
|---|---|---|
| [#1](https://github.com/riscPrint/risc-v-workstation/issues/1) Integrate risc-v-workstation with BOOM | M1 | [D27.c90](acceptance.md#D27c90) |
| [#5](https://github.com/riscPrint/risc-v-workstation/issues/5) Triage the 24 SpinalChecks firings on BOOM | M2 | [D17.c90](acceptance.md#D17c90) |
| [#8](https://github.com/riscPrint/risc-v-workstation/issues/8) Generic gap: Spike platform fixes privilege modes and misaligned-access policy | M2 | [D11.c90](acceptance.md#D11c90) |
| [#10](https://github.com/riscPrint/risc-v-workstation/issues/10) Cosim: compare FP registers and `fflags` | M2 | [D11.c90](acceptance.md#D11c90) |
| [#11](https://github.com/riscPrint/risc-v-workstation/issues/11) Cosim: per-core settings for absent PMP CSRs and `mtval` on `ecall` | M2 | [D11.c90](acceptance.md#D11c90) |
| [#14](https://github.com/riscPrint/risc-v-workstation/issues/14) Speed: persistent simulation server | M4 | [D07.c90](acceptance.md#D07c90) |
| [#15](https://github.com/riscPrint/risc-v-workstation/issues/15) Owner decisions from the simplicity audit | M1 | [D27.c90](acceptance.md#D27c90) |
| [#16](https://github.com/riscPrint/risc-v-workstation/issues/16) CI: GitHub Actions | M4 | [D23.c90](acceptance.md#D23c90) |
| [#17](https://github.com/riscPrint/risc-v-workstation/issues/17) Installer: full Linux installs with --with-riscv-gcc, --with-cosim, --with-formal, --with-gem5 and --all | M2 | [D29.c90](acceptance.md#D29c90) |
| [#18](https://github.com/riscPrint/risc-v-workstation/issues/18) Formal: sequential equivalence | M3 | [D15.c90](acceptance.md#D15c90) |
| [#19](https://github.com/riscPrint/risc-v-workstation/issues/19) Formal: datapath checking against a C model | M3 | [D15.c90](acceptance.md#D15c90) |
| [#20](https://github.com/riscPrint/risc-v-workstation/issues/20) Formal: security and information flow | M3 | [D15.c90](acceptance.md#D15c90) |
| [#21](https://github.com/riscPrint/risc-v-workstation/issues/21) Formal: deeper proofs | M3 | [D15.c90](acceptance.md#D15c90) |
| [#22](https://github.com/riscPrint/risc-v-workstation/issues/22) Lint and clock-domain crossing | M4 | [D37.c90](acceptance.md#D37c90), [D37.c7](acceptance.md#D37c7) |
| [#23](https://github.com/riscPrint/risc-v-workstation/issues/23) Emulation and FPGA prototyping | M7 | Owner deferral; no tool acceptance gate |
| [#24](https://github.com/riscPrint/risc-v-workstation/issues/24) Integrated debug GUI and VS Code panels | M5 | [D05.c90](acceptance.md#D05c90), [D06.c4](acceptance.md#D06c4) |
| [#25](https://github.com/riscPrint/risc-v-workstation/issues/25) Regression farm and web dashboard | M6 | [D23.c1](acceptance.md#D23c1), [D23.c2](acceptance.md#D23c2), [D23.c3](acceptance.md#D23c3), [D23.c4](acceptance.md#D23c4), [D24.c1](acceptance.md#D24c1) |
| [#26](https://github.com/riscPrint/risc-v-workstation/issues/26) Non-Spinal cores | M3 | [D05.c90](acceptance.md#D05c90), [D30.c3](acceptance.md#D30c3) |
| [#27](https://github.com/riscPrint/risc-v-workstation/issues/27) Idea: agent bug-fix loop | M5 | [D19.c90](acceptance.md#D19c90), [D19.c2](acceptance.md#D19c2) |
| [#28](https://github.com/riscPrint/risc-v-workstation/issues/28) Idea: self-explaining design diff | M4 | [D06.c90](acceptance.md#D06c90) |
| [#29](https://github.com/riscPrint/risc-v-workstation/issues/29) Idea: spec-to-test generation from Sail | M2 | [D14.c90](acceptance.md#D14c90) |
| [#31](https://github.com/riscPrint/risc-v-workstation/issues/31) Idea: continuous model calibration | M3 | [D35.c90](acceptance.md#D35c90) |
| [#32](https://github.com/riscPrint/risc-v-workstation/issues/32) Idea: bug-pattern memory | M4 | [D19.c90](acceptance.md#D19c90) |
| [#33](https://github.com/riscPrint/risc-v-workstation/issues/33) Idea: random instruction streams with cosim | M2 | [D14.c90](acceptance.md#D14c90) |
| [#34](https://github.com/riscPrint/risc-v-workstation/issues/34) Integration model: how core projects install and use the workstation | M1 | [D27.c90](acceptance.md#D27c90) |
| [#35](https://github.com/riscPrint/risc-v-workstation/issues/35) `rvw doctor`: check (and optionally install) the setup | M3 | [D29.c90](acceptance.md#D29c90), [D29.c9](acceptance.md#D29c9) |
| [#37](https://github.com/riscPrint/risc-v-workstation/issues/37) Choose a license | M7 | Owner task in [organisation.md](organisation.md); no tool acceptance gate |
| [#38](https://github.com/riscPrint/risc-v-workstation/issues/38) Community files: CONTRIBUTING, SECURITY, issue and PR templates | M3 | [D32.c90](acceptance.md#D32c90) |
| [#39](https://github.com/riscPrint/risc-v-workstation/issues/39) Ask GitHub Support to purge cached old commits | M7 | Owner task in [organisation.md](organisation.md); no tool acceptance gate |
| [#40](https://github.com/riscPrint/risc-v-workstation/issues/40) Reproducible installs: Python lock file and tested tool versions | M2 | [D29.c90](acceptance.md#D29c90) |
| [#41](https://github.com/riscPrint/risc-v-workstation/issues/41) Fast and slow test sets for CI | M4 | [D23.c90](acceptance.md#D23c90) |
| [#42](https://github.com/riscPrint/risc-v-workstation/issues/42) Coverage: FSM coverage and Scala line mapping | M2 | [D14.c90](acceptance.md#D14c90) |
| [#43](https://github.com/riscPrint/risc-v-workstation/issues/43) SpinalWaves needs a forked Surfer | M2 | [D18.c90](acceptance.md#D18c90) |
| [#45](https://github.com/riscPrint/risc-v-workstation/issues/45) Run `rvw bisect` on real core history | M4 | [D19.c90](acceptance.md#D19c90) |
| [#46](https://github.com/riscPrint/risc-v-workstation/issues/46) Formal: multi-clock designs and asynchronous resets | M4 | [D37.c90](acceptance.md#D37c90), [D37.c7](acceptance.md#D37c7) |
| [#48](https://github.com/riscPrint/risc-v-workstation/issues/48) More test sources through RiscvSim: ACT4, riscv-dv, TestRIG | M2 | [D09.c90](acceptance.md#D09c90) |
| [#49](https://github.com/riscPrint/risc-v-workstation/issues/49) Konata: stall causes and predicated-off commits | M2 | [D03.c90](acceptance.md#D03c90) |
| [#51](https://github.com/riscPrint/risc-v-workstation/issues/51) PPA estimates: synthesis, timing, area and power | M7 | Owner deferral; no tool acceptance gate |
| [#52](https://github.com/riscPrint/risc-v-workstation/issues/52) Fault injection for functional safety | M1 | [D28.c90](acceptance.md#D28c90) |
| [#54](https://github.com/riscPrint/risc-v-workstation/issues/54) Remote MCP server with authentication | M2 | [D25.c90](acceptance.md#D25c90) |
| [#55](https://github.com/riscPrint/risc-v-workstation/issues/55) SystemVerilog and Verilog cores: design queries | M2 | [D05.c90](acceptance.md#D05c90) |
| [#57](https://github.com/riscPrint/risc-v-workstation/issues/57) Agent run budgets and cost reports | M4 | [D23.c90](acceptance.md#D23c90) |
| [#58](https://github.com/riscPrint/risc-v-workstation/issues/58) Documentation site | M3 | [D29.c90](acceptance.md#D29c90), [D29.c7](acceptance.md#D29c7) |
| [#59](https://github.com/riscPrint/risc-v-workstation/issues/59) Run jobs on Kubernetes for scale tests | M6 | [D23.c90](acceptance.md#D23c90) |
| [#60](https://github.com/riscPrint/risc-v-workstation/issues/60) Formal: counterexample debugging (FV 8) | M3 | [D15.c90](acceptance.md#D15c90) |
| [#61](https://github.com/riscPrint/risc-v-workstation/issues/61) Formal: full SVA and a SymbiYosys regression runner (FV 9) | M3 | [D15.c90](acceptance.md#D15c90) |
| [#62](https://github.com/riscPrint/risc-v-workstation/issues/62) Formal: proof-core and cone-of-influence reports (FV 6) | M3 | [D14.c90](acceptance.md#D14c90), [D15.c7p7](acceptance.md#D15c7p7) |
| [#63](https://github.com/riscPrint/risc-v-workstation/issues/63) Formal: generic riscv-formal harness | M3 | [D15.c90](acceptance.md#D15c90) |
| [#64](https://github.com/riscPrint/risc-v-workstation/issues/64) Formal: riscv-formal checks generated from Sail | M2 | [D09.c90](acceptance.md#D09c90) |
| [#65](https://github.com/riscPrint/risc-v-workstation/issues/65) SpinalChecks: more check rules | M2 | [D17.c90](acceptance.md#D17c90) |
| [#66](https://github.com/riscPrint/risc-v-workstation/issues/66) SpinalChecks: TileLink and AXI protocol checks | M2 | [D17.c90](acceptance.md#D17c90) |
| [#70](https://github.com/riscPrint/risc-v-workstation/issues/70) SpinalBlocks and SpinalDB: check on more designs | M2 | [D05.c90](acceptance.md#D05c90) |
| [#71](https://github.com/riscPrint/risc-v-workstation/issues/71) Native tool bundle: pinned binaries per OS | M4 | [D23.c90](acceptance.md#D23c90) |
| [#72](https://github.com/riscPrint/risc-v-workstation/issues/72) gem5: model features for wide cores | M3 | [D01.c90](acceptance.md#D01c90) |
| [#74](https://github.com/riscPrint/risc-v-workstation/issues/74) Simulation: measure and cut Verilator build and run times for large configs | M5 | [D06.c90](acceptance.md#D06c90), [D07.c5](acceptance.md#D07c5) |
| [#75](https://github.com/riscPrint/risc-v-workstation/issues/75) Verification: riscv-vector-tests | M2 | [D09.c90](acceptance.md#D09c90) |
| [#76](https://github.com/riscPrint/risc-v-workstation/issues/76) Cleanup: drop the generic input_commands fields | M1 | [D27.c90](acceptance.md#D27c90) |
| [#77](https://github.com/riscPrint/risc-v-workstation/issues/77) Decide what the IDE needs beyond VS Code and Metals | M2 | [D05.c90](acceptance.md#D05c90) |
| [#78](https://github.com/riscPrint/risc-v-workstation/issues/78) chore(release): define the public release checklist | M3 | [D32.c90](acceptance.md#D32c90) Tool checklist only; publication, licences and external decisions are owner tasks in [organisation.md](organisation.md). |
| [#79](https://github.com/riscPrint/risc-v-workstation/issues/79) test(release): scan credentials and publication metadata | M1 | [D27.c90](acceptance.md#D27c90) |
| [#80](https://github.com/riscPrint/risc-v-workstation/issues/80) feat(platform): track implemented isa versions and options | M2 | [D09.c90](acceptance.md#D09c90) |
| [#82](https://github.com/riscPrint/risc-v-workstation/issues/82) feat(cov): generate expected isa coverage bins | M2 | [D09.c90](acceptance.md#D09c90) |
| [#83](https://github.com/riscPrint/risc-v-workstation/issues/83) test(waves): validate interactive typed rendering | M2 | [D05.c90](acceptance.md#D05c90) |
| [#84](https://github.com/riscPrint/risc-v-workstation/issues/84) feat(sim): verify sv39 translation behavior | M2 | [D09.c90](acceptance.md#D09c90) |
| [#85](https://github.com/riscPrint/risc-v-workstation/issues/85) feat(checks): generate csr behavior verification | M2 | [D09.c90](acceptance.md#D09c90) |
| [#87](https://github.com/riscPrint/risc-v-workstation/issues/87) feat(cosim): check unread architectural csr effects | M2 | [D11.c90](acceptance.md#D11c90) |
| [#90](https://github.com/riscPrint/risc-v-workstation/issues/90) feat(sim): define multi-hart run and trace contracts | M2 | [D12.c90](acceptance.md#D12c90) |
| [#91](https://github.com/riscPrint/risc-v-workstation/issues/91) feat(sim): verify lr/sc reservations and progress | M2 | [D17.c90](acceptance.md#D17c90) |
| [#93](https://github.com/riscPrint/risc-v-workstation/issues/93) feat(cosim): define faulting memory access records | M2 | [D11.c90](acceptance.md#D11c90) |
| [#95](https://github.com/riscPrint/risc-v-workstation/issues/95) feat(platform): query verdict evidence across all tools | M2 | [D25.c90](acceptance.md#D25c90) |
| [#96](https://github.com/riscPrint/risc-v-workstation/issues/96) feat(cosim): check rvwmo litmus outcomes | M2 | [D17.c90](acceptance.md#D17c90) |
| [#97](https://github.com/riscPrint/risc-v-workstation/issues/97) feat(sim): verify amo atomicity and ordering | M2 | [D17.c90](acceptance.md#D17c90) |
| [#98](https://github.com/riscPrint/risc-v-workstation/issues/98) feat(checks): verify zihpm counter behavior | M2 | [D03.c90](acceptance.md#D03c90) |
| [#99](https://github.com/riscPrint/risc-v-workstation/issues/99) feat(sim): verify tlb invalidation and asid behavior | M2 | [D09.c90](acceptance.md#D09c90) |
| [#100](https://github.com/riscPrint/risc-v-workstation/issues/100) feat(platform): adjudicate independent reference disagreements | M2 | [D11.c90](acceptance.md#D11c90) |
| [#102](https://github.com/riscPrint/risc-v-workstation/issues/102) feat(sim): verify memory fence ordering | M2 | [D17.c90](acceptance.md#D17c90) |
| [#103](https://github.com/riscPrint/risc-v-workstation/issues/103) feat(sim): verify instruction visibility and fence.i | M3 | [D17.c5](acceptance.md#D17c5) |
| [#104](https://github.com/riscPrint/risc-v-workstation/issues/104) feat(platform): track rva23 and rvb23 profile obligations | M2 | [D09.c90](acceptance.md#D09c90) |
| [#106](https://github.com/riscPrint/risc-v-workstation/issues/106) feat(platform): test agents against misleading evidence | M3 | [D25.c90](acceptance.md#D25c90), [D25.c3c](acceptance.md#D25c3c) |
| [#107](https://github.com/riscPrint/risc-v-workstation/issues/107) feat(formal): prove declared connectivity | M3 | [D15.c90](acceptance.md#D15c90) |
| [#109](https://github.com/riscPrint/risc-v-workstation/issues/109) feat(sim): verify instruction and data cache behavior | M2 | [D17.c90](acceptance.md#D17c90) |
| [#111](https://github.com/riscPrint/risc-v-workstation/issues/111) feat(sim): verify reset lifecycle and warm reset | M2 | [D17.c90](acceptance.md#D17c90) |
| [#112](https://github.com/riscPrint/risc-v-workstation/issues/112) feat(sim): verify physical memory attributes | M2 | [D17.c90](acceptance.md#D17c90) |
| [#114](https://github.com/riscPrint/risc-v-workstation/issues/114) feat(cosim): compare hypervisor architectural state | M2 | [D10.c90](acceptance.md#D10c90) |
| [#118](https://github.com/riscPrint/risc-v-workstation/issues/118) feat(lint): analyze reset-domain crossings | M4 | [D37.c3](acceptance.md#D37c3), [D37.c7](acceptance.md#D37c7) |
| [#119](https://github.com/riscPrint/risc-v-workstation/issues/119) feat(platform): benchmark agent and human engineering tasks | M3 | [D25.c90](acceptance.md#D25c90), [D25.c3a](acceptance.md#D25c3a) |
| [#122](https://github.com/riscPrint/risc-v-workstation/issues/122) feat(platform): define custom instruction semantics | M2 | [D12.c90](acceptance.md#D12c90) |
| [#123](https://github.com/riscPrint/risc-v-workstation/issues/123) feat(platform): expose agent workflow plans and completion events | M2 | [D25.c90](acceptance.md#D25c90) |
| [#124](https://github.com/riscPrint/risc-v-workstation/issues/124) feat(arch): model soc cache and memory topology | M3 | [D01.c90](acceptance.md#D01c90) |
| [#125](https://github.com/riscPrint/risc-v-workstation/issues/125) feat(perf): analyze memory and interconnect performance | M3 | [D01.c90](acceptance.md#D01c90) |
| [#127](https://github.com/riscPrint/risc-v-workstation/issues/127) feat(debug): verify debug module lifecycle | M2 | [D18.c90](acceptance.md#D18c90) |
| [#128](https://github.com/riscPrint/risc-v-workstation/issues/128) feat(sim): verify coherence forward progress | M2 | [D17.c90](acceptance.md#D17c90), [D17.c3](acceptance.md#D17c3) |
| [#129](https://github.com/riscPrint/risc-v-workstation/issues/129) feat(sim): verify page access and dirty updates | M2 | [D09.c90](acceptance.md#D09c90) |
| [#131](https://github.com/riscPrint/risc-v-workstation/issues/131) feat(sim): verify plic arbitration and delivery | M2 | [D17.c90](acceptance.md#D17c90) |
| [#132](https://github.com/riscPrint/risc-v-workstation/issues/132) feat(sim): add deterministic checkpoints and replay | M4 | [D08.c90](acceptance.md#D08c90) |
| [#133](https://github.com/riscPrint/risc-v-workstation/issues/133) feat(debug): add native dmi and jtag simulation drivers | M2 | [D18.c90](acceptance.md#D18c90) |
| [#134](https://github.com/riscPrint/risc-v-workstation/issues/134) feat(integration): verify memory-map and bridge consistency | M2 | [D21.c3](acceptance.md#D21c3) |
| [#136](https://github.com/riscPrint/risc-v-workstation/issues/136) feat(cosim): compare debug entry and stepping state | M2 | [D11.c90](acceptance.md#D11c90) |
| [#137](https://github.com/riscPrint/risc-v-workstation/issues/137) feat(sim): verify cache-block operation extensions | M2 | [D10.c3](acceptance.md#D10c3) |
| [#138](https://github.com/riscPrint/risc-v-workstation/issues/138) feat(sim): verify epmp security policy | M2 | [D33.c90](acceptance.md#D33c90) |
| [#139](https://github.com/riscPrint/risc-v-workstation/issues/139) feat(sim): verify supervisor privilege controls | M2 | [D09.c90](acceptance.md#D09c90) |
| [#140](https://github.com/riscPrint/risc-v-workstation/issues/140) feat(sim): verify two-stage guest translation | M2 | [D10.c90](acceptance.md#D10c90) |
| [#141](https://github.com/riscPrint/risc-v-workstation/issues/141) feat(platform): track risc-v specification changes | M2 | [D09.c90](acceptance.md#D09c90) |
| [#142](https://github.com/riscPrint/risc-v-workstation/issues/142) feat(checks): verify register-map side-effect transactions | M3 | [D15.c90](acceptance.md#D15c90) |
| [#143](https://github.com/riscPrint/risc-v-workstation/issues/143) feat(cosim): load custom reference extensions | M2 | [D11.c5](acceptance.md#D11c5) |
| [#144](https://github.com/riscPrint/risc-v-workstation/issues/144) feat(debug): verify trigger modules | M2 | [D18.c90](acceptance.md#D18c90) |
| [#145](https://github.com/riscPrint/risc-v-workstation/issues/145) feat(sim): verify shared tlb shootdown scenarios | M3 | [D17.c7](acceptance.md#D17c7) |
| [#146](https://github.com/riscPrint/risc-v-workstation/issues/146) feat(checks): verify clock-gating controls | M2 | [D37.c90](acceptance.md#D37c90) |
| [#147](https://github.com/riscPrint/risc-v-workstation/issues/147) feat(sim): verify sv48 translation behavior | M2 | [D10.c90](acceptance.md#D10c90) |
| [#148](https://github.com/riscPrint/risc-v-workstation/issues/148) feat(sim): verify svpbmt page attributes | M2 | [D10.c90](acceptance.md#D10c90) |
| [#149](https://github.com/riscPrint/risc-v-workstation/issues/149) feat(sim): verify wfi sleep and wakeup behavior | M2 | [D21.c3](acceptance.md#D21c3) |
| [#150](https://github.com/riscPrint/risc-v-workstation/issues/150) feat(sim): define portable resource-aware scenarios | M5 | [D14.c90](acceptance.md#D14c90), [D14.c7](acceptance.md#D14c7) |
| [#151](https://github.com/riscPrint/risc-v-workstation/issues/151) feat(sim): verify hart lifecycle and shared resources | M2 | [D17.c90](acceptance.md#D17c90) |
| [#152](https://github.com/riscPrint/risc-v-workstation/issues/152) feat(sim): reduce instruction and concurrent stimulus failures | M2 | [D14.c90](acceptance.md#D14c90) |
| [#153](https://github.com/riscPrint/risc-v-workstation/issues/153) feat(debug): verify abstract commands and program buffer | M2 | [D18.c90](acceptance.md#D18c90) |
| [#154](https://github.com/riscPrint/risc-v-workstation/issues/154) feat(sim): verify sv32 translation behavior | M2 | [D10.c90](acceptance.md#D10c90) |
| [#155](https://github.com/riscPrint/risc-v-workstation/issues/155) feat(sim): generate custom extension verification plans | M2 | [D14.c90](acceptance.md#D14c90) |
| [#156](https://github.com/riscPrint/risc-v-workstation/issues/156) feat(debug): verify debug system-bus access | M2 | [D18.c90](acceptance.md#D18c90) |
| [#157](https://github.com/riscPrint/risc-v-workstation/issues/157) feat(checks): verify isolation and power-off behavior | M2 | [D37.c90](acceptance.md#D37c90) |
| [#158](https://github.com/riscPrint/risc-v-workstation/issues/158) feat(sim): verify aia imsic behavior | M2 | [D10.c90](acceptance.md#D10c90) |
| [#159](https://github.com/riscPrint/risc-v-workstation/issues/159) feat(sim): verify supervisor timer extensions | M2 | [D10.c90](acceptance.md#D10c90) |
| [#160](https://github.com/riscPrint/risc-v-workstation/issues/160) feat(arch): manage design-space exploration experiments | M4 | [D01.c90](acceptance.md#D01c90), [D02.c3](acceptance.md#D02c3) |
| [#161](https://github.com/riscPrint/risc-v-workstation/issues/161) feat(debug): test openocd and gdb interoperability | M2 | [D18.c90](acceptance.md#D18c90) |
| [#162](https://github.com/riscPrint/risc-v-workstation/issues/162) feat(platform): define explicit low-power intent | M2 | [D37.c90](acceptance.md#D37c90) |
| [#163](https://github.com/riscPrint/risc-v-workstation/issues/163) feat(checks): verify retention and power sequencing | M2 | [D37.c90](acceptance.md#D37c90) |
| [#164](https://github.com/riscPrint/risc-v-workstation/issues/164) feat(sim): verify svnapot page mappings | M2 | [D10.c90](acceptance.md#D10c90) |
| [#165](https://github.com/riscPrint/risc-v-workstation/issues/165) feat(sim): verify aia aplic behavior | M2 | [D10.c90](acceptance.md#D10c90) |
| [#166](https://github.com/riscPrint/risc-v-workstation/issues/166) feat(sim): verify nmi and recoverable error entry | M2 | [D10.c90](acceptance.md#D10c90) |
| [#167](https://github.com/riscPrint/risc-v-workstation/issues/167) feat(cov): track reusable block verification evidence | M4 | [D14.c90](acceptance.md#D14c90), [D06.c6](acceptance.md#D06c6) |
| [#168](https://github.com/riscPrint/risc-v-workstation/issues/168) feat(debug): verify e-trace encoder streams | M2 | [D18.c6](acceptance.md#D18c6) |
| [#169](https://github.com/riscPrint/risc-v-workstation/issues/169) feat(platform): generate custom instruction software hooks | M2 | [D12.c90](acceptance.md#D12c90) |
| [#170](https://github.com/riscPrint/risc-v-workstation/issues/170) feat(sim): verify compare-and-swap extensions | M2 | [D10.c90](acceptance.md#D10c90) |
| [#171](https://github.com/riscPrint/risc-v-workstation/issues/171) feat(sim): verify sv57 translation behavior | M2 | [D10.c90](acceptance.md#D10c90) |
| [#172](https://github.com/riscPrint/risc-v-workstation/issues/172) feat(debug): verify trace loss and resynchronization | M2 | [D18.c6](acceptance.md#D18c6) |
| [#173](https://github.com/riscPrint/risc-v-workstation/issues/173) feat(debug): query large waveforms through indexed storage | M3 | [D18.c90](acceptance.md#D18c90), [D18.c2](acceptance.md#D18c2) |
| [#174](https://github.com/riscPrint/risc-v-workstation/issues/174) feat(sim): verify landing-pad control-flow integrity | M2 | [D10.c90](acceptance.md#D10c90) |
| [#175](https://github.com/riscPrint/risc-v-workstation/issues/175) feat(sim): verify shadow-stack control-flow integrity | M2 | [D10.c90](acceptance.md#D10c90) |
| [#176](https://github.com/riscPrint/risc-v-workstation/issues/176) feat(sim): verify state-enable access controls | M2 | [D10.c90](acceptance.md#D10c90) |
| [#177](https://github.com/riscPrint/risc-v-workstation/issues/177) feat(sim): verify environment configuration controls | M2 | [D10.c90](acceptance.md#D10c90) |
| [#178](https://github.com/riscPrint/risc-v-workstation/issues/178) feat(sim): support systemverilog uvm testbench adapters | M4 | [D13.c90](acceptance.md#D13c90) |
| [#179](https://github.com/riscPrint/risc-v-workstation/issues/179) feat(sim): verify pointer masking and address rules | M2 | [D10.c90](acceptance.md#D10c90) |
| [#180](https://github.com/riscPrint/risc-v-workstation/issues/180) feat(cov): exchange coverage through ucis | M4 | [D14.c90](acceptance.md#D14c90), [D14.c3](acceptance.md#D14c3) |
| [#181](https://github.com/riscPrint/risc-v-workstation/issues/181) feat(sim): verify architectural ras reporting | M2 | [D10.c90](acceptance.md#D10c90) |
| [#182](https://github.com/riscPrint/risc-v-workstation/issues/182) feat(sim): add memory-controller and noc stress agents | M4 | [D08.c90](acceptance.md#D08c90) |
| [#183](https://github.com/riscPrint/risc-v-workstation/issues/183) feat(arch): support representative workload sampling | M5 | [D08.c90](acceptance.md#D08c90), [D08.c3](acceptance.md#D08c3) |
| [#184](https://github.com/riscPrint/risc-v-workstation/issues/184) feat(sim): verify ztso memory-order behavior | M3 | [D17.c6](acceptance.md#D17c6) |
| [#185](https://github.com/riscPrint/risc-v-workstation/issues/185) feat(lint): validate rtl timing-constraint intent | M2 | [D37.c5](acceptance.md#D37c5) |
| [#186](https://github.com/riscPrint/risc-v-workstation/issues/186) feat(sim): verify clic and aclic configurations | M2 | [D10.c90](acceptance.md#D10c90) |
| [#187](https://github.com/riscPrint/risc-v-workstation/issues/187) feat(sim): add systemc and tlm co-simulation adapters | M4 | [D30.c90](acceptance.md#D30c90), [D31.c6](acceptance.md#D31c6) |
| [#188](https://github.com/riscPrint/risc-v-workstation/issues/188) feat(sim): verify iommu translation and isolation | M2 | [D17.c90](acceptance.md#D17c90) |
| [#189](https://github.com/riscPrint/risc-v-workstation/issues/189) feat(cosim): exchange standard risc-v observation streams | M2 | [D11.c5](acceptance.md#D11c5) |
| [#190](https://github.com/riscPrint/risc-v-workstation/issues/190) feat(sim): add apb verification agents | M2 | [D37.c90](acceptance.md#D37c90) |
| [#191](https://github.com/riscPrint/risc-v-workstation/issues/191) feat(debug): add reverse-step through checkpoint replay | M4 | [D08.c90](acceptance.md#D08c90), [D18.c3](acceptance.md#D18c3) |
| [#192](https://github.com/riscPrint/risc-v-workstation/issues/192) feat(sim): add axi-stream verification agents | M2 | [D37.c90](acceptance.md#D37c90) |
| [#193](https://github.com/riscPrint/risc-v-workstation/issues/193) feat(integration): export rtl implementation handoff data | M2 | [D37.c5](acceptance.md#D37c5) |
| [#194](https://github.com/riscPrint/risc-v-workstation/issues/194) feat(debug): verify n-trace encoder streams | M2 | [D18.c6](acceptance.md#D18c6) |
| [#195](https://github.com/riscPrint/risc-v-workstation/issues/195) feat(debug): verify trace control and security filters | M2 | [D18.c6](acceptance.md#D18c6) |
| [#196](https://github.com/riscPrint/risc-v-workstation/issues/196) feat(arch): explore custom instruction trade-offs | M2 | [D12.c90](acceptance.md#D12c90) |
| [#197](https://github.com/riscPrint/risc-v-workstation/issues/197) feat(sim): verify dvfs and clock-switch behavior | M2 | [D37.c90](acceptance.md#D37c90) |
| [#198](https://github.com/riscPrint/risc-v-workstation/issues/198) feat(checks): verify test-mode functional isolation | M3 | [D37.c6](acceptance.md#D37c6) |
| [#199](https://github.com/riscPrint/risc-v-workstation/issues/199) feat(sim): add ahb verification agents | M2 | [D37.c90](acceptance.md#D37c90) |
| [#200](https://github.com/riscPrint/risc-v-workstation/issues/200) feat(checks): report rtl dft access constraints | M3 | [D37.c6](acceptance.md#D37c6) |
| [#201](https://github.com/riscPrint/risc-v-workstation/issues/201) feat(arch): model system power-state workloads | M2 | [D37.c90](acceptance.md#D37c90) |
| [#202](https://github.com/riscPrint/risc-v-workstation/issues/202) feat(sim): add uart verification agents | M2 | [D37.c90](acceptance.md#D37c90) |
| [#203](https://github.com/riscPrint/risc-v-workstation/issues/203) feat(platform): track cryptographic entropy interfaces | M3 | [D34.c5](acceptance.md#D34c5) |
| [#204](https://github.com/riscPrint/risc-v-workstation/issues/204) feat(sim): add spi verification agents | M2 | [D37.c90](acceptance.md#D37c90) |
| [#205](https://github.com/riscPrint/risc-v-workstation/issues/205) feat(sim): add i2c verification agents | M2 | [D37.c90](acceptance.md#D37c90) |
| [#206](https://github.com/riscPrint/risc-v-workstation/issues/206) feat(integration): import implementation feedback links | M2 | [D37.c5](acceptance.md#D37c5) |
| [#207](https://github.com/riscPrint/risc-v-workstation/issues/207) feat(debug): verify vendor trace format adapters | M2 | [D18.c6](acceptance.md#D18c6) |
| [#208](https://github.com/riscPrint/risc-v-workstation/issues/208) feat(integration): describe memory bist handoff requirements | M3 | [D37.c6](acceptance.md#D37c6) |
| [#209](https://github.com/riscPrint/risc-v-workstation/issues/209) feat(sim): add gpio verification agents | M2 | [D37.c90](acceptance.md#D37c90) |
| [#210](https://github.com/riscPrint/risc-v-workstation/issues/210) feat(cosim): assess cheri architectural comparison | M3 | [D34.c3](acceptance.md#D34c3) |
| [#211](https://github.com/riscPrint/risc-v-workstation/issues/211) feat(integration): describe jtag and test access topology | M3 | [D37.c6](acceptance.md#D37c6) |
| [#212](https://github.com/riscPrint/risc-v-workstation/issues/212) feat(sim): add optional chi verification backend | M2 | [D37.c90](acceptance.md#D37c90) |
| [#213](https://github.com/riscPrint/risc-v-workstation/issues/213) feat(sim): validate dram model integration contracts | M4 | [D08.c90](acceptance.md#D08c90) |
| [#214](https://github.com/riscPrint/risc-v-workstation/issues/214) feat(sim): add timing annotation capability contracts | M4 | [D31.c90](acceptance.md#D31c90), [D31.c3](acceptance.md#D31c3) |
| [#215](https://github.com/riscPrint/risc-v-workstation/issues/215) feat(sim): add pcie transaction-model adapters | M2 | [D37.c90](acceptance.md#D37c90) |
| [#216](https://github.com/riscPrint/risc-v-workstation/issues/216) feat(sim): add ethernet packet-model adapters | M2 | [D37.c90](acceptance.md#D37c90) |
| [#217](https://github.com/riscPrint/risc-v-workstation/issues/217) feat(sim): define mixed-signal boundary model adapters | M4 | [D37.c4](acceptance.md#D37c4) |
| [#282](https://github.com/riscPrint/risc-v-workstation/issues/282) chore(workloads): choose open alternatives to SPEC CPU2017 | M6 | [D20.c90](acceptance.md#D20c90), [D20.c6](acceptance.md#D20c6) |
| [#294](https://github.com/riscPrint/risc-v-workstation/issues/294) feat(formal): extend open formal engines to match or beat JasperGold and VC Formal | M5 | [D15.c90](acceptance.md#D15c90), [D15.c12](acceptance.md#D15c12) |
| [#295](https://github.com/riscPrint/risc-v-workstation/issues/295) feat(sim): extend open simulation to match or beat VCS and Xcelium | M6 | [D07.c90](acceptance.md#D07c90) |
| [#296](https://github.com/riscPrint/risc-v-workstation/issues/296) feat(sim): build a full open UVM flow | M4 | [D13.c90](acceptance.md#D13c90), [D13.c2](acceptance.md#D13c2) |
| [#297](https://github.com/riscPrint/risc-v-workstation/issues/297) feat(debug): extend open debug tools to match or beat Verdi | M5 | [D18.c90](acceptance.md#D18c90) |
| [#335](https://github.com/riscPrint/risc-v-workstation/issues/335) feat(sim): version-aware core adapters so bisect and gates work across core history | M4 | [D30.c6](acceptance.md#D30c6) |
| [#344](https://github.com/riscPrint/risc-v-workstation/issues/344) perf(sim): capture PGO and hierarchy inputs for BOOM trials | M4 | [D07.c90](acceptance.md#D07c90) |
| [#345](https://github.com/riscPrint/risc-v-workstation/issues/345) feat(sim): evaluate native Arcilator with C1 and C2 contracts | M4 | [D07.c90](acceptance.md#D07c90) |
| [#346](https://github.com/riscPrint/risc-v-workstation/issues/346) feat(sim): save and restore native model and harness state | M4 | [D08.c90](acceptance.md#D08c90) |
| [#347](https://github.com/riscPrint/risc-v-workstation/issues/347) feat(sim): transfer Spike checkpoints into VexRiscv RTL | M4 | [D08.c90](acceptance.md#D08c90) |
| [#348](https://github.com/riscPrint/risc-v-workstation/issues/348) feat(arch): measure checkpoint warm-up bias against RTL | M4 | [D08.c90](acceptance.md#D08c90) |
| [#349](https://github.com/riscPrint/risc-v-workstation/issues/349) feat(cov): measure isa closure against random stimulus | M3 | [D14.c90](acceptance.md#D14c90), [D14.c9](acceptance.md#D14c9) |
| [#350](https://github.com/riscPrint/risc-v-workstation/issues/350) feat(sim): extend checkpoint profiles for FP and system state | M4 | [D08.c90](acceptance.md#D08c90) |
| [#351](https://github.com/riscPrint/risc-v-workstation/issues/351) feat(component-sims): qualify TAGE-SC-L and BOOM-like project models | M3 | [D01.c90](acceptance.md#D01c90) |
| [#352](https://github.com/riscPrint/risc-v-workstation/issues/352) feat(cov): close sequence bins with bounded stimulus actions | M3 | [D14.c90](acceptance.md#D14c90), [D14.c9](acceptance.md#D14c9) |
| [#353](https://github.com/riscPrint/risc-v-workstation/issues/353) feat(cov): guide stimulus with measured rtl event goals | M3 | [D14.c90](acceptance.md#D14c90), [D14.c9](acceptance.md#D14c9) |
| [#354](https://github.com/riscPrint/risc-v-workstation/issues/354) feat(arch): check own core configuration and timing structures | M3 | [D01.c90](acceptance.md#D01c90) |
| [#355](https://github.com/riscPrint/risc-v-workstation/issues/355) feat(arch): calibrate own core model against held-out rtl events | M3 | [D01.c90](acceptance.md#D01c90) |
| [#356](https://github.com/riscPrint/risc-v-workstation/issues/356) feat(arch): qualify own core predictions and native speed | M3 | [D01.c90](acceptance.md#D01c90) |
| [#357](https://github.com/riscPrint/risc-v-workstation/issues/357) feat(arch): model multi-level BTB and FTQ-directed prefetching | M3 | [D01.c90](acceptance.md#D01c90) |
| [#358](https://github.com/riscPrint/risc-v-workstation/issues/358) feat(component-sims): compare predictor models with explicit RTL events | M3 | [D01.c90](acceptance.md#D01c90) |
| [#359](https://github.com/riscPrint/risc-v-workstation/issues/359) feat(arch): model a generic micro-op cache | M3 | [D01.c90](acceptance.md#D01c90) |
| [#360](https://github.com/riscPrint/risc-v-workstation/issues/360) feat(component-sims): add BTB and RAS trace models | M3 | [D01.c90](acceptance.md#D01c90) |
| [#361](https://github.com/riscPrint/risc-v-workstation/issues/361) feat(formal): extend coherence models with fair progress and directory profiles | M2 | [D17.c90](acceptance.md#D17c90), [D17.c3](acceptance.md#D17c3) |
| [#362](https://github.com/riscPrint/risc-v-workstation/issues/362) feat(arch): validate wide rename and bound memory renaming | M3 | [D17.c90](acceptance.md#D17c90), [D01.c7](acceptance.md#D01c7) |
| [#363](https://github.com/riscPrint/risc-v-workstation/issues/363) feat(sim): bind coherence model monitors to TileLink-C channel RTL | M2 | [D17.c90](acceptance.md#D17c90), [D17.c3](acceptance.md#D17c3) |
| [#364](https://github.com/riscPrint/risc-v-workstation/issues/364) feat(agent-bench): qualify native Spinal and VexRiscv tasks | M3 | [D25.c90](acceptance.md#D25c90), [D25.c3a](acceptance.md#D25c3a) |
| [#365](https://github.com/riscPrint/risc-v-workstation/issues/365) feat(component-sims): add prefetch and cache-replacement studies | M3 | [D01.c90](acceptance.md#D01c90) |
| [#366](https://github.com/riscPrint/risc-v-workstation/issues/366) feat(agent-bench): add bounded external agent trials | M3 | [D25.c90](acceptance.md#D25c90), [D25.c3a](acceptance.md#D25c3a) |
| [#367](https://github.com/riscPrint/risc-v-workstation/issues/367) feat(arch): integrate generated scheduling models into native compilers | M3 | [D38.c4](acceptance.md#D38c4) |
| [#369](https://github.com/riscPrint/risc-v-workstation/issues/369) feat(arch): extend scheduling measurements with held-out kernels | M3 | [D38.c4](acceptance.md#D38c4) |
| [#370](https://github.com/riscPrint/risc-v-workstation/issues/370) feat(query): elaborate full SV cores with slang and captured includes | M1 | [D05.c0](acceptance.md#D05c0) |
| [#371](https://github.com/riscPrint/risc-v-workstation/issues/371) feat(query): add a GHDL front end for VHDL designs | M1 | [D05.c0](acceptance.md#D05c0) |
| [#372](https://github.com/riscPrint/risc-v-workstation/issues/372) feat(query): add a FIRRTL and CIRCT front end for Chisel | M1 | [D05.c0](acceptance.md#D05c0) |
| [#375](https://github.com/riscPrint/risc-v-workstation/issues/375) Owner review: upstream SpinalTrace work (ccromjongh/SpinalHDL, SigTrail) | M2 | [D18.c90](acceptance.md#D18c90), [D18.c12](acceptance.md#D18c12) |
| [#376](https://github.com/riscPrint/risc-v-workstation/issues/376) feat(cov): integrate RISCV-DV random instruction streams with cosim | M2 | [D14.c90](acceptance.md#D14c90) |
| [#377](https://github.com/riscPrint/risc-v-workstation/issues/377) feat(integration): add VexiiRiscv as a test core | M2 | [D30.c90](acceptance.md#D30c90) |
| [#378](https://github.com/riscPrint/risc-v-workstation/issues/378) docs(research): study CORE-V-VERIF for UVM and CPU verification practice | M4 | [D13.c90](acceptance.md#D13c90) |
| [#379](https://github.com/riscPrint/risc-v-workstation/issues/379) docs(research): study Chipyard and find contributions we can make | M2 | [D30.c90](acceptance.md#D30c90) |

# New tools and command families

Hourly refresh collected at 2026-11-13T14:22:26.916089+00:00: 212 additional merged PRs; 775 merged PRs in total; 213 current open issues; 7 currently closed issues closed since midnight. The 218-issue midnight census and separate new issues #722 and #723 are unchanged. Earlier collection text below is historical. The latest refresh notes take precedence for current state. No project tests, builds, simulations or proofs ran.

Snapshot collected at 2026-11-13T07:16:42.340567+00:00. PR merge window starts at 2026-11-13T00:00:00Z. This is a reading audit. No tests, builds, simulations or proofs ran for this report. PR bodies report the evidence. Their artifacts were not independently rerun.

The requested examples include tools that do have issue references. Thus this inventory distinguishes a new family from an unsolicited family. A reference can cover only part of a tool. The owner must decide whether a new standalone tracker is needed. Existing families with major extensions are retained here so that the Components table does not miss their new scope.

## ComponentSims / rvw csim

Path: `ComponentSims/; rvw/src/rvw/csim/`.

Purpose: Trace-driven predictor, cache, prefetch and timing studies.

Evidence level: ran on real core RTL. This is the strongest reported slice, not qualification of the family.

Sources: [#447](https://github.com/riscPrint/risc-v-workstation/pull/447), [#483](https://github.com/riscPrint/risc-v-workstation/pull/483), [#510](https://github.com/riscPrint/risc-v-workstation/pull/510), [#576](https://github.com/riscPrint/risc-v-workstation/pull/576), [#784](https://github.com/riscPrint/risc-v-workstation/pull/784), [#862](https://github.com/riscPrint/risc-v-workstation/pull/862).

Issue association: [#37](https://github.com/riscPrint/risc-v-workstation/issues/37), [#72](https://github.com/riscPrint/risc-v-workstation/issues/72), [#124](https://github.com/riscPrint/risc-v-workstation/issues/124), [#351](https://github.com/riscPrint/risc-v-workstation/issues/351), [#355](https://github.com/riscPrint/risc-v-workstation/issues/355), [#357](https://github.com/riscPrint/risc-v-workstation/issues/357), [#358](https://github.com/riscPrint/risc-v-workstation/issues/358), [#360](https://github.com/riscPrint/risc-v-workstation/issues/360), [#365](https://github.com/riscPrint/risc-v-workstation/issues/365).

Proposed Components row:

| ComponentSims / rvw csim | `ComponentSims/; rvw/src/rvw/csim/` | ARCH | No new BOOM qualification claimed | Trace-driven predictor, cache, prefetch and timing studies. | Experimental; reported evidence: ran on real core RTL. Scope limits remain in the cited PRs. |

## SpinalProbes / rvw probes

Path: `SpinalProbes/; rvw/src/rvw/probes/`.

Purpose: Optional simulation probes and consumer conversion.

Evidence level: ran on real core RTL. This is the strongest reported slice, not qualification of the family.

Sources: [#612](https://github.com/riscPrint/risc-v-workstation/pull/612), [#614](https://github.com/riscPrint/risc-v-workstation/pull/614), [#784](https://github.com/riscPrint/risc-v-workstation/pull/784), [#829](https://github.com/riscPrint/risc-v-workstation/pull/829).

Issue association: [#49](https://github.com/riscPrint/risc-v-workstation/issues/49).

Proposed Components row:

| SpinalProbes / rvw probes | `SpinalProbes/; rvw/src/rvw/probes/` | ARCH, DBG | No new BOOM qualification claimed | Optional simulation probes and consumer conversion. | Experimental; reported evidence: ran on real core RTL. Scope limits remain in the cited PRs. |

## rvw sec

Path: `rvw/src/rvw/sec/`.

Purpose: Dynamic simulation security experiments and contract suites.

Evidence level: ran on seeded RTL fixture. This is the strongest reported slice, not qualification of the family.

Sources: [#696](https://github.com/riscPrint/risc-v-workstation/pull/696), [#700](https://github.com/riscPrint/risc-v-workstation/pull/700), [#703](https://github.com/riscPrint/risc-v-workstation/pull/703), [#715](https://github.com/riscPrint/risc-v-workstation/pull/715), [#717](https://github.com/riscPrint/risc-v-workstation/pull/717), [#720](https://github.com/riscPrint/risc-v-workstation/pull/720), [#726](https://github.com/riscPrint/risc-v-workstation/pull/726).

Issue association: No reference to a collected issue. Treat as unsolicited until the owner assigns scope..

Proposed Components row:

| rvw sec | `rvw/src/rvw/sec/` | VER | No new BOOM qualification claimed | Dynamic simulation security experiments and contract suites. | Experimental; reported evidence: ran on seeded RTL fixture. Scope limits remain in the cited PRs. |

## rvw fault

Path: `rvw/src/rvw/fault/; RiscvSim/`.

Purpose: Fault plans, native public-access injection and C2 classification.

Evidence level: ran on seeded RTL fixture. This is the strongest reported slice, not qualification of the family.

Sources: [#556](https://github.com/riscPrint/risc-v-workstation/pull/556), [#689](https://github.com/riscPrint/risc-v-workstation/pull/689).

Issue association: [#52](https://github.com/riscPrint/risc-v-workstation/issues/52).

Proposed Components row:

| rvw fault | `rvw/src/rvw/fault/; RiscvSim/` | VER | No new BOOM qualification claimed | Fault plans, native public-access injection and C2 classification. | Experimental; reported evidence: ran on seeded RTL fixture. Scope limits remain in the cited PRs. |

## rvw bugmem

Path: `rvw/src/rvw/bugmem/`.

Purpose: Store failure patterns and find similar reports.

Evidence level: unit tests only. This is the strongest reported slice, not qualification of the family.

Sources: [#484](https://github.com/riscPrint/risc-v-workstation/pull/484).

Issue association: [#32](https://github.com/riscPrint/risc-v-workstation/issues/32).

Proposed Components row:

| rvw bugmem | `rvw/src/rvw/bugmem/` | DBG | No new BOOM qualification claimed | Store failure patterns and find similar reports. | Experimental; reported evidence: unit tests only. Scope limits remain in the cited PRs. |

## SpinalSoc / rvw soc compose

Path: `SpinalSoc/; rvw/src/rvw/soc/`.

Purpose: Compose map-driven peripheral SoCs and generate software data.

Evidence level: ran on real core RTL. This is the strongest reported slice, not qualification of the family.

Sources: [#683](https://github.com/riscPrint/risc-v-workstation/pull/683), [#694](https://github.com/riscPrint/risc-v-workstation/pull/694), [#709](https://github.com/riscPrint/risc-v-workstation/pull/709), [#805](https://github.com/riscPrint/risc-v-workstation/pull/805), [#851](https://github.com/riscPrint/risc-v-workstation/pull/851).

Issue association: No reference to a collected issue. Treat as unsolicited until the owner assigns scope..

Proposed Components row:

| SpinalSoc / rvw soc compose | `SpinalSoc/; rvw/src/rvw/soc/` | SIM, PLAT | No new BOOM qualification claimed | Compose map-driven peripheral SoCs and generate software data. | Experimental; reported evidence: ran on real core RTL. Scope limits remain in the cited PRs. |

## rvw vip / protocol families

Path: `rvw/src/rvw/vip/; Uvm/vip/`.

Purpose: Protocol agents, RTL controls and optional external-model contracts.

Evidence level: ran on seeded RTL fixture. This is the strongest reported slice, not qualification of the family.

Sources: [#396](https://github.com/riscPrint/risc-v-workstation/pull/396), [#413](https://github.com/riscPrint/risc-v-workstation/pull/413), [#439](https://github.com/riscPrint/risc-v-workstation/pull/439), [#462](https://github.com/riscPrint/risc-v-workstation/pull/462), [#478](https://github.com/riscPrint/risc-v-workstation/pull/478), [#493](https://github.com/riscPrint/risc-v-workstation/pull/493), [#516](https://github.com/riscPrint/risc-v-workstation/pull/516), [#527](https://github.com/riscPrint/risc-v-workstation/pull/527), [#571](https://github.com/riscPrint/risc-v-workstation/pull/571), [#579](https://github.com/riscPrint/risc-v-workstation/pull/579), [#586](https://github.com/riscPrint/risc-v-workstation/pull/586), [#595](https://github.com/riscPrint/risc-v-workstation/pull/595), [#603](https://github.com/riscPrint/risc-v-workstation/pull/603), [#609](https://github.com/riscPrint/risc-v-workstation/pull/609), [#620](https://github.com/riscPrint/risc-v-workstation/pull/620), [#627](https://github.com/riscPrint/risc-v-workstation/pull/627), [#636](https://github.com/riscPrint/risc-v-workstation/pull/636), [#642](https://github.com/riscPrint/risc-v-workstation/pull/642), [#647](https://github.com/riscPrint/risc-v-workstation/pull/647), [#656](https://github.com/riscPrint/risc-v-workstation/pull/656), [#662](https://github.com/riscPrint/risc-v-workstation/pull/662), [#853](https://github.com/riscPrint/risc-v-workstation/pull/853).

Issue association: [#48](https://github.com/riscPrint/risc-v-workstation/issues/48), [#182](https://github.com/riscPrint/risc-v-workstation/issues/182), [#190](https://github.com/riscPrint/risc-v-workstation/issues/190), [#199](https://github.com/riscPrint/risc-v-workstation/issues/199), [#202](https://github.com/riscPrint/risc-v-workstation/issues/202), [#204](https://github.com/riscPrint/risc-v-workstation/issues/204), [#205](https://github.com/riscPrint/risc-v-workstation/issues/205), [#209](https://github.com/riscPrint/risc-v-workstation/issues/209), [#211](https://github.com/riscPrint/risc-v-workstation/issues/211), [#212](https://github.com/riscPrint/risc-v-workstation/issues/212), [#213](https://github.com/riscPrint/risc-v-workstation/issues/213), [#215](https://github.com/riscPrint/risc-v-workstation/issues/215), [#216](https://github.com/riscPrint/risc-v-workstation/issues/216), [#217](https://github.com/riscPrint/risc-v-workstation/issues/217).

Proposed Components row:

| rvw vip / protocol families | `rvw/src/rvw/vip/; Uvm/vip/` | VER | No new BOOM qualification claimed | Protocol agents, RTL controls and optional external-model contracts. | Experimental; reported evidence: ran on seeded RTL fixture. Scope limits remain in the cited PRs. |

## rvw uvm / CPU and RAL families

Path: `rvw/src/rvw/uvm/; Uvm/`.

Purpose: Project benches, RAL and CPU verification sequences.

Evidence level: ran on real core RTL. This is the strongest reported slice, not qualification of the family.

Sources: [#394](https://github.com/riscPrint/risc-v-workstation/pull/394), [#414](https://github.com/riscPrint/risc-v-workstation/pull/414), [#469](https://github.com/riscPrint/risc-v-workstation/pull/469), [#536](https://github.com/riscPrint/risc-v-workstation/pull/536), [#592](https://github.com/riscPrint/risc-v-workstation/pull/592), [#600](https://github.com/riscPrint/risc-v-workstation/pull/600), [#605](https://github.com/riscPrint/risc-v-workstation/pull/605), [#618](https://github.com/riscPrint/risc-v-workstation/pull/618), [#624](https://github.com/riscPrint/risc-v-workstation/pull/624), [#668](https://github.com/riscPrint/risc-v-workstation/pull/668), [#674](https://github.com/riscPrint/risc-v-workstation/pull/674), [#690](https://github.com/riscPrint/risc-v-workstation/pull/690), [#704](https://github.com/riscPrint/risc-v-workstation/pull/704), [#711](https://github.com/riscPrint/risc-v-workstation/pull/711).

Issue association: [#296](https://github.com/riscPrint/risc-v-workstation/issues/296).

Proposed Components row:

| rvw uvm / CPU and RAL families | `rvw/src/rvw/uvm/; Uvm/` | VER | No new BOOM qualification claimed | Project benches, RAL and CPU verification sequences. | Experimental; reported evidence: ran on real core RTL. Scope limits remain in the cited PRs. |

## rvw lsp

Path: `rvw/src/rvw/lsp/`.

Purpose: Database-backed language navigation and an editor client.

Evidence level: unit tests only. This is the strongest reported slice, not qualification of the family.

Sources: [#798](https://github.com/riscPrint/risc-v-workstation/pull/798).

Issue association: [#26](https://github.com/riscPrint/risc-v-workstation/issues/26), [#55](https://github.com/riscPrint/risc-v-workstation/issues/55).

Proposed Components row:

| rvw lsp | `rvw/src/rvw/lsp/` | IDE | No new BOOM qualification claimed | Database-backed language navigation and an editor client. | Experimental; reported evidence: unit tests only. Scope limits remain in the cited PRs. |

## rvw plan

Path: `rvw/src/rvw/plan/`.

Purpose: Roll up project verification evidence and trends.

Evidence level: unit tests only. This is the strongest reported slice, not qualification of the family.

Sources: [#567](https://github.com/riscPrint/risc-v-workstation/pull/567).

Issue association: [#167](https://github.com/riscPrint/risc-v-workstation/issues/167).

Proposed Components row:

| rvw plan | `rvw/src/rvw/plan/` | PLAT | No new BOOM qualification claimed | Roll up project verification evidence and trends. | Experimental; reported evidence: unit tests only. Scope limits remain in the cited PRs. |

## rvw agent guide

Path: `rvw/src/rvw/agent/`.

Purpose: Expose the agent playbook through CLI and MCP.

Evidence level: unit tests only. This is the strongest reported slice, not qualification of the family.

Sources: [#649](https://github.com/riscPrint/risc-v-workstation/pull/649), [#792](https://github.com/riscPrint/risc-v-workstation/pull/792).

Issue association: [#27](https://github.com/riscPrint/risc-v-workstation/issues/27), [#106](https://github.com/riscPrint/risc-v-workstation/issues/106).

Proposed Components row:

| rvw agent guide | `rvw/src/rvw/agent/` | PLAT | No new BOOM qualification claimed | Expose the agent playbook through CLI and MCP. | Experimental; reported evidence: unit tests only. Scope limits remain in the cited PRs. |

## rvw evidence

Path: `rvw/src/rvw/evidence/`.

Purpose: Index original cross-tool evidence and dependencies.

Evidence level: unit tests only. This is the strongest reported slice, not qualification of the family.

Sources: [#604](https://github.com/riscPrint/risc-v-workstation/pull/604).

Issue association: [#95](https://github.com/riscPrint/risc-v-workstation/issues/95).

Proposed Components row:

| rvw evidence | `rvw/src/rvw/evidence/` | PLAT | No new BOOM qualification claimed | Index original cross-tool evidence and dependencies. | Experimental; reported evidence: unit tests only. Scope limits remain in the cited PRs. |

## Standard device plugins

Path: `rvw/src/rvw/sim/; RiscvSim/`.

Purpose: Device models, live input wiring and device-aware checkpoints.

Evidence level: ran on real core RTL. This is the strongest reported slice, not qualification of the family.

Sources: [#485](https://github.com/riscPrint/risc-v-workstation/pull/485), [#635](https://github.com/riscPrint/risc-v-workstation/pull/635), [#801](https://github.com/riscPrint/risc-v-workstation/pull/801), [#814](https://github.com/riscPrint/risc-v-workstation/pull/814).

Issue association: [#187](https://github.com/riscPrint/risc-v-workstation/issues/187), [#295](https://github.com/riscPrint/risc-v-workstation/issues/295).

Proposed Components row:

| Standard device plugins | `rvw/src/rvw/sim/; RiscvSim/` | SIM | No new BOOM qualification claimed | Device models, live input wiring and device-aware checkpoints. | Experimental; reported evidence: ran on real core RTL. Scope limits remain in the cited PRs. |

## Arcilator adapter

Path: `rvw/src/rvw/sim/; RiscvSim/`.

Purpose: Alternate native engine and controlled comparison with Verilator.

Evidence level: ran on real core RTL. This is the strongest reported slice, not qualification of the family.

Sources: [#654](https://github.com/riscPrint/risc-v-workstation/pull/654), [#714](https://github.com/riscPrint/risc-v-workstation/pull/714), [#826](https://github.com/riscPrint/risc-v-workstation/pull/826).

Issue association: [#45](https://github.com/riscPrint/risc-v-workstation/issues/45), [#335](https://github.com/riscPrint/risc-v-workstation/issues/335), [#345](https://github.com/riscPrint/risc-v-workstation/issues/345).

Proposed Components row:

| Arcilator adapter | `rvw/src/rvw/sim/; RiscvSim/` | SIM | No new BOOM qualification claimed | Alternate native engine and controlled comparison with Verilator. | Experimental; reported evidence: ran on real core RTL. Scope limits remain in the cited PRs. |

## slang front end

Path: `rvw/src/rvw/query/`.

Purpose: Build a database from elaborated SystemVerilog.

Evidence level: unit tests only. This is the strongest reported slice, not qualification of the family.

Sources: [#601](https://github.com/riscPrint/risc-v-workstation/pull/601), [#788](https://github.com/riscPrint/risc-v-workstation/pull/788), [#832](https://github.com/riscPrint/risc-v-workstation/pull/832), [#839](https://github.com/riscPrint/risc-v-workstation/pull/839), [#859](https://github.com/riscPrint/risc-v-workstation/pull/859).

Issue association: [#55](https://github.com/riscPrint/risc-v-workstation/issues/55), [#370](https://github.com/riscPrint/risc-v-workstation/issues/370), [#371](https://github.com/riscPrint/risc-v-workstation/issues/371).

Proposed Components row:

| slang front end | `rvw/src/rvw/query/` | IDE | No new BOOM qualification claimed | Build a database from elaborated SystemVerilog. | Experimental; reported evidence: unit tests only. Scope limits remain in the cited PRs. |

## GHDL front end

Path: `rvw/src/rvw/query/`.

Purpose: Build a database from the supported VHDL synthesis subset.

Evidence level: unit tests only. This is the strongest reported slice, not qualification of the family.

Sources: [#633](https://github.com/riscPrint/risc-v-workstation/pull/633), [#811](https://github.com/riscPrint/risc-v-workstation/pull/811).

Issue association: [#370](https://github.com/riscPrint/risc-v-workstation/issues/370), [#371](https://github.com/riscPrint/risc-v-workstation/issues/371).

Proposed Components row:

| GHDL front end | `rvw/src/rvw/query/` | IDE | No new BOOM qualification claimed | Build a database from the supported VHDL synthesis subset. | Experimental; reported evidence: unit tests only. Scope limits remain in the cited PRs. |

## FIRRTL/CIRCT front end

Path: `rvw/src/rvw/query/`.

Purpose: Build a database from Chisel-generated FIRRTL through CIRCT.

Evidence level: unit tests only. This is the strongest reported slice, not qualification of the family.

Sources: [#657](https://github.com/riscPrint/risc-v-workstation/pull/657), [#818](https://github.com/riscPrint/risc-v-workstation/pull/818).

Issue association: [#372](https://github.com/riscPrint/risc-v-workstation/issues/372).

Proposed Components row:

| FIRRTL/CIRCT front end | `rvw/src/rvw/query/` | IDE | No new BOOM qualification claimed | Build a database from Chisel-generated FIRRTL through CIRCT. | Experimental; reported evidence: unit tests only. Scope limits remain in the cited PRs. |

## rvw checks

Path: `rvw/src/rvw/checks/`.

Purpose: Generate project checks and report connected qualification gaps.

Evidence level: ran on real core RTL. This is the strongest reported slice, not qualification of the family.

Sources: [#602](https://github.com/riscPrint/risc-v-workstation/pull/602), [#732](https://github.com/riscPrint/risc-v-workstation/pull/732), [#775](https://github.com/riscPrint/risc-v-workstation/pull/775), [#800](https://github.com/riscPrint/risc-v-workstation/pull/800), [#840](https://github.com/riscPrint/risc-v-workstation/pull/840), [#861](https://github.com/riscPrint/risc-v-workstation/pull/861).

Issue association: [#65](https://github.com/riscPrint/risc-v-workstation/issues/65), [#66](https://github.com/riscPrint/risc-v-workstation/issues/66), [#85](https://github.com/riscPrint/risc-v-workstation/issues/85), [#98](https://github.com/riscPrint/risc-v-workstation/issues/98), [#146](https://github.com/riscPrint/risc-v-workstation/issues/146).

Proposed Components row:

| rvw checks | `rvw/src/rvw/checks/` | FV | No new BOOM qualification claimed | Generate project checks and report connected qualification gaps. | Experimental; reported evidence: ran on real core RTL. Scope limits remain in the cited PRs. |

## Farm service and workflows

Path: `rvw/src/rvw/farm/`.

Purpose: Queue work, plan shards and retain recovery and cost evidence.

Evidence level: unit tests only. This is the strongest reported slice, not qualification of the family.

Sources: [#570](https://github.com/riscPrint/risc-v-workstation/pull/570), [#574](https://github.com/riscPrint/risc-v-workstation/pull/574), [#581](https://github.com/riscPrint/risc-v-workstation/pull/581), [#594](https://github.com/riscPrint/risc-v-workstation/pull/594), [#598](https://github.com/riscPrint/risc-v-workstation/pull/598), [#615](https://github.com/riscPrint/risc-v-workstation/pull/615), [#641](https://github.com/riscPrint/risc-v-workstation/pull/641), [#652](https://github.com/riscPrint/risc-v-workstation/pull/652), [#658](https://github.com/riscPrint/risc-v-workstation/pull/658), [#680](https://github.com/riscPrint/risc-v-workstation/pull/680).

Issue association: [#25](https://github.com/riscPrint/risc-v-workstation/issues/25), [#54](https://github.com/riscPrint/risc-v-workstation/issues/54), [#57](https://github.com/riscPrint/risc-v-workstation/issues/57), [#59](https://github.com/riscPrint/risc-v-workstation/issues/59), [#123](https://github.com/riscPrint/risc-v-workstation/issues/123).

Proposed Components row:

| Farm service and workflows | `rvw/src/rvw/farm/` | SIM, PLAT | No new BOOM qualification claimed | Queue work, plan shards and retain recovery and cost evidence. | Experimental; reported evidence: unit tests only. Scope limits remain in the cited PRs. |

## Debug Module campaign commands

Path: `rvw/src/rvw/debug/`.

Purpose: Reference Debug Module, DMI/JTAG drivers and trace campaigns.

Evidence level: reference model only (Spike/Sail/Python). This is the strongest reported slice, not qualification of the family.

Sources: [#455](https://github.com/riscPrint/risc-v-workstation/pull/455), [#473](https://github.com/riscPrint/risc-v-workstation/pull/473), [#512](https://github.com/riscPrint/risc-v-workstation/pull/512), [#541](https://github.com/riscPrint/risc-v-workstation/pull/541), [#568](https://github.com/riscPrint/risc-v-workstation/pull/568).

Issue association: [#127](https://github.com/riscPrint/risc-v-workstation/issues/127), [#133](https://github.com/riscPrint/risc-v-workstation/issues/133), [#144](https://github.com/riscPrint/risc-v-workstation/issues/144), [#153](https://github.com/riscPrint/risc-v-workstation/issues/153), [#156](https://github.com/riscPrint/risc-v-workstation/issues/156), [#161](https://github.com/riscPrint/risc-v-workstation/issues/161), [#168](https://github.com/riscPrint/risc-v-workstation/issues/168), [#172](https://github.com/riscPrint/risc-v-workstation/issues/172), [#194](https://github.com/riscPrint/risc-v-workstation/issues/194), [#195](https://github.com/riscPrint/risc-v-workstation/issues/195), [#207](https://github.com/riscPrint/risc-v-workstation/issues/207).

Proposed Components row:

| Debug Module campaign commands | `rvw/src/rvw/debug/` | DBG | No new BOOM qualification claimed | Reference Debug Module, DMI/JTAG drivers and trace campaigns. | Experimental; reported evidence: reference model only (Spike/Sail/Python). Scope limits remain in the cited PRs. |

## Native HDL project scaffolds

Path: `rvw/src/rvw/init/`.

Purpose: Generate mapped external-core projects and launchers.

Evidence level: ran on seeded RTL fixture. This is the strongest reported slice, not qualification of the family.

Sources: [#666](https://github.com/riscPrint/risc-v-workstation/pull/666), [#787](https://github.com/riscPrint/risc-v-workstation/pull/787), [#820](https://github.com/riscPrint/risc-v-workstation/pull/820), [#847](https://github.com/riscPrint/risc-v-workstation/pull/847), [#854](https://github.com/riscPrint/risc-v-workstation/pull/854), [#856](https://github.com/riscPrint/risc-v-workstation/pull/856), [#869](https://github.com/riscPrint/risc-v-workstation/pull/869).

Issue association: [#26](https://github.com/riscPrint/risc-v-workstation/issues/26), [#35](https://github.com/riscPrint/risc-v-workstation/issues/35), [#55](https://github.com/riscPrint/risc-v-workstation/issues/55), [#70](https://github.com/riscPrint/risc-v-workstation/issues/70).

Proposed Components row:

| Native HDL project scaffolds | `rvw/src/rvw/init/` | PLAT | No new BOOM qualification claimed | Generate mapped external-core projects and launchers. | Experimental; reported evidence: ran on seeded RTL fixture. Scope limits remain in the cited PRs. |

## Agent trial and evidence benchmark

Path: `rvw/src/rvw/agent_bench/`.

Purpose: Score fixture tasks and run bounded external MCP client trials.

Evidence level: unit tests only. This is the strongest reported slice, not qualification of the family.

Sources: [#806](https://github.com/riscPrint/risc-v-workstation/pull/806), [#809](https://github.com/riscPrint/risc-v-workstation/pull/809), [#817](https://github.com/riscPrint/risc-v-workstation/pull/817), [#830](https://github.com/riscPrint/risc-v-workstation/pull/830).

Issue association: [#27](https://github.com/riscPrint/risc-v-workstation/issues/27), [#106](https://github.com/riscPrint/risc-v-workstation/issues/106), [#364](https://github.com/riscPrint/risc-v-workstation/issues/364), [#366](https://github.com/riscPrint/risc-v-workstation/issues/366).

Proposed Components row:

| Agent trial and evidence benchmark | `rvw/src/rvw/agent_bench/` | PLAT | No new BOOM qualification claimed | Score fixture tasks and run bounded external MCP client trials. | Experimental; reported evidence: unit tests only. Scope limits remain in the cited PRs. |

## MCP profiles and tool catalog

Path: `rvw/src/rvw/mcp/`.

Purpose: Authenticated sessions, profile filtering and common result envelopes.

Evidence level: unit tests only. This is the strongest reported slice, not qualification of the family.

Sources: [#623](https://github.com/riscPrint/risc-v-workstation/pull/623), [#841](https://github.com/riscPrint/risc-v-workstation/pull/841), [#846](https://github.com/riscPrint/risc-v-workstation/pull/846), [#857](https://github.com/riscPrint/risc-v-workstation/pull/857), [#867](https://github.com/riscPrint/risc-v-workstation/pull/867).

Issue association: [#54](https://github.com/riscPrint/risc-v-workstation/issues/54).

Proposed Components row:

| MCP profiles and tool catalog | `rvw/src/rvw/mcp/` | PLAT | No new BOOM qualification claimed | Authenticated sessions, profile filtering and common result envelopes. | Experimental; reported evidence: unit tests only. Scope limits remain in the cited PRs. |

## Cacheless multi-hart example

Path: `examples/smp/`.

Purpose: Run two to eight external VexiiRiscv harts with simulation RAM and devices.

Evidence level: ran on real core RTL. This is the strongest reported slice, not qualification of the family.

Sources: [#835](https://github.com/riscPrint/risc-v-workstation/pull/835).

Issue association: [#90](https://github.com/riscPrint/risc-v-workstation/issues/90).

Proposed Components row:

| Cacheless multi-hart example | `examples/smp/` | VER | No new BOOM qualification claimed | Run two to eight external VexiiRiscv harts with simulation RAM and devices. | Experimental; reported evidence: ran on real core RTL. Scope limits remain in the cited PRs. |

## rvw memory

Path: `rvw/src/rvw/memory/`.

Purpose: Serialized and axiomatic memory observation checks and concurrent campaigns.

Evidence level: ran on real core RTL. This is the strongest reported slice, not qualification of the family.

Sources: [#385](https://github.com/riscPrint/risc-v-workstation/pull/385), [#398](https://github.com/riscPrint/risc-v-workstation/pull/398), [#477](https://github.com/riscPrint/risc-v-workstation/pull/477), [#606](https://github.com/riscPrint/risc-v-workstation/pull/606), [#741](https://github.com/riscPrint/risc-v-workstation/pull/741), [#753](https://github.com/riscPrint/risc-v-workstation/pull/753), [#835](https://github.com/riscPrint/risc-v-workstation/pull/835).

Issue association: [#90](https://github.com/riscPrint/risc-v-workstation/issues/90), [#91](https://github.com/riscPrint/risc-v-workstation/issues/91), [#97](https://github.com/riscPrint/risc-v-workstation/issues/97), [#151](https://github.com/riscPrint/risc-v-workstation/issues/151), [#170](https://github.com/riscPrint/risc-v-workstation/issues/170).

Proposed Components row:

| rvw memory | `rvw/src/rvw/memory/` | VER | No new BOOM qualification claimed | Serialized and axiomatic memory observation checks and concurrent campaigns. | Experimental; reported evidence: ran on real core RTL. Scope limits remain in the cited PRs. |

## rvw privilege

Path: `rvw/src/rvw/privilege/`.

Purpose: Project-owned privilege and interrupt programs with independent observation checks.

Evidence level: reference model only (Spike/Sail/Python). This is the strongest reported slice, not qualification of the family.

Sources: [#393](https://github.com/riscPrint/risc-v-workstation/pull/393), [#428](https://github.com/riscPrint/risc-v-workstation/pull/428), [#466](https://github.com/riscPrint/risc-v-workstation/pull/466), [#791](https://github.com/riscPrint/risc-v-workstation/pull/791), [#812](https://github.com/riscPrint/risc-v-workstation/pull/812), [#821](https://github.com/riscPrint/risc-v-workstation/pull/821), [#836](https://github.com/riscPrint/risc-v-workstation/pull/836), [#860](https://github.com/riscPrint/risc-v-workstation/pull/860).

Issue association: [#112](https://github.com/riscPrint/risc-v-workstation/issues/112), [#138](https://github.com/riscPrint/risc-v-workstation/issues/138), [#139](https://github.com/riscPrint/risc-v-workstation/issues/139), [#149](https://github.com/riscPrint/risc-v-workstation/issues/149), [#176](https://github.com/riscPrint/risc-v-workstation/issues/176).

Proposed Components row:

| rvw privilege | `rvw/src/rvw/privilege/` | VER | No new BOOM qualification claimed | Project-owned privilege and interrupt programs with independent observation checks. | Experimental; reported evidence: reference model only (Spike/Sail/Python). Scope limits remain in the cited PRs. |

## rvw verification-plan

Path: `rvw/src/rvw/verification_plan/`.

Purpose: Versioned extension and environment-control verification plans.

Evidence level: unit tests only. This is the strongest reported slice, not qualification of the family.

Sources: [#403](https://github.com/riscPrint/risc-v-workstation/pull/403), [#631](https://github.com/riscPrint/risc-v-workstation/pull/631).

Issue association: [#155](https://github.com/riscPrint/risc-v-workstation/issues/155), [#177](https://github.com/riscPrint/risc-v-workstation/issues/177), [#178](https://github.com/riscPrint/risc-v-workstation/issues/178), [#296](https://github.com/riscPrint/risc-v-workstation/issues/296).

Proposed Components row:

| rvw verification-plan | `rvw/src/rvw/verification_plan/` | VER | No new BOOM qualification claimed | Versioned extension and environment-control verification plans. | Experimental; reported evidence: unit tests only. Scope limits remain in the cited PRs. |

## Inventory completeness check

Static Git tree comparison against the last main commit before midnight, `324b2958be30578f95312a958615e9061a121f98`, finds 15 new top-level CLI packages: `agent`, `bugmem`, `checks`, `csim`, `evidence`, `fault`, `lsp`, `memory`, `plan`, `privilege`, `probes`, `sec`, `uvm`, `verification_plan`, `vip`. All are listed above. Other entries are new libraries, adapters or major extensions to existing families. No CLI was executed for this check. Issue references above prevent an unsupported claim that every listed family was unsolicited.

## Refresh scope updates

These updates supersede only the matching earlier scope statements. Keep all acceptance cells and milestone assignments unchanged.

| Family | Added evidence | Remaining scope |
|---|---|---|
| Generated checks | [#893](https://github.com/riscPrint/risc-v-workstation/pull/893): 57 bound Vex checks, 49 C1 passes, zero firings. [#921](https://github.com/riscPrint/risc-v-workstation/pull/921): Vexii and stub SoC connected captures; three selected depth-4 passes. | Vexii PC valid-hold fires twice. BOOM [#910](https://github.com/riscPrint/risc-v-workstation/pull/910)/[#929](https://github.com/riscPrint/risc-v-workstation/pull/929) remains source-only, with one historical ID unmapped. [#940](https://github.com/riscPrint/risc-v-workstation/pull/940) adds review metadata, not waivers or passes. |
| Debug | [#896](https://github.com/riscPrint/risc-v-workstation/pull/896): real Vex DMI/JTAG and OpenOCD runs. [#914](https://github.com/riscPrint/risc-v-workstation/pull/914): four RTL ingress cases match C2 and reference trace flow. | Five target deviations; breakpoint stop at target+4 unexplained. No physical JTAG or hardware encoder capture. |
| Security | [#899](https://github.com/riscPrint/risc-v-workstation/pull/899)/[#920](https://github.com/riscPrint/risc-v-workstation/pull/920): real two-core timing/IFT and probe channels. | Vexii remu takes 14 versus 38 cycles. Bounded no_leak_observed results are not security proofs. Cache/TLB channels remain unrun. |
| UVM and VIP | [#903](https://github.com/riscPrint/risc-v-workstation/pull/903): live SV CPU and same-revision C4 accept. [#918](https://github.com/riscPrint/risc-v-workstation/pull/918): 49/50 passes per core; live Vex pyuvm and Vexii capture replay differ. [#944](https://github.com/riscPrint/risc-v-workstation/pull/944)/[#950](https://github.com/riscPrint/risc-v-workstation/pull/950): seeded peripheral/semantic RTL. | ma_data fails on both cores. No live Vexii pyuvm pins or complete physical protocol models. |
| SoC | [#886](https://github.com/riscPrint/risc-v-workstation/pull/886)/[#894](https://github.com/riscPrint/risc-v-workstation/pull/894)/[#915](https://github.com/riscPrint/risc-v-workstation/pull/915): CPU register capture, seven fabric assertions proved, independent peripheral pyuvm reads with a negative control. | Core ingress, connectivity, CDC/RDC and full automatic verification remain open. Peripheral test-master execution is not CPU execution. |
| Multicore | [#917](https://github.com/riscPrint/risc-v-workstation/pull/917)/[#935](https://github.com/riscPrint/risc-v-workstation/pull/935): cacheless two-hart atomics, six litmus outcomes, FENCE.I, IPI and selected HSM; 38 strict Spike matches. | One RVWMO search remains inconclusive at 100000 candidates. No coherent-cache RTL or full SBI qualification. |
| Formal SVA | [#875](https://github.com/riscPrint/risc-v-workstation/pull/875): typed parsing. [#892](https://github.com/riscPrint/risc-v-workstation/pull/892)/[#948](https://github.com/riscPrint/risc-v-workstation/pull/948): emitted forms and module-local defaults. [#923](https://github.com/riscPrint/risc-v-workstation/pull/923)/[#937](https://github.com/riscPrint/risc-v-workstation/pull/937): 34 depth-12 assertion passes, 33 antecedents reached, one not reached. | Six simulation antecedents inactive. No unbounded core proof or full multi-clock/nested composition. [#924](https://github.com/riscPrint/risc-v-workstation/pull/924) core M assertions time out despite arithmetic slice checks. |
| Probes and models | [#938](https://github.com/riscPrint/risc-v-workstation/pull/938)/[#939](https://github.com/riscPrint/risc-v-workstation/pull/939): second-core streams and validation. [#943](https://github.com/riscPrint/risc-v-workstation/pull/943): disabled-probe generated Verilog identical. [#945](https://github.com/riscPrint/risc-v-workstation/pull/945): BOOM 258 RTL cycles versus 96 model cycles. | Vexii retire counter differs by two. Generated equality is static evidence. Timing accuracy stays inconclusive. |
| BOOM state | [#919](https://github.com/riscPrint/risc-v-workstation/pull/919)/[#928](https://github.com/riscPrint/risc-v-workstation/pull/928): small native probes and FP/CSR C2/2 capture. [#934](https://github.com/riscPrint/risc-v-workstation/pull/934): optional DPI source plumbing. | Reset fflags/fcsr disagree with Spike at order zero. Native DPI/fault qualification and wider presets remain open. |
| Integration and replay | [#911](https://github.com/riscPrint/risc-v-workstation/pull/911)/[#922](https://github.com/riscPrint/risc-v-workstation/pull/922): PicoRV32 identity and 46 strict matches. [#926](https://github.com/riscPrint/risc-v-workstation/pull/926): separate scratch core 42 native passes, 41 matches and split-access refusal. [#931](https://github.com/riscPrint/risc-v-workstation/pull/931): relocated offline Vex replay passes 16 checks. | Keep the two core campaigns distinct. Replay executes from reset; no second-machine run or live-state portability. |
| Interfaces | [#876](https://github.com/riscPrint/risc-v-workstation/pull/876)/[#884](https://github.com/riscPrint/risc-v-workstation/pull/884)/[#887](https://github.com/riscPrint/risc-v-workstation/pull/887)/[#916](https://github.com/riscPrint/risc-v-workstation/pull/916) and metadata PRs add jobs, JSON, schema smoke and aliases. [#942](https://github.com/riscPrint/risc-v-workstation/pull/942) removes inapplicable JVM requirements. | Schema smoke runs no handlers. Metadata is not native qualification. Other declaration debt remains. |

## Reviewed delta at 2026-11-13T14:22:26.916089+00:00

These notes supersede only matching earlier scope statements. Historical failures and hand-reviewed fixes remain. No acceptance rule or milestone is changed. All results are reported by PR bodies and were not rerun in this audit.

New or extended families include `examples/naxriscv`, the Spinal source axis, `rvw perf topdown` and function/configuration reports, `rvw sec campaign` and `model-check`, `rvw cov source-report`, `probe-goals` and `smoke`, `rvw_tools_load`, `rvw checks plan`, generic ACT4 profiles, `rvw regress instruction-feed`, external-interrupt evidence replay, SoC watchdog/block/UART/flash profiles, and SystemC multi-initiator memory. Existing Components proposals must retain these limits. No new tracker or milestone is inferred from a command.

| Family | Added reported evidence | Remaining scope | Sources |
|---|---|---|---|
| Core integration | NaxRiscv has 59 ISA passes and native probes, nine-rule seed-1 checks, Kanata and selected fault controls. Chisel and VHDL each have 41 strict matches and one ma_data failure/timeout. | Nax unseeded check firings, RAM-state/data/recovery checks and orphan events remain. Non-Spinal fault mapping and full ISA qualification remain open. | [#979](https://github.com/riscPrint/risc-v-workstation/pull/979), [#1108](https://github.com/riscPrint/risc-v-workstation/pull/1108), [#1127](https://github.com/riscPrint/risc-v-workstation/pull/1127), [#1131](https://github.com/riscPrint/risc-v-workstation/pull/1131), [#1143](https://github.com/riscPrint/risc-v-workstation/pull/1143), [#1150](https://github.com/riscPrint/risc-v-workstation/pull/1150) |
| BOOM | Small has four FP/CSR matches with explicit initial FCSR alignment, retained prediction probes, register flips and a clean 218-instruction DPI match. | SFB endpoint differs by one. Wider presets, checkpoint restore, plugin bindings and model accuracy remain open. | [#961](https://github.com/riscPrint/risc-v-workstation/pull/961), [#1091](https://github.com/riscPrint/risc-v-workstation/pull/1091), [#1101](https://github.com/riscPrint/risc-v-workstation/pull/1101), [#1103](https://github.com/riscPrint/risc-v-workstation/pull/1103), [#1116](https://github.com/riscPrint/risc-v-workstation/pull/1116) |
| Generated checks | Cancellation fixes give 51 Vexii passes with zero firings. Activation follow-up adds 20 simulation activations and 13 conditional unreachability results. | Five original activation gaps and new backpressure failures remain. Bounded engine observations without reached triggers are not activated passes. One historical BOOM ID remains missing. | [#1107](https://github.com/riscPrint/risc-v-workstation/pull/1107), [#1122](https://github.com/riscPrint/risc-v-workstation/pull/1122), [#1136](https://github.com/riscPrint/risc-v-workstation/pull/1136), [#1144](https://github.com/riscPrint/risc-v-workstation/pull/1144) |
| Formal ISA | M-only MPP update and MEPC bit-zero readback have defect dispositions. Pico has 40 finite matches and two unsupported profiles. Conditional LUI model proof is retained. | 37 later instruction portfolio attempts add zero proofs. Twenty CSR bindings, observer conformance and full pipeline signoff remain open. | [#967](https://github.com/riscPrint/risc-v-workstation/pull/967), [#1035](https://github.com/riscPrint/risc-v-workstation/pull/1035), [#1061](https://github.com/riscPrint/risc-v-workstation/pull/1061), [#1070](https://github.com/riscPrint/risc-v-workstation/pull/1070), [#1074](https://github.com/riscPrint/risc-v-workstation/pull/1074), [#1117](https://github.com/riscPrint/risc-v-workstation/pull/1117), [#1134](https://github.com/riscPrint/risc-v-workstation/pull/1134), [#1139](https://github.com/riscPrint/risc-v-workstation/pull/1139) |
| Datapath and equivalence | Real extracted unit proofs, reduced operand partitions, RAM/vector FIFO equivalence and a payload-corruption control have receipts. | Optional DivRadix2 has a concrete mismatch. Default divider zero-divisor proof is separate. Partial operands and small widths do not prove unrestricted whole units or cores. | [#1053](https://github.com/riscPrint/risc-v-workstation/pull/1053), [#1076](https://github.com/riscPrint/risc-v-workstation/pull/1076), [#1125](https://github.com/riscPrint/risc-v-workstation/pull/1125), [#1146](https://github.com/riscPrint/risc-v-workstation/pull/1146), [#1155](https://github.com/riscPrint/risc-v-workstation/pull/1155) |
| MMU and interrupts | RV32 PMP has 394 strict matches. Twelve fresh PLIC traces now match with checked ordered device evidence, no masks or synchronization. Eight random privilege runs match. | Nineteen PMP-denied walks and three interrupt mtval failures are core findings. Reset-event binding and unsupported modes remain open. | [#1111](https://github.com/riscPrint/risc-v-workstation/pull/1111), [#1121](https://github.com/riscPrint/risc-v-workstation/pull/1121), [#1124](https://github.com/riscPrint/risc-v-workstation/pull/1124), [#1128](https://github.com/riscPrint/risc-v-workstation/pull/1128), [#1147](https://github.com/riscPrint/risc-v-workstation/pull/1147) |
| ACT4 | Instruction campaigns give 52 passing VexRiscv and 58 passing Vexii cases with strict matches. Functional merges retain observed and qualified populations separately. | Six Vex MEPC failures remain. All 270 supervisor cases fail in bootstrap. Only 37 representative reference checks ran; 233 are NOT RUN. BOOM is config/unit-test only. | [#1100](https://github.com/riscPrint/risc-v-workstation/pull/1100), [#1148](https://github.com/riscPrint/risc-v-workstation/pull/1148), [#1153](https://github.com/riscPrint/risc-v-workstation/pull/1153), [#1156](https://github.com/riscPrint/risc-v-workstation/pull/1156), [#1161](https://github.com/riscPrint/risc-v-workstation/pull/1161) |
| SMP | Cacheless stress, serialized full-program replay and N=2..8 races/replay have native results. Cached two-hart RTL handoff has one-line byte checks and monitor replay. | Simulation PLIC races do not qualify RTL PLIC. Cached in-simulation SV bind is NOT RUN. Full coherence and RVWMO qualification remain open. | [#1012](https://github.com/riscPrint/risc-v-workstation/pull/1012), [#1027](https://github.com/riscPrint/risc-v-workstation/pull/1027), [#1115](https://github.com/riscPrint/risc-v-workstation/pull/1115), [#1133](https://github.com/riscPrint/risc-v-workstation/pull/1133), [#1154](https://github.com/riscPrint/risc-v-workstation/pull/1154) |
| Devices and boot | Live Vexii UART/CLINT/PLIC and an OpenSBI supervisor payload run. SystemC has a native multi-initiator example and RTL bridge. | Linux times out after 600 seconds with empty UART, no completed boot and no C2. Checkpoint restore remains absent. TLM effects occur at call time. | [#1018](https://github.com/riscPrint/risc-v-workstation/pull/1018), [#1119](https://github.com/riscPrint/risc-v-workstation/pull/1119), [#1162](https://github.com/riscPrint/risc-v-workstation/pull/1162) |
| SoC and VIP | Scoped source-cut connectivity proofs, protocol/register consumers, UART, block device and SPI ROM-copy boot have native controls. Repaired SV fixtures pass their declared matrix. | CDC/RDC has 2507 findings. Peripheral masters are not CPUs. Four inert model stubs, physical protocols, complete UART compliance and full SoC acceptance remain open. | [#987](https://github.com/riscPrint/risc-v-workstation/pull/987), [#1008](https://github.com/riscPrint/risc-v-workstation/pull/1008), [#1063](https://github.com/riscPrint/risc-v-workstation/pull/1063), [#1083](https://github.com/riscPrint/risc-v-workstation/pull/1083), [#1112](https://github.com/riscPrint/risc-v-workstation/pull/1112) |
| Coverage and feed | Native point/source reports, probe goals, suite minimisation and offline independent instruction-feed controls run on both examples. | Single-seed directed closure does not beat random. Smoke earns no new coverage credit. Live TestRIG transport, operand holes and full statement attribution remain open. | [#994](https://github.com/riscPrint/risc-v-workstation/pull/994), [#1022](https://github.com/riscPrint/risc-v-workstation/pull/1022), [#1081](https://github.com/riscPrint/risc-v-workstation/pull/1081), [#1114](https://github.com/riscPrint/risc-v-workstation/pull/1114), [#1145](https://github.com/riscPrint/risc-v-workstation/pull/1145) |
| Timing and probes | Cached data observers, branch target categories, Nax function comparisons and project-bound causal/dependency events have measured slices. | Timing accuracy stays inconclusive. Nax training error worsens to 20.7%; original held-out error is 13.0%. Vexii commit-port/C2 tail boundaries remain different. | [#1098](https://github.com/riscPrint/risc-v-workstation/pull/1098), [#1138](https://github.com/riscPrint/risc-v-workstation/pull/1138), [#1141](https://github.com/riscPrint/risc-v-workstation/pull/1141), [#1142](https://github.com/riscPrint/risc-v-workstation/pull/1142), [#1149](https://github.com/riscPrint/risc-v-workstation/pull/1149), [#1151](https://github.com/riscPrint/risc-v-workstation/pull/1151) |
| Security | Real paired campaigns find Vexii div/remu signatures. Memory/CSR bindings and PMP variant runs add bounded observations. | Model-check uses Spike/model predictions. No_leak_observed is not proof. X candidates remain unconfirmed; async-reset guards refuse unsupported semantics. | [#955](https://github.com/riscPrint/risc-v-workstation/pull/955), [#958](https://github.com/riscPrint/risc-v-workstation/pull/958), [#959](https://github.com/riscPrint/risc-v-workstation/pull/959), [#968](https://github.com/riscPrint/risc-v-workstation/pull/968), [#1025](https://github.com/riscPrint/risc-v-workstation/pull/1025), [#1036](https://github.com/riscPrint/risc-v-workstation/pull/1036), [#1140](https://github.com/riscPrint/risc-v-workstation/pull/1140) |
| Farm and agent | Queued native shards, failure signatures, dashboards, budgets and a prepared tiny-core bring-up walk add measured slices. | Eight-test ranking misses the planted fault. Safe selection falls back to all 49. No C4 cost/acceptance, Kubernetes runtime or LLM repair success is inferred. | [#966](https://github.com/riscPrint/risc-v-workstation/pull/966), [#1031](https://github.com/riscPrint/risc-v-workstation/pull/1031), [#1057](https://github.com/riscPrint/risc-v-workstation/pull/1057), [#1067](https://github.com/riscPrint/risc-v-workstation/pull/1067), [#1090](https://github.com/riscPrint/risc-v-workstation/pull/1090), [#1109](https://github.com/riscPrint/risc-v-workstation/pull/1109) |
| Evidence and CI | Shared CSR catalog, MCP metadata and weakest-input verdict fixes have unit/static evidence. Suite repair reports retain exact component results. | CI plans are not workflow runs. Linux is disabled and untested. Remaining UVM random-data, slang SVA and Spike PLIC failures remain. Full rebased-main suite was NOT RUN. | [#1092](https://github.com/riscPrint/risc-v-workstation/pull/1092), [#1099](https://github.com/riscPrint/risc-v-workstation/pull/1099), [#1123](https://github.com/riscPrint/risc-v-workstation/pull/1123), [#1152](https://github.com/riscPrint/risc-v-workstation/pull/1152), [#1160](https://github.com/riscPrint/risc-v-workstation/pull/1160) |

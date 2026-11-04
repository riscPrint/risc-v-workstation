# SpinalTrace GUI

The SpinalTrace front-end is written in Rust using the Tauri framework. For build instructions, please refer to the readme of the repository root.

This GUI is forked from the ChiselTrace GUI, which is part of the ChiselTrace project.

The graph shows `Trace accuracy` above the nodes. Expand the status to read the
limits. The status stays visible when you change the graph head or hierarchy groups.
`approximate` and `incomplete` results must not be used as exact dependency traces.

## Limit ownership

Viewer node identity: [#113](https://github.com/riscPrint/risc-v-workstation/issues/113). Source grouping and accuracy display: [#94](https://github.com/riscPrint/risc-v-workstation/issues/94). Integrated navigation: [#24](https://github.com/riscPrint/risc-v-workstation/issues/24).

Retained limit: Grouped graph conversion copies data. Source paths need local files. No graph-representation rewrite or portable source bundle is promised.

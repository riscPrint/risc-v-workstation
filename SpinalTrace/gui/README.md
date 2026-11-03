# SpinalTrace GUI

The SpinalTrace front-end is written in Rust using the Tauri framework. For build instructions, please refer to the readme of the repository root.

This GUI is forked from the ChiselTrace GUI, which is part of the ChiselTrace project.

The graph shows `Trace accuracy` above the nodes. Expand the status to read the
limits. The status stays visible when you change the graph head or hierarchy groups.
`approximate` and `incomplete` results must not be used as exact dependency traces.

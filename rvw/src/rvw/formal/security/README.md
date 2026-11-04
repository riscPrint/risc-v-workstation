# Hardware leakage checks

This increment targets #20. It uses a hardware threat model separate from C8.
Assets are secret input registers. The attacker controls public inputs and sees
selected digital observations. The trusted boundary contains the reference model,
reset procedure and observation adapter. Keys, analog power, noise and tool-input
attacks are outside this model.

The IFT transform accepts a flattened Yosys JSON netlist after `techmap; simplemap`.
It adds `__t` ports and value-sensitive taint transfer logic. It tracks data and
mux control flow through Boolean gates and rising-edge registers. Clock is public.
Apply a public reset before observation. No implicit state initialization or
implicit declassification occurs. Unsupported cells, blackboxes, X/Z constants,
multiple clocks and undriven bits cause an error. No structural path is a proof.
Reconvergent paths can overtaint because the transform loses correlations.

This is an external Yosys netlist transform, not the upstream CellIFT pass.

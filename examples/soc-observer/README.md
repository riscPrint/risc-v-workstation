# RTL transaction observer binding

`binding.json` is a template for a single-beat, single-hart project monitor.
The signal names match the native bridge fixture in
`rvw/tests/test_soc_observer.py`. Replace them for a real core project.
`retire_valid` must select memory retirements. Do not infer `retire_tag` from
addresses or C2 records. Use an independently observed transaction identity.

Generate with `rvw soc observe --binding binding.json --out observer`.
The SoC command README gives simulation plusargs and packaging commands.
A native fixture check does not qualify a core or execute an ELF.

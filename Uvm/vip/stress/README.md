# Memory-controller and NoC stress agents

Python supplies seeded abstract service and independent request/response
checks. Configure latency, jitter, service bandwidth, refresh-like pauses,
credits per source and a maximum response wait. QoS selects service
priority. The wait bound applies to every source and QoS class. A starving
low-priority request fails rather than being hidden by aggregate bandwidth.
Requests use word addresses and abstract 64-bit data. Out-of-range accesses
return errors. Writes take effect at acceptance in this abstract model.

SV provides an event bridge with stimulus, driver, monitor, QoS coverage
and a reference scoreboard. It supports four sources, 16 IDs per source,
four credits and 64 words. Request and response events share the bridge.
The fixture forwards events; `+buggy` changes data. A project must translate
its native bus and actual service behavior into these events. The SV
fixture is not a NoC or DRAM controller. Python's scheduler is not RTL.

Run `rvw/.venv/bin/python -m pytest rvw/tests/test_vip_stress.py -q`.
Lint the four SV files with pinned UVM. Native controller/NoC campaigns,
UVM runtime builds and electrical memory validation were not run.

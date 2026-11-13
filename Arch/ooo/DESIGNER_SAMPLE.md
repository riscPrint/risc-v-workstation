# Designer report sample

Model IPC: 0.2926. Evidence: model-only.

| Workload | Instructions | Cycles | IPC |
|---|---:|---:|---:|
| chain | 1010 | 2417 | 0.4179 |
| multiply | 1010 | 2417 | 0.4179 |
| memory | 1010 | 2417 | 0.4179 |
| independent | 1010 | 2417 | 0.4179 |
| divide | 1010 | 8216 | 0.1229 |
| branch | 1110 | 3167 | 0.3505 |

## Functions in chain

| Function | Retiring | Front end | Bad speculation | Memory | Core |
|---|---:|---:|---:|---:|---:|
| &lt;unmapped&gt; | 47.6% | 28.6% | 0.0% | 0.0% | 23.8% |
| kernel | 41.7% | 12.4% | 24.9% | 0.0% | 20.9% |


## Functions in multiply

| Function | Retiring | Front end | Bad speculation | Memory | Core |
|---|---:|---:|---:|---:|---:|
| &lt;unmapped&gt; | 47.6% | 28.6% | 0.0% | 0.0% | 23.8% |
| kernel | 41.7% | 12.4% | 20.8% | 0.0% | 25.0% |


## Functions in memory

| Function | Retiring | Front end | Bad speculation | Memory | Core |
|---|---:|---:|---:|---:|---:|
| &lt;unmapped&gt; | 50.0% | 25.0% | 0.0% | 5.0% | 20.0% |
| kernel | 41.7% | 8.3% | 24.9% | 25.0% | 0.0% |


## Functions in independent

| Function | Retiring | Front end | Bad speculation | Memory | Core |
|---|---:|---:|---:|---:|---:|
| &lt;unmapped&gt; | 47.6% | 28.6% | 0.0% | 0.0% | 23.8% |
| kernel | 41.7% | 12.4% | 24.9% | 0.0% | 20.9% |


## Functions in divide

| Function | Retiring | Front end | Bad speculation | Memory | Core |
|---|---:|---:|---:|---:|---:|
| &lt;unmapped&gt; | 55.6% | 27.8% | 0.0% | 0.0% | 16.7% |
| kernel | 12.2% | 0.0% | 4.9% | 0.0% | 82.9% |


## Functions in branch

| Function | Retiring | Front end | Bad speculation | Memory | Core |
|---|---:|---:|---:|---:|---:|
| &lt;unmapped&gt; | 47.6% | 28.6% | 0.0% | 0.0% | 23.8% |
| kernel | 35.0% | 15.8% | 28.5% | 0.0% | 20.7% |


## Structures to inspect

- latencies.divide: elasticity 0.33250207813799065.
- frontend.fetch_latency: elasticity 0.2769302615193025.
- branch_penalty: elasticity 0.19648732094953744.
- latencies.load: elasticity 0.0.
- rob_entries: elasticity 0.0.

## Next three changes to try

- {"branch_penalty": {"after": 1, "before": 3}, "frontend.fetch_latency": {"after": 1, "before": 3}}: model speedup 1.262.
- {"branch_penalty": {"after": 1, "before": 3}, "frontend.fetch_latency": {"after": 2, "before": 3}}: model speedup 1.262.
- {"branch_penalty": {"after": 1, "before": 3}}: model speedup 1.140.

Model results need RTL checks. Function rows use ELF symbols when supplied.

This sample uses six RTL-captured RV32IM kernel paths from the correlation experiment.
These timings are model predictions. They are not measured RTL IPC.

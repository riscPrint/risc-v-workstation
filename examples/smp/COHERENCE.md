# Cache and coherence scope

The cacheless C1 SMP profiles use `FetchCachelessPlugin` and `LsuCachelessPlugin`.
Those profiles have no instruction cache, data cache or shared coherent cache.
The top exports one native fetch bus and one native LSU bus per hart.
The simulation harness supplies shared RAM, atomic service and devices.

| Observer | Binding in this example | Reason |
|---|---|---|
| Cache and coherence observers | Unbound | No cache state, cache line or coherence permission signals exist. |
| TileLink-C monitor | Unbound | The native LSU bus has no B, C or E channels, probes, grants or permission transfers. |

The C1 result declares `details.cache_coherence` as `not_present`.
A passing program does not turn that field into coherence evidence.
The TileLink transfer descriptions in PMA configuration describe access
permissions. They do not create a TileLink port or a coherence fabric.

LR/SC, AMO, shared-memory, instruction-visibility and lifecycle results apply
to these cacheless RTL cores and their simulation memory service. The scalar
RVWMO checker uses captured physical memory effects and syntactic dependencies.
Those results do not qualify MESI, MOESI or a cache/home implementation.

A coherent-cache configuration needs a new project binding for the real cache
and protocol signals. It must also provide independent expected line data and
explicit service bounds. The existing harness requires the cacheless LSU
plugin. Do not map its native request/response fields onto TileLink-C channels.

## Separate cached path

`rvw/CachedSmpTop` hosts two real cached VexiiRiscv cores and the upstream
TileLink hub. See the cached SMP section in `README.md` for native commands,
the selected data-line oracle, permission observers and generated monitor
binding. This path is separate from the cacheless C1 adapter. Its observations
do not change the cacheless adapter's `cache_coherence: not_present` field.

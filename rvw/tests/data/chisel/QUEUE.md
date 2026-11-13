# Chisel Queue fixture

`Queue.scala` wraps the Chisel 6.5.0 standard `Queue` with 8-bit data and four
entries. Generate `QueueTop.fir` by running this command in this directory:

```sh
scala-cli run Queue.scala --server=false
```

The Scala, Chisel and compiler plugin versions are pinned in the source.
The generated artifact preserves source information for the wrapper and the
standard Queue and Counter implementations. The native test lowers this artifact
with firtool and compares nine path queries with an independent emitted RTL
traversal. No Scala build is needed to run that test.

To check standard-library source mappings, set `RVW_CHISEL_SOURCE` to an external
source tree with `src/main/scala/chisel3/util/Decoupled.scala` and `Counter.scala`
from the Chisel 6.5.0 sources artifact. Maven coordinate:
`org.chipsalliance:chisel_2.13:6.5.0:sources`.
The sources JAR SHA-256 used for the native check was
`7cdd09c56eca4096e44620724c1cee8ffd8e93fa31ac360bb5e334460b044d57`.
Absent library sources do not create a claimed library source binding.

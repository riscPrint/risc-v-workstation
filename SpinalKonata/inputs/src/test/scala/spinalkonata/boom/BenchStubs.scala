// Test-only BOOM seam. Compile the real BenchTrace orchestration without core builds.
package boom.common {
  object BoomConfigs { def small(): Int = 0; def large(): Int = 1 }
}
package boom.sim {
  object BoomSim {
    sealed trait Result
    case object Pass extends Result
    case class Fail(code: Long) extends Result
    case object Timeout extends Result
    case class RvfiError(code: Int) extends Result
    var outcome: Result = Pass
    var beforeCompile: () => Unit = () => ()
    def compile(params: Int, config: String, konata: Boolean): Unit = beforeCompile()
  }
}
package spinalkonata.boom {
  object ProbeRun {
    var loaded: Array[Byte] = Array.emptyByteArray
    private def finish(elf: Array[Byte], konata: Option[java.io.File], onFinish: (Long, Long) => Unit): boom.sim.BoomSim.Result = {
      loaded = elf
      konata.foreach(f => java.nio.file.Files.writeString(f.toPath, "Kanata\t0004\nC=\t0\n"))
      onFinish(2, 1)
      boom.sim.BoomSim.outcome
    }
    def run(compiled: Unit, elfPath: String, maxCycles: Long, seed: Int,
            konata: Option[java.io.File], memLatency: Option[Int], onFinish: (Long, Long) => Unit): boom.sim.BoomSim.Result =
      finish(java.nio.file.Files.readAllBytes(java.nio.file.Paths.get(elfPath)), konata, onFinish)
    def run(compiled: Unit, elf: riscvsim.ElfFile, disassembly: Map[BigInt, (Long, String)], maxCycles: Long, seed: Int,
            konata: Option[java.io.File], memLatency: Option[Int], onFinish: (Long, Long) => Unit): boom.sim.BoomSim.Result =
      finish(elf.bytes, konata, onFinish)
  }
}

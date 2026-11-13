package rvwvex

import spinal.core._
import vexriscv.VexRiscv
import vexriscv.plugin._
import spinalchecks._

/** Project-owned bindings for this M-only, no-debug configuration. */
class HpmChecksPlugin extends Plugin[VexRiscv] {
  override def build(pipeline: VexRiscv): Unit = {
    val csr = pipeline.config.get(classOf[CsrPlugin])
    require(csr.config.mcycleAccess == CsrAccess.READ_WRITE && csr.config.minstretAccess == CsrAccess.READ_WRITE,
      "counter callbacks require the existing writable machine interfaces")
    require(!csr.config.withPrivilegedDebug, "debug stopcount needs a separate event binding")
    def readHalf(address: Int): Bits = {
      val fields = csr.csrMapping.mapping(address).collect { case r: CsrRead => r }
      require(fields.nonEmpty, s"no readable counter half at $address")
      val bits = Bits(32 bits).allowOverride
      bits := 0
      for (r <- fields) bits(r.bitOffset, r.that.getBitsWidth bits) := r.that.asBits
      bits
    }
    def counter(name: String, low: Int, high: Int, event: UInt, meaning: String): Unit = {
      val observed = (readHalf(high) ## readHalf(low)).asUInt
      val writeLow = csr.isWriting(low)
      val writeHigh = csr.isWriting(high)
      val data = Mux(writeHigh, csr.writeData() ## B(0, 32 bits), B(0, 32 bits) ## csr.writeData()).asUInt
      val mask = Mux(writeHigh, B(BigInt("ffffffff00000000", 16), 64 bits), B(BigInt("ffffffff", 16), 64 bits)).asUInt
      HpmChecks.bind(name, HpmModel(1, 64, 0, meaning), observed, event, False, True,
        writeLow || writeHigh, data, mask)
    }
    counter("mcycle", 0xb00, 0xb80, U(1, 1 bits), "one active core clock sample; debug is disabled")
    counter("minstret", 0xb02, 0xb82, pipeline.stages.last.arbitration.isFiring.asUInt,
      "last pipeline stage isFiring; not inferred from counter storage")
  }
}

object HpmChecksMain {
  def main(args: Array[String]): Unit = {
    require(args.length == 1, "usage: HpmChecksMain output-directory")
    val core = VexTop.configuration()
    core.plugins += new HpmChecksPlugin
    val (config, _) = SpinalChecks.install(VexTop.spinalConfig.copy(targetDirectory = args(0)).includeFormal,
      ChecksConfig(enable = Seq("hpm.*"), reportPath = args(0) + "/checks.json"))
    config.generateVerilog(new VexRiscv(core))
  }
}

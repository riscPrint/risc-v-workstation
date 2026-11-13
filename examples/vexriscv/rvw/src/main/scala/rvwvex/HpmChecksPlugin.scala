package rvwvex

import spinal.core._
import vexriscv.VexRiscv
import vexriscv.plugin._
import spinalchecks._

/** Project-owned bindings for this M-only, no-debug configuration. */
class HpmChecksPlugin(observationFault: Boolean = false, readObservationFault: Boolean = false) extends Plugin[VexRiscv] {
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
      val checked = if (observationFault) observed ^ U(1, 64 bits) else observed
      val expected = HpmChecks.track(name, HpmModel(1, 64, 0, meaning), checked, event, False, True,
        writeLow || writeHigh, data, mask)
      def reads(label: String, lo: Int, hi: Int): Unit = {
        require(Seq(lo, hi).forall(a => csr.csrMapping.mapping.get(a).exists(_.exists(_.isInstanceOf[CsrRead]))),
          "read callbacks require existing counter mappings")
        val readLow = csr.isReading(lo)
        val readHigh = csr.isReading(hi)
        val response = if (readObservationFault) csr.readData() ^ B(1, 32 bits) else csr.readData()
        HpmChecks.bindHalfRead(name + "_" + label, expected, readHigh, response, readLow || readHigh)
      }
      reads("machine", low, high)
      reads("user", low + 0x100, high + 0x100)
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

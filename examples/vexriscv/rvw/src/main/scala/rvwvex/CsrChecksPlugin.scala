package rvwvex

import spinal.core._
import vexriscv.VexRiscv
import vexriscv.plugin._

/** Optional project binding. The normal adapter does not install this plugin. */
class CsrChecksPlugin(model: spinalchecks.CsrModel, observationFault: Boolean = false) extends Plugin[VexRiscv] {
  override def build(pipeline: VexRiscv): Unit = {
    val csr = pipeline.config.get(classOf[CsrPlugin])
    val fields = csr.csrMapping.mapping(0x340).collect { case r: CsrRead => r }
    require(fields.nonEmpty, "mscratch has no readable storage")
    val observed = Bits(32 bits).allowOverride
    observed := 0
    for (r <- fields) observed(r.bitOffset, r.that.getBitsWidth bits) := r.that.asBits
    // isWriting/isReading use the plugin's onWrite/onRead callbacks. These fire
    // on accepted CSR accesses, not when an instruction is merely decoded.
    val write = csr.isWriting(0x340)
    val read = csr.isReading(0x340)
    val checked = if (observationFault) observed ^ B(1, 32 bits) else observed
    spinalchecks.CsrChecks.bind("mscratch", model,
      checked, read, write, csr.writeData(), U(3, 2 bits), False,
      B(0, 32 bits), B(0, 32 bits), csr.readData())
  }
}

object CsrChecksPlugin {
  def loadModel(file: String): spinalchecks.CsrModel = {
    val source = scala.io.Source.fromFile(file)
    val model = try ujson.read(source.mkString) finally source.close()
    require(model("schema").str == "rvw.csr/1" && model("xlen").num == 32)
    val scratch = model("csrs").arr.find(_("name").str == "mscratch").get
    require(scratch("address").num == 0x340 && scratch("privilege").str == "M")
    val fields = scratch("fields").arr
    require(fields.size == 1 && fields.head("lsb").num == 0 && fields.head("width").num == 32)
    require(fields.head("access")("M").str == "RW" && !scratch.obj.get("read_only").exists(_.bool))
    require(!fields.head.obj.get("effect").exists(_.str != "none"))
    spinalchecks.CsrModel(version = 1, width = 32,
      reset = BigInt(scratch("reset").num.toLong), writeMask = BigInt("ffffffff", 16),
      minPrivilege = 3, resetKnown = scratch.obj.get("reset_known").forall(_.bool))
  }
}

object CsrChecksMain {
  def main(args: Array[String]): Unit = {
    require(args.length == 2, "usage: CsrChecksMain output-directory generated-model.json")
    val spec = CsrChecksPlugin.loadModel(args(1))
    val config = VexTop.configuration()
    config.plugins += new CsrChecksPlugin(spec)
    val (spinal, _) = spinalchecks.SpinalChecks.install(
      VexTop.spinalConfig.copy(targetDirectory = args(0)).includeFormal,
      spinalchecks.ChecksConfig(enable = Seq("csr.*"), reportPath = args(0) + "/checks.json"))
    spinal.generateVerilog(new VexRiscv(config))
  }
}

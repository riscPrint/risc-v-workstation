package examplesocdebug
import spinal.core._
import rvwvex.{VexDebug,DmiPortPlugin,JtagDebugPlugin}

class DmiCore extends examplesocvex.VexCore(Some(VexDebug.configuration("rv32im_dmi"))) {
  val debug=area.cpu.config.get(classOf[DmiPortPlugin])
  val dmi=debug.dmi.toIo()
  val ndmreset=debug.ndmreset.toIo()
}
class JtagCore extends examplesocvex.VexCore(Some(VexDebug.configuration("rv32im_jtag"))) {
  val debug=area.cpu.config.get(classOf[JtagDebugPlugin])
  val jtag=debug.jtag.toIo()
  val ndmreset=debug.ndmreset.toIo()
}

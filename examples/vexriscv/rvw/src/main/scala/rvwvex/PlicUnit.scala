package rvwvex

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._
import spinal.lib.misc.plic._

/** Unmodified library PLIC, two contexts and three level-sensitive sources. */
class PlicUnit extends Component {
  val io = new Bundle {
    val bus = slave(Apb3(Apb3Config(addressWidth = 22, dataWidth = 32)))
    val sources = in Bits(3 bits)
    val irq = out Bits(2 bits)
  }
  val gateways = (1 to 3).map(id => PlicGatewayActiveHigh(io.sources(id - 1), id, 3))
  val targets = (0 to 1).map(id => PlicTarget(id, gateways, 3))
  PlicMapper(Apb3SlaveFactory(io.bus), PlicMapping.sifive)(gateways, targets)
  for (id <- 0 to 1) io.irq(id) := targets(id).iep
}

object PlicUnit {
  def main(args: Array[String]): Unit = {
    SpinalConfig(targetDirectory = args(0), defaultConfigForClockDomains =
      ClockDomainConfig(resetKind = SYNC)).generateVerilog(new PlicUnit)
  }
}

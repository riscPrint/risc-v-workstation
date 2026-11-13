package rvwsoc

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._
import spinal.lib.bus.misc.SizeMapping

/** Actual fabric with unconstrained requests and peripheral responses.
  * No core or peripheral state is part of this decode-only proof target.
  * APB temporal checks need legal-master assumptions and are separate.
  */
class FabricProof(windows: Seq[SizeMapping]) extends Component {
  require(windows.nonEmpty)
  val config = Apb3Config(32, 32)
  val io = new Bundle {
    val bus = slave(Apb3(config))
    val targets = Vec(master(Apb3(config)), windows.size)
  }
  Fabric.connect(io.bus, io.targets.toSeq.zip(windows), checkProtocol = false)
}

object FabricProofGenerate extends App {
  require(args.length >= 2, "output directory and base:size windows required")
  val windows = args.drop(1).map { arg =>
    val pair = arg.split(":")
    require(pair.length == 2)
    SizeMapping(BigInt(pair(0), 16), BigInt(pair(1), 16))
  }.toSeq
  SpinalConfig(targetDirectory = args(0),
    defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC))
    .generateVerilog(new FabricProof(windows))
}

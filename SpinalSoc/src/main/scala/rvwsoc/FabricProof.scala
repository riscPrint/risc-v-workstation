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

/** Bounded protocol checks under an explicit legal APB master contract. */
class FabricProtocolProof(windows: Seq[SizeMapping]) extends Component {
  val config = Apb3Config(32, 32)
  val io = new Bundle {
    val bus = slave(Apb3(config))
    val targets = Vec(master(Apb3(config)), windows.size)
  }
  val selected = io.bus.PSEL.orR
  val previousSelect = RegNext(selected) init(False)
  val previousEnable = RegNext(io.bus.PENABLE) init(False)
  val completed = RegNext(selected && io.bus.PENABLE && io.bus.PREADY) init(False)
  val waiting = RegNext(selected && io.bus.PENABLE && !io.bus.PREADY) init(False)
  val payload = io.bus.PADDR.asBits ## io.bus.PWRITE.asBits ## io.bus.PWDATA
  val previousPayload = RegNext(payload)
  assume(!io.bus.PENABLE || selected)
  when(io.bus.PENABLE) { assume(previousSelect) }
  when(previousSelect && !previousEnable) { assume(selected && io.bus.PENABLE) }
  when(completed) { assume(!selected || !io.bus.PENABLE) }
  when(waiting) { assume(selected && io.bus.PENABLE) }
  when((previousSelect && !previousEnable) || waiting) { assume(payload === previousPayload) }
  Fabric.connect(io.bus, io.targets.toSeq.zip(windows))
}

object FabricProtocolProofGenerate extends App {
  val windows = args.drop(1).map { arg =>
    val pair = arg.split(":")
    SizeMapping(BigInt(pair(0), 16), BigInt(pair(1), 16))
  }.toSeq
  SpinalConfig(targetDirectory = args(0),
    defaultConfigForClockDomains = ClockDomainConfig(resetKind = SYNC))
    .includeFormal.generateVerilog(new FabricProtocolProof(windows))
}

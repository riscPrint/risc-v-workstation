package examplesocdma

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba4.axi._
import spinal.lib.bus.misc.SizeMapping
import rvwsoc._

/** Project traffic generator: write/read 32 words, then publish a marker. */
class DmaTraffic(config: Axi4Config) extends Component {
  require(config.dataWidth==32 && config.useId && config.useResp)
  val io=new Bundle {
    val bus=master(Axi4(config))
    val done,error=out Bool()
    val writes,reads=out UInt(8 bits)
  }
  val state=Reg(UInt(3 bits)) init(0)
  val index=Reg(UInt(6 bits)) init(0)
  val awSent,wSent=Reg(Bool()) init(False)
  val error=Reg(Bool()) init(False)
  val writes,reads=Reg(UInt(8 bits)) init(0)
  val address=(U(0x80001000L,32 bits)+(index.resize(32)<<2)).resized
  val value=Mux(index===32,B(0x600dffffL,32 bits),(U(0x600d0000L,32 bits)+index.resize(32)).asBits)
  for(ax <- Seq[Axi4Ax](io.bus.aw.payload,io.bus.ar.payload)) {
    ax.assignFromBits(B(0,ax.getBitsWidth bits))
    ax.addr.removeAssignments() := address
    ax.id.removeAssignments() := 1
    if(config.useSize) ax.size.removeAssignments() := 2
    if(config.useBurst) ax.burst.removeAssignments() := B(1,2 bits)
  }
  io.bus.w.payload.assignFromBits(B(0,io.bus.w.payload.getBitsWidth bits))
  io.bus.w.data.removeAssignments() := value
  if(config.useStrb) io.bus.w.strb.removeAssignments() := 15
  if(config.useLast) io.bus.w.last.removeAssignments() := True
  io.bus.aw.valid:=state===0 && !awSent
  io.bus.w.valid:=state===0 && !wSent
  io.bus.b.ready:=state===1
  io.bus.ar.valid:=state===2
  io.bus.r.ready:=state===3
  when(io.bus.aw.fire) { awSent:=True }
  when(io.bus.w.fire) { wSent:=True }
  when(state===0 && (awSent || io.bus.aw.fire) && (wSent || io.bus.w.fire)) { state:=1 }
  when(io.bus.b.fire) {
    writes:=writes+1
    when(io.bus.b.resp=/=0) { error:=True;state:=5 }.otherwise { state:=2 }
  }
  when(io.bus.ar.fire) { state:=3 }
  when(io.bus.r.fire) {
    reads:=reads+1
    when(io.bus.r.resp=/=0 || io.bus.r.data=/=value) { error:=True;state:=5 }
    .elsewhen(index===32) { state:=4 }
    .otherwise { index:=index+1;awSent:=False;wSent:=False;state:=0 }
  }
  io.done:=state===4;io.error:=error
  io.writes:=writes;io.reads:=reads
}

class VexDmaCore extends Component with AxiCoreWrapper {
  val cpu=new examplesocvex.VexCore
  val dma=new DmaTraffic(cpu.config)
  val fabric=new NativeAxiCrossbar(cpu.config,2,Seq(SizeMapping(0,BigInt(1)<<32)))
  val io=new Bundle {
    val bus=master(Axi4(fabric.outputConfig))
    val interrupts=in Bits(32 bits)
    val debugReset=in Bool()
    val retired=out UInt(32 bits)
    val dmaDone,dmaError=out Bool()
    val dmaWrites,dmaReads=out UInt(8 bits)
  }
  def bus=io.bus
  def interrupts=io.interrupts
  def debugReset=io.debugReset
  cpu.io.interrupts:=io.interrupts;cpu.io.debugReset:=io.debugReset
  fabric.io.inputs(0) << cpu.io.bus
  fabric.io.inputs(1) << dma.io.bus
  io.bus << fabric.io.outputs(0)
  io.retired:=cpu.io.retired;io.dmaDone:=dma.io.done;io.dmaError:=dma.io.error
  io.dmaWrites:=dma.io.writes;io.dmaReads:=dma.io.reads
}

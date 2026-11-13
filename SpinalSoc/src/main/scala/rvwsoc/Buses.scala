package rvwsoc

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._
import spinal.lib.bus.amba4.axi._
import spinal.lib.bus.amba4.axilite._
import spinal.lib.bus.amba4.axilite.AxiLite4Utils._
import spinal.lib.bus.tilelink

// These traits leave the original APB3 CoreWrapper source compatible.
trait AxiCoreWrapper { this: Component =>
  def bus: Axi4
  def interrupts: Bits
  def debugReset: Bool
}
trait AxiLiteCoreWrapper { this: Component =>
  def bus: AxiLite4
  def interrupts: Bits
  def debugReset: Bool
}
trait TileLinkCoreWrapper { this: Component =>
  def bus: tilelink.Bus
  def interrupts: Bits
  def debugReset: Bool
}

/** One outstanding transfer. Hold response data and errors through backpressure.
  * APB uses the library's strobe extension. No read/modify/write on MMIO.
  */
class LiteToApb(config: AxiLite4Config) extends Component {
  require(config.dataWidth == 32)
  val io = new Bundle {
    val up = slave(AxiLite4(config))
    val down = master(Apb3(Apb3Config(config.addressWidth, 32, useStrb = true)))
  }
  val aw = io.up.aw.m2sPipe()
  val w = io.up.w.m2sPipe()
  val ar = io.up.ar.m2sPipe()
  val state = Reg(UInt(2 bits)) init(0) // idle, access, response
  val write = Reg(Bool())
  val address = Reg(UInt(config.addressWidth bits))
  val data = Reg(Bits(32 bits))
  val mask = Reg(Bits(4 bits))
  val response = Reg(Bits(32 bits))
  val error = Reg(Bool())
  val writeReady = aw.valid && w.valid
  aw.ready := state === 0 && w.valid
  w.ready := state === 0 && aw.valid
  ar.ready := state === 0 && !writeReady
  io.down.PSEL := 0
  io.down.PENABLE := state === 1
  io.down.PADDR := address
  io.down.PWRITE := write
  io.down.PWDATA := data
  io.down.PSTRB := mask
  when(state === 0 && (writeReady || ar.valid)) {
    address := (writeReady.mux(aw.addr, ar.addr) >> 2) << 2
    write := writeReady
    data := w.data
    mask := w.strb
    state := 1
  }
  // The request registers supply a full setup cycle before ACCESS.
  val setup = RegNext(state === 0) init(True)
  when(state === 1) {
    io.down.PSEL := 1
    io.down.PENABLE := !setup
    when(!setup && io.down.PREADY) {
      response := io.down.PRDATA
      error := io.down.PSLVERROR
      state := 2
    }
  }
  io.up.b.valid := state === 2 && write
  io.up.b.resp := error ## False
  io.up.r.valid := state === 2 && !write
  io.up.r.data := response
  io.up.r.resp := error ## False
  when(io.up.b.fire || io.up.r.fire) { state := 0 }
}

object BusIngress {
  def apply(bus: SimpleCpuBus): Apb3 = {
    val bridge = new SimpleToApb(bus.addressWidth)
    bridge.io.cpu <> bus
    bridge.io.apb
  }
  def apply(bus: AxiLite4): Apb3 = {
    val bridge = new LiteToApb(bus.config)
    bridge.io.up << bus
    bridge.io.down
  }
  def apply(bus: Axi4): Apb3 = {
    require(bus.config.dataWidth == 32, "AXI ingress currently requires 32 data bits")
    apply(bus.toLite()) // Library ID removal and burst splitting.
  }
  def apply(bus: tilelink.Bus): Apb3 = {
    require(Set(32, 64, 128).contains(bus.p.dataWidth) && !bus.p.withBCE)
    require(bus.p.node != null, "TileLink ingress needs negotiated node parameters")
    val node = bus.p.node.copy(m = bus.p.node.m.copy(dataWidth = 32))
    val narrow = if(bus.p.dataWidth == 32) bus else {
      val adapter = new tilelink.WidthAdapter(bus.p, node.toBusParameter())
      adapter.io.up << bus
      adapter.io.down
    }
    val bridge = new tilelink.Apb3Bridge(node, tilelink.Apb3BridgeConfig(apb4 = true))
    bridge.io.up << narrow
    val down = Apb3(bridge.io.down.config.copy(useProt = false))
    down.PADDR := bridge.io.down.PADDR
    down.PSEL := bridge.io.down.PSEL
    down.PENABLE := bridge.io.down.PENABLE
    down.PWRITE := bridge.io.down.PWRITE
    down.PWDATA := bridge.io.down.PWDATA
    down.PSTRB := bridge.io.down.PSTRB
    bridge.io.down.PRDATA := down.PRDATA
    bridge.io.down.PREADY := down.PREADY
    bridge.io.down.PSLVERROR := down.PSLVERROR
    down
  }
  /** Legacy APB3 peripherals cannot accept partial writes. Reject them before
    * asserting PSEL, so register side effects cannot occur on an error.
    */
  def legacy(bus: Apb3, target: Apb3): Unit = {
    val partial = bus.PWRITE && !bus.PSTRB.andR
    target.PADDR := bus.PADDR.resized
    target.PSEL := bus.PSEL.andMask(!partial)
    target.PENABLE := bus.PENABLE
    target.PWRITE := bus.PWRITE
    target.PWDATA := bus.PWDATA
    bus.PRDATA := target.PRDATA
    bus.PREADY := partial || target.PREADY
    bus.PSLVERROR := partial || target.PSLVERROR
  }
}

/** Pack strobes into the bundled payload before the library toggle crossing.
  * Apb3CC itself does not transfer PSTRB. Both domains must reset together.
  */
object BusClockCrossing {
  def apply(bus: Apb3, destination: ClockDomain): Apb3 = {
    require(bus.config.selWidth == 1 && bus.config.dataWidth == 32)
    val packedConfig = bus.config.copy(dataWidth = 64, useStrb = false, useProt = false)
    val bridge = Apb3CC(packedConfig, ClockDomain.current, destination)
    val input = bridge.io.input
    input.PADDR := bus.PADDR
    input.PSEL := bus.PSEL
    input.PENABLE := bus.PENABLE
    input.PWRITE := bus.PWRITE
    input.PWDATA := B(0, 28 bits) ## (if(bus.config.useStrb) bus.PSTRB else B(15, 4 bits)) ## bus.PWDATA
    bus.PRDATA := input.PRDATA(31 downto 0)
    bus.PREADY := input.PREADY
    bus.PSLVERROR := input.PSLVERROR
    val output = bridge.io.output
    val down = Apb3(bus.config)
    down.PADDR := output.PADDR
    down.PSEL := output.PSEL
    down.PENABLE := output.PENABLE
    down.PWRITE := output.PWRITE
    down.PWDATA := output.PWDATA(31 downto 0)
    if(bus.config.useStrb) down.PSTRB := output.PWDATA(35 downto 32)
    if(bus.config.useProt) down.PPROT := 0
    output.PRDATA := B(0, 32 bits) ## down.PRDATA
    output.PREADY := down.PREADY
    output.PSLVERROR := down.PSLVERROR
    down
  }
}

import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._
import spinal.lib.bus.amba4.axilite._

// The external test master drives actual APB and AXI-Lite wires.
class SeededSoc extends Component {
  val io = new Bundle {
    val apb = slave(Apb3(Apb3Config(32, 32)))
    val axi = slave(AxiLite4(AxiLite4Config(32, 32)))
    val tx = out Bool()
  }
  noIoPrefix()
  val control = Reg(Bits(32 bits)) init(0)
  io.apb.PREADY := True
  io.apb.PRDATA := control
  io.apb.PSLVERROR := io.apb.PADDR =/= U(0x10000000L, 32 bits)
  when(io.apb.PSEL(0) && io.apb.PENABLE && io.apb.PWRITE && !io.apb.PSLVERROR) {
    control := io.apb.PWDATA
  }
  val serial = Reg(Bits(32 bits)) init(0)
  val awPending = RegInit(False)
  val wPending = RegInit(False)
  val address = Reg(UInt(32 bits)) init(0)
  val data = Reg(Bits(32 bits)) init(0)
  val strobe = Reg(Bits(4 bits)) init(0)
  val bValid = RegInit(False)
  val bResp = Reg(Bits(2 bits)) init(0)
  io.axi.aw.ready := !awPending && !bValid
  io.axi.w.ready := !wPending && !bValid
  when(io.axi.aw.fire) { address := io.axi.aw.addr; awPending := True }
  when(io.axi.w.fire) { data := io.axi.w.data; strobe := io.axi.w.strb; wPending := True }
  io.axi.b.valid := bValid
  io.axi.b.resp := bResp
  when(io.axi.b.fire) { bValid := False }
  val shift = Reg(Bits(10 bits)) init(B(1023, 10 bits))
  val bitsLeft = Reg(UInt(4 bits)) init(0)
  val divider = Reg(UInt(3 bits)) init(0)
  io.tx := shift(0)
  when(bitsLeft =/= 0) {
    divider := divider + 1
    when(divider === 7) {
      shift := B"1" ## shift(9 downto 1)
      bitsLeft := bitsLeft - 1
    }
  }
  when(awPending && wPending && !bValid) {
    awPending := False; wPending := False; bValid := True
    bResp := B(0, 2 bits)
    when(address =/= U(0x10001000L, 32 bits)) { bResp := B(2, 2 bits) }
      .otherwise {
        for(i <- 0 until 4) when(strobe(i)) { serial(i*8+7 downto i*8) := data(i*8+7 downto i*8) }
        when(strobe(0) && bitsLeft === 0) {
          shift := B"1" ## data(7 downto 0) ## B"0"
          divider := 0; bitsLeft := 10
        }
      }
  }
  val rValid = RegInit(False)
  val rData = Reg(Bits(32 bits)) init(0)
  val rResp = Reg(Bits(2 bits)) init(0)
  io.axi.ar.ready := !rValid
  io.axi.r.valid := rValid; io.axi.r.data := rData; io.axi.r.resp := rResp
  when(io.axi.r.fire) { rValid := False }
  when(io.axi.ar.fire) {
    rValid := True; rData := serial
    rResp := Mux(io.axi.ar.addr === U(0x10001000L, 32 bits), B(0, 2 bits), B(2, 2 bits))
  }
}
object SeededSocMain extends App {
  SpinalConfig(targetDirectory=args(0)).generateVerilog(new SeededSoc)
}

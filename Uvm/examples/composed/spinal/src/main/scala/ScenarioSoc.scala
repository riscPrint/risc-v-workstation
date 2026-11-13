package uvmsoc
import spinal.core._
import spinal.lib._
import spinal.lib.bus.amba3.apb._
import rvwsoc.CoreWrapper

class BusMaster extends Component with CoreWrapper {
 val io = new Bundle {
  val bus=master(Apb3(Apb3Config(32,32)))
  val interrupts=in Bits(32 bits)
  val debugReset=in Bool()
  val start=in Bool()
  val address=in UInt(32 bits)
  val write=in Bool()
  val data=in Bits(32 bits)
  val done=out Bool()
  val busy=out Bool()
  val error=out Bool()
  val readData=out Bits(32 bits)
 }
 def bus=io.bus
 def interrupts=io.interrupts
 def debugReset=io.debugReset
 val state=Reg(UInt(2 bits)) init(0)
 val address=Reg(UInt(32 bits)) init(0)
 val data=Reg(Bits(32 bits)) init(0)
 val write=Reg(Bool()) init(False)
 val error=Reg(Bool()) init(False)
 val readData=Reg(Bits(32 bits)) init(0)
 io.bus.PSEL := B(0,1 bits)
 io.bus.PENABLE := state===2
 io.bus.PADDR := address
 io.bus.PWRITE := write
 io.bus.PWDATA := data
 io.busy := state===1 || state===2
 io.done := state===3
 io.error := error
 io.readData := readData
 when(state===0 && io.start) { address:=io.address; data:=io.data; write:=io.write; state:=1 }
 when(state===1) { state:=2 }
 when(state===1 || state===2) { io.bus.PSEL:=1 }
 when(state===2 && io.bus.PREADY) { readData:=io.bus.PRDATA; error:=io.bus.PSLVERROR; state:=3 }
 when(state===3 && !io.start) { state:=0 }
}
class Endpoint extends Component {
 val io=new Bundle {
  val bus=slave(Apb3(Apb3Config(8,32)))
  val hold=in Bool()
  val injectError=in Bool()
  val requestIrq=in Bool()
  val irq=out Bool()
 }
 val value=Reg(Bits(32 bits)) init(0x1234)
 io.bus.PREADY := !io.hold
 io.bus.PSLVERROR := io.injectError
 io.bus.PRDATA := value
 io.irq := io.requestIrq
 when(io.bus.PSEL.lsb && io.bus.PENABLE && io.bus.PREADY && io.bus.PWRITE && !io.injectError) { value:=io.bus.PWDATA }
}
class ScenarioSoc extends generated.ComposedSoc {
 val start=core.io.start.toIo()
 val address=core.io.address.toIo()
 val write=core.io.write.toIo()
 val data=core.io.data.toIo()
 val done=core.io.done.toIo()
 val busy=core.io.busy.toIo()
 val error=core.io.error.toIo()
 val readData=core.io.readData.toIo()
 val observedIrqs=out Bits(32 bits)
 observedIrqs:=core.interrupts
}
object Generate extends App {
 SpinalConfig(targetDirectory=args(0)).generateVerilog(new ScenarioSoc)
}

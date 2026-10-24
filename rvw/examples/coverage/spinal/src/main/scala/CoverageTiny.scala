import spinal.core._

class CoverageTiny extends Component {
  val io = new Bundle {
    val a = in UInt(4 bits)
    val choose = in Bool()
    val y = out UInt(5 bits)
  }
  val state = Reg(UInt(2 bits)) init 0
  state := state + 1
  when(state === 2) { state := 0 }
  io.y := io.a.resize(5) + 1
  when(!io.choose) { io.y := io.a.resize(5) ^ 3 }
  when(state === 3) { io.y := 31 }
}

object EmitCoverageTiny extends App {
  SpinalConfig(targetDirectory = args(0), genLineComments = true).generateVerilog(new CoverageTiny)
}

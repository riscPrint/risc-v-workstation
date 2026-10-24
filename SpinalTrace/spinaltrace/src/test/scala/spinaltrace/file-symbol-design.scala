// Deliberately in a file whose name is not a legal HDL identifier (spinal-boom has
// `frontend-types.scala`): the probe names must keep only letters and digits, like Spinal's own.
package spinaltrace

import spinal.core._

class HyphenFileDesign extends Component {
  val io = new Bundle {
    val sel       = in Bool ()
    val a, b      = in UInt (4 bits)
    val o         = out UInt (4 bits)
  }
  io.o := (io.sel && io.a > io.b) ? io.a | io.b
}

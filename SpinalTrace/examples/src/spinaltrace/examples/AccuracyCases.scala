package spinaltrace.examples
import spinal.core._

class EnabledState extends Component {
  val io = new Bundle {
    val enable, soft = in Bool()
    val data = in UInt(8 bits)
    val result = out UInt(8 bits)
  }
  val area = new ClockingArea(ClockDomain.current.copy(clockEnable = io.enable, softReset = io.soft)) {
    val state = RegNext(io.data) init(0)
  }
  io.result := area.state
}
class MaskedMemory extends Component {
  val io = new Bundle {
    val address = in UInt(2 bits)
    val data = in Bits(16 bits)
    val mask = in Bits(2 bits)
    val result = out Bits(16 bits)
  }
  val mem = Mem(Bits(16 bits), 4)
  mem.write(io.address, io.data, mask = io.mask)
  io.result := mem.readAsync(io.address)
}
class MixedMemory extends Component {
  val io = new Bundle {
    val address = in UInt(3 bits)
    val data = in Bits(8 bits)
    val result = out Bits(16 bits)
  }
  val mem = Mem(Bits(16 bits), 4)
  mem.writeMixedWidth(io.address, io.data)
  io.result := mem.readAsync(io.address(2 downto 1))
}
class ManyPartialWrites extends Component {
  val io = new Bundle {
    val index = in UInt(5 bits)
    val data = in Bits(20 bits)
    val result = out Bits(32 bits)
  }
  val state = Reg(Bits(32 bits)) init(0)
  for (i <- 0 until 20) state(io.index + U(i, 5 bits)) := io.data(i)
  io.result := state
}
class SameLine extends Component {
  val io = new Bundle { val a = in UInt(8 bits); val result = out UInt(8 bits) }
  val intermediate = UInt(8 bits); intermediate := io.a + 1; io.result := intermediate + 1
}

// Tests replace the named key with its raw expression to exercise incomplete extraction.
class ExpressionSwitch extends Component {
  val io = new Bundle {
    val key, selector = in UInt(8 bits)
    val result = out UInt(8 bits)
  }
  val keyExpr = io.key + 1
  io.result := 0
  switch(io.selector) {
    is(U(0, 8 bits)) { io.result := keyExpr }
  }
}

class AsyncWriteMemory extends Component {
  val io = new Bundle {
    val address = in UInt(2 bits)
    val data = in Bits(8 bits)
    val enable = in Bool()
    val result = out Bits(8 bits)
  }
  val mem = Mem(Bits(8 bits), 4)
  io.result := mem.readAsyncWrite(io.address, io.data, io.enable)
}

class LargeMemory extends Component {
  val io = new Bundle {
    val address = in UInt(13 bits)
    val data = in Bits(8 bits)
    val result = out Bits(8 bits)
  }
  val mem = Mem(Bits(8 bits), 8192)
  mem.write(io.address, io.data)
  io.result := mem.readAsync(io.address)
}

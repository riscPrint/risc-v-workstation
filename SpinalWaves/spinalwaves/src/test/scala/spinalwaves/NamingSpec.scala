package spinalwaves

import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

class NamingChild extends Component {
  val io = new Bundle {
    val a = in UInt(8 bits)
    val result = out UInt(8 bits)
  }
  io.result := io.a + 1
}
class NamingTop extends Component {
  val io = new Bundle {
    val a = in UInt(8 bits)
    val nested = out(new Bundle { val values = Vec(UInt(8 bits), 2) })
  }
  val sub = new NamingChild
  sub.io.a := io.a
  val work = new Area {
    val count = Reg(UInt(8 bits)) init 0
    count := count + 1
  }
  io.nested.values(0) := sub.io.result
  io.nested.values(1) := work.count
}

class NamingSpec extends AnyFunSuite {
  test("shared names preserve Bundle, Vec, Area and child boundaries") {
    val report = SpinalWaves.elaborateWithLocations(SpinalConfig(targetDirectory = "target/naming-rtl"))(new NamingTop)
    val top = report.toplevel
    assert(HglNaming.instancePath(top).isEmpty)
    assert(HglNaming.instancePath(top.sub) == Seq("sub"))
    assert(HglNaming.hglPath(top.sub.io.a) == ("sub.io", "a"))
    assert(HglNaming.hglPath(top.io.nested.values(1)) == ("io", "nested.values.1"))
    assert(HglNaming.hglPath(top.work.count) == ("work", "count"))
    assert(HglNaming.rtlPath(top.sub.io.a) == "sub.io_a")
    val location = SourceLocator(top.io.a).get
    assert(location.absPath.endsWith("/NamingSpec.scala"))
    assert(location.line == 15)
    assert(SourceLocator(top.work.count).exists(_.line == 21))
  }
}

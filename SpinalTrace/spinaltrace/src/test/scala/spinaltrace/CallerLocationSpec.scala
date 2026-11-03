package spinaltrace

import org.scalatest.funsuite.AnyFunSuite

class CallerLocationSpec extends AnyFunSuite {
  test("library-only traces retain distinct elaboration callers") {
    def location(caller: String, file: String, line: Int) = {
      val trace = new Throwable
      trace.setStackTrace(Array(
        new StackTraceElement("spinal.lib.StreamFifo", "impl", "Stream.scala", 100),
        new StackTraceElement(caller, "compile", file, line)))
      val frame = new Locations(Nil).frame(trace).get
      SourceInfo.locate(frame, Nil)
    }
    val old = location("example.LegacyAdapter", "LegacyAdapter.scala", 45)
    val current = location("riscvsim.RiscvSimConfig", "SimSession.scala", 40)
    assert(old == (("LegacyAdapter.scala", 45, 1)))
    assert(current == (("SimSession.scala", 40, 1)))
    assert(old != current)
  }
}

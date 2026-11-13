package riscvsim.boom

import org.scalatest.funsuite.AnyFunSuite
import riscvsim._
import java.nio.file.Files

class StateEncodingSpec extends AnyFunSuite {
  test("FP state retains a write to f0 and raw NaN boxing") {
    val fp = RvfiFpState(true, 0, BigInt("ffffffff7fc00001", 16), 17, 113)
    assert(fp.fields("fd_valid").bool)
    assert(fp.fields("fd").num == 0)
    assert(fp.fields("fd_wdata").str == "0xffffffff7fc00001")
  }
  test("flags must equal the low fcsr bits") {
    intercept[IllegalArgumentException] { RvfiFpState(false, 0, 0, 1, 0) }
  }
  test("state declaration selects C2 version 2") {
    val path = Files.createTempFile("rvfi-state", ".jsonl")
    try {
      val w = new RvfiTraceWriter(path.toFile, ujson.Obj("capabilities" -> ujson.Arr("state")))
      w.end(1, "pass"); w.close()
      val header = ujson.read(Files.readString(path).linesIterator.next())
      assert(header("schema").str == "rvw.rvfi/2")
    } finally Files.delete(path)
  }
}

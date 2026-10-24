package spinaldb

import java.nio.file.Files
import java.sql.DriverManager
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

class Round17ClockBox extends BlackBox {
  setDefinitionName("Round17ClockBox"); noIoPrefix()
  val c = in Bool()
  val y = out Bool()
  mapCurrentClockDomain(clock = c)
  setInlineVerilog("module Round17ClockBox(input c, output y); assign y=c; endmodule")
}
class Round17BoxTop extends Component {
  val y = out Bool()
  val bb = new Round17ClockBox
  y := bb.y
}

class Round17BlackBoxSpec extends AnyFunSuite {
  test("round 17: BlackBox clock inputs retain conservative dependency edges") {
    val root = Files.createTempDirectory("spinaldb-r17box").toFile
    SpinalDB.generate(SpinalConfig(targetDirectory = new java.io.File(root, "rtl").getPath),
      new java.io.File(root, "box.db"), DbOptions(pdg = false, blocks = false, hgldd = false))(new Round17BoxTop)
    val con = DriverManager.getConnection("jdbc:sqlite:" + new java.io.File(root, "box.db"))
    try {
      val r = con.createStatement().executeQuery("SELECT count(*) FROM edges e JOIN signals a ON e.src=a.id " +
        "JOIN signals b ON e.dst=b.id WHERE a.path='bb.c' AND b.path='bb.y' AND e.kind='blackbox'")
      assert(r.next() && r.getInt(1) == 1)
    } finally con.close()
  }
}

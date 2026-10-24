package spinaldb

import java.io.File
import java.nio.file.Files
import java.sql.DriverManager
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

class Round18Memory(mode: String, policy: ReadUnderWritePolicy, during: DuringWritePolicy = dontCare) extends Component {
  setDefinitionName("Round18Memory")
  val addr = in UInt(2 bits)
  val en, wen = in Bool()
  val data = in Bits(8 bits)
  val mask = in Bits(2 bits)
  val y, direct = out Bits(8 bits)
  direct := data
  val mem = Mem(Bits(8 bits), 4)
  mem.initBigInt(Seq(1, 2, 3, 4).map(BigInt(_)))
  if (mode == "sync" || mode == "enabled") mem.write(addr, data, wen, mask)
  y := (mode match {
    case "sync" => mem.readSync(addr, readUnderWrite = policy)
    case "enabled" => mem.readSync(addr, en, readUnderWrite = policy)
    case "rw" => mem.readWriteSync(addr, data, en, wen, mask, readUnderWrite = policy, duringWrite = (if (policy != dontCare && during == dontCare) doRead else during))
    case "async" => mem.readAsync(addr)
  })
}
class Round18Box(path: String) extends BlackBox {
  setDefinitionName("Round18Box"); noIoPrefix(); addRTLPath(path)
  val y = out Bool()
}
class Round18Top(path: String) extends Component {
  setDefinitionName("Round18Top")
  val y = out Bool()
  val bb = new Round18Box(path)
  y := bb.y
}
object Round18Fixtures {
  val modes = Seq("sync", "enabled", "rw", "async")
  val policies = Seq("dont" -> dontCare, "read" -> readFirst, "write" -> writeFirst)
  val cases = for (mode <- modes; (label, policy) <- policies
    if (mode == "rw" || label != "write") && (mode != "async" || label == "dont")) yield (mode, label, policy)
  def main(args: Array[String]): Unit = {
    val root = new File(args(0)); root.mkdirs()
    def write(name: String)(gen: => Component): Unit =
      SpinalDB.generate(SpinalConfig(targetDirectory = new File(root, "rtl-" + name).getPath),
        new File(root, name + ".db"), DbOptions(pdg = false, blocks = false, hgldd = false))(gen)
    for ((mode, label, policy) <- cases)
      write(s"r18_${mode}_$label")(new Round18Memory(mode, policy))
    for ((label, during) <- Seq("do" -> doRead, "dont" -> dontRead))
      write(s"r18_rw_during_$label")(new Round18Memory("rw", dontCare, during))
    val body = root.toPath.resolve("Round18Box.v")
    val synth = root.toPath.resolve("synth.svh")
    val sim = root.toPath.resolve("sim.svh")
    Files.writeString(body, s"module Round18Box(output y);\n`ifdef SYNTHESIS\n`include \"$synth\"\n`else\n`include \"$sim\"\n`endif\nendmodule\n")
    Files.writeString(synth, "assign y = 1'b0;\n")
    for (n <- 0 to 1) {
      Files.writeString(sim, s"assign y = 1'b$n;\n")
      write(s"r18_box$n")(new Round18Top(body.toString))
    }
    Files.writeString(body, s"module Round18Box(output y);\n`ifdef OUTSIDE\n`include \"$sim\"\n`else\nassign y=0;\n`endif\nendmodule\n")
    write("r18_box_unknown")(new Round18Top(body.toString))
  }
}
class Round18Spec extends AnyFunSuite {
  test("round 18: BlackBox fingerprint covers SYNTHESIS and simulation includes") {
    val root = Files.createTempDirectory("spinaldb-r18-deps")
    val body = root.resolve("Box.v")
    val a = root.resolve("synth.svh"); val b = root.resolve("sim.svh")
    val nested = root.resolve("nested.svh")
    Files.writeString(a, "assign y = 0;\n")
    Files.writeString(b, "`include \"nested.svh\"\n")
    Files.writeString(nested, "assign y = 0;\n")
    Files.writeString(body, "module Box(output y);\n`ifdef SYNTHESIS\n`include \"synth.svh\"\n`else\n`include \"sim.svh\"\n`endif\nendmodule\n")
    def scan() = HdlDeps.captureAll(Seq(HdlDeps.Request("Box", Seq("body" -> body.toFile), Nil, Nil)), Nil)._1.head
    val first = scan()
    assert(first.problems.isEmpty, first.problems)
    assert(first.chunks.exists(_._1.contains("nested.svh")), first.chunks.map(_._1))
    Files.writeString(nested, "assign y = 1;\n")
    val second = scan()
    assert(second.problems.isEmpty, second.problems)
    assert(!first.chunks.map(_._2.toSeq).equals(second.chunks.map(_._2.toSeq)))
    Files.delete(nested)
    assert(scan().problems.nonEmpty, "an unreadable simulation include must be incomplete")
  }
  test("round 18: unresolved conditional defines and macro includes are incomplete") {
    val root = Files.createTempDirectory("spinaldb-r18-macros")
    val body = root.resolve("Box.v"); val inc = root.resolve("extra.svh")
    Files.writeString(inc, "assign y=0;\n")
    val bodies = Seq(
      "`ifdef OUTSIDE\n`include \"extra.svh\"\n`else\nassign y=0;\n`endif\n",
      "`define HEADER \"extra.svh\"\n`include `HEADER\n",
      "`ifdef SYNTHESIS\nassign y=0;\n`else\n`ifdef OUTSIDE\n`include \"extra.svh\"\n`else\nassign y=0;\n`endif\n`endif\n",
      "`undef SYNTHESIS\nassign y=0;\n")
    for (text <- bodies) {
      Files.writeString(body, "module Box(output y);\n" + text + "endmodule\n")
      val result = HdlDeps.captureAll(Seq(HdlDeps.Request("Box", Seq("body" -> body.toFile), Nil, Nil)), Nil)._1.head
      assert(result.problems.nonEmpty && result.chunks.isEmpty, text)
    }
  }
  test("round 18: synchronous read ports have explicit state and no address bypass") {
    val root = Files.createTempDirectory("spinaldb-r18-netlist")
    Round18Fixtures.main(Array(root.toString))
    for ((mode, label, _) <- Round18Fixtures.cases) {
      val con = DriverManager.getConnection("jdbc:sqlite:" + root.resolve(s"r18_${mode}_$label.db"))
      try {
        val r = con.createStatement().executeQuery("SELECT count(*) FROM signals WHERE kind='mem_read'")
        assert(r.next() && r.getInt(1) == (if (mode == "async") 0 else 1), s"$mode $label")
        val ports = con.createStatement().executeQuery("SELECT count(*) FROM mem_ports p JOIN signals s ON s.id=p.output_id WHERE s.kind='mem_read' AND s.clock_domain_id=p.clock_domain_id")
        assert(ports.next() && ports.getInt(1) == (if (mode == "async") 0 else 1))
        if (mode != "async") {
          val bypass = con.createStatement().executeQuery("SELECT count(*) FROM edges e JOIN signals a ON e.src=a.id JOIN signals b ON e.dst=b.id WHERE a.path IN ('addr','en') AND b.path='y'")
          assert(bypass.next() && bypass.getInt(1) == 0)
        }
      } finally con.close()
    }
  }
}

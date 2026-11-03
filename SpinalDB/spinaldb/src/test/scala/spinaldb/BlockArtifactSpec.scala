package spinaldb

import java.nio.file.Files
import java.sql.DriverManager
import java.util.zip.GZIPInputStream
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

/** The database must preserve the extractor's diagram and source-navigation data. */
class BlockArtifactSpec extends AnyFunSuite {
  class ClockedTop extends Component {
    val count = out UInt(8 bits)
    val state = Reg(UInt(8 bits)) init(0)
    state := state + 1
    count := state
  }

  test("implicit clock source locations retain the elaboration caller") {
    val dir = Files.createTempDirectory("spinaldb-block-clock-")
    def config = SpinalConfig(targetDirectory = dir.toString)
    val direct = spinalblocks.SpinalBlocks.generate(config, dir.resolve("direct.json").toFile)(new ClockedTop)
    val database = SpinalDB.elaborate(config, traceNaming = false)(new ClockedTop)
    def clockLocation(top: Component) = {
      val diagram = spinalblocks.SpinalBlocks.extract(top)
      diagram("modules")(top.definitionName)("ports").arr.find(_("name").str == "clk").get("loc")
    }
    val oldLoc = clockLocation(direct.toplevel)
    val newLoc = clockLocation(database.toplevel)
    // The default clock is created before the design's constructor. Do not
    // relabel either caller as design source to claim diagram parity.
    assert(oldLoc("file").str.endsWith("BlockArtifactSpec.scala"))
    assert(newLoc("file").str.endsWith("SpinalDB.scala"))
    assert(oldLoc != newLoc)
  }

  test("block artifact preserves direct extraction for both RTL backends and analog ports") {
    for (mode <- Seq(Verilog, SystemVerilog)) {
      val dir = Files.createTempDirectory("spinaldb-block-artifact-")
      val report = SpinalDB.elaborate(SpinalConfig(mode = mode, targetDirectory = dir.toString),
        traceNaming = false)(new Round24Fixtures.PadTop)
      val out = dir.resolve("design.db").toFile
      val roots = Seq(java.nio.file.Paths.get("src/test/scala").toAbsolutePath)
      SpinalDB.write(report, out, DbOptions(pdg = false, hgldd = false, sourceRoots = roots))
      val c = DriverManager.getConnection("jdbc:sqlite:" + out.getAbsolutePath)
      val stored = try {
        val rs = c.createStatement().executeQuery("SELECT content FROM artifacts WHERE name='blocks.json'")
        assert(rs.next())
        val in = new GZIPInputStream(new java.io.ByteArrayInputStream(rs.getBytes(1)))
        try ujson.read(new String(in.readAllBytes(), java.nio.charset.StandardCharsets.UTF_8))
        finally in.close()
      } finally c.close()
      val direct = spinalblocks.SpinalBlocks.extract(report.toplevel, roots)
      stored.obj.remove("generated"); direct.obj.remove("generated")
      assert(stored == direct)
      val modules = stored("modules").obj.values.toSeq
      assert(modules.exists(m => m("blackbox").bool))
      assert(modules.exists(m => m("ports").arr.exists(p => p("dir").str == "inout")))
      assert(modules.exists(m => m("loc") != ujson.Null))
      assert(modules.flatMap(_("instances").arr).exists(i => i("loc") != ujson.Null))
    }
  }
}

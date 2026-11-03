package spinaldb

import java.nio.file.Files
import java.sql.DriverManager
import java.util.zip.GZIPInputStream
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

/** The database must preserve the extractor's diagram and source-navigation data. */
class BlockArtifactSpec extends AnyFunSuite {
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

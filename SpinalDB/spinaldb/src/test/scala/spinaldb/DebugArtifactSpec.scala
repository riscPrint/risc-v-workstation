package spinaldb

import java.nio.file.Files
import java.sql.DriverManager
import java.util.zip.GZIPInputStream
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._

class DebugArtifactSpec extends AnyFunSuite {
  test("PDG and HGLDD preserve direct extraction from the same report") {
    val dir = Files.createTempDirectory("spinaldb-debug-")
    val roots = Seq(java.nio.file.Paths.get("../../SpinalTrace/examples/src").toAbsolutePath.normalize)
    val report = SpinalDB.elaborate(SpinalConfig(targetDirectory = dir.resolve("rtl").toString))(
      new spinaltrace.examples.GCD)
    val out = dir.resolve("design.db").toFile
    SpinalDB.write(report, out, DbOptions(blocks = false, sourceRoots = roots))
    val c = DriverManager.getConnection("jdbc:sqlite:" + out.getAbsolutePath)
    def artifact(name: String): ujson.Value = {
      val stmt = c.prepareStatement("SELECT content FROM artifacts WHERE name=?")
      stmt.setString(1, name)
      val rs = stmt.executeQuery()
      assert(rs.next())
      val in = new GZIPInputStream(new java.io.ByteArrayInputStream(rs.getBytes(1)))
      try ujson.read(new String(in.readAllBytes(), "UTF-8"))
      finally { in.close(); rs.close(); stmt.close() }
    }
    try {
      val direct = spinaltrace.PdgExtractor.extract(report,
        spinaltrace.ExtractOptions(sourceRoots = roots.map(_.toFile)))
      assert(artifact("pdg.json") == spinaltrace.PdgModel.toJson(direct))
      val hgldd = spinalwaves.HglddEmitter.emit(report, dir.resolve("direct"), roots)
      assert(artifact("hgldd/" + hgldd.getFileName) == ujson.read(Files.readString(hgldd)))
    } finally c.close()
  }
}

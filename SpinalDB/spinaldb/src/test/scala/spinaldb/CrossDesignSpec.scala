package spinaldb

import java.nio.file.{Files, Paths}
import java.sql.DriverManager
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.core.sim._
import scala.sys.process._

/** Bounded cross-design cases. Structural edges are not dynamic causes. */
class CrossDesignSpec extends AnyFunSuite {
  test("both backends retain coarse BlackBox input and inout dependencies") {
    for (mode <- Seq(Verilog, SystemVerilog)) {
      val dir = Files.createTempDirectory("spinaldb-coarse-")
      val db = dir.resolve("design.db")
      SpinalDB.generate(SpinalConfig(mode = mode, targetDirectory = dir.resolve("rtl").toString),
        db.toFile, DbOptions(pdg = false, hgldd = false))(new Round24Fixtures.PadTop)
      val c = DriverManager.getConnection("jdbc:sqlite:" + db)
      try {
        val rs = c.createStatement().executeQuery(
          "SELECT a.path,b.path FROM edges e JOIN signals a ON a.id=e.src " +
          "JOIN signals b ON b.id=e.dst WHERE e.kind='blackbox'")
        val edges = scala.collection.mutable.Set.empty[(String, String)]
        while (rs.next()) edges += ((rs.getString(1), rs.getString(2)))
        // q reads pad in the inline body. en/d dependencies remain deliberately coarse.
        for (input <- Seq("bb.pad", "bb.en", "bb.d")) assert(edges(input -> "bb.q"), edges)
        assert(edges("bb.en" -> "bb.pad"), edges)
        assert(edges("bb.d" -> "bb.pad"), edges)
        assert(!edges("bb.pad" -> "bb.pad"), edges)
      } finally c.close()
    }
  }

  test("no-pdg database HGLDD resolves a separately compiled plain waveform") {
    val dir = Files.createTempDirectory("spinaldb-plain-wave-")
    val cfg = SpinalConfig(targetDirectory = dir.resolve("plain-rtl").toString)
    val plain = cfg.generateVerilog(new spinaltrace.examples.GCD)
    val sim = SimConfig.withWave.workspacePath(dir.resolve("sim").toString).compile(plain)
    sim.doSim("plain") { dut =>
      dut.io.a #= 48; dut.io.b #= 18; dut.io.loadValues #= true
      dut.clockDomain.forkStimulus(10)
      dut.clockDomain.waitSampling(3)
      dut.io.loadValues #= false
      dut.clockDomain.waitSampling(12)
    }
    val report = SpinalDB.elaborate(SpinalConfig(targetDirectory = dir.resolve("db-rtl").toString),
      traceNaming = false)(new spinaltrace.examples.GCD)
    val db = dir.resolve("design.db")
    SpinalDB.write(report, db.toFile, DbOptions(pdg = false, blocks = false))
    val c = DriverManager.getConnection("jdbc:sqlite:" + db)
    val metadata = dir.resolve("hgldd"); Files.createDirectories(metadata)
    try {
      val rs = c.createStatement().executeQuery("SELECT name,content FROM artifacts WHERE name LIKE 'hgldd/%'")
      var count = 0
      while (rs.next()) {
        val in = new java.util.zip.GZIPInputStream(new java.io.ByteArrayInputStream(rs.getBytes(2)))
        try Files.write(metadata.resolve(Paths.get(rs.getString(1)).getFileName), in.readAllBytes())
        finally in.close()
        count += 1
      }
      assert(count > 0)
    } finally c.close()
    val files = Files.walk(dir.resolve("sim"))
    val wave = try {
      import scala.jdk.CollectionConverters._
      files.iterator().asScala.find(_.toString.endsWith(".vcd")).get
    } finally files.close()
    val checker = sys.env.getOrElse("SPINALWAVES_CHECK", "spinalwaves-check")
    val extra = spinalwaves.SimLayout.extraScopes(wave, report.toplevelName)
    val output = new StringBuilder
    val code = (Seq(checker, "--vcd", wave.toString, "--hgldd", metadata.toString,
      "--top-module", report.toplevelName, "--no-rewrite", "--extra-scopes") ++ extra)
      .!(ProcessLogger(s => output.append(s).append('\n'), s => output.append(s).append('\n')))
    assert(code == 0, output.toString)
  }
}

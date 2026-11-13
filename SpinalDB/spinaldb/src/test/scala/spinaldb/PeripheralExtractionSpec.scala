package spinaldb

import java.nio.file.Files
import java.sql.DriverManager
import java.util.zip.GZIPInputStream
import org.scalatest.funsuite.AnyFunSuite
import spinal.core._
import spinal.lib.bus.amba3.apb.Apb3Gpio
import spinal.lib.com.uart.{Apb3UartCtrl, UartCtrlGenerics, UartCtrlMemoryMappedConfig}
import spinal.lib.misc.MachineTimer

/** Real library designs, with database and diagram extraction in both compiler backends. */
class PeripheralExtractionSpec extends AnyFunSuite {
  for (mode <- Seq(Verilog, SystemVerilog);
       (name, make) <- Seq[(String, () => Component)](
         "gpio" -> (() => Apb3Gpio(8, withReadSync = true)),
         "timer" -> (() => MachineTimer()),
         "uart" -> (() => Apb3UartCtrl(UartCtrlMemoryMappedConfig(UartCtrlGenerics(),
           txFifoDepth = 4, rxFifoDepth = 4))))) {
    test(s"$name retains database signals, registers and block artifact with $mode") {
      val dir = Files.createTempDirectory(s"spinaldb-$name-")
      val report = SpinalDB.elaborate(SpinalConfig(mode = mode,
        targetDirectory = dir.resolve("rtl").toString), traceNaming = false)(make())
      val db = dir.resolve("design.db")
      SpinalDB.write(report, db.toFile, DbOptions(pdg = false, hgldd = false))
      val c = DriverManager.getConnection("jdbc:sqlite:" + db)
      try {
        for (where <- Seq("", " WHERE kind='reg'")) {
          val rows = c.createStatement().executeQuery(s"SELECT COUNT(*) FROM signals$where")
          assert(rows.next() && rows.getInt(1) > 0, where)
        }
        val rows = c.createStatement().executeQuery("SELECT content FROM artifacts WHERE name='blocks.json'")
        assert(rows.next())
        val stream = new GZIPInputStream(new java.io.ByteArrayInputStream(rows.getBytes(1)))
        val stored = try ujson.read(new String(stream.readAllBytes(), "UTF-8")) finally stream.close()
        val direct = spinalblocks.SpinalBlocks.extract(report.toplevel)
        stored.obj.remove("generated"); direct.obj.remove("generated")
        assert(stored == direct)
        assert(stored("modules").obj.nonEmpty)
      } finally c.close()
    }
  }
}

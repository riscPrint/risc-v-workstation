package rvwsoc

import java.io.File
import spinal.core._
import spinaldb.{Main, SpinalDB}

/** Typed extraction of a fresh composition. No core signal names are needed. */
object Database {
  def main(args: Array[String]): Unit = {
    val (options, rtl, values) = Main.parse(args.toSeq)
    require(values.length == 3, "database path, clock Hz and reset kind required")
    val reset = values(2) match {
      case "sync_high" => SYNC
      case "async_high" => ASYNC
      case _ => throw new IllegalArgumentException("unsupported reset kind")
    }
    val config = SpinalConfig(inlineRom = true, targetDirectory = rtl.getOrElse("rtl-db"),
      defaultClockDomainFrequency = FixedFrequency(values(1).toLong Hz),
      defaultConfigForClockDomains = ClockDomainConfig(resetKind = reset))
    SpinalDB.generate(config, new File(values(0)), options)(new generated.ComposedSoc)
  }
}

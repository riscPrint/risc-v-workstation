package rvwsoc

import java.io.File
import spinal.core._
import spinaldb.{Main, SpinalDB}

/** Typed extraction of a fresh composition. No core signal names are needed. */
object Database {
  def main(args: Array[String]): Unit = {
    val (options, rtl, values) = Main.parse(args.toSeq)
    require(values.length == 3 || values.length == 4, "database path, clock Hz, reset kind and optional component class required")
    val reset = values(2) match {
      case "sync_high" => SYNC
      case "async_high" => ASYNC
      case _ => throw new IllegalArgumentException("unsupported reset kind")
    }
    val config = SpinalConfig(inlineRom = true, targetDirectory = rtl.getOrElse("rtl-db"),
      defaultClockDomainFrequency = FixedFrequency(values(1).toLong Hz),
      defaultConfigForClockDomains = ClockDomainConfig(resetKind = reset))
    val cls = Class.forName(if (values.length == 4) values(3) else "generated.ComposedSoc")
    SpinalDB.generate(config, new File(values(0)), options)(cls.getDeclaredConstructor().newInstance().asInstanceOf[Component])
  }
}

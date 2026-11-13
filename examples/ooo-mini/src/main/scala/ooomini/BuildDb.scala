package ooomini

import java.io.File
import spinal.core._

object BuildDb extends App {
  spinaldb.SpinalDB.generate(
    SpinalConfig(targetDirectory="rvw/out/db-rtl",defaultConfigForClockDomains=ClockDomainConfig(resetKind=SYNC)),
    new File("rvw/out/design.db"))(new Core())
}

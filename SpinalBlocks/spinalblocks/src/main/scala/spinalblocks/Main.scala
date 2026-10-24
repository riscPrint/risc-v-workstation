package spinalblocks

import java.io.File

import spinal.core._

/** Diagram of any component with a no-argument constructor:
  * {{{
  * sbt "spinalblocks/runMain spinalblocks.Main my.pkg.MyTop [out.json]"
  * }}}
  * For components that need parameters, call `SpinalBlocks.generate` from your own main. */
object Main {
  def main(args: Array[String]): Unit = {
    require(args.nonEmpty, "usage: spinalblocks.Main <component class> [out.json|out.json.gz]")
    val cls = Class.forName(args(0))
    val out = new File(if (args.length > 1) args(1) else cls.getSimpleName + ".json")
    val locations = !sys.env.get("SPINALBLOCKS_LOCATIONS").contains("0")
    SpinalBlocks.generate(SpinalConfig(targetDirectory = "target/spinalblocks-rtl"), out, locations)(
      cls.getDeclaredConstructor().newInstance().asInstanceOf[Component])
  }
}

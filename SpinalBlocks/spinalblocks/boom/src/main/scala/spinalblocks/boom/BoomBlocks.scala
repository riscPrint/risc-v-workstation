package spinalblocks.boom

import java.io.File
import java.nio.file.Paths

import boom.common._
import boom.sim.BoomSim
import boom.system.BoomSimTop

/** Block diagram of the BOOM simulation top (tile, caches, TileLink, sim memory port).
  *
  * {{{
  * sbt "boom/run [small|medium|large|mega|giga] [out.json]"
  * }}}
  * Runs from spinal-boom/ so source locations resolve against its sources. The default output is
  * spinal-boom/blocks/boom-<preset>.json.gz. `SPINALBLOCKS_LOCATIONS=0` skips the second elaboration
  * (faster, no jump-to-source). */
object BoomBlocks {
  def main(args: Array[String]): Unit = {
    val preset = args.headOption.getOrElse("small")
    val tile = preset match {
      case "small"  => BoomConfigs.small()
      case "medium" => BoomConfigs.medium()
      case "large"  => BoomConfigs.large()
      case "mega"   => BoomConfigs.mega()
      case "giga"   => BoomConfigs.giga()
      case other    => sys.error(s"unknown preset $other")
    }
    val out = new File(if (args.length > 1) args(1) else s"blocks/boom-$preset.json.gz").getAbsoluteFile
    val locations = !sys.env.get("SPINALBLOCKS_LOCATIONS").contains("0")
    implicit val p: rocketchip.config.Parameters = BoomSim.params(tile)
    spinalblocks.SpinalBlocks.generate(SpinalBoomConfig(s"simWorkspace/spinalblocks/$preset"), out, locations,
      Seq(Paths.get("src/main/scala"), Paths.get("src/test/scala")))(new BoomSimTop(BoomSim.resetVector))
  }
}

package spinaldb.boom

import java.io.File
import java.nio.file.Paths

import boom.common._
import boom.sim.BoomSim
import boom.system.BoomSimTop
import spinaldb.{DbOptions, SpinalDB}

import scala.sys.process._
import scala.util.Try

/** Design database of the BOOM simulation top (tile, caches, TileLink, sim memory port).
  *
  * {{{
  * sbt "run [small|medium|large|mega|giga] [out.db] [--rtl DIR] [--no-pdg] [--no-blocks] [--no-hgldd]"
  * }}}
  * Default output `boom-<preset>.db`, RTL into `target/rtl/<preset>`. Source locations resolve against
  * the spinal-boom checkout given by SPINAL_BOOM (passed in as `-Dspinal.boom`). */
object BoomDB {
  def main(args: Array[String]): Unit = {
    val boomDir = new File(sys.props.getOrElse("spinal.boom", sys.env.getOrElse("SPINAL_BOOM", "../../../spinal-boom-eda"))).getCanonicalFile
    val base = DbOptions(sourceRoots = Seq("src/main/scala", "src/test/scala").map(d => new File(boomDir, d).toPath))
    val (opts, rtl, pos) = spinaldb.Main.parse(args.toSeq, base)
    val preset = pos.headOption.getOrElse("small")
    val tile = preset match {
      case "small"  => BoomConfigs.small()
      case "medium" => BoomConfigs.medium()
      case "large"  => BoomConfigs.large()
      case "mega"   => BoomConfigs.mega()
      case "giga"   => BoomConfigs.giga()
      case other    => sys.error(s"unknown preset $other")
    }
    val out = new File(pos.lift(1).getOrElse(s"boom-$preset.db")).getAbsoluteFile
    def git(args: String*): Option[String] = Try(Process("git" +: args, boomDir).!!.trim).toOption
    val meta = Seq("core" -> "boom", "config" -> preset, "core_repo" -> boomDir.getPath) ++
      git("rev-parse", "--short", "HEAD").map("core_rev" -> _) ++
      git("status", "--porcelain", "--untracked-files=no").map(s => "core_dirty" -> s.nonEmpty.toString)
    implicit val p: rocketchip.config.Parameters = BoomSim.params(tile)
    SpinalDB.generate(SpinalBoomConfig(rtl.getOrElse(s"target/rtl/$preset")), out, opts.copy(meta = opts.meta ++ meta))(
      new BoomSimTop(BoomSim.resetVector))
  }
}

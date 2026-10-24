package spinaldb

import java.io.File
import java.nio.file.Paths

import spinal.core._

/** Design database of any component with a no-argument constructor:
  * {{{
  * sbt "runMain spinaldb.Main my.pkg.MyTop out.db [--rtl DIR] [--source-root DIR]... [--no-pdg] [--pdg-tables] [--no-blocks] [--no-hgldd]"
  * }}}
  * For components that need parameters, call `SpinalDB.generate` from your own main (see `boom/`). */
object Main {
  val usage = "usage: spinaldb.Main <component class> <out.db> [--rtl DIR] [--source-root DIR]... [--no-pdg] [--pdg-tables] [--no-blocks] [--no-hgldd] [--meta KEY=VALUE]... [--blackbox-source DEFINITION=FILE]..."

  /** `--args-file FILE` stands for the NUL-separated arguments in FILE (how build-db.sh passes them, so
    * sbt's command parser never splits a path with spaces or runs a `;`-chained command). */
  def expandArgsFile(args: Seq[String]): Seq[String] = args match {
    case Seq("--args-file", f, tail @ _*) =>
      val text = new String(java.nio.file.Files.readAllBytes(Paths.get(f)), java.nio.charset.StandardCharsets.UTF_8)
      text.split("\u0000", -1).toSeq.dropRight(1) ++ expandArgsFile(tail)
    case Seq(h, tail @ _*) => h +: expandArgsFile(tail)
    case _                 => Seq.empty
  }

  /** Parses the options shared by every SpinalDB entry point; returns the options and the positional args. */
  def parse(args: Seq[String], base: DbOptions = DbOptions()): (DbOptions, Option[String], Seq[String]) = {
    var o     = base
    var rtl   = Option.empty[String]
    var roots = Seq.empty[java.nio.file.Path]
    val pos   = Seq.newBuilder[String]
    var rest  = expandArgsFile(args).toList
    while (rest.nonEmpty) {
      rest match {
        case "--rtl" :: d :: t         => rtl = Some(d); rest = t
        case "--source-root" :: d :: t => roots :+= Paths.get(d); rest = t
        case "--no-pdg" :: t           => o = o.copy(pdg = false); rest = t
        case "--pdg-tables" :: t       => o = o.copy(pdgTables = true); rest = t
        case "--no-blocks" :: t        => o = o.copy(blocks = false); rest = t
        case "--no-hgldd" :: t         => o = o.copy(hgldd = false); rest = t
        case "--blackbox-source" :: kv :: t =>
          // The external body of a BlackBox (its Verilog/VHDL), hashed into the database so a diff can compare it.
          val (k, v) = kv.span(_ != '=')
          require(k.nonEmpty && v.length > 1, s"--blackbox-source needs DEFINITION=FILE, got $kv")
          o = o.copy(blackboxSources = o.blackboxSources.updated(k, o.blackboxSources.getOrElse(k, Nil) :+ Paths.get(v.drop(1))))
          rest = t
        case "--meta" :: kv :: t       =>
          val (k, v) = kv.span(_ != '='); o = o.copy(meta = o.meta :+ (k -> v.drop(1))); rest = t
        case flag :: _ if flag.startsWith("--") => sys.error(s"unknown option $flag\n$usage")
        case p :: t                    => pos += p; rest = t
        case Nil                       =>
      }
    }
    (if (roots.nonEmpty) o.copy(sourceRoots = roots) else o, rtl, pos.result())
  }

  def main(args: Array[String]): Unit = {
    val (opts, rtl, pos) = parse(args.toSeq)
    require(pos.length == 2, usage)
    val cls = Class.forName(pos(0))
    SpinalDB.generate(SpinalConfig(targetDirectory = rtl.getOrElse("target/spinaldb-rtl")), new File(pos(1)),
      opts.copy(meta = opts.meta :+ ("design" -> pos(0))))(cls.getDeclaredConstructor().newInstance().asInstanceOf[Component])
  }
}

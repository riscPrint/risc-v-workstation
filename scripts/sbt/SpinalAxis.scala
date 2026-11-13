import sbt._
import sbt.Keys._

/** The SpinalHDL version axis of the workstation's Spinal libraries.
  *
  * Release axis (default): the libraries compile against the released SpinalHDL jars.
  * Source axis: `RVW_SPINAL_SOURCE` names a SpinalHDL source checkout (for example a core's pinned
  * `ext/SpinalHDL`). The libraries then compile against that checkout's `core`, `lib`, `sim` and
  * `idslplugin` projects, so a core that pins its own SpinalHDL links libraries built for it.
  * Both axes cross-build for Scala 2.13.14 and 2.12.18. Select the Scala version with `'++V!'`
  * (a SpinalHDL source build defaults to 2.12). Library code stays source-compatible with both:
  * use `scala.collection.compat._` for 2.13-only collection methods on 2.12.
  * Each axis writes to its own target directory, so the two never share class files. */
object SpinalAxis {
  val release = "1.15.0"
  val source: Option[File] = sys.env.get("RVW_SPINAL_SOURCE").filter(_.nonEmpty).map(p => file(p).getCanonicalFile)

  /** Short name of the active axis: `release-1.15.0` or `source-<checkout hash>`. */
  def axis: String = source.fold(s"release-$release") { dir =>
    val head = scala.util.Try(scala.sys.process.Process(Seq("git", "-C", dir.getPath, "rev-parse", "--short=12", "HEAD")).!!.trim).getOrElse("")
    s"source-${if (head.nonEmpty) head else Integer.toHexString(dir.getPath.hashCode)}"
  }

  private def ref(module: String): ProjectReference = ProjectRef(source.get, module)

  /** `dependsOn` targets of the source axis (empty on the release axis). */
  def projects(modules: String*): Seq[ClasspathDep[ProjectReference]] =
    source.toSeq.flatMap(_ => modules.map(m => ClasspathDependency(ref(m), None)))

  /** SpinalHDL dependency settings for the given modules (`core`, `lib`, `sim`). */
  def settings(modules: String*): Seq[Setting[_]] = Seq(
    // Scala 2.13 collection names on Scala 2.12 (scala.jdk.CollectionConverters, toIntOption, ...).
    libraryDependencies += "org.scala-lang.modules" %% "scala-collection-compat" % "2.12.0",
    crossScalaVersions := Seq("2.13.14", "2.12.18")) ++ (source match {
    case None => Seq(libraryDependencies ++= modules.map(m => "com.github.spinalhdl" %% s"spinalhdl-$m" % release) :+
      compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % release))
    case Some(_) =>
      val plugin = ref("idslplugin")
      Seq(
        scalacOptions += (plugin / Compile / packageBin / artifactPath).map(f => s"-Xplugin:${f.getAbsolutePath}").value,
        scalacOptions += "-Xplugin-require:idsl-plugin",
        Compile / compile := (Compile / compile).dependsOn(plugin / Compile / packageBin).value,
        target := baseDirectory.value / "target" / s"spinal-$axis")
  })
}

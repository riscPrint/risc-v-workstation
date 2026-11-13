// Run with `sbt '++2.13.14!' ...`: the pinned SpinalHDL source build defaults to Scala 2.12.
ThisBuild / scalaVersion := "2.13.14"
ThisBuild / version := "0.1.0"
val workstation = file(sys.env("RVW_HOME")).getCanonicalFile
val vexii = file(sys.env.getOrElse("VEXIIRISCV", "..")).getCanonicalFile
val spinal = vexii / "ext/SpinalHDL"

// VexiiRiscv needs its pinned SpinalHDL source revision (ext/SpinalHDL), not the 1.15.0 release.
// The released jars that RiscvSim and SpinalDB declare are excluded and replaced by that source.
lazy val spinalIdsl = ProjectRef(spinal, "idslplugin")
lazy val spinalCore = ProjectRef(spinal, "core")
lazy val spinalLib = ProjectRef(spinal, "lib")
lazy val spinalSim = ProjectRef(spinal, "sim")

val pinnedSpinal = Seq(
  // The exclusion also drops the source projects' own library dependencies; declare them here.
  excludeDependencies += ExclusionRule("com.github.spinalhdl"),
  libraryDependencies ++= Seq(
    "org.scala-lang" % "scala-reflect" % scalaVersion.value,
    "org.scala-lang" % "scala-compiler" % scalaVersion.value,
    "com.github.scopt" %% "scopt" % "4.1.0",
    "com.lihaoyi" %% "sourcecode" % "0.3.0",
    "commons-io" % "commons-io" % "2.11.0",
    "net.openhft" % "affinity" % "3.23.2",
    "org.slf4j" % "slf4j-simple" % "2.0.5",
    "com.github.oshi" % "oshi-core" % "6.4.0"),
  scalacOptions += (spinalIdsl / Compile / packageBin / artifactPath).map { f => s"-Xplugin:${f.getAbsolutePath}" }.value,
  scalacOptions += "-Xplugin-require:idsl-plugin",
  Compile / compile := (Compile / compile).dependsOn(spinalIdsl / Compile / packageBin).value)

// Compile the external core sources and the rvls trace interface here.
// Consume the generic simulator as a library. The core build files stay unused.
lazy val root = (project in file("."))
  .dependsOn(ProjectRef(workstation / "RiscvSim", "riscvsim"), spinalIdsl, spinalCore, spinalLib, spinalSim)
  .settings(pinnedSpinal)
  .settings(
    name := "rvw-vexiiriscv",
    Compile / unmanagedSourceDirectories ++= Seq(
      vexii / "src/main/scala",
      vexii / "ext/rvls/bindings/spinal",
      vexii / "ext/rvls/bindings/jni"),
    libraryDependencies ++= Seq(
      "org.scalatest" %% "scalatest" % "3.2.17",
      "org.yaml" % "snakeyaml" % "1.8",
      "net.fornwall" % "jelf" % "0.7.0",
      "org.scream3r" % "jssc" % "2.8.0",
      "com.lihaoyi" %% "ujson" % "3.3.1"),
    scalacOptions ++= Seq("-feature", "-language:reflectiveCalls"),
    fork := true,
    run / javaOptions ++= Seq("-Xss64m", "-Xmx3g")
  )

lazy val db = (project in file("db"))
  .dependsOn(root, ProjectRef(workstation / "SpinalDB/spinaldb", "spinaldb"))
  .settings(pinnedSpinal)
  .settings(
    name := "rvw-vexiiriscv-db",
    fork := true,
    run / javaOptions ++= Seq("-Xss64m", "-Xmx3g"))

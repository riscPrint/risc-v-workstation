ThisBuild / scalaVersion := "2.13.14"
ThisBuild / organization := "spinaldb"
ThisBuild / version := "0.1.0-SNAPSHOT"

// Naming, source locations, two-pass elaboration and HGLDD come from SpinalWaves; the PDG extractor
// and its naming phase from SpinalTrace.
lazy val spinalwaves = ProjectRef(file("../../SpinalWaves/spinalwaves"), "spinalwaves")
lazy val spinaltrace = ProjectRef(file("../../SpinalTrace/spinaltrace"), "spinaltrace")

// SpinalBlocks' extractor is compiled from its sources instead of through a ProjectRef: loading the
// SpinalBlocks build would also load its `boom` project and the spinal-boom checkout it points at.

lazy val spinaldb = (project in file("."))
  .dependsOn(spinalwaves, spinaltrace)
  .dependsOn(SpinalAxis.projects("core", "lib"): _*)
  .settings(SpinalAxis.settings("core", "lib"))
  .settings(
    name := "spinaldb",
    libraryDependencies ++= Seq(
      "com.lihaoyi" %% "ujson" % "3.3.1",
      "org.xerial" % "sqlite-jdbc" % "3.53.4.0",
      "org.scalatest" %% "scalatest" % "3.2.19" % Test
    ),
    Compile / unmanagedSourceDirectories += (baseDirectory.value / "../../SpinalBlocks/spinalblocks/src/main/scala").getCanonicalFile,
    // SpinalTrace's example designs (GCD, Features) double as test designs here.
    Test / unmanagedSourceDirectories += (baseDirectory.value / "../../SpinalTrace/examples/src").getCanonicalFile,
    scalacOptions ++= Seq("-deprecation", "-feature", "-language:reflectiveCalls"),
    fork := true,
    javaOptions ++= Seq("-Xss64m"),
    Test / parallelExecution := false
  )

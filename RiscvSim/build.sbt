ThisBuild / scalaVersion := "2.13.14"
ThisBuild / organization := "riscvsim"
ThisBuild / version := "0.1.0-SNAPSHOT"

// Generic pieces for simulating any Spinal RISC-V core with RVFI: ELF loading, tohost,
// the RVFI trace writer, result.json, and the run-contract command line (build / run / run-many).
// No core-specific code here.
lazy val riscvsim = (project in file("."))
  .dependsOn(ProjectRef(file("../SpinalTrace/spinaltrace"), "spinaltrace"))
  .dependsOn(ProjectRef(file("../SpinalProbes"), "spinalprobes"))
  .dependsOn(ProjectRef(file("../SpinalChecks"), "spinalchecks") % "test->compile")
  .dependsOn(ProjectRef(file("../SpinalDB/spinaldb"), "spinaldb") % "test->compile")
  .dependsOn(SpinalAxis.projects("core", "sim"): _*)
  .settings(SpinalAxis.settings("core", "sim"))
  .settings(
    name := "riscvsim",
    libraryDependencies ++= Seq(
      "com.lihaoyi" %% "ujson" % "3.3.1",
      "net.java.dev.jna" % "jna" % "5.12.1",
      "org.scalatest" %% "scalatest" % "3.2.19" % Test
    ),
    scalacOptions ++= Seq("-deprecation", "-feature", "-language:reflectiveCalls"),
    fork := true,
    Test / parallelExecution := false,
    // Keep native test caches private to this checkout.
    Test / envVars += "RISCVSIM_WORK" -> (baseDirectory.value / "target" / "test-work").getAbsolutePath,
    // What boom/run.sh passes to real runs, so the replay-path test runs in the plain suite.
    Test / javaOptions ++= Seq(
      s"-Driscvsim.script=${(baseDirectory.value / "boom" / "run.sh").getAbsolutePath}",
      s"-Driscvsim.tools=${baseDirectory.value.getParentFile.getAbsolutePath}")
  )

ThisBuild / scalaVersion := "2.13.14"
ThisBuild / organization := "riscvsim"
ThisBuild / version := "0.1.0-SNAPSHOT"

val spinalVersion = "1.15.0"

// Generic pieces for simulating any Spinal RISC-V core with RVFI: ELF loading, tohost,
// the RVFI trace writer, result.json, and the run-contract command line (build / run / run-many).
// No core-specific code here.
lazy val riscvsim = (project in file("."))
  .settings(
    name := "riscvsim",
    libraryDependencies ++= Seq(
      "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
      "com.github.spinalhdl" %% "spinalhdl-sim" % spinalVersion,
      compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion),
      "com.lihaoyi" %% "ujson" % "3.3.1",
      "org.scalatest" %% "scalatest" % "3.2.19" % Test
    ),
    scalacOptions ++= Seq("-deprecation", "-feature", "-language:reflectiveCalls"),
    fork := true,
    Test / parallelExecution := false,
    // What boom/run.sh passes to real runs, so the replay-path test runs in the plain suite.
    Test / javaOptions ++= Seq(
      s"-Driscvsim.script=${(baseDirectory.value / "boom" / "run.sh").getAbsolutePath}",
      s"-Driscvsim.tools=${baseDirectory.value.getParentFile.getAbsolutePath}")
  )

ThisBuild / scalaVersion := "2.13.14"
ThisBuild / organization := "spinalkonata"
ThisBuild / version := "0.1.0-SNAPSHOT"
val spinalVersion = "1.15.0"

lazy val root = (project in file(".")).settings(
  name := "spinalkonata",
  libraryDependencies ++= Seq(
    "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
    "com.github.spinalhdl" %% "spinalhdl-lib" % spinalVersion,
    compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion),
    "org.scalatest" %% "scalatest" % "3.2.19" % Test
  ),
  fork := true,
  Test / parallelExecution := false,
  javaOptions ++= Seq("-Xmx2g", "-XX:ActiveProcessorCount=2")
)


// Test the adapter's input boundary without compiling or writing to the BOOM checkout.
// Reuse the canonical ELF reader instead of adding another parser.
lazy val inputs = (project in file("inputs")).settings(
  name := "spinalkonata-input-tests",
  Compile / unmanagedSources ++= Seq(
    baseDirectory.value.getParentFile / "boom/src/main/scala/spinalkonata/boom/InputCapture.scala",
    baseDirectory.value.getParentFile.getParentFile / "RiscvSim/src/main/scala/riscvsim/ElfFile.scala"),
  libraryDependencies ++= Seq("com.lihaoyi" %% "ujson" % "3.3.1",
    "org.scalatest" %% "scalatest" % "3.2.19" % Test),
  Test / unmanagedSources += baseDirectory.value.getParentFile /
    "boom/src/main/scala/spinalkonata/boom/BenchTrace.scala",
  Test / parallelExecution := false,
  fork := true,
  javaOptions += s"-Dspinalkonata.repo=${baseDirectory.value.getParentFile.getParentFile.getAbsolutePath}",
  javaOptions ++= Seq("-Xmx1g", "-XX:ActiveProcessorCount=2")
)

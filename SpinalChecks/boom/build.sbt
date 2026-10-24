// SpinalChecks applied to spinal-boom from the outside: elaborates BOOM with the checks phase and runs
// riscv-tests/benchmarks in Verilator through the clone's own harness (boom.sim.BoomSim).
// The BOOM sources come from SPINAL_BOOM (default: the private clone ../../../spinal-boom-eda).
// Builds touching that clone run under scripts/with-lock.sh boom (see docs/PLATFORM_CONTRACTS.md).
ThisBuild / scalaVersion := "2.13.14"

val spinalVersion = "1.15.0"
val spinalBoomDir = file(sys.env.getOrElse("SPINAL_BOOM", "../../../spinal-boom-eda"))

lazy val spinalchecks = ProjectRef(file(".."), "spinalchecks")

lazy val boom = (project in file("."))
  .dependsOn(spinalchecks, ProjectRef(spinalBoomDir, "root") % "compile->compile;compile->test")
  .settings(
    name := "spinalchecks-boom",
    libraryDependencies += compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion),
    scalacOptions ++= Seq("-deprecation", "-feature", "-language:reflectiveCalls"),
    fork := true,
    javaOptions ++= Seq("-Xss64m", "-Xmx8g"),
    outputStrategy := Some(StdoutOutput)
  )

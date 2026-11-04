// Prototype: BOOM's run-contract adapter with a SpinalTrace-instrumented model (see README.md).
// Reuses RiscvSim's generic driver and BOOM's run loop unchanged; only the model build differs.
ThisBuild / scalaVersion := "2.13.14"
val spinalVersion = "1.15.0"

lazy val riscvsimBoom = ProjectRef(file("../boom"), "boom")
lazy val spinaltrace = ProjectRef(file("../../SpinalTrace/spinaltrace").getCanonicalFile, "spinaltrace")

lazy val root = (project in file("."))
  .dependsOn(riscvsimBoom, spinaltrace)
  .settings(
    name := "riscvsim-boom-spinaltrace",
    libraryDependencies += compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion),
    scalacOptions ++= Seq("-deprecation", "-feature", "-language:reflectiveCalls")
  )

ThisBuild / scalaVersion := "2.13.14"
lazy val root = (project in file("."))
  .dependsOn(ProjectRef(file("../../RiscvSim"), "riscvsim"), ProjectRef(file("../../SpinalChecks"), "spinalchecks"))
  .settings(
    name := "ooo-mini",
    libraryDependencies += compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % "1.15.0"),
    scalacOptions ++= Seq("-language:reflectiveCalls"),
    fork := true,
    run / javaOptions ++= Seq("-Xmx2g", "-XX:ActiveProcessorCount=2")
  )

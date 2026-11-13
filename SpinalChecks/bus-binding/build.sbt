ThisBuild / scalaVersion := "2.13.14"
ThisBuild / version := "0.1.0-SNAPSHOT"
lazy val root = (project in file("."))
  .dependsOn(ProjectRef(file(".."), "spinalchecks"),
    ProjectRef(file("../../SpinalDB/spinaldb"), "spinaldb"))
  .settings(
    name := "checks-bus-binding",
    libraryDependencies += compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % "1.15.0"),
    fork := true,
    run / javaOptions ++= Seq("-Xss64m", "-Xmx3g"))

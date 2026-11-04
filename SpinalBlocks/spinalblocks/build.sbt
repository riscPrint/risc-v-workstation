ThisBuild / scalaVersion := "2.13.14"
ThisBuild / organization := "spinalblocks"
ThisBuild / version := "0.1.0-SNAPSHOT"

val spinalVersion = "1.15.0"

// Source locations (two-pass elaboration, source-root lookup) come from the sibling SpinalWaves project.
lazy val spinalwaves = ProjectRef(file("../../SpinalWaves/spinalwaves"), "spinalwaves")

lazy val spinalblocks = (project in file("."))
  .dependsOn(spinalwaves)
  .settings(
    name := "spinalblocks",
    libraryDependencies ++= Seq(
      "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
      "com.github.spinalhdl" %% "spinalhdl-lib" % spinalVersion,
      compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion),
      "com.lihaoyi" %% "ujson" % "3.3.1",
      "org.scalatest" %% "scalatest" % "3.2.19" % Test
    ),
    scalacOptions ++= Seq("-deprecation", "-feature", "-language:reflectiveCalls"),
    fork := true,
    Test / parallelExecution := false
  )


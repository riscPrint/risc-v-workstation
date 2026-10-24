ThisBuild / scalaVersion := "2.13.14"
ThisBuild / organization := "spinalchecks"
ThisBuild / version := "0.1.0-SNAPSHOT"

val spinalVersion = "1.15.0"

// The generic library: assertions generated from an elaborated Spinal design. No core-specific code here;
// the BOOM adapter is a separate sbt build in boom/ (it pulls in the spinal-boom sources).
lazy val spinalchecks = (project in file("."))
  .settings(
    name := "spinalchecks",
    libraryDependencies ++= Seq(
      "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
      "com.github.spinalhdl" %% "spinalhdl-lib" % spinalVersion,
      compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion),
      "org.scalatest" %% "scalatest" % "3.2.19" % Test
    ),
    scalacOptions ++= Seq("-deprecation", "-feature", "-language:reflectiveCalls"),
    fork := true,
    javaOptions ++= Seq("-Xss16m"),
    Test / parallelExecution := false
  )

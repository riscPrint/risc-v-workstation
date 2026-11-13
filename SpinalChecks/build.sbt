ThisBuild / scalaVersion := "2.13.14"
ThisBuild / organization := "spinalchecks"
ThisBuild / version := "0.1.0-SNAPSHOT"

// The generic library: assertions generated from an elaborated Spinal design. No core-specific code here;
// the BOOM adapter is a separate sbt build in boom/ (it pulls in the spinal-boom sources).
lazy val spinalchecks = (project in file("."))
  .dependsOn(SpinalAxis.projects("core", "lib"): _*)
  .settings(SpinalAxis.settings("core", "lib"))
  .settings(
    name := "spinalchecks",
    libraryDependencies ++= Seq(
      "org.scalatest" %% "scalatest" % "3.2.19" % Test
    ),
    scalacOptions ++= Seq("-deprecation", "-feature", "-language:reflectiveCalls"),
    fork := true,
    javaOptions ++= Seq("-Xss16m"),
    Test / parallelExecution := false
  )

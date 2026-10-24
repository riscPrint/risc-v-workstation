ThisBuild / scalaVersion := "2.13.14"
ThisBuild / organization := "spinaltrace"
ThisBuild / version := "0.1.0-SNAPSHOT"

val spinalVersion = "1.15.0"

// Shared naming / location / HGLDD API from the sibling SpinalWaves project (docs/CONTRACT.md there).
lazy val spinalwaves = ProjectRef(file("../../SpinalWaves/spinalwaves"), "spinalwaves")

lazy val spinaltrace = (project in file("."))
  .dependsOn(spinalwaves)
  .settings(
    name := "spinaltrace",
    libraryDependencies ++= Seq(
      "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
      "com.github.spinalhdl" %% "spinalhdl-lib" % spinalVersion,
      compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion),
      "com.lihaoyi" %% "ujson" % "3.3.1",
      "org.scalatest" %% "scalatest" % "3.2.19" % Test
    ),
    // Example designs live at the repository root so they can be read on their own.
    Test / unmanagedSourceDirectories += baseDirectory.value / ".." / "examples" / "src",
    scalacOptions ++= Seq("-deprecation", "-feature", "-language:reflectiveCalls"),
    Test / fork := true,
    // The tests call the Rust CLI (build it first: cargo build --release -p spinaltrace-cli) and must
    // never wait for input.
    Test / envVars ++= Map(
      "SPINALTRACE_CLI" -> sys.env.getOrElse("SPINALTRACE_CLI", (baseDirectory.value / ".." / "target" / "release" / "spinaltrace-cli").getCanonicalPath),
      "SPINALTRACE_NONINTERACTIVE" -> "1"
    ),
    Test / parallelExecution := false
  )

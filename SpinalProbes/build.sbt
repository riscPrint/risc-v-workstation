ThisBuild / scalaVersion := "2.13.14"
ThisBuild / organization := "spinalprobes"
ThisBuild / version := "0.1.0-SNAPSHOT"

// The RTL side of the probe layer: a typed API a core calls at elaboration.
// Depends on spinalhdl-core and -sim (for the public-signal tag) only. The simulation
// sampler lives in RiscvSim (riscvsim.ProbeCollector).
lazy val spinalprobes = (project in file(".")).dependsOn(SpinalAxis.projects("core", "sim"): _*).settings(SpinalAxis.settings("core", "sim")).settings(
  name := "spinalprobes",
  libraryDependencies ++= Seq(
    "org.scalatest" %% "scalatest" % "3.2.19" % Test
  ),
  fork := true,
  Test / parallelExecution := false,
  javaOptions ++= Seq("-Xmx1g", "-XX:ActiveProcessorCount=2")
)

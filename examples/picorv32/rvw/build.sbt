// RVW_HOME selects the installed workstation. The adapter is the generic RiscvSim MappedAdapter.
ThisBuild / scalaVersion := "2.13.14"
val workstation = file(sys.env("RVW_HOME")).getCanonicalFile
val coreSource = file(sys.env.getOrElse("RVW_CORE_SOURCE", "..")).getCanonicalFile
lazy val root = (project in file("."))
  .dependsOn(ProjectRef(workstation / "RiscvSim", "riscvsim"))
  .settings(name := "rvw-core-adapter", fork := true)

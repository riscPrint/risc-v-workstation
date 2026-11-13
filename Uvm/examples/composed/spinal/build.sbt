ThisBuild / scalaVersion := "2.13.14"
val spinalVersion = "1.15.0"
libraryDependencies ++= Seq(
 "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
 "com.github.spinalhdl" %% "spinalhdl-lib" % spinalVersion,
 compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion)
)
Compile / unmanagedSourceDirectories ++= Seq(
 baseDirectory.value / "../generated",
 baseDirectory.value / "../../../../SpinalSoc/src/main/scala"
)
fork := true

// SpinalSoc protocol monitors use the shared assertion library.
lazy val root = (project in file("."))
  .dependsOn(ProjectRef(file("../../../../SpinalChecks"), "spinalchecks"))

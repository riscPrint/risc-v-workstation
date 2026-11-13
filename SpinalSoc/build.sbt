ThisBuild / scalaVersion := "2.13.14"
ThisBuild / organization := "rvwsoc"
ThisBuild / version := "0.1.0-SNAPSHOT"
val spinalVersion = "1.15.0"
libraryDependencies ++= Seq(
  "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
  "com.github.spinalhdl" %% "spinalhdl-lib" % spinalVersion,
  compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion)
)
Compile / unmanagedSourceDirectories += baseDirectory.value / "generated"
fork := true

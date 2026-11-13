ThisBuild / scalaVersion := "2.13.14"
val spinalVersion = "1.15.0"
lazy val tiny = (project in file("."))
  .settings(
    name := "tiny",
    libraryDependencies ++= Seq(
      "com.github.spinalhdl" %% "spinalhdl-core" % spinalVersion,
      "com.github.spinalhdl" %% "spinalhdl-lib" % spinalVersion,
      compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % spinalVersion)))

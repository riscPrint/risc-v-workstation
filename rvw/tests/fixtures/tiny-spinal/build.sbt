ThisBuild / scalaVersion := "2.13.14"
lazy val cpu = (project in file(".")).settings(
  libraryDependencies ++= Seq(
    "com.github.spinalhdl" %% "spinalhdl-core" % "1.15.0",
    "com.github.spinalhdl" %% "spinalhdl-lib" % "1.15.0",
    compilerPlugin("com.github.spinalhdl" %% "spinalhdl-idsl-plugin" % "1.15.0")))

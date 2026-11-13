"""Input declarations for generated external Spinal adapters."""
INPUT_COMMANDS = '''[
  "ar", "awk", "basename", "cat", "chmod", "cmp", "cp", "cut", "date", "dirname", "du", "env",
  "expr", "find", "getconf", "grep", "head", "hostname", "ld", "ln", "mkdir", "mktemp", "mv", "nice",
  "perl", "ps", "readlink", "realpath", "rm", "rmdir", "sbt", "sed", "sh", "shasum", "sleep",
  "sort", "stat", "tail", "tee", "touch", "tr", "uname", "unzip", "wc", "which", "xargs",
  "zip",
]'''
INPUT_ENV = '''[
  "AR", "BASH_ENV", "CC", "CCACHE_CONFIGPATH", "CCACHE_PATH", "CCACHE_PREFIX",
  "CCC_OVERRIDE_OPTIONS", "CFLAGS", "COMPILER_PATH", "COURSIER_CACHE", "COURSIER_REPOSITORIES",
  "CPATH", "CPLUS_INCLUDE_PATH", "CPP", "CPPFLAGS", "CXX", "CXXFLAGS", "C_INCLUDE_PATH",
  "DEVELOPER_DIR", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH", "ENV", "GCC_EXEC_PREFIX",
  "GNUMAKEFLAGS", "HOME", "IVY_HOME", "JAVA_HOME", "JAVA_OPTS", "JAVA_TOOL_OPTIONS", "JDK_HOME",
  "JDK_JAVA_OPTIONS", "JVM_OPTS", "LDFLAGS", "LDLIBS", "LD_LIBRARY_PATH", "LD_PRELOAD",
  "LIBRARY_PATH", "LINK", "MACOSX_DEPLOYMENT_TARGET", "MAKE", "MAKEFILES", "MAKEFLAGS",
  "MAKEOVERRIDES", "MFLAGS", "OBJCACHE", "OBJC_INCLUDE_PATH", "OPT", "OPT_FAST", "OPT_GLOBAL",
  "OPT_SLOW", "PATH", "PERL5LIB", "PERL5OPT", "PYTHONHOME", "PYTHONPATH", "RISCVSIM_COVERAGE", "RISCVSIM_REQUIRES",
  "RISCVSIM_CP_CACHE", "RISCVSIM_EXTRA_INPUTS", "RISCVSIM_MAKE", "RISCVSIM_MAKE_JOBS",
  "RISCVSIM_WORK", "RISCVSIM_XMX", "SBT_BOOT_DIRECTORY", "SBT_GLOBAL_BASE", "SBT_IVY_HOME",
  "SBT_JAVA_OPTS", "SBT_OPTS", "SDKROOT", "RVW_HOME", "RVW_CORE_SOURCE", "RVW_CORE_MAP", "SPINAL_MAKE_CMD",
  "SPINAL_VERILATOR_FLAGS", "USER_CPPFLAGS", "USER_LDFLAGS", "USER_LDLIBS", "VERILATOR_BIN",
  "VERILATOR_FLAGS", "VERILATOR_GDB", "VERILATOR_GDBBT", "VERILATOR_NO_OPT", "VERILATOR_ROOT",
  "VFLAGS", "_JAVA_OPTIONS",
]'''

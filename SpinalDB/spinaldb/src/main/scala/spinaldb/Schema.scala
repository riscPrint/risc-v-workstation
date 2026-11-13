package spinaldb

/** SQLite schema and typed-key contract: see SpinalDB/README.md and C6.
  * Bump the version when a reader would misread an older database. */
object Schema {
  val Version = "rvw.designdb/20"

  val ddl: Seq[String] = Seq(
    "CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)",
    "CREATE TABLE files(id INTEGER PRIMARY KEY, path TEXT NOT NULL UNIQUE)",
    """CREATE TABLE components(
      |  id INTEGER PRIMARY KEY, parent_id INTEGER, path TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
      |  module TEXT, class_name TEXT, blackbox INTEGER NOT NULL DEFAULT 0, depth INTEGER NOT NULL,
      |  file_id INTEGER, line INTEGER, tags TEXT)""".stripMargin,
    """CREATE TABLE areas(
      |  id INTEGER PRIMARY KEY, component_id INTEGER NOT NULL, parent_id INTEGER, name TEXT NOT NULL,
      |  path TEXT NOT NULL, class_name TEXT, file_id INTEGER, line INTEGER)""".stripMargin,
    """CREATE TABLE clock_domains(
      |  id INTEGER PRIMARY KEY, clock TEXT, reset TEXT, reset_kind TEXT, reset_active_high INTEGER,
      |  clock_enable TEXT, soft_reset TEXT, clock_edge TEXT, clock_enable_active_high INTEGER,
      |  soft_reset_active_high INTEGER, clock_key TEXT, reset_key TEXT, clock_enable_key TEXT,
      |  soft_reset_key TEXT)""".stripMargin,
    """CREATE TABLE signals(
      |  id INTEGER PRIMARY KEY, component_id INTEGER NOT NULL, area_id INTEGER,
      |  name TEXT NOT NULL, path TEXT NOT NULL, spinal_path TEXT,
      |  kind TEXT NOT NULL, direction TEXT, type TEXT, width INTEGER, data_type TEXT,
      |  clock_domain_id INTEGER, reset_value TEXT, clock_role TEXT,
      |  generated INTEGER NOT NULL DEFAULT 0, pruned INTEGER NOT NULL DEFAULT 0, tags TEXT, port_index INTEGER,
      |  file_id INTEGER, line INTEGER)""".stripMargin,
    """CREATE TABLE bundles(
      |  id INTEGER PRIMARY KEY, component_id INTEGER NOT NULL, parent_id INTEGER, path TEXT NOT NULL,
      |  class_name TEXT, direction TEXT, signals INTEGER, bits INTEGER, file_id INTEGER, line INTEGER)""".stripMargin,
    """CREATE TABLE memories(
      |  id INTEGER PRIMARY KEY, signal_id INTEGER NOT NULL, component_id INTEGER NOT NULL, name TEXT NOT NULL,
      |  path TEXT NOT NULL, width INTEGER, depth INTEGER, technology TEXT, init_sha256 TEXT, init_words INTEGER,
      |  key TEXT, file_id INTEGER, line INTEGER)""".stripMargin,
    """CREATE TABLE mem_ports(
      |  id INTEGER PRIMARY KEY, memory_id INTEGER NOT NULL, component_id INTEGER, kind TEXT NOT NULL,
      |  address TEXT, data TEXT, enable TEXT, write_enable TEXT, mask TEXT, clock_domain_id INTEGER,
      |  cond_id INTEGER, key TEXT, file_id INTEGER, line INTEGER, output_id INTEGER)""".stripMargin,
    """CREATE TABLE statements(
      |  id INTEGER PRIMARY KEY, component_id INTEGER NOT NULL, kind TEXT NOT NULL, key TEXT, clock_domain_id INTEGER,
      |  cond_id INTEGER, file_id INTEGER, line INTEGER)""".stripMargin,
    """CREATE TABLE blackboxes(
      |  component_id INTEGER PRIMARY KEY, generics TEXT, rtl_paths TEXT, body_sha256 TEXT, body_from TEXT,
      |  key TEXT NOT NULL)""".stripMargin,
    """CREATE TABLE conds(
      |  id INTEGER PRIMARY KEY, parent_id INTEGER, component_id INTEGER NOT NULL, kind TEXT NOT NULL,
      |  expr TEXT, keys TEXT, key TEXT, signal_id INTEGER, file_id INTEGER, line INTEGER)""".stripMargin,
    """CREATE TABLE assignments(
      |  id INTEGER PRIMARY KEY, target_id INTEGER NOT NULL, component_id INTEGER NOT NULL, kind TEXT NOT NULL,
      |  range TEXT, source TEXT, enable TEXT, mask TEXT, key TEXT, cond_id INTEGER, seq INTEGER NOT NULL,
      |  file_id INTEGER, line INTEGER)""".stripMargin,
    "CREATE TABLE assign_reads(assignment_id INTEGER NOT NULL, signal_id INTEGER NOT NULL, kind TEXT NOT NULL)",
    "CREATE TABLE cond_reads(cond_id INTEGER NOT NULL, signal_id INTEGER NOT NULL)",
    """CREATE TABLE edges(src INTEGER NOT NULL, dst INTEGER NOT NULL, kind TEXT NOT NULL,
      |  PRIMARY KEY(src, dst, kind)) WITHOUT ROWID""".stripMargin,
    """CREATE TABLE pdg_vertices(id INTEGER PRIMARY KEY, name TEXT, kind TEXT, clocked INTEGER, module_path TEXT,
      |  assigns_to TEXT, file_id INTEGER, line INTEGER)""".stripMargin,
    "CREATE TABLE pdg_edges(src INTEGER NOT NULL, dst INTEGER NOT NULL, kind TEXT NOT NULL, clocked INTEGER)",
    "CREATE TABLE artifacts(name TEXT PRIMARY KEY, media_type TEXT, encoding TEXT, size INTEGER, content BLOB)",
    "CREATE TABLE clock_frequencies(clock_domain_id INTEGER NOT NULL, hz TEXT NOT NULL)",
    "CREATE TABLE rtl_files(path TEXT NOT NULL)",
    "CREATE TABLE input_files(path TEXT PRIMARY KEY, resolved TEXT, sha256 TEXT NOT NULL, size INTEGER NOT NULL, record TEXT NOT NULL)",
    "CREATE TABLE warnings(source TEXT NOT NULL, message TEXT NOT NULL)"
  )

  val indexes: Seq[String] = Seq(
    "CREATE INDEX signals_path ON signals(path)",
    "CREATE INDEX signals_spinal_path ON signals(spinal_path)",
    "CREATE INDEX signals_name ON signals(name)",
    "CREATE INDEX signals_component ON signals(component_id)",
    "CREATE INDEX components_parent ON components(parent_id)",
    "CREATE INDEX areas_component ON areas(component_id)",
    "CREATE INDEX bundles_component ON bundles(component_id)",
    "CREATE INDEX bundles_path ON bundles(path)",
    "CREATE INDEX assignments_target ON assignments(target_id)",
    "CREATE INDEX assign_reads_signal ON assign_reads(signal_id)",
    "CREATE INDEX assign_reads_assignment ON assign_reads(assignment_id)",
    "CREATE INDEX cond_reads_signal ON cond_reads(signal_id)",
    "CREATE INDEX cond_reads_cond ON cond_reads(cond_id)",
    "CREATE INDEX conds_parent ON conds(parent_id)",
    "CREATE INDEX edges_dst ON edges(dst, kind)",
    "CREATE INDEX memories_signal ON memories(signal_id)",
    "CREATE INDEX mem_ports_memory ON mem_ports(memory_id)",
    "CREATE INDEX pdg_edges_src ON pdg_edges(src)",
    "CREATE INDEX pdg_edges_dst ON pdg_edges(dst)"
  )
}

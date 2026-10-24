package spinaldb

import java.io.File
import java.sql.{Connection, DriverManager, PreparedStatement, Types}

import scala.collection.mutable

/** Thin batched writer over a fresh SQLite file (the old file is replaced). One transaction. */
class DbWriter(file: File) extends AutoCloseable {
  file.getAbsoluteFile.getParentFile.mkdirs()
  Seq(file, new File(file.getPath + "-journal"), new File(file.getPath + "-wal")).foreach(f => if (f.exists()) f.delete())

  Class.forName("org.sqlite.JDBC")
  val conn: Connection = DriverManager.getConnection("jdbc:sqlite:" + file.getAbsolutePath)
  private val st = conn.createStatement()
  st.execute("PRAGMA journal_mode=OFF")
  st.execute("PRAGMA synchronous=OFF")
  Schema.ddl.foreach(st.execute)
  conn.setAutoCommit(false)

  final class Table(sql: String) {
    private val ps: PreparedStatement = conn.prepareStatement(sql)
    private var pending = 0
    var rows = 0L
    def add(values: Any*): Unit = {
      var i = 1
      values.foreach { v =>
        v match {
          case null          => ps.setNull(i, Types.NULL)
          case None          => ps.setNull(i, Types.NULL)
          case Some(x)       => set(i, x)
          case x             => set(i, x)
        }
        i += 1
      }
      ps.addBatch(); pending += 1; rows += 1
      if (pending >= 5000) flush()
    }
    private def set(i: Int, v: Any): Unit = v match {
      case x: Int         => ps.setInt(i, x)
      case x: Long        => ps.setLong(i, x)
      case x: Boolean     => ps.setInt(i, if (x) 1 else 0)
      case x: Double      => ps.setDouble(i, x)
      case x: String      => ps.setString(i, x)
      case x: Array[Byte] => ps.setBytes(i, x)
      case x              => ps.setString(i, x.toString)
    }
    def flush(): Unit = if (pending > 0) { ps.executeBatch(); pending = 0 }
    def close(): Unit = { flush(); ps.close() }
  }

  private val tables = mutable.ArrayBuffer[Table]()
  def table(name: String, columns: String*): Table = {
    val t = new Table(s"INSERT INTO $name(${columns.mkString(",")}) VALUES(${columns.map(_ => "?").mkString(",")})")
    tables += t
    t
  }

  def exec(sql: String): Unit = st.execute(sql)

  def finish(indexes: Seq[String]): Unit = {
    tables.foreach(_.close())
    indexes.foreach(st.execute)
    conn.commit()
    conn.setAutoCommit(true)
    st.execute("ANALYZE")
  }

  override def close(): Unit = { st.close(); conn.close() }
}

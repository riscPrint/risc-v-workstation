# Design database language server

Run **RVW: Start Design Database Language Server** to start `rvw lsp`.
Set `lsp.database` to a design database. Set `lsp.executable` to a custom rvw
path if needed. Set `lsp.lintSettings` to run lint on document open and save.
Empty database settings use the selected project in the first workspace folder.
The workspace must be trusted. Run the command again after settings change.

Definitions, hover, structural references and captured source symbols use the
same database operations as agent queries. The server supports Scala, Verilog,
SystemVerilog and VHDL documents. Rebuild the database after source changes.
See `rvw/src/rvw/lsp/README.md` for evidence limits and source mapping limits.

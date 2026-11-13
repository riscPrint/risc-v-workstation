# rvw lsp

Run `rvw lsp --db design.db` for a stdio language server over the captured
SpinalDB or HDL database. The CLI also accepts `--project`. MCP `lsp_request`
exposes the same navigation methods to an agent without an editor.

The server supports definition, hover, references and document symbols.
A generated Verilog signal resolves through its module and stored name to its
Scala declaration. Hover includes type, width, clock domain, assignments and
stale-database warnings. References are stored assignment and condition lines.
They do not include every lexical occurrence of a name.

Pass `--lint-settings settings.json` to run `rvw lint` on document open and save.
Active findings with file locations become LSP diagnostics. Native lint timeouts
come from the settings file. Waived findings do not become active diagnostics.
The server processes requests in sequence. A lint run delays later requests.

In VS Code, run **RVW: Start Design Database Language Server**. Set
`lsp.database` and, if needed, `lsp.executable` and `lsp.lintSettings`.
An empty database setting uses the selected workspace project. The extension
uses the first workspace folder as its working directory. It requires workspace
trust before it starts a process. Run the command again to restart the client.

## Decisions

- Use the captured design database as the semantic source.
- Support full document synchronization and UTF-16 positions.
- Return an error for ambiguous instance names. Do not select an instance.
- Open the database for each request so a rebuilt database is used next time.
- Share navigation with agents through MCP. Use the standard VS Code LSP client.

## Limits

Rebuild after source changes. Open text supplies cursor tokens, but it does not
re-elaborate a design. Source locations refer to the captured elaboration.
Definitions use declaration lines with column zero. Document symbols use captured
source declarations, so generated RTL with only Scala bindings has no symbol
list. Macro uses and compound expressions need frontend token maps that are not
stored yet. Repeated instance declarations can be ambiguous. This server does
not supply completion, rename, live elaboration or logic equivalence checks.

# Build the local documentation site

The site uses MkDocs 1.6.1 and the existing Markdown. It has no hosting setup.
The build does not change the source READMEs or publish content.

```sh
uv sync --locked --extra dev --extra mcp --extra docs --project rvw
rvw/.venv/bin/python scripts/build-docs.py --out /tmp/rvw-docs-site
```

Open `/tmp/rvw-docs-site/index.html`. `use_directory_urls: false` permits local
file navigation. The nav covers setup, bring-your-own-core, architecture,
installation, command reference and contracts. The builder adds one page for
each tracked Markdown file, including nested tool and example READMEs. It copies all tracked
Markdown into a temporary tree so relative documentation links retain their
paths. Source-code links point to the exact Git revision on GitHub.

Use `--check --out /tmp/rvw-docs-site` for a staging check without MkDocs or
an output directory. This checks source availability, not HTML rendering.

The page count follows the tracked Markdown files. Existing broken Markdown targets and
stale anchors produce warnings. They remain visible in the build log. This is
not a clean link-check or command-execution result. Worked-path qualification,
CI link/code-block checks and legacy link repairs remain open under #58.

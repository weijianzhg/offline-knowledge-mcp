# Codex

Complete [setup](../setup.md) first. Use stdio to let Codex manage the process, or connect to an already running local HTTP server. These instructions use the [official MCP configuration format](https://developers.openai.com/codex/mcp/).

## stdio (recommended)

Replace `/absolute/path/offline-knowledge-mcp` with your checkout location:

```sh
codex mcp add offline-knowledge -- /absolute/path/offline-knowledge-mcp/.venv/bin/python -m knowledge_mcp.server --transport stdio --db /absolute/path/offline-knowledge-mcp/data/knowledge.sqlite3
```

Windows PowerShell, with your actual paths:

```powershell
codex mcp add offline-knowledge -- 'C:\path\offline-knowledge-mcp\.venv\Scripts\python.exe' -m knowledge_mcp.server --transport stdio --db 'C:\path\offline-knowledge-mcp\data\knowledge.sqlite3'
```

Alternatively merge the following into `~/.codex/config.toml` (`$HOME\.codex\config.toml` on Windows). Do not replace other settings:

```toml
[mcp_servers.offline-knowledge]
command = "/absolute/path/offline-knowledge-mcp/.venv/bin/python"
args = ["-m", "knowledge_mcp.server", "--transport", "stdio", "--db", "/absolute/path/offline-knowledge-mcp/data/knowledge.sqlite3"]
startup_timeout_sec = 20
```

For Windows TOML, single-quoted literal strings avoid backslash escaping:

```toml
[mcp_servers.offline-knowledge]
command = 'C:\path\offline-knowledge-mcp\.venv\Scripts\python.exe'
args = ['-m', 'knowledge_mcp.server', '--transport', 'stdio', '--db', 'C:\path\offline-knowledge-mcp\data\knowledge.sqlite3']
startup_timeout_sec = 20
```

Choose one entry for this server name. Restart the client/session after changes; run `codex mcp list` and inspect `/mcp` in the CLI. In the desktop app, use Settings → MCP servers to inspect or add the same command/arguments. Available UI labels can vary by client version.

## HTTP alternative

Start the HTTP process as described in [setup](../setup.md), then:

```sh
codex mcp add offline-knowledge --url http://127.0.0.1:8766/mcp
```

Use this instead of the stdio registration. Stop the terminal server with Ctrl+C when done. `codex mcp remove offline-knowledge` removes the registration.

## Grounding instructions

Optionally copy the [shared guidance](../agent-instructions.md) into a project's `AGENTS.md`. The server also sends grounding guidance during MCP initialization; an extra skill is not required. Ask Codex to list sources and search for `eclipse` after importing the sample. Confirm it calls tools and cites the returned URL; the sample uses example.org and is labelled synthetic.

These are local-client instructions. A hosted/cloud task has its own filesystem and network: your Mac's `127.0.0.1` and database are not accessible there. Install the server and data in that execution environment or provide a separately secured remote integration.

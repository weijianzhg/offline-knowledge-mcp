# Claude Code

Complete [setup](../setup.md) first. Claude Code can launch stdio processes or connect to Streamable HTTP. See its [official MCP documentation](https://code.claude.com/docs/en/mcp).

## stdio (recommended)

macOS/Linux, using your actual absolute paths:

```sh
claude mcp add --transport stdio offline-knowledge -- /absolute/path/offline-knowledge-mcp/.venv/bin/python -m knowledge_mcp.server --transport stdio --db /absolute/path/offline-knowledge-mcp/data/knowledge.sqlite3
```

Windows PowerShell:

```powershell
claude mcp add --transport stdio offline-knowledge -- 'C:\path\offline-knowledge-mcp\.venv\Scripts\python.exe' -m knowledge_mcp.server --transport stdio --db 'C:\path\offline-knowledge-mcp\data\knowledge.sqlite3'
```

`--` separates Claude's flags from the server command. The default scope is local to the current project; add `--scope user` before the server name for a personal registration shared across projects. No separate HTTP process is needed.

## HTTP alternative

Start the local HTTP server from [setup](../setup.md), then register its URL:

```sh
claude mcp add --transport http offline-knowledge http://127.0.0.1:8766/mcp
```

Choose one transport for this name. Restart the session, run `claude mcp get offline-knowledge`, then inspect `/mcp` inside Claude Code. Allow tools according to your normal permissions. To remove it, run `claude mcp remove offline-knowledge` in the same scope.

Ask Claude to list sources and search/read `eclipse`. Verify actual tool calls and the returned citation, not just an answer from memory. Optionally add the [shared grounding guidance](../agent-instructions.md) to `CLAUDE.md`. No particular Claude model or custom skill is required by the server.

If Claude Code runs in WSL, a container or a remote development environment, install Python/dependencies and register paths in that environment. A Windows `.exe` path or a Mac loopback URL is not automatically a valid remote setup.

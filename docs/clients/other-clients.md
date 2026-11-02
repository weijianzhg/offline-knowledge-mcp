# Other MCP clients

This server has no agent-specific runtime dependency. It uses the official Python SDK, five read-only tools, one resource and one prompt. Hosts need not support resources or prompts to use the tools. The connection format still depends on each host.

## stdio

After [installation](../setup.md), configure the equivalent of this common JSON format (merge into the host's config, replacing all placeholder paths):

```json
{
  "mcpServers": {
    "offline-knowledge": {
      "command": "/absolute/path/offline-knowledge-mcp/.venv/bin/python",
      "args": ["-m", "knowledge_mcp.server", "--transport", "stdio", "--db", "/absolute/path/offline-knowledge-mcp/data/knowledge.sqlite3"]
    }
  }
}
```

For Windows, the command is `C:\\path\\offline-knowledge-mcp\\.venv\\Scripts\\python.exe` and the database is `C:\\path\\offline-knowledge-mcp\\data\\knowledge.sqlite3` in JSON. Backslashes must be doubled in JSON. Paths containing spaces remain a single command/argument string; do not embed shell quotation marks in the JSON strings. Use absolute paths, not `~` or shell variables, unless your host explicitly expands them.

The editable package installation makes `-m knowledge_mcp.server` independent of the host working directory. The host owns process lifetime. stdout is reserved for MCP messages; logs go to stderr.

## Streamable HTTP

Start the HTTP server separately and supply `http://127.0.0.1:8766/mcp` in the host's Streamable HTTP connection UI. Some clients require `type: http`, others use `url` in a different wrapper. Consult that client's configuration schema; the JSON above describes stdio only. This project does not expose legacy SSE or an OpenAPI endpoint directly.

Loopback refers to the machine/environment running the client backend. Remote/cloud clients cannot reach a laptop by that URL. For Docker/remote access, see the [Open WebUI guide](open-webui.md).

Use the [grounding guidance](../agent-instructions.md) in the host's system instructions if it does not consume MCP server instructions. First confirm tool discovery and a call to `list_sources`, then search/read real evidence. MCP connectivity alone cannot guarantee the model selects tools correctly.

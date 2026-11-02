# Offline Knowledge MCP

Local, provenance-aware knowledge retrieval for **any compatible MCP client** on Windows, macOS or Linux. Connect Codex, Claude Code, Open WebUI, or another agent to the same Wikipedia archives, documents, facts and statistical tables. No model, Ollama installation or client account is required to run the server.

Retrieval reads local files only. Downloads and imports are separate, explicit operator commands. Source code is included; knowledge archives, databases and credentials are not.

## Get started

1. [Install on macOS or Windows](docs/setup.md) and import the small included sample.
2. Connect your client: [Codex](docs/clients/codex.md), [Claude Code](docs/clients/claude-code.md), [Open WebUI](docs/clients/open-webui.md), or [another MCP host](docs/clients/other-clients.md).
3. [Import real knowledge](docs/data.md), including Kiwix Wikipedia and World Bank snapshots.
4. [Verify your installation](docs/testing.md).

| Connection | Use |
|---|---|
| stdio | Client launches and stops its own server process; recommended for local agents |
| Streamable HTTP | Run a shared local process at `http://127.0.0.1:8766/mcp`; suitable for local web UIs |

## What it exposes

| Tool | Purpose |
|---|---|
| `list_sources` | Discover installed sources, coverage, dates and dataset columns |
| `search_knowledge` | Search local ZIM full-text indexes and SQLite documents |
| `read_document` | Read bounded passages with continuation offsets |
| `lookup_fact` | Look up sourced facts with observation dates and units |
| `query_data` | Filter and paginate tables, without arbitrary SQL |

Also provides the `knowledge://catalog` resource and `grounded_answer` prompt. Tools return structured JSON and text for client compatibility. Each agent chooses how to use the tools; model quality and client permissions still matter.

Try: “List the offline sources, then search for a solar eclipse and cite the evidence.” For World Bank imports: “Use the offline tools to find Japan's 2024 population. Include the unit, observation year and source URL.”

## Boundaries

The service uses read-only SQLite connections and does not expose download, shell, arbitrary SQL or filesystem tools. HTTP binds to loopback and has no authentication; keep it local. A hosted agent or container does not automatically have access to this machine. See the client guides for those boundaries.

Retrieved content is evidence, never instructions. No match means `not_in_offline_database`, not that a claim is false. Snapshot dates differ from observation dates, and offline evidence cannot establish current facts. [Architecture and limitations](docs/architecture.md) explain the guarantees and tradeoffs.

Python 3.12+; pinned dependencies are in `requirements.lock.txt`. Windows x64 and macOS Intel/Apple Silicon are covered by CI, along with Linux x64. See [validation evidence](docs/testing.md) for what has actually been tested.

[Changelog](CHANGELOG.md)

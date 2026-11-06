# Install on macOS and Windows

Use CPython 3.12 or newer with SQLite FTS5. Python 3.12 is the reference version in CI. No Docker, LLM, API key or UI is needed. Installation needs internet access; normal retrieval does not.

The [libzim wheels](https://python-libzim.readthedocs.io/en/latest/) support macOS Intel/Apple Silicon, Windows x64 and common Linux architectures. On Windows ARM, use an x64 Python under emulation; a native ARM Windows libzim wheel is not claimed here.

## macOS (also Linux)

From a terminal, with Git and Python 3.12+ installed:

```sh
git clone https://github.com/weijianzhg/offline-knowledge-mcp.git
cd offline-knowledge-mcp
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m knowledge_mcp.ingest init
.venv/bin/python -m knowledge_mcp.verify
```

## Windows (PowerShell)

Use an x64 Python. These commands call the venv interpreter directly, so activating a PowerShell script is unnecessary:

```powershell
git clone https://github.com/weijianzhg/offline-knowledge-mcp.git
Set-Location offline-knowledge-mcp
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m knowledge_mcp.ingest init
.\.venv\Scripts\python.exe -m knowledge_mcp.verify
```

The software is now installed with an empty database. This verification checks tool discovery, not content. Next, use the [unified collection installer](../README.md#install-knowledge-collections) to install all collections or a selection. The optional `examples/` directory contains synthetic onboarding data; use the [custom import commands](data.md#advanced-imports) to load it. Keep synthetic and real evidence separate when appropriate.

## Database location and launch

The editable installation defaults to `data/knowledge.sqlite3` inside this checkout. Keep the checkout and its `.venv` together; recreate the venv after moving them. For an external database, pass `--db` to **every** import, server and verification command. Use absolute paths in client configurations. For example:

```sh
.venv/bin/python -m knowledge_mcp.ingest --db "$HOME/Knowledge/knowledge.sqlite3" init
.venv/bin/python -m knowledge_mcp.server --db "$HOME/Knowledge/knowledge.sqlite3" --transport streamable-http
```

On Windows:

```powershell
.\.venv\Scripts\python.exe -m knowledge_mcp.ingest --db "$HOME\Knowledge\knowledge.sqlite3" init
.\.venv\Scripts\python.exe -m knowledge_mcp.server --db "$HOME\Knowledge\knowledge.sqlite3" --transport streamable-http
```

HTTP stays in the foreground; leave that terminal open and stop it with Ctrl+C. A stdio client manages its own process and needs no separate server. `--stdio` remains an alias for `--transport stdio`; the historical default remains Streamable HTTP. Set `--port 8767` if 8766 is occupied, and update the client URL.

Windows users can optionally use `Start-KnowledgeMCP.ps1` and `Stop-KnowledgeMCP.ps1` for the existing background HTTP launcher with the default database. Those scripts use Windows process APIs and are not the macOS launch path. They write logs under `logs/`. No startup service or automatic download schedule is installed.

## Troubleshooting

- Python is too old: choose a 3.12+ interpreter explicitly when creating `.venv`.
- `No module named knowledge_mcp`: use the venv interpreter and complete the editable install. Do not rely on a client's working directory.
- `no such module: fts5`: use a Python distribution with SQLite FTS5, such as the official CPython installers.
- Missing database: initialize the same absolute `--db` used by the client; a clone contains no database.
- Empty catalog: import sample or real sources. Initialization alone installs no knowledge.
- ZIM cannot open after moving machines: re-register the local archive; its stored path is machine-specific.
- On Windows, native libzim/Xapian has limitations reopening non-ASCII archive paths. The server uses an ASCII Windows short-path alias where available. If short names are disabled, move the archive to an ASCII-only path such as `C:\Knowledge\wikipedia.zim` and re-register it. SQLite databases and imported documents do not need this workaround.
- GUI cannot find Python: set the absolute `.venv/bin/python` or `.venv\Scripts\python.exe` path in the client.

## Short commands for Windows

For everyday background operation, install **knowledge-start** and **knowledge-stop** using the [Windows command instructions](../README.md#short-windows-commands). These use the default database and port. For an external database or a custom port, use the explicit server commands above.

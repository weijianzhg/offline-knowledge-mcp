# Offline Knowledge MCP

A working local knowledge service for Open WebUI, Ollama, and other MCP hosts. Retrieval reads local files only. Downloading data is an explicit, separate operation.

## Use it

The server listens on `http://127.0.0.1:8766/mcp`. In Open WebUI, refresh the model list and select **Offline Knowledge (Qwen3.8)**. The preset enables the knowledge tools and asks the model to ground factual answers in retrieved evidence.

Try:

- “Using the offline data, what was Japan's population in 2024? Cite the source and date.”
- “Search the offline Wikipedia collection and explain what causes a solar eclipse.”
- “Which sources and years are available in this offline collection?”

Start or stop the service from this folder:

```powershell
.\Start-KnowledgeMCP.ps1
.\Stop-KnowledgeMCP.ps1
```

It is running after initial setup. Start it again after reboot; no automatic startup or scheduled downloads have been installed. The Open WebUI preset needs this process running. Closing a chat does not stop it. Retrieval does not require a model to be resident in memory.

## Installed collection

| Collection | Coverage | Date |
|---|---|---|
| Kiwix Wikipedia 100 | 5,056 article entries in the publisher's “Top one hundred Wikipedia articles” collection; about 318 MiB | Archive built 2026-08-20 |
| World Bank WDI | Population and GDP in current US dollars; GBR, USA, JPN, CHN, IND, DEU, FRA, CAN, AUS, WLD; 2000–2025; 520 rows including missing observations | Downloaded 2026-11-01; publisher update 2026-10-08 |

This is a starter collection, not full English Wikipedia. The archive's label does not mean it contains precisely 100 entries. Its article count is read from the archive. The ZIM's publisher SHA-256 and internal checksum were verified before registration. The publisher checksum is recorded in `data/raw/wikipedia.meta4`.

World Bank observation years are preserved separately from download and publisher update dates. Null observations stay null in `query_data` and are omitted from `lookup_fact`. GDP is nominal GDP in current US dollars, not real GDP or purchasing-power-adjusted GDP. Population is country/aggregate level, not city or metropolitan population. Indicator definitions and upstream organizations are stored with each fact.

## Protocol and tools

MCP protocol revisions use dates. This implementation uses the official Python **SDK 2.3.0** and was tested over Streamable HTTP using protocol **2026-07-28**. “MCP 2.0” is not the protocol revision identifier. Protocol handling and legacy negotiation come from the official SDK; this project implements the tools, resources, and prompts it needs, not every optional MCP feature.

| Tool | Purpose |
|---|---|
| `list_sources` | Discover coverage, snapshots, datasets and columns |
| `search_knowledge` | Keyword search of local ZIM indexes and SQLite FTS5 documents |
| `read_document` | Read bounded article passages, with continuation offsets |
| `lookup_fact` | Exact subject/predicate/year lookup, with units and provenance |
| `query_data` | Filter and paginate a local table using equality filters |

Also exposes the `knowledge://catalog` resource and `grounded_answer` prompt. Tool responses contain structured JSON plus a text representation for host compatibility.

Examples of arguments:

```json
{"subject":"JPN","predicate":"population","observation_date":"2024"}
```

```json
{"dataset_id":"world_bank","filters":{"country_code":"GBR","indicator":"NY.GDP.MKTP.CD","year":2024}}
```

`lookup_fact` uses ISO3 subject codes for World Bank data. `query_data` filters compare exact values and types. Imported generic CSV values remain strings; World Bank `year` is an integer. Arbitrary SQL and filesystem paths are not exposed to the model.

No-match responses say `not_in_offline_database`; they do not assert that a claim is false. `max_age_days` flags old search results rather than discarding evidence. Source age measures snapshot age, not the age or accuracy of every claim. An offline snapshot cannot prove information is current. Article-level revision timestamps are not extracted in this version.

## Architecture

```text
Open WebUI -> Ollama model (tool selection)
     |
     +-> Offline Knowledge MCP, 127.0.0.1:8766
            +-> libzim: on-disk Wikipedia archive and built-in full-text index
            +-> SQLite: documents/FTS5, sourced facts, typed statistical rows

Operator import command -> downloaded snapshot -> validation -> local database
```

The serving module does not import the downloader. SQLite connections used by tools are read-only, and tools do not accept shell commands, remote URLs to fetch, arbitrary file paths, or arbitrary SQL. HTML is extracted as text without executing scripts or fetching media. The service binds only to loopback; it is intended for this single-user machine and has no network authentication. Do not expose it on a LAN without adding appropriate authentication.

The model still needs to select the right tool and interpret evidence correctly. Grounding reduces unsupported answers; it does not guarantee correctness. The preset instructs it to cite sources, distinguish inference, and treat retrieved instructions as untrusted document content.

The service uses the installed x64 Python runtime under `AppData/Roaming/open-webui/python`, with separate dependencies in `.venv`. Windows ARM runs this retrieval backend through x64 compatibility. Ollama GPU inference is independent.

## Maintain the data

Refresh the selected World Bank series when online:

```powershell
.\.venv\Scripts\python.exe -m knowledge_mcp.ingest sync-world-bank
```

All responses are downloaded first, preserved under `data/raw/` with SHA-256 hashes, and imported in one database transaction. A download or import failure leaves the existing data intact. The default range ends in 2025; change `--last-year` when appropriate. Additional countries can be selected with `--countries 'GBR;USA;JPN'`. A sync replaces the existing World Bank selection, so include every country you want to keep.

To add a larger English Wikipedia ZIM, download an archive with a full-text index from Kiwix, verify its publisher checksum, then register the local file:

```powershell
.\.venv\Scripts\python.exe -m knowledge_mcp.ingest register-zim 'D:\Knowledge\wikipedia_en_all_nopic_DATE.zim' --source-id wikipedia_en_full --sha256 PUBLISHER_SHA256
```

The filename and hash above are placeholders. Use the current catalog's actual filename and checksum. Full text-only English Wikipedia is much larger than the installed starter collection. Registering a ZIM does not unpack or duplicate its built-in index. Use the same source ID to replace a source; retain the old archive if you want rollback. Long-lived server handles may keep an old archive open until restart on Windows.

Other factual subsets can be imported as JSONL. Each line must have `id`, `subject`, `predicate`, `value`, `citation_url`; optional fields are `unit`, `observation_date`, and `qualifiers`. A source manifest must include `id`, `name`, `source_url`, `license`, and `scope`; include `snapshot_date` when known.

```powershell
.\.venv\Scripts\python.exe -m knowledge_mcp.ingest facts '.\my-facts.jsonl' --source '.\my-source.json'
.\.venv\Scripts\python.exe -m knowledge_mcp.ingest csv '.\my-data.csv' --source '.\my-source.json' --dataset-id my_data
```

Document JSONL uses `id`, `title`, `text`, and `citation_url`:

```powershell
.\.venv\Scripts\python.exe -m knowledge_mcp.ingest documents '.\my-documents.jsonl' --source '.\my-source.json'
```

JSONL imports upsert IDs; omitted old records remain. CSV imports replace that dataset. For an immutable new snapshot, use a new source ID. Full Wikidata dumps, PubMed, OpenAlex, vector search, automatic synchronization and SQL aggregation are not implemented or installed. The fact/CSV import interfaces provide a route for curated subsets.

## Connect another host

Use the Streamable HTTP URL `http://127.0.0.1:8766/mcp`. For a host that launches stdio servers:

```json
{
  "mcpServers": {
    "offline-knowledge": {
      "command": "C:\\Users\\weiji\\LocalLLM\\knowledge-mcp\\.venv\\Scripts\\python.exe",
      "args": ["-m", "knowledge_mcp.server", "--stdio"],
      "cwd": "C:\\Users\\weiji\\LocalLLM\\knowledge-mcp"
    }
  }
}
```

Host configuration formats vary. Open WebUI uses its Admin → Integrations → External Tool Servers screen and connection type MCP (Streamable HTTP). `Connect-OpenWebUI.ps1` can re-register this connection; it preserves other tool connections and an existing model preset. It uses this machine's DPAPI-protected local WebUI credential without printing the password or token.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe .\Verify-KnowledgeMCP.py
.\Test-OpenWebUIGrounding.ps1
```

Tests cover read-only access, query parameterization, stale/missing evidence, pagination, atomic import rollback, replacement imports, HTML extraction and the MCP contract. The installed-data verifier checks Wikipedia and World Bank retrieval with Python outbound socket connections blocked, then checks the real localhost HTTP MCP interface. This is a process-level test, not an OS firewall audit or a claim that all of Open WebUI's optional features are offline.

Evidence is saved in `logs/verification.json`, `logs/openwebui-connection.json`, and `logs/openwebui-grounding.json`. Runtime logs are `logs/server.out.log` and `logs/server.err.log`.

Dependencies are pinned in `requirements.lock.txt`; reinstall into a Python 3.12 x64 venv with `pip install -r requirements.lock.txt`. The database and archives are persistent in `data/` and are excluded from source control.

## Restore from the GitHub backup

The private repository backs up source code, scripts, documentation, pinned dependencies, and `source-manifest.json`. It excludes credentials, chats, runtime logs, the virtual environment, and downloaded knowledge data. For a byte-for-byte backup of the installed knowledge snapshot, copy `data/` separately to your backup storage while the importer is idle.

After cloning onto a Windows machine with Python 3.12 x64, run from the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m knowledge_mcp.ingest init
New-Item -ItemType Directory -Force -Path .\data\archives | Out-Null
$manifest = Get-Content .\source-manifest.json -Raw | ConvertFrom-Json
$archive = Join-Path '.\data\archives' $manifest.wikipedia.filename
Invoke-WebRequest -Uri $manifest.wikipedia.url -OutFile $archive
.\.venv\Scripts\python.exe -m knowledge_mcp.ingest register-zim $archive --source-id $manifest.wikipedia.source_id --sha256 $manifest.wikipedia.sha256
.\.venv\Scripts\python.exe -m knowledge_mcp.ingest sync-world-bank
.\Start-KnowledgeMCP.ps1
```

Archive registration rejects a checksum mismatch. If Kiwix no longer hosts this dated archive, use a newer archive and its matching publisher checksum. World Bank may revise historical values, so a fresh import can differ from the initial snapshot. Configure Open WebUI's MCP connection manually on another machine; the local DPAPI credential file is machine/account-specific and is not in GitHub. Adjust the absolute paths in the stdio example for a different checkout location.

## Sources

- MCP protocol versioning: https://modelcontextprotocol.io/docs/2026-07-28/learn/versioning
- Official Python SDK: https://py.sdk.modelcontextprotocol.io/
- Open WebUI MCP integration: https://docs.openwebui.com/features/extensibility/mcp/
- Kiwix archives: https://download.kiwix.org/zim/wikipedia/
- libzim Python API: https://python-libzim.readthedocs.io/en/latest/
- World Bank API: https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures
- Wikipedia licensing: https://en.wikipedia.org/wiki/Wikipedia:Copyrights
- World Bank dataset terms: https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets

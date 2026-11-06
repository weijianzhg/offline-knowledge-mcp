# Import and maintain knowledge

Run commands from the checkout after [setup](setup.md). In this guide, `python` means `.venv/bin/python` on macOS/Linux or `.\.venv\Scripts\python.exe` on Windows. Substitute that executable; no activation is needed. Add `--db ABSOLUTE_PATH` immediately before each ingest subcommand if using an external database.

## Included sample

`examples/` contains synthetic documents, facts and a CSV for onboarding. The values are invented and its example.org citations identify demonstration content. It is not an encyclopedia or statistical snapshot. Keep sample and real data in different databases if you do not want them mixed.

## Wikipedia (Kiwix ZIM)

`source-manifest.json` describes the original starter archive, about 318 MiB, dated 2026-08-20. It is a small English collection, not full Wikipedia. Availability may change. Verify publisher checksums, not just a completed download.

macOS/Linux:

```sh
mkdir -p data/archives data/raw
curl -fL --retry 2 https://download.kiwix.org/zim/wikipedia/wikipedia_en_100_2026-08.zim -o data/archives/wikipedia_en_100_2026-08.zim
curl -fL https://download.kiwix.org/zim/wikipedia/wikipedia_en_100_2026-08.zim.meta4 -o data/raw/wikipedia.meta4
.venv/bin/python -m knowledge_mcp.ingest register-zim data/archives/wikipedia_en_100_2026-08.zim --source-id wikipedia_en_100 --sha256 2eb7fd115bfb8644a08a9482f01f52b507428b1b8a30129fead92f7b6715440b
```

Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force data/archives, data/raw | Out-Null
$manifest = Get-Content source-manifest.json -Raw | ConvertFrom-Json
$archive = Join-Path data/archives $manifest.wikipedia.filename
Invoke-WebRequest $manifest.wikipedia.url -OutFile $archive
Invoke-WebRequest $manifest.wikipedia.publisher_metadata_url -OutFile data/raw/wikipedia.meta4
.\.venv\Scripts\python.exe -m knowledge_mcp.ingest register-zim $archive --source-id $manifest.wikipedia.source_id --sha256 $manifest.wikipedia.sha256
```

Registration checks SHA-256 when supplied, the archive's internal checksum, English language and presence of a full-text index. Confirm the hash against the publisher's `.meta4` metadata. If the archive is unavailable, choose an indexed English archive from the [Kiwix catalog](https://download.kiwix.org/zim/wikipedia/) and use its matching publisher checksum. Do not reuse the old hash for another file.

For larger archives, replace the path/source ID/hash. Registration reads the built-in index without unpacking it; hashing may take time. The archive path is recorded as an absolute local path. Re-register it after moving a database to another machine. Restart running servers after replacing archives, especially on Windows. Use a different source ID to preserve multiple snapshots; use the same ID to replace one.

Wikipedia text has attribution and share-alike obligations; media licenses vary. See [Wikipedia's copyright guidance](https://en.wikipedia.org/wiki/Wikipedia:Copyrights). Downloaded data is excluded from Git.

## World Bank

```sh
python -m knowledge_mcp.ingest sync-world-bank
python -m knowledge_mcp.ingest sync-world-bank --countries 'GBR;USA;JPN' --first-year 2000 --last-year 2025
```

Use **one** of these commands for your desired scope. A sync replaces the existing World Bank selection; include all countries/years you want to retain. The defaults are in `source-manifest.json`: population and nominal GDP in current US dollars, selected countries/aggregates, 2000–2025. Adjust the end year explicitly when appropriate.

Downloads and definitions are saved under `raw/` beside the selected database, with SHA-256 hashes in source metadata. All responses are fetched before one import transaction. Download or import failures retain the previous World Bank records. Re-fetching can change historical observations because the publisher revises them. [World Bank API](https://datahelpdesk.worldbank.org/knowledgebase/articles/898581-api-basic-call-structures), [dataset terms](https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets).

`lookup_fact` uses ISO3 subjects such as `JPN`, predicates `population` / `gdp_current_usd`, and observation years such as `2024`. Table filters compare types exactly: World Bank `year` is an integer, while generic CSV values remain strings. Null observations remain null in tables and are omitted from fact lookups. Population is country/aggregate level, not city/metropolitan population; GDP is nominal, not real or PPP-adjusted. Definitions and upstream organizations accompany the facts.

## Your own data

Supply a source JSON containing `id`, `name`, `source_url`, `license`, `scope`, and optionally `snapshot_date` in `YYYY-MM-DD` format. See [the sample](../examples/source.json).

```sh
python -m knowledge_mcp.ingest documents my-documents.jsonl --source my-source.json
python -m knowledge_mcp.ingest facts my-facts.jsonl --source my-source.json
python -m knowledge_mcp.ingest csv my-data.csv --source my-source.json --dataset-id my_data
```

Document JSONL requires `id`, `title`, `text`, `citation_url`. Fact JSONL requires `id`, `subject`, `predicate`, `value`, `citation_url`; optional keys: `unit`, `observation_date`, `qualifiers`. UTF-8 and UTF-8 with BOM are accepted. CSV headers must be unique simple identifiers. See [examples](../examples/) for complete files.

JSONL imports upsert IDs; omitted records remain. CSV imports replace the dataset. For immutable snapshots, use new source IDs (and dataset IDs for CSV). Back up the database, associated archives and raw snapshots while importers are idle, using SQLite's backup tooling or stopping all processes before copying the database and any WAL files. Git is a source backup, not a knowledge-data backup.

## Offline repair, travel and literature collections

Install the three pinned English Kiwix archives (about **7.9 GB / 7.35 GiB** total):

```powershell
.\.venv\Scripts\python.exe -m knowledge_mcp.collections all
```

On macOS/Linux use `.venv/bin/python` instead. For an external database, add `--db /absolute/path/knowledge.sqlite3` before `all`. To install just one collection, replace `all` with `wikivoyage`, `ifixit`, or `gutenberg`.

| Source ID | Included snapshot | Archive date | Download |
|---|---|---|---|
| `wikivoyage_en` | English Wikivoyage, including pictures | 2026-09-13 | 1.07 GB |
| `ifixit_en` | English iFixit archive, including repair illustrations | 2025-12-21 | 3.57 GB |
| `gutenberg_en_literature` | Project Gutenberg, LCC PN: Literature (General) | 2026-03-06 | 3.25 GB |

Gutenberg is a **selected subject collection**, not the entire English library. Archives can contain redirects and navigation pages; catalog entry counts are not unique book or guide counts. A snapshot's date does not establish that every page was updated on that date. Travel listings can change; older literature is historical source material.

Downloads go into `archives/` beside the database. The installer checks the pinned publisher file size and SHA-256 from Kiwix's `.meta4` files, then verifies the ZIM internal checksum, English language and full-text index before registering it in SQLite. The built-in lexical indexes are reused directly; no embeddings, model training, database migration or new dependencies are needed. Existing Wikipedia and World Bank sources remain available. Registration is atomic **per collection**; if a later collection fails, earlier successful registrations remain. Re-running reuses verified archives. An interrupted download stays as `.part`; a complete valid staged file is reused, while an incomplete file is downloaded again. A corrupt complete file causes an explicit failure; move it aside before retrying.

Pinned filenames, sizes and hashes live in `knowledge_mcp/collections.py`. The source catalog records publisher links, licensing, snapshot dates and archive hashes. Downloads are excluded from Git. If a pinned archive disappears from Kiwix, deliberately update its filename, size and publisher hash together; do not substitute another archive under the old checksum.

Restart a running HTTP service after updating its code:

```powershell
knowledge-stop
knowledge-start
.\.venv\Scripts\python.exe -m knowledge_mcp.verify --url http://127.0.0.1:8766/mcp --extra-collections --output logs/extra-collections-http.json
.\.venv\Scripts\python.exe -m knowledge_mcp.verify --extra-collections --output logs/extra-collections-stdio.json
```

The first probe checks the shared server; the second launches a temporary stdio process. Both require real search matches, correct publisher citations, matching text/hashes and pagination. Local evidence checks block outbound Python sockets. These checks verify MCP retrieval, not a guarantee that every LLM will select or interpret the tools correctly.

Ask your connected model:

- “Search `wikivoyage_en` for London and read the result. Explain the City of London and cite its snapshot.”
- “Search `ifixit_en` for battery adhesive strips, read the guide and identify the compatible devices and required tools.”
- “Search `gutenberg_en_literature` for poetry, read a matching book and cite its title and author.”

Use `source_id` to focus searches. Unfiltered results interleave independent backend ranks so the first archive cannot fill every result slot; this is a simple fairness rule, not a global relevance score. Archive hits include `excerpt_offset`, which can be passed as `read_document.offset` to read near the match. `archive_entry` identifies the original page inside the ZIM.

The MCP tools return **text only**. Pictures and formatting remain in the ZIM and can be viewed offline using a [Kiwix reader](https://get.kiwix.org/); the publisher citation links themselves require internet. Read illustrated repair procedures in the original archive when the pictures matter. A Kiwix reader is separate from this MCP installation.

Publisher terms: [Wikivoyage CC BY-SA](https://en.wikivoyage.org/wiki/Wikivoyage:Copyleft), [iFixit CC BY-NC-SA 3.0](https://www.ifixit.com/Info/Licensing), and [Project Gutenberg's per-book and jurisdiction-dependent terms](https://www.gutenberg.org/policy/license.html). Original attribution and notices remain in the archives; this repository does not redistribute their contents.
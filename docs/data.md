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

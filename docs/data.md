# Install and maintain knowledge

Complete [software setup](setup.md) first. Here `python` means the environment's `.venv/bin/python` on macOS/Linux or `.\.venv\Scripts\python.exe` on Windows; activation is unnecessary.

## One installer for every collection

```sh
python -m knowledge_mcp.collections --list
python -m knowledge_mcp.collections all
python -m knowledge_mcp.collections wikipedia world-bank
python -m knowledge_mcp.collections ifixit wikivoyage gutenberg
```

Choose `all` or one or more collection names. Duplicate names are installed once. Invalid names, an empty selection, or combining `all` with individual names fail before any download. `--list` only displays the catalog. Add `--db ABSOLUTE_PATH` to use another database; archives and raw API snapshots are kept beside that database.

| Name | Source ID | Coverage | Pinned archive date |
|---|---|---|---|
| `wikipedia` | `wikipedia_en_100` | English starter collection, not full Wikipedia | 2026-08-20 |
| `world-bank` | `world_bank` | Population/GDP; GBR, USA, JPN, CHN, IND, DEU, FRA, CAN, AUS, WLD; 2000–2025 | Download date recorded on installation |
| `wikivoyage` | `wikivoyage_en` | English travel guide, including pictures | 2026-09-13 |
| `ifixit` | `ifixit_en` | English repair archive, including illustrations | 2025-12-21 |
| `gutenberg` | `gutenberg_en_literature` | English general literature, LCC PN; not the entire library | 2026-03-06 |

The four archives total 8,223,768,269 bytes (about 8.22 GB / 7.66 GiB); the World Bank snapshot is small. Archive entry counts include redirects and navigation pages and are not unique book/guide counts. Snapshot dates are not individual article revision dates. Travel listings may change; older literature is historical material.

## Download, indexing and reuse

`knowledge_mcp/collection_manifest.json` is the single catalog for names, scope, pinned archive URLs/sizes/publisher SHA-256 hashes and World Bank defaults. It ships with the Python package. It replaces the original root `source-manifest.json`; callers that used that file should use the installer or packaged catalog. Both data types use the same bounded downloader; source-specific adapters handle archive registration or structured statistical import.

- **Archives:** files are saved under `archives/`. The downloader verifies pinned size and publisher SHA-256 from Kiwix's `.meta4` metadata before accepting a file. Registration also checks internal ZIM integrity, language and a full-text index. Existing valid archives are reused and revalidated without network access. Lexical indexes remain inside the ZIM; no duplicate vector index is built.
- **World Bank:** downloaded JSON responses are retained under `raw/` with SHA-256 hashes. Facts, definitions and table rows are imported in one database transaction. Existing installed data is reused by default, including a custom country/year selection. Use `python -m knowledge_mcp.collections world-bank --refresh` to replace it with a new download using the catalog defaults. Historical observations may be revised upstream. `--refresh` does not change pinned archive versions.
- **Selection:** only named collections are installed. Existing unselected collections are retained; selection is not an uninstall operation. Each collection is atomic independently. If a later collection fails, earlier successful installations remain available.
- **Recovery:** failed downloads remain as `.part` files. Complete, checksum-valid staged archives are reused; incomplete files are downloaded again. Corrupt complete files fail explicitly; move them aside before retrying. Existing accepted files and database records survive failed replacements. Re-run the same selection after resolving a failure.

Source catalogs record attribution, licensing, snapshot dates and archive hashes. Downloads, databases and credentials are excluded from Git. Updating software does not automatically refresh data. If a pinned archive disappears, deliberately update its URL, filename, size and publisher hash together.

## Verify and use

Start the HTTP service with `knowledge-start` on configured Windows installations, or follow [setup](setup.md). Restart after changing server code or replacing open archives.

```sh
# Discovery/catalog check for any installed selection
python -m knowledge_mcp.verify --url http://127.0.0.1:8766/mcp

# Require the original Wikipedia and World Bank collections
python -m knowledge_mcp.verify --url http://127.0.0.1:8766/mcp --installed-collection

# Require travel, repair and literature search/read/citations
python -m knowledge_mcp.verify --url http://127.0.0.1:8766/mcp --extra-collections
```

Omit `--url` to verify a temporary stdio server. Add `--output logs/verification.json` to save a report. Combine `--installed-collection --extra-collections` when all five sources are installed. Pass the same `--db` as the server. A requested collection check fails if that collection is absent; catalog-only verification does not prove retrieval quality. See [testing](testing.md) for the optional real-model diagnostic.

Ask your model to list sources first, then search/read with a specific source ID:

- “Search `wikivoyage_en` for London and read the result. Explain the City of London and cite its snapshot.”
- “Search `ifixit_en` for battery adhesive strips, read the guide and identify its author and required tools.”
- “Search `gutenberg_en_literature` for poetry, read a matching book and cite its title and author.”

Unfiltered results interleave independent backend ranks so one archive cannot fill every slot; this is a simple fairness rule, not a global relevance score. Archive hits return `excerpt_offset`; pass it as `read_document.offset` to read near the match. `archive_entry` identifies the original ZIM page. MCP returns **text only**. Open the downloaded ZIM in a [Kiwix reader](https://get.kiwix.org/) to view its original illustrations offline; publisher citation links require internet. A Kiwix reader is separate from this server.

## Advanced imports

The unified installer covers the supported collections. The existing low-level import commands remain available for custom sources and coverage.

For another indexed English archive, verify its publisher checksum and register it explicitly:

```sh
python -m knowledge_mcp.ingest register-zim /path/to/archive.zim --source-id my_travel --collection wikivoyage --sha256 PUBLISHER_SHA256
```

The path/hash above are placeholders. Supported archive adapters are `wikipedia` (default), `wikivoyage`, `ifixit` and `gutenberg`. Paths are stored as absolute local paths; re-register after moving an archive. A new source ID retains both snapshots; the same ID replaces its registration.

For a custom World Bank selection:

```sh
python -m knowledge_mcp.ingest sync-world-bank --countries 'GBR;USA;JPN' --first-year 2000 --last-year 2025
```

This explicitly replaces the existing selection; include all countries/years you want to retain. Add `--db ABSOLUTE_PATH` immediately before the ingest subcommand. `lookup_fact` uses ISO3 subjects such as `JPN`, predicates `population` / `gdp_current_usd`, and observation years such as `2024`. Null observations remain null in tables and are omitted from facts. GDP is nominal current US dollars, not real or PPP-adjusted GDP; population is country/aggregate level, not city population.

For your own documents, facts and tables, supply a source JSON with `id`, `name`, `source_url`, `license`, `scope`, and optionally `snapshot_date` (`YYYY-MM-DD`). See `examples/` for synthetic onboarding data; it is not real encyclopedic or statistical evidence.

```sh
python -m knowledge_mcp.ingest documents my-documents.jsonl --source my-source.json
python -m knowledge_mcp.ingest facts my-facts.jsonl --source my-source.json
python -m knowledge_mcp.ingest csv my-data.csv --source my-source.json --dataset-id my_data
```

Document JSONL needs `id`, `title`, `text`, `citation_url`. Facts need `id`, `subject`, `predicate`, `value`, `citation_url`; optional keys are `unit`, `observation_date`, `qualifiers`. UTF-8 with or without BOM is accepted. CSV headers must be unique simple identifiers. Generic CSV values remain strings; World Bank `year` is an integer. JSONL upserts IDs (omitted old records remain); CSV replaces its dataset.

Back up SQLite using its backup tooling, together with the associated archives and raw snapshots. Git backs up the software, not installed knowledge.

## Source terms

Original attribution/notices remain in the archives; this repository does not redistribute their contents. Sources: [Wikipedia](https://en.wikipedia.org/wiki/Wikipedia:Copyrights), [Wikivoyage CC BY-SA](https://en.wikivoyage.org/wiki/Wikivoyage:Copyleft), [iFixit CC BY-NC-SA 3.0](https://www.ifixit.com/Info/Licensing), [Gutenberg per-book/jurisdiction-dependent terms](https://www.gutenberg.org/policy/license.html), and [World Bank terms](https://www.worldbank.org/en/about/legal/terms-of-use-for-datasets).

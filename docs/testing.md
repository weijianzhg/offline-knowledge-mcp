# Testing and validation

Use the venv Python from [setup](setup.md). Tests need no LLM, credentials, large downloads or external data APIs. The ZIM test creates a tiny indexed archive locally.

macOS/Linux:

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m knowledge_mcp.verify --query eclipse --output logs/verification.json
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m knowledge_mcp.verify --query eclipse --output logs/verification.json
```

The second command assumes you imported the included sample (or other matching evidence). Without `--query`, the verifier checks discovery/catalog connectivity only, even if the database is empty. With `--query`, it also requires a local search match and reads that evidence over MCP. By default it launches a temporary real stdio process and then closes it.

To probe a separately running HTTP process, add `--url http://127.0.0.1:8766/mcp`. Pass the same absolute `--db` to the server and verifier. To check the original real-data starter collection, add `--installed-collection --query 'solar eclipse'`. That requires `wikipedia_en_100` plus World Bank Japan population for 2024; it does not assume a fixed population value. The verifier creates an output directory if requested and otherwise prints JSON without saving files. `Verify-KnowledgeMCP.py` remains a compatibility entry point for the same options.

The suite covers provenance, stale/missing evidence, read-only access, parameterized queries, pagination, import rollback/replacement, HTML extraction, native ZIM checksum/search/read, external database/raw-file paths, spaces and Unicode in paths, installed-package imports from a different working directory, stdio aliases, all five tools, resources/prompts, real HTTP and verifier failure cases. Local retrieval is exercised with outbound socket connections blocked in the Python process. This is not an OS firewall audit; the separate protocol probe is permitted to use localhost.

[Cross-platform CI](../.github/workflows/test.yml) installs pinned dependencies and the package, runs the suite, and executes the documented sample imports on Python 3.12 across Windows x64, macOS Apple Silicon, macOS Intel and Linux x64. It also parses the optional PowerShell helpers on Windows. CI does not download Wikipedia or run a model/UI. Live results are available in the repository's [Actions tab](https://github.com/weijianzhg/offline-knowledge-mcp/actions).

## macOS validation, 2026-11-02

On an Apple Silicon Mac with CPython 3.12, the sample setup and both real MCP transports were exercised. The original Kiwix archive was downloaded, its publisher SHA-256 and internal checksum verified, and World Bank data imported. Wikipedia search/read and the Japan 2024 population fact/table agreement passed with outbound sockets blocked during local retrieval, then through stdio and localhost HTTP. Reports are kept locally in ignored `logs/`.

Codex CLI registration syntax is checked using isolated configuration, without changing the user's installed MCP registrations. The separate client guides are based on official client documentation. Server transport validation does not imply every model's inference or every UI deployment has been tested. The optional Open WebUI API helpers require their own configured Windows/WebUI environment for an end-to-end chat test.

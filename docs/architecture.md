# Architecture and boundaries

```text
MCP client / chosen model
    | stdio (client-managed) or Streamable HTTP (local process)
    v
Offline Knowledge MCP
    +-- libzim: on-disk ZIM archive and full-text index
    +-- SQLite: documents/FTS5, sourced facts, typed statistical rows

Operator import command --> downloaded/local snapshot --> validation --> database
```

The server does not import the downloader. SQLite retrieval connections use `mode=ro` and `query_only`. Tools accept bounded queries and identifiers, not arbitrary SQL, shell commands, paths or URLs to fetch. Article HTML is extracted as text without executing scripts or fetching media. Imports are operator-only CLI actions.

The official [Python MCP SDK](https://py.sdk.modelcontextprotocol.io/) supplies protocol handling and transport negotiation. This project pins SDK 2.3.0; MCP protocol revisions are date identifiers, not the SDK version. The verifier reports the negotiated protocol. Tools provide structured content plus text, and read-only/idempotent annotations. Resources, prompts and server instructions are optional host features; tools alone suffice for retrieval.

HTTP binds to `127.0.0.1` with no authentication and a bounded request body. It is for trusted local clients on a single-user machine. A loopback bind is not per-user authorization. Do not publish a port or use a forwarding proxy on an untrusted network without authentication and access controls. stdio avoids a listening port and lets the client manage lifecycle.

Search uses SQLite FTS5 and ZIM keyword indexes, not vector embeddings. `max_age_days` flags old results; it does not discard them. The snapshot is the archive build/import date, not each article's revision time. Missing evidence cannot prove a claim false. Statistical observations preserve dates, units and definitions. The model still has to select tools, interpret evidence and cite sources correctly.

Full Wikidata dumps, PubMed/OpenAlex adapters, automatic synchronization, arbitrary SQL aggregation and client-specific inference are not implemented. No API key or cloud LLM dependency is part of retrieval. A UI or hosted model can still transmit retrieved evidence outside the machine; choose client/model settings appropriate for your data.

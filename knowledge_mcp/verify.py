"""Probe a local MCP server without a model, credentials or data downloads."""
import argparse
import asyncio
import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

from mcp import Client, StdioServerParameters

from .store import DEFAULT_DB, Store, utc_now

TOOLS = {"list_sources", "search_knowledge", "read_document", "lookup_fact", "query_data"}


async def verify(db_path, url=None, query=None, installed_collection=False, extra_collections=False, history_collections=False):
    store = Store(db_path)
    # Event loop creation happens before this patch (Windows uses a socket pair).
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Outbound network forbidden")):
        catalog = store.list_sources()
        expected = store.search(query) if query else None
        if expected is not None and (not expected["results"] or expected["source_errors"]):
            raise RuntimeError(f"Search failed: {expected}")
        if expected:
            document = store.read(expected["results"][0]["document_id"])
            if not document["text"]:
                raise RuntimeError("Search returned an empty document")
        if installed_collection:
            wiki = store.search("solar eclipse", source_id="wikipedia_en_100", limit=2)
            if not wiki["results"] or wiki["source_errors"]:
                raise RuntimeError(f"Wikipedia check failed: {wiki}")
            article = store.read(wiki["results"][0]["document_id"])
            if "Moon" not in article["text"]:
                raise RuntimeError("Wikipedia article is missing expected evidence")
            facts = store.lookup_fact("JPN", "population", "2024")["results"]
            rows = store.query_data("world_bank", {"country_code": "JPN", "indicator": "SP.POP.TOTL", "year": 2024})
            if not facts or not rows["rows"] or facts[0]["value"] != rows["rows"][0]["value"]:
                raise RuntimeError("World Bank fact/table mismatch")

    collection_checks = []
    checks = []
    if extra_collections:
        checks.extend([
            ("wikivoyage_en", "London", "https://en.wikivoyage.org/wiki/"),
            ("ifixit_en", "battery replacement", "https://www.ifixit.com/"),
            ("gutenberg_en_literature", "poetry", "https://www.gutenberg.org/ebooks/"),
        ])
    if history_collections:
        checks.extend(("gutenberg_en_history_" + code, query, "https://www.gutenberg.org/ebooks/")
                      for code, query in [("d", "Rome"), ("e", "Lincoln"), ("f", "Canada")])
    if checks:
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Outbound network forbidden")):
            for source_id, collection_query, prefix in checks:
                hits = store.search(collection_query, source_id=source_id)
                if hits["source_errors"] or not hits["results"]:
                    raise RuntimeError(f"Collection search failed: {source_id}")
                hit = hits["results"][0]
                doc = store.read(hit["document_id"], offset=hit["excerpt_offset"])
                if (not doc["text"].strip() or not doc["citation_url"].startswith(prefix)
                        or doc["source"]["id"] != source_id
                        or collection_query.split()[0].lower() not in doc["text"].lower()):
                    raise RuntimeError(f"Collection evidence/citation failed: {source_id}")
                collection_checks.append((source_id, collection_query, hit, doc))

    target = url or StdioServerParameters(
        command=sys.executable,
        args=["-m", "knowledge_mcp.server", "--db", str(db_path), "--transport", "stdio"],
    )
    async with Client(target, read_timeout_seconds=20) as client:
        names = {tool.name for tool in (await client.list_tools()).tools}
        if names != TOOLS:
            raise RuntimeError(f"Unexpected tools: {names}")
        result = await client.call_tool("list_sources")
        if result.is_error or result.structured_content != catalog:
            raise RuntimeError("MCP catalog differs from the selected local database")
        if query:
            result = await client.call_tool("search_knowledge", {"query": query})
            if (result.is_error or result.structured_content["status"] != "found"
                    or result.structured_content["source_errors"] or not result.structured_content["results"]):
                raise RuntimeError("MCP search failed")
            remote_id = result.structured_content["results"][0]["document_id"]
            if remote_id != expected["results"][0]["document_id"]:
                raise RuntimeError("MCP search differs from local evidence")
            result = await client.call_tool("read_document", {
                "document_id": remote_id})
            if (result.is_error or result.structured_content["status"] != "found"
                    or result.structured_content["sha256"] != document["sha256"]
                    or result.structured_content["text"] != document["text"]):
                raise RuntimeError("MCP document differs from local evidence")
        if installed_collection:
            result = await client.call_tool("lookup_fact", {
                "subject": "JPN", "predicate": "population", "observation_date": "2024"})
            if result.is_error or result.structured_content["results"][0]["value"] != facts[0]["value"]:
                raise RuntimeError("MCP World Bank check failed")
            result = await client.call_tool("read_document", {"document_id": article["document_id"]})
            if (result.is_error or result.structured_content["text"] != article["text"]
                    or result.structured_content["sha256"] != article["sha256"]):
                raise RuntimeError("MCP Wikipedia check failed")
        for source_id, collection_query, hit, doc in collection_checks:
            response = await client.call_tool("search_knowledge", {"query": collection_query, "source_id": source_id})
            if (response.is_error or response.structured_content["source_errors"]
                    or not response.structured_content["results"]
                    or response.structured_content["results"][0]["document_id"] != hit["document_id"]):
                raise RuntimeError(f"MCP collection search failed: {source_id}")
            response = await client.call_tool("read_document", {
                "document_id": hit["document_id"], "offset": hit["excerpt_offset"]})
            if response.is_error or response.structured_content != doc:
                raise RuntimeError(f"MCP collection evidence differs: {source_id}")
            if doc["next_offset"] is not None:
                expected_page = store.read(hit["document_id"], offset=doc["next_offset"])
                response = await client.call_tool("read_document", {
                    "document_id": hit["document_id"], "offset": doc["next_offset"]})
                if response.is_error or response.structured_content != expected_page:
                    raise RuntimeError(f"MCP collection pagination differs: {source_id}")
        return {"status": "PASS", "checked_at": utc_now(), "transport": "streamable-http" if url else "stdio",
                "protocol_version": client.protocol_version, "tools": sorted(names),
                "source_ids": [s["id"] for s in catalog["sources"]],
                "outbound_socket_blocked_during_local_retrieval": True,
                "search_checked": query, "installed_collection_checked": installed_collection,
                "extra_collections": [{"source_id": sid, "query": q, "title": doc["title"],
                                       "citation_url": doc["citation_url"], "sha256": doc["sha256"]}
                                      for sid, q, hit, doc in collection_checks]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--url", help="Probe an already running HTTP server instead of launching stdio")
    parser.add_argument("--query", help="Require a matching local document and verify it over MCP")
    parser.add_argument("--installed-collection", action="store_true", help="Also require the starter Wikipedia and World Bank sources")
    parser.add_argument("--extra-collections", action="store_true", help="Require Wikivoyage, iFixit and Gutenberg search/read/citations")
    parser.add_argument("--history-collections", action="store_true", help="Require all three Gutenberg history archives and verify search/read/citations")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    db_path = args.db.expanduser().resolve()
    if not db_path.is_file():
        parser.error("Database missing; initialize and import data first")
    report = asyncio.run(verify(db_path, args.url, args.query, args.installed_collection, args.extra_collections, args.history_collections))
    serialized = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()

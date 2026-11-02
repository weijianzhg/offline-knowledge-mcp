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


async def verify(db_path, url=None, query=None, installed_collection=False):
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
        return {"status": "PASS", "checked_at": utc_now(), "transport": "streamable-http" if url else "stdio",
                "protocol_version": client.protocol_version, "tools": sorted(names),
                "source_ids": [s["id"] for s in catalog["sources"]],
                "outbound_socket_blocked_during_local_retrieval": True,
                "search_checked": query, "installed_collection_checked": installed_collection}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--url", help="Probe an already running HTTP server instead of launching stdio")
    parser.add_argument("--query", help="Require a matching local document and verify it over MCP")
    parser.add_argument("--installed-collection", action="store_true", help="Also require the starter Wikipedia and World Bank sources")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    db_path = args.db.expanduser().resolve()
    if not db_path.is_file():
        parser.error("Database missing; initialize and import data first")
    report = asyncio.run(verify(db_path, args.url, args.query, args.installed_collection))
    serialized = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)


if __name__ == "__main__":
    main()

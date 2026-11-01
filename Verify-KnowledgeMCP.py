"""Validate installed data offline, then exercise the real HTTP MCP transport."""
import asyncio
import json
import socket
from unittest.mock import patch

from mcp import Client
from knowledge_mcp.store import ROOT, Store, utc_now


async def main():
    store = Store()
    with patch.object(socket.socket, "connect", side_effect=AssertionError("Outbound network forbidden")):
        search = store.search("solar eclipse", source_id="wikipedia_en_100", limit=2)
        assert search["results"] and not search["source_errors"], search
        doc = store.read(search["results"][0]["document_id"])
        assert "Moon" in doc["text"] and doc["citation_url"].startswith("https://en.wikipedia.org/")
        fact = store.lookup_fact("JPN", "population", "2024")["results"][0]
        rows = store.query_data("world_bank", {"country_code": "JPN", "indicator": "SP.POP.TOTL", "year": 2024})
        assert rows["rows"][0]["value"] == fact["value"]
        assert store.search("zzzxqnovalidevidencezz")["status"] == "not_in_offline_database"
    async with Client("http://127.0.0.1:8766/mcp") as client:
        tools = (await client.list_tools()).tools
        assert len(tools) == 5
        response = await client.call_tool("lookup_fact", {"subject": "JPN", "predicate": "population", "observation_date": "2024"})
        assert not response.is_error
        assert response.structured_content["results"][0]["value"] == fact["value"]
        report = {"checked_at": utc_now(), "status": "PASS", "protocol_version": client.protocol_version,
                  "tools": [t.name for t in tools], "outbound_socket_blocked_during_retrieval": True,
                  "wikipedia_article": doc["title"], "wikipedia_citation": doc["citation_url"],
                  "world_bank_japan_population_2024": fact["value"],
                  "catalog": store.list_sources()}
    (ROOT / "logs" / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "catalog"}, indent=2))


asyncio.run(main())

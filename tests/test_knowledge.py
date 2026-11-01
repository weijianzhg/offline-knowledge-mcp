import asyncio
import json
import socket
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from mcp import Client
from knowledge_mcp.ingest import import_jsonl
from knowledge_mcp.server import create_server
from knowledge_mcp.store import Store, connect, initialize, put_document, put_source, plain_text


class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "test.sqlite3"
        initialize(self.path)
        self.source = {"id": "fixture", "name": "Test evidence", "source_url": "https://example.org",
                       "license": "test", "scope": "Synthetic test fixture only", "snapshot_date": "2000-01-01"}
        with closing(connect(self.path, True)) as db, db:
            put_source(db, self.source)
            put_document(db, "fixture", {"id": "eclipse", "title": "Eclipse test", "text": "An eclipse is an alignment. " * 200,
                         "citation_url": "https://example.org/eclipse"})
            db.execute("INSERT INTO facts VALUES(?,?,?,?,?,?,?,?,?)",
                       ("f1", "fixture", "TEST", "population", "100", "people", "2024", '{"definition":"fixture"}', "https://example.org/stat"))
            db.execute("INSERT INTO datasets VALUES(?,?,?,?)", ("test", "fixture", "fixture", '["year","value"]'))
            for year in range(2020, 2025):
                db.execute("INSERT INTO dataset_rows VALUES(?,?,?)", ("test", year, json.dumps({"year": year, "value": year - 2000})))
        self.store = Store(self.path)

    def test_search_provenance_and_staleness(self):
        result = self.store.search("eclipse", max_age_days=30)
        self.assertEqual(result["status"], "found")
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["source"]["freshness"], "older_than_requested_limit")
        self.assertEqual(result["results"][0]["citation_url"], "https://example.org/eclipse")

    def test_missing_is_not_false(self):
        self.assertEqual(self.store.search("notarealword")["status"], "not_in_offline_database")
        self.assertEqual(self.store.lookup_fact("UNKNOWN")["status"], "not_in_offline_database")
        self.assertEqual(self.store.read("missing")["status"], "not_in_offline_database")

    def test_read_pagination(self):
        first = self.store.read("fixture:eclipse", max_chars=100)
        second = self.store.read("fixture:eclipse", offset=first["next_offset"], max_chars=100)
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertEqual(second["offset"], 100)
        self.assertEqual(first["text"] + second["text"], ("An eclipse is an alignment. " * 200)[:200])

    def test_parameterized_queries(self):
        self.assertEqual(self.store.lookup_fact("TEST' OR 1=1 --")["results"], [])
        self.assertEqual(self.store.search('" OR * --')["status"], "not_in_offline_database")
        with self.assertRaises(ValueError):
            self.store.query_data("test", {"year') OR 1=1 --": 2024})

    def test_fact_date_and_units(self):
        item = self.store.lookup_fact("test", "population", "2024")["results"][0]
        self.assertEqual((item["value"], item["unit"], item["observation_date"]), (100, "people", "2024"))

    def test_table_filters_and_pagination(self):
        self.assertEqual(self.store.query_data("test", {"year": 2024})["rows"], [{"year": 2024, "value": 24}])
        first = self.store.query_data("test", limit=2)
        second = self.store.query_data("test", limit=2, offset=first["next_offset"])
        self.assertEqual(second["rows"][0]["year"], 2022)

    def test_bad_limits(self):
        for limit in (0, -1, 1001):
            with self.assertRaises(ValueError):
                self.store.search("eclipse", limit=limit)

    def test_readonly_database(self):
        import sqlite3
        with closing(connect(self.path)) as db, self.assertRaises(sqlite3.OperationalError):
            db.execute("DELETE FROM sources")

    def test_import_rollback(self):
        source = Path(self.temp.name) / "source.json"
        source.write_text(json.dumps(self.source), encoding="utf-8")
        data = Path(self.temp.name) / "bad.jsonl"
        data.write_text(json.dumps({"id": "new", "title": "new", "text": "rollbackneedle", "citation_url": "https://example.org/new"}) + '\n{broken', encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            import_jsonl(self.path, data, source, "documents")
        self.assertEqual(self.store.search("rollbackneedle")["results"], [])

    def test_replace_does_not_duplicate_search(self):
        with closing(connect(self.path, True)) as db, db:
            put_document(db, "fixture", {"id": "eclipse", "title": "Updated", "text": "Newer replacement evidence", "citation_url": "https://example.org/new"})
        self.assertEqual(self.store.search("eclipse")["results"], [])
        self.assertEqual(len(self.store.search("replacement")["results"]), 1)

    def test_html_is_text(self):
        self.assertEqual(plain_text('<p>Useful &amp; true</p><script>fetch("https://evil")</script>'), "Useful & true")

    def test_mcp_contract_without_outbound_network(self):
        async def run():
            async with Client(create_server(self.path)) as client:
                names = {tool.name for tool in (await client.list_tools()).tools}
                self.assertEqual(names, {"list_sources", "search_knowledge", "read_document", "lookup_fact", "query_data"})
                result = await client.call_tool("lookup_fact", {"subject": "TEST", "predicate": "population"})
                self.assertFalse(result.is_error)
                self.assertEqual(result.structured_content["results"][0]["value"], 100)
                resource = await client.read_resource("knowledge://catalog")
                self.assertIn("fixture", resource.contents[0].text)
        # Windows creates a loopback socket pair while initializing its event loop.
        with asyncio.Runner() as runner:
            runner.get_loop()
            with patch.object(socket.socket, "connect", side_effect=AssertionError("Outbound network forbidden")):
                runner.run(run())


if __name__ == "__main__":
    unittest.main()

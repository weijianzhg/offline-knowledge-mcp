"""Real transport and filesystem tests, shared by Windows and macOS CI."""
import asyncio
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp import Client, StdioServerParameters

from knowledge_mcp.ingest import register_zim, sync_world_bank
from knowledge_mcp.store import Store
from knowledge_mcp.verify import TOOLS, verify
import test_knowledge

ROOT = Path(__file__).resolve().parents[1]


class PortabilityTests(unittest.TestCase):
    setUp = test_knowledge.KnowledgeTests.setUp

    def cli(self, module, *args):
        return subprocess.run([sys.executable, '-m', module, *map(str, args)],
                              cwd=self.temp.name, capture_output=True, text=True, timeout=30)

    def test_cli_with_unicode_spaces_and_different_working_directory(self):
        path = Path(self.temp.name) / 'Knowledge café #1' / '100%.sqlite3'
        result = self.cli('knowledge_mcp.ingest', '--db', path, 'init')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(Store(path).list_sources()['offline'])
        result = self.cli('knowledge_mcp.verify', '--db', path)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['source_ids'], [])

    def test_non_latin_database_path_with_windows_stdout_encoding(self):
        path = Path(self.temp.name) / '知識' / 'knowledge.sqlite3'
        result = subprocess.run([
            sys.executable, '-m', 'knowledge_mcp.ingest', '--db', str(path), 'init'],
            cwd=self.temp.name, env={**os.environ, 'PYTHONIOENCODING': 'cp1252'},
            capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['database'], str(path.resolve()))

    def test_stdio_tools_resources_and_prompts_from_another_directory(self):
        async def run(flag):
            target = StdioServerParameters(command=sys.executable, args=[
                '-m', 'knowledge_mcp.server', '--db', str(self.path), *flag], cwd=self.temp.name)
            async with Client(target) as client:
                tools = (await client.list_tools()).tools
                self.assertEqual({t.name for t in tools}, TOOLS)
                self.assertTrue(all(t.annotations.read_only_hint for t in tools))
                for name, arguments, field in [
                    ('list_sources', {}, 'sources'),
                    ('search_knowledge', {'query': 'eclipse'}, 'results'),
                    ('read_document', {'document_id': 'fixture:eclipse'}, 'text'),
                    ('lookup_fact', {'subject': 'TEST'}, 'results'),
                    ('query_data', {'dataset_id': 'test'}, 'rows'),
                ]:
                    result = await client.call_tool(name, arguments)
                    self.assertFalse(result.is_error, result)
                    self.assertTrue(result.structured_content[field])
                resource = await client.read_resource('knowledge://catalog')
                self.assertIn('fixture', resource.contents[0].text)
                prompt = await client.get_prompt('grounded_answer', {'question': 'What is an eclipse?'})
                self.assertIn('What is an eclipse?', prompt.messages[0].content.text)
                result = await client.call_tool('query_data', {'dataset_id': 'test', 'filters': {'bad_column': 1}})
                self.assertTrue(result.is_error)
        for flag in (['--transport', 'stdio'], ['--stdio']):
            with self.subTest(flag=flag):
                asyncio.run(run(flag))

    def test_real_http_transport_and_verifier_report(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        with (Path(self.temp.name) / 'server.err').open('w') as error_log:
            process = subprocess.Popen([sys.executable, '-m', 'knowledge_mcp.server', '--db', str(self.path),
                                        '--transport', 'streamable-http', '--port', str(port)],
                                       cwd=self.temp.name, stdout=subprocess.DEVNULL, stderr=error_log)
            try:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    self.assertIsNone(process.poll(), 'HTTP server exited early')
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                            break
                    except OSError:
                        time.sleep(0.1)
                else:
                    self.fail('HTTP startup timed out')
                output = Path(self.temp.name) / 'nested' / 'report.json'
                result = self.cli('knowledge_mcp.verify', '--db', self.path, '--url',
                                  f'http://127.0.0.1:{port}/mcp', '--query', 'eclipse', '--output', output)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(output.read_text(encoding='utf-8'))
                self.assertEqual(report['transport'], 'streamable-http')
                self.assertEqual(report['status'], 'PASS')
            finally:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                   capture_output=True, timeout=10)
                else:
                    process.terminate()
                process.wait(timeout=10)

    def test_verifier_requires_requested_evidence(self):
        with self.assertRaises(RuntimeError):
            asyncio.run(verify(self.path, query='notarealword'))
        with self.assertRaises(ValueError):
            asyncio.run(verify(self.path, installed_collection=True))

    def test_missing_database_and_invalid_port_fail_clearly(self):
        result = self.cli('knowledge_mcp.server', '--db', Path(self.temp.name) / 'missing.db', '--stdio')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Database missing', result.stderr)
        result = self.cli('knowledge_mcp.server', '--db', self.path, '--port', '0')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--port must be', result.stderr)

    def test_raw_downloads_follow_external_database(self):
        def fake_fetch(url, destination):
            destination.parent.mkdir(parents=True, exist_ok=True)
            if '/indicator/' in url and '/country/' not in url:
                result = [{}, [{'name': 'Test indicator', 'sourceNote': 'Definition', 'sourceOrganization': 'Fixture'}]]
            else:
                result = [{'pages': 1, 'lastupdated': '2026-01-01'}, [{
                    'countryiso3code': 'JPN', 'country': {'value': 'Japan', 'id': 'JP'},
                    'indicator': {'value': 'Test indicator'}, 'date': '2024', 'value': 100}]]
            destination.write_text(json.dumps(result), encoding='utf-8')
            return result
        with patch('knowledge_mcp.ingest.fetch_json', side_effect=fake_fetch):
            result = sync_world_bank(self.path, 'JPN', 2024, 2024)
        raw = self.path.parent / result['source']['raw_files']
        self.assertEqual(len(list(raw.glob('*.json'))), 4)
        self.assertEqual(len(result['source']['raw_sha256']), 4)
        self.assertEqual(self.store.lookup_fact('JPN', 'population')['results'][0]['value'], 100)

    def test_native_zim_checksum_search_and_read(self):
        from libzim.writer import Creator, Hint, Item, StringProvider

        class Article(Item):
            def get_path(self):
                return 'Solar_eclipse'

            def get_title(self):
                return 'Solar eclipse'

            def get_mimetype(self):
                return 'text/html'

            def get_contentprovider(self):
                return StringProvider('<html><body><p>The Moon causes a solar eclipse.</p></body></html>')

            def get_hints(self):
                return {Hint.FRONT_ARTICLE: True}

        archive = Path(self.temp.name) / 'sample café.zim'
        with Creator(str(archive)).config_indexing(True, 'eng') as creator:
            creator.add_item(Article())
            for name, value in {'Title': 'Synthetic ZIM', 'Description': 'Test only',
                                'Language': 'eng', 'Date': '2026-01-01'}.items():
                creator.add_metadata(name, value)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            register_zim(self.path, archive, 'test_zim', '0' * 64)
        register_zim(self.path, archive, 'test_zim', digest)
        try:
            result = self.store.search('eclipse', source_id='test_zim')
            self.assertFalse(result['source_errors'], result)
            doc = self.store.read(result['results'][0]['document_id'])
            self.assertIn('Moon', doc['text'])
            self.assertTrue(doc['citation_url'].endswith('/Solar_eclipse'))
        finally:
            self.store.archives.clear()


if __name__ == '__main__':
    unittest.main()

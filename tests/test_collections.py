"""Regression coverage for source provenance, download integrity and mixed search."""
import hashlib
import io
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledge_mcp.collections import install_collection
from knowledge_mcp.ingest import register_zim
from knowledge_mcp.store import Store
from knowledge_mcp.zim_sources import citation_url


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'knowledge.sqlite3'

    def make_archive(self, collection, path):
        from libzim.writer import Creator, Hint, Item, StringProvider
        class Article(Item):
            def get_path(self): return path
            def get_title(self): return 'Shared needle ' + collection
            def get_mimetype(self): return 'text/html'
            def get_contentprovider(self):
                return StringProvider('<html><body><p>' + 'Introduction. ' * 700 + 'sharedneedle evidence ' + collection + '</p></body></html>')
            def get_hints(self): return {Hint.FRONT_ARTICLE: True}
        archive = self.root / (collection + '.zim')
        with Creator(str(archive)).config_indexing(True, 'eng') as creator:
            creator.add_item(Article())
            class SecondArticle(Article):
                def get_path(self): return path + "2"
            creator.add_item(SecondArticle())
            for key, value in {'Title': collection, 'Description': 'Synthetic test archive', 'Language': 'eng', 'Date': '2026-01-01'}.items():
                creator.add_metadata(key, value)
        return archive

    def test_native_archives_citations_offsets_and_interleaving_offline(self):
        paths = {'wikipedia': 'Solar_eclipse', 'wikivoyage': 'London/City_of_London',
                 'ifixit': 'Guide/Battery+Replacement/1234', 'gutenberg': 'A Book.123'}
        for name, path in paths.items():
            archive = self.make_archive(name, path)
            register_zim(self.db, archive, name, hashlib.sha256(archive.read_bytes()).hexdigest(), name)
        store = Store(self.db)
        try:
            with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')):
                combined = store.search('sharedneedle', limit=4)
                self.assertFalse(combined['source_errors'])
                self.assertEqual({x['source']['id'] for x in combined['results']}, set(paths))
                for name, path in paths.items():
                    result = store.search('sharedneedle', source_id=name)['results'][0]
                    self.assertGreater(result['excerpt_offset'], 6000)
                    doc = store.read(result['document_id'], offset=result['excerpt_offset'])
                    self.assertIn('sharedneedle evidence ' + name, doc['text'])
                    self.assertEqual(doc['citation_url'], citation_url(name, doc['archive_entry']))
                    self.assertIn(doc['archive_entry'], (path, path + '2'))
                    self.assertNotIn('_rank', result)
        finally:
            store.archives.clear()

    def test_citation_mapping(self):
        self.assertEqual(citation_url('wikivoyage', 'A/New_York_City'), 'https://en.wikivoyage.org/wiki/New_York_City')
        self.assertEqual(citation_url('ifixit', 'Guide/A+B/123'), 'https://www.ifixit.com/Guide/A+B/123')
        self.assertEqual(citation_url('gutenberg', 'A book.456'), 'https://www.gutenberg.org/ebooks/456')
        with self.assertRaises(ValueError): citation_url('gutenberg', 'index.html')

    def spec(self, data):
        return {'kind': 'zim', 'url': 'https://example.org/fixture.zim', 'filename': 'fixture.zim', 'source_id': 'fixture', 'size': len(data),
                'sha256': hashlib.sha256(data).hexdigest()}

    def test_install_download_and_reuse(self):
        data = b'fake archive for downloader only'
        with patch('knowledge_mcp.collections.COLLECTIONS', {'wikivoyage': self.spec(data)}), \
             patch('knowledge_mcp.downloads.urlopen', return_value=io.BytesIO(data)) as fetch, \
             patch('knowledge_mcp.ingest.register_zim', return_value={'id': 'fixture'}) as register:
            install_collection('wikivoyage', self.db)
            install_collection('wikivoyage', self.db)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(register.call_count, 2)
            self.assertEqual((self.root / 'archives/fixture.zim').read_bytes(), data)

    def test_named_history_collection_reuses_gutenberg_adapter(self):
        from knowledge_mcp.catalog import COLLECTIONS
        archive = self.make_archive('history-world', 'History of Rome.123')
        spec = {**COLLECTIONS['history-world'], 'filename': archive.name,
                'size': archive.stat().st_size,
                'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
        with patch('knowledge_mcp.collections.COLLECTIONS', {'history-world': spec}), \
             patch('knowledge_mcp.downloads.urlopen', return_value=io.BytesIO(archive.read_bytes())):
            installed = install_collection('history-world', self.db)
        self.assertEqual(installed['source']['collection'], 'gutenberg')
        self.assertIn('/zim/gutenberg/', installed['source']['source_url'])
        store = Store(self.db)
        try:
            with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')):
                result = store.search('sharedneedle', source_id=spec['source_id'])
                self.assertFalse(result['source_errors'])
                self.assertTrue(result['results'])
                doc = store.read(result['results'][0]['document_id'])
                self.assertTrue(doc['citation_url'].startswith('https://www.gutenberg.org/ebooks/'))
                self.assertEqual(doc['source']['id'], spec['source_id'])
        finally:
            store.archives.clear()

    def test_bad_download_never_registers(self):
        for data in [b'bad', b'wrong!', b'too long for expected']:
            with self.subTest(data=data), \
                 patch('knowledge_mcp.collections.COLLECTIONS', {'wikivoyage': self.spec(b'valid!')}), \
                 patch('knowledge_mcp.downloads.urlopen', return_value=io.BytesIO(data)), \
                 patch('knowledge_mcp.ingest.register_zim') as register:
                partial = self.root / 'archives/fixture.zim.part'
                partial.unlink(missing_ok=True)
                with self.assertRaises(ValueError): install_collection('wikivoyage', self.db)
                register.assert_not_called()
                self.assertFalse((self.root / 'archives/fixture.zim').exists())

    def test_failed_refresh_preserves_registered_archive(self):
        archive = self.make_archive('wikivoyage', 'London')
        register_zim(self.db, archive, 'travel', collection='wikivoyage')
        before = Store(self.db).list_sources()
        with self.assertRaises(ValueError):
            register_zim(self.db, archive, 'travel', '0' * 64, 'wikivoyage')
        self.assertEqual(Store(self.db).list_sources(), before)

    def test_invalid_existing_download_is_not_overwritten(self):
        target = self.root / 'archives/fixture.zim'
        target.parent.mkdir()
        target.write_bytes(b'broken')
        with patch('knowledge_mcp.collections.COLLECTIONS', {'wikivoyage': self.spec(b'valid!')}), \
             patch('knowledge_mcp.downloads.urlopen') as fetch, \
             patch('knowledge_mcp.ingest.register_zim') as register:
            with self.assertRaises(ValueError): install_collection('wikivoyage', self.db)
            fetch.assert_not_called()
            register.assert_not_called()
            self.assertEqual(target.read_bytes(), b'broken')
class UnifiedInstallerTests(unittest.TestCase):
    def test_selection_validation_and_deduplication(self):
        from knowledge_mcp.catalog import COLLECTIONS, select_collections
        self.assertEqual(select_collections(['all']), list(COLLECTIONS))
        self.assertEqual(select_collections(['ifixit', 'wikipedia', 'ifixit']), ['ifixit', 'wikipedia'])
        for names in ([], ['all', 'ifixit'], ['not-a-collection']):
            with self.assertRaises(ValueError): select_collections(names)

    def test_cli_list_and_invalid_selection_do_not_install(self):
        from contextlib import redirect_stdout, redirect_stderr
        from knowledge_mcp.collections import main
        with patch('knowledge_mcp.collections.install_collection') as install:
            for arguments in (['--list'], ['invalid'], ['all', 'ifixit'], []):
                with patch('sys.argv', ['collections', *arguments]), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    if arguments == ['--list']: main()
                    else:
                        with self.assertRaises(SystemExit) as error: main()
                        self.assertEqual(error.exception.code, 2)
            install.assert_not_called()

    def test_cli_installs_only_selected_collections(self):
        from contextlib import redirect_stdout
        from knowledge_mcp.collections import main
        with patch('sys.argv', ['collections', 'ifixit', 'gutenberg', 'ifixit']), \
             patch('knowledge_mcp.collections.install_collection', return_value={}) as install, \
             redirect_stdout(io.StringIO()):
            main()
            self.assertEqual([call.args[0] for call in install.call_args_list], ['ifixit', 'gutenberg'])

    def test_world_bank_first_install_reuse_and_explicit_refresh(self):
        from knowledge_mcp.store import initialize, connect, put_source
        from contextlib import closing
        from knowledge_mcp.catalog import COLLECTIONS
        with tempfile.TemporaryDirectory() as temp:
            db_path = Path(temp) / 'knowledge.sqlite3'
            with patch('knowledge_mcp.ingest.sync_world_bank', return_value={'source': {'id': 'world_bank'}}) as sync:
                result = install_collection('world-bank', db_path)
                self.assertEqual(result['status'], 'installed')
                spec = COLLECTIONS['world-bank']
                sync.assert_called_once_with(db_path.resolve(), spec['countries'], spec['first_year'], spec['last_year'])
            initialize(db_path)
            with closing(connect(db_path, True)) as db, db:
                put_source(db, {'id': 'world_bank', 'name': 'Custom selection', 'source_url': 'https://data.worldbank.org/', 'license': 'test', 'scope': 'Custom countries'})
            with patch('knowledge_mcp.ingest.sync_world_bank', return_value={'source': {'id': 'world_bank'}}) as sync:
                # A source record without its data table is incomplete, so repair it.
                install_collection('world-bank', db_path)
                sync.assert_called_once()
            with closing(connect(db_path, True)) as db, db:
                db.execute("INSERT INTO datasets VALUES(?,?,?,?)", ('world_bank', 'world_bank', 'Custom selection', '["year"]'))
                db.execute("INSERT INTO dataset_rows VALUES(?,?,?)", ('world_bank', 1, '{"year": 2024}'))
            with patch('knowledge_mcp.ingest.sync_world_bank', return_value={'source': {'id': 'world_bank'}}) as sync:
                result = install_collection('world-bank', db_path)
                self.assertEqual(result['status'], 'reused')
                self.assertEqual(result['source']['scope'], 'Custom countries')
                sync.assert_not_called()
                install_collection('world-bank', db_path, refresh=True)
                sync.assert_called_once()

    def test_world_bank_uses_shared_downloader(self):
        from knowledge_mcp.ingest import fetch_json
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'raw.json'
            with patch('knowledge_mcp.downloads.urlopen', return_value=io.BytesIO(b'{"value": 12}')):
                self.assertEqual(fetch_json('https://example.org/data', target), {'value': 12})
            self.assertEqual(target.read_bytes(), b'{"value": 12}')

    def test_failed_unpinned_download_preserves_previous_file(self):
        from knowledge_mcp.downloads import download_file
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'raw.json'
            target.write_bytes(b'original')
            with patch('knowledge_mcp.downloads.urlopen', return_value=io.BytesIO(b'oversized')):
                with self.assertRaises(ValueError): download_file('https://example.org', target, 3)
            self.assertEqual(target.read_bytes(), b'original')
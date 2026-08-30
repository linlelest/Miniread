"""V2.1 数据层迁移测试：新表与 books 表新增列的幂等性验证"""
import os
import shutil
import sqlite3
import tempfile
import unittest

from config import Config
from database import init_db

# books 表 V2.1 新增列
_V21_BOOK_COLUMNS = ('group_id', 'kind', 'rss_url', 'sync_interval', 'last_synced')


class V21MigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix='miniread_v21_')
        cls._old = (Config.DATABASE_PATH, Config.UPLOAD_FOLDER, Config.CANONICAL_DIR, Config.DOWNLOAD_FOLDER)
        Config.DATABASE_PATH = os.path.join(cls._tmp, 'test.db')
        Config.UPLOAD_FOLDER = os.path.join(cls._tmp, 'uploads')
        Config.CANONICAL_DIR = os.path.join(cls._tmp, 'books')
        Config.DOWNLOAD_FOLDER = os.path.join(cls._tmp, 'downloads')
        init_db()

    @classmethod
    def tearDownClass(cls):
        Config.DATABASE_PATH, Config.UPLOAD_FOLDER, Config.CANONICAL_DIR, Config.DOWNLOAD_FOLDER = cls._old
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_01_init_db_idempotent(self):
        # setUpClass 已建库一次，这里重复调用两次，不抛异常即视为幂等
        init_db()
        init_db()

    def test_02_books_new_columns_exist(self):
        conn = sqlite3.connect(Config.DATABASE_PATH)
        try:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(books)")}
            for col in _V21_BOOK_COLUMNS:
                self.assertIn(col, cols)
        finally:
            conn.close()

    def test_03_new_tables_exist(self):
        conn = sqlite3.connect(Config.DATABASE_PATH)
        try:
            group_cols = {row[1] for row in conn.execute("PRAGMA table_info(book_groups)")}
            self.assertIn('user_id', group_cols)
            self.assertIn('name', group_cols)
            self.assertIn('sort_order', group_cols)

            rss_cols = {row[1] for row in conn.execute("PRAGMA table_info(rss_items)")}
            for col in ('book_id', 'guid', 'title', 'link', 'published', 'content'):
                self.assertIn(col, rss_cols)
        finally:
            conn.close()

    def test_04_rss_items_unique_constraint(self):
        conn = sqlite3.connect(Config.DATABASE_PATH)
        try:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'rss_items'"
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertIn('UNIQUE', row[0].upper())
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()

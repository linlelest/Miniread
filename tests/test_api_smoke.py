import io
import json
import os
import shutil
import tempfile
import unittest
import uuid

from config import Config


class ApiSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix='miniread_smoke_')
        cls._old = (Config.DATABASE_PATH, Config.UPLOAD_FOLDER, Config.CANONICAL_DIR, Config.DOWNLOAD_FOLDER)
        Config.DATABASE_PATH = os.path.join(cls._tmp, 'test.db')
        Config.UPLOAD_FOLDER = os.path.join(cls._tmp, 'uploads')
        Config.CANONICAL_DIR = os.path.join(cls._tmp, 'books')
        Config.DOWNLOAD_FOLDER = os.path.join(cls._tmp, 'downloads')
        from app import create_app
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()
        r = cls.client.get('/api/auth/check-admin')
        if not r.get_json()['data']['hasAdmin']:
            r = cls.client.post('/api/auth/admin-register', json={
                'username': 'smoke_admin', 'password': 'Smoke#12345'})
            assert r.status_code == 200, r.get_json()
        r = cls.client.post('/api/auth/login', json={
            'username': 'smoke_admin', 'password': 'Smoke#12345'})
        assert r.status_code == 200, r.get_json()

    @classmethod
    def tearDownClass(cls):
        Config.DATABASE_PATH, Config.UPLOAD_FOLDER, Config.CANONICAL_DIR, Config.DOWNLOAD_FOLDER = cls._old
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def _upload(self, text, options=None, name=None, set_default=None):
        name = name or ('%s.txt' % uuid.uuid4().hex[:6])
        data = {'file': (io.BytesIO(text.encode('utf-8')), name)}
        if options is not None:
            data['import_options'] = json.dumps(options)
        if set_default:
            data['set_default'] = '1'
        return self.client.post('/api/books/upload', data=data, content_type='multipart/form-data')

    def test_01_upload_txt_and_read(self):
        text = '第一章 起点\n\n段落一。\n\n第二章 转折\n\n段落二。\n'
        r = self._upload(text, {'encoding': 'auto'}, name='测试书.txt')
        self.assertEqual(r.status_code, 200, r.get_json())
        body = r.get_json()['data']
        book = body['book']
        self.assertEqual(body['summary']['sections'], 2)
        self.assertEqual(book['read_kind'], 'canonical')
        self.assertEqual(book['canonical_status'], 'ready')
        bid = book['id']

        r = self.client.get('/api/books')
        books = r.get_json()['data']
        self.assertTrue(any(b['id'] == bid for b in books))

        r = self.client.get('/api/books/%d/manifest' % bid)
        m = r.get_json()['data']
        self.assertEqual(len(m['sections']), 2)
        self.assertEqual(len(m['toc']), 2)

        r = self.client.get('/api/books/%d/section/0' % bid)
        self.assertEqual(r.status_code, 200)
        self.assertIn('段落一。', r.get_data(as_text=True))
        etag = r.headers.get('ETag')
        self.assertTrue(etag)
        r2 = self.client.get('/api/books/%d/section/0' % bid, headers={'If-None-Match': etag})
        self.assertEqual(r2.status_code, 304)

        r = self.client.get('/api/books/%d/section/9' % bid)
        self.assertEqual(r.status_code, 404)

    def test_02_settings_and_position(self):
        r = self._upload('第一章 甲\n\n甲文。\n\n第二章 乙\n\n乙文。\n')
        self.assertEqual(r.status_code, 200)
        bid = r.get_json()['data']['book']['id']

        r = self.client.put('/api/reading/%d/settings' % bid, json={
            'font_size': 20, 'word_spacing': 2.5, 'letter_spacing': 0.5,
            'theme_preset': 'parchment', 'page_mode': 'single', 'indent': 1,
        })
        self.assertEqual(r.status_code, 200)
        r = self.client.get('/api/reading/%d/settings' % bid)
        s = r.get_json()['data']
        self.assertEqual(s['font_size'], 20)
        self.assertEqual(s['word_spacing'], 2.5)
        self.assertEqual(s['theme_preset'], 'parchment')
        self.assertEqual(s['page_mode'], 'single')

        r = self.client.put('/api/reading/%d/position' % bid, json={
            'position': 0.42, 'chapter_title': '第二章 乙',
            'position_data': {'type': 'canonical', 'chapter': 1, 'offset': 128},
        })
        self.assertEqual(r.status_code, 200)
        r = self.client.get('/api/books/%d' % bid)
        d = r.get_json()['data']
        self.assertEqual(d['last_read_percent'], 42.0)
        self.assertEqual(d['position']['offset'], 128)

    def test_03_unsupported_format_rejected(self):
        r = self.client.post('/api/books/upload', data={
            'file': (io.BytesIO(b'BADLITDATA'), 'bad.lit'),
        }, content_type='multipart/form-data')
        self.assertEqual(r.status_code, 400)
        self.assertIn('不支持', r.get_json()['message'])

    def test_04_import_defaults(self):
        r = self.client.put('/api/import/defaults', json={'encoding': 'gb18030', 'strip_toc': True})
        self.assertEqual(r.status_code, 200)
        r = self.client.get('/api/import/defaults')
        d = r.get_json()['data']
        self.assertEqual(d.get('encoding'), 'gb18030')

    def test_05_duplicate_upload_rejected(self):
        text = '第一章 起点\n\n正文。\n'
        r1 = self._upload(text, name='dup1.txt')
        self.assertEqual(r1.status_code, 200)
        r2 = self._upload(text, name='dup2.txt')
        self.assertEqual(r2.status_code, 409)

    def test_06_custom_regex_upload(self):
        r = self._upload('卷一 上\n内容A\n卷一 下\n内容B\n',
                         {'chapter_regex': '^卷[一二]+ .+$'})
        self.assertEqual(r.status_code, 200, r.get_json())
        body = r.get_json()['data']
        self.assertEqual(body['summary']['sections'], 2)
        bid = body['book']['id']
        r = self.client.get('/api/books/%d/section/1' % bid)
        self.assertIn('内容B', r.get_data(as_text=True))
        self.client.delete('/api/books/%d' % bid)

    def test_07_delete_book(self):
        r = self._upload('第一章 a\n正文。\n', name='del.txt')
        self.assertEqual(r.status_code, 200)
        bid = r.get_json()['data']['book']['id']
        r = self.client.delete('/api/books/%d' % bid)
        self.assertEqual(r.status_code, 200)
        r = self.client.get('/api/books/%d/manifest' % bid)
        self.assertEqual(r.status_code, 404)

    def test_08_upload_pdf_native(self):
        r = self.client.post('/api/books/upload', data={
            'file': (io.BytesIO(b'%PDF-1.4\n%%EOF\n'), 'doc.pdf'),
        }, content_type='multipart/form-data')
        self.assertEqual(r.status_code, 200, r.get_json())
        body = r.get_json()['data']
        self.assertIsNone(body['summary']['sections'])
        self.assertEqual(body['book']['read_kind'], 'pdf')
        # V2.1 修复：PDF 不触发 LibreOffice 转换流程
        self.assertEqual(body['book']['convert_status'], 'none')
        bid = body['book']['id']
        r = self.client.get('/api/books/%d/manifest' % bid)
        m = r.get_json()['data']
        self.assertEqual(m['format'], 'pdf')
        self.assertIn('/file', m['file_url'])
        self.assertEqual(m.get('convert_status'), 'none')

    def test_09_bookmark_edit_delete_and_props(self):
        r = self._upload('第一章 a\n正文。\n', name='bm.txt')
        self.assertEqual(r.status_code, 200)
        bid = r.get_json()['data']['book']['id']

        r = self.client.post('/api/reading/%d/bookmarks' % bid, json={
            'chapter': '第一章 a', 'position_data': {'type': 'canonical', 'chapter': 0}, 'note': '旧名字'})
        self.assertEqual(r.status_code, 200)
        r = self.client.get('/api/reading/%d/bookmarks' % bid)
        marks = r.get_json()['data']
        self.assertEqual(len(marks), 1)
        mid = marks[0]['id']

        r = self.client.put('/api/reading/%d/bookmarks/%d' % (bid, mid), json={'note': '新名字'})
        self.assertEqual(r.status_code, 200)
        r = self.client.get('/api/reading/%d/bookmarks' % bid)
        self.assertEqual(r.get_json()['data'][0]['note'], '新名字')

        r = self.client.delete('/api/reading/%d/bookmarks/%d' % (bid, mid))
        self.assertEqual(r.status_code, 200)
        r = self.client.get('/api/reading/%d/bookmarks' % bid)
        self.assertEqual(r.get_json()['data'], [])

        r = self.client.put('/api/books/%d' % bid, data={
            'title': '改名后的书', 'author': '某作者',
            'placeholder': (io.BytesIO(b''), ''),
        }, content_type='multipart/form-data')
        self.assertEqual(r.status_code, 200)
        r = self.client.get('/api/books/%d' % bid)
        d = r.get_json()['data']
        self.assertEqual(d['title'], '改名后的书')
        self.assertEqual(d['author'], '某作者')


if __name__ == '__main__':
    unittest.main()

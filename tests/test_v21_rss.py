"""V2.1 RSS 订阅测试：解析净化、订阅 API 与越权校验"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from config import Config
from services.rss_sync import parse_feed

# 内嵌 RSS 2.0 样本：2 个条目，含 content:encoded、恶意 HTML 与 pubDate
RSS_SAMPLE = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>测试周刊</title>
    <description>用于测试的订阅源</description>
    <item>
      <title>第一篇文章</title>
      <link>http://example.com/post-1</link>
      <guid>post-1</guid>
      <pubDate>Mon, 01 Jan 2024 08:00:00 GMT</pubDate>
      <content:encoded><![CDATA[<p>正文一</p><script>alert('xss')</script><a href="javascript:evil()" onclick="steal()">链接</a>]]></content:encoded>
    </item>
    <item>
      <title>第二篇文章</title>
      <link>http://example.com/post-2</link>
      <guid>post-2</guid>
      <pubDate>Tue, 02 Jan 2024 09:30:00 GMT</pubDate>
      <description><![CDATA[<p>正文二</p><iframe src="http://evil.example"></iframe>]]></description>
    </item>
  </channel>
</rss>'''

# 内嵌 Atom 样本
ATOM_SAMPLE = '''<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom 测试源</title>
  <subtitle>Atom 副标题</subtitle>
  <entry>
    <id>urn:entry-1</id>
    <title>Atom 条目一</title>
    <link rel="alternate" type="text/html" href="http://example.com/atom-1"/>
    <published>2024-01-03T10:00:00Z</published>
    <updated>2024-01-04T11:00:00Z</updated>
    <content type="html">&lt;p&gt;Atom 正文&lt;/p&gt;</content>
  </entry>
</feed>'''

# 未闭合的坏 XML
BAD_XML = '<rss><channel><item><title>未闭合'.encode('utf-8')


class V21RssTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix='miniread_rss_')
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
                'username': 'rss_admin', 'password': 'Rss#12345'})
            assert r.status_code == 200, r.get_json()
        r = cls.client.post('/api/auth/login', json={
            'username': 'rss_admin', 'password': 'Rss#12345'})
        assert r.status_code == 200, r.get_json()
        # 第二个普通用户，用于越权校验
        cls.client2 = cls.app.test_client()
        r = cls.client2.post('/api/auth/register', json={
            'username': 'rss_other', 'password': 'Rss#12345'})
        assert r.status_code == 200, r.get_json()
        r = cls.client2.post('/api/auth/login', json={
            'username': 'rss_other', 'password': 'Rss#12345'})
        assert r.status_code == 200, r.get_json()

    @classmethod
    def tearDownClass(cls):
        Config.DATABASE_PATH, Config.UPLOAD_FOLDER, Config.CANONICAL_DIR, Config.DOWNLOAD_FOLDER = cls._old
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def _create_rss(self, name=None, interval=None):
        """以第一个用户身份创建订阅（patch 抓取函数，返回同一样本）"""
        payload = {'url': 'http://example.com/feed.xml'}
        if name is not None:
            payload['name'] = name
        if interval is not None:
            payload['interval'] = interval
        with mock.patch('services.rss_sync.fetch_feed', return_value=RSS_SAMPLE.encode('utf-8')):
            return self.client.post('/api/rss', json=payload)

    def test_01_parse_rss2_and_sanitize(self):
        feed = parse_feed(RSS_SAMPLE.encode('utf-8'))
        self.assertEqual(feed['title'], '测试周刊')
        self.assertEqual(len(feed['items']), 2)
        item = feed['items'][0]
        self.assertEqual(item['guid'], 'post-1')
        self.assertEqual(item['link'], 'http://example.com/post-1')
        self.assertEqual(item['published'], 1704096000.0)
        low = item['content'].lower()
        self.assertNotIn('<script', low)
        self.assertNotIn('onclick', low)
        self.assertNotIn('javascript:', low)
        self.assertIn('正文一', item['content'])
        self.assertNotIn('<iframe', feed['items'][1]['content'].lower())
        self.assertIn('正文二', feed['items'][1]['content'])

    def test_02_parse_atom(self):
        feed = parse_feed(ATOM_SAMPLE.encode('utf-8'))
        self.assertEqual(feed['title'], 'Atom 测试源')
        self.assertEqual(len(feed['items']), 1)
        item = feed['items'][0]
        self.assertEqual(item['guid'], 'urn:entry-1')
        self.assertEqual(item['link'], 'http://example.com/atom-1')
        self.assertEqual(item['published'], 1704276000.0)
        self.assertIn('Atom 正文', item['content'])

    def test_03_bad_xml_raises(self):
        with self.assertRaises(ValueError):
            parse_feed(BAD_XML)

    def test_04_api_create_items_and_resync(self):
        r = self._create_rss()
        self.assertEqual(r.status_code, 200, r.get_json())
        body = r.get_json()['data']
        self.assertTrue(body['book_id'])
        # 未传 name 时默认取 feed 标题
        self.assertEqual(body['title'], '测试周刊')
        self.assertEqual(body['items'], 2)
        bid = body['book_id']

        r = self.client.get('/api/rss/%d/items?page=1&size=1' % bid)
        self.assertEqual(r.status_code, 200, r.get_json())
        d = r.get_json()['data']
        self.assertEqual(d['total'], 2)
        self.assertEqual(d['page'], 1)
        self.assertEqual(d['size'], 1)
        # published 倒序：第二篇（更新时间更晚）在前
        self.assertEqual(d['items'][0]['guid'], 'post-2')

        r = self.client.get('/api/rss/%d/items?page=2&size=1' % bid)
        d = r.get_json()['data']
        self.assertEqual(d['items'][0]['guid'], 'post-1')

        # 重复 sync 同一样本：不产生重复条目
        with mock.patch('services.rss_sync.fetch_feed', return_value=RSS_SAMPLE.encode('utf-8')):
            r = self.client.post('/api/rss/%d/sync' % bid)
        self.assertEqual(r.status_code, 200, r.get_json())
        d = r.get_json()['data']
        self.assertEqual(d['added'], 0)
        self.assertIsNotNone(d['last_synced'])

    def test_05_api_update_subscription(self):
        r = self._create_rss(name='旧名字', interval=6)
        self.assertEqual(r.status_code, 200, r.get_json())
        bid = r.get_json()['data']['book_id']

        r = self.client.put('/api/rss/%d' % bid, json={'name': '新名字', 'interval': 12})
        self.assertEqual(r.status_code, 200, r.get_json())
        d = r.get_json()['data']
        self.assertEqual(d['title'], '新名字')
        self.assertEqual(d['sync_interval'], 12)

    def test_06_api_forbidden_access(self):
        r = self._create_rss(name='私有订阅')
        self.assertEqual(r.status_code, 200, r.get_json())
        bid = r.get_json()['data']['book_id']

        # 第二个用户访问第一个用户的订阅条目：404
        r = self.client2.get('/api/rss/%d/items' % bid)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.get_json()['message'], '订阅不存在')

    def test_07_api_invalid_url(self):
        with mock.patch('services.rss_sync.fetch_feed',
                        side_effect=ValueError('订阅源抓取失败')):
            r = self.client.post('/api/rss', json={'url': 'http://example.com/broken.xml'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('订阅解析失败', r.get_json()['message'])


if __name__ == '__main__':
    unittest.main()

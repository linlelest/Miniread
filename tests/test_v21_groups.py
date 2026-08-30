import io
import os
import shutil
import tempfile
import unittest
import uuid

from config import Config


class V21GroupsTest(unittest.TestCase):
    """V2.1 分组与批量操作 API 测试"""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix='miniread_v21_')
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
                'username': 'v21_admin', 'password': 'V21#12345'})
            assert r.status_code == 200, r.get_json()
        r = cls.client.post('/api/auth/login', json={
            'username': 'v21_admin', 'password': 'V21#12345'})
        assert r.status_code == 200, r.get_json()

    @classmethod
    def tearDownClass(cls):
        Config.DATABASE_PATH, Config.UPLOAD_FOLDER, Config.CANONICAL_DIR, Config.DOWNLOAD_FOLDER = cls._old
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def _upload(self, text, title=None):
        name = '%s.txt' % uuid.uuid4().hex[:6]
        data = {'file': (io.BytesIO(text.encode('utf-8')), name)}
        if title:
            data['title'] = title
        r = self.client.post('/api/books/upload', data=data, content_type='multipart/form-data')
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()['data']['book']

    def _create_group(self, name):
        r = self.client.post('/api/groups', json={'name': name})
        self.assertEqual(r.status_code, 200, r.get_json())
        return r.get_json()['data']

    def _other_client(self):
        # 注册并登录第二个用户（独立 client 持有各自的会话 cookie）
        other = self.app.test_client()
        r = other.post('/api/auth/register', json={
            'username': 'v21_second', 'password': 'Second#12345'})
        self.assertIn(r.status_code, (200, 409))
        r = other.post('/api/auth/login', json={
            'username': 'v21_second', 'password': 'Second#12345'})
        self.assertEqual(r.status_code, 200, r.get_json())
        return other

    def test_01_create_group_and_list_member_count(self):
        # 空名与纯空格名均拒绝
        r = self.client.post('/api/groups', json={'name': ''})
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/api/groups', json={'name': '   '})
        self.assertEqual(r.status_code, 400)
        grp = self._create_group('我的精选')
        self.assertTrue(grp['id'])
        self.assertEqual(grp['name'], '我的精选')
        self.assertEqual(grp['member_count'], 0)
        r = self.client.get('/api/groups')
        groups = r.get_json()['data']
        self.assertTrue(any(g['id'] == grp['id'] for g in groups))
        self.assertTrue(all('member_count' in g for g in groups))

    def test_02_batch_move_and_group_filter(self):
        b1 = self._upload('第一章 甲\n甲的内容。\n', title='分组书一')
        b2 = self._upload('第一章 乙\n乙的内容。\n', title='分组书二')
        grp = self._create_group('移动目标组')
        r = self.client.post('/api/books/batch-move', json={
            'ids': [b1['id'], b2['id']], 'group_id': grp['id']})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()['data']['moved'], 2)
        # ?group=<id> 只见组内这 2 本
        r = self.client.get('/api/books?group=%d' % grp['id'])
        books = r.get_json()['data']
        self.assertEqual(sorted(b['id'] for b in books), sorted([b1['id'], b2['id']]))
        # 详情透出 V2.1 字段
        r = self.client.get('/api/books/%d' % b1['id'])
        d = r.get_json()['data']
        self.assertEqual(d['group_id'], grp['id'])
        self.assertEqual(d['kind'], '')
        self.assertEqual(d['rss_url'], '')
        self.assertEqual(d['sync_interval'], 24)
        self.assertIsNone(d['last_synced'])
        # ?group=root 不含组内书
        r = self.client.get('/api/books?group=root')
        ids = [b['id'] for b in r.get_json()['data']]
        self.assertNotIn(b1['id'], ids)
        self.assertNotIn(b2['id'], ids)
        # 不带参数全部可见
        r = self.client.get('/api/books')
        ids = [b['id'] for b in r.get_json()['data']]
        self.assertIn(b1['id'], ids)
        self.assertIn(b2['id'], ids)
        # 移出分组：group_id 传 null
        r = self.client.post('/api/books/batch-move', json={'ids': [b2['id']], 'group_id': None})
        self.assertEqual(r.get_json()['data']['moved'], 1)
        r = self.client.get('/api/books?group=%d' % grp['id'])
        self.assertEqual([b['id'] for b in r.get_json()['data']], [b1['id']])
        # 移回分组，保持数据完整
        self.client.post('/api/books/batch-move', json={'ids': [b2['id']], 'group_id': grp['id']})

    def test_03_batch_move_validation_and_cross_user(self):
        book = self._upload('第一章 越权\n越权内容。\n', title='越权测试书')
        grp = self._create_group('校验组')
        # ids 非列表
        r = self.client.post('/api/books/batch-move', json={'ids': 'bad', 'group_id': grp['id']})
        self.assertEqual(r.status_code, 400)
        # 分组不存在
        r = self.client.post('/api/books/batch-move', json={
            'ids': [book['id']], 'group_id': 999999})
        self.assertEqual(r.status_code, 400)
        # 第二用户移动第一用户的书 → 被忽略 moved=0
        other = self._other_client()
        r = other.post('/api/groups', json={'name': '他人分组'})
        self.assertEqual(r.status_code, 200, r.get_json())
        other_group = r.get_json()['data']
        r = other.post('/api/books/batch-move', json={
            'ids': [book['id']], 'group_id': other_group['id']})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['data']['moved'], 0)
        # 归属未变
        r = self.client.get('/api/books/%d' % book['id'])
        self.assertIsNone(r.get_json()['data']['group_id'])
        # 他人分组对第一用户不可改
        r = self.client.put('/api/groups/%d' % other_group['id'], json={'name': '篡改'})
        self.assertEqual(r.status_code, 404)

    def test_04_batch_delete(self):
        b1 = self._upload('第一章 删一\n删除内容一。\n', title='待删书一')
        b2 = self._upload('第一章 删二\n删除内容二。\n', title='待删书二')
        # 第二用户删除他人的书 → deleted=0 且书仍在
        other = self._other_client()
        r = other.post('/api/books/batch-delete', json={'ids': [b1['id']]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['data']['deleted'], 0)
        r = self.client.get('/api/books/%d' % b1['id'])
        self.assertEqual(r.status_code, 200)
        # 批删自己的书（混入不存在的 id）
        r = self.client.post('/api/books/batch-delete', json={
            'ids': [b1['id'], b2['id'], 999999]})
        self.assertEqual(r.get_json()['data']['deleted'], 2)
        r = self.client.get('/api/books/%d' % b1['id'])
        self.assertEqual(r.status_code, 404)
        r = self.client.get('/api/books/%d' % b2['id'])
        self.assertEqual(r.status_code, 404)

    def test_05_query_filter(self):
        hit = self._upload('第一章 量子\n量子内容。\n', title='量子物理导论')
        self._upload('第一章 随笔\n随笔内容。\n', title='山河故人志')
        r = self.client.get('/api/books?query=量子')
        books = r.get_json()['data']
        self.assertTrue(books)
        self.assertTrue(all('量子' in b['title'] for b in books))
        self.assertIn(hit['id'], [b['id'] for b in books])
        # 无匹配 → 空列表
        r = self.client.get('/api/books?query=绝对不存在的关键词xyz')
        self.assertEqual(r.get_json()['data'], [])

    def test_06_rename_and_delete_group_nulls_books(self):
        b1 = self._upload('第一章 归组\n归组内容一。\n', title='组内书一')
        b2 = self._upload('第二章 归组\n归组内容二。\n', title='组内书二')
        grp = self._create_group('旧组名')
        r = self.client.post('/api/books/batch-move', json={
            'ids': [b1['id'], b2['id']], 'group_id': grp['id']})
        self.assertEqual(r.get_json()['data']['moved'], 2)
        # 空名改名拒绝
        r = self.client.put('/api/groups/%d' % grp['id'], json={'name': ' '})
        self.assertEqual(r.status_code, 400)
        # 正常改名
        r = self.client.put('/api/groups/%d' % grp['id'], json={'name': '新组名'})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()['data']['name'], '新组名')
        # member_count 跟随组内书数
        r = self.client.get('/api/groups')
        cnt = {g['id']: g['member_count'] for g in r.get_json()['data']}
        self.assertEqual(cnt[grp['id']], 2)
        # 删除分组后组内书回到未分组
        r = self.client.delete('/api/groups/%d' % grp['id'])
        self.assertEqual(r.status_code, 200)
        r = self.client.get('/api/books?group=root')
        ids = [b['id'] for b in r.get_json()['data']]
        self.assertIn(b1['id'], ids)
        self.assertIn(b2['id'], ids)
        r = self.client.get('/api/groups')
        self.assertNotIn(grp['id'], [g['id'] for g in r.get_json()['data']])
        # 重复删除 → 404
        r = self.client.delete('/api/groups/%d' % grp['id'])
        self.assertEqual(r.status_code, 404)


if __name__ == '__main__':
    unittest.main()

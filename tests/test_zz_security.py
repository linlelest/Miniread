"""
Miniread V2.1 安全测试套件
覆盖：设备数量限制、登录失败限速、越权访问、SQL 注入无效化、
管理员权限隔离、上传白名单、SSRF 防护、路径穿越。
"""
import io
import json
import os
import shutil
import tempfile
import unittest

from config import Config


class SecurityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix='miniread_sec_')
        cls._old = (Config.DATABASE_PATH, Config.UPLOAD_FOLDER, Config.CANONICAL_DIR, Config.DOWNLOAD_FOLDER)
        Config.DATABASE_PATH = os.path.join(cls._tmp, 'test.db')
        Config.UPLOAD_FOLDER = os.path.join(cls._tmp, 'uploads')
        Config.CANONICAL_DIR = os.path.join(cls._tmp, 'books')
        Config.DOWNLOAD_FOLDER = os.path.join(cls._tmp, 'downloads')
        from app import create_app
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.client = cls.app.test_client()

        # 管理员
        r = cls.client.post('/api/auth/admin-register', json={
            'username': 'sec_admin', 'password': 'Sec#12345'})
        assert r.status_code == 200, r.get_json()
        cls.admin_cookie = r.headers.get('Set-Cookie').split(';')[0]

    @classmethod
    def tearDownClass(cls):
        Config.DATABASE_PATH, Config.UPLOAD_FOLDER, Config.CANONICAL_DIR, Config.DOWNLOAD_FOLDER = cls._old
        shutil.rmtree(cls._tmp, ignore_errors=True)
        # 清空登录限速状态，避免影响其他测试模块
        from utils import helpers
        helpers._login_failures.clear()

    def _login(self, username, password):
        r = self.client.post('/api/auth/login', json={
            'username': username, 'password': password, 'remember': True})
        return r

    def _register_and_login(self, username):
        r = self.client.post('/api/auth/register', json={
            'username': username, 'password': 'Pass#12345', 'password2': 'Pass#12345'})
        self.assertEqual(r.status_code, 200, r.get_json())
        r = self.client.post('/api/auth/login', json={
            'username': username, 'password': 'Pass#12345'})
        self.assertEqual(r.status_code, 200)
        return r

    def _upload(self, text, name):
        r = self.client.post('/api/books/upload', data={
            'file': (io.BytesIO(text.encode('utf-8')), name),
        }, content_type='multipart/form-data')
        return r

    # ---------- 设备数量限制 ----------
    def test_01_device_limit_kicks_oldest_sessions(self):
        """同一账号最多 3 个有效会话，第 4 次登录随机踢出多余会话"""
        r = self.client.post('/api/auth/register', json={
            'username': 'dev_user', 'password': 'Dev#12345', 'password2': 'Dev#12345'})
        self.assertEqual(r.status_code, 200)

        tokens = []
        for i in range(5):
            r = self.client.post('/api/auth/login', json={
                'username': 'dev_user', 'password': 'Dev#12345'})
            self.assertEqual(r.status_code, 200)
            token = r.get_json()['data']['sessionId']
            tokens.append(token)

        # 数据库中有效会话数量守恒（不超过 3）
        import sqlite3
        conn = sqlite3.connect(Config.DATABASE_PATH)
        cnt = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE user_id = ? AND expires_at > strftime('%s','now')",
            (self._uid('dev_user'),),
        ).fetchone()[0]
        conn.close()
        self.assertLessEqual(cnt, 3)

        # 5 个 token 中恰好只剩 3 个有效（随机踢出 2 个），最新登录必有效
        alive = 0
        for i, tk in enumerate(tokens):
            fresh = self.app.test_client()
            r = fresh.get('/api/auth/check', headers={'Authorization': 'Bearer ' + tk})
            if r.get_json()['data']['authenticated']:
                alive += 1
            if i == len(tokens) - 1:
                self.assertEqual(r.get_json()['data']['authenticated'], True, '最新登录必须有效')
        self.assertEqual(alive, 3)

    def _uid(self, username):
        import sqlite3
        conn = sqlite3.connect(Config.DATABASE_PATH)
        row = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        return row[0] if row else 0

    # ---------- 登录失败限速 ----------
    def test_02_login_rate_limit(self):
        """连续失败达到上限后暂时拒绝该 IP 登录"""
        self.client.post('/api/auth/register', json={
            'username': 'rate_user', 'password': 'Rate#12345', 'password2': 'Rate#12345'})
        codes = []
        for i in range(6):
            r = self.client.post('/api/auth/login', json={
                'username': 'rate_user', 'password': 'wrong-%d' % i})
            codes.append(r.status_code)
        # 前 5 次为 401（密码错误），第 6 次触发限速 429
        self.assertEqual(codes[:5], [401] * 5)
        self.assertEqual(codes[5], 429)

        # 正确密码在限速期内同样被拒（防爆破）
        r = self.client.post('/api/auth/login', json={
            'username': 'rate_user', 'password': 'Rate#12345'})
        self.assertEqual(r.status_code, 429)

        # 清空限速后恢复
        from utils import helpers
        helpers._login_failures.clear()
        r = self.client.post('/api/auth/login', json={
            'username': 'rate_user', 'password': 'Rate#12345'})
        self.assertEqual(r.status_code, 200)

    # ---------- SQL 注入无效化 ----------
    def test_03_sql_injection_neutralized(self):
        payload = "' OR '1'='1' --"
        r = self.client.post('/api/auth/login', json={'username': payload, 'password': 'x'})
        self.assertIn(r.status_code, (401, 400))

        r = self._upload('第一章 a\n正文。\n', name='inj.txt')
        bid = r.get_json()['data']['book']['id']
        r = self.client.get('/api/books?query=' + payload.replace(' ', '%20'))
        self.assertEqual(r.status_code, 200)
        titles = [b['title'] for b in r.get_json()['data']]
        self.assertNotIn("'; DROP TABLE users;--", titles)

        # users 表依然完好
        r = self.client.get('/api/books')
        self.assertEqual(r.status_code, 200)

    # ---------- 越权访问 ----------
    def test_04_cross_user_isolation(self):
        r = self._register_and_login('sec_user_b')
        self.assertEqual(r.status_code, 200)

        # 用户 B 上传一本书
        r = self._upload('B 的书\n', name='b-book.txt')
        b_book = r.get_json()['data']['book']['id']

        # 用户 B 创建分组
        r = self.client.post('/api/groups', json={'name': 'B组'})
        b_group = r.get_json()['data']['id']

        # 切回管理员（用户 A），访问 B 的资源必须不可见/不可操作
        self.client.delete_cookie('miniread_session')
        r = self.client.post('/api/auth/login', json={
            'username': 'sec_admin', 'password': 'Sec#12345'})
        self.assertEqual(r.status_code, 200)

        r = self.client.get('/api/books/%d' % b_book)
        self.assertEqual(r.status_code, 404)
        r = self.client.delete('/api/books/%d' % b_book)
        self.assertEqual(r.status_code, 404)
        r = self.client.put('/api/groups/%d' % b_group, json={'name': 'hack'})
        self.assertEqual(r.status_code, 404)
        r = self.client.delete('/api/groups/%d' % b_group)
        self.assertEqual(r.status_code, 404)
        r = self.client.post('/api/books/batch-move', json={'ids': [b_book], 'group_id': None})
        self.assertEqual(r.get_json()['data']['moved'], 0)
        r = self.client.get('/api/rss/%d/items' % b_book)
        self.assertIn(r.status_code, (401, 404))

    # ---------- 管理员接口权限隔离 ----------
    def test_05_admin_routes_forbidden_for_users(self):
        r = self._register_and_login('sec_user_c')
        r = self.client.get('/api/admin/users')
        self.assertEqual(r.status_code, 403)
        r = self.client.post('/api/admin/users/ban', json={'user_id': 1, 'action': 'ban'})
        self.assertEqual(r.status_code, 403)
        r = self.client.get('/api/admin/export')
        self.assertEqual(r.status_code, 403)
        r = self.client.post('/api/admin/update/apply')
        self.assertEqual(r.status_code, 403)

    # ---------- 上传白名单 ----------
    def test_06_upload_extension_whitelist(self):
        r = self.client.post('/api/books/upload', data={
            'file': (io.BytesIO(b'MZ\x90\x00fake'), 'evil.exe'),
        }, content_type='multipart/form-data')
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/api/books/upload', data={
            'file': (io.BytesIO(b'#!/bin/bash\nrm -rf /\n'), 'evil.sh'),
        }, content_type='multipart/form-data')
        self.assertEqual(r.status_code, 400)

    # ---------- SSRF 防护 ----------
    def test_07_rss_ssrf_protection(self):
        from services.rss_sync import _validate_feed_url

        # 内网 / 回环 / 链路本地 / 保留地址拒绝
        for url in (
            'http://127.0.0.1:7766/rss.xml',
            'http://localhost/rss.xml',
            'http://10.0.0.1/rss.xml',
            'http://172.16.0.1/rss.xml',
            'http://192.168.1.1/rss.xml',
            'http://169.254.169.254/latest/meta-data/',
            'http://[::1]/rss.xml',
            'http://0.0.0.0/rss.xml',
        ):
            with self.assertRaises(ValueError, msg=url):
                _validate_feed_url(url)

        # 非 http/https 协议拒绝
        for url in ('ftp://example.com/rss.xml', 'file:///etc/passwd', 'gopher://x'):
            with self.assertRaises(ValueError, msg=url):
                _validate_feed_url(url)

        # 公网域名通过（mock DNS，避免测试环境代理/虚拟网卡干扰）
        import socket
        from unittest.mock import patch
        fake = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 0))]
        with patch('socket.getaddrinfo', return_value=fake):
            _validate_feed_url('https://example.com/rss.xml')

        # API 层：内网地址被拒绝且不创建记录
        r = self.client.post('/api/rss', json={'url': 'http://127.0.0.1:9/rss.xml', 'name': 'x'})
        self.assertEqual(r.status_code, 400)

    # ---------- 路径穿越 ----------
    def test_08_path_traversal_ann_media(self):
        for evil in (
            '/api/public/ann-media/..%2F..%2Fapp.py',
            '/api/public/ann-media/..\\..\\app.py',
            '/api/public/ann-media/....//....//app.py',
            '/api/public/ann-media/%2e%2e%2f%2e%2e%2fsecret_key',
        ):
            r = self.client.get(evil)
            # 绝不能返回 200（泄露文件内容）
            self.assertNotEqual(r.status_code, 200, evil)

    # ---------- XSS 存储不影响数据完整性 ----------
    def test_09_xss_payload_stored_verbatim(self):
        r = self._upload('第一章 x\n<script>alert(1)</script>正文\n', name='xss.txt')
        self.assertEqual(r.status_code, 200)
        bid = r.get_json()['data']['book']['id']
        r = self.client.get('/api/books/%d' % bid)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['data']['title'], 'xss')
        # 章节内容按原样存储（净化在规范书生成时进行），API 不崩溃
        r = self.client.get('/api/books/%d/section/0' % bid)
        self.assertIn(r.status_code, (200, 404))


if __name__ == '__main__':
    unittest.main()

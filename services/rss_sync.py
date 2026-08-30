"""
Miniread (极读) - V2.1 RSS 订阅同步服务
负责订阅源抓取、解析、HTML 净化、入库同步与后台定时循环
"""
import hashlib
import re
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from database import get_db

# content:encoded 与 Atom 命名空间
_CONTENT_NS = '{http://purl.org/rss/1.0/modules/content/}encoded'
_ATOM_NS = '{http://www.w3.org/2005/Atom}'

# 同步循环轮询间隔（秒）
_SYNC_INTERVAL_SECONDS = 1800


def _strip_style_colors(style_value):
    """从内联 style 值中剥离颜色类声明（RSS 正文常带写死的深浅色，暗色主题下不可读）"""
    cleaned = re.sub(r'(?:^|;)\s*(?:color|background-color|background)\s*:\s*[^;]*', '', style_value, flags=re.IGNORECASE)
    cleaned = cleaned.strip('; ')
    return (' style="%s"' % cleaned) if cleaned else ''


def sanitize_html(html):
    """轻量 HTML 净化：移除脚本类标签、事件属性、javascript: 伪协议与内联颜色"""
    if not html:
        return ''
    html = re.sub(r'<script\b[^>]*>.*?</script\s*>', '', html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r'<iframe\b[^>]*>.*?</iframe\s*>', '', html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r'<style\b[^>]*>.*?</style\s*>', '', html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r'\son\w+\s*=\s*"[^"]*"', '', html, flags=re.IGNORECASE)
    html = re.sub(r"\son\w+\s*=\s*'[^']*'", '', html, flags=re.IGNORECASE)
    html = re.sub(r'(href|src)\s*=\s*(["\'])\s*javascript:[^"\']*\2', r'\1=\2', html, flags=re.IGNORECASE)
    html = re.sub(r'style\s*=\s*"([^"]*)"', lambda m: _strip_style_colors(m.group(1)), html, flags=re.IGNORECASE)
    html = re.sub(r"style\s*=\s*'([^']*)'", lambda m: _strip_style_colors(m.group(1)), html, flags=re.IGNORECASE)
    return html


def _text(node):
    """读取节点全部文本（含嵌套）并去除首尾空白"""
    if node is None:
        return ''
    return ''.join(node.itertext()).strip()


def _title_guid(title):
    """无 guid 与 link 时，用标题哈希兜底生成条目标识"""
    return 'hash:' + hashlib.sha256((title or '').encode('utf-8')).hexdigest()


def _rfc822_to_epoch(value):
    """RFC822 日期（RSS pubDate）转 epoch，失败返回当前时间"""
    value = (value or '').strip()
    if not value:
        return time.time()
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (TypeError, ValueError):
        return time.time()


def _iso_to_epoch(value):
    """ISO8601 日期（Atom published/updated）转 epoch，失败返回当前时间"""
    value = (value or '').strip()
    if not value:
        return time.time()
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (TypeError, ValueError):
        return time.time()


def _parse_rss2(root):
    """解析 RSS 2.0：channel/title 与 channel/item"""
    channel = root.find('channel')
    if channel is None:
        raise ValueError('无法解析订阅内容')
    items = []
    for item in channel.findall('item'):
        title = _text(item.find('title'))
        link = _text(item.find('link'))
        guid = _text(item.find('guid')) or link or _title_guid(title)
        content = _text(item.find(_CONTENT_NS)) or _text(item.find('description'))
        items.append({
            'guid': guid,
            'title': title,
            'link': link,
            'published': _rfc822_to_epoch(_text(item.find('pubDate'))),
            'content': sanitize_html(content),
        })
    return {
        'title': _text(channel.find('title')),
        'description': _text(channel.find('description')),
        'items': items,
    }


def _atom_link(entry):
    """取 Atom entry 链接：优先 rel='alternate'，否则第一个 link 的 href"""
    links = entry.findall(_ATOM_NS + 'link')
    for link in links:
        if link.get('rel') == 'alternate':
            return link.get('href') or ''
    if links:
        return links[0].get('href') or ''
    return ''


def _parse_atom(root):
    """解析 Atom：feed/title 与 feed/entry"""
    items = []
    for entry in root.findall(_ATOM_NS + 'entry'):
        title = _text(entry.find(_ATOM_NS + 'title'))
        link = _atom_link(entry)
        guid = _text(entry.find(_ATOM_NS + 'id')) or link or _title_guid(title)
        content = _text(entry.find(_ATOM_NS + 'content')) or _text(entry.find(_ATOM_NS + 'summary'))
        # published 优先于 updated
        published_text = _text(entry.find(_ATOM_NS + 'published')) or _text(entry.find(_ATOM_NS + 'updated'))
        published = _iso_to_epoch(published_text)
        items.append({
            'guid': guid,
            'title': title,
            'link': link,
            'published': published,
            'content': sanitize_html(content),
        })
    return {
        'title': _text(root.find(_ATOM_NS + 'title')),
        'description': _text(root.find(_ATOM_NS + 'subtitle')),
        'items': items,
    }


def parse_feed(data):
    """解析 RSS 2.0 / Atom 订阅内容，返回统一结构；失败抛 ValueError"""
    if isinstance(data, str):
        data = data.encode('utf-8')
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise ValueError('无法解析订阅内容') from e
    tag = root.tag.rsplit('}', 1)[-1].lower()
    if tag == 'rss':
        return _parse_rss2(root)
    if tag == 'feed':
        return _parse_atom(root)
    raise ValueError('无法解析订阅内容')


# ============ SSRF 防护 ============

# 抓取大小上限（字节），防止超大响应造成内存/带宽 DoS
MAX_FEED_BYTES = 10 * 1024 * 1024

_ALLOWED_SCHEMES = ('http', 'https')


def _assert_public_host(host):
    """校验主机名解析出的所有 IP 均为公网地址（SSRF 防护）"""
    import ipaddress as _ip
    import socket as _socket
    try:
        infos = _socket.getaddrinfo(host, None)
    except Exception as e:
        raise ValueError('订阅地址无法解析') from e
    for info in infos:
        addr = info[4][0]
        try:
            ip = _ip.ip_address(addr)
        except ValueError:
            continue
        # is_global 为 False 覆盖：回环/私网/链路本地/保留地址（含 127.0.0.1、10/8、
        # 172.16/12、192.168/16、169.254/16、::1、fc00::/7 等）
        if not ip.is_global:
            raise ValueError('不允许访问内网或保留地址')


def _validate_feed_url(url):
    """校验订阅地址：仅 http/https 且目标主机为公网地址"""
    from urllib.parse import urlparse
    if not url or not isinstance(url, str):
        raise ValueError('订阅地址无效')
    parsed = urlparse(url.strip())
    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError('仅支持 http/https 订阅地址')
    host = parsed.hostname
    if not host:
        raise ValueError('订阅地址无效')
    _assert_public_host(host)


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """重定向时逐跳重新校验目标地址，防止通过重定向绕过 SSRF 校验"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_feed_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_feed(url, timeout=20):
    """抓取订阅源原始字节，非 200 或任何异常抛 ValueError。

    安全约束：仅 http/https、仅公网目标（含重定向逐跳校验）、限制读取大小。
    """
    _validate_feed_url(url)
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Miniread RSS Reader)'},
    )
    opener = urllib.request.build_opener(_SafeRedirectHandler)
    try:
        with opener.open(req, timeout=timeout) as resp:
            if getattr(resp, 'status', 200) != 200:
                raise ValueError('订阅源返回状态码 %s' % resp.status)
            data = resp.read(MAX_FEED_BYTES + 1)
            if len(data) > MAX_FEED_BYTES:
                raise ValueError('订阅内容过大')
            return data
    except urllib.error.HTTPError as e:
        raise ValueError('订阅源返回状态码 %s' % e.code) from e
    except ValueError:
        raise
    except Exception as e:
        raise ValueError('订阅源抓取失败：%s' % e) from e


def sync_book(book_id):
    """同步单个订阅：抓取、解析、去重入库，返回本次新增条数"""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT rss_url FROM books WHERE id = ? AND kind = 'rss'",
            (book_id,),
        ).fetchone()
        url = row['rss_url'] if row else ''
    finally:
        conn.close()
    if not url:
        return 0

    feed = parse_feed(fetch_feed(url))

    conn = get_db()
    try:
        existing = {
            r['guid'] for r in conn.execute(
                'SELECT guid FROM rss_items WHERE book_id = ?', (book_id,)
            )
        }
        added = 0
        for item in feed['items']:
            guid = item['guid']
            if guid in existing:
                continue
            existing.add(guid)
            cur = conn.execute(
                '''INSERT OR IGNORE INTO rss_items
                   (book_id, guid, title, link, published, content)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (book_id, guid, item['title'], item['link'],
                 item['published'], item['content']),
            )
            if cur.rowcount and cur.rowcount > 0:
                added += cur.rowcount
        conn.execute(
            "UPDATE books SET last_synced = strftime('%s', 'now') WHERE id = ?",
            (book_id,),
        )
        conn.commit()
        return added
    finally:
        conn.close()


def sync_due_books():
    """同步所有到期订阅（从未同步或已超过 sync_interval 小时），单个失败静默跳过"""
    conn = get_db()
    try:
        rows = conn.execute(
            '''SELECT id FROM books
               WHERE kind = 'rss'
               AND (last_synced IS NULL
                    OR last_synced + sync_interval * 3600 <= strftime('%s', 'now'))'''
        ).fetchall()
    finally:
        conn.close()
    for row in rows:
        try:
            sync_book(row['id'])
        except Exception:
            continue


def start_sync_loop():
    """启动后台守护线程（rss-sync）：立即同步一轮，之后每 30 分钟一轮"""

    def _loop():
        while True:
            try:
                sync_due_books()
            except Exception:
                pass
            time.sleep(_SYNC_INTERVAL_SECONDS)

    threading.Thread(target=_loop, daemon=True, name='rss-sync').start()

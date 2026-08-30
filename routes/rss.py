"""
Miniread (极读) - V2.1 RSS 订阅路由
创建/编辑订阅、手动同步、分页拉取条目
"""
from flask import Blueprint, g, request

from database import get_db
from services import rss_sync
from utils.helpers import json_response, require_auth

rss_bp = Blueprint('rss', __name__)


def _get_rss_book(book_id):
    """校验归属且 kind='rss'，不满足返回 None"""
    conn = get_db()
    try:
        return conn.execute(
            "SELECT * FROM books WHERE id = ? AND user_id = ? AND kind = 'rss'",
            (book_id, g.current_user['id']),
        ).fetchone()
    finally:
        conn.close()


def _parse_interval(value, default=24):
    """解析同步间隔（小时），int 且最小 1，无上限"""
    try:
        interval = int(value)
    except (TypeError, ValueError):
        return default
    return max(interval, 1)


@rss_bp.route('/api/rss', methods=['POST'])
@require_auth
def create_subscription():
    """创建 RSS 订阅：校验链接可解析后入库并立即同步一轮"""
    data = request.get_json(silent=True) or {}
    url = (data.get('url') or '').strip()
    if not url or not (url.startswith('http://') or url.startswith('https://')):
        return json_response(code=400, message='请提供有效的订阅链接')

    try:
        feed = rss_sync.parse_feed(rss_sync.fetch_feed(url))
    except ValueError:
        return json_response(code=400, message='订阅解析失败，请检查链接')

    name = (data.get('name') or '').strip() or feed['title'] or 'RSS 订阅'
    interval = _parse_interval(data.get('interval'), 24)

    conn = get_db()
    try:
        cur = conn.execute(
            '''INSERT INTO books
               (user_id, title, author, format, file_path, file_size, source,
                kind, rss_url, sync_interval, canonical_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (g.current_user['id'], name, 'RSS 订阅', 'rss', '', 0, 'rss',
             'rss', url, interval, 'none'),
        )
        book_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    # 创建后立即同步一轮，失败不影响订阅创建
    added = 0
    try:
        added = rss_sync.sync_book(book_id)
    except Exception:
        pass

    return json_response(data={'book_id': book_id, 'title': name, 'items': added})


@rss_bp.route('/api/rss/<int:book_id>', methods=['PUT'])
@require_auth
def update_subscription(book_id):
    """编辑订阅：改名或调整同步间隔"""
    row = _get_rss_book(book_id)
    if row is None:
        return json_response(code=404, message='订阅不存在')

    data = request.get_json(silent=True) or {}
    title = row['title']
    interval = row['sync_interval'] or 24
    if (data.get('name') or '').strip():
        title = data['name'].strip()
    if data.get('interval') is not None:
        interval = _parse_interval(data.get('interval'), interval)

    conn = get_db()
    try:
        conn.execute(
            'UPDATE books SET title = ?, sync_interval = ? WHERE id = ?',
            (title, interval, book_id),
        )
        conn.commit()
    finally:
        conn.close()

    return json_response(data={'title': title, 'sync_interval': interval})


@rss_bp.route('/api/rss/<int:book_id>/sync', methods=['POST'])
@require_auth
def sync_subscription(book_id):
    """手动同步单个订阅"""
    if _get_rss_book(book_id) is None:
        return json_response(code=404, message='订阅不存在')
    try:
        added = rss_sync.sync_book(book_id)
    except ValueError as e:
        return json_response(code=400, message=str(e) or '订阅同步失败')

    conn = get_db()
    try:
        row = conn.execute(
            'SELECT last_synced FROM books WHERE id = ?', (book_id,)
        ).fetchone()
    finally:
        conn.close()

    return json_response(data={'added': added, 'last_synced': row['last_synced'] if row else None})


@rss_bp.route('/api/rss/<int:book_id>/items', methods=['GET'])
@require_auth
def list_subscription_items(book_id):
    """分页拉取订阅条目，按发布时间倒序"""
    if _get_rss_book(book_id) is None:
        return json_response(code=404, message='订阅不存在')

    try:
        page = max(int(request.args.get('page', 1)), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        size = max(int(request.args.get('size', 20)), 1)
    except (TypeError, ValueError):
        size = 20
    offset = (page - 1) * size

    conn = get_db()
    try:
        total = conn.execute(
            'SELECT COUNT(*) AS cnt FROM rss_items WHERE book_id = ?', (book_id,)
        ).fetchone()['cnt']
        rows = conn.execute(
            '''SELECT id, guid, title, link, published, content
               FROM rss_items
               WHERE book_id = ?
               ORDER BY published DESC, id DESC
               LIMIT ? OFFSET ?''',
            (book_id, size, offset),
        ).fetchall()
    finally:
        conn.close()

    # content 入库前已在 parse_feed 中净化，这里直接透传
    items = [dict(r) for r in rows]
    return json_response(data={'total': total, 'page': page, 'size': size, 'items': items})

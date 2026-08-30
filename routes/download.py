import json
import os
import queue
import re
import secrets
import threading
import time
import traceback
import uuid

import requests
from flask import Blueprint, Response, g, request

from config import Config
from database import get_db
from utils.helpers import json_response, require_auth

download_bp = Blueprint('download', __name__)

ALLOWED_FORMATS = ('epub', 'txt', 'html', 'pdf')
ACTIVE_STATUSES = ('pending', 'downloading')
FETCH_TIMEOUT = 1800
SSE_MAX_CONNECTIONS = 3
SSE_IDLE_TIMEOUT = 15
SSE_LIFETIME = 900
DB_WRITE_INTERVAL = 1.0
INTERPOLATE_INTERVAL = 3
PROGRESS_CAP = 95

_sse_lock = threading.Lock()
_sse_clients = {}
_live_lock = threading.Lock()
_task_live = {}
_http = requests.Session()


def _get_server_config(user_id):
    conn = get_db()
    try:
        row = conn.execute(
            'SELECT server_url, api_token FROM novel_server_config WHERE user_id = ?',
            (user_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return '', ''
    return (row['server_url'] or '').strip().rstrip('/'), (row['api_token'] or '').strip()


def _get_task(task_id, user_id):
    conn = get_db()
    try:
        return conn.execute(
            'SELECT * FROM download_tasks WHERE id = ? AND user_id = ?',
            (task_id, user_id)
        ).fetchone()
    finally:
        conn.close()


def _update_task(task_id, fields, guard=True):
    sets = ', '.join(f'{k} = ?' for k in fields)
    sql = f'UPDATE download_tasks SET {sets} WHERE id = ?'
    params = list(fields.values()) + [task_id]
    if guard:
        sql += " AND status IN ('pending', 'downloading')"
    conn = get_db()
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_tasks_snapshot(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            '''SELECT * FROM download_tasks WHERE user_id = ?
               ORDER BY created_at DESC, id DESC LIMIT 20''',
            (user_id,)
        ).fetchall()
    finally:
        conn.close()
    with _live_lock:
        live = {task_id: dict(value) for task_id, value in _task_live.items()}
    tasks = []
    for row in rows:
        d = dict(row)
        status = d['status']
        current = live.get(d['id'], {})
        index = current.get('index', 0)
        total = current.get('total', 0)
        progress = d['progress']
        if 'progress' in current and status in ACTIVE_STATUSES:
            progress = current['progress']
        if status == 'completed':
            index = index or d['total_chapters']
            total = total or d['total_chapters']
            progress = 100
        tasks.append({
            'id': d['id'],
            'book_name': d['book_name'],
            'author': d['author'],
            'source_name': d['source_name'],
            'format': d['format'],
            'status': status,
            'progress': progress,
            'index': index,
            'total': total,
            'estimated': d['estimated'],
            'error_message': d['error_message'],
            'created_at': d['created_at'],
            'completed_at': d['completed_at'],
        })
    return tasks


def _push_snapshot(user_id):
    event = {'type': 'progress', 'tasks': get_tasks_snapshot(user_id)}
    with _sse_lock:
        queues = list(_sse_clients.get(user_id, ()))
    for q in queues:
        try:
            q.put(event)
        except Exception:
            traceback.print_exc()


def _safe_book_filename(book_name, book_format):
    name = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', str(book_name or '').strip()).strip(' .')
    if not name:
        name = 'book'
    if len(name) > 80:
        name = name[:80]
    return f'{name}.{book_format}'


def _unique_path(directory, filename):
    base, ext = os.path.splitext(filename)
    path = os.path.join(directory, filename)
    counter = 1
    while os.path.exists(path):
        path = os.path.join(directory, f'{base}_{counter}{ext}')
        counter += 1
    return path


def _new_dlid():
    # so-novel-server 约定 dlid 为 9 位数字
    while True:
        dlid = ''.join(secrets.choice('0123456789') for _ in range(9))
        conn = get_db()
        try:
            row = conn.execute('SELECT id FROM download_tasks WHERE dlid = ?', (dlid,)).fetchone()
        finally:
            conn.close()
        if not row:
            return dlid


def _fail_task(user_id, task_id, message):
    try:
        _update_task(task_id, {'status': 'failed', 'error_message': message})
    except Exception:
        traceback.print_exc()
    _push_snapshot(user_id)


def _consume_progress(user_id, task_id, server_url, api_token, dlid, interp_start, stop_event):
    finished = False
    last_write = 0.0
    resp = None
    try:
        resp = _http.get(
            f'{server_url}/download-progress',
            params={'token': api_token},
            stream=True,
            timeout=(10, None)
        )
        resp.encoding = 'utf-8'
        if resp.status_code != 200:
            raise RuntimeError(f'HTTP {resp.status_code}')
        for raw in resp.iter_lines(decode_unicode=True):
            if stop_event.is_set():
                finished = True
                break
            if not raw or not isinstance(raw, str) or raw.startswith(':'):
                continue
            if not raw.startswith('data:'):
                continue
            try:
                payload = json.loads(raw[5:].strip())
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            # so-novel-server SSE 事件带 type 字段：
            #   download-progress: {type, downloads:[{dlid,bookName,index,total,status}]}
            #   download-finished: {type, dlid, bookName, status} 终态帧
            event_type = str(payload.get('type') or '')
            if event_type == 'download-finished':
                # 仅本任务的终态帧才结束消费；并发其他任务的终态帧直接跳过
                if str(payload.get('dlid', '')) == str(dlid):
                    finished = True
                    break
                continue
            downloads = payload.get('downloads')
            if not isinstance(downloads, list):
                continue
            for item in downloads:
                if not isinstance(item, dict) or str(item.get('dlid', '')) != str(dlid):
                    continue
                try:
                    index = max(0, int(item.get('index') or 0))
                except (TypeError, ValueError):
                    index = 0
                try:
                    total = max(0, int(item.get('total') or 0))
                except (TypeError, ValueError):
                    total = 0
                item_status = str(item.get('status') or 'downloading')
                progress = round(index / total * 100) if total > 0 else 0
                with _live_lock:
                    _task_live[task_id] = {'index': index, 'total': total, 'progress': progress}
                now = time.time()
                if now - last_write >= DB_WRITE_INTERVAL:
                    last_write = now
                    fields = {'status': 'downloading'}
                    if total > 0:
                        fields['progress'] = progress
                    try:
                        if _update_task(task_id, fields) == 0:
                            finished = True
                            break
                    except Exception:
                        traceback.print_exc()
                _push_snapshot(user_id)
                if item_status != 'downloading':
                    # 终态帧：立即落库最终章节数，避免主线程读取竞态导致完成态显示 0 章
                    try:
                        _update_task(task_id, {'total_chapters': index, 'progress': 100})
                    except Exception:
                        traceback.print_exc()
                    finished = True
                    break
            if finished:
                break
    except Exception:
        traceback.print_exc()
    finally:
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass
        if not finished and not stop_event.is_set():
            try:
                _update_task(task_id, {'estimated': 1})
            except Exception:
                traceback.print_exc()
            interp_start.set()


def _interpolate(user_id, task_id, interp_start, stop_event):
    interp_start.wait()
    while not stop_event.is_set():
        time.sleep(INTERPOLATE_INTERVAL)
        if stop_event.is_set():
            break
        with _live_lock:
            current = _task_live.get(task_id)
        if current is None:
            break
        progress = min(current.get('progress', 0) + 1, PROGRESS_CAP)
        with _live_lock:
            if task_id in _task_live:
                _task_live[task_id]['progress'] = progress
        try:
            if _update_task(task_id, {'progress': progress}) == 0:
                break
        except Exception:
            traceback.print_exc()
        _push_snapshot(user_id)


def _run_task(task_id, user_id, server_url, api_token, url, book_format, book_name, author, dlid):
    stop_event = threading.Event()
    interp_start = threading.Event()
    consumer = threading.Thread(
        target=_consume_progress,
        args=(user_id, task_id, server_url, api_token, dlid, interp_start, stop_event),
        daemon=True
    )
    interpolator = threading.Thread(
        target=_interpolate,
        args=(user_id, task_id, interp_start, stop_event),
        daemon=True
    )
    consumer.start()
    interpolator.start()
    with _live_lock:
        _task_live[task_id] = {'index': 0, 'total': 0, 'progress': 0}
    try:
        try:
            _update_task(task_id, {'status': 'downloading'})
        except Exception:
            traceback.print_exc()
        _push_snapshot(user_id)
        fetch_resp = _http.get(
            f'{server_url}/book-fetch',
            params={'url': url, 'format': book_format, 'token': api_token, 'dlid': dlid},
            timeout=FETCH_TIMEOUT
        )
        if fetch_resp.status_code != 200:
            msg = f'下载服务器响应异常 (HTTP {fetch_resp.status_code})'
            try:
                j = fetch_resp.json()
                msg = _map_upstream_message(j.get('code', fetch_resp.status_code), j.get('message') or msg)
            except Exception:
                pass
            _fail_task(user_id, task_id, msg)
            return
        try:
            result = fetch_resp.json()
        except Exception:
            _fail_task(user_id, task_id, '下载服务器返回数据异常')
            return
        # so-novel-server 约定：成功码为 200，失败时透传上游 message
        if result.get('code') != 200:
            _fail_task(user_id, task_id, _map_upstream_message(result.get('code'), result.get('message')))
            return
        file_resp = _http.get(
            f'{server_url}/book-download',
            params={'dlid': dlid, 'token': api_token},
            stream=True,
            timeout=(10, 120)
        )
        try:
            if file_resp.status_code != 200:
                msg = '获取下载文件失败，文件可能已过期'
                try:
                    j = file_resp.json()
                    msg = _map_upstream_message(j.get('code'), j.get('message') or msg)
                except Exception:
                    pass
                _fail_task(user_id, task_id, msg)
                return
            user_dir = os.path.join(Config.UPLOAD_FOLDER, str(user_id))
            os.makedirs(user_dir, exist_ok=True)
            save_path = _unique_path(user_dir, _safe_book_filename(book_name, book_format))
            with open(save_path, 'wb') as f:
                for chunk in file_resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
        finally:
            try:
                file_resp.close()
            except Exception:
                pass
        file_size = os.path.getsize(save_path)
        with _live_lock:
            index = _task_live.get(task_id, {}).get('index', 0)
        conn = get_db()
        try:
            conn.execute(
                '''INSERT INTO books (user_id, title, author, format, file_path, file_size,
                   source, canonical_status, fingerprint)
                   VALUES (?, ?, ?, ?, ?, ?, 'sonovel', 'legacy', ?)''',
                (user_id, book_name, author, book_format, save_path, file_size, uuid.uuid4().hex)
            )
            conn.execute(
                '''UPDATE download_tasks SET status = 'completed', progress = 100,
                   total_chapters = MAX(COALESCE(total_chapters, 0), ?), completed_at = ?
                   WHERE id = ? AND status IN ('pending', 'downloading')''',
                (index, time.time(), task_id)
            )
            conn.commit()
        finally:
            conn.close()
        _push_snapshot(user_id)
    except requests.exceptions.Timeout:
        traceback.print_exc()
        _fail_task(user_id, task_id, '下载超时，请稍后重试')
    except requests.exceptions.ConnectionError:
        traceback.print_exc()
        _fail_task(user_id, task_id, '无法连接到下载服务器')
    except Exception as e:
        traceback.print_exc()
        _fail_task(user_id, task_id, f'下载失败: {e}')
    finally:
        stop_event.set()
        interp_start.set()
        with _live_lock:
            _task_live.pop(task_id, None)


def _map_upstream_message(code, message=None):
    """按 so-novel-server 的错误码约定（API.md）映射为可读文案，优先透传上游 message"""
    if message:
        return str(message)
    try:
        code = int(code)
    except (TypeError, ValueError):
        return '未知错误'
    if code == 400:
        return '请求参数错误'
    if code == 401:
        return 'Token无效，请检查配置'
    if code == 403:
        return '权限不足或账号已被封禁'
    if code == 404:
        return '书源资源不存在'
    if code == 409:
        return '资源冲突，请稍后再试'
    if code == 501:
        return '下载服务器维护中，请稍后再试'
    if code == 503:
        return '请求过于频繁，请稍后再试'
    if code >= 500:
        return '书源异常，请稍后再试'
    return f'搜索失败 (code={code})'


@download_bp.route('/api/download/config', methods=['GET'])
@require_auth
def get_config():
    server_url, api_token = _get_server_config(g.current_user['id'])
    return json_response(data={'serverUrl': server_url, 'hasToken': bool(api_token)})


@download_bp.route('/api/download/config', methods=['PUT'])
@require_auth
def update_config():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    user_id = g.current_user['id']
    conn = get_db()
    try:
        row = conn.execute(
            'SELECT server_url, api_token FROM novel_server_config WHERE user_id = ?',
            (user_id,)
        ).fetchone()
        server_url = row[0] if row else ''
        api_token = row[1] if row else ''
        # 部分更新：只覆盖请求中出现的字段，未提供的保持原值
        if 'serverUrl' in data or 'server_url' in data:
            server_url = str(data.get('serverUrl') or data.get('server_url') or '').strip().rstrip('/')
        if 'apiToken' in data or 'api_token' in data:
            api_token = str(data.get('apiToken') or data.get('api_token') or '').strip()
        existing = conn.execute(
            'SELECT id FROM novel_server_config WHERE user_id = ?',
            (user_id,)
        ).fetchone()
        if existing:
            conn.execute(
                'UPDATE novel_server_config SET server_url = ?, api_token = ? WHERE user_id = ?',
                (server_url, api_token, user_id)
            )
        else:
            conn.execute(
                'INSERT INTO novel_server_config (user_id, server_url, api_token) VALUES (?, ?, ?)',
                (user_id, server_url, api_token)
            )
        conn.commit()
    finally:
        conn.close()
    return json_response(data={'message': '配置已保存'})


@download_bp.route('/api/download/search', methods=['GET'])
@require_auth
def search_books():
    kw = request.args.get('kw', '').strip()
    if not kw:
        return json_response(code=400, message='请输入搜索关键词')
    server_url, api_token = _get_server_config(g.current_user['id'])
    if not server_url:
        return json_response(code=400, message='请先在右上角设置中配置服务器地址')
    if not api_token:
        return json_response(code=400, message='请先在右上角设置中配置Token')
    try:
        resp = _http.get(
            f'{server_url}/search/aggregated',
            params={'kw': kw, 'token': api_token},
            timeout=Config.SONOVEL_TIMEOUT * 2
        )
    except requests.exceptions.Timeout:
        return json_response(code=502, message='搜书服务器响应超时')
    except requests.exceptions.RequestException:
        return json_response(code=502, message='无法连接到搜书服务器，请检查服务器地址')
    # 上游错误可能是 HTTP 4xx/5xx + JSON body（{code,message}），也可能是 HTTP 200 + body 错误码，两种都解析
    try:
        result = resp.json()
    except Exception:
        return json_response(code=502, message='搜书服务器返回数据异常')
    if resp.status_code != 200:
        return json_response(code=502, message=_map_upstream_message(
            result.get('code', resp.status_code), result.get('message')))
    # so-novel-server 约定：成功码为 200（非 0），错误时透传上游 message
    if result.get('code') != 200:
        return json_response(code=502, message=_map_upstream_message(result.get('code'), result.get('message')))
    return json_response(data=result.get('data') or [])


@download_bp.route('/api/download/fetch', methods=['POST'])
@require_auth
def fetch_book():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    url = str(data.get('url') or '').strip()
    book_format = str(data.get('format') or 'epub').strip().lower()
    book_name = str(data.get('bookName') or data.get('book_name') or '').strip()
    author = str(data.get('author') or '').strip()
    source_name = str(data.get('sourceName') or data.get('source_name') or '').strip()
    if not url:
        return json_response(code=400, message='缺少书籍URL')
    if book_format not in ALLOWED_FORMATS:
        return json_response(code=400, message='不支持的下载格式，仅支持 epub/txt/html/pdf')
    user_id = g.current_user['id']
    server_url, api_token = _get_server_config(user_id)
    if not server_url or not api_token:
        return json_response(code=400, message='请先配置服务器地址和Token')
    dlid = _new_dlid()
    conn = get_db()
    try:
        cursor = conn.execute(
            '''INSERT INTO download_tasks
               (user_id, book_name, author, source_name, format, url, dlid, status, progress, estimated, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', 0, 0, ?)''',
            (user_id, book_name, author, source_name, book_format, url, dlid, time.time())
        )
        task_id = cursor.lastrowid
        conn.commit()
    finally:
        conn.close()
    threading.Thread(
        target=_run_task,
        args=(task_id, user_id, server_url, api_token, url, book_format, book_name, author, dlid),
        daemon=True
    ).start()
    return json_response(data={'task_id': task_id, 'dlid': dlid})


@download_bp.route('/api/download/tasks', methods=['GET'])
@require_auth
def list_tasks():
    return json_response(data=get_tasks_snapshot(g.current_user['id']))


@download_bp.route('/api/download/tasks/<int:task_id>', methods=['DELETE'])
@require_auth
def delete_task(task_id):
    user_id = g.current_user['id']
    row = _get_task(task_id, user_id)
    if not row:
        return json_response(code=404, message='任务不存在')
    conn = get_db()
    try:
        if row['status'] in ACTIVE_STATUSES:
            conn.execute(
                "UPDATE download_tasks SET status = 'abandoned', error_message = ? WHERE id = ?",
                ('已停止跟踪，服务器端下载不会中止', task_id)
            )
        else:
            conn.execute('DELETE FROM download_tasks WHERE id = ?', (task_id,))
        conn.commit()
    finally:
        conn.close()
    _push_snapshot(user_id)
    return json_response(data={'message': '任务已删除'})


@download_bp.route('/api/download/progress', methods=['GET'])
@require_auth
def download_progress():
    user_id = g.current_user['id']
    with _sse_lock:
        clients = _sse_clients.get(user_id)
        if clients is None:
            clients = []
            _sse_clients[user_id] = clients
        if len(clients) >= SSE_MAX_CONNECTIONS:
            limited = True
        else:
            limited = False
            q = queue.Queue()
            clients.append(q)
    if limited:
        return json_response(code=429, message='实时连接数已达上限，请稍后重试')

    def generate():
        try:
            initial = {'type': 'progress', 'tasks': get_tasks_snapshot(user_id)}
            yield f'data: {json.dumps(initial)}\n\n'
            deadline = time.time() + SSE_LIFETIME
            while time.time() < deadline:
                try:
                    event = q.get(timeout=SSE_IDLE_TIMEOUT)
                except queue.Empty:
                    yield ': ping\n\n'
                    continue
                yield f'data: {json.dumps(event)}\n\n'
        except GeneratorExit:
            pass
        except Exception:
            traceback.print_exc()
        finally:
            with _sse_lock:
                remaining = _sse_clients.get(user_id)
                if remaining is not None:
                    try:
                        remaining.remove(q)
                    except ValueError:
                        pass
                    if not remaining:
                        _sse_clients.pop(user_id, None)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        }
    )

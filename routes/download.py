"""
Miniread (极读) - SoNovel 书籍下载路由
"""
import os
import time
import threading
import requests
from flask import Blueprint, request, g, Response, jsonify
from database import get_db
from config import Config
from utils.helpers import json_response, require_auth, format_file_size

download_bp = Blueprint('download', __name__)

# 存储SSE连接客户端
_sse_clients = {}  # user_id -> [queue]


@download_bp.route('/api/download/config', methods=['GET'])
@require_auth
def get_config():
    """获取SoNovel服务器配置"""
    conn = get_db()
    row = conn.execute(
        'SELECT server_url, api_token FROM novel_server_config WHERE user_id = ?',
        (g.current_user['id'],)
    ).fetchone()
    conn.close()

    if row:
        return json_response(data={
            'serverUrl': row['server_url'],
            'apiToken': row['api_token']
        })
    return json_response(data={'serverUrl': '', 'apiToken': ''})


@download_bp.route('/api/download/config', methods=['PUT'])
@require_auth
def update_config():
    """更新SoNovel服务器配置"""
    data = request.get_json()
    server_url = (data.get('serverUrl') or '').strip().rstrip('/')
    api_token = (data.get('apiToken') or '').strip()

    conn = get_db()
    existing = conn.execute(
        'SELECT id FROM novel_server_config WHERE user_id = ?',
        (g.current_user['id'],)
    ).fetchone()

    if existing:
        conn.execute(
            'UPDATE novel_server_config SET server_url = ?, api_token = ? WHERE user_id = ?',
            (server_url, api_token, g.current_user['id'])
        )
    else:
        conn.execute(
            'INSERT INTO novel_server_config (user_id, server_url, api_token) VALUES (?, ?, ?)',
            (g.current_user['id'], server_url, api_token)
        )

    conn.commit()
    conn.close()
    return json_response(data={'message': '配置已保存'})


@download_bp.route('/api/download/search', methods=['GET'])
@require_auth
def search_books():
    """通过SoNovel API搜索书籍"""
    kw = request.args.get('kw', '').strip()
    if not kw:
        return json_response(code=400, message='请输入搜索关键词')

    # 获取服务器配置
    conn = get_db()
    config_row = conn.execute(
        'SELECT server_url, api_token FROM novel_server_config WHERE user_id = ?',
        (g.current_user['id'],)
    ).fetchone()
    conn.close()

    if not config_row or not config_row['server_url']:
        return json_response(code=400, message='请先在右上角设置中配置服务器地址和Token')
    if not config_row['api_token']:
        return json_response(code=400, message='请先在右上角设置中配置Token')

    try:
        resp = requests.get(f"{config_row['server_url']}/search/aggregated",
            params={'kw': kw, 'token': config_row['api_token']}, timeout=Config.SONOVEL_TIMEOUT)

        if resp.status_code != 200:
            return json_response(code=502, message='无法连接到搜书服务器，请检查服务器地址')

        data = resp.json()
        code_map = {400:'请求参数错误，请重试', 401:'Token无效或已过期，请重新获取Token',
                    403:'账号权限不足', 404:'未找到相关书籍', 409:'资源冲突',
                    500:'搜书服务器内部错误，请稍后重试', 501:'搜书服务器正在维护中',
                    503:'请求过于频繁，请稍后再试'}
        sc = data.get('code', 200)
        if sc != 200:
            return json_response(code=502, message=code_map.get(sc, f'搜书服务器错误 (code={sc})'))

        return json_response(data=data.get('data', []))

    except requests.exceptions.ConnectionError:
        return json_response(code=502, message='无法连接到SoNovel服务器，请检查服务器地址')
    except requests.exceptions.Timeout:
        return json_response(code=502, message='SoNovel服务器响应超时')
    except Exception as e:
        return json_response(code=500, message=f'搜索请求失败: {str(e)}')


@download_bp.route('/api/download/fetch', methods=['POST'])
@require_auth
def fetch_book():
    """从SoNovel下载书籍"""
    data = request.get_json()
    url = (data.get('url') or '').strip()
    book_format = (data.get('format') or 'epub').strip()
    book_name = (data.get('bookName') or '').strip()
    author = (data.get('author') or '').strip()
    source_name = (data.get('sourceName') or '').strip()

    if not url:
        return json_response(code=400, message='缺少书籍URL')

    # 获取服务器配置
    conn = get_db()
    config_row = conn.execute(
        'SELECT server_url, api_token FROM novel_server_config WHERE user_id = ?',
        (g.current_user['id'],)
    ).fetchone()
    conn.close()

    if not config_row or not config_row['server_url'] or not config_row['api_token']:
        return json_response(code=400, message='请先配置服务器地址和Token')

    # 创建下载任务
    conn = get_db()
    now = time.time()
    cursor = conn.execute(
        '''INSERT INTO download_tasks
           (user_id, book_name, author, source_name, format, url, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (g.current_user['id'], book_name, author, source_name, book_format, url, 'pending', now)
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # 异步执行下载
    server_url = config_row['server_url']
    api_token = config_row['api_token']

    thread = threading.Thread(
        target=_do_fetch_book,
        args=(task_id, g.current_user['id'], server_url, api_token, url, book_format, book_name, author),
        daemon=True
    )
    thread.start()

    return json_response(data={
        'taskId': task_id,
        'message': '下载任务已创建'
    })


def _do_fetch_book(task_id, user_id, server_url, api_token, url, book_format, book_name, author):
    """后台下载 — SoNovel的book-fetch是阻塞的(下载完成才返回)"""
    import json
    conn = get_db()

    def set_progress(pct):
        try:
            conn.execute('UPDATE download_tasks SET progress=? WHERE id=?', (pct, task_id))
            conn.commit()
            _notify_sse(user_id, {'type': 'download-progress', 'taskId': task_id, 'progress': pct})
        except: pass

    def fail(msg):
        try: conn.execute('UPDATE download_tasks SET status=?,error_message=? WHERE id=?', ('failed',msg,task_id)); conn.commit()
        except: pass
        _notify_sse(user_id, {'type': 'download-error', 'taskId': task_id, 'error': msg})

    try:
        set_progress(1)
        conn.execute('UPDATE download_tasks SET status=? WHERE id=?', ('downloading', task_id)); conn.commit()
        set_progress(5)

        # 1. SoNovel下载(阻塞, 直到完成才返回dlid)
        fetch_resp = requests.get(f"{server_url}/book-fetch",
            params={'url': url, 'format': book_format, 'token': api_token},
            timeout=Config.SONOVEL_TIMEOUT * 3)
        set_progress(60)
        if fetch_resp.status_code != 200:
            fail(fetch_resp.json().get('message','SoNovel错误') if fetch_resp.text else 'SoNovel错误'); conn.close(); return
        result = fetch_resp.json()
        if result.get('code') != 200:
            fail(result.get('message', '下载失败')); conn.close(); return

        dlid = result.get('data', {}).get('dlid', '')
        file_name = result.get('data', {}).get('fileName', f'{book_name}.{book_format}')
        set_progress(70)

        # 2. 从SoNovel取回文件到Miniread
        file_resp = requests.get(f"{server_url}/book-download",
            params={'dlid': dlid, 'token': api_token}, stream=True,
            timeout=Config.SONOVEL_TIMEOUT * 2)
        if file_resp.status_code != 200:
            fail('文件传输失败'); conn.close(); return

        user_dir = os.path.join(Config.UPLOAD_FOLDER, str(user_id)); os.makedirs(user_dir, exist_ok=True)
        save_path = os.path.join(user_dir, file_name)
        c = 1
        while os.path.exists(save_path):
            n, e = os.path.splitext(file_name); save_path = os.path.join(user_dir, f"{n}_{c}{e}"); c += 1

        total = int(file_resp.headers.get('content-length', 0)); received = 0
        with open(save_path, 'wb') as f:
            for chunk in file_resp.iter_content(chunk_size=65536):
                if chunk: f.write(chunk); received += len(chunk)
                if total > 0:
                    pct = 70 + int((received / total) * 25)
                    if pct % 5 == 0: set_progress(min(pct, 95))

        set_progress(96); file_size = os.path.getsize(save_path)

        from services.book_parser import parse_epub
        title, book_auth, t_ch = book_name, author, 0
        bext = os.path.splitext(file_name)[1].lower().lstrip('.')
        try:
            if bext == 'epub':
                meta = parse_epub(save_path)
                title = meta.get('title', title); book_auth = meta.get('author', book_auth)
                t_ch = meta.get('total_chapters', 0)
        except: pass

        now = time.time()
        conn.execute('''INSERT INTO books (user_id,title,author,format,file_path,file_size,source,total_chapters,created_at)
          VALUES (?,?,?,?,?,?,?,?,?)''', (user_id,title,book_auth,bext,save_path,file_size,'sonovel',t_ch,now))
        set_progress(100)
        conn.execute('UPDATE download_tasks SET status=?,dlid=?,progress=100,completed_at=? WHERE id=?',
          ('completed', dlid, now, task_id)); conn.commit(); conn.close()
        _notify_sse(user_id, {'type': 'download-complete', 'taskId': task_id, 'bookName': title, 'message': f'《{title}》下载完成'})

    except Exception as e:
        try: conn.execute('UPDATE download_tasks SET status=?,error_message=? WHERE id=?', ('failed',str(e),task_id)); conn.commit()
        except: pass
        finally:
            try: conn.close()
            except: pass
        _notify_sse(user_id, {'type': 'download-error', 'taskId': task_id, 'error': str(e)})


def _notify_sse(user_id, data):
    """通过SSE通知前端"""
    import json
    if user_id in _sse_clients:
        for q in _sse_clients[user_id]:
            q.put(data)


@download_bp.route('/api/download/tasks', methods=['GET'])
@require_auth
def list_tasks():
    """获取下载任务列表"""
    conn = get_db()
    tasks = conn.execute(
        '''SELECT * FROM download_tasks WHERE user_id = ?
           ORDER BY created_at DESC LIMIT 50''',
        (g.current_user['id'],)
    ).fetchall()
    conn.close()
    return json_response(data=[dict(t) for t in tasks])


@download_bp.route('/api/download/tasks/<int:task_id>', methods=['DELETE'])
@require_auth
def delete_task(task_id):
    """删除下载任务"""
    conn = get_db()
    conn.execute(
        'DELETE FROM download_tasks WHERE id = ? AND user_id = ?',
        (task_id, g.current_user['id'])
    )
    conn.commit()
    conn.close()
    return json_response(data={'message': '任务已删除'})


@download_bp.route('/api/download/progress', methods=['GET'])
@require_auth
def download_progress_sse():
    """SSE实时下载进度"""
    import json
    import queue

    user_id = g.current_user['id']

    def generate():
        q = queue.Queue()
        if user_id not in _sse_clients:
            _sse_clients[user_id] = []
        _sse_clients[user_id].append(q)

        try:
            # 发送初始连接确认
            yield f"data: {json.dumps({'type': 'connected', 'message': 'SSE连接已建立'})}\n\n"
            import time as t
            timeout = time.time() + 600  # 10分钟超时
            while time.time() < timeout:
                try:
                    msg = q.get(timeout=1)
                    yield f"data: {json.dumps(msg)}\n\n"
                    if msg.get('type') in ('download-complete', 'download-error'):
                        # 发送完完成/错误消息后短暂等待确保客户端收到
                        t.sleep(0.5)
                except queue.Empty:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
        except GeneratorExit:
            pass
        finally:
            if user_id in _sse_clients:
                try:
                    _sse_clients[user_id].remove(q)
                    if not _sse_clients[user_id]:
                        del _sse_clients[user_id]
                except:
                    pass

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )

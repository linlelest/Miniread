"""
Miniread (极读) - 管理员路由
"""
import time
from flask import Blueprint, request, g
from database import get_db, get_setting, set_setting
from utils.helpers import (
    json_response, require_admin, generate_invite_code,
    generate_token, get_client_ip
)

admin_bp = Blueprint('admin', __name__)


# ============ 用户管理 ============

@admin_bp.route('/api/admin/users', methods=['GET'])
@require_admin
def list_users():
    """获取所有用户"""
    conn = get_db()
    users = conn.execute(
        '''SELECT id, username, role, banned, banned_ip, ban_expires_at,
           deleted, delete_reason, deleted_at, created_at
           FROM users WHERE deleted = 0 ORDER BY created_at DESC'''
    ).fetchall()
    conn.close()
    return json_response(data=[dict(u) for u in users])


@admin_bp.route('/api/admin/users/ban', methods=['POST'])
@require_admin
def ban_user():
    """封禁/解封用户"""
    data = request.get_json()
    user_id = data.get('userId')
    action = data.get('action')  # 'ban' or 'unban'

    if not user_id or action not in ('ban', 'unban'):
        return json_response(code=400, message='参数错误')

    if int(user_id) == g.current_user['id']:
        return json_response(code=400, message='不能操作自己的账号')

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ? AND deleted = 0', (user_id,)).fetchone()
    if not user:
        conn.close()
        return json_response(code=404, message='用户不存在')

    now = time.time()
    if action == 'ban':
        ip = get_client_ip()
        # 如果是封禁用户，尝试获取该用户最后登录的IP
        user_ip = user['banned_ip'] or request.remote_addr
        ban_expires = now + 5 * 24 * 3600  # 5天

        conn.execute(
            'UPDATE users SET banned = 1, banned_at = ?, banned_ip = ?, ban_expires_at = ? WHERE id = ?',
            (now, user_ip, ban_expires, user_id)
        )
        # 删除该用户的所有session
        conn.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
        # 记录日志
        conn.execute(
            'INSERT INTO banned_log (username, reason, action) VALUES (?, ?, ?)',
            (user['username'], '管理员封禁', 'ban')
        )
        conn.commit()
        conn.close()
        return json_response(data={'message': f'已封禁用户 {user["username"]}'})

    elif action == 'unban':
        conn.execute(
            'UPDATE users SET banned = 0, banned_at = NULL, banned_ip = NULL, ban_expires_at = NULL WHERE id = ?',
            (user_id,)
        )
        conn.commit()
        conn.close()
        return json_response(data={'message': f'已解封用户 {user["username"]}'})


@admin_bp.route('/api/admin/users/delete', methods=['POST'])
@require_admin
def delete_user():
    """永久删除用户"""
    data = request.get_json()
    user_id = data.get('userId')
    reason = (data.get('reason') or '').strip()

    if not user_id:
        return json_response(code=400, message='缺少用户ID')
    if not reason:
        return json_response(code=400, message='请填写删除原因')

    if int(user_id) == g.current_user['id']:
        return json_response(code=400, message='不能删除自己的账号')

    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ? AND deleted = 0', (user_id,)).fetchone()
    if not user:
        conn.close()
        return json_response(code=404, message='用户不存在')
    if user['role'] == 'admin':
        conn.close()
        return json_response(code=400, message='不能删除管理员账号')

    now = time.time()
    conn.execute(
        'UPDATE users SET deleted = 1, delete_reason = ?, deleted_at = ? WHERE id = ?',
        (reason, now, user_id)
    )
    # 删除该用户的所有session
    conn.execute('DELETE FROM sessions WHERE user_id = ?', (user_id,))
    # 记录日志
    conn.execute(
        'INSERT INTO banned_log (username, reason, action) VALUES (?, ?, ?)',
        (user['username'], reason, 'delete')
    )
    conn.commit()
    conn.close()

    return json_response(data={'message': f'已删除用户 {user["username"]}'})


# ============ 公告管理 ============

@admin_bp.route('/api/admin/announcements', methods=['GET'])
@require_admin
def list_announcements():
    """获取所有公告"""
    conn = get_db()
    anns = conn.execute(
        'SELECT * FROM announcements ORDER BY sort_order, created_at DESC'
    ).fetchall()
    conn.close()
    return json_response(data=[dict(a) for a in anns])


@admin_bp.route('/api/admin/announcements', methods=['POST'])
@require_admin
def create_announcement():
    """创建公告"""
    data = request.get_json()
    content = (data.get('content') or '').strip()
    visibility = data.get('visibility', 'all')
    show_dismiss = 1 if data.get('showDismiss') else 0
    pinned = 1 if data.get('pinned') else 0
    active = 1 if data.get('active', True) else 0

    if not content:
        return json_response(code=400, message='请输入公告内容')

    conn = get_db()
    # 获取最大排序值
    max_order = conn.execute('SELECT MAX(sort_order) as m FROM announcements').fetchone()
    sort_order = (max_order['m'] or 0) + 1

    now = time.time()
    cursor = conn.execute(
        '''INSERT INTO announcements
           (content, visibility, show_dismiss, pinned, sort_order, active, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (content, visibility, show_dismiss, pinned, sort_order, active, now, now)
    )
    ann_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return json_response(data={'id': ann_id, 'message': '公告已创建'})


@admin_bp.route('/api/admin/announcements/<int:ann_id>', methods=['PUT'])
@require_admin
def update_announcement(ann_id):
    """更新公告"""
    data = request.get_json()
    conn = get_db()
    existing = conn.execute('SELECT * FROM announcements WHERE id = ?', (ann_id,)).fetchone()
    if not existing:
        conn.close()
        return json_response(code=404, message='公告不存在')

    content = data.get('content', existing['content'])
    visibility = data.get('visibility', existing['visibility'])
    show_dismiss = 1 if data.get('showDismiss') else 0
    pinned = 1 if data.get('pinned') else 0
    active = 1 if data.get('active', True) else 0

    conn.execute(
        '''UPDATE announcements SET content=?, visibility=?, show_dismiss=?,
           pinned=?, active=?, updated_at=? WHERE id=?''',
        (content, visibility, show_dismiss, pinned, active, time.time(), ann_id)
    )
    conn.commit()
    conn.close()
    return json_response(data={'message': '公告已更新'})


@admin_bp.route('/api/admin/announcements/<int:ann_id>', methods=['DELETE'])
@require_admin
def delete_announcement(ann_id):
    """删除公告"""
    conn = get_db()
    conn.execute('DELETE FROM announcements WHERE id = ?', (ann_id,))
    conn.commit()
    conn.close()
    return json_response(data={'message': '公告已删除'})


@admin_bp.route('/api/admin/announcements/reorder', methods=['PUT'])
@require_admin
def reorder_announcements():
    """拖动排序公告"""
    data = request.get_json()
    order = data.get('order', [])  # [id1, id2, id3, ...]

    conn = get_db()
    for i, ann_id in enumerate(order):
        conn.execute(
            'UPDATE announcements SET sort_order = ? WHERE id = ?',
            (i, ann_id)
        )
    conn.commit()
    conn.close()
    return json_response(data={'message': '排序已更新'})


# ============ 邀请码管理 ============

@admin_bp.route('/api/admin/invite-codes', methods=['GET'])
@require_admin
def list_invite_codes():
    """获取所有邀请码"""
    conn = get_db()
    codes = conn.execute(
        'SELECT * FROM invite_codes ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return json_response(data=[dict(c) for c in codes])


@admin_bp.route('/api/admin/invite-codes/generate', methods=['POST'])
@require_admin
def generate_codes():
    """批量生成邀请码"""
    data = request.get_json()
    count = int(data.get('count', 10))
    max_uses = int(data.get('maxUses', 1))
    expires_in_days = data.get('expiresInDays')  # None or number
    note = (data.get('note') or '').strip()

    if count < 1 or count > 1000:
        return json_response(code=400, message='数量范围: 1-1000')

    conn = get_db()
    now = time.time()
    expires_at = None
    if expires_in_days is not None and int(expires_in_days) > 0:
        expires_at = now + int(expires_in_days) * 24 * 3600

    generated = []
    for _ in range(count):
        code = generate_invite_code(8)
        # 确保唯一
        while conn.execute('SELECT id FROM invite_codes WHERE code = ?', (code,)).fetchone():
            code = generate_invite_code(8)
        conn.execute(
            """INSERT INTO invite_codes (code, max_uses, expires_at, note, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (code, max_uses, expires_at, note, now)
        )
        generated.append(code)

    conn.commit()
    conn.close()
    return json_response(data={'codes': generated, 'count': len(generated), 'message': f'已生成 {len(generated)} 个邀请码'})


@admin_bp.route('/api/admin/invite-codes/<int:code_id>', methods=['PUT'])
@require_admin
def update_invite_code(code_id):
    """更新邀请码"""
    data = request.get_json()
    conn = get_db()
    existing = conn.execute('SELECT * FROM invite_codes WHERE id = ?', (code_id,)).fetchone()
    if not existing:
        conn.close()
        return json_response(code=404, message='邀请码不存在')

    if 'maxUses' in data:
        conn.execute('UPDATE invite_codes SET max_uses = ? WHERE id = ?', (int(data['maxUses']), code_id))
    if 'note' in data:
        conn.execute('UPDATE invite_codes SET note = ? WHERE id = ?', (data['note'], code_id))
    if 'active' in data:
        conn.execute('UPDATE invite_codes SET active = ? WHERE id = ?', (1 if data['active'] else 0, code_id))
    if 'expiresInDays' in data:
        now = time.time()
        expires_at = now + int(data['expiresInDays']) * 24 * 3600 if int(data['expiresInDays']) > 0 else None
        conn.execute('UPDATE invite_codes SET expires_at = ? WHERE id = ?', (expires_at, code_id))

    conn.commit()
    conn.close()
    return json_response(data={'message': '更新成功'})


@admin_bp.route('/api/admin/invite-codes/<int:code_id>', methods=['DELETE'])
@require_admin
def delete_invite_code(code_id):
    """删除单个邀请码"""
    conn = get_db()
    conn.execute('DELETE FROM invite_codes WHERE id = ?', (code_id,))
    conn.commit()
    conn.close()
    return json_response(data={'message': '邀请码已删除'})


@admin_bp.route('/api/admin/invite-codes/batch-delete', methods=['POST'])
@require_admin
def batch_delete_codes():
    """批量删除邀请码"""
    data = request.get_json()
    ids = data.get('ids', [])
    if not ids:
        return json_response(code=400, message='请选择要删除的邀请码')

    conn = get_db()
    placeholders = ','.join('?' * len(ids))
    conn.execute(f'DELETE FROM invite_codes WHERE id IN ({placeholders})', ids)
    conn.commit()
    conn.close()
    return json_response(data={'message': f'已删除 {len(ids)} 个邀请码'})


@admin_bp.route('/api/admin/invite-codes/config', methods=['PUT'])
@require_admin
def config_invite():
    """配置邀请码系统"""
    data = request.get_json()
    enabled = '1' if data.get('enabled') else '0'
    prompt = data.get('prompt', '需要邀请码才能注册，请联系管理员获取')

    set_setting('invite_enabled', enabled)
    set_setting('invite_prompt', prompt)
    return json_response(data={'message': '配置已更新'})


# ============ 维护模式 ============

@admin_bp.route('/api/admin/maintenance', methods=['GET'])
@require_admin
def get_maintenance():
    """获取维护设置"""
    return json_response(data={
        'mode': get_setting('maintenance_mode') == '1',
        'content': get_setting('maintenance_content', ''),
    })


@admin_bp.route('/api/admin/maintenance', methods=['PUT'])
@require_admin
def set_maintenance():
    """设置维护模式"""
    data = request.get_json()
    mode = '1' if data.get('mode') else '0'
    content = data.get('content', '')

    set_setting('maintenance_mode', mode)
    set_setting('maintenance_content', content)
    return json_response(data={'message': '维护设置已更新'})


# ============ 更新检查 ============

@admin_bp.route('/api/admin/update/check', methods=['GET'])
@require_admin
def check_update():
    """检查更新"""
    import requests
    current_version = get_setting('version', '1.0.0')

    try:
        resp = requests.get(
            'https://api.github.com/repos/linlelest/Miniread/releases/latest',
            headers={'Accept': 'application/vnd.github.v3+json'},
            timeout=10
        )
        if resp.status_code == 200:
            release = resp.json()
            latest_tag = release.get('tag_name', 'v0.0.0').lstrip('v')
            has_update = _compare_versions(latest_tag, current_version) > 0
            return json_response(data={
                'currentVersion': current_version,
                'latestVersion': latest_tag,
                'hasUpdate': has_update,
                'url': release.get('html_url', ''),
                'body': release.get('body', ''),
            })
        else:
            return json_response(data={
                'currentVersion': current_version,
                'hasUpdate': False,
                'message': '无法获取最新版本信息'
            })
    except Exception as e:
        return json_response(code=500, message=f'检查更新失败: {str(e)}')


@admin_bp.route('/api/admin/update/apply', methods=['POST'])
@require_admin
def apply_update():
    """应用更新"""
    import requests
    import zipfile
    import shutil
    import sys
    import subprocess

    try:
        resp = requests.get(
            'https://api.github.com/repos/linlelest/Miniread/releases/latest',
            headers={'Accept': 'application/vnd.github.v3+json'},
            timeout=10
        )
        release = resp.json()
        latest_tag = release.get('tag_name', '')

        # 查找zip资产
        assets = release.get('assets', [])
        download_url = None
        for asset in assets:
            if asset.get('name', '').endswith('.zip'):
                download_url = asset.get('browser_download_url')
                break

        if not download_url:
            return json_response(code=400, message='未找到可下载的更新包')

        # 设置更新状态
        set_setting('updating', '1')
        set_setting('update_progress', '0')
        set_setting('update_message', '正在下载更新包...')

        # 下载更新包
        update_resp = requests.get(download_url, stream=True, timeout=300)
        set_setting('update_progress', '20')
        set_setting('update_message', '下载完成，正在解压...')

        # 保存到临时目录
        import tempfile
        tmp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(tmp_dir, 'update.zip')
        with open(zip_path, 'wb') as f:
            for chunk in update_resp.iter_content(chunk_size=8192):
                f.write(chunk)

        set_setting('update_progress', '50')
        set_setting('update_message', '正在解压更新包...')

        # 解压
        extract_dir = os.path.join(tmp_dir, 'extracted')
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)

        set_setting('update_progress', '70')
        set_setting('update_message', '正在替换文件...')

        # 替换文件
        import shutil
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for item in os.listdir(extract_dir):
            src = os.path.join(extract_dir, item)
            dst = os.path.join(base_dir, item)
            if item == 'uploads' or item == 'downloads' or item == 'data':
                continue  # 不覆盖用户数据和上传文件
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        # 更新版本号
        set_setting('version', latest_tag.lstrip('v'))

        set_setting('update_progress', '90')
        set_setting('update_message', '正在重启服务...')

        # 清理临时文件
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

        set_setting('update_progress', '100')
        set_setting('update_message', '更新完成，服务即将重启')
        set_setting('updating', '0')

        # 重启服务
        def restart_server():
            import subprocess, sys, time
            time.sleep(2)
            subprocess.Popen([sys.executable] + sys.argv)
            sys.exit(0)

        import threading
        threading.Thread(target=restart_server, daemon=True).start()

        return json_response(data={'success': True, 'message': '更新已执行，服务重启中...'})

    except Exception as e:
        set_setting('updating', '0')
        set_setting('update_progress', '0')
        return json_response(code=500, message=f'更新失败: {str(e)}')


# ============ 公开日志 ============

@admin_bp.route('/api/admin/banned-log', methods=['GET'])
@require_admin
def get_banned_log():
    """获取封禁/删除日志（管理员完整视图）"""
    conn = get_db()
    logs = conn.execute(
        'SELECT * FROM banned_log ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return json_response(data=[dict(l) for l in logs])


# ============ 辅助 ============

def _compare_versions(v1, v2):
    """比较版本号，返回 1(v1>v2), -1, 0"""
    try:
        parts1 = [int(x) for x in v1.split('.')]
        parts2 = [int(x) for x in v2.split('.')]
        max_len = max(len(parts1), len(parts2))
        parts1.extend([0] * (max_len - len(parts1)))
        parts2.extend([0] * (max_len - len(parts2)))
        for a, b in zip(parts1, parts2):
            if a > b:
                return 1
            if a < b:
                return -1
        return 0
    except:
        return 0


import os  # Enabling import for apply_update


# ============ 数据导出 ============

@admin_bp.route('/api/admin/export', methods=['GET'])
@require_admin
def export_data():
    """导出全部数据为JSON"""
    import json, time
    conn = get_db()
    tables = ['users', 'sessions', 'books', 'bookmarks', 'highlights',
              'reading_settings', 'announcements', 'banned_log',
              'invite_codes', 'settings', 'download_tasks', 'novel_server_config']

    data = {'version': Config.VERSION, 'exported_at': time.time(), 'tables': {}}
    for table in tables:
        try:
            rows = conn.execute(f'SELECT * FROM {table}').fetchall()
            data['tables'][table] = [dict(r) for r in rows]
        except:
            data['tables'][table] = []
    conn.close()

    resp = json_response(data=data)
    from flask import Response
    json_str = json.dumps({'code': 200, 'data': data}, ensure_ascii=False, default=str)
    return Response(json_str, mimetype='application/json',
                    headers={'Content-Disposition': f'attachment; filename=miniread_backup_{int(time.time())}.json'})


@admin_bp.route('/api/admin/import', methods=['POST'])
@require_admin
def import_data():
    """导入JSON数据（管理员用）"""
    import json, time
    data = request.get_json()
    if not data or 'tables' not in data:
        return json_response(code=400, message='无效的备份文件')

    conn = get_db()
    tables = data['tables']
    for table_name, rows in tables.items():
        if not rows:
            continue
        try:
            # Clear existing data
            conn.execute(f'DELETE FROM {table_name}')
            for row in rows:
                cols = ', '.join(row.keys())
                vals = ', '.join('?' * len(row))
                conn.execute(f'INSERT INTO {table_name} ({cols}) VALUES ({vals})',
                             list(row.values()))
        except Exception as e:
            pass  # Best effort
    conn.commit()
    conn.close()
    return json_response(data={'message': f'已导入 {sum(len(v) for v in tables.values())} 条记录'})


"""
Miniread (极读) - 管理员路由
"""
import time
import os
from flask import Blueprint, request, g
from config import Config
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
    title = (data.get('title') or '').strip()
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
           (title, content, visibility, show_dismiss, pinned, sort_order, active, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (title, content, visibility, show_dismiss, pinned, sort_order, active, now, now)
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
    title = data.get('title', existing['title'])
    visibility = data.get('visibility', existing['visibility'])
    show_dismiss = 1 if data.get('showDismiss') else 0
    pinned = 1 if data.get('pinned') else 0
    active = 1 if data.get('active', True) else 0

    conn.execute(
        '''UPDATE announcements SET title=?, content=?, visibility=?, show_dismiss=?,
           pinned=?, active=?, updated_at=? WHERE id=?''',
        (title, content, visibility, show_dismiss, pinned, active, time.time(), ann_id)
    )
    conn.commit()
    conn.close()
    _cleanup_ann_media()
    return json_response(data={'message': '公告已更新'})


@admin_bp.route('/api/admin/announcements/<int:ann_id>', methods=['DELETE'])
@require_admin
def delete_announcement(ann_id):
    """删除公告"""
    conn = get_db()
    conn.execute('DELETE FROM announcements WHERE id = ?', (ann_id,))
    conn.commit()
    conn.close()
    _cleanup_ann_media()
    return json_response(data={'message': '公告已删除'})


ANN_MEDIA_DIR = os.path.join(Config.DATA_DIR, 'ann_media')
import re as _re_ann

_ANN_MEDIA_RE = _re_ann.compile(r'/api/public/ann-media/([A-Za-z0-9_.\-]+)')


def _ann_media_refs(content):
    return set(_ANN_MEDIA_RE.findall(content or ''))


def _cleanup_ann_media():
    """删除不再被任何公告引用的媒体文件"""
    if not os.path.isdir(ANN_MEDIA_DIR):
        return
    conn = get_db()
    refs = set()
    try:
        for (content,) in conn.execute('SELECT content FROM announcements'):
            refs |= _ann_media_refs(content)
    finally:
        conn.close()
    for fn in os.listdir(ANN_MEDIA_DIR):
        if fn not in refs:
            try:
                os.remove(os.path.join(ANN_MEDIA_DIR, fn))
            except OSError:
                pass


_ANN_IMG_EXT = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp'}
_ANN_VID_EXT = {'mp4', 'webm', 'mov', 'mkv', 'avi', 'm4v'}


@admin_bp.route('/api/admin/announcements/upload', methods=['POST'])
@require_admin
def upload_ann_media():
    """上传公告图片/视频：图片尽量转 WebP，视频尽量转 H.264 mp4"""
    import io
    import shutil
    import subprocess
    import uuid

    f = request.files.get('file')
    kind = request.form.get('kind') or 'image'
    if not f or not f.filename:
        return json_response(code=400, message='请选择文件')
    ext = (f.filename.rsplit('.', 1)[-1] or '').lower()
    os.makedirs(ANN_MEDIA_DIR, exist_ok=True)

    if kind == 'image':
        if ext not in _ANN_IMG_EXT:
            return json_response(code=400, message='不支持的图片格式')
        data = f.read()
        out_name = 'img_%s.webp' % uuid.uuid4().hex[:12]
        out_path = os.path.join(ANN_MEDIA_DIR, out_name)
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(data))
            if im.mode in ('RGBA', 'P'):
                im = im.convert('RGBA')
            else:
                im = im.convert('RGB')
            if im.width > 1600:
                h = round(im.height * 1600 / im.width)
                im = im.resize((1600, h), Image.LANCZOS)
            im.save(out_path, 'WEBP', quality=85, method=4)
        except Exception:
            out_name = 'img_%s.%s' % (uuid.uuid4().hex[:12], ext if ext != 'jpeg' else 'jpg')
            out_path = os.path.join(ANN_MEDIA_DIR, out_name)
            with open(out_path, 'wb') as fh:
                fh.write(data)
        return json_response(data={'url': '/api/public/ann-media/' + out_name, 'kind': 'image'})

    if kind == 'video':
        if ext not in _ANN_VID_EXT:
            return json_response(code=400, message='不支持的视频格式')
        base = 'vid_%s' % uuid.uuid4().hex[:12]
        src_path = os.path.join(ANN_MEDIA_DIR, base + '.' + ext)
        f.save(src_path)
        out_path = os.path.join(ANN_MEDIA_DIR, base + '.mp4')
        ffmpeg = shutil.which('ffmpeg')
        converted = False
        if ffmpeg and ext != 'mp4':
            try:
                subprocess.run(
                    [ffmpeg, '-y', '-i', src_path, '-c:v', 'libx264', '-preset', 'fast',
                     '-crf', '26', '-c:a', 'aac', '-movflags', '+faststart', out_path],
                    capture_output=True, timeout=600,
                    creationflags=(0x08000000 if os.name == 'nt' else 0))
                converted = os.path.exists(out_path) and os.path.getsize(out_path) > 0
            except Exception:
                converted = False
        if converted:
            try:
                os.remove(src_path)
            except OSError:
                pass
            return json_response(data={'url': '/api/public/ann-media/' + base + '.mp4', 'kind': 'video'})
        return json_response(data={'url': '/api/public/ann-media/' + base + '.' + ext, 'kind': 'video', 'converted': False})

    return json_response(code=400, message='kind 必须为 image 或 video')


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
            latest_tag = release.get('tag_name', 'v0.0.0').lstrip('vV')
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
        # 注意：sys.exit() 在请求线程中只会终止线程，waitress 主进程不会退出，
        # 导致新进程端口被占而启动失败、服务器永远运行旧代码。
        # 正确做法：先安排一个延迟启动新进程的壳（Windows/无守护场景），
        # 再用 os._exit 强制结束当前进程；有 systemd 时由 Restart=always 拉起。
        def restart_server():
            import subprocess, sys, time, os as _os
            time.sleep(2)
            if _os.name == 'nt':
                # Windows：用 cmd 延迟 2 秒后启动新实例（此时旧进程已退出，端口已释放）
                subprocess.Popen(
                    ['cmd', '/c', 'timeout /t 2 /nobreak >nul & start "" "%s" run.py' % sys.executable],
                    cwd=base_dir,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
            elif _os.path.exists('/run/systemd/system') and subprocess.call(
                ['systemctl', 'is-active', '--quiet', 'miniread']
            ) == 0:
                # Linux systemd 托管：直接退出，由 Restart=always 拉起
                pass
            else:
                # 无守护进程托管：自行拉起新实例后退出
                subprocess.Popen([sys.executable, 'run.py'], cwd=base_dir)
            _os._exit(0)

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
    """比较版本号（兼容 V2.0 / v2.0.1 / 2.0 格式），返回 1(v1>v2), -1, 0"""

    def parse(v):
        v = str(v).strip().lstrip('vV')
        parts = []
        for seg in v.split('.'):
            num = ''
            for ch in seg:
                if ch.isdigit():
                    num += ch
                else:
                    break
            parts.append(int(num) if num else 0)
        return parts

    try:
        p1, p2 = parse(v1), parse(v2)
        n = max(len(p1), len(p2))
        p1 += [0] * (n - len(p1))
        p2 += [0] * (n - len(p2))
        for a, b in zip(p1, p2):
            if a > b:
                return 1
            if a < b:
                return -1
        return 0
    except Exception:
        return 0


import os  # Enabling import for apply_update


# ============ 数据导出 ============

@admin_bp.route('/api/admin/export', methods=['GET'])
@require_admin
def export_data():
    """导出全部数据为ZIP（数据库 + 密钥 + 全部书籍 + 规范书存储）"""
    import io
    import json
    import time
    import zipfile
    from flask import send_file

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        try:
            conn = get_db()
            conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            conn.close()
        except Exception:
            pass
        if os.path.exists(Config.DATABASE_PATH):
            zf.write(Config.DATABASE_PATH, 'db/miniread.db')
        sk = os.path.join(Config.DATA_DIR, 'secret_key')
        if os.path.exists(sk):
            zf.write(sk, 'db/secret_key')

        def add_tree(base, prefix):
            if not os.path.isdir(base):
                return 0
            count = 0
            for root, _dirs, files in os.walk(base):
                for name in files:
                    fp = os.path.join(root, name)
                    arc = prefix + os.path.relpath(fp, base).replace('\\', '/')
                    zf.write(fp, arc)
                    count += 1
            return count

        add_tree(Config.UPLOAD_FOLDER, 'uploads/')
        add_tree(Config.CANONICAL_DIR, 'canonical/')
        zf.writestr('meta.json', json.dumps(
            {'version': Config.VERSION, 'exported_at': time.time()},
            ensure_ascii=False))

    buf.seek(0)
    return send_file(
        buf, mimetype='application/zip', as_attachment=True,
        download_name='miniread_backup_%s.zip' % time.strftime('%Y%m%d_%H%M%S'))


@admin_bp.route('/api/admin/import', methods=['POST'])
@require_admin
def import_data():
    """导入备份：支持ZIP全量恢复（新）与JSON表数据（旧）"""
    import io
    import json
    import shutil
    import tempfile
    import zipfile

    f = request.files.get('file')
    if not f or not f.filename:
        data = request.get_json(silent=True)
        if not data:
            return json_response(code=400, message='请选择备份文件')
        raw = json.dumps(data).encode('utf-8')
    else:
        raw = f.read()
    if not raw:
        return json_response(code=400, message='备份文件为空')

    # ---------- ZIP 全量恢复 ----------
    if raw[:2] == b'PK':
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile:
            return json_response(code=400, message='备份文件损坏')
        names = zf.namelist()
        if 'db/miniread.db' not in names:
            return json_response(code=400, message='备份缺少数据库文件')
        for n in names:
            if n.startswith('/') or '..' in n.replace('\\', '/'):
                return json_response(code=400, message='备份包含不安全路径')

        tmp = tempfile.mkdtemp()
        try:
            zf.extractall(tmp)
            db_src = os.path.join(tmp, 'db', 'miniread.db')
            for suffix in ('', '-wal', '-shm'):
                try:
                    os.remove(Config.DATABASE_PATH + suffix)
                except OSError:
                    pass
            shutil.copy2(db_src, Config.DATABASE_PATH)

            sk_src = os.path.join(tmp, 'db', 'secret_key')
            if os.path.exists(sk_src):
                os.makedirs(Config.DATA_DIR, exist_ok=True)
                sk_dst = os.path.join(Config.DATA_DIR, 'secret_key')
                shutil.copy2(sk_src, sk_dst)
                with open(sk_dst, 'r', encoding='utf-8') as fh:
                    new_key = fh.read().strip()
                if new_key:
                    Config.SECRET_KEY = new_key
                    from flask import current_app
                    current_app.config['SECRET_KEY'] = new_key

            up_src = os.path.join(tmp, 'uploads')
            if os.path.isdir(up_src):
                shutil.rmtree(Config.UPLOAD_FOLDER, ignore_errors=True)
                os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
                shutil.copytree(up_src, Config.UPLOAD_FOLDER, dirs_exist_ok=True)

            cn_src = os.path.join(tmp, 'canonical')
            if os.path.isdir(cn_src):
                shutil.rmtree(Config.CANONICAL_DIR, ignore_errors=True)
                os.makedirs(Config.CANONICAL_DIR, exist_ok=True)
                shutil.copytree(cn_src, Config.CANONICAL_DIR, dirs_exist_ok=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        return json_response(data={'message': '备份已恢复：书籍、设置与数据已还原（会话可能需要重新登录）'})

    # ---------- JSON 表数据（旧格式兼容） ----------
    try:
        obj = json.loads(raw.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return json_response(code=400, message='无效的备份文件')
    if isinstance(obj, dict) and isinstance(obj.get('data'), dict):
        obj = obj['data']
    if not isinstance(obj, dict) or 'tables' not in obj:
        return json_response(code=400, message='无效的备份文件')

    conn = get_db()
    tables = obj['tables']
    allowed_tables = {
        'users', 'books', 'bookmarks', 'highlights', 'reading_settings',
        'announcements', 'invite_codes', 'settings', 'novel_server_config',
        'user_prefs', 'banned_log',
    }
    imported = 0
    for table_name, rows in tables.items():
        if table_name in ('sessions', 'download_tasks'):
            continue
        if table_name not in allowed_tables or not isinstance(rows, list) or not rows:
            continue
        try:
            conn.execute('DELETE FROM ' + table_name)
            for row in rows:
                safe_cols = [c for c in row.keys() if c.isidentifier()]
                if not safe_cols:
                    continue
                cols = ', '.join(safe_cols)
                vals = ', '.join('?' * len(safe_cols))
                conn.execute('INSERT INTO ' + table_name + ' (' + cols + ') VALUES (' + vals + ')',
                             [row[c] for c in safe_cols])
                imported += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return json_response(data={'message': f'已导入 {imported} 条记录'})


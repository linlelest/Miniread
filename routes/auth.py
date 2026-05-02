"""
Miniread (极读) - 用户认证路由
"""
import time
from flask import Blueprint, request, g
from database import get_db
from utils.helpers import (
    hash_password, check_password, generate_token,
    json_response, require_auth, get_current_user,
    check_ip_banned, get_client_ip
)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/auth/check-admin', methods=['GET'])
def check_admin():
    """检查管理员是否存在"""
    conn = get_db()
    row = conn.execute(
        'SELECT COUNT(*) as cnt FROM users WHERE role = ? AND deleted = 0', ('admin',)
    ).fetchone()
    conn.close()
    return json_response(data={'hasAdmin': row['cnt'] > 0})


@auth_bp.route('/api/auth/admin-register', methods=['POST'])
def admin_register():
    """管理员首次注册"""
    # 检查是否已有管理员
    conn = get_db()
    existing = conn.execute(
        'SELECT COUNT(*) as cnt FROM users WHERE role = ? AND deleted = 0', ('admin',)
    ).fetchone()
    if existing['cnt'] > 0:
        conn.close()
        return json_response(code=400, message='管理员已存在，不可重复注册')

    data = request.get_json()
    if not data:
        return json_response(code=400, message='请提供注册信息')

    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()

    if len(username) < 4:
        conn.close()
        return json_response(code=400, message='用户名至少4个字符')
    if len(password) < 4:
        conn.close()
        return json_response(code=400, message='密码至少4个字符')

    # 检查用户名是否被占用
    existing_user = conn.execute(
        'SELECT id FROM users WHERE username = ?', (username,)
    ).fetchone()
    if existing_user:
        conn.close()
        return json_response(code=409, message='用户名已存在')

    password_hash = hash_password(password)
    now = time.time()

    cursor = conn.execute(
        'INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)',
        (username, password_hash, 'admin', now)
    )
    user_id = cursor.lastrowid

    # 创建Session
    session_token = generate_token()
    expires = now + 30 * 24 * 3600  # 30天
    conn.execute(
        'INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)',
        (user_id, session_token, expires)
    )
    conn.commit()
    conn.close()

    resp = json_response(data={
        'sessionId': session_token,
        'username': username,
        'role': 'admin',
        'message': '管理员注册成功'
    })
    resp.set_cookie(
        'miniread_session', session_token,
        max_age=30 * 24 * 3600,
        path='/',
        httponly=True,
        samesite='Lax'
    )
    return resp


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()
    if not data:
        return json_response(code=400, message='请提供登录信息')

    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    remember = data.get('remember', False)

    if not username or not password:
        return json_response(code=400, message='用户名和密码不能为空')

    # 检查IP是否被封禁
    ip = get_client_ip()
    if check_ip_banned(ip):
        return json_response(code=403, message='您的IP已被临时封禁，请稍后再试')

    conn = get_db()
    user = conn.execute(
        'SELECT * FROM users WHERE username = ? AND deleted = 0', (username,)
    ).fetchone()

    if not user:
        conn.close()
        return json_response(code=401, message='用户名或密码错误')

    user_dict = dict(user)

    if user_dict['banned']:
        conn.close()
        return json_response(code=403, message='账号已被封禁')

    if not check_password(password, user_dict['password_hash']):
        conn.close()
        return json_response(code=401, message='用户名或密码错误')

    # 创建Session
    session_token = generate_token()
    now = time.time()
    if remember:
        expires = now + 30 * 24 * 3600  # 30天
    else:
        expires = now + 24 * 3600  # 1天

    conn.execute(
        'INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)',
        (user_dict['id'], session_token, expires)
    )
    conn.commit()
    conn.close()

    resp = json_response(data={
        'sessionId': session_token,
        'username': user_dict['username'],
        'role': user_dict['role']
    })
    resp.set_cookie(
        'miniread_session', session_token,
        max_age=int(expires - now),
        path='/',
        httponly=True,
        samesite='Lax'
    )
    return resp


@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.get_json()
    if not data:
        return json_response(code=400, message='请提供注册信息')

    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    invite_code = (data.get('inviteCode') or '').strip()

    if len(username) < 4:
        return json_response(code=400, message='用户名至少4个字符')
    if len(password) < 4:
        return json_response(code=400, message='密码至少4个字符')

    # 检查IP是否被封禁
    ip = get_client_ip()
    if check_ip_banned(ip):
        return json_response(code=403, message='您的IP已被临时封禁，请5天后再试')

    conn = get_db()

    # 检查邀请码系统是否开启
    invite_enabled = conn.execute(
        'SELECT value FROM settings WHERE key = ?', ('invite_enabled',)
    ).fetchone()

    if invite_enabled and invite_enabled['value'] == '1':
        if not invite_code:
            conn.close()
            return json_response(code=400, message='需要邀请码才能注册')

        # 验证邀请码
        now = time.time()
        inv = conn.execute(
            '''SELECT * FROM invite_codes
               WHERE code = ? AND active = 1
               AND (max_uses = 0 OR used_count < max_uses)
               AND (expires_at IS NULL OR expires_at > ?)''',
            (invite_code, now)
        ).fetchone()

        if not inv:
            conn.close()
            return json_response(code=400, message='邀请码无效或已过期')

        # 消耗邀请码
        conn.execute(
            'UPDATE invite_codes SET used_count = used_count + 1 WHERE id = ?',
            (inv['id'],)
        )

    # 检查用户名是否已存在
    existing = conn.execute(
        'SELECT id FROM users WHERE username = ?', (username,)
    ).fetchone()
    if existing:
        conn.close()
        return json_response(code=409, message='用户名已存在')

    password_hash = hash_password(password)
    now = time.time()
    conn.execute(
        'INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)',
        (username, password_hash, 'user', now)
    )
    conn.commit()
    conn.close()

    return json_response(data={'message': '注册成功'})


@auth_bp.route('/api/auth/check', methods=['GET'])
def check_auth():
    """检查登录状态"""
    user = get_current_user()
    if user:
        return json_response(data={
            'authenticated': True,
            'username': user['username'],
            'role': user['role'],
            'userId': user['id']
        })
    return json_response(data={'authenticated': False})


@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    """登出"""
    session_token = request.cookies.get('miniread_session')
    if session_token:
        conn = get_db()
        conn.execute('DELETE FROM sessions WHERE token = ?', (session_token,))
        conn.commit()
        conn.close()

    resp = json_response(data={'message': '已登出'})
    resp.delete_cookie('miniread_session')
    return resp


@auth_bp.route('/api/auth/change-password', methods=['POST'])
@require_auth
def change_password():
    """修改密码"""
    data = request.get_json()
    old_password = (data.get('oldPassword') or '').strip()
    new_password = (data.get('newPassword') or '').strip()

    if not old_password or not new_password:
        return json_response(code=400, message='请提供新旧密码')
    if len(new_password) < 4:
        return json_response(code=400, message='新密码至少4个字符')

    user = g.current_user
    if not check_password(old_password, user['password_hash']):
        return json_response(code=400, message='原密码错误')

    new_hash = hash_password(new_password)
    conn = get_db()
    conn.execute(
        'UPDATE users SET password_hash = ? WHERE id = ?',
        (new_hash, user['id'])
    )
    conn.commit()
    conn.close()

    return json_response(data={'message': '密码修改成功'})


@auth_bp.route('/api/auth/change-username', methods=['POST'])
@require_auth
def change_username():
    """修改用户名（普通用户）"""
    data = request.get_json()
    new_username = (data.get('username') or '').strip()

    if len(new_username) < 4:
        return json_response(code=400, message='用户名至少4个字符')

    conn = get_db()
    existing = conn.execute(
        'SELECT id FROM users WHERE username = ? AND id != ?',
        (new_username, g.current_user['id'])
    ).fetchone()
    if existing:
        conn.close()
        return json_response(code=409, message='用户名已被占用')

    conn.execute(
        'UPDATE users SET username = ? WHERE id = ?',
        (new_username, g.current_user['id'])
    )
    conn.commit()
    conn.close()

    return json_response(data={'username': new_username, 'message': '用户名修改成功'})

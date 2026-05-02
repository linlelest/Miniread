"""
Miniread (极读) - 工具函数
"""
import hashlib
import os
import uuid
import re
import bcrypt
from functools import wraps
from flask import request, jsonify, g
from database import get_db


def hash_password(password):
    """密码哈希"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def check_password(password, hashed):
    """验证密码"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def generate_token():
    """生成64位随机token"""
    return hashlib.sha256(os.urandom(64)).hexdigest()


def generate_invite_code(length=8):
    """生成邀请码"""
    return uuid.uuid4().hex[:length].upper()


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    from config import Config
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in Config.ALLOWED_EXTENSIONS


def get_file_extension(filename):
    """获取文件扩展名（小写）"""
    if '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[1].lower()


def safe_filename(filename):
    """生成安全的文件名"""
    # 移除路径分隔符
    filename = os.path.basename(filename)
    # 替换非法字符
    name, ext = os.path.splitext(filename)
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    return name + ext


def format_file_size(size_bytes):
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def clean_html_text(text):
    """清理HTML文本"""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&quot;', '"', text)
    return text


def detect_chapters_txt(content, max_chapters=5000):
    """
    从TXT文本中检测章节
    支持常见章节标题格式：
    - 第X章/节/卷/部/篇
    - Chapter X
    - 序章/楔子/尾声/后记/番外
    """
    patterns = [
        r'(?:^|\n)\s*(第[0-9零一二三四五六七八九十百千万]+[章节卷部篇集回].*)',
        r'(?:^|\n)\s*(Chapter\s+\d+.*)',
        r'(?:^|\n)\s*(序章|楔子|尾声|后记|番外.*|引子|终章|结局)',
        r'(?:^|\n)\s*(第[0-9零一二三四五六七八九十百千万]+\s*(?:卷|部|篇|集|回).*)',
        r'(?:^|\n)\s*(VOL\.?\s*\d+.*)',
        r'(?:^|\n)\s*(Part\s+\d+.*)',
        r'(?:^|\n)\s*(§+\s+.*)',
    ]

    chapters = []
    seen_positions = set()

    for pattern in patterns:
        for match in re.finditer(pattern, content, re.IGNORECASE):
            pos = match.start()
            line = match.group(1).strip()
            # 过滤过长的行（可能是误匹配）
            if len(line) > 100:
                continue
            # 避免重复
            if pos not in seen_positions:
                seen_positions.add(pos)
                chapters.append({
                    'title': line,
                    'position': pos,
                    'index': 0  # 稍后排序赋值
                })
            if len(chapters) >= max_chapters:
                break
        if len(chapters) >= max_chapters:
            break

    # 按位置排序
    chapters.sort(key=lambda x: x['position'])

    # 分配索引
    for i, ch in enumerate(chapters):
        ch['index'] = i

    return chapters


def json_response(data=None, code=200, message='OK'):
    """统一JSON响应格式 - 返回Response对象（支持set_cookie）"""
    resp = {'code': code, 'message': message, 'data': data}
    response = jsonify(resp)
    response.status_code = code
    return response


def require_auth(f):
    """认证装饰器 - 需要登录"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return json_response(code=401, message='未登录或会话已过期')
        if user['banned']:
            return json_response(code=403, message='账号已被封禁')
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """管理员认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            return json_response(code=401, message='未登录或会话已过期')
        if user['banned']:
            return json_response(code=403, message='账号已被封禁')
        if user['role'] != 'admin':
            return json_response(code=403, message='需要管理员权限')
        g.current_user = user
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    """从请求中获取当前用户"""
    # 首先检查Session Cookie
    session_token = request.cookies.get('miniread_session')
    if session_token:
        conn = get_db()
        row = conn.execute('''
            SELECT u.* FROM users u
            JOIN sessions s ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > strftime('%s', 'now')
            AND u.deleted = 0
        ''', (session_token,)).fetchone()
        conn.close()
        if row:
            return dict(row)

    # 其次检查Authorization Bearer Token
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        conn = get_db()
        row = conn.execute('''
            SELECT u.* FROM users u
            JOIN sessions s ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > strftime('%s', 'now')
            AND u.deleted = 0
        ''', (token,)).fetchone()
        conn.close()
        if row:
            return dict(row)

    return None


def check_ip_banned(ip):
    """检查IP是否被封禁"""
    conn = get_db()
    now = __import__('time').time()
    row = conn.execute('''
        SELECT id FROM users
        WHERE banned_ip = ? AND ban_expires_at > ?
        AND banned = 1 AND deleted = 0
        LIMIT 1
    ''', (ip, now)).fetchone()
    conn.close()
    return row is not None


def get_client_ip():
    """获取客户端IP"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    if request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP').strip()
    return request.remote_addr

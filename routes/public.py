"""
Miniread (极读) - 公开路由
无需认证即可访问的接口
"""
from flask import Blueprint, request
from database import get_db, get_setting
from utils.helpers import json_response

public_bp = Blueprint('public', __name__)


@public_bp.route('/api/public/announcements', methods=['GET'])
def get_announcements():
    """获取公开公告"""
    conn = get_db()
    anns = conn.execute(
        '''SELECT id, title, content, visibility, show_dismiss, pinned, sort_order, updated_at, created_at
           FROM announcements
           WHERE active = 1
           ORDER BY pinned DESC, sort_order, created_at DESC'''
    ).fetchall()
    conn.close()
    return json_response(data=[dict(a) for a in anns])


@public_bp.route('/api/public/banned-log', methods=['GET'])
def get_banned_log():
    """获取公开的封禁/删除记录"""
    conn = get_db()
    limit = request.args.get('limit', 5, type=int)
    logs = conn.execute(
        'SELECT username, reason, action, created_at FROM banned_log ORDER BY created_at DESC LIMIT ?',
        (limit,)
    ).fetchall()
    conn.close()
    return json_response(data=[dict(l) for l in logs])


@public_bp.route('/api/public/maintenance', methods=['GET'])
def check_maintenance():
    """检查维护状态"""
    mode = get_setting('maintenance_mode', '0') == '1'
    content = get_setting('maintenance_content', '')
    return json_response(data={
        'maintenance': mode,
        'content': content
    })


@public_bp.route('/api/public/update-status', methods=['GET'])
def update_status():
    """获取更新状态"""
    updating = get_setting('updating', '0') == '1'
    progress = int(get_setting('update_progress', '0'))
    message = get_setting('update_message', '')
    return json_response(data={
        'updating': updating,
        'progress': progress,
        'message': message
    })


@public_bp.route('/api/public/invite-status', methods=['GET'])
def invite_status():
    """检查邀请码系统状态"""
    enabled = get_setting('invite_enabled', '0') == '1'
    prompt = get_setting('invite_prompt', '')
    return json_response(data={
        'enabled': enabled,
        'prompt': prompt
    })

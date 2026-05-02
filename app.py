"""
Miniread (极读) - 主应用入口 · 在线阅读管理平台
"""
import os
from flask import Flask, request, jsonify, render_template, redirect, g
from flask_cors import CORS
from config import Config
from database import init_db, get_setting, get_db


def create_app():
    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(Config)
    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(Config.DOWNLOAD_FOLDER, exist_ok=True)
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    init_db()
    CORS(app, supports_credentials=True)

    @app.before_request
    def global_middleware():
        path = request.path

        # === 更新期间 ===
        if get_setting('updating', '0') == '1':
            allowed = ['/upgrade', '/api/public/update-status', '/api/auth/check',
                       '/api/auth/logout', '/api/admin/', '/login', '/api/auth/login', '/static/']
            if not any(path.startswith(p) for p in allowed):
                from utils.helpers import get_current_user
                user = get_current_user()
                if not user or user['role'] != 'admin':
                    if path.startswith('/api/'):
                        r = jsonify({'code': 501, 'message': '网站升级中', 'data': None}); r.status_code = 503; return r
                    return redirect('/upgrade')
            return

        # === 维护模式 ===
        if get_setting('maintenance_mode', '0') == '1':
            from utils.helpers import get_current_user
            user = get_current_user()
            if user and user['role'] == 'admin':
                return  # 管理员通行
            # 非管理员全部拦截
            allowed = ['/maintenance', '/api/public/maintenance', '/api/auth/check',
                       '/api/auth/logout', '/api/auth/login', '/static/']
            if not any(path.startswith(p) for p in allowed):
                if path.startswith('/api/'):
                    r = jsonify({'code': 501, 'message': '网站维护中', 'data': None}); r.status_code = 503; return r
                return redirect('/maintenance')

        # === 首次使用：强制管理员注册 ===
        if not path.startswith('/api/') and not path.startswith('/static/') and path != '/favicon.ico':
            conn = get_db()
            has_admin = conn.execute(
                "SELECT COUNT(*) as cnt FROM users WHERE role='admin' AND deleted=0"
            ).fetchone()['cnt'] > 0
            conn.close()
            if not has_admin and path not in ('/login', '/', '/sonovelwebguide', '/sonovel教程1.png'):
                return redirect('/login')

    # 注册蓝图
    from routes.auth import auth_bp
    from routes.books import books_bp
    from routes.download import download_bp
    from routes.admin import admin_bp
    from routes.public import public_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(books_bp)
    app.register_blueprint(download_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(public_bp)

    # === 页面路由 ===

    @app.route('/')
    def landing():
        """落地页 — 始终展示"""
        from utils.helpers import get_current_user
        user = get_current_user()
        # 传递登录状态给模板
        return render_template('landing.html', logged_in=bool(user))

    @app.route('/main')
    def main_page():
        """读书主界面 — 需要登录"""
        from utils.helpers import get_current_user
        if not get_current_user():
            return redirect('/login')
        return render_template('main.html')

    @app.route('/login')
    def login_page():
        from utils.helpers import get_current_user
        user = get_current_user()
        if user:
            return redirect('/main')
        return render_template('login.html')

    @app.route('/admin')
    def admin_page():
        from utils.helpers import get_current_user
        user = get_current_user()
        if not user or user['role'] != 'admin':
            return redirect('/login')
        return render_template('admin.html')

    @app.route('/maintenance')
    def maintenance_page():
        return render_template('maintenance.html')

    @app.route('/upgrade')
    def upgrade_page():
        return render_template('upgrade.html')

    @app.route('/sonovelwebguide')
    def sonovel_guide():
        return render_template('sonovelguide.html')

    @app.route('/aboutsonovelweb.md')
    def sonovel_md():
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aboutsonovelweb.md')
        return open(path, 'r', encoding='utf-8').read()

    @app.route('/sonovel教程1.png')
    def sonovel_img():
        import os
        from flask import send_file
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sonovel教程1.png')
        if os.path.exists(path):
            return send_file(path, mimetype='image/png')
        return 'image not found', 404

    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith('/api/'):
            r = jsonify({'code': 404, 'message': 'Not Found', 'data': None}); r.status_code = 404; return r
        return render_template('landing.html'), 200

    @app.errorhandler(500)
    def server_error(e):
        r = jsonify({'code': 500, 'message': 'Server Error', 'data': None}); r.status_code = 500; return r

    return app


app = create_app()

if __name__ == '__main__':
    print(f"\n  Miniread (极读) v{Config.VERSION}\n  http://{Config.HOST}:{Config.PORT}\n")
    app.run(host=Config.HOST, port=Config.PORT, debug=False, threaded=True)

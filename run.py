"""
Miniread (极读) - 启动脚本
支持 Flask 开发模式和 waitress 生产模式
"""
import os
import sys
import threading
import time

SESSION_CLEANUP_INTERVAL = 24 * 3600  # 24 小时


def start_session_cleanup_thread():
    """启动会话清理守护线程：启动时立即清理一次过期会话，此后每 24 小时执行一次"""
    from database import cleanup_expired_sessions

    def _loop():
        while True:
            try:
                removed = cleanup_expired_sessions()
                if removed:
                    print(f"已清理 {removed} 条过期会话")
            except Exception as exc:
                print(f"会话清理失败: {exc}")
            time.sleep(SESSION_CLEANUP_INTERVAL)

    threading.Thread(target=_loop, name='session-cleanup', daemon=True).start()


def main():
    from app import app
    from config import Config

    start_session_cleanup_thread()

    # 检查是否在生产模式
    production = os.environ.get('MINIREAD_PRODUCTION', '').lower() in ('1', 'true', 'yes')

    if production:
        try:
            from waitress import serve
            print(f"""
╔══════════════════════════════════════════╗
║       Miniread (极读) v{Config.VERSION}          ║
║   在线阅读管理平台 (生产模式)            ║
║   http://{Config.HOST}:{Config.PORT}                     ║
╚══════════════════════════════════════════╝
            """)
            serve(app, host=Config.HOST, port=Config.PORT, threads=8)
        except ImportError:
            print("waitress 未安装，回退到 Flask 开发服务器")
            app.run(host=Config.HOST, port=Config.PORT, threaded=True)
    else:
        print(f"""
╔══════════════════════════════════════════╗
║       Miniread (极读) v{Config.VERSION}          ║
║   在线阅读管理平台                       ║
║   http://{Config.HOST}:{Config.PORT}                     ║
╚══════════════════════════════════════════╝
        """)
        app.run(host=Config.HOST, port=Config.PORT, debug=False, threaded=True)


if __name__ == '__main__':
    main()

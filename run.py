"""
Miniread (极读) - 启动脚本
支持 Flask 开发模式和 waitress 生产模式
"""
import os
import sys

def main():
    from app import app
    from config import Config

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

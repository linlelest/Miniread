"""
Miniread (极读) - 配置管理
"""
import os

class Config:
    """应用配置"""
    # 基础路径
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # 数据库
    DATABASE_PATH = os.path.join(BASE_DIR, 'data', 'miniread.db')

    # 上传目录
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

    # 下载临时目录
    DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'downloads')

    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'miniread-secret-key-change-in-production')
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200MB max upload

    # Session配置
    SESSION_COOKIE_NAME = 'miniread_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 30 * 24 * 3600  # 30 days for "remember me"

    # 服务器配置
    HOST = os.environ.get('HOST', '0.0.0.0')
    PORT = int(os.environ.get('PORT', 7766))

    # 版本号 (每次发布更新)
    VERSION = '1.0.0'

    # 支持的电子书格式
    ALLOWED_EXTENSIONS = {
        'txt', 'epub', 'pdf', 'mobi', 'azw', 'azw3', 'fb2',
        'html', 'htm', 'md', 'markdown', 'docx', 'rtf', 'djvu',
        'chm', 'cbr', 'cbz', 'prc', 'pdb', 'lit'
    }

    # 可在线阅读的格式 (Tier 1)
    READABLE_FORMATS_T1 = {'txt', 'epub', 'pdf'}

    # 可转换格式 (Tier 2 - 服务端转HTML)
    CONVERTIBLE_FORMATS_T2 = {'fb2', 'html', 'htm', 'md', 'markdown', 'docx'}

    # 基础管理格式 (Tier 3 - 仅下载/管理)
    MANAGED_FORMATS_T3 = {'mobi', 'azw', 'azw3', 'rtf', 'djvu', 'chm', 'cbr', 'cbz', 'prc', 'pdb', 'lit'}

    # 上传分块大小
    CHUNK_SIZE = 8192

    # SoNovel默认超时
    SONOVEL_TIMEOUT = 120  # seconds

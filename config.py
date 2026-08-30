"""
Miniread (极读) - 配置管理
"""
import os
import secrets


def _load_or_create_secret_key(key_file=None):
    """
    解析 SECRET_KEY，优先级：
    1. 环境变量 MINIREAD_SECRET_KEY
    2. data/secret_key 文件
    3. 自动生成随机值并持久化到 data/secret_key
    """
    env_key = os.environ.get('MINIREAD_SECRET_KEY')
    if env_key:
        return env_key
    if key_file is None:
        key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'secret_key')
    if os.path.exists(key_file):
        try:
            with open(key_file, 'r', encoding='utf-8') as f:
                stored = f.read().strip()
            if stored:
                return stored
        except OSError:
            pass
    generated = secrets.token_hex(32)
    os.makedirs(os.path.dirname(key_file), exist_ok=True)
    with open(key_file, 'w', encoding='utf-8') as f:
        f.write(generated)
    return generated


class Config:
    """应用配置"""
    # 基础路径
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # 数据目录
    DATA_DIR = os.path.join(BASE_DIR, 'data')

    # 数据库
    DATABASE_PATH = os.path.join(DATA_DIR, 'miniread.db')

    # 规范书存储目录 (data/books/<book_id>/)
    CANONICAL_DIR = os.path.join(DATA_DIR, 'books')

    # 上传目录
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

    # 下载临时目录
    DOWNLOAD_FOLDER = os.path.join(BASE_DIR, 'downloads')

    # Flask配置（无硬编码默认值，来源见 _load_or_create_secret_key）
    SECRET_KEY = _load_or_create_secret_key()
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
    VERSION = '2.1'

    # 支持的电子书格式（LIT/CHM/DJVU/CBR/PDB 无解析器，已彻底移除）
    ALLOWED_EXTENSIONS = {
        'txt', 'epub', 'pdf', 'mobi', 'azw', 'azw3', 'prc', 'fb2',
        'html', 'htm', 'md', 'markdown', 'docx', 'rtf', 'cbz', 'pptx', 'ppt'
    }

    # 格式处理类型：canonical=导入时转规范书 / native=foliate-js 原生解析 / pdf=pdf.js / pptx=浏览器渲染
    # ppt 与 pptx 走同一链路：上传后 LibreOffice 转 PDF，转换失败回退浏览器渲染
    # rss=RSS 订阅（不经过 upload 通道，由订阅服务直接写入 books 表，format='rss'）
    FORMAT_KIND = {
        'txt': 'canonical', 'epub': 'canonical', 'docx': 'canonical',
        'fb2': 'canonical', 'html': 'canonical', 'htm': 'canonical',
        'md': 'canonical', 'markdown': 'canonical', 'rtf': 'canonical',
        'mobi': 'native', 'azw': 'native', 'azw3': 'native', 'prc': 'native',
        'cbz': 'native', 'pdf': 'pdf', 'pptx': 'pptx', 'ppt': 'pptx',
        'rss': 'rss',
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

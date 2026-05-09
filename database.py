"""
Miniread (极读) - 数据库初始化与管理
SQLite 单文件数据库
"""
import sqlite3
import os
from config import Config


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库，创建所有表"""
    os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
    conn = get_db()
    cursor = conn.cursor()

    # ============ 用户表 ============
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            banned INTEGER DEFAULT 0,
            banned_at REAL,
            banned_ip TEXT,
            ban_expires_at REAL,
            deleted INTEGER DEFAULT 0,
            delete_reason TEXT,
            deleted_at REAL,
            created_at REAL DEFAULT (strftime('%s', 'now'))
        )
    ''')

    # ============ 会话表 (Remember Me) ============
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at REAL NOT NULL,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # ============ 书籍表 ============
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            author TEXT DEFAULT '',
            format TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            cover_path TEXT DEFAULT '',
            source TEXT DEFAULT 'local',
            last_read_position REAL DEFAULT 0,
            last_read_chapter TEXT DEFAULT '',
            note TEXT DEFAULT '',
            total_chapters INTEGER DEFAULT 0,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # ============ 书签表 ============
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            chapter TEXT DEFAULT '',
            position REAL DEFAULT 0,
            note TEXT DEFAULT '',
            created_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
        )
    ''')

    # ============ 高亮/收藏文字表 ============
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS highlights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER NOT NULL,
            chapter TEXT DEFAULT '',
            selected_text TEXT NOT NULL,
            position REAL DEFAULT 0,
            color TEXT DEFAULT '#FFFF00',
            note TEXT DEFAULT '',
            created_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
        )
    ''')

    # ============ 阅读设置表 ============
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reading_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_id INTEGER,
            font_size INTEGER DEFAULT 18,
            background_color TEXT DEFAULT '#F5F0E8',
            text_color TEXT DEFAULT '#333333',
            line_spacing REAL DEFAULT 1.8,
            paragraph_spacing REAL DEFAULT 1.2,
            font_family TEXT DEFAULT 'serif',
            page_width TEXT DEFAULT '800px',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE
        )
    ''')

    # ============ 公告表 ============
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT DEFAULT '',
            content TEXT NOT NULL,
            visibility TEXT DEFAULT 'all',
            show_dismiss INTEGER DEFAULT 0,
            pinned INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at REAL DEFAULT (strftime('%s', 'now')),
            updated_at REAL DEFAULT (strftime('%s', 'now'))
        )
    ''')

    # ============ 封禁/删除记录表 (公开) ============
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS banned_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            reason TEXT DEFAULT '',
            action TEXT NOT NULL,
            created_at REAL DEFAULT (strftime('%s', 'now'))
        )
    ''')

    # ============ 邀请码表 ============
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS invite_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            max_uses INTEGER DEFAULT 1,
            used_count INTEGER DEFAULT 0,
            expires_at REAL,
            note TEXT DEFAULT '',
            active INTEGER DEFAULT 1,
            created_at REAL DEFAULT (strftime('%s', 'now'))
        )
    ''')

    # ============ 系统设置表 ============
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # ============ 下载任务表 (SoNovel集成) ============
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS download_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            book_name TEXT DEFAULT '',
            author TEXT DEFAULT '',
            source_name TEXT DEFAULT '',
            format TEXT DEFAULT 'epub',
            url TEXT DEFAULT '',
            dlid TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            total_chapters INTEGER DEFAULT 0,
            error_message TEXT DEFAULT '',
            created_at REAL DEFAULT (strftime('%s', 'now')),
            completed_at REAL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # ============ SoNovel服务器配置表 (每用户) ============
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS novel_server_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            server_url TEXT DEFAULT '',
            api_token TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')

    # ============ 数据库迁移 ============
    try:
        cursor.execute("ALTER TABLE books ADD COLUMN note TEXT DEFAULT ''")
    except:
        pass
    try:
        cursor.execute("ALTER TABLE announcements ADD COLUMN title TEXT DEFAULT ''")
    except:
        pass  # Column already exists

    # ============ 默认系统设置 ============
    default_settings = [
        ('maintenance_mode', '0'),
        ('maintenance_content', '## 网站维护中\n\n网站正在维护，请稍后再来。'),
        ('invite_enabled', '0'),
        ('invite_prompt', '需要邀请码才能注册，请联系管理员获取'),
        ('version', Config.VERSION),
        ('updating', '0'),
        ('update_progress', '0'),
        ('update_message', ''),
    ]
    for key, value in default_settings:
        cursor.execute(
            'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
            (key, value)
        )

    conn.commit()

    # ============ 创建索引 ============
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_user ON books(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_bookmarks_user_book ON bookmarks(user_id, book_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_highlights_user_book ON highlights(user_id, book_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_download_tasks_user ON download_tasks(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)')

    conn.commit()
    conn.close()


def get_setting(key, default=None):
    """获取系统设置"""
    conn = get_db()
    row = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
    conn.close()
    if row:
        return row['value']
    return default


def set_setting(key, value):
    """设置系统设置"""
    conn = get_db()
    conn.execute(
        'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
        (key, str(value))
    )
    conn.commit()
    conn.close()

"""
Miniread (极读) - 书籍管理路由
"""
import os
import time
import json
from flask import Blueprint, request, g, send_file
from werkzeug.utils import secure_filename
from database import get_db
from config import Config
from utils.helpers import (
    json_response, require_auth, allowed_file,
    get_file_extension, safe_filename, format_file_size,
    detect_chapters_txt
)
from services.book_parser import (
    parse_epub, parse_fb2, parse_docx, parse_html,
    parse_markdown, parse_rtf, parse_pdf, extract_txt_preview
)

books_bp = Blueprint('books', __name__)


@books_bp.route('/api/books', methods=['GET'])
@require_auth
def list_books():
    """获取用户书架"""
    conn = get_db()
    books = conn.execute(
        '''SELECT id, title, author, note, format, file_size, cover_path,
           source, last_read_position, last_read_chapter,
           total_chapters, created_at
           FROM books WHERE user_id = ?
           ORDER BY created_at DESC''',
        (g.current_user['id'],)
    ).fetchall()
    conn.close()

    result = []
    for b in books:
        d = dict(b)
        d['file_size_formatted'] = format_file_size(d['file_size'])
        d['last_read_percent'] = round(d['last_read_position'] * 100, 1)
        # Set cover_url if: manual cover exists, OR format supports auto-extract
        import os as _os
        has_manual = d.get('cover_path') and _os.path.exists(d['cover_path'])
        has_auto = d['format'] in ('epub', 'pdf', 'mobi', 'azw3', 'fb2')
        d['cover_url'] = f'/api/books/{d["id"]}/cover' if (has_manual or has_auto) else None
        result.append(d)

    return json_response(data=result)


@books_bp.route('/api/books/upload', methods=['POST'])
@require_auth
def upload_book():
    """上传书籍"""
    if 'file' not in request.files:
        return json_response(code=400, message='请选择文件')

    file = request.files['file']
    if file.filename == '':
        return json_response(code=400, message='请选择文件')

    if not allowed_file(file.filename):
        return json_response(code=400, message='不支持的电子书格式')

    # 保存文件
    filename = safe_filename(file.filename)
    ext = get_file_extension(filename)
    user_dir = os.path.join(Config.UPLOAD_FOLDER, str(g.current_user['id']))
    os.makedirs(user_dir, exist_ok=True)

    # 避免重名
    base_name = os.path.splitext(filename)[0]
    save_path = os.path.join(user_dir, filename)
    counter = 1
    while os.path.exists(save_path):
        new_name = f"{base_name}_{counter}.{ext}"
        save_path = os.path.join(user_dir, new_name)
        counter += 1

    file.save(save_path)
    file_size = os.path.getsize(save_path)

    # 提取书籍信息
    title = base_name
    author = ''
    total_chapters = 0

    try:
        if ext == 'epub':
            meta = parse_epub(save_path)
            title = meta.get('title', title)
            author = meta.get('author', author)
            total_chapters = meta.get('total_chapters', 0)
        elif ext == 'fb2':
            meta = parse_fb2(save_path)
            title = meta.get('title', title)
            author = meta.get('author', author)
            total_chapters = meta.get('total_chapters', 0)
        elif ext in ('txt', 'text'):
            # 尝试从文件名提取标题
            title = base_name
            # 检测章节数量
            try:
                with open(save_path, 'r', encoding='utf-8') as f:
                    sample = f.read(500000)  # Read first 500KB for detection
                chapters = detect_chapters_txt(sample)
                total_chapters = len(chapters)
            except UnicodeDecodeError:
                try:
                    with open(save_path, 'r', encoding='gbk') as f:
                        sample = f.read(500000)
                    chapters = detect_chapters_txt(sample)
                    total_chapters = len(chapters)
                except:
                    pass
    except Exception as e:
        pass  # 解析失败不影响上传

    # 存入数据库
    conn = get_db()
    now = time.time()
    cursor = conn.execute(
        '''INSERT INTO books (user_id, title, author, format, file_path,
           file_size, source, total_chapters, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (g.current_user['id'], title, author, ext, save_path,
         file_size, 'local', total_chapters, now)
    )
    book_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return json_response(data={
        'id': book_id,
        'title': title,
        'author': author,
        'format': ext,
        'file_size': file_size,
        'file_size_formatted': format_file_size(file_size),
        'total_chapters': total_chapters,
        'message': '上传成功'
    })


@books_bp.route('/api/books/<int:book_id>', methods=['GET'])
@require_auth
def get_book(book_id):
    """获取书籍详情"""
    conn = get_db()
    book = conn.execute(
        'SELECT * FROM books WHERE id = ? AND user_id = ?',
        (book_id, g.current_user['id'])
    ).fetchone()
    conn.close()

    if not book:
        return json_response(code=404, message='书籍不存在')

    d = dict(book)
    d['file_size_formatted'] = format_file_size(d['file_size'])
    d['last_read_percent'] = round(d['last_read_position'] * 100, 1)
    return json_response(data=d)


@books_bp.route('/api/books/<int:book_id>', methods=['PUT'])
@require_auth
def update_book(book_id):
    """更新书籍信息 — 支持JSON或FormData（含封面文件）"""
    # Accept both JSON and FormData
    if request.content_type and 'application/json' in request.content_type:
        data = request.get_json()
    else:
        data = {k: v for k, v in request.form.items()}

    conn = get_db()
    book = conn.execute(
        'SELECT * FROM books WHERE id = ? AND user_id = ?',
        (book_id, g.current_user['id'])
    ).fetchone()
    if not book:
        conn.close()
        return json_response(code=404, message='书籍不存在')

    title = data.get('title', book['title'])
    author = data.get('author', book['author'])
    note = data.get('note', book['note'])
    cover_path = book['cover_path']

    # Handle cover file upload
    if 'cover' in request.files:
        cover_file = request.files['cover']
        if cover_file and cover_file.filename:
            import os
            user_dir = os.path.join(Config.UPLOAD_FOLDER, str(g.current_user['id']))
            os.makedirs(user_dir, exist_ok=True)
            ext = os.path.splitext(cover_file.filename)[1].lower()
            if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
                cover_name = f'cover_{book_id}{ext}'
                cover_save = os.path.join(user_dir, cover_name)
                cover_file.save(cover_save)
                cover_path = cover_save

    conn.execute(
        'UPDATE books SET title = ?, author = ?, note = ?, cover_path = ? WHERE id = ?',
        (title, author, note, cover_path, book_id)
    )
    conn.commit()
    conn.close()
    return json_response(data={'message': '更新成功'})


@books_bp.route('/api/books/<int:book_id>', methods=['DELETE'])
@require_auth
def delete_book(book_id):
    """删除书籍"""
    conn = get_db()
    book = conn.execute(
        'SELECT * FROM books WHERE id = ? AND user_id = ?',
        (book_id, g.current_user['id'])
    ).fetchone()
    if not book:
        conn.close()
        return json_response(code=404, message='书籍不存在')

    # 清理内存缓存，释放文件句柄
    if book['file_path'] in _epub_meta:
        del _epub_meta[book['file_path']]

    # 删除文件（书籍 + 自定义封面）
    file_path = book['file_path']
    if file_path and os.path.exists(file_path):
        try: os.remove(file_path)
        except Exception as e: pass
    cover_path = book['cover_path']
    if cover_path and os.path.exists(cover_path):
        try: os.remove(cover_path)
        except Exception as e: pass

    # 删除数据库记录
    conn.execute('DELETE FROM books WHERE id = ?', (book_id,))
    conn.execute('DELETE FROM bookmarks WHERE book_id = ?', (book_id,))
    conn.execute('DELETE FROM highlights WHERE book_id = ?', (book_id,))
    conn.execute('DELETE FROM reading_settings WHERE book_id = ?', (book_id,))
    conn.commit()
    conn.close()
    return json_response(data={'message': '已删除'})


@books_bp.route('/api/books/<int:book_id>/toc', methods=['GET'])
@require_auth
def get_toc(book_id):
    """获取书籍目录"""
    conn = get_db()
    book = conn.execute(
        'SELECT * FROM books WHERE id = ? AND user_id = ?',
        (book_id, g.current_user['id'])
    ).fetchone()
    conn.close()

    if not book:
        return json_response(code=404, message='书籍不存在')

    try:
        chapters = _get_book_chapters(book)
        return json_response(data=chapters)
    except Exception as e:
        return json_response(code=500, message=f'目录解析失败: {str(e)}')


@books_bp.route('/api/books/<int:book_id>/content', methods=['GET'])
@require_auth
def get_book_content(book_id):
    """获取书籍内容（章节内容）"""
    chapter_index = request.args.get('chapter', 0, type=int)

    conn = get_db()
    book = conn.execute(
        'SELECT * FROM books WHERE id = ? AND user_id = ?',
        (book_id, g.current_user['id'])
    ).fetchone()
    conn.close()

    if not book:
        return json_response(code=404, message='书籍不存在')

    try:
        chapters = _get_book_chapters(book)
        if not chapters:
            return json_response(code=400, message='无法识别该书籍的章节')

        if chapter_index < 0 or chapter_index >= len(chapters):
            return json_response(code=400, message='章节索引超出范围')

        content_html = _get_chapter_content(book, chapters, chapter_index)

        return json_response(data={
            'chapterIndex': chapter_index,
            'chapterTitle': chapters[chapter_index]['title'],
            'totalChapters': len(chapters),
            'content': content_html,
            'prevChapter': chapter_index - 1 if chapter_index > 0 else None,
            'nextChapter': chapter_index + 1 if chapter_index < len(chapters) - 1 else None,
        })
    except Exception as e:
        return json_response(code=500, message=f'内容读取失败: {str(e)}')


@books_bp.route('/api/books/<int:book_id>/cover', methods=['GET'])
@require_auth
def get_book_cover(book_id):
    """获取书籍封面 — 直接从文件提取并返回（跳过磁盘缓存，避免404）"""
    conn = get_db()
    book = conn.execute(
        'SELECT * FROM books WHERE id = ? AND user_id = ?',
        (book_id, g.current_user['id'])
    ).fetchone()
    conn.close()

    if not book:
        return json_response(code=404, message='书籍不存在')

    # Serve manually uploaded cover first
    if book['cover_path']:
        has = False
        try: has = os.path.exists(book['cover_path'])
        except: pass
        if has:
            import mimetypes
            mime, _ = mimetypes.guess_type(book['cover_path'])
            return send_file(book['cover_path'], mimetype=mime or 'image/jpeg')

    # Auto-extract from ebook formats
    if book['format'] in ('epub', 'pdf', 'mobi', 'azw3', 'fb2'):
        try:
            import zipfile, base64
            with zipfile.ZipFile(book['file_path'], 'r') as zf:
                # Strategy 1: Find cover meta in OPF
                opf_name = None
                for n in zf.namelist():
                    if n.endswith('.opf') and not n.startswith('__'):
                        opf_name = n
                        break
                if opf_name:
                    import re, xml.etree.ElementTree as ET
                    opf = zf.read(opf_name).decode('utf-8', errors='replace')
                    # Find cover meta
                    m = re.search(r'<meta[^>]+name="cover"[^>]+content="([^"]+)"', opf, re.I)
                    if m:
                        cover_id = m.group(1)
                        # Find item with that id
                        root = ET.fromstring(opf)
                        for item in root.iter():
                            if item.get('id') == cover_id:
                                href = item.get('href', '')
                                if href:
                                    opf_dir = os.path.dirname(opf_name).replace('\\', '/')
                                    full = os.path.normpath((opf_dir + '/' + href if opf_dir else href)).replace('\\', '/')
                                    for zn in zf.namelist():
                                        if zn.replace('\\', '/') == full.replace('\\', '/') or zn.endswith('/' + href):
                                            raw = zf.read(zn)
                                            ext = href.rsplit('.', 1)[-1].lower()
                                            if ext in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
                                                from flask import Response
                                                return Response(raw, mimetype='image/' + ('jpeg' if ext == 'jpg' else ext))
                # Strategy 2: Look for ITEM_COVER type in manifest
                for zn in zf.namelist():
                    if 'cover' in zn.lower() and zn.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                        raw = zf.read(zn)
                        ext = zn.rsplit('.', 1)[-1].lower()
                        from flask import Response
                        return Response(raw, mimetype='image/' + ('jpeg' if ext == 'jpg' else ext))
        except:
            pass

    return json_response(code=404, message='无封面')


def _serve_image_data(item, book):
    """Serve image data directly from item, set proper headers"""
    raw = item.get_content()
    ext = item.get_name().rsplit('.', 1)[-1].lower() if '.' in item.get_name() else 'jpg'
    mime_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                'gif': 'image/gif', 'svg': 'image/svg+xml', 'webp': 'image/webp'}
    mime = mime_map.get(ext, 'image/' + ext)
    from flask import Response
    return Response(raw, mimetype=mime)


@books_bp.route('/api/books/<int:book_id>/epub-image', methods=['GET'])
@require_auth
def serve_epub_image(book_id):
    """直接服务EPUB内部图片 — 极速，无需base64编码"""
    import zipfile
    path = request.args.get('path', '')
    if not path:
        return json_response(code=400, message='缺少path参数')

    conn = get_db()
    book = conn.execute('SELECT file_path,format FROM books WHERE id=? AND user_id=?',
                        (book_id, g.current_user['id'])).fetchone()
    conn.close()
    if not book:
        return json_response(code=404, message='书籍不存在')
    if book['format'] not in ('epub',):
        return json_response(code=400, message='仅支持EPUB格式')

    try:
        with zipfile.ZipFile(book['file_path'], 'r') as zf:
            # Try exact match first, then basename match
            for name in zf.namelist():
                if name == path or name.endswith('/' + path) or os.path.basename(name) == path:
                    raw = zf.read(name)
                    ext = os.path.splitext(name)[1].lstrip('.').lower()
                    mime_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                                'png': 'image/png', 'gif': 'image/gif',
                                'svg': 'image/svg+xml', 'webp': 'image/webp'}
                    mime = mime_map.get(ext, 'image/' + ext)
                    from flask import Response
                    return Response(raw, mimetype=mime,
                                    headers={'Cache-Control': 'public, max-age=3600'})
            return json_response(code=404, message='图片未找到')
    except Exception as e:
        return json_response(code=500, message=str(e))


@books_bp.route('/api/books/<int:book_id>/download', methods=['GET'])
@require_auth
def download_book_file(book_id):
    """下载原始书籍文件"""
    conn = get_db()
    book = conn.execute(
        'SELECT * FROM books WHERE id = ? AND user_id = ?',
        (book_id, g.current_user['id'])
    ).fetchone()
    conn.close()

    if not book:
        return json_response(code=404, message='书籍不存在')

    if not os.path.exists(book['file_path']):
        return json_response(code=404, message='文件不存在')

    download_name = f"{book['title']}.{book['format']}"
    return send_file(
        book['file_path'],
        as_attachment=True,
        download_name=download_name
    )


@books_bp.route('/api/books/<int:book_id>/file', methods=['GET'])
@require_auth
def serve_book_file(book_id):
    """服务原始文件（内联展示用）"""
    conn = get_db()
    book = conn.execute(
        'SELECT * FROM books WHERE id = ? AND user_id = ?',
        (book_id, g.current_user['id'])
    ).fetchone()
    conn.close()

    if not book:
        return json_response(code=404, message='书籍不存在')

    if not os.path.exists(book['file_path']):
        return json_response(code=404, message='文件不存在')

    mimetypes_map = {
        'pdf': 'application/pdf',
        'epub': 'application/epub+zip',
        'mobi': 'application/x-mobipocket-ebook',
        'azw': 'application/vnd.amazon.ebook',
        'djvu': 'image/vnd.djvu',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }
    mime = mimetypes_map.get(book['format'].lower(), 'application/octet-stream')

    return send_file(
        book['file_path'],
        mimetype=mime,
        as_attachment=False
    )


# ============ 阅读进度与设置 ============

@books_bp.route('/api/reading/<int:book_id>/settings', methods=['GET'])
@require_auth
def get_reading_settings(book_id):
    """获取阅读设置"""
    conn = get_db()
    # 优先获取该书的设置
    settings = conn.execute(
        'SELECT * FROM reading_settings WHERE user_id = ? AND book_id = ?',
        (g.current_user['id'], book_id)
    ).fetchone()

    # 如果没有该书特定设置，返回用户全局默认
    if not settings:
        settings = conn.execute(
            'SELECT * FROM reading_settings WHERE user_id = ? AND book_id IS NULL',
            (g.current_user['id'],)
        ).fetchone()

    conn.close()

    if settings:
        data = dict(settings)
        data.pop('id', None)
        return json_response(data=data)
    else:
        return json_response(data={
            'font_size': 18,
            'background_color': '#F5F0E8',
            'text_color': '#333333',
            'line_spacing': 1.8,
            'paragraph_spacing': 1.2,
            'font_family': 'serif',
            'page_width': '800px',
        })


@books_bp.route('/api/reading/<int:book_id>/settings', methods=['PUT'])
@require_auth
def update_reading_settings(book_id):
    """更新阅读设置"""
    data = request.get_json()
    conn = get_db()

    existing = conn.execute(
        'SELECT id FROM reading_settings WHERE user_id = ? AND book_id = ?',
        (g.current_user['id'], book_id)
    ).fetchone()

    fields = {
        'font_size': data.get('font_size', 18),
        'background_color': data.get('background_color', '#F5F0E8'),
        'text_color': data.get('text_color', '#333333'),
        'line_spacing': data.get('line_spacing', 1.8),
        'paragraph_spacing': data.get('paragraph_spacing', 1.2),
        'font_family': data.get('font_family', 'serif'),
        'page_width': data.get('page_width', '800px'),
    }

    if existing:
        conn.execute('''
            UPDATE reading_settings SET
            font_size=?, background_color=?, text_color=?,
            line_spacing=?, paragraph_spacing=?, font_family=?, page_width=?
            WHERE id=?''',
            (*fields.values(), existing['id'])
        )
    else:
        conn.execute('''
            INSERT INTO reading_settings
            (user_id, book_id, font_size, background_color, text_color,
             line_spacing, paragraph_spacing, font_family, page_width)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (g.current_user['id'], book_id, *fields.values())
        )

    conn.commit()
    conn.close()
    return json_response(data={'message': '设置已保存'})


@books_bp.route('/api/reading/<int:book_id>/position', methods=['PUT'])
@require_auth
def save_reading_position(book_id):
    """保存阅读进度"""
    data = request.get_json()
    position = data.get('position', 0)
    chapter = data.get('chapter', '')

    conn = get_db()
    conn.execute(
        'UPDATE books SET last_read_position = ?, last_read_chapter = ? WHERE id = ? AND user_id = ?',
        (position, chapter, book_id, g.current_user['id'])
    )
    conn.commit()
    conn.close()
    return json_response(data={'message': '进度已保存'})


# ============ 书签管理 ============

@books_bp.route('/api/reading/<int:book_id>/bookmarks', methods=['GET'])
@require_auth
def list_bookmarks(book_id):
    """获取书签列表"""
    conn = get_db()
    marks = conn.execute(
        'SELECT * FROM bookmarks WHERE user_id = ? AND book_id = ? ORDER BY position',
        (g.current_user['id'], book_id)
    ).fetchall()
    conn.close()
    return json_response(data=[dict(m) for m in marks])


@books_bp.route('/api/reading/<int:book_id>/bookmarks', methods=['POST'])
@require_auth
def add_bookmark(book_id):
    """添加书签"""
    data = request.get_json()
    chapter = data.get('chapter', '')
    position = data.get('position', 0)
    note = data.get('note', '')

    conn = get_db()
    now = time.time()
    c = conn.execute(
        'INSERT INTO bookmarks (user_id, book_id, chapter, position, note, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        (g.current_user['id'], book_id, chapter, position, note, now)
    )
    mark_id = c.lastrowid
    conn.commit()
    conn.close()
    return json_response(data={'id': mark_id, 'message': '书签已添加'})


@books_bp.route('/api/reading/<int:book_id>/bookmarks/<int:mark_id>', methods=['DELETE'])
@require_auth
def delete_bookmark(book_id, mark_id):
    """删除书签"""
    conn = get_db()
    conn.execute(
        'DELETE FROM bookmarks WHERE id = ? AND user_id = ? AND book_id = ?',
        (mark_id, g.current_user['id'], book_id)
    )
    conn.commit()
    conn.close()
    return json_response(data={'message': '书签已删除'})


# ============ 高亮/收藏管理 ============

@books_bp.route('/api/reading/<int:book_id>/highlights', methods=['GET'])
@require_auth
def list_highlights(book_id):
    """获取高亮列表"""
    conn = get_db()
    items = conn.execute(
        'SELECT * FROM highlights WHERE user_id = ? AND book_id = ? ORDER BY created_at DESC',
        (g.current_user['id'], book_id)
    ).fetchall()
    conn.close()
    return json_response(data=[dict(h) for h in items])


@books_bp.route('/api/reading/<int:book_id>/highlights', methods=['POST'])
@require_auth
def add_highlight(book_id):
    """添加高亮"""
    data = request.get_json()
    selected_text = data.get('text', '')
    chapter = data.get('chapter', '')
    position = data.get('position', 0)
    color = data.get('color', '#FFFF00')
    note = data.get('note', '')

    if not selected_text.strip():
        return json_response(code=400, message='请选择文字')

    conn = get_db()
    now = time.time()
    c = conn.execute(
        '''INSERT INTO highlights
           (user_id, book_id, chapter, selected_text, position, color, note, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (g.current_user['id'], book_id, chapter, selected_text, position, color, note, now)
    )
    h_id = c.lastrowid
    conn.commit()
    conn.close()
    return json_response(data={'id': h_id, 'message': '已收藏'})


@books_bp.route('/api/reading/<int:book_id>/highlights/<int:h_id>', methods=['DELETE'])
@require_auth
def delete_highlight(book_id, h_id):
    """删除高亮"""
    conn = get_db()
    conn.execute(
        'DELETE FROM highlights WHERE id = ? AND user_id = ? AND book_id = ?',
        (h_id, g.current_user['id'], book_id)
    )
    conn.commit()
    conn.close()
    return json_response(data={'message': '已删除'})


# ============ 辅助函数 ============

def _get_book_chapters(book):
    """根据书籍格式获取章节列表 — 保证至少返回1章"""
    ext = book['format'].lower()
    file_path = book['file_path']

    if not os.path.exists(file_path):
        raise FileNotFoundError('文件不存在')

    try:
        if ext == 'epub':
            chapters = parse_epub(file_path).get('chapters', [])
        elif ext == 'fb2':
            chapters = parse_fb2(file_path).get('chapters', [])
        elif ext in ('txt', 'text'):
            chapters = _get_txt_chapters(file_path)
        elif ext in ('html', 'htm'):
            chapters = parse_html(file_path).get('chapters', [])
        elif ext in ('md', 'markdown'):
            chapters = parse_markdown(file_path).get('chapters', [])
        elif ext == 'docx':
            chapters = parse_docx(file_path).get('chapters', [])
        elif ext == 'rtf':
            chapters = parse_rtf(file_path).get('chapters', [])
        elif ext == 'pdf':
            chapters = parse_pdf(file_path).get('chapters', [{'title': book['title'], 'index': 0, 'position': 0}])
        else:
            chapters = _get_txt_chapters(file_path)
    except Exception:
        chapters = []

    # GUARANTEE: never return empty
    if not chapters:
        chapters = [{'title': book['title'], 'index': 0, 'position': 0}]
    return chapters


def _get_txt_chapters(file_path):
    """获取TXT文件的章节"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='gbk') as f:
            content = f.read()

    chapters = detect_chapters_txt(content)

    if not chapters:
        # 如果没有检测到章节，整本书作为一个章节
        return [{
            'title': '正文',
            'index': 0,
            'position': 0
        }]

    return chapters


def _get_chapter_content(book, chapters, chapter_index):
    """获取指定章节的内容（转HTML）"""
    ext = book['format'].lower()
    file_path = book['file_path']
    chapter = chapters[chapter_index]

    if ext == 'epub':
        return _get_epub_chapter(file_path, chapter_index, book['id'])
    elif ext == 'fb2':
        return _get_fb2_chapter(file_path, chapter_index)
    elif ext in ('txt', 'text'):
        return _get_txt_chapter(file_path, chapters, chapter_index)
    elif ext in ('html', 'htm'):
        return _get_html_chapter(file_path, chapter_index)
    elif ext in ('md', 'markdown'):
        return _get_markdown_chapter(file_path, chapter_index)
    elif ext == 'docx':
        return _get_docx_chapter(file_path, chapter_index)
    elif ext == 'rtf':
        return _get_rtf_chapter(file_path, chapter_index)
    elif ext == 'pdf':
        return _get_pdf_chapter(book, file_path, chapter_index)
    else:
        return _get_txt_chapter(file_path, chapters, chapter_index)


# EPUB metadata cache: {file_path: (spine_order, opf_dir, docs)}
_epub_meta = {}

# --- zzz end of cache vars ---


# EPUB metadata cache: {file_path: (spine_order, opf_dir, docs)}
_epub_meta = {}


def _get_epub_chapter(file_path, chapter_index, book_id=0, cache_ahead=4):
    """EPUB章节 — 直接从zip读取，不预加载"""
    if file_path not in _epub_meta:
        _epub_meta[file_path] = _epub_build_meta(file_path)
    _, opf_dir, docs, _ = _epub_meta[file_path]

    if not docs or chapter_index >= len(docs):
        return '<p>章节不存在</p>'

    return _epub_parse_one(file_path, docs[chapter_index], opf_dir, book_id)


@books_bp.route('/api/books/<int:book_id>/cache-clear', methods=['POST'])
@require_auth
def clear_book_cache(book_id):
    """清空指定书籍的EPUB缓存"""
    conn = get_db()
    book = conn.execute('SELECT file_path FROM books WHERE id=? AND user_id=?',
                        (book_id, g.current_user['id'])).fetchone()
    conn.close()
    if book and book['file_path'] in _epub_meta:
        del _epub_meta[book['file_path']]
    return json_response(data={'message': 'ok'})


def _epub_build_meta(file_path):
    """只解析 OPF spine，存储文件路径列表，不预加载内容"""
    import xml.etree.ElementTree as ET, zipfile, os

    docs = []
    spine_order = {}
    opf_dir = ''

    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            for name in zf.namelist():
                if name.endswith('.opf') and not name.startswith('__'):
                    opf_dir = os.path.dirname(name).replace('\\', '/')
                    opf_xml = zf.read(name).decode('utf-8', errors='replace')
                    root = ET.fromstring(opf_xml)

                    ns = {'opf': 'http://www.idpf.org/2007/opf'}
                    manifest = root.find('.//{http://www.idpf.org/2007/opf}manifest') or root.find('.//manifest')
                    href_map = {}
                    if manifest is not None:
                        for item in manifest:
                            href_map[item.get('id', '')] = item.get('href', '')

                    spine_el = root.find('.//{http://www.idpf.org/2007/opf}spine') or root.find('.//spine')
                    if spine_el is not None:
                        for idx, ref in enumerate(spine_el):
                            ref_id = ref.get('idref', '')
                            spine_order[ref_id] = idx
                            if ref_id in href_map:
                                h = href_map[ref_id]
                                full = os.path.normpath((opf_dir + '/' + h if opf_dir else h)).replace('\\', '/')
                                docs.append(full)
                    break
    except:
        pass

    return (spine_order, opf_dir, docs, None)


def _epub_parse_one(file_path, doc_path, opf_dir, book_id=0):
    """按路径从zip读取单章，解析HTML并替换img src"""
    from bs4 import BeautifulSoup
    import zipfile, os

    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            raw = zf.read(doc_path)
            try: decoded = raw.decode('utf-8')
            except:
                try: decoded = raw.decode('latin-1')
                except: decoded = raw.decode('utf-8', errors='replace')

            soup = BeautifulSoup(decoded, 'html.parser')
            body = soup.find('body') or soup
            for t in body.find_all(['script', 'style', 'nav']):
                t.decompose()
            html = str(body) if body else str(soup)

            # Rewrite img src
            img_soup = BeautifulSoup(html, 'html.parser')
            doc_dir = os.path.dirname(doc_path).replace('\\', '/')
            for img_tag in img_soup.find_all('img'):
                src = img_tag.get('src', '')
                if not src or src.startswith('data:') or src.startswith('http'):
                    continue
                candidates = [src]
                if doc_dir: candidates.insert(0, os.path.normpath(doc_dir+'/'+src).replace('\\','/'))
                if opf_dir: candidates.insert(0, os.path.normpath(opf_dir+'/'+src).replace('\\','/'))
                img_tag['src'] = '/api/books/'+str(book_id)+'/epub-image?path='+candidates[0]
            return str(img_soup)
    except:
        return '<p>章节解析失败</p>'


def _epub_img_to_data(item, lazy_imgs):
    """Extract image item to base64 data URI and cache"""
    import base64, os
    name = item.get_name()
    if name in lazy_imgs and isinstance(lazy_imgs[name], str):
        return lazy_imgs[name]

    try:
        raw = item.get_content()
        ext = os.path.splitext(name)[1].lstrip('.').lower()
        mime_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                    'gif': 'image/gif', 'svg': 'image/svg+xml', 'webp': 'image/webp'}
        mime = mime_map.get(ext, 'image/' + ext)
        b64 = base64.b64encode(raw).decode()
        data_uri = f'data:{mime};base64,{b64}'
        lazy_imgs[name] = data_uri
        return data_uri
    except:
        return None


def _get_fb2_chapter(file_path, chapter_index):
    chapters_data = parse_fb2(file_path)
    fb2_chapters = chapters_data.get('epub_chapters', [])
    if chapter_index < len(fb2_chapters):
        return fb2_chapters[chapter_index].get('content', '')
    return '<p>章节内容为空</p>'


def _get_txt_chapter(file_path, chapters, chapter_index):
    """获取TXT章节内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='gbk') as f:
            content = f.read()

    start_pos = chapters[chapter_index]['position']
    if chapter_index < len(chapters) - 1:
        end_pos = chapters[chapter_index + 1]['position']
        chapter_text = content[start_pos:end_pos]
    else:
        chapter_text = content[start_pos:]

    # 转HTML
    lines = chapter_text.strip().split('\n')
    html_parts = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # 跳过标题行（已单独显示）
        if line == chapters[chapter_index]['title']:
            continue
        # 转义HTML特殊字符
        line = (line
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;'))
        html_parts.append(f'<p>{line}</p>')

    return '\n'.join(html_parts)


def _get_html_chapter(file_path, chapter_index):
    chapters_data = parse_html(file_path)
    html_chapters = chapters_data.get('epub_chapters', [])
    if chapter_index < len(html_chapters):
        return html_chapters[chapter_index].get('content', '')
    return '<p>章节内容为空</p>'


def _get_markdown_chapter(file_path, chapter_index):
    chapters_data = parse_markdown(file_path)
    md_chapters = chapters_data.get('epub_chapters', [])
    if chapter_index < len(md_chapters):
        return md_chapters[chapter_index].get('content', '')
    return '<p>章节内容为空</p>'


def _get_docx_chapter(file_path, chapter_index):
    chapters_data = parse_docx(file_path)
    docx_chapters = chapters_data.get('epub_chapters', [])
    if chapter_index < len(docx_chapters):
        return docx_chapters[chapter_index].get('content', '')
    return '<p>章节内容为空</p>'


def _get_rtf_chapter(file_path, chapter_index):
    chapters_data = parse_rtf(file_path)
    rtf_chapters = chapters_data.get('epub_chapters', [])
    if chapter_index < len(rtf_chapters):
        return rtf_chapters[chapter_index].get('content', '')
    return '<p>章节内容为空</p>'


def _get_pdf_chapter(book, file_path, chapter_index):
    """PDF — 全页嵌入原生阅读器"""
    book_id = book['id']
    return '<embed src="/api/books/' + str(book_id) + '/file" type="application/pdf" ' \
           'style="position:absolute;top:0;left:0;width:100%;height:100%;border:none" />'

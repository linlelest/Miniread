import hashlib
import json
import os
import threading
import uuid

from flask import Blueprint, Response, g, request, send_file
from werkzeug.utils import secure_filename

from config import Config
from database import get_db
from services.book_store import (
    asset_path,
    build_canonical,
    load_manifest,
    needs_build,
    read_section,
    remove_canonical,
    section_etag,
)
from utils.helpers import (
    format_file_size,
    get_file_extension,
    json_response,
    require_auth,
    safe_filename,
)

books_bp = Blueprint('books', __name__)

_SETTINGS_INT = {'font_size', 'font_weight', 'tap_zones', 'indent', 'justify'}
_SETTINGS_FLOAT = {'line_spacing', 'paragraph_spacing', 'word_spacing', 'letter_spacing', 'text_indent', 'v_margin'}
_SETTINGS_STR = {
    'background_color', 'text_color', 'accent_color', 'font_family',
    'theme_preset', 'page_mode', 'transition', 'page_width',
}
_IMPORT_KEYS = {'encoding', 'chapter_regex', 'toc_mode', 'strip_toc', 'heading_level'}


def _format_unsupported_message(ext):
    return '暂不支持 %s 格式（可先转换为 EPUB/TXT 后上传）' % ext.upper()


def _set_convert(book_id, status, path):
    conn = get_db()
    conn.execute(
        'UPDATE books SET convert_status = ?, convert_path = ? WHERE id = ?',
        (status, path, book_id),
    )
    conn.commit()
    conn.close()


def _spawn_office_convert(book_id, src_path):
    # 守卫：仅 PPT/PPTX 允许进入转换流程（其他格式误调用时直接复位状态）
    if not src_path.lower().endswith(('.ppt', '.pptx')):
        _set_convert(book_id, 'none', None)
        return

    def worker():
        from services.convert_office import convert_to_pdf, find_soffice
        try:
            if not find_soffice():
                _set_convert(book_id, 'none', None)
                return
            pdf = convert_to_pdf(src_path, os.path.dirname(src_path))
            _set_convert(book_id, 'done' if pdf else 'failed', pdf)
        except Exception:
            try:
                _set_convert(book_id, 'failed', None)
            except Exception:
                pass
    threading.Thread(target=worker, daemon=True, name='office-convert-%d' % book_id).start()


def _get_book(book_id):
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM books WHERE id = ? AND user_id = ? AND 1=1',
        (book_id, g.current_user['id']),
    ).fetchone()
    conn.close()
    return row


def _ensure_canonical(row):
    if Config.FORMAT_KIND.get(row['format']) != 'canonical':
        return None
    if not needs_build(row):
        manifest = load_manifest(row['id'])
        if manifest and manifest.get('gen') == 4:
            return manifest
    options = {}
    try:
        if row['import_options']:
            options = json.loads(row['import_options'])
    except (ValueError, TypeError):
        options = {}
    manifest = build_canonical(row['id'], row['format'], row['file_path'], options)
    conn = get_db()
    conn.execute(
        "UPDATE books SET canonical_status = 'ready', canonical_dir = ?, total_chapters = ? WHERE id = ?",
        (os.path.join(Config.CANONICAL_DIR, str(row['id'])), len(manifest['sections']), row['id']),
    )
    conn.commit()
    conn.close()
    return manifest


def _book_dict(row, manifest=None):
    d = dict(row)
    d['file_size_formatted'] = format_file_size(d['file_size'])
    pos = d.get('last_read_position') or 0
    d['last_read_percent'] = round(pos * 100, 1)
    kind = Config.FORMAT_KIND.get(d['format'])
    d['read_kind'] = kind
    d['unsupported'] = kind is None
    # V2.1 透出分组与 RSS 订阅字段（row 可能为 sqlite3.Row 或缺列，统一 .get 兜底）
    d['group_id'] = d.get('group_id')
    d['kind'] = d.get('kind') or ''
    d['rss_url'] = d.get('rss_url') or ''
    d['sync_interval'] = d.get('sync_interval')
    d['last_synced'] = d.get('last_synced')
    has_manual = d.get('cover_path') and os.path.exists(d['cover_path'])
    has_canonical_cover = False
    if manifest is None and d.get('canonical_status') == 'ready':
        manifest = load_manifest(d['id'])
    if manifest and manifest.get('cover'):
        has_canonical_cover = True
    d['cover_url'] = ('/api/books/%d/cover' % d['id']) if (has_manual or has_canonical_cover) else None
    if d.get('position_data'):
        try:
            d['position'] = json.loads(d['position_data'])
        except (ValueError, TypeError):
            d['position'] = None
    else:
        d['position'] = None
    d.pop('position_data', None)
    if manifest:
        d['total_chapters'] = len(manifest['sections'])
    return d


@books_bp.route('/api/books', methods=['GET'])
@require_auth
def list_books():
    # 动态拼接过滤条件：query 关键词（标题/作者）与 group 分组筛选
    clauses = ['user_id = ?']
    params = [g.current_user['id']]
    query = (request.args.get('query') or '').strip()
    if query:
        # 转义 LIKE 通配符保证按字面匹配；SQLite LIKE 对 ASCII 天然不区分大小写，中文直接匹配
        escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        like = '%' + escaped + '%'
        clauses.append("(title LIKE ? ESCAPE '\\' OR author LIKE ? ESCAPE '\\')")
        params.extend([like, like])
    group = (request.args.get('group') or '').strip()
    if group == 'root':
        # root 表示未分组书籍
        clauses.append('group_id IS NULL')
    elif group.isdigit():
        clauses.append('group_id = ?')
        params.append(int(group))
    conn = get_db()
    rows = conn.execute(
        '''SELECT id, title, author, note, format, file_size, cover_path, fingerprint,
           source, last_read_position, last_read_chapter, canonical_status,
           convert_status, total_chapters, created_at,
           kind, group_id, rss_url, sync_interval, last_synced
           FROM books WHERE %s ORDER BY created_at DESC''' % ' AND '.join(clauses),
        params,
    ).fetchall()
    conn.close()
    return json_response(data=[_book_dict(r) for r in rows])


def _fetch_group(gid):
    # 读取归属当前用户的分组，不存在或非本人时返回 None
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM book_groups WHERE id = ? AND user_id = ?',
        (gid, g.current_user['id']),
    ).fetchone()
    conn.close()
    return row


def _group_dict(row):
    # 分组字典转换，附带 member_count（仅统计当前用户自己组内的书）
    d = dict(row)
    conn = get_db()
    cnt = conn.execute(
        'SELECT COUNT(*) AS c FROM books WHERE group_id = ? AND user_id = ?',
        (row['id'], g.current_user['id']),
    ).fetchone()
    conn.close()
    d['member_count'] = cnt['c']
    return d


@books_bp.route('/api/groups', methods=['GET'])
@require_auth
def list_groups():
    conn = get_db()
    rows = conn.execute(
        'SELECT * FROM book_groups WHERE user_id = ? ORDER BY sort_order, created_at',
        (g.current_user['id'],),
    ).fetchall()
    conn.close()
    return json_response(data=[_group_dict(r) for r in rows])


@books_bp.route('/api/groups', methods=['POST'])
@require_auth
def create_group():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {k: v for k, v in request.form.items() if k == 'name'}
    name = str(body.get('name') or '').strip()
    if not name:
        return json_response(code=400, message='分组名称不能为空')
    conn = get_db()
    cur = conn.execute(
        'INSERT INTO book_groups (user_id, name) VALUES (?, ?)',
        (g.current_user['id'], name[:100]),
    )
    gid = cur.lastrowid
    conn.commit()
    conn.close()
    return json_response(data=_group_dict(_fetch_group(gid)))


@books_bp.route('/api/groups/<int:gid>', methods=['PUT'])
@require_auth
def update_group(gid):
    row = _fetch_group(gid)
    if not row:
        return json_response(code=404, message='分组不存在')
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {k: v for k, v in request.form.items() if k == 'name'}
    name = str(body.get('name') or '').strip()
    if not name:
        return json_response(code=400, message='分组名称不能为空')
    conn = get_db()
    conn.execute('UPDATE book_groups SET name = ? WHERE id = ?', (name[:100], gid))
    conn.commit()
    conn.close()
    return json_response(data=_group_dict(_fetch_group(gid)), message='已保存')


@books_bp.route('/api/groups/<int:gid>', methods=['DELETE'])
@require_auth
def delete_group(gid):
    row = _fetch_group(gid)
    if not row:
        return json_response(code=404, message='分组不存在')
    conn = get_db()
    # 组内书籍先回到未分组状态，再删除分组本身
    conn.execute(
        'UPDATE books SET group_id = NULL WHERE group_id = ? AND user_id = ?',
        (gid, g.current_user['id']),
    )
    conn.execute('DELETE FROM book_groups WHERE id = ?', (gid,))
    conn.commit()
    conn.close()
    return json_response(message='已删除')


@books_bp.route('/api/books/upload', methods=['POST'])
@require_auth
def upload_book():
    if 'file' not in request.files:
        return json_response(code=400, message='请选择文件')
    file = request.files['file']
    if not file.filename:
        return json_response(code=400, message='请选择文件')
    ext = get_file_extension(file.filename)
    if ext not in Config.ALLOWED_EXTENSIONS:
        return json_response(code=400, message='不支持的文件类型 .%s' % ext)
    if ext not in Config.FORMAT_KIND:
        return json_response(code=400, message=_format_unsupported_message(ext))

    options = {}
    raw_options = request.form.get('import_options')
    if raw_options:
        try:
            loaded = json.loads(raw_options)
            if isinstance(loaded, dict):
                options = {k: loaded[k] for k in _IMPORT_KEYS if k in loaded}
        except ValueError:
            return json_response(code=400, message='导入选项格式错误')

    data = file.read()
    if not data:
        return json_response(code=400, message='文件为空')
    fingerprint = hashlib.sha1(data).hexdigest()

    conn = get_db()
    dup = conn.execute(
        'SELECT id FROM books WHERE user_id = ? AND fingerprint = ?',
        (g.current_user['id'], fingerprint),
    ).fetchone()
    conn.close()
    if dup:
        return json_response(code=409, message='该书已在书架中')

    user_dir = os.path.join(Config.UPLOAD_FOLDER, str(g.current_user['id']))
    os.makedirs(user_dir, exist_ok=True)
    stored_name = '%s_%s' % (uuid.uuid4().hex[:8], secure_filename(file.filename) or ('book.%s' % ext))
    file_path = os.path.join(user_dir, stored_name)
    with open(file_path, 'wb') as f:
        f.write(data)

    title = (request.form.get('title') or '').strip() or os.path.splitext(file.filename)[0]
    conn = get_db()
    cur = conn.execute(
        '''INSERT INTO books (user_id, title, author, format, file_path, file_size,
           source, fingerprint, canonical_status, import_options)
           VALUES (?, ?, ?, ?, ?, ?, 'local', ?, 'pending', ?)''',
        (g.current_user['id'], title, (request.form.get('author') or '').strip(),
         ext, file_path, len(data), fingerprint, json.dumps(options, ensure_ascii=False)),
    )
    book_id = cur.lastrowid
    conn.commit()
    conn.close()

    manifest = None
    summary = {'sections': None, 'title': title, 'native': True}
    if Config.FORMAT_KIND.get(ext) == 'canonical':
        try:
            manifest = build_canonical(book_id, ext, file_path, options)
        except ValueError as e:
            conn = get_db()
            conn.execute('DELETE FROM books WHERE id = ?', (book_id,))
            conn.commit()
            conn.close()
            remove_canonical(book_id)
            try:
                os.remove(file_path)
            except OSError:
                pass
            return json_response(code=400, message=str(e))
        except Exception:
            conn = get_db()
            conn.execute('DELETE FROM books WHERE id = ?', (book_id,))
            conn.commit()
            conn.close()
            remove_canonical(book_id)
            try:
                os.remove(file_path)
            except OSError:
                pass
            return json_response(code=500, message='解析失败，请检查文件是否损坏')
        conn = get_db()
        conn.execute(
            "UPDATE books SET canonical_status = 'ready', canonical_dir = ?, total_chapters = ? WHERE id = ?",
            (os.path.join(Config.CANONICAL_DIR, str(book_id)), len(manifest['sections']), book_id),
        )
        conn.commit()
        conn.close()
    else:
        conn = get_db()
        # 仅 PPT/PPTX 需要 LibreOffice 转 PDF；PDF/MOBI/CBZ 等原生格式不走转换
        if Config.FORMAT_KIND.get(ext) == 'pptx':
            from services.convert_office import find_soffice
            if find_soffice():
                # 本机可转换：进入 pending，由后台线程执行
                conn.execute("UPDATE books SET canonical_status = 'none', convert_status = 'pending' WHERE id = ?", (book_id,))
                conn.commit()
                conn.close()
                _spawn_office_convert(book_id, file_path)
            else:
                # 本机无 LibreOffice：直接就绪，打开时走前端内置 PPTX 预览兜底
                conn.execute("UPDATE books SET canonical_status = 'none', convert_status = 'none' WHERE id = ?", (book_id,))
                conn.commit()
                conn.close()
        else:
            conn.execute("UPDATE books SET canonical_status = 'none', convert_status = 'none' WHERE id = ?", (book_id,))
            conn.commit()
            conn.close()

    if request.form.get('set_default') == '1':
        conn = get_db()
        conn.execute(
            'INSERT OR REPLACE INTO user_prefs (user_id, key, value) VALUES (?, ?, ?)',
            (g.current_user['id'], 'import_defaults', json.dumps(options, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()

    conn = get_db()
    row = conn.execute('SELECT * FROM books WHERE id = ?', (book_id,)).fetchone()
    conn.close()
    if manifest:
        summary = {
            'sections': len(manifest['sections']),
            'encoding': manifest.get('import_options', {}).get('encoding'),
            'title': manifest.get('title') or title,
        }
    return json_response(data={'book': _book_dict(row, manifest), 'summary': summary})


@books_bp.route('/api/import/defaults', methods=['GET', 'PUT'])
@require_auth
def import_defaults():
    conn = get_db()
    if request.method == 'GET':
        row = conn.execute(
            "SELECT value FROM user_prefs WHERE user_id = ? AND key = 'import_defaults'",
            (g.current_user['id'],),
        ).fetchone()
        conn.close()
        try:
            return json_response(data=json.loads(row['value']) if row else {})
        except (ValueError, TypeError):
            return json_response(data={})
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {k: v for k, v in request.form.items() if k in ('title', 'author', 'note')}
    options = {k: body[k] for k in _IMPORT_KEYS if k in body}
    conn.execute(
        'INSERT OR REPLACE INTO user_prefs (user_id, key, value) VALUES (?, ?, ?)',
        (g.current_user['id'], 'import_defaults', json.dumps(options, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()
    return json_response(data=options)


@books_bp.route('/api/books/<int:book_id>', methods=['GET'])
@require_auth
def book_detail(book_id):
    row = _get_book(book_id)
    if not row:
        return json_response(code=404, message='书籍不存在')
    manifest = None
    if Config.FORMAT_KIND.get(row['format']) == 'canonical':
        try:
            manifest = _ensure_canonical(row)
        except (ValueError, Exception):
            manifest = load_manifest(book_id)
    return json_response(data=_book_dict(row, manifest))


@books_bp.route('/api/books/<int:book_id>', methods=['PUT'])
@require_auth
def book_update(book_id):
    row = _get_book(book_id)
    if not row:
        return json_response(code=404, message='书籍不存在')
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {k: v for k, v in request.form.items() if k in ('title', 'author', 'note')}
    fields = []
    values = []
    for key in ('title', 'author', 'note'):
        if key in body:
            fields.append('%s = ?' % key)
            values.append(str(body[key])[:200])
    cover_file = request.files.get('cover')
    if cover_file and cover_file.filename:
        user_dir = os.path.join(Config.UPLOAD_FOLDER, str(g.current_user['id']))
        os.makedirs(user_dir, exist_ok=True)
        cover_name = 'cover_%d_%s' % (book_id, secure_filename(cover_file.filename) or 'cover.png')
        cover_path = os.path.join(user_dir, cover_name)
        cover_file.save(cover_path)
        fields.append('cover_path = ?')
        values.append(cover_path)
    if fields:
        values.append(book_id)
        conn = get_db()
        conn.execute('UPDATE books SET %s WHERE id = ?' % ', '.join(fields), values)
        conn.commit()
        conn.close()
    return json_response(message='已保存')


def _delete_book_row(row):
    # 单删与批删共用的清理逻辑：删库记录、清规范书目录与磁盘文件
    # rss_items 建表已带 ON DELETE CASCADE（get_db 已开启 PRAGMA foreign_keys=ON），
    # 这里仍显式删除一次，防御外键未生效时残留
    conn = get_db()
    conn.execute('DELETE FROM rss_items WHERE book_id = ?', (row['id'],))
    conn.execute('DELETE FROM books WHERE id = ?', (row['id'],))
    conn.commit()
    conn.close()
    remove_canonical(row['id'])
    try:
        if row['convert_path'] and os.path.exists(row['convert_path']):
            os.remove(row['convert_path'])
    except OSError:
        pass
    try:
        if row['file_path'] and os.path.exists(row['file_path']):
            os.remove(row['file_path'])
    except OSError:
        pass


@books_bp.route('/api/books/<int:book_id>', methods=['DELETE'])
@require_auth
def book_delete(book_id):
    row = _get_book(book_id)
    if not row:
        return json_response(code=404, message='书籍不存在')
    _delete_book_row(row)
    return json_response(message='已删除')


def _parse_id_list(raw):
    # 提取合法 id 列表：仅保留可转整数的元素并去重（排除 bool）
    ids = []
    for item in raw:
        if isinstance(item, bool):
            continue
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return list(dict.fromkeys(ids))


@books_bp.route('/api/books/batch-move', methods=['POST'])
@require_auth
def batch_move_books():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get('ids'), list):
        return json_response(code=400, message='参数 ids 必须为列表')
    ids = _parse_id_list(body['ids'])
    group_id = body.get('group_id')
    if group_id is not None:
        if isinstance(group_id, bool):
            return json_response(code=400, message='分组不存在')
        try:
            group_id = int(group_id)
        except (TypeError, ValueError):
            return json_response(code=400, message='分组不存在')
        # 分组必须存在且归属当前用户
        if not _fetch_group(group_id):
            return json_response(code=400, message='分组不存在')
    moved = 0
    if ids:
        placeholders = ', '.join('?' for _ in ids)
        conn = get_db()
        # group_id 为 None 时绑定为 SQL NULL，即移出分组
        # 非本人的书籍因 AND user_id = ? 被忽略，不计入 moved
        cur = conn.execute(
            'UPDATE books SET group_id = ? WHERE id IN (%s) AND user_id = ?' % placeholders,
            [group_id] + ids + [g.current_user['id']],
        )
        moved = cur.rowcount
        conn.commit()
        conn.close()
    return json_response(data={'moved': moved})


@books_bp.route('/api/books/batch-delete', methods=['POST'])
@require_auth
def batch_delete_books():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get('ids'), list):
        return json_response(code=400, message='参数 ids 必须为列表')
    deleted = 0
    # 逐本经 _get_book 校验归属，非本人的书直接跳过，保持与单删一致的清理行为
    for book_id in _parse_id_list(body['ids']):
        row = _get_book(book_id)
        if row:
            _delete_book_row(row)
            deleted += 1
    return json_response(data={'deleted': deleted})


@books_bp.route('/api/books/<int:book_id>/reparse', methods=['POST'])
@require_auth
def book_reparse(book_id):
    row = _get_book(book_id)
    if not row:
        return json_response(code=404, message='书籍不存在')
    if Config.FORMAT_KIND.get(row['format']) != 'canonical':
        return json_response(code=400, message='该格式无需重新解析')
    remove_canonical(book_id)
    conn = get_db()
    conn.execute("UPDATE books SET canonical_status = 'legacy' WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    try:
        fresh = _get_book(book_id)
        manifest = _ensure_canonical(fresh)
    except ValueError as e:
        return json_response(code=400, message=str(e))
    except Exception:
        return json_response(code=500, message='重新解析失败，请检查文件是否损坏')
    return json_response(data={'sections': len(manifest['sections'])})


@books_bp.route('/api/books/<int:book_id>/manifest', methods=['GET'])
@require_auth
def book_manifest(book_id):
    row = _get_book(book_id)
    if not row:
        return json_response(code=404, message='书籍不存在')
    kind = Config.FORMAT_KIND.get(row['format'])
    if kind == 'canonical':
        try:
            manifest = _ensure_canonical(row)
        except ValueError as e:
            return json_response(code=400, message=str(e))
        except Exception:
            return json_response(code=500, message='书籍解析失败，请重新上传')
        if manifest is None:
            return json_response(code=500, message='规范书缺失，请重新上传')
        manifest = dict(manifest)
        manifest['book_title'] = row['title']
        return json_response(data=manifest)
    if kind in ('native', 'pdf', 'pptx'):
        convert_status = row['convert_status'] or 'none'
        if row['format'] in ('pptx', 'ppt') and convert_status == 'done' \
                and row['convert_path'] and os.path.exists(row['convert_path']):
            return json_response(data={
                'format': 'pdf',
                'file_url': '/api/books/%d/converted' % book_id,
                'book_title': row['title'],
                'convert_status': 'done',
            })
        return json_response(data={
            'format': row['format'],
            'file_url': '/api/books/%d/file' % book_id,
            'book_title': row['title'],
            'convert_status': convert_status,
        })
    return json_response(code=400, message=_format_unsupported_message(row['format']))


@books_bp.route('/api/books/<int:book_id>/section/<int:n>', methods=['GET'])
@require_auth
def book_section(book_id, n):
    row = _get_book(book_id)
    if not row:
        return json_response(code=404, message='书籍不存在')
    if Config.FORMAT_KIND.get(row['format']) != 'canonical':
        return json_response(code=400, message='该格式不支持分节阅读')
    try:
        _ensure_canonical(row)
    except ValueError as e:
        return json_response(code=400, message=str(e))
    etag = section_etag(book_id, n)
    if etag and request.headers.get('If-None-Match') == etag:
        return Response(status=304)
    html = read_section(book_id, n)
    if html is None:
        return json_response(code=404, message='章节不存在')
    resp = Response(html, mimetype='text/html; charset=utf-8')
    if etag:
        resp.headers['ETag'] = etag
    return resp


@books_bp.route('/api/books/<int:book_id>/asset/<path:name>', methods=['GET'])
@require_auth
def book_asset(book_id, name):
    if not _get_book(book_id):
        return json_response(code=404, message='书籍不存在')
    path = asset_path(book_id, name)
    if not path:
        return json_response(code=404, message='资源不存在')
    return send_file(path)


@books_bp.route('/api/books/<int:book_id>/cover', methods=['GET'])
@require_auth
def book_cover(book_id):
    row = _get_book(book_id)
    if not row:
        return json_response(code=404, message='书籍不存在')
    manifest = load_manifest(book_id) if row['canonical_status'] == 'ready' else None
    if manifest and manifest.get('cover'):
        name = manifest['cover'].rsplit('/', 1)[-1]
        path = asset_path(book_id, name)
        if path:
            return send_file(path)
    if row['cover_path'] and os.path.exists(row['cover_path']):
        return send_file(row['cover_path'])
    return json_response(code=404, message='无封面')


@books_bp.route('/api/books/by-fp/<fingerprint>', methods=['GET'])
@require_auth
def book_by_fingerprint(fingerprint):
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM books WHERE user_id = ? AND fingerprint = ?',
        (g.current_user['id'], fingerprint),
    ).fetchone()
    conn.close()
    if not row:
        return json_response(code=404, message='书籍不存在')
    return json_response(data=_book_dict(row))


@books_bp.route('/api/books/<int:book_id>/file', methods=['GET'])
@require_auth
def book_file(book_id):
    row = _get_book(book_id)
    if not row:
        return json_response(code=404, message='书籍不存在')
    if not row['file_path'] or not os.path.exists(row['file_path']):
        return json_response(code=404, message='原文件不存在')
    return send_file(row['file_path'], as_attachment=False)


@books_bp.route('/api/books/<int:book_id>/converted', methods=['GET'])
@require_auth
def book_converted(book_id):
    row = _get_book(book_id)
    if not row:
        return json_response(code=404, message='书籍不存在')
    if (row['convert_status'] or 'none') != 'done' \
            or not row['convert_path'] or not os.path.exists(row['convert_path']):
        return json_response(code=404, message='转换文件不存在')
    return send_file(row['convert_path'], as_attachment=False, mimetype='application/pdf')


@books_bp.route('/api/books/<int:book_id>/download', methods=['GET'])
@require_auth
def book_download(book_id):
    row = _get_book(book_id)
    if not row:
        return json_response(code=404, message='书籍不存在')
    if not row['file_path'] or not os.path.exists(row['file_path']):
        return json_response(code=404, message='原文件不存在')
    download_name = '%s.%s' % (secure_filename(row['title']) or 'book', row['format'])
    return send_file(row['file_path'], as_attachment=True, download_name=download_name)


@books_bp.route('/api/reading/<int:book_id>/settings', methods=['GET'])
@require_auth
def reading_settings_get(book_id):
    conn = get_db()
    row = conn.execute(
        'SELECT * FROM reading_settings WHERE user_id = ? AND book_id = ?',
        (g.current_user['id'], book_id),
    ).fetchone()
    if row:
        conn.close()
        return json_response(data=dict(row))
    row = conn.execute(
        'SELECT * FROM reading_settings WHERE user_id = ? AND book_id IS NULL',
        (g.current_user['id'],),
    ).fetchone()
    conn.close()
    return json_response(data=dict(row) if row else {})


def _coerce_settings(body):
    out = {}
    for key in _SETTINGS_INT:
        if key in body:
            try:
                out[key] = 1 if body[key] in (True, 'true', '1', 1) else 0 if key in ('indent', 'justify', 'tap_zones') else int(float(body[key]))
            except (TypeError, ValueError):
                pass
    for key in _SETTINGS_FLOAT:
        if key in body:
            try:
                out[key] = float(body[key])
            except (TypeError, ValueError):
                pass
    for key in _SETTINGS_STR:
        if key in body and body[key] is not None:
            out[key] = str(body[key])[:64]
    return out


def _upsert_settings(book_id, values):
    if not values:
        return
    conn = get_db()
    cols = ', '.join(values.keys())
    marks = ', '.join('?' for _ in values)
    params = list(values.values())
    row = conn.execute(
        'SELECT id FROM reading_settings WHERE user_id = ? AND book_id %s' % ('= ?' if book_id else 'IS NULL'),
        ([g.current_user['id'], book_id] if book_id else [g.current_user['id']]),
    ).fetchone()
    if row:
        sets = ', '.join('%s = ?' % k for k in values)
        conn.execute(
            'UPDATE reading_settings SET %s WHERE id = ?' % sets,
            params + [row['id']],
        )
    else:
        # 旧库 color/theme_preset 列可能仍带固定默认值，显式补空串（空 = 跟随主题/书架明暗）
        values.setdefault('background_color', '')
        values.setdefault('text_color', '')
        values.setdefault('theme_preset', '')
        cols = ', '.join(values.keys())
        marks = ', '.join('?' for _ in values)
        params = list(values.values())
        conn.execute(
            'INSERT INTO reading_settings (user_id, book_id, %s) VALUES (?, ?, %s)' % (cols, marks),
            [g.current_user['id'], book_id] + params,
        )
    conn.commit()
    conn.close()


@books_bp.route('/api/reading/<int:book_id>/settings', methods=['PUT'])
@require_auth
def reading_settings_put(book_id):
    row = _get_book(book_id)
    if not row:
        return json_response(code=404, message='书籍不存在')
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {k: v for k, v in request.form.items() if k in ('title', 'author', 'note')}
    values = _coerce_settings(body)
    _upsert_settings(book_id, values)
    return json_response(data=values, message='已保存')


@books_bp.route('/api/reading/settings', methods=['GET', 'PUT'])
@require_auth
def global_reading_settings():
    if request.method == 'GET':
        conn = get_db()
        row = conn.execute(
            'SELECT * FROM reading_settings WHERE user_id = ? AND book_id IS NULL',
            (g.current_user['id'],),
        ).fetchone()
        conn.close()
        return json_response(data=dict(row) if row else {})
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {k: v for k, v in request.form.items() if k in ('title', 'author', 'note')}
    values = _coerce_settings(body)
    _upsert_settings(None, values)
    return json_response(data=values, message='已保存')


@books_bp.route('/api/reading/<int:book_id>/position', methods=['PUT', 'POST'])
@require_auth
def reading_position(book_id):
    row = _get_book(book_id)
    if not row:
        return json_response(code=404, message='书籍不存在')
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {k: v for k, v in request.form.items() if k in ('title', 'author', 'note')}
    try:
        position = float(body.get('position', 0))
    except (TypeError, ValueError):
        position = 0
    position = max(0.0, min(1.0, position))
    chapter_title = str(body.get('chapter_title') or '')[:200]
    pos_data = body.get('position_data')
    pos_json = None
    if isinstance(pos_data, dict):
        pos_json = json.dumps(pos_data, ensure_ascii=False)[:2000]
    elif isinstance(pos_data, str):
        pos_json = pos_data[:2000]
    conn = get_db()
    conn.execute(
        '''UPDATE books SET last_read_position = ?, last_read_chapter = ?,
           position_data = COALESCE(?, position_data) WHERE id = ?''',
        (position, chapter_title, pos_json, book_id),
    )
    conn.commit()
    conn.close()
    return json_response(message='进度已保存')


@books_bp.route('/api/reading/<int:book_id>/bookmarks', methods=['GET', 'POST'])
@require_auth
def bookmarks_route(book_id):
    conn = get_db()
    if request.method == 'GET':
        rows = conn.execute(
            'SELECT * FROM bookmarks WHERE user_id = ? AND book_id = ? ORDER BY created_at DESC',
            (g.current_user['id'], book_id),
        ).fetchall()
        conn.close()
        return json_response(data=[dict(r) for r in rows])
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {k: v for k, v in request.form.items() if k in ('title', 'author', 'note')}
    position = body.get('position_data')
    if isinstance(position, dict):
        position = json.dumps(position, ensure_ascii=False)
    conn.execute(
        'INSERT INTO bookmarks (user_id, book_id, chapter, position, note) VALUES (?, ?, ?, ?, ?)',
        (g.current_user['id'], book_id,
         str(body.get('chapter') or '')[:200],
         str(position if position is not None else body.get('position', 0))[:2000],
         str(body.get('note') or '')[:500]),
    )
    conn.commit()
    conn.close()
    return json_response(message='书签已添加')


@books_bp.route('/api/reading/<int:book_id>/bookmarks/<int:mark_id>', methods=['PUT', 'DELETE'])
@require_auth
def bookmark_modify(book_id, mark_id):
    conn = get_db()
    if request.method == 'PUT':
        body = request.get_json(silent=True) or {}
        note = str(body.get('note') or '')[:500]
        if not note:
            conn.close()
            return json_response(code=400, message='备注不能为空')
        cur = conn.execute(
            'UPDATE bookmarks SET note = ? WHERE id = ? AND user_id = ? AND book_id = ?',
            (note, mark_id, g.current_user['id'], book_id),
        )
        conn.commit()
        conn.close()
        if cur.rowcount == 0:
            return json_response(code=404, message='书签不存在')
        return json_response(message='书签已更新')
    conn.execute(
        'DELETE FROM bookmarks WHERE id = ? AND user_id = ? AND book_id = ?',
        (mark_id, g.current_user['id'], book_id),
    )
    conn.commit()
    conn.close()
    return json_response(message='书签已删除')


@books_bp.route('/api/reading/<int:book_id>/highlights/<int:hl_id>', methods=['PUT', 'DELETE'])
@require_auth
def highlight_modify(book_id, hl_id):
    conn = get_db()
    if request.method == 'PUT':
        body = request.get_json(silent=True) or {}
        note = str(body.get('note') or '')[:500]
        cur = conn.execute(
            'UPDATE highlights SET note = ? WHERE id = ? AND user_id = ? AND book_id = ?',
            (note, hl_id, g.current_user['id'], book_id),
        )
        conn.commit()
        conn.close()
        if cur.rowcount == 0:
            return json_response(code=404, message='标注不存在')
        return json_response(message='标注已更新')
    conn.execute(
        'DELETE FROM highlights WHERE id = ? AND user_id = ? AND book_id = ?',
        (hl_id, g.current_user['id'], book_id),
    )
    conn.commit()
    conn.close()
    return json_response(message='标注已删除')


@books_bp.route('/api/reading/<int:book_id>/highlights', methods=['GET', 'POST'])
@require_auth
def highlights_route(book_id):
    conn = get_db()
    if request.method == 'GET':
        rows = conn.execute(
            'SELECT * FROM highlights WHERE user_id = ? AND book_id = ? ORDER BY created_at DESC',
            (g.current_user['id'], book_id),
        ).fetchall()
        conn.close()
        return json_response(data=[dict(r) for r in rows])
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {k: v for k, v in request.form.items() if k in ('title', 'author', 'note')}
    text = str(body.get('selected_text') or '')[:2000]
    if not text:
        conn.close()
        return json_response(code=400, message='划选内容为空')
    position = body.get('position_data')
    if isinstance(position, dict):
        position = json.dumps(position, ensure_ascii=False)
    conn.execute(
        '''INSERT INTO highlights (user_id, book_id, chapter, selected_text, position, color, note)
           VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (g.current_user['id'], book_id,
         str(body.get('chapter') or '')[:200], text,
         str(position if position is not None else body.get('position', 0))[:2000],
         str(body.get('color') or '#FFE066')[:16],
         str(body.get('note') or '')[:500]),
    )
    conn.commit()
    conn.close()
    return json_response(message='已收藏')


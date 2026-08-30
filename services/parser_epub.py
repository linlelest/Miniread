import posixpath
import re
from html import escape

from bs4 import BeautifulSoup


def _norm(name):
    if not name:
        return ''
    name = name.replace('\\', '/').split('#')[0]
    return posixpath.normpath(name).lstrip('./')


def _ext_of(name, default='jpg'):
    m = re.search(r'\.([a-z0-9]{2,5})$', (name or '').lower())
    return m.group(1) if m else default


def _is_nav_doc(name, media_type='', props='', nav_hrefs=None):
    name = _norm(name)
    base = posixpath.basename(name).lower()
    if props and 'nav' in props:
        return True
    if media_type and 'dtbncx' in media_type:
        return True
    if nav_hrefs is not None and name in nav_hrefs:
        return True
    return base in ('nav.xhtml', 'nav.html', 'toc.xhtml', 'toc.html')


def _looks_like_toc_page(body):
    """链接密度启发式：整页几乎全是链接且文字很少 → 目录页"""
    anchors = body.find_all('a')
    plain = len(' '.join(body.get_text(' ', strip=True).split()))
    link_chars = sum(len(a.get_text('', strip=True)) for a in anchors)
    return len(anchors) >= 3 and plain < 300 and plain and link_chars >= plain * 0.6


def _remap_toc(items, new_index):
    out = []
    for t in items or []:
        s = t.get('section')
        ns = new_index.get(s) if s is not None else None
        children = _remap_toc(t.get('children') or [], new_index)
        if ns is None and not children:
            continue
        out.append({'title': t.get('title', ''), 'section': ns, 'children': children})
    return out


def parse_epub(file_path, store, options):
    try:
        meta, sections, toc, cover = _parse_ebooklib(file_path, store)
    except Exception:
        meta, sections, toc, cover = _parse_zip(file_path, store)
    meta['cover'] = cover
    return meta, sections, toc


def _parse_ebooklib(file_path, store):
    from ebooklib import epub, ITEM_DOCUMENT, ITEM_IMAGE

    book = epub.read_epub(file_path)
    meta = {'title': '', 'author': '', 'language': ''}
    try:
        meta['title'] = (book.get_metadata('DC', 'title') or [('')])[0][0] or ''
        meta['author'] = (book.get_metadata('DC', 'creator') or [('')])[0][0] or ''
        meta['language'] = (book.get_metadata('DC', 'language') or [('')])[0][0] or ''
    except Exception:
        pass

    # 收集目录文档（EPUB3 nav / NCX）
    nav_hrefs = set()
    try:
        for it in book.get_items():
            if _is_nav_doc(it.get_name(), getattr(it, 'media_type', '') or '',
                           getattr(it, 'properties', None) or ''):
                nav_hrefs.add(_norm(it.get_name()))
    except Exception:
        pass

    docs = []
    for entry in book.spine:
        idref = entry[0] if isinstance(entry, (list, tuple)) else entry
        item = book.get_item_with_id(idref)
        if item is None or item.get_type() != ITEM_DOCUMENT:
            continue
        if isinstance(item, epub.EpubNav) or _is_nav_doc(item.get_name(), '', getattr(item, 'properties', None) or '', nav_hrefs):
            continue
        docs.append(item)
    if not docs:
        docs = [it for it in book.get_items_of_type(ITEM_DOCUMENT)
                if not _is_nav_doc(it.get_name(), '', '', nav_hrefs)]
    if not docs:
        docs = list(book.get_items_of_type(ITEM_DOCUMENT))

    images = {}
    for it in book.get_items_of_type(ITEM_IMAGE):
        images[_norm(it.get_name())] = (it.get_content(), _ext_of(it.get_name()))
        images.setdefault(posixpath.basename(_norm(it.get_name())), (it.get_content(), _ext_of(it.get_name())))

    href_index = {}
    for i, doc in enumerate(docs):
        n = _norm(doc.get_name())
        href_index.setdefault(n, i)
        href_index.setdefault(posixpath.basename(n), i)

    cover = None
    try:
        for it in book.get_items():
            props = getattr(it, 'properties', None) or []
            if 'cover-image' in props and it.get_type() == ITEM_IMAGE:
                cover = (it.get_content(), _ext_of(it.get_name()))
                break
    except Exception:
        pass
    if cover is None:
        try:
            cm = book.get_metadata('OPF', 'cover')
            if cm:
                cid = cm[0][1].get('content')
                item = book.get_item_with_id(cid)
                if item is not None:
                    cover = (item.get_content(), _ext_of(item.get_name()))
        except Exception:
            pass
    if cover is None:
        for key, val in images.items():
            if 'cover' in key.lower():
                cover = val
                break

    raw = []
    for i, doc in enumerate(docs):
        soup = BeautifulSoup(doc.get_content(), 'html.parser')
        body = soup.body or soup
        _rewrite_images(body, _norm(doc.get_name()), images, store)
        title = ''
        for h in body.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            t = ' '.join(h.get_text(' ', strip=True).split())
            if t:
                title = t[:80]
                break
        if not title:
            title = '第 %d 节' % (i + 1)
        inner = body.decode_contents() if body.name == 'body' else str(body)
        if not inner.strip():
            continue
        if _looks_like_toc_page(body):
            continue
        raw.append((i, {'title': escape(title), 'html': inner}))

    sections = [s for _, s in raw]
    new_index = {old: new for new, (old, _s) in enumerate(raw)}
    toc = _remap_toc(_conv_toc(getattr(book, 'toc', None) or [], href_index), new_index)
    return meta, sections, toc, cover


def _rewrite_images(container, doc_name, images, store):
    if container is None:
        return
    for img in container.find_all('img'):
        src = img.get('src') or ''
        url = _map_image(src, doc_name, images, store)
        if url:
            img['src'] = url
    for img in container.find_all('image'):
        href = img.get('xlink:href') or img.get('href') or ''
        url = _map_image(href, doc_name, images, store)
        if url:
            img['href'] = url
            if img.get('xlink:href'):
                img['xlink:href'] = url


def _map_image(href, doc_name, images, store):
    if not href or href.startswith(('http:', 'https:', 'data:')):
        return None
    target = posixpath.normpath(posixpath.join(posixpath.dirname(doc_name), _norm(href)))
    hit = images.get(target) or images.get(posixpath.basename(target)) or images.get(_norm(href))
    if not hit:
        return None
    return store.add(hit[0], hit[1])


def _href_section(href, href_index):
    if not href:
        return None
    n = _norm(href)
    return href_index.get(n) or href_index.get(posixpath.basename(n))


def _conv_toc(entries, href_index):
    out = []
    for ent in entries or []:
        if isinstance(ent, tuple):
            sec, children = ent
            node = {
                'title': (getattr(sec, 'title', '') or '')[:80],
                'section': _href_section(getattr(sec, 'href', ''), href_index),
                'children': _conv_toc(children, href_index),
            }
            if node['section'] is not None or node['children']:
                out.append(node)
        else:
            n = _href_section(getattr(ent, 'href', ''), href_index)
            if n is not None:
                out.append({'title': (getattr(ent, 'title', '') or '')[:80], 'section': n, 'children': []})
    return out


def _parse_zip(file_path, store):
    import zipfile
    import xml.etree.ElementTree as ET

    zf = zipfile.ZipFile(file_path)
    names = set(zf.namelist())

    def read(name):
        return zf.read(name) if name in names else b''

    def local(tag):
        return tag.rsplit('}', 1)[-1]

    container = ET.fromstring(read('META-INF/container.xml'))
    opf_path = ''
    for el in container.iter():
        if local(el.tag) == 'rootfile':
            opf_path = el.get('full-path')
            break
    if not opf_path:
        raise ValueError('EPUB 缺少 OPF')

    opf = ET.fromstring(read(opf_path))
    base = posixpath.dirname(_norm(opf_path))
    manifest = {}
    spine_ids = []
    ncx_id = ''
    for el in opf.iter():
        t = local(el.tag)
        if t == 'item':
            manifest[el.get('id')] = {
                'href': el.get('href') or '',
                'type': el.get('media-type') or '',
                'props': el.get('properties') or '',
            }
        elif t == 'itemref':
            spine_ids.append(el.get('idref'))
        elif t == 'spine':
            ncx_id = el.get('toc') or ''

    def full(href):
        return posixpath.normpath(posixpath.join(base, _norm(href)))

    images = {}
    for id, info in manifest.items():
        if 'image' in info['type']:
            data = read(full(info['href']))
            if data:
                images[_norm(info['href'])] = (data, _ext_of(info['href']))
                images.setdefault(posixpath.basename(_norm(info['href'])), (data, _ext_of(info['href'])))

    docs = []
    for idref in spine_ids:
        info = manifest.get(idref)
        if not info:
            continue
        if not ('html' in info['type'] or info['href'].endswith(('.xhtml', '.html', '.htm'))):
            continue
        if _is_nav_doc(info['href'], info['type'], info['props']):
            continue
        docs.append(info)

    href_index = {}
    for i, info in enumerate(docs):
        n = _norm(info['href'])
        href_index.setdefault(full(info['href']), i)
        href_index.setdefault(n, i)
        href_index.setdefault(posixpath.basename(n), i)

    cover = None
    for id, info in manifest.items():
        if 'cover-image' in info['props']:
            data = read(full(info['href']))
            if data:
                cover = (data, _ext_of(info['href']))
            break
    if cover is None:
        for el in opf.iter():
            if local(el.tag) == 'meta' and el.get('name') == 'cover':
                info = manifest.get(el.get('content'))
                if info:
                    data = read(full(info['href']))
                    if data:
                        cover = (data, _ext_of(info['href']))
                break

    meta = {'title': '', 'author': '', 'language': ''}
    for el in opf.iter():
        t = local(el.tag)
        if t in ('title', 'creator', 'language') and not meta.get({'title': 'title', 'creator': 'author', 'language': 'language'}[t]):
            meta[{'title': 'title', 'creator': 'author', 'language': 'language'}[t]] = (el.text or '').strip()

    ncx_href = ''
    if ncx_id and ncx_id in manifest:
        ncx_href = manifest[ncx_id]['href']
    else:
        for id, info in manifest.items():
            if 'ncx' in info['type'] or info['href'].endswith('.ncx'):
                ncx_href = info['href']
                break

    toc = []
    if ncx_href:
        try:
            ncx = ET.fromstring(read(full(ncx_href)))

            def walk_points(parent):
                out = []
                for np in parent:
                    if local(np.tag) != 'navPoint':
                        continue
                    label = ''
                    src = ''
                    for c in np.iter():
                        if local(c.tag) == 'navLabel':
                            label = ''.join((c.itertext())).strip()
                        elif local(c.tag) == 'content':
                            src = c.get('src') or ''
                    idx = _href_section(src, href_index)
                    node = {'title': label[:80], 'section': idx, 'children': walk_points(np)}
                    if idx is not None or node['children']:
                        out.append(node)
                return out

            for np in ncx.iter():
                if local(np.tag) == 'navMap':
                    toc = walk_points(np)
        except Exception:
            toc = []

    raw = []
    for i, info in enumerate(docs):
        soup = BeautifulSoup(read(full(info['href'])), 'html.parser')
        body = soup.body or soup
        _rewrite_images(body, full(info['href']), images, store)
        title = ''
        for h in body.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            t = ' '.join(h.get_text(' ', strip=True).split())
            if t:
                title = t[:80]
                break
        if not title:
            title = '第 %d 节' % (i + 1)
        inner = body.decode_contents() if body.name == 'body' else str(body)
        if not inner.strip():
            continue
        if _looks_like_toc_page(body):
            continue
        raw.append((i, {'title': escape(title), 'html': inner}))

    sections = [s for _, s in raw]
    new_index = {old: new for new, (old, _s) in enumerate(raw)}
    toc = _remap_toc(toc, new_index)

    return meta, sections, toc, cover

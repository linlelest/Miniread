import base64
import binascii
import posixpath
import re

from lxml import etree

_XLINK = '{http://www.w3.org/1999/xlink}href'


def _local(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _el_text(el):
    return ' '.join(''.join(el.itertext()).split())


def _href_of(el):
    for k, v in (el.attrib or {}).items():
        if k == _XLINK or k.rsplit('}', 1)[-1] == 'href':
            return v
    return None


def parse_fb2(file_path, store, options):
    parser = etree.XMLParser(recover=True, huge_tree=True)
    tree = etree.parse(file_path, parser)
    root = tree.getroot()

    binaries = {}
    for el in root.iter():
        if _local(el.tag) == 'binary' and el.get('id'):
            binaries[el.get('id')] = (el.get('content-type') or 'image/jpeg', el.text or '')

    meta = {'title': '', 'author': '', 'language': ''}
    cover = None
    for el in root.iter():
        if _local(el.tag) == 'title-info':
            for c in el:
                t = _local(c.tag)
                if t == 'book-title' and not meta['title']:
                    meta['title'] = _el_text(c)
                elif t == 'lang' and not meta['language']:
                    meta['language'] = _el_text(c)
                elif t == 'author' and not meta['author']:
                    names = [_el_text(x) for x in c if _local(x.tag) in ('first-name', 'middle-name', 'last-name')]
                    meta['author'] = ' '.join(n for n in names if n)
                elif t == 'coverpage' and cover is None:
                    href = _image_href(c)
                    if href:
                        cover = _decode_binary(binaries, href, store)
            break

    body = None
    for el in root.iter():
        if _local(el.tag) == 'body' and (el.get('name') or '') != 'notes':
            body = el
            break
    if body is None:
        raise ValueError('FB2 缺少正文 body')

    sections = []
    top_sections = [c for c in body if _local(c.tag) == 'section']
    if top_sections:
        for i, sec in enumerate(top_sections):
            title = ''
            for c in sec:
                if _local(c.tag) == 'title':
                    title = _el_text(c)[:80]
                    break
            html_parts = []
            for c in sec:
                if _local(c.tag) == 'title':
                    continue
                html_parts.append(_render(c, binaries, store))
            html = ''.join(html_parts)
            if html.strip():
                sections.append({'title': title or ('第 %d 节' % (i + 1)), 'html': html})
    else:
        html = ''.join(_render(c, binaries, store) for c in body)
        if html.strip():
            sections.append({'title': meta['title'] or '全文', 'html': html})

    toc = [{'title': s['title'], 'section': i, 'children': []} for i, s in enumerate(sections)]
    meta['cover'] = cover
    return meta, sections, toc


def _image_href(el):
    if el is None:
        return None
    if _local(el.tag) == 'image':
        return _href_of(el)
    for x in el.iter():
        if x is not el and _local(x.tag) == 'image':
            return _href_of(x)
    return None


def _decode_binary(binaries, href, store):
    if not href:
        return None
    bid = href.lstrip('#')
    hit = binaries.get(bid)
    if not hit:
        return None
    ct, b64 = hit
    try:
        data = base64.b64decode(re.sub(r'\s+', '', b64))
    except (binascii.Error, ValueError):
        return None
    if not data:
        return None
    ext = (ct.split('/')[-1] if '/' in ct else ct).split(';')[0].lower()
    if ext not in ('png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'):
        ext = 'jpg'
    return data, ('jpg' if ext == 'jpeg' else ext)


def _render(el, binaries, store):
    t = _local(el.tag)
    if t == 'image':
        url = _register_image(binaries, _href_of(el), store)
        return '<img src="%s" alt=""/>' % url if url else ''
    if t == 'p':
        inner = _inline(el, binaries, store)
        return '<p>%s</p>' % (inner or '&#160;')
    if t == 'empty-line':
        return '<p class="blank">&#160;</p>'
    if t in ('poem', 'stanza'):
        lines = []
        for c in el.iter():
            if _local(c.tag) == 'v':
                lines.append(_inline(c, binaries, store) or '&#160;')
        if lines:
            return '<div class="poem">%s</div>' % ''.join('<p>%s</p>' % l for l in lines)
        return ''
    if t == 'subtitle':
        return '<p class="subtitle">%s</p>' % _inline(el, binaries, store)
    if t == 'epigraph':
        return '<blockquote>%s</blockquote>' % ''.join(_render(c, binaries, store) for c in el)
    if t == 'cite':
        return '<blockquote>%s</blockquote>' % ''.join(_render(c, binaries, store) for c in el)
    if t in ('text-field', 'table'):
        return ''
    if t == 'title':
        return ''
    return _inline(el, binaries, store)


def _inline(el, binaries, store):
    parts = []
    if el.text:
        parts.append(_esc(el.text))
    for c in el:
        t = _local(c.tag)
        inner = _inline(c, binaries, store)
        if t == 'strong':
            parts.append('<strong>%s</strong>' % inner)
        elif t == 'emph':
            parts.append('<em>%s</em>' % inner)
        elif t == 'a':
            href = _href_of(c) or '#'
            parts.append('<a href="#" data-href="%s">%s</a>' % (_esc(href), inner or '&#160;'))
        elif t == 'note':
            parts.append('<sup>%s</sup>' % inner)
        elif t == 'style':
            parts.append('<span>%s</span>' % inner)
        elif t == 'image':
            url = _register_image(binaries, _href_of(c), store)
            if url:
                parts.append('<img src="%s" alt=""/>' % url)
        elif t == 'empty-line':
            parts.append('<br/>')
        else:
            parts.append(inner)
        if c.tail:
            parts.append(_esc(c.tail))
    return ''.join(parts)


def _esc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _register_image(binaries, href, store):
    if not href or href.startswith(('http:', 'https:', 'data:')):
        return None
    bid = posixpath.basename(href.lstrip('#'))
    hit = binaries.get(bid)
    if not hit:
        return None
    ct, b64 = hit
    try:
        data = base64.b64decode(re.sub(r'\s+', '', b64))
    except (binascii.Error, ValueError):
        return None
    if not data:
        return None
    ext = (ct.split('/')[-1] if '/' in ct else ct).split(';')[0].lower()
    if ext not in ('png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'):
        ext = 'jpg'
    return store.add(data, 'jpg' if ext == 'jpeg' else ext)

from bs4 import BeautifulSoup

_HEADING_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']


def _heading_names(level):
    level = max(1, min(6, int(level or 2)))
    return set(_HEADING_TAGS[:level])


def _flatten_containers(soup, names):
    for _ in range(3):
        tops = [c for c in soup.children if getattr(c, 'name', None)]
        if any(c.name in names for c in tops):
            return
        for c in tops:
            if c.name in ('div', 'section', 'article', 'main', 'body'):
                c.unwrap()
            else:
                c.extract()


def split_html(html, level=2):
    soup = BeautifulSoup(html or '', 'html.parser')
    names = _heading_names(level)
    _flatten_containers(soup, names)
    tops = [c for c in soup.children if getattr(c, 'name', None)]
    heads = [c for c in tops if c.name in names]
    if not heads:
        return []

    sections = []
    for i, head in enumerate(heads):
        title = ' '.join(head.get_text(' ', strip=True).split())[:80] or ('第 %d 节' % (i + 1))
        parts = []
        node = head.next_sibling
        stop = heads[i + 1] if i + 1 < len(heads) else None
        while node is not None and node is not stop:
            if getattr(node, 'name', None):
                parts.append(str(node.extract()))
            elif isinstance(node, str) and node.strip():
                parts.append('<p>%s</p>' % node.strip())
            node = node.next_sibling
        body = ''.join(parts)
        sections.append({'title': title, 'html': '<h%d>%s</h%d>%s' % (min(int(head.name[1]), 6), head.get_text(' ', strip=True), min(int(head.name[1]), 6), body)})
    return sections

import re

from bs4 import BeautifulSoup, Comment

_REMOVE_TAGS = ['script', 'style', 'iframe', 'object', 'embed', 'link', 'meta', 'form', 'base']
_EVENT_ATTR = re.compile(r'^on', re.I)
_SAFE_URL = re.compile(r'\s*(javascript|vbscript|data(?!:image/))', re.I)


def _clean_attrs(tag):
    for name in list(tag.attrs):
        if _EVENT_ATTR.match(name):
            del tag.attrs[name]
            continue
        if name in ('href', 'src', 'xlink:href', 'srcset', 'action', 'formaction') and name in tag.attrs:
            val = tag.attrs[name]
            if isinstance(val, list):
                val = ' '.join(val)
            if isinstance(val, str) and _SAFE_URL.match(val.strip()):
                tag.attrs[name] = '#'


def sanitize_fragment(html):
    soup = BeautifulSoup(html or '', 'html.parser')
    for t in soup.find_all(_REMOVE_TAGS):
        t.decompose()
    for c in soup.find_all(string=lambda text: isinstance(text, Comment)):
        c.extract()
    for t in soup.find_all(True):
        _clean_attrs(t)
    for a in soup.find_all('a'):
        href = a.get('href')
        if href and href != '#':
            a['data-href'] = href
        a['href'] = '#'
        if 'target' in a.attrs:
            del a.attrs['target']
    return str(soup)

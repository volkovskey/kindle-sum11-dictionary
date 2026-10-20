"""Ukrainian entries of the Ukrainian Wiktionary (uk.wiktionary.org) as dictionary entries.

parse(dump) reads ukwiktionary-*-pages-articles.xml.bz2 and returns
(entries, form_pages, date):
  entries     list of (headword, display_head, body_html, reference_only) with a
              usable definition; reference_only means every sense only points to
              another word («те саме, що…», «жін. до…»); surnames, first names and
              place names are left out
  form_pages  {lemma: {inflected forms}} from pages that are only a word form
              ({{Форма-ім|база=...}} etc.), to be indexed with their lemma
  date        YYYY-MM-DD of the newest revision in the dump
"""
import bz2, html, re
import xml.etree.ElementTree as ET

LANG = re.compile(r'^(?:=\s*\{\{-([a-z-]+)-\}\}\s*=|\{\{=([a-z-]+)=[^\n]*)', re.M)
SECTION = re.compile(r'^(=+)\s*([^=\n]+?)\s*\1\s*$', re.M)
FORM_TEMPLATES = ('Форма-ім', 'Форма-дієсл', 'Форма-прикм', 'Форма-займ', 'Форма-числ')
WORD = re.compile(r"[А-ЩЬЮЯҐЄІЇа-щьюяґєії’'ʼ-]+")

# templates whose rendering is "<label> <first argument>"
REFERRING = {
    'те саме': 'те саме, що',
    'дія': 'дія за знач.',
    'діястан': 'дія і стан за знач.',
    'змп': 'зменш.-пестл. до',
    'жін. ім.': 'жін. до',
    'абстр. ім.': 'абстр. ім. до',
    'властивість': 'властивість за знач.',
    'прислівник': 'присл. до',
    'дієприкм.': 'дієприкм. до',
    'скор.': 'скороч. від',
}
LABEL_ALIASES = {'тмн': 'мн.', 'тодн.': 'тільки одн.'}
# templates that carry no text worth showing
DROP = {'семантика', 'списки семантичних зв’язків', 'іл', 'ГРАК', 'СУМ', 'СУМ20', 'ВТССУМ'}
POS = {'імен': 'ім.', 'дієсл': 'дієсл.', 'прикм': 'прикм.', 'присл': 'присл.',
       'займ': 'займ.', 'числ': 'числ.', 'числів': 'числ.', 'вигук': 'виг.', 'спол': 'спол.',
       'прийм': 'прийм.', 'част': 'част.', 'дієприкм': 'дієприкм.'}
GENDER = {'m': 'ч.', 'f': 'ж.', 'n': 'с.'}


def split_top(s, sep='|'):
    """Split on `sep` outside nested {{ }} and [[ ]]."""
    out, depth, cur, i = [], 0, [], 0
    while i < len(s):
        two = s[i:i + 2]
        if two in ('{{', '[['):
            depth += 1; cur.append(two); i += 2; continue
        if two in ('}}', ']]') and depth:
            depth -= 1; cur.append(two); i += 2; continue
        if s[i] == sep and not depth:
            out.append(''.join(cur)); cur = []; i += 1; continue
        cur.append(s[i]); i += 1
    out.append(''.join(cur))
    return out


def find_templates(s):
    """Yield (start, end) of top-level {{...}} in s."""
    depth, start, i = 0, None, 0
    while i < len(s):
        if s.startswith('{{', i):
            if depth == 0:
                start = i
            depth += 1; i += 2; continue
        if s.startswith('}}', i) and depth:
            depth -= 1; i += 2
            if depth == 0:
                yield start, i
            continue
        i += 1


def args_of(body):
    parts = split_top(body)
    name = parts[0].strip()
    pos, named = [], {}
    for p in parts[1:]:
        k, eq, v = p.partition('=')
        if eq and re.fullmatch(r'[\w .-]+', k.strip()):
            named[k.strip()] = v.strip()
        else:
            pos.append(p.strip())
    return name, pos, named


class Renderer:
    def __init__(self):
        self.examples = []

    def text(self, s):
        """Wikitext fragment -> HTML; examples are collected in self.examples."""
        s = re.sub(r'<!--.*?-->', '', s, flags=re.S)
        s = re.sub(r'<ref[^>]*/>|<ref[^>]*>.*?</ref>', '', s, flags=re.S)
        out, last = [], 0
        for a, b in find_templates(s):
            out.append(self.inline(s[last:a]))
            out.append(self.template(s[a + 2:b - 2]))
            last = b
        out.append(self.inline(s[last:]))
        return ''.join(out)

    def inline(self, s):
        s = html.unescape(s.replace('&nbsp;', ' '))
        s = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', s)
        s = re.sub(r'\[https?://\S+ ([^\]]*)\]', r'\1', s)
        s = re.sub(r'<[^>]+>', '', s)
        s = html.escape(s, quote=False)
        s = re.sub(r"'''''(.*?)'''''", r'<b><i>\1</i></b>', s)
        s = re.sub(r"'''(.*?)'''", r'<b>\1</b>', s)
        s = re.sub(r"''(.*?)''", r'<i>\1</i>', s)
        return s.replace("'''", '').replace("''", '')

    def template(self, body):
        name, pos, named = args_of(body)
        if not name or name in DROP:
            return ''
        if name in ('приклад', 'приклад2'):
            if pos and pos[0].strip():
                quote = self.text(pos[0]).strip()
                src = ', '.join(self.text(x).strip().strip('()') for x in pos[1:4] if x.strip())
                if named.get('автор') and not src:
                    src = self.text(named['автор']).strip()
                self.examples.append(f'<i>{quote}</i>' + (f' ({src})' if src else ''))
            return ''
        if name == 'виділ':
            return f'<b>{self.text(pos[0])}</b>' if pos else ''
        if name == 'позначка':
            return f'<i>{self.text(pos[0]).strip()}</i>' if pos else ''
        if name == 'стос.':
            if not pos:
                return '<i>стос.</i>'
            what = self.text(pos[0]).strip()
            tail = f', пов’язаний з {self.text(pos[1]).strip()}' if len(pos) > 1 and pos[1].strip() else ''
            return f'стосується {what}{tail}'
        if name in REFERRING:
            ref = [p for p in pos if p and p != 'uk']
            word = self.text(ref[-1]).strip() if ref else ''
            return f'{REFERRING[name]} <b>{word}</b>' if word else f'<i>{REFERRING[name]}</i>'
        if name == '-':
            return ' — '
        if name in LABEL_ALIASES:
            return f'<i>{LABEL_ALIASES[name]}</i>'
        # bare labels such as {{розм.}}, {{перен.|uk}}, {{діал.}}
        if all(p in ('', 'uk') for p in pos) and not named and len(name) <= 16 and not name[0].isupper():
            return f'<i>{html.escape(name)}</i>'
        return ''


def clean_spaces(s):
    # unbalanced templates in the source: cut at the first one, drop stray braces
    s = re.sub(r'[{}]+', '', s.split('{{')[0])
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'\s+([.,;:!?)])', r'\1', s)
    return s.strip()


def has_letters(h):
    return len(re.findall(r'[а-яґєіїa-z]', re.sub(r'<i>.*?</i>|<[^>]+>', '', h), re.I)) >= 3


def sections(text):
    """[(title, body)] of the (sub)sections of one language section."""
    ms = list(SECTION.finditer(text))
    return [(m.group(2).strip(), text[m.end():ms[i + 1].start() if i + 1 < len(ms) else len(text)])
            for i, m in enumerate(ms)]


def numbered(body):
    # a template may span several lines: keep it on its definition line
    flat, depth, i = [], 0, 0
    while i < len(body):
        if body.startswith('{{', i):
            depth += 1; flat.append('{{'); i += 2; continue
        if body.startswith('}}', i) and depth:
            depth -= 1; flat.append('}}'); i += 2; continue
        flat.append(' ' if body[i] == '\n' and depth else body[i]); i += 1
    return [l for l in ''.join(flat).split('\n') if re.match(r'#(?![:*])', l)]


# senses that make an entry an onomastic one (surname, first name, settlement, ...)
PROPER = re.compile(r"прізвище|ім[’'ʼ]я|по батькові|населен|\bсел[оа]\b|селище|місто|містечко|хутір|річка|озеро|"
                    r"район|громад|област|планета|астероїд|клуб|футбол")


def is_onomastic(title, body):
    senses = [re.sub(r'<[^>]+>', '', s) for s in re.findall(r'<p>(?:\d+\. )?(.*?)</p>', body)]
    senses = [s for s in senses if s and not re.fullmatch(r'(ім|прикм|дієсл)\..*', s)]
    return title[:1].isupper() and all(PROPER.search(s) for s in senses)


def head_and_pos(text, title):
    """Stressed spelling of the headword and a part-of-speech label."""
    head = title
    m = re.search(r'\{\{склади\|([^{}]*)\}\}', text)
    if m:
        cand = ''.join(p for p in m.group(1).split('|') if p not in ('.', '-', '') and '=' not in p)
    else:
        m = re.search(r'склади=([^|{}\n]+)', text)
        cand = m.group(1).replace('-', '').strip() if m else ''
    if cand and cand.replace('́', '').lower() == title.lower():
        head = cand
    label = ''
    m = re.search(r'\{\{(імен|дієсл|прикм|присл|займ|числ|числів|вигук|спол|прийм|част|дієприкм)[ \w]* uk\b([^|}]*)', text)
    if m:
        label = POS[m.group(1)]
        g = re.search(r'\b([mfn])\b', m.group(2))
        if m.group(1) == 'імен' and g:
            label += ' ' + GENDER[g.group(1)]
        if m.group(1) == 'дієсл':
            if ' нед' in m.group(0):
                label += ' недок.'
            elif ' док' in m.group(0):
                label += ' док.'
    return head, label


def render_entry(title, text):
    """HTML body for one Ukrainian section, or None when it has no definition."""
    secs = sections(text)
    senses, syns = [], []
    for name, body in secs:
        if name == 'Значення':
            senses.append(numbered(body))
        elif name == 'Синоніми':
            syns.append(numbered(body))
    head, pos = head_and_pos(text, title)
    parts, n_ok, n_ref = [], 0, 0
    if pos:
        parts.append(f'<p><i>{pos}</i></p>')
    for bi, block in enumerate(senses):
        syn_block = syns[bi] if bi < len(syns) else []
        items = []
        for li, line in enumerate(block):
            sub = line.startswith('##')
            r = Renderer()
            d = clean_spaces(r.text(line.lstrip('#')))
            d = d.strip(' .;') + '.' if has_letters(d) else ''
            syn = ''
            if not sub and li < len(syn_block):
                s = clean_spaces(Renderer().text(syn_block[li].lstrip('#'))).strip(' .—-')
                if has_letters(s):
                    syn = s
            if d:
                n_ok += 1
                if re.sub(r'^(<i>[^<]*</i>[,\s]*)+', '', d).startswith(tuple(REFERRING.values())):
                    n_ref += 1
            if d or r.examples:
                items.append((sub, d, r.examples, syn))
        num = 0
        for sub, d, exs, syn in items:
            if not sub:
                num += 1
            prefix = '' if sub or len([x for x in items if not x[0]]) == 1 else f'{num}. '
            if d:
                parts.append(f'<p>{prefix}{d}</p>')
            elif exs:
                parts.append(f'<p>{prefix}</p>' if prefix else '')
            parts += [f'<p class="ex">{e}</p>' for e in exs]
            if syn:
                parts.append(f'<p class="ex">Син.: {syn}</p>')
    if not n_ok:
        return None
    return head, ''.join(balanced(p) for p in parts if p), n_ref == n_ok


def balanced(p):
    """Drop <b>/<i> from a paragraph whose tags are not properly nested."""
    stack = []
    for close, tag in re.findall(r'<(/?)([bi])>', p):
        if not close:
            stack.append(tag)
        elif not stack or stack.pop() != tag:
            break
    else:
        if not stack:
            return p
    return re.sub(r'</?[bi]>', '', p)


def parse(dump):
    entries, form_pages, date = [], {}, ''
    for _, el in ET.iterparse(bz2.open(dump), events=('end',)):
        if not el.tag.endswith('}page'):
            continue
        title, ns = el.findtext('{*}title'), el.findtext('{*}ns')
        text = el.findtext('{*}revision/{*}text') or ''
        date = max(date, (el.findtext('{*}revision/{*}timestamp') or '')[:10])
        el.clear()
        if ns != '0' or not WORD.fullmatch(title or ''):
            continue
        ms = list(LANG.finditer(text))
        for i, m in enumerate(ms):
            if (m.group(1) or m.group(2)) != 'uk':
                continue
            sec = text[m.start():ms[i + 1].start() if i + 1 < len(ms) else len(text)]
            f = re.search(r'\{\{(' + '|'.join(FORM_TEMPLATES) + r')\b[^{}]*?база\s*=\s*([^|}\n]+)', sec)
            if f:
                form_pages.setdefault(f.group(2).strip().replace('́', ''), set()).add(title)
                continue
            r = render_entry(title, sec)
            if r and not is_onomastic(title, r[1]):
                entries.append((title, *r))
    return entries, form_pages, date

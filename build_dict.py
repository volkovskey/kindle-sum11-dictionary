"""Build Kindle dictionary source (OPF + HTML) from SUM-11 and/or the Ukrainian Wiktionary.

usage: python3 -I build_dict.py --mode MODE --sum <tabfile> --wiki <dump.xml.bz2> <outdir>
       NO_INFL=1 python3 -I build_dict.py ...   # headwords only, no word forms

Writes <outdir>/<name>/dict.opf (+ HTML) for each mode; MODE is "all" or one of
  sum11        SUM-11 only
  wiki         Ukrainian Wiktionary only
  sum11+wiki   SUM-11, plus Wiktionary entries for words SUM-11 lacks
  wiki+sum11   Wiktionary, plus SUM-11 entries for words Wiktionary lacks

Both sources are always read: the Wiktionary capitalized-entry filter needs
SUM-11's headwords. Compile the result with kindling (not kindlegen, see README):
       kindling-cli build <outdir>/<name>/dict.opf -o <name>.mobi
"""
import sys, os, re, html, argparse
import pymorphy3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python -I leaves it out
import wiktionary

MODES = {
    'sum11': ('СУМ-11: тлумачний словник української мови', 'sum11'),
    'wiki': ('Вікісловник: тлумачний словник української мови', 'wiktionary'),
    'sum11+wiki': ('СУМ-11 + Вікісловник: тлумачний словник', 'sum11-wiktionary'),
    'wiki+sum11': ('Вікісловник + СУМ-11: тлумачний словник', 'wiktionary-sum11'),
}
SOURCE_NAME = {'sum11': 'СУМ-11', 'wiki': 'Вікісловник'}

ap = argparse.ArgumentParser()
ap.add_argument('--mode', choices=[*MODES, 'all'], required=True)
ap.add_argument('--sum', required=True, help='SUM-11 tab file')
ap.add_argument('--wiki', required=True, help='ukwiktionary pages-articles .xml.bz2 dump')
ap.add_argument('out')
args = ap.parse_args()
morph = pymorphy3.MorphAnalyzer(lang='uk')

APOS = ["’", "'", "ʼ"]
MAX_IFORMS = 120
NO_INFL = os.environ.get('NO_INFL') == '1'
VALID = re.compile(r"[а-щьюяґєіїa-z’'ʼ-]+", re.I)
ALPHABET = {c: i for i, c in enumerate("абвгґдеєжзиіїйклмнопрстуфхцчшщьюя")}


def apos_variants(w):
    if not any(a in w for a in APOS):
        return {w}
    base = w
    for a in APOS[1:]:
        base = base.replace(a, "’")
    return {base.replace("’", a) for a in APOS}


def forms_for(word):
    """All inflected forms of `word` (as a lemma) per pymorphy3."""
    q = word.replace("’", "'").replace("ʼ", "'")
    forms = set()
    for p in morph.parse(q):
        if p.normal_form != q.lower():
            continue
        for f in p.lexeme:
            forms.add(f.word)
    out = set()
    for f in forms:
        out |= apos_variants(f)
    return out


def g_forms():
    """Modern ґ-spellings for SUM-11 headwords, which are written with г.

    Maps the г-spelling of every pymorphy3 lemma with ґ to that lemma's
    ґ-forms (just the lemma itself under NO_INFL), so «ґанку» opens «ганок».
    """
    lex = {}
    for f, _, nf, *_ in morph.dictionary.iter_known_words(''):
        if 'ґ' in nf and 'ґ' in f:
            lex.setdefault(nf, set()).update(apos_variants(f))
    out = {}
    for nf, forms in lex.items():
        out.setdefault(nf.replace('ґ', 'г'), set()).update({nf} if NO_INFL else forms)
    return out


def key(w):
    """Spelling-insensitive identity of a headword: stress, apostrophe kind, ґ/г, trailing «…»."""
    w = w.lower().replace('́', '').replace('ґ', 'г').rstrip('…').strip()
    return w.replace("'", "’").replace("ʼ", "’")


def sort_key(w):
    return [ALPHABET.get(c, 100 + ord(c)) for c in key(w) if c not in "’-"]


def clean(v):
    v = v.replace('\\n', '')
    v = re.sub(r'</?font[^>]*>', '', v)
    v = re.sub(r'</?span[^>]*>', '', v)
    v = v.replace('<div style="margin-left:1em">', '<p>')
    v = re.sub(r'<div style="margin-left:\d+em">', '<p class="ex">', v)
    v = v.replace('</div>', '</p>')
    v = re.sub(r'<br\s*>', '<br/>', v)
    return v


def entry(word, head, body, extra_forms):
    word_l = word.lower()
    iforms = set()
    if not word.endswith('…'):
        iforms = forms_for(word_l)
    iforms |= apos_variants(word_l)
    iforms.discard(word_l)
    iforms = sorted(f for f in iforms if VALID.fullmatch(f))[:MAX_IFORMS]
    if NO_INFL:
        iforms = []
    plain_w = word_l.rstrip('…').strip()
    # a book in the older spelling writes г for ґ
    if 'ґ' in plain_w:
        extra_forms = set(extra_forms) | {f.replace('ґ', 'г') for f in [plain_w, *iforms]}
    # extra forms go after the cap so they are never cut off
    iforms += sorted(f for f in extra_forms if VALID.fullmatch(f) and f not in iforms and f != plain_w)
    # Kindle does not lowercase a tapped word for a uk dictionary,
    # so a word at the start of a sentence needs its capitalized form indexed.
    iforms += [c for c in (f[:1].upper() + f[1:] for f in [plain_w] + iforms)
               if c not in (plain_w, *iforms)]
    infl = ''
    if iforms:
        infl = '<idx:infl>' + ''.join(
            f'<idx:iform value="{html.escape(f, quote=True)}"/>' for f in iforms) + '</idx:infl>'
    w = html.escape(plain_w, quote=True)
    return (f'<idx:entry name="default" scriptable="yes">'
            f'<h5><dt><idx:orth value="{w}">{head}{infl}</idx:orth></dt></h5>'
            f'<dd>{body}</dd><mbp:pagebreak/></idx:entry>\n')


# ---- sources: dicts with word, head (HTML), body (HTML), src, extra (set of forms)

def load_sum(path):
    g = g_forms()
    res = []
    for line in open(path, encoding='utf-8'):
        if line.startswith('##'):
            continue
        k, _, val = line.rstrip('\n').partition('\t')
        if not k or not val:
            continue
        body = clean(val)
        m = re.match(r'<p><b>(.*?)</b>', body)
        for w in (w.strip() for w in k.split('|')):
            if not w:
                continue
            plain = w.lower().rstrip('…').strip()
            res.append(dict(word=w, head=m.group(1) if m else html.escape(plain),
                            body=('<p>' + body[m.end():]) if m else body,
                            src='sum11', extra=set(g.get(plain, ()))))
    return res


def load_wiki(path, sum_entries):
    entries, form_pages, date = wiktionary.parse(path)
    # a capitalized entry («Земля», «Сонце») would take the lookups of the
    # sentence-initial common word, which Kindle searches by exact spelling first
    common = {key(e['word']) for e in sum_entries} | {key(t) for t, *_ in entries if not t[:1].isupper()}
    res = []
    for title, head, body, ref_only in entries:
        if title[:1].isupper() and key(title) in common:
            continue
        forms = set() if NO_INFL else {f.lower() for f in form_pages.get(title, ())}
        res.append(dict(word=title, head=html.escape(head.upper(), quote=False), body=body,
                        src='wiki', extra=forms, weak=ref_only))
    return res, date


def absorb(base, others):
    """`base`, plus the entries of `others` for words `base` lacks.

    A dropped headword whose spelling differs (SUM-11 «ганок» vs Wiktionary
    «ґанок») becomes an extra form of the kept entries, so it still opens something.
    """
    by_key = {}
    for e in base:
        by_key.setdefault(key(e['word']), []).append(e)
    res = list(base)
    for e in others:
        k = key(e['word'])
        if k in by_key:
            spelling = e['word'].lower().rstrip('…').strip()
            for p in by_key[k]:
                if spelling != p['word'].lower().rstrip('…').strip():
                    p['extra'].add(spelling)
        else:
            res.append(e)
    return res


def combine(primary, secondary):
    """All of `primary`, plus `secondary` entries for words `primary` lacks.

    A primary entry that only points to another word («те саме, що ґанок»)
    gives way to a secondary entry for the same word, which is more useful in
    a lookup popup, where references cannot be followed.
    """
    sec_keys = {key(e['word']) for e in secondary}
    weak = [e for e in primary if e.get('weak') and key(e['word']) in sec_keys]
    keep = [e for e in primary if not (e.get('weak') and key(e['word']) in sec_keys)]
    return absorb(absorb(keep, secondary), weak)


HEAD = ('<html xmlns:math="http://exslt.org/math" xmlns:svg="http://www.w3.org/2000/svg" '
        'xmlns:tl="https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf" '
        'xmlns:saxon="http://saxon.sf.net/" xmlns:xs="http://www.w3.org/2001/XMLSchema" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:cx="https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:mbp="https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf" '
        'xmlns:mmc="https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf" '
        'xmlns:idx="https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf">'
        '<head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>'
        '<link rel="stylesheet" href="style.css" type="text/css"/></head><body>'
        '<mbp:frameset>\n')
TAIL = '</mbp:frameset></body></html>\n'
LIMIT = 6 * 1024 * 1024


def write_entries(out, entries, hybrid):
    files, buf, size = [], [], 0

    def flush():
        nonlocal buf, size
        if not buf:
            return
        name = f'content{len(files) + 1:03d}.html'
        with open(os.path.join(out, name), 'w', encoding='utf-8') as fh:
            fh.write(HEAD + ''.join(buf) + TAIL)
        files.append(name)
        buf, size = [], 0

    for n, e in enumerate(entries, 1):
        body = e['body']
        if hybrid:
            body += f'<p><i>— {SOURCE_NAME[e["src"]]}</i></p>'
        x = entry(e['word'], e['head'], body, e['extra'])
        buf.append(x)
        size += len(x.encode('utf-8'))
        if size > LIMIT:
            flush()
        if n % 20000 == 0:
            print('entries', n, file=sys.stderr)
    flush()
    return files


def write_cover(out, title, entries, counts, hybrid, wiki_date):
    about = {
        'sum11': '<p>Словник української мови в 11 томах (АН УРСР, 1970–1980). '
                 'Дані: github.com/bakustarver/ukr-dictionaries-list-opensource</p>',
        'wiki': f'<p>Український Вікісловник (uk.wiktionary.org), стан на {wiki_date}. '
                'Тексти Вікісловника поширюються за ліцензією CC BY-SA 4.0 '
                '(creativecommons.org/licenses/by-sa/4.0), автори — дописувачі Вікісловника.</p>',
    }
    with open(os.path.join(out, 'cover.html'), 'w', encoding='utf-8') as fh:
        fh.write('<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/></head>'
                 f'<body><h1>{title}</h1>'
                 f'<p>Kindle-версія{"" if NO_INFL else " з формами слів"}: {len(entries)} статей'
                 + (f' ({counts["sum11"]} з СУМ-11, {counts["wiki"]} з Вікісловника)' if hybrid else '') + '.</p>'
                 + ''.join(about[s] for s in ('sum11', 'wiki') if counts[s])
                 + '<p>Проєкт: github.com/volkovskey/kindle-sum11-dictionary</p>'
                 '</body></html>\n')


def write_opf(out, flist, title, ident, counts):
    manifest = '\n'.join(
        f'    <item id="c{i}" href="{f}" media-type="application/xhtml+xml"/>' for i, f in enumerate(flist))
    spine = '\n'.join(['    <itemref idref="cover"/>'] +
                      [f'    <itemref idref="c{i}"/>' for i in range(len(flist))])
    guide = '\n'.join(f'    <reference type="index" title="IndexName" href="{f}"/>' for f in flist)
    creators = '\n'.join(f'    <dc:creator>{c}</dc:creator>' for c, s in
                         (('Академія наук УРСР', 'sum11'), ('Дописувачі Вікісловника', 'wiki')) if counts[s])
    rights = '\n    <dc:rights>Тексти Вікісловника: CC BY-SA 4.0</dc:rights>' if counts['wiki'] else ''
    opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package unique-identifier="uid" version="2.0" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">{ident}</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:language>uk</dc:language>
{creators}{rights}
    <x-metadata>
      <DictionaryInLanguage>uk</DictionaryInLanguage>
      <DictionaryOutLanguage>uk</DictionaryOutLanguage>
      <DefaultLookupIndex>default</DefaultLookupIndex>
      <CdeType>DICTIONARY</CdeType>
      <output encoding="UTF-8"/>
    </x-metadata>
  </metadata>
  <manifest>
    <item id="css" href="style.css" media-type="text/css"/>
    <item id="cover" href="cover.html" media-type="application/xhtml+xml"/>
{manifest}
  </manifest>
  <spine>
{spine}
  </spine>
  <guide>
{guide}
  </guide>
</package>
'''
    with open(os.path.join(out, 'dict.opf'), 'w', encoding='utf-8') as fh:
        fh.write(opf)


def build(mode, sum_entries, wiki_entries, wiki_date):
    title, name = MODES[mode]
    # combine() adds forms to the primary entries: work on copies
    copy = lambda es: [dict(e, extra=set(e['extra'])) for e in es]
    sums, wikis = copy(sum_entries), copy(wiki_entries)
    entries = {'sum11': lambda: sums, 'wiki': lambda: wikis,
               'sum11+wiki': lambda: combine(sums, wikis), 'wiki+sum11': lambda: combine(wikis, sums)}[mode]()
    if mode != 'sum11':
        entries.sort(key=lambda e: sort_key(e['word']))
    hybrid = '+' in mode
    counts = {s: sum(e['src'] == s for e in entries) for s in SOURCE_NAME}
    print(mode, 'entries', len(entries), counts, file=sys.stderr)
    out = os.path.join(args.out, name)
    os.makedirs(out, exist_ok=True)
    files = write_entries(out, entries, hybrid)
    with open(os.path.join(out, 'style.css'), 'w', encoding='utf-8') as fh:
        fh.write('p{margin:0 0 .3em 0}\np.ex{margin-left:1em;font-size:90%}\nhr{margin:.4em 0}\n')
    write_cover(out, title, entries, counts, hybrid, wiki_date)
    ident = 'sum11-uk-uk-kindle' if mode == 'sum11' else f'{name}-uk-uk-kindle'
    write_opf(out, files, title, ident, counts)
    print('done', mode, len(entries), 'entries in', len(files), 'files ->', out, file=sys.stderr)


sum_entries = load_sum(args.sum)
print('SUM-11 entries', len(sum_entries), file=sys.stderr)
wiki_entries, wiki_date = load_wiki(args.wiki, sum_entries)
print('Wiktionary entries', len(wiki_entries), 'as of', wiki_date, file=sys.stderr)
for mode in (MODES if args.mode == 'all' else [args.mode]):
    build(mode, sum_entries, wiki_entries, wiki_date)

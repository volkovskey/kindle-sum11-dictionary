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


SUPERLATIVE = re.compile(r'(?:як|що)?най(.+[шщч](?:ий|е)?)')


def comparative_heads(word):
    """Headword candidates for a comparative: itself, its lemmas, the positive degree."""
    cands = [word] + [p.normal_form for p in morph.parse(word)]
    for c in list(cands):
        if m := re.fullmatch(r'(.+?)(іш|ш)ий', c):  # гарніший, могутніший, коротший, ширший, дешевший
            cands += [m[1] + e for e in ('ий', 'ій', 'кий', 'окий')]
        elif m := re.fullmatch(r'(.+?)і?ше', c):  # частіше
            cands += [m[1] + 'о']
    return cands


def morph_extras(heads):
    """Extra forms pymorphy3 keeps apart from a headword's lexeme, by headword.

    - modern ґ-spellings for SUM-11 headwords written with г: the г-spelling of
      every lemma with ґ gets that lemma's ґ-forms, so «ґанку» opens «ганок»;
    - gerunds, separate lemmas in pymorphy3: «кажучи», «побачивши» open the verb;
    - superlatives: «найменшого», «найчастіше» open the comparative («менший»)
      or the positive degree, whichever is a headword.
    Under NO_INFL only the ґ-lemmas themselves are added. Headwords are
    spelled with ’ (as in SUM-11), pymorphy3 lemmas with '.
    """
    g_lex, grnd, verbs, supr = {}, set(), {}, {}
    for f, tag, nf, *_ in morph.dictionary.iter_known_words(''):
        if 'ґ' in nf and 'ґ' in f:
            g_lex.setdefault(nf, set()).update(apos_variants(f))
        if NO_INFL:
            continue
        if 'GRND' in tag:
            grnd.add(f)
        elif 'VERB' in tag and ('past' in tag and 'masc' in tag or 'pres' in tag and '3per' in tag and 'plur' in tag):
            verbs.setdefault(nf, set()).add(f)
        elif ('ADJF' in tag or 'ADVB' in tag) and SUPERLATIVE.fullmatch(nf):
            supr.setdefault(nf, set()).add(f)
    out = {}
    add = lambda head, forms: out.setdefault(head.replace("'", "’"), set()).update(forms)
    for nf, forms in g_lex.items():
        add(nf.replace('ґ', 'г'), {nf} if NO_INFL else forms)
    for nf, forms in verbs.items():
        # дивився -> дивившись, побачив -> побачивши, кажуть -> кажучи, дивляться -> дивлячись
        cands = set()
        for f in forms:
            refl = f.endswith(('ся', 'сь'))
            stem = f[:-2] if refl else f
            if stem.endswith('ть'):
                stem = stem[:-2] + 'чи'
            else:
                stem += 'ши'
            cands |= {stem + 'сь', stem + 'ся'} if refl else {stem}
        found = cands & grnd
        if found:
            add(nf, set().union(*(apos_variants(f) for f in found)))
    for nf, forms in supr.items():
        target = next((h for h in comparative_heads(SUPERLATIVE.fullmatch(nf)[1])
                       if h.replace("'", "’") in heads), None)
        if target:
            add(target, set().union(*(apos_variants(f) for f in forms)))
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


PARA = re.compile(r'<p( class="ex")?>(.*?)</p>', re.S)
CITATION = re.compile(r'\(([^(),]+),[^()]*\b1[789]\d\d\b[^()]*\)')
HOMONYM = re.compile(r'<b>[А-ЯІЇЄҐ’\u0301-]+[¹²³⁴⁵]')
POS_ONLY = re.compile(r'(?:<i>[^<]*</i>\s*)+')


def layout(head, body, src, note):
    """Entry text as the lookup popup renders it.

    The popup applies no stylesheet (kindling strips classes too) and indents and
    justifies every <p>, so an entry is one left-aligned block of <br/>-separated
    lines styled only with tags the popup honors: <b>, <i>, <font size>.
    The grammar that SUM-11 prints after the headword («, а, ч., зоол.»), or
    Wiktionary's part of speech, stays on the headword line.
    """
    paras = PARA.findall(body)
    rest = PARA.sub('', body).strip()
    lead = ''
    if paras and not paras[0][0] and (src == 'sum11' or POS_ONLY.fullmatch(paras[0][1].strip())):
        lead = paras.pop(0)[1]
        if src != 'sum11':
            lead = ' ' + lead
    lines = []
    for ex, text in paras:
        text = text.strip()
        if ex and text.startswith('Син.:'):
            lines.append(f'<font size="-1">{text}</font>')
        elif ex:
            # «(Сенч., На Бат. горі, 1960, 32)» -> «(Сенч.)»: volume, year and page mean nothing in a popup
            short = CITATION.sub(r'(\1)', text)
            if all(short.count(f'<{t}>') == short.count(f'</{t}>') for t in 'ib'):  # a citation can hold a stray tag
                text = short
            lines.append(f'&#160;&#160;• <font size="-1">{text}</font>')
        elif m := re.match(r'(\d+)\.', text):
            # a blank line before every numbered sense but the first, which follows the headword
            lines.append(('<br/>' if lines else '') + f'<b>{m[1]}.</b>' + text[m.end():])
        elif HOMONYM.match(text):  # КОСА́² inside the КОСА́¹ record
            lines.append('<br/>' + text)
        else:
            lines.append(re.sub(r'^//', '<b>//</b>', text))
    if rest:
        lines.append(rest)
    if note:
        lines.append(f'<br/><font size="-1"><i>— {note}</i></font>')
    return lead, ''.join('<br/>' + l for l in lines)


def entry(word, head, body, extra_forms, src='sum11', note=None):
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
    lead, lines = layout(head, body, src, note)
    return (f'<idx:entry name="default" scriptable="yes"><div align="left">'
            f'<idx:orth value="{w}"><b>{head}</b>{infl}</idx:orth>{lead}{lines}'
            f'</div><mbp:pagebreak/></idx:entry>\n')


# ---- sources: dicts with word, head (HTML), body (HTML), src, extra (set of forms)

def load_sum(path):
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
                            src='sum11', extra=set()))
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
        x = entry(e['word'], e['head'], e['body'], e['extra'], e['src'],
                  SOURCE_NAME[e['src']] if hybrid else None)
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
        fh.write('div{text-align:left;margin-bottom:.8em}\n')
    write_cover(out, title, entries, counts, hybrid, wiki_date)
    ident = 'sum11-uk-uk-kindle' if mode == 'sum11' else f'{name}-uk-uk-kindle'
    write_opf(out, files, title, ident, counts)
    print('done', mode, len(entries), 'entries in', len(files), 'files ->', out, file=sys.stderr)


sum_entries = load_sum(args.sum)
print('SUM-11 entries', len(sum_entries), file=sys.stderr)
wiki_entries, wiki_date = load_wiki(args.wiki, sum_entries)
print('Wiktionary entries', len(wiki_entries), 'as of', wiki_date, file=sys.stderr)
plain = lambda e: e['word'].lower().rstrip('…').strip().replace("'", "’").replace("ʼ", "’")
extras = morph_extras({plain(e) for e in sum_entries + wiki_entries})
for e in sum_entries + wiki_entries:
    e['extra'] |= extras.get(plain(e), set())
print('extra forms for', len(extras), 'headwords', file=sys.stderr)
for mode in (MODES if args.mode == 'all' else [args.mode]):
    build(mode, sum_entries, wiki_entries, wiki_date)

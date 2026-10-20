"""Build Kindle dictionary source (OPF + HTML) from the SUM-11 tab file.

usage: python3 -I build_sum.py <tabfile> <outdir>
       NO_INFL=1 python3 -I build_sum.py <tabfile> <outdir>   # headwords only, no word forms

Compile the result with kindling (not kindlegen, see README):
       kindling-cli build <outdir>/sum11.opf -o sum11.mobi
"""
import sys, os, re, html
import pymorphy3

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
morph = pymorphy3.MorphAnalyzer(lang='uk')

APOS = ["’", "'", "ʼ"]
MAX_IFORMS = 120
NO_INFL = os.environ.get('NO_INFL') == '1'
VALID = re.compile(r"[а-щьюяґєіїa-z’'ʼ-]+")


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


G_FORMS = g_forms()


def clean(v):
    v = v.replace('\\n', '')
    v = re.sub(r'</?font[^>]*>', '', v)
    v = re.sub(r'</?span[^>]*>', '', v)
    v = v.replace('<div style="margin-left:1em">', '<p>')
    v = re.sub(r'<div style="margin-left:\d+em">', '<p class="ex">', v)
    v = v.replace('</div>', '</p>')
    v = re.sub(r'<br\s*>', '<br/>', v)
    return v


def entry(word, body, extra_forms):
    word_l = word.lower()
    iforms = set()
    if not word.endswith('…'):
        iforms = forms_for(word_l)
    iforms |= apos_variants(word_l)
    iforms.discard(word_l)
    iforms = sorted(f for f in iforms if VALID.fullmatch(f))[:MAX_IFORMS]
    if NO_INFL:
        iforms = []
    # extra forms (the ґ-spellings) go after the cap so they are never cut off
    iforms += sorted(f for f in extra_forms if VALID.fullmatch(f) and f not in iforms)
    # Kindle does not lowercase a tapped word for a uk dictionary,
    # so a word at the start of a sentence needs its capitalized form indexed.
    plain_w = word_l.rstrip('…').strip()
    iforms += [c for c in (f[:1].upper() + f[1:] for f in [plain_w] + iforms)
               if c not in (plain_w, *iforms)]
    infl = ''
    if iforms:
        infl = '<idx:infl>' + ''.join(
            f'<idx:iform value="{html.escape(f, quote=True)}"/>' for f in iforms) + '</idx:infl>'
    w = html.escape(plain_w, quote=True)
    m = re.match(r'<p><b>(.*?)</b>', body)
    head = m.group(1) if m else w
    rest = ('<p>' + body[m.end():]) if m else body
    return (f'<idx:entry name="default" scriptable="yes">'
            f'<h5><dt><idx:orth value="{w}">{head}{infl}</idx:orth></dt></h5>'
            f'<dd>{rest}</dd><mbp:pagebreak/></idx:entry>\n')


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

files, buf, size, n = [], [], 0, 0
LIMIT = 6 * 1024 * 1024


def flush():
    global buf, size
    if not buf:
        return
    name = f'content{len(files) + 1:03d}.html'
    with open(os.path.join(out, name), 'w', encoding='utf-8') as fh:
        fh.write(HEAD + ''.join(buf) + TAIL)
    files.append(name)
    buf, size = [], 0


for line in open(src, encoding='utf-8'):
    if line.startswith('##'):
        continue
    key, _, val = line.rstrip('\n').partition('\t')
    if not key or not val:
        continue
    body = clean(val)
    words = [w.strip() for w in key.split('|') if w.strip()]
    for w in words:
        e = entry(w, body, G_FORMS.get(w.lower().rstrip('…').strip(), set()))
        buf.append(e)
        size += len(e.encode('utf-8'))
        n += 1
        if size > LIMIT:
            flush()
    if n % 20000 < len(words):
        print('entries', n, file=sys.stderr)
flush()

with open(os.path.join(out, 'style.css'), 'w', encoding='utf-8') as fh:
    fh.write('p{margin:0 0 .3em 0}\np.ex{margin-left:1em;font-size:90%}\nhr{margin:.4em 0}\n')

with open(os.path.join(out, 'cover.html'), 'w', encoding='utf-8') as fh:
    fh.write('<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/></head>'
             '<body><h1>Словник української мови (СУМ-11)</h1>'
             '<p>Тлумачний словник в 11 томах (АН УРСР, 1970–1980). Kindle-версія'
             + ('' if NO_INFL else ' з формами слів') + '.</p>'
             '<p>Джерело даних: github.com/bakustarver/ukr-dictionaries-list-opensource</p>'
             '<p>Проєкт: github.com/volkovskey/kindle-sum11-dictionary</p>'
             '</body></html>\n')


def write_opf(name, flist, title):
    manifest = '\n'.join(
        f'    <item id="c{i}" href="{f}" media-type="application/xhtml+xml"/>' for i, f in enumerate(flist))
    spine = '\n'.join(['    <itemref idref="cover"/>'] +
                      [f'    <itemref idref="c{i}"/>' for i in range(len(flist))])
    guide = '\n'.join(f'    <reference type="index" title="IndexName" href="{f}"/>' for f in flist)
    opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package unique-identifier="uid" version="2.0" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">sum11-uk-uk-kindle</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:language>uk</dc:language>
    <dc:creator>Академія наук УРСР</dc:creator>
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
    with open(os.path.join(out, name), 'w', encoding='utf-8') as fh:
        fh.write(opf)


write_opf('sum11.opf', files, 'СУМ-11: тлумачний словник української мови')
print('done', n, 'entries in', len(files), 'files', file=sys.stderr)

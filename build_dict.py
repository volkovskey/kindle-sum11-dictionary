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
import sys, os, re, html, argparse, shutil
from collections import Counter
import pymorphy3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # python -I leaves it out
import wiktionary

# titles stay short: the lookup popup cuts the dictionary name at ~30 characters
MODES = {
    'sum11': ('СУМ-11', 'sum11'),
    'wiki': ('Вікісловник', 'wiktionary'),
    'sum11+wiki': ('СУМ-11 + Вікісловник', 'sum11-wiktionary'),
    'wiki+sum11': ('Вікісловник + СУМ-11', 'wiktionary-sum11'),
}
SUBTITLE = 'Тлумачний словник української мови'
COVERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'covers')
SOURCE_NAME = {'sum11': 'СУМ-11', 'wiki': 'Вікісловник', 'claude': 'Claude (ШІ)'}

ap = argparse.ArgumentParser()
ap.add_argument('--mode', choices=[*MODES, 'all'], required=True)
ap.add_argument('--sum', required=True, help='SUM-11 tab file')
ap.add_argument('--wiki', required=True, help='ukwiktionary pages-articles .xml.bz2 dump')
ap.add_argument('--claude', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'claude.tsv'),
                help='definitions written by Claude for words no source has (mixed dictionaries only)')
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
COMPARATIVE = re.compile(r'.+(?:іш|ш)ий')


def comparative_heads(word):
    """Headword candidates for a comparative: itself, its lemmas, the positive degree."""
    cands = [word] + [p.normal_form for p in morph.parse(word)]
    for c in list(cands):
        if m := re.fullmatch(r'(.+?)(іш|ш)ий', c):  # гарніший, могутніший, коротший, ширший, дешевший, раніший
            cands += [m[1] + e for e in ('ий', 'ій', 'кий', 'окий', 'ній')]
        elif m := re.fullmatch(r'(.+?)і?ше', c):  # частіше
            cands += [m[1] + 'о']
    return cands


def morph_extras(heads):
    """Extra forms pymorphy3 keeps apart from a headword's lexeme, by headword.

    - modern ґ-spellings for SUM-11 headwords written with г: the г-spelling of
      every lemma with ґ gets that lemma's ґ-forms, so «ґанку» opens «ганок»;
    - gerunds, separate lemmas in pymorphy3: «кажучи», «побачивши» open the verb;
    - superlatives: «найменшого», «найчастіше» open the comparative («менший»)
      or the positive degree, whichever is a headword;
    - comparatives that are no headword: «швидший», «раніше» open «швидкий», «ранній».
    Under NO_INFL only the ґ-lemmas themselves are added. Headwords are
    spelled with ’ (as in SUM-11), pymorphy3 lemmas with '.
    """
    g_lex, grnd, verbs, supr, compr = {}, set(), {}, {}, {}
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
        elif 'ADJF' in tag and COMPARATIVE.fullmatch(nf) and nf.replace("'", "’") not in heads:
            compr.setdefault(nf, set()).add(f)
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
    for nf, forms in compr.items():
        target = next((h for h in comparative_heads(nf)[1:] if h != nf and h.replace("'", "’") in heads), None)
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
    if paras and not paras[0][0] and (src in ('sum11', 'claude') or POS_ONLY.fullmatch(paras[0][1].strip())):
        lead = paras.pop(0)[1]
        if src == 'wiki':
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
            # a blank line before every numbered sense but the first, which follows its headword line
            lines.append(('<br/>' if m[1] != '1' else '') + f'<b>{m[1]}.</b>' + text[m.end():])
        elif HOMONYM.match(text):  # КОСА́² inside the КОСА́¹ record
            lines.append('<br/>' + text)
        else:
            lines.append(re.sub(r'^//', '<b>//</b>', text))
    if rest:
        lines.append(rest)
    if note:
        lines.append(f'<br/><font size="-1"><i>— {note}</i></font>')
    return lead, ''.join('<br/>' + l for l in lines)


def headword(e):
    return e['word'].lower().rstrip('…').strip()


def group_forms(group):
    """Lowercase inflected forms of a group of entries sharing a headword."""
    plain_w = headword(group[0])
    iforms, extra_forms = set(), set()
    for e in group:
        word_l = e['word'].lower()
        if not word_l.endswith('…'):
            iforms |= forms_for(word_l)
        iforms |= apos_variants(word_l)
        iforms.discard(word_l)
        extra_forms |= e['extra']
    iforms = sorted(f for f in iforms if VALID.fullmatch(f))[:MAX_IFORMS]
    if NO_INFL:
        iforms = []
    # a book in the older spelling writes г for ґ
    if 'ґ' in plain_w:
        extra_forms |= {f.replace('ґ', 'г') for f in [plain_w, *iforms]}
    # extra forms go after the cap so they are never cut off
    return iforms + sorted(f for f in extra_forms if VALID.fullmatch(f) and f not in iforms and f != plain_w)


WORDS = re.compile(r"[а-щьюяґєії’'ʼ]+")


def resolve_shared(groups, forms):
    """Give a form shared by several headwords to the most frequent of them.

    Kindle opens one entry per lookup, the first in index order, so «мені»
    (я, мень), «голові» (голова, гол) and «мав» (мати, манути) opened the
    rarer word. pymorphy3 has no frequencies for Ukrainian, so a headword's
    frequency is counted in the dictionary's own text, mostly quotations:
    occurrences of its forms that belong to no other headword. A form stays with every owner when
    none of them occurs.
    """
    owners = {}
    for h, fs in forms.items():
        for f in fs:
            owners.setdefault(f, []).append(h)
    shared = {f: hs for f, hs in owners.items() if len(hs) > 1 and f not in forms}
    count = Counter()
    for group in groups.values():
        for e in group:
            count.update(w.replace("'", '’').replace('ʼ', '’')
                         for w in WORDS.findall(re.sub(r'<[^>]+>', ' ', e['body']).lower()))
    score = {h: count[h] + sum(count[f] for f in fs if len(owners[f]) == 1) for h, fs in forms.items()}
    moved = 0
    for f, hs in shared.items():
        best = max(hs, key=lambda h: score[h])
        if score[best] and sorted(score[h] for h in hs)[-2] < score[best]:
            for h in hs:
                if h != best:
                    forms[h].remove(f)
            moved += 1
    print('shared forms', len(shared), 'given to one headword', moved, file=sys.stderr)


ELIDED = re.compile(r"[а-щьюяґєії]{1,2}[’'ʼ](.+)")


def add_elided(forms):
    """Index «явився» for «з’явився», a form found on a Kindle with firmware 5.20.

    That firmware opens nothing for a tapped word with an apostrophe inside
    («сум’яття»), whatever the label, but drops a one-letter prefix and its
    apostrophe the way French drops «l’»: «з’явився» is looked up as «явився».
    The part after a short prefix is added where no headword or form has it
    already, so it never takes a lookup from another word.
    """
    taken = set(forms)
    for fs in forms.values():
        taken.update(fs)
    added = 0
    for h, fs in forms.items():
        for f in [h, *fs]:
            m = ELIDED.fullmatch(f)
            if m and m[1] not in taken and VALID.fullmatch(m[1]):
                fs.append(m[1])
                taken.add(m[1])
                added += 1
    print('elided forms', added, file=sys.stderr)


def entry(group, iforms, hybrid):
    """One lookup entry for all the entries of `group`, which share a headword.

    The popup shows a single entry per lookup, so homonyms («рентген» and the
    prefix «рентген…», two Wiktionary «коса» pages) go into one entry, each
    starting on its own headword line, after a blank line.
    """
    plain_w = headword(group[0])
    # Kindle does not lowercase a tapped word for a uk dictionary,
    # so a word at the start of a sentence needs its capitalized form indexed.
    iforms = iforms + [c for c in (f[:1].upper() + f[1:] for f in [plain_w] + iforms)
                       if c not in (plain_w, *iforms)]
    infl = ''
    if iforms:
        infl = '<idx:infl>' + ''.join(
            f'<idx:iform value="{html.escape(f, quote=True)}"/>' for f in iforms) + '</idx:infl>'
    w = html.escape(plain_w, quote=True)
    # in a mixed dictionary, sign each part if the sources differ, else just the end
    mixed = len({e['src'] for e in group}) > 1
    text = ''
    for i, e in enumerate(group):
        note = SOURCE_NAME[e['src']] if hybrid and (mixed or i == len(group) - 1) else None
        lead, lines = layout(e['head'], e['body'], e['src'], note)
        text += (f'<idx:orth value="{w}"><b>{e["head"]}</b>{infl}</idx:orth>' if i == 0
                 else f'<br/><br/><b>{e["head"]}</b>') + lead + lines
    return (f'<idx:entry name="default" scriptable="yes"><div align="left">{text}'
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
        if len(title) > 1 and title.isupper():  # an abbreviation (ШІ) is looked up in capitals
            forms.add(title)
        res.append(dict(word=title, head=html.escape(head.upper(), quote=False), body=body,
                        src='wiki', extra=forms, weak=ref_only))
    return res, date


GRAM_LABEL = re.compile(r'(?<![а-яіїєґ’])(ч|ж|с|мн|прийм|спол|част|виг|присл|док|недок|невідм|числ|порядк|кільк|'
                        r'розм|перен|заст|діал|спец|техн|мед|біол|бот|зоол|фізіол|юр|військ|церк|ірон|зневажл|'
                        r'пестл|збірн|офіц|поет|знач|ім|присудк|прикм|підсил|перев|р|в|з|до|у|стос|ч\. і ж)\.')
SENSE_LABEL = re.compile(r'^((?:(?:невідм|розм|перен|заст|діал|спец|техн|мед|біол|бот|зоол|фізіол|юр|військ|церк|ірон|'
                         r'зневажл|пестл|збірн|офіц|поет|перев)\.,? |у знач\. (?:ім|присудк|прикм|підсил\. част)\.,? )+)')


def load_claude(path):
    """Short definitions Claude wrote for words no source has: word, HEADWORD, grammar, senses split by « | »."""
    res = []
    if not os.path.exists(path):
        return res
    for line in open(path, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        word, head, gram, senses = line.rstrip('\n').split('\t')
        gram = GRAM_LABEL.sub(lambda m: f'<i>{m[0]}</i>', html.escape(gram, quote=False))
        senses = [SENSE_LABEL.sub(lambda m: f'<i>{m[1].strip()}</i> ', html.escape(s.strip(), quote=False))
                  for s in senses.split(' | ')]
        if len(senses) == 1:
            body = f'<p>, {gram} {senses[0]}</p>'
        else:
            body = f'<p>, {gram}</p>' + ''.join(f'<p>{i}. {s}</p>' for i, s in enumerate(senses, 1))
        # an abbreviation (ШІ) is looked up in capitals, which no lowercase form produces
        res.append(dict(word=word.lower(), head=html.escape(head, quote=False), body=body, src='claude',
                        extra={word} if word != word.lower() else set()))
    return res


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

    groups = {}
    for e in entries:
        groups.setdefault(headword(e), []).append(e)
    for group in groups.values():
        group.sort(key=lambda e: e['word'].endswith('…'))  # the word before the prefix «рентген…»
    forms = {h: group_forms(g) for h, g in groups.items()}
    resolve_shared(groups, forms)
    add_elided(forms)
    for n, (h, group) in enumerate(groups.items(), 1):
        x = entry(group, forms[h], hybrid)
        buf.append(x)
        size += len(x.encode('utf-8'))
        if size > LIMIT:
            flush()
        if n % 20000 == 0:
            print('entries', n, file=sys.stderr)
    flush()
    print('lookup entries', len(groups), file=sys.stderr)
    return files


def write_cover(out, title, entries, counts, hybrid, wiki_date):
    about = {
        'sum11': '<p>Словник української мови в 11 томах (АН УРСР, 1970–1980). '
                 'Дані: github.com/bakustarver/ukr-dictionaries-list-opensource</p>',
        'wiki': f'<p>Український Вікісловник (uk.wiktionary.org), стан на {wiki_date}. '
                'Тексти Вікісловника поширюються за ліцензією CC BY-SA 4.0 '
                '(creativecommons.org/licenses/by-sa/4.0), автори — дописувачі Вікісловника.</p>',
        'claude': '<p>Короткі тлумачення слів, яких немає ні в СУМ-11, ні у Вікісловнику, написав Claude (ШІ, Anthropic); '
                  'вони підписані «— Claude (ШІ)» і можуть містити помилки.</p>',
    }
    with open(os.path.join(out, 'cover.html'), 'w', encoding='utf-8') as fh:
        fh.write('<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/></head>'
                 f'<body><h1>{title}</h1><p><b>{SUBTITLE}</b></p>'
                 f'<p>Kindle-версія{"" if NO_INFL else " з формами слів"}: {len(entries)} статей'
                 + (f' ({counts["sum11"]} з СУМ-11, {counts["wiki"]} з Вікісловника'
                    + (f', {counts["claude"]} написав Claude' if counts['claude'] else '') + ')' if hybrid else '') + '.</p>'
                 + ''.join(about[s] for s in ('sum11', 'wiki', 'claude') if counts[s])
                 + '<p>Проєкт: github.com/volkovskey/kindle-sum11-dictionary</p>'
                 '</body></html>\n')


def write_opf(out, flist, title, ident, counts):
    manifest = '\n'.join(
        f'    <item id="c{i}" href="{f}" media-type="application/xhtml+xml"/>' for i, f in enumerate(flist))
    spine = '\n'.join(['    <itemref idref="cover"/>'] +
                      [f'    <itemref idref="c{i}"/>' for i in range(len(flist))])
    guide = '\n'.join(f'    <reference type="index" title="IndexName" href="{f}"/>' for f in flist)
    creators = '\n'.join(f'    <dc:creator>{c}</dc:creator>' for c, s in
                         (('Академія наук УРСР', 'sum11'), ('Дописувачі Вікісловника', 'wiki'),
                          ('Claude (ШІ, Anthropic)', 'claude')) if counts[s])
    rights = '\n    <dc:rights>Тексти Вікісловника: CC BY-SA 4.0</dc:rights>' if counts['wiki'] else ''
    opf = f'''<?xml version="1.0" encoding="utf-8"?>
<package unique-identifier="uid" version="2.0" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="uid">{ident}</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:language>uk</dc:language>
    <dc:description>{SUBTITLE}</dc:description>
{creators}{rights}
    <meta name="cover" content="cover-image"/>
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
    <item id="cover-image" href="cover.jpg" media-type="image/jpeg"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
{manifest}
  </manifest>
  <spine toc="ncx">
{spine}
  </spine>
  <guide>
{guide}
  </guide>
</package>
'''
    with open(os.path.join(out, 'dict.opf'), 'w', encoding='utf-8') as fh:
        fh.write(opf)
    # Kindle wants a table of contents; a dictionary has one natural entry, its front page
    with open(os.path.join(out, 'toc.ncx'), 'w', encoding='utf-8') as fh:
        fh.write(f'''<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="uk">
  <head><meta name="dtb:uid" content="{ident}"/></head>
  <docTitle><text>{title}</text></docTitle>
  <navMap>
    <navPoint id="cover" playOrder="1"><navLabel><text>{title}</text></navLabel><content src="cover.html"/></navPoint>
  </navMap>
</ncx>
''')


def build(mode, sum_entries, wiki_entries, claude_entries, wiki_date):
    title, name = MODES[mode]
    # combine() adds forms to the primary entries: work on copies
    copy = lambda es: [dict(e, extra=set(e['extra'])) for e in es]
    sums, wikis = copy(sum_entries), copy(wiki_entries)
    entries = {'sum11': lambda: sums, 'wiki': lambda: wikis,
               'sum11+wiki': lambda: combine(sums, wikis), 'wiki+sum11': lambda: combine(wikis, sums)}[mode]()
    if '+' in mode:  # Claude's definitions only fill words both sources lack
        entries = absorb(entries, copy(claude_entries))
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
    shutil.copy(os.path.join(COVERS, f'{name}.jpg'), os.path.join(out, 'cover.jpg'))
    ident = 'sum11-uk-uk-kindle' if mode == 'sum11' else f'{name}-uk-uk-kindle'
    write_opf(out, files, title, ident, counts)
    print('done', mode, len(entries), 'entries in', len(files), 'files ->', out, file=sys.stderr)


sum_entries = load_sum(args.sum)
print('SUM-11 entries', len(sum_entries), file=sys.stderr)
wiki_entries, wiki_date = load_wiki(args.wiki, sum_entries)
print('Wiktionary entries', len(wiki_entries), 'as of', wiki_date, file=sys.stderr)
claude_entries = load_claude(args.claude)
print('Claude entries', len(claude_entries), file=sys.stderr)
plain = lambda e: e['word'].lower().rstrip('…').strip().replace("'", "’").replace("ʼ", "’")
extras = morph_extras({plain(e) for e in sum_entries + wiki_entries + claude_entries})
for e in sum_entries + wiki_entries + claude_entries:
    e['extra'] |= extras.get(plain(e), set())
print('extra forms for', len(extras), 'headwords', file=sys.stderr)
for mode in (MODES if args.mode == 'all' else [args.mode]):
    build(mode, sum_entries, wiki_entries, claude_entries, wiki_date)

"""Draw the library covers in covers/ (1600x2560 JPEG, one per dictionary).

usage: python3 make_covers.py <font dir> [out dir, default covers]

The covers are committed, so a build does not need this script. It needs
Pillow and the e-Ukraine typeface (CC BY 4.0, Ministry of Digital
Transformation of Ukraine), e.g. the .otf files of
https://github.com/bennetfabian/e-Ukraine in <font dir>.
"""
import sys
from PIL import Image, ImageDraw, ImageFont

FD = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else 'covers'
W, H, M = 1600, 2560, 150
INK, PAPER, GREY = (20, 20, 20), (255, 255, 255), (105, 105, 105)
F = lambda name, size: ImageFont.truetype(f'{FD}/{name}.otf', size)

SUM = ('Словник української мови в 11 томах', 'АН УРСР, 1970–1980')
WIKI = ('Український Вікісловник', 'uk.wiktionary.org')
COVERS = [
    ('sum11-wiktionary', ['СУМ-11', 'Вікісловник'], [SUM, WIKI]),
    ('wiktionary-sum11', ['Вікісловник', 'СУМ-11'], [WIKI, SUM]),
    ('sum11', ['СУМ-11'], [SUM]),
    ('wiktionary', ['Вікісловник'], [WIKI]),
]

# one title size for every cover: the widest line fills the text width
probe = ImageDraw.Draw(Image.new('L', (1, 1)))
width100 = lambda l: probe.textlength(l, font=F('e-UkraineHead-Bold', 100))
TITLE = F('e-UkraineHead-Bold', int(100 * (W - 2 * M) / max(width100(l) for _, ls, _ in COVERS for l in ls)))
AND = F('e-UkraineHead-Light', 84)


def cover(name, lines, sources):
    im = Image.new('RGB', (W, H), PAPER)
    d = ImageDraw.Draw(im)
    d.text((M, 200), 'Тлумачний словник', font=F('e-UkraineHead-Medium', 84), fill=INK)
    d.text((M, 300), 'української мови', font=F('e-UkraineHead-Medium', 84), fill=INK)
    # place lines by their baselines, so the gaps around the small «та» are equal
    cap = -d.textbbox((0, 0), 'СУМ', font=TITLE, anchor='ls')[1]
    xh = -d.textbbox((0, 0), 'та', font=AND, anchor='ls')[1]
    gap = 55
    base = 900 + cap
    for i, line in enumerate(lines):
        if i:  # «та» between the two sources of a mixed dictionary
            base += gap + xh
            d.text((M + 6, base), 'та', font=AND, fill=GREY, anchor='ls')
            base += gap + cap
        d.text((M, base), line, font=TITLE, fill=INK, anchor='ls')
    y = 1640
    d.line([(M, y), (M + 160, y)], fill=INK, width=6)
    y += 70
    # each source is its own block: name, then a grey detail line
    for source, detail in sources:
        d.text((M, y), source, font=F('e-Ukraine-Regular', 60), fill=INK)
        d.text((M, y + 84), detail, font=F('e-Ukraine-Light', 54), fill=GREY)
        y += 224
    d.text((M, H - 260), 'для Kindle', font=F('e-UkraineHead-Regular', 72), fill=INK)
    im.convert('L').save(f'{OUT}/{name}.jpg', quality=75, optimize=True)  # grey like e-ink, under Kindle's 127 KB


for c in COVERS:
    cover(*c)

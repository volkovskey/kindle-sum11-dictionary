<div align="center">

# 📖 SUM-11 for Kindle

**The Ukrainian explanatory dictionary in 11 volumes**<br>
Academy of Sciences of the Ukrainian SSR · 1970–1980

Long-press a word in a Ukrainian book to see its definition.

[![Release](https://img.shields.io/github/v/release/volkovskey/kindle-sum11-dictionary?color=0057B7)](../../releases/latest)
[![License: AGPL-3.0](https://img.shields.io/badge/code-AGPL--3.0-informational)](LICENSE)
![Kindle](https://img.shields.io/badge/Kindle-.mobi-FF9900?logo=amazon&logoColor=white)

**[⬇️ Download](../../releases/latest)** &nbsp;·&nbsp; **[Українська версія](README.md)**

</div>

---

- ~131k entries with usage examples.
- Inflected forms are found (≈3.7M forms generated with pymorphy3), including
  capitalized ones at the start of a sentence.
- Modern spellings with «ґ» open the SUM-11 headwords written with «г».

## Install

1. Download `sum11.mobi` from [Releases](../../releases/latest).
2. Copy the file to `documents/dictionaries` on the Kindle **over USB**, then
   eject. Kindles released in 2024 or later and Kindle Scribe do not mount as
   a drive on macOS: use **Tools → USB File Manager** in
   [Send to Kindle for Mac](https://www.amazon.com/sendtokindle).
   Wireless Send to Kindle does not work: it rejects `.mobi` and would not put
   the file into the dictionaries folder.
3. In a Ukrainian book, long-press a word. If another dictionary opens, tap its
   name in the popup and pick *«СУМ-11: тлумачний словник української мови»*.

Kindle has no Ukrainian keyboard, so typing searches inside the dictionary is
limited. Lookups from books work fully.

## Build

```sh
./build.sh            # -> sum11.mobi
NO_INFL=1 ./build.sh  # -> sum11-plain.mobi (headwords only)
```

The script needs macOS or Linux with `python3`, `curl` and `unzip`. It downloads
the SUM-11 tab file, generates OPF/HTML with `build_sum.py` and compiles them
with [kindling](https://github.com/ciscoriordan/kindling).

## Lessons learned

1. `spell="yes"` on `<idx:entry>` makes kindlegen 2.9 crash on some Cyrillic
   headwords (`E25007` / `E21012`). Remove it.
2. **kindlegen-built Ukrainian dictionaries do not work on the device.** A
   Kindle binary-searches the index using fixed per-character weights
   (Cyrillic by code point, apostrophes and hyphens ignored). For `uk`,
   kindlegen sorts the index with its own collation (e.g. «е» before «б»), so
   lookups miss: nothing is found from books, and searching always lands on the
   first entry. Build with kindling, which sorts the way the device searches.
   kindling also requires `<x-metadata>` to be *inside* `<metadata>`.
3. Kindle does not lowercase a tapped word for a Ukrainian dictionary, so
   capitalized forms have to be indexed explicitly.
4. The trailing «…» of prefix headwords (`авіа…`) was removed from `value`.

## Known gaps

The source data (in every format of the upstream release) lacks all words
starting with «п’я» (п’ять, п’ятниця…) as well as «грунт», «гудзик», «дзига».

## Credits and license

Data: [bakustarver/ukr-dictionaries-list-opensource](https://github.com/bakustarver/ukr-dictionaries-list-opensource).
Inspired by [pavlo-liapin/kindle-eng-ukr-dictionary](https://github.com/pavlo-liapin/kindle-eng-ukr-dictionary).
Built with [kindling](https://github.com/ciscoriordan/kindling),
[pymorphy3](https://github.com/no-plagiarism/pymorphy3) and pymorphy3-dicts-uk.

Code: [AGPL-3.0](LICENSE). The rights to the SUM-11 text are not explicitly
stated by the data source. The text is not stored in this repository and is
only included in the free, non-commercial `.mobi` release. If you are a rights
holder and object, please open an issue and it will be removed.

<div align="center">

# 📖 Ukrainian explanatory dictionary for Kindle

**SUM-11** (Academy of Sciences of the Ukrainian SSR · 1970–1980) **+ Ukrainian Wiktionary**

Long-press a word in a Ukrainian book to see its definition.

[![Release](https://img.shields.io/github/v/release/volkovskey/kindle-sum11-dictionary?color=0057B7)](../../releases/latest)
[![License: AGPL-3.0](https://img.shields.io/badge/code-AGPL--3.0-informational)](LICENSE)
[![Wiktionary: CC BY-SA 4.0](https://img.shields.io/badge/Wiktionary-CC%20BY--SA%204.0-lightgrey)](https://creativecommons.org/licenses/by-sa/4.0/)
![Kindle](https://img.shields.io/badge/Kindle-.mobi-FF9900?logo=amazon&logoColor=white)

**[⬇️ Download](../../releases/latest)** &nbsp;·&nbsp; **[Українська версія](README.md)**

</div>

---

<table>
  <tr>
    <td align="center" width="50%"><img src="docs/screenshots/popup.png" alt="Lookup popup for «Зверхність» in a book"></td>
    <td align="center" width="50%"><img src="docs/screenshots/expanded.png" alt="Expanded entry «скорпіон»"></td>
  </tr>
</table>

## Which file

<table>
  <tr>
    <td align="center" width="25%"><a href="https://github.com/volkovskey/kindle-sum11-dictionary/releases/latest/download/sum11-wiktionary.mobi"><img src="covers/sum11-wiktionary.jpg" alt="Cover «СУМ-11 та Вікісловник»"></a><br><sub>⭐ <a href="https://github.com/volkovskey/kindle-sum11-dictionary/releases/latest/download/sum11-wiktionary.mobi"><code>sum11-wiktionary.mobi</code></a></sub></td>
    <td align="center" width="25%"><a href="https://github.com/volkovskey/kindle-sum11-dictionary/releases/latest/download/wiktionary-sum11.mobi"><img src="covers/wiktionary-sum11.jpg" alt="Cover «Вікісловник та СУМ-11»"></a><br><sub><a href="https://github.com/volkovskey/kindle-sum11-dictionary/releases/latest/download/wiktionary-sum11.mobi"><code>wiktionary-sum11.mobi</code></a></sub></td>
    <td align="center" width="25%"><a href="https://github.com/volkovskey/kindle-sum11-dictionary/releases/latest/download/sum11.mobi"><img src="covers/sum11.jpg" alt="Cover «СУМ-11»"></a><br><sub><a href="https://github.com/volkovskey/kindle-sum11-dictionary/releases/latest/download/sum11.mobi"><code>sum11.mobi</code></a></sub></td>
    <td align="center" width="25%"><a href="https://github.com/volkovskey/kindle-sum11-dictionary/releases/latest/download/wiktionary.mobi"><img src="covers/wiktionary.jpg" alt="Cover «Вікісловник»"></a><br><sub><a href="https://github.com/volkovskey/kindle-sum11-dictionary/releases/latest/download/wiktionary.mobi"><code>wiktionary.mobi</code></a></sub></td>
  </tr>
</table>

| | File | Entries | Size | Contents |
|:--:|:--|--:|--:|:--|
| ⭐ | **`sum11-wiktionary.mobi`** | 138,040 | 194&nbsp;MB | SUM-11 first, Wiktionary for words SUM-11 lacks |
| | `wiktionary-sum11.mobi` | 138,018 | 188&nbsp;MB | Wiktionary first, SUM-11 for words Wiktionary lacks or only cross-references |
| | `sum11.mobi` | 131,155 | 185&nbsp;MB | SUM-11 only |
| | `wiktionary.mobi` | 19,915 | 18&nbsp;MB | Ukrainian Wiktionary only |

All variants find inflected forms (≈4M, generated with pymorphy3, including
gerunds and superlatives: «кажучи» opens «казати»), capitalized
words at the start of a sentence, «ґ»/«г» spellings and any apostrophe. In the
mixed dictionaries every entry ends with its source. ⭐ marks the recommended one.

SUM-11 is consistent: detailed definitions with literary examples, which is what
you need for the rare and archaic words people usually look up. Wiktionary is
uneven, so in the recommended file it only adds words SUM-11 lacks («інтернет»,
«ґрунт», «п’ять»). Pick `wiktionary-sum11.mobi` if you prefer modern
definitions over detail, e.g. to avoid Soviet-era wording for the words
Wiktionary covers.

## Install

1. Download a `.mobi` from [Releases](../../releases/latest).
2. Copy it to `documents/dictionaries` on the Kindle **over USB**, then
   eject. Kindles released in 2024 or later and Kindle Scribe do not mount as
   a drive on macOS: use **Tools → USB File Manager** in
   [Send to Kindle for Mac](https://www.amazon.com/sendtokindle).
   Wireless Send to Kindle does not work: it rejects `.mobi` and would not put
   the file into the dictionaries folder.
3. Open the dictionary once from the library like a regular book, then close
   it. Without this, some Kindles report "no definition found" on lookups.
4. In a Ukrainian book, long-press a word. If another dictionary opens, tap
   **⋮** in the popup → **Change Dictionary** and pick the one you installed.

Kindle has no Ukrainian keyboard, so typing searches inside the dictionary is
limited. Lookups from books work fully.

## Update

Copying a new version over the old file is not enough: the Kindle keeps a
`.sdr` folder with its own data next to the dictionary. Delete it together with
the old file so nothing of the previous version is left.

1. Connect the Kindle over USB as above.
2. In `documents/dictionaries`, delete the old dictionary and its `.sdr`
   folder, e.g. `sum11-wiktionary.mobi` and `sum11-wiktionary.sdr/`. Leave
   everything else alone.
3. Install the new version following the steps above.

## Build

```sh
./build.sh                  # all four variants -> dist/*.mobi
MODE=wiki+sum11 ./build.sh  # one variant: sum11 | wiki | sum11+wiki | wiki+sum11
NO_INFL=1 ./build.sh        # headwords only    -> dist/*-plain.mobi
```

The script needs macOS or Linux with `python3`, `curl` and `unzip`. It downloads
the SUM-11 tab file and the latest Ukrainian Wiktionary dump, generates OPF/HTML
with `build_dict.py` (Wiktionary wikitext parsing in `wiktionary.py`) and
compiles them with [kindling](https://github.com/ciscoriordan/kindling).

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
5. Kindle tries the exact spelling first, so Wiktionary entries for surnames
   and villages («Щастя», a town) hijack sentence-initial common words
   («щастя»). They are filtered out.
6. A lookup popup cannot follow cross-references, so in the mixed
   dictionaries an entry that only says «same as X» gives way to a full entry
   from the other source.
7. pymorphy3 treats gerunds («кажучи», «побачивши») and superlatives
   («найменший») as separate lemmas, so they are not in the verb's or
   adjective's paradigm. In 16 novels (1.4M words) that was 1.2% of all words.
   Gerunds are now derived from present and past forms and kept only if
   pymorphy3 knows them; superlatives point to the comparative or positive
   headword.
8. The lookup popup applies no stylesheet (and kindling strips `class`), so
   every `<p>` gets a first-line indent and justified text. Entries are one
   `<div align="left">` of `<br/>`-separated lines styled only with `<b>`,
   `<i>` and `<font size>`: grammar on the headword line, bold sense numbers,
   smaller indented examples with citations shortened to the author.
9. A form shared by two words opens the first entry in index order, so «мені»
   opened «мень» (a fish) instead of «я». pymorphy3 has no Ukrainian
   frequencies, so each headword's frequency is counted in the dictionary's
   own text (7.6M words, 5M of them in quotations), and a shared form goes to the more frequent word.
   Entries with the same headword («рентген», «рентген…») are merged into one.
10. kindling stores the dictionary identifier in the ASIN records (EXTH 113
    and 504). A Kindle that sees an ASIN looks the cover up in the Amazon store
    and shows a blank library tile. `library_cover.py` renames both records
    after the build; on a Kindle the cover then shows, and lookups and
    Vocabulary Builder keep working.

## Known gaps

The SUM-11 source data (in every format of the upstream release: 127,068
records of the ~134k in print) lacks whole alphabetical blocks:

- «прот…» to «пущ…» except a few words (проти, проте, професор, прохання,
  прямо, психологія, пташка, пух);
- part of «прост…» (простягти);
- «замус…» to «зао…» (занадто, заняття);
- «п’я…» and part of «п’є…» (п’ять, п’яний);
- «об’…» and «обов’язок» (об’єкт, об’єднати);
- single words: «грунт», «гудзик», «дзига».

Tested on 16 novels, these gaps cost about 0.5% of words. The mixed dictionaries
fill some of them («п’ять», «професор», «психологія») from Wiktionary.

## Credits and license

SUM-11 data: [bakustarver/ukr-dictionaries-list-opensource](https://github.com/bakustarver/ukr-dictionaries-list-opensource).
[Ukrainian Wiktionary](https://uk.wiktionary.org/) by its contributors.
Inspired by [pavlo-liapin/kindle-eng-ukr-dictionary](https://github.com/pavlo-liapin/kindle-eng-ukr-dictionary).
Covers use the [e-Ukraine](https://thedigital.gov.ua/fonts) typeface by the
Ministry of Digital Transformation of Ukraine (design by Fedoriv, CC BY 4.0).
Built with [kindling](https://github.com/ciscoriordan/kindling),
[pymorphy3](https://github.com/no-plagiarism/pymorphy3) and pymorphy3-dicts-uk.

Code: [AGPL-3.0](LICENSE). Wiktionary texts are licensed under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), and the
dictionaries containing them are distributed under the same terms. The rights
to the SUM-11 text are not explicitly stated by the data source. The texts are
not stored in this repository and are only included in the free,
non-commercial `.mobi` releases. If you are a rights holder and object, please
open an issue and they will be removed.

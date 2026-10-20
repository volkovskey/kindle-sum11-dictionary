#!/usr/bin/env bash
# Build the dictionaries from scratch: download SUM-11 and the Ukrainian
# Wiktionary dump, generate OPF + HTML with build_dict.py, compile with kindling.
#
#   ./build.sh                  # all four variants      -> dist/*.mobi
#   MODE=wiki+sum11 ./build.sh  # one variant (sum11 | wiki | sum11+wiki | wiki+sum11)
#   NO_INFL=1 ./build.sh        # headwords only, no word forms -> dist/*-plain.mobi
set -euo pipefail
cd "$(dirname "$0")"

TAB_URL=https://github.com/bakustarver/ukr-dictionaries-list-opensource/releases/download/ukr-ukr_SUM-11_or_1/Tabfile-ukr-ukr_SUM-11_or_1.zip
TAB=work/ukr-ukr_SUM-11_or_1.txt
WIKI_URL=${WIKI_URL:-https://dumps.wikimedia.org/ukwiktionary/latest/ukwiktionary-latest-pages-articles.xml.bz2}
WIKI=work/ukwiktionary-pages-articles.xml.bz2
KINDLING_VERSION=v0.45.6
MODE=${MODE:-all}

mkdir -p work dist

if [ ! -f "$TAB" ]; then
    echo ">> downloading SUM-11 tab file"
    curl -fL -o work/tab.zip "$TAB_URL"
    unzip -j -o work/tab.zip '*.txt' -d work
fi

if [ ! -f "$WIKI" ]; then
    echo ">> downloading Ukrainian Wiktionary dump"
    curl -fL -o "$WIKI" "$WIKI_URL"
fi

if [ ! -x .venv/bin/python ]; then
    echo ">> creating venv"
    python3 -m venv .venv
    .venv/bin/pip install -q -r requirements.txt
fi

if command -v kindling-cli >/dev/null; then
    KINDLING=kindling-cli
else
    case "$(uname -s)-$(uname -m)" in
        Darwin-arm64)  asset=kindling-cli-mac-apple-silicon ;;
        Darwin-x86_64) asset=kindling-cli-mac-intel ;;
        Linux-x86_64)  asset=kindling-cli-linux ;;
        *) echo "no kindling binary for $(uname -s)-$(uname -m); install it from https://github.com/ciscoriordan/kindling" >&2; exit 1 ;;
    esac
    KINDLING=work/$asset
    if [ ! -x "$KINDLING" ]; then
        echo ">> downloading kindling $KINDLING_VERSION"
        curl -fL -o "$KINDLING" "https://github.com/ciscoriordan/kindling/releases/download/$KINDLING_VERSION/$asset"
        chmod +x "$KINDLING"
    fi
fi

if [ "${NO_INFL:-}" = 1 ]; then out=build-plain suffix=-plain; else out=build suffix=; fi

echo ">> generating $out/"
rm -rf "$out"
.venv/bin/python -I build_dict.py --mode "$MODE" --sum "$TAB" --wiki "$WIKI" "$out"

for opf in "$out"/*/dict.opf; do
    name=$(basename "$(dirname "$opf")")
    echo ">> compiling dist/$name$suffix.mobi"
    "$KINDLING" build "$opf" -o "dist/$name$suffix.mobi"
done
ls -l dist/

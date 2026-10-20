#!/usr/bin/env bash
# Build sum11.mobi from scratch: download the SUM-11 tab file, generate
# OPF + HTML with build_sum.py, compile with kindling.
#
#   ./build.sh            # full dictionary with word forms -> sum11.mobi
#   NO_INFL=1 ./build.sh  # headwords only                  -> sum11-plain.mobi
set -euo pipefail
cd "$(dirname "$0")"

TAB_URL=https://github.com/bakustarver/ukr-dictionaries-list-opensource/releases/download/ukr-ukr_SUM-11_or_1/Tabfile-ukr-ukr_SUM-11_or_1.zip
TAB=work/ukr-ukr_SUM-11_or_1.txt
KINDLING_VERSION=v0.45.6

mkdir -p work

if [ ! -f "$TAB" ]; then
    echo ">> downloading SUM-11 tab file"
    curl -fL -o work/tab.zip "$TAB_URL"
    unzip -j -o work/tab.zip '*.txt' -d work
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

if [ "${NO_INFL:-}" = 1 ]; then out=build-plain mobi=sum11-plain.mobi; else out=build mobi=sum11.mobi; fi

echo ">> generating $out/"
rm -rf "$out"
.venv/bin/python -I build_sum.py "$TAB" "$out"

echo ">> compiling $mobi"
"$KINDLING" build "$out/sum11.opf" -o "$mobi"
ls -l "$mobi"

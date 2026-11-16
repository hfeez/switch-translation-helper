#!/usr/bin/env bash
# Build Linux/macOS. Pakai: ./build.sh [onefile]
set -euo pipefail
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
python -m pip install -q -r requirements.txt pyinstaller
python -m unittest discover -s tests
MODE=--onedir; [ "${1:-}" = "onefile" ] && MODE=--onefile
pyinstaller --noconfirm --clean --windowed $MODE --name SwitchTranslationHelper main.py
echo "Selesai. Lihat folder dist/"

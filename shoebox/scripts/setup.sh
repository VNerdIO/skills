#!/usr/bin/env bash
# Create (or reuse) the shoebox virtualenv and print its python path on the last line.
# Pillow is required. face_recognition (dlib) is optional: if it fails to build,
# the skill still works and falls back to Claude-vision-only person matching.
set -euo pipefail

VENV="${SHOEBOX_VENV:-$HOME/.local/share/shoebox/venv}"

if ! command -v exiftool >/dev/null 2>&1; then
  echo "ERROR: exiftool not found. Install with: brew install exiftool" >&2
  exit 1
fi

# dlib does not build on very new Pythons, so pin 3.12. uv can fetch it if it's not installed.
if [ ! -x "$VENV/bin/python" ]; then
  mkdir -p "$(dirname "$VENV")"
  if command -v uv >/dev/null 2>&1; then
    echo "Creating venv at $VENV (uv, Python 3.12)" >&2
    uv venv -q --python 3.12 "$VENV" >&2
  else
    PY=""
    for c in python3.12 python3.11 python3.13 python3; do
      if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
    done
    echo "Creating venv at $VENV with $PY" >&2
    "$PY" -m venv "$VENV"
  fi
fi

P="$VENV/bin/python"
if command -v uv >/dev/null 2>&1; then
  pipi() { uv pip install -q --python "$P" "$@"; }
else
  "$P" -m pip install -q --upgrade pip >&2
  pipi() { "$P" -m pip install -q "$@"; }
fi
"$P" -c "import PIL, numpy" 2>/dev/null || pipi Pillow numpy >&2

if ! "$P" -c "import face_recognition" 2>/dev/null; then
  echo "Installing face_recognition..." >&2
  # face_recognition_models imports pkg_resources, removed in newer setuptools.
  pipi "setuptools<81" >&2
  # Prefer the prebuilt dlib-bin wheel: building dlib from source fails on recent macOS
  # SDKs (bundled libpng: 'fp.h' not found). face_recognition is installed --no-deps so it
  # doesn't pull the source 'dlib' package back in.
  if { pipi dlib-bin >&2 || { pipi cmake >&2 && PATH="$VENV/bin:$PATH" pipi --no-build-isolation dlib >&2; }; } \
     && pipi --no-deps face_recognition >&2 \
     && pipi face_recognition_models Click >&2; then
    echo "face_recognition installed." >&2
  else
    echo "WARNING: face_recognition failed to install; continuing without local face clustering." >&2
  fi
fi

"$P" -c "import face_recognition" 2>/dev/null && echo "FACES=yes" >&2 || echo "FACES=no" >&2
echo "$P"

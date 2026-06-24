#!/usr/bin/env bash
# ig-clean — strip AI provenance metadata (C2PA / IPTC / XMP / EXIF) so Instagram
# does not apply the "AI Info" / "Made with AI" label.
#
# Usage:
#   ./clean.sh                      # process every image in ./in  -> ./out
#   ./clean.sh path/to/folder       # process a folder -> ./out
#   ./clean.sh img1.jpg img2.png    # process specific files -> ./out
#
# Strategy per file:
#   PNG / WebP / TIFF (lossless)  -> re-encode + strip  (zero quality loss, guarantees C2PA gone)
#   JPEG / HEIC (lossy)           -> lossless metadata strip via exiftool (pixels untouched);
#                                    re-encode fallback ONLY if a signal survives.
#
# Originals are never modified. Cleaned files land in ./out.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="$SCRIPT_DIR/out"
mkdir -p "$OUT_DIR"

# AI signals we check for in the BEFORE/AFTER report.
SIGNAL_RE='C2PA|JUMBF|jumbf|DigitalSourceType|digitalSourceType|trainedAlgorithmicMedia|compositeWithTrained|Firefly|OpenAI|DALL|GPT|Generative|Stable Diffusion|Midjourney|Software'

# ---- collect input files -------------------------------------------------
declare -a FILES=()
if [[ $# -eq 0 ]]; then
  while IFS= read -r -d '' f; do FILES+=("$f"); done \
    < <(find "$SCRIPT_DIR/in" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' -o -iname '*.tif' -o -iname '*.tiff' -o -iname '*.heic' \) -print0 2>/dev/null)
elif [[ $# -eq 1 && -d "$1" ]]; then
  while IFS= read -r -d '' f; do FILES+=("$f"); done \
    < <(find "$1" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' -o -iname '*.tif' -o -iname '*.tiff' -o -iname '*.heic' \) -print0)
else
  FILES=("$@")
fi

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "No images found. Put photos in $SCRIPT_DIR/in or pass paths/folder as arguments."
  exit 1
fi

signals_in() { exiftool -a -G1 "$1" 2>/dev/null | grep -Ei "$SIGNAL_RE" || true; }

echo "ig-clean — processing ${#FILES[@]} image(s)"
echo "output -> $OUT_DIR"
echo

CLEAN=0; FLAGGED=0
for src in "${FILES[@]}"; do
  base="$(basename "$src")"
  ext="${base##*.}"; ext_lc="$(echo "$ext" | tr '[:upper:]' '[:lower:]')"
  dst="$OUT_DIR/$base"

  echo "============================================================"
  echo "FILE: $base"

  before="$(signals_in "$src")"
  if [[ -n "$before" ]]; then
    echo "  BEFORE — AI/provenance signals found:"
    echo "$before" | sed 's/^/    /'
  else
    echo "  BEFORE — no obvious AI metadata (cleaning anyway)"
  fi

  case "$ext_lc" in
    png|webp|tif|tiff)
      # Lossless formats: re-encode (drops C2PA chunks + every metadata container), then belt-and-suspenders strip.
      magick "$src" -auto-orient -strip "$dst"
      exiftool -all= -overwrite_original -P "$dst" >/dev/null 2>&1 || true
      ;;
    jpg|jpeg|heic)
      # Lossy: keep pixels byte-for-byte, strip metadata losslessly. Bake orientation so nothing rotates.
      cp "$src" "$dst"
      exiftool -all= -tagsfromfile @ -Orientation -overwrite_original -P "$dst" >/dev/null 2>&1 || \
        exiftool -all= -overwrite_original -P "$dst" >/dev/null 2>&1
      # Verify; if anything survived (stubborn JUMBF), re-encode as fallback.
      if [[ -n "$(signals_in "$dst")" ]]; then
        echo "  ! residual signal after lossless strip — re-encoding as fallback"
        magick "$src" -auto-orient -strip -quality 96 "$dst"
        exiftool -all= -overwrite_original -P "$dst" >/dev/null 2>&1 || true
      fi
      ;;
    *)
      echo "  ! unsupported extension .$ext — skipped"; continue ;;
  esac

  after="$(signals_in "$dst")"
  if [[ -z "$after" ]]; then
    echo "  AFTER  — CLEAN ✅  no AI/provenance signals remain"
    CLEAN=$((CLEAN+1))
  else
    echo "  AFTER  — ⚠️ signals still present:"
    echo "$after" | sed 's/^/    /'
    FLAGGED=$((FLAGGED+1))
  fi
done

echo "============================================================"
echo "Done. Clean: $CLEAN   Needs review: $FLAGGED"
echo "Cleaned files are in: $OUT_DIR"

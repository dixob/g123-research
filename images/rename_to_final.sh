#!/bin/bash
# VLM Game Understanding — Corrected Final Rename Script
# Renames the 12 currently-named files to match hsdxd_annotations_final.json screenshot_ids
# Uses temp names to avoid collision chains
#
# Usage:
#   bash rename_to_final.sh --dry-run   (preview only)
#   bash rename_to_final.sh             (rename for real)

DRY_RUN=false
[[ "$1" == "--dry-run" ]] && DRY_RUN=true

SKIPPED=0
RENAMED=0
ERRORS=0

do_rename() {
  local src="$1"
  local dst="$2"
  if [ ! -f "$src" ]; then
    echo "  SKIP (not found): $src"
    ((SKIPPED++))
    return
  fi
  if [ "$DRY_RUN" = true ]; then
    echo "  DRY-RUN: $src → $dst"
  else
    mv "$src" "$dst"
    if [ $? -eq 0 ]; then
      echo "  OK: $src → $dst"
      ((RENAMED++))
    else
      echo "  ERROR: $src → $dst"
      ((ERRORS++))
    fi
  fi
}

echo "=== VLM Final Rename (12 files) ==="
$DRY_RUN && echo "--- DRY RUN MODE ---"
echo ""

echo "--- Step 1: Rename to temp names (avoids collision chains) ---"
do_rename "highschooldxd_battle_002_EN.png"           "_tmp_battle_001_EN.png"
do_rename "highschooldxd_battle_003_EN.png"           "_tmp_battle_002_EN.png"
do_rename "highschooldxd_idle_overworld_001_EN.png"   "_tmp_overworld_071_EN.png"
do_rename "highschooldxd_idle_overworld_006_EN.png"   "_tmp_overworld_073_EN.png"
do_rename "highschooldxd_idle_overworld_007_EN.png"   "_tmp_overworld_074_EN.png"
do_rename "highschooldxd_idle_overworld_008_EN.png"   "_tmp_overworld_075_EN.png"
do_rename "highschooldxd_idle_overworld_014_EN.png"   "_tmp_overworld_076_EN.png"
do_rename "highschooldxd_idle_overworld_015_EN.png"   "_tmp_overworld_077_EN.png"
do_rename "highschooldxd_idle_overworld_016_EN.png"   "_tmp_overworld_078_EN.png"
do_rename "highschooldxd_idle_overworld_017_EN.png"   "_tmp_overworld_079_EN.png"
do_rename "highschooldxd_idle_overworld_018_EN.png"   "_tmp_overworld_080_EN.png"
do_rename "highschooldxd_post_battle_001_EN.png"      "_tmp_post_battle_091_EN.png"

echo ""
echo "--- Step 2: Rename temp names to final names ---"
do_rename "_tmp_battle_001_EN.png"      "highschooldxd_battle_001_EN.png"
do_rename "_tmp_battle_002_EN.png"      "highschooldxd_battle_002_EN.png"
do_rename "_tmp_overworld_071_EN.png"   "highschooldxd_idle_overworld_071_EN.png"
do_rename "_tmp_overworld_073_EN.png"   "highschooldxd_idle_overworld_073_EN.png"
do_rename "_tmp_overworld_074_EN.png"   "highschooldxd_idle_overworld_074_EN.png"
do_rename "_tmp_overworld_075_EN.png"   "highschooldxd_idle_overworld_075_EN.png"
do_rename "_tmp_overworld_076_EN.png"   "highschooldxd_idle_overworld_076_EN.png"
do_rename "_tmp_overworld_077_EN.png"   "highschooldxd_idle_overworld_077_EN.png"
do_rename "_tmp_overworld_078_EN.png"   "highschooldxd_idle_overworld_078_EN.png"
do_rename "_tmp_overworld_079_EN.png"   "highschooldxd_idle_overworld_079_EN.png"
do_rename "_tmp_overworld_080_EN.png"   "highschooldxd_idle_overworld_080_EN.png"
do_rename "_tmp_post_battle_091_EN.png" "highschooldxd_post_battle_091_EN.png"

echo ""
echo "=== Summary ==="
if [ "$DRY_RUN" = true ]; then
  echo "  Dry run complete — no files changed"
  echo ""
  echo "  NOTE: 41 files on disk have no matching annotation in hsdxd_annotations_final.json"
  echo "  These are unannotated screenshots — they can stay as-is or be moved to an /unannotated subfolder"
  echo "  Run: ls highschooldxd_*.png arifureta_*.png | grep -v -f <(python -c \""
  echo "  import json; f=open('hsdxd_annotations_final.json',encoding='utf-8'); d=json.load(f)"
  echo "  [print(a['screenshot_id']+'.png') for a in d['annotations']]\")"
  echo "  to see which named files have no annotation match."
else
  echo "  Renamed: $RENAMED"
  echo "  Skipped: $SKIPPED"
  echo "  Errors:  $ERRORS"
  echo ""
  echo "  NOTE: 41 files on disk have no matching annotation in hsdxd_annotations_final.json"
  echo "  These are unannotated screenshots — safe to ignore or move to /unannotated"
fi

#!/bin/bash
# VLM Game Understanding — Screenshot Rename Script
# Run from the folder containing your screenshots: bash rename_screenshots.sh
# Dry-run mode: bash rename_screenshots.sh --dry-run

DRY_RUN=false
[[ "$1" == "--dry-run" ]] && DRY_RUN=true

rename_file() {
  local src="$1"
  local dst="$2"
  if [ ! -f "$src" ]; then
    echo "  SKIP (not found): $src"
    return
  fi
  if [ "$DRY_RUN" = true ]; then
    echo "  DRY-RUN: $src → $dst"
  else
    mv "$src" "$dst"
    echo "  RENAMED: $src → $dst"
  fi
}

echo "=== VLM Screenshot Rename ==="
$DRY_RUN && echo "--- DRY RUN MODE --- (no files will be changed)"
echo ""

echo "--- HSDxD EN ---"
rename_file "Screenshot_(90).png"  "highschooldxd_idle_overworld_001_EN.png"
rename_file "Screenshot_(91).png"  "highschooldxd_pre_battle_001_EN.png"
rename_file "Screenshot_(92).png"  "highschooldxd_battle_001_EN.png"
rename_file "Screenshot_(93).png"  "highschooldxd_battle_002_EN.png"
rename_file "Screenshot_(94).png"  "highschooldxd_battle_003_EN.png"
rename_file "Screenshot_(95).png"  "highschooldxd_post_battle_001_EN.png"
rename_file "Screenshot_(97).png"  "highschooldxd_idle_overworld_002_EN.png"
rename_file "Screenshot_(96).png"  "highschooldxd_idle_overworld_003_EN.png"
rename_file "Screenshot_(99).png"  "highschooldxd_idle_overworld_005_EN.png"
rename_file "Screenshot_(100).png" "highschooldxd_idle_overworld_006_EN.png"
rename_file "Screenshot_(101).png" "highschooldxd_idle_overworld_007_EN.png"
rename_file "Screenshot_(102).png" "highschooldxd_idle_overworld_008_EN.png"
rename_file "Screenshot_(103).png" "highschooldxd_idle_overworld_009_EN.png"
rename_file "Screenshot_(104).png" "highschooldxd_idle_overworld_010_EN.png"
rename_file "Screenshot_(105).png" "highschooldxd_idle_overworld_011_EN.png"
rename_file "Screenshot_(106).png" "highschooldxd_idle_overworld_012_EN.png"
rename_file "Screenshot_(107).png" "highschooldxd_idle_overworld_013_EN.png"
rename_file "Screenshot_(108).png" "highschooldxd_idle_overworld_014_EN.png"
rename_file "Screenshot_(109).png" "highschooldxd_idle_overworld_015_EN.png"
rename_file "Screenshot_(110).png" "highschooldxd_idle_overworld_016_EN.png"
rename_file "Screenshot_(111).png" "highschooldxd_idle_overworld_017_EN.png"
rename_file "Screenshot_(112).png" "highschooldxd_idle_overworld_018_EN.png"
rename_file "Screenshot_(113).png" "highschooldxd_idle_overworld_019_EN.png"
rename_file "Screenshot_(114).png" "highschooldxd_idle_overworld_020_EN.png"
rename_file "Screenshot_(115).png" "highschooldxd_idle_overworld_021_EN.png"
rename_file "Screenshot_(116).png" "highschooldxd_idle_overworld_022_EN.png"
rename_file "Screenshot_(120).png" "highschooldxd_gacha_001_EN.png"
rename_file "Screenshot_(121).png" "highschooldxd_gacha_002_EN.png"
rename_file "Screenshot_(122).png" "highschooldxd_gacha_003_EN.png"
rename_file "Screenshot_(123).png" "highschooldxd_gacha_004_EN.png"
rename_file "Screenshot_(124).png" "highschooldxd_gacha_005_EN.png"
rename_file "Screenshot_(125).png" "highschooldxd_gacha_006_EN.png"
rename_file "Screenshot_(170).png" "highschooldxd_menu_001_EN.png"

echo ""
echo "--- Arifureta JP ---"
rename_file "Screenshot_(96).png"  "arifureta_gacha_001_JP.png"
rename_file "Screenshot_(97).png"  "arifureta_gacha_002_JP.png"
rename_file "Screenshot_(98).png"  "arifureta_gacha_003_JP.png"
rename_file "Screenshot_(99).png"  "arifureta_gacha_004_JP.png"

echo ""
echo "--- HSDxD JP ---"
rename_file "Screenshot_(128).png" "highschooldxd_idle_overworld_001_JP.png"
rename_file "Screenshot_(129).png" "highschooldxd_idle_overworld_002_JP.png"
rename_file "Screenshot_(130).png" "highschooldxd_idle_overworld_003_JP.png"
rename_file "Screenshot_(131).png" "highschooldxd_pre_battle_001_JP.png"
rename_file "Screenshot_(132).png" "highschooldxd_battle_001_JP.png"
rename_file "Screenshot_(133).png" "highschooldxd_post_battle_001_JP.png"
rename_file "Screenshot_(134).png" "highschooldxd_battle_002_JP.png"
rename_file "Screenshot_(135).png" "highschooldxd_battle_003_JP.png"
rename_file "Screenshot_(136).png" "highschooldxd_battle_004_JP.png"
rename_file "Screenshot_(137).png" "highschooldxd_gacha_001_JP.png"
rename_file "Screenshot_(138).png" "highschooldxd_gacha_002_JP.png"
rename_file "Screenshot_(139).png" "highschooldxd_gacha_003_JP.png"
rename_file "Screenshot_(140).png" "highschooldxd_gacha_004_JP.png"
rename_file "Screenshot_(141).png" "highschooldxd_gacha_005_JP.png"
rename_file "Screenshot_(142).png" "highschooldxd_gacha_006_JP.png"
rename_file "Screenshot_(143).png" "highschooldxd_gacha_007_JP.png"
rename_file "Screenshot_(144).png" "highschooldxd_gacha_008_JP.png"
rename_file "Screenshot_(145).png" "highschooldxd_gacha_009_JP.png"
rename_file "Screenshot_(169).png" "highschooldxd_menu_001_JP.png"

echo ""
echo "=== Done ==="

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
rename_file "Screenshot (90).png"  "highschooldxd_idle_overworld_001_EN.png"
rename_file "Screenshot (91).png"  "highschooldxd_pre_battle_001_EN.png"
rename_file "Screenshot (92).png"  "highschooldxd_battle_001_EN.png"
rename_file "Screenshot (93).png"  "highschooldxd_battle_002_EN.png"
rename_file "Screenshot (94).png"  "highschooldxd_battle_003_EN.png"
rename_file "Screenshot (95).png"  "highschooldxd_post_battle_001_EN.png"
rename_file "Screenshot (97).png"  "highschooldxd_idle_overworld_002_EN.png"
rename_file "Screenshot (96).png"  "highschooldxd_idle_overworld_003_EN.png"
rename_file "Screenshot (99).png"  "highschooldxd_idle_overworld_005_EN.png"
rename_file "Screenshot (100).png" "highschooldxd_idle_overworld_006_EN.png"
rename_file "Screenshot (101).png" "highschooldxd_idle_overworld_007_EN.png"
rename_file "Screenshot (102).png" "highschooldxd_idle_overworld_008_EN.png"
rename_file "Screenshot (103).png" "highschooldxd_idle_overworld_009_EN.png"
rename_file "Screenshot (104).png" "highschooldxd_idle_overworld_010_EN.png"
rename_file "Screenshot (105).png" "highschooldxd_idle_overworld_011_EN.png"
rename_file "Screenshot (106).png" "highschooldxd_idle_overworld_012_EN.png"
rename_file "Screenshot (107).png" "highschooldxd_idle_overworld_013_EN.png"
rename_file "Screenshot (108).png" "highschooldxd_idle_overworld_014_EN.png"
rename_file "Screenshot (109).png" "highschooldxd_idle_overworld_015_EN.png"
rename_file "Screenshot (110).png" "highschooldxd_idle_overworld_016_EN.png"
rename_file "Screenshot (111).png" "highschooldxd_idle_overworld_017_EN.png"
rename_file "Screenshot (112).png" "highschooldxd_idle_overworld_018_EN.png"
rename_file "Screenshot (113).png" "highschooldxd_idle_overworld_019_EN.png"
rename_file "Screenshot (114).png" "highschooldxd_idle_overworld_020_EN.png"
rename_file "Screenshot (115).png" "highschooldxd_idle_overworld_021_EN.png"
rename_file "Screenshot (116).png" "highschooldxd_idle_overworld_022_EN.png"
rename_file "Screenshot (120).png" "highschooldxd_gacha_001_EN.png"
rename_file "Screenshot (121).png" "highschooldxd_gacha_002_EN.png"
rename_file "Screenshot (122).png" "highschooldxd_gacha_003_EN.png"
rename_file "Screenshot (123).png" "highschooldxd_gacha_004_EN.png"
rename_file "Screenshot (124).png" "highschooldxd_gacha_005_EN.png"
rename_file "Screenshot (125).png" "highschooldxd_gacha_006_EN.png"
rename_file "Screenshot (170).png" "highschooldxd_menu_001_EN.png"

echo ""
echo "--- Arifureta JP ---"
rename_file "Screenshot (96).png"  "arifureta_gacha_001_JP.png"
rename_file "Screenshot (97).png"  "arifureta_gacha_002_JP.png"
rename_file "Screenshot (98).png"  "arifureta_gacha_003_JP.png"
rename_file "Screenshot (99).png"  "arifureta_gacha_004_JP.png"

echo ""
echo "--- HSDxD JP ---"
rename_file "Screenshot (128).png" "highschooldxd_idle_overworld_001_JP.png"
rename_file "Screenshot (129).png" "highschooldxd_idle_overworld_002_JP.png"
rename_file "Screenshot (130).png" "highschooldxd_idle_overworld_003_JP.png"
rename_file "Screenshot (131).png" "highschooldxd_pre_battle_001_JP.png"
rename_file "Screenshot (132).png" "highschooldxd_battle_001_JP.png"
rename_file "Screenshot (133).png" "highschooldxd_post_battle_001_JP.png"
rename_file "Screenshot (134).png" "highschooldxd_battle_002_JP.png"
rename_file "Screenshot (135).png" "highschooldxd_battle_003_JP.png"
rename_file "Screenshot (136).png" "highschooldxd_battle_004_JP.png"
rename_file "Screenshot (137).png" "highschooldxd_gacha_001_JP.png"
rename_file "Screenshot (138).png" "highschooldxd_gacha_002_JP.png"
rename_file "Screenshot (139).png" "highschooldxd_gacha_003_JP.png"
rename_file "Screenshot (140).png" "highschooldxd_gacha_004_JP.png"
rename_file "Screenshot (141).png" "highschooldxd_gacha_005_JP.png"
rename_file "Screenshot (142).png" "highschooldxd_gacha_006_JP.png"
rename_file "Screenshot (143).png" "highschooldxd_gacha_007_JP.png"
rename_file "Screenshot (144).png" "highschooldxd_gacha_008_JP.png"
rename_file "Screenshot (145).png" "highschooldxd_gacha_009_JP.png"
rename_file "Screenshot (169).png" "highschooldxd_menu_001_JP.png"

echo ""
echo "=== Done ==="

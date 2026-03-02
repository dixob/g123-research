# G123 VLM Research — Annotation & Benchmark Workflow
# ===================================================
#
# Annotation loop:
#   1. make template       → print blank compact template
#   2. (human fills)       → save to data/annotations/compact/<id>.json
#   3. make hydrate        → expand compact → full schema in data/annotations/full/
#   4. make validate       → validate all full-schema annotations
#   5. make benchmark      → run VLM benchmark against full annotations
#
# Quick test:
#   make smoke             → benchmark 1 model, 3 samples
#

COMPACT_DIR  = data/annotations/compact
FULL_DIR     = data/annotations/full
LEGACY_DIR   = data/annotations/legacy
IMAGES_DIR   = images
RESULTS_DIR  = benchmark_results
ANNOTATOR    = robert

.PHONY: template hydrate validate benchmark smoke clean-results help

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

template:  ## Print a blank compact annotation template
	python g123_schema.py template

hydrate:  ## Hydrate compact annotations → full schema
	python g123_schema.py hydrate $(COMPACT_DIR) $(FULL_DIR) $(ANNOTATOR)

validate:  ## Validate all full-schema annotations
	python g123_schema.py validate $(FULL_DIR)

benchmark:  ## Run full benchmark (all models, all annotations)
	python run_benchmark.py --annotations-dir $(FULL_DIR) --images-dir $(IMAGES_DIR)

smoke:  ## Quick benchmark — 1 model, 3 samples
	python run_benchmark.py --annotations-dir $(FULL_DIR) --images-dir $(IMAGES_DIR) \
	  --models gpt-4o --max-samples 3 --no-save

benchmark-battle:  ## Benchmark battle screens only
	python run_benchmark.py --annotations-dir $(FULL_DIR) --images-dir $(IMAGES_DIR) \
	  --screen-types battle

benchmark-gacha:  ## Benchmark gacha screens only
	python run_benchmark.py --annotations-dir $(FULL_DIR) --images-dir $(IMAGES_DIR) \
	  --screen-types gacha

export-schema:  ## Export Pydantic model as JSON Schema file
	python g123_schema.py export-schema

clean-results:  ## Remove benchmark result files
	rm -rf $(RESULTS_DIR)/*

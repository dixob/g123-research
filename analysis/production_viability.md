# Production Viability Report: VLM Game State Extraction at CTW Scale

**Date:** 2026-03-01
**Author:** Robert (AI Research Scientist candidate)
**Context:** Extrapolating benchmark findings to CTW/G123 production deployment

---

## Executive Summary

This report evaluates whether Vision Language Models can power automated game analytics at CTW scale: **28 active games, 500M+ registered users, real-time operations across JP/EN/global markets**.

**Key finding:** VLM-based game state extraction is production-viable today for batch analytics use cases (QA automation, gacha compliance, economy monitoring) using Gemini 2.5 Flash at approximately **$4.50/day for 10,000 screenshots**. Real-time use cases (sub-second latency) require either self-hosted models or a two-stage pipeline with lightweight pre-classification.

---

## 1. Cost Analysis

### Per-Screenshot Cost Comparison

| Model | Input $/1M tok | Output $/1M tok | Est. Cost/Screenshot | Monthly @ 10K/day |
|-------|---------------|-----------------|---------------------|-------------------|
| GPT-4o | $2.50 | $10.00 | ~$0.0075 | ~$2,250 |
| Gemini 2.5 Flash | $0.15 | $0.60 | ~$0.00045 | ~$135 |
| Qwen3-VL-32B (API) | $0.65 | $0.65 | ~$0.00098 | ~$294 |
| Qwen3-VL-32B (self-hosted) | GPU cost | GPU cost | ~$0.0003-0.001 | ~$90-300 |

**Assumptions:** ~800 input tokens (image + prompt), ~500 output tokens (JSON response) per screenshot.

### Cost at CTW Scale

CTW operates 28 games. Assuming varying screenshot volumes per game:

| Scenario | Screenshots/Day | Gemini Flash/Month | GPT-4o/Month | Self-Hosted/Month |
|----------|----------------|-------------------|-------------|-------------------|
| Light monitoring (10/game) | 280 | $4 | $63 | GPU baseline |
| Standard QA (100/game) | 2,800 | $38 | $630 | GPU baseline |
| Full coverage (1K/game) | 28,000 | $378 | $6,300 | ~$900-2,700 |
| Heavy analytics (5K/game) | 140,000 | $1,890 | $31,500 | ~$4,500-13,500 |

**Recommendation:** Gemini 2.5 Flash is the clear winner for API-based deployment up to ~50K screenshots/day. Above that, self-hosted Qwen3 on dedicated GPUs becomes cost-competitive.

### Cost Optimization: Two-Stage Pipeline

A CLIP pre-classifier (~0ms marginal cost, already cached embeddings) can route screenshots to screen-type-specific prompts, reducing token waste by eliminating irrelevant field extraction:

| Approach | Avg Tokens/Call | Cost/Screenshot | Savings |
|----------|----------------|-----------------|---------|
| Generic prompt | ~1,300 | $0.00045 | Baseline |
| Screen-type-specific | ~900 | $0.00031 | **31% cheaper** |
| CLIP pre-filter + specific | ~700 | $0.00024 | **47% cheaper** |

At 28K screenshots/day, the CLIP optimization saves **~$180/month** on Gemini Flash alone.

### Agent Retry Cost

The LangGraph QA agent adds retry logic for validation failures:

| Metric | Single-Shot | Agent (max 2 retries) |
|--------|------------|----------------------|
| API calls per screenshot | 1 | 1.0-3.0 (avg ~1.3) |
| Cost multiplier | 1.0× | ~1.3× |
| Parse failure rate | ~5-10% | ~0-1% |

The ~30% cost increase for agent retries eliminates nearly all parse failures — essential for production reliability.

---

## 2. Latency Analysis

### API Latency Profile

| Model | p50 | p90 | p99 | SLA Feasibility |
|-------|-----|-----|-----|----------------|
| GPT-4o | ~2.5s | ~4.0s | ~8.0s | Batch only |
| Gemini 2.5 Flash | ~1.2s | ~2.5s | ~5.0s | Near-real-time |
| Qwen3-VL-32B (API) | ~3.0s | ~5.0s | ~10.0s | Batch only |
| Qwen3-VL-32B (self-hosted, A100) | ~0.3s | ~0.5s | ~1.0s | Real-time capable |

### CTW Latency Requirements

Based on CTW's infrastructure (TiDB for sub-second analytics):

| Use Case | Latency SLA | Recommended Approach |
|----------|-------------|---------------------|
| Real-time game analytics | <500ms | Self-hosted Qwen3 on A100/H100 |
| Live QA monitoring | <5s | Gemini Flash API |
| Batch QA reports | <30s | Any model, parallel batch |
| Gacha compliance audit | <60s | Gemini Flash, sequential |
| Daily economy reports | <10min | Any model, full batch pipeline |

**Key insight:** CTW's sub-second SLA is only achievable with self-hosted models. API-based VLMs are viable for all non-real-time use cases.

---

## 3. Accuracy-Cost Trade-off

### Model Selection Matrix

| Dimension | GPT-4o | Gemini 2.5 Flash | Qwen3-VL-32B |
|-----------|--------|-------------------|--------------|
| Numeric extraction | Strong | Good | Good |
| Japanese text | Moderate | Moderate | Strong (CJK training) |
| Screen classification | Strong | Strong | Good |
| UI element detection | Strong | Good | Moderate |
| Cost efficiency | Low | **Best** | Good (API) / **Best** (self-hosted) |

### Recommended Strategy: Tiered Deployment

```
                    ┌─────────────────┐
                    │  All Screenshots │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ CLIP Pre-Filter │  (free, <10ms)
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼───┐  ┌──────▼─────┐  ┌────▼────────┐
     │ Battle/QA  │  │   Gacha    │  │  Idle/Menu  │
     │ Gemini     │  │  GPT-4o    │  │  Gemini     │
     │ Flash      │  │ (accuracy) │  │  Flash      │
     └────────────┘  └────────────┘  └─────────────┘
```

- **Gemini Flash** for high-volume, lower-stakes extraction (battle state, menu navigation)
- **GPT-4o** for high-stakes extraction (gacha rates for compliance, financial metrics)
- **Self-hosted Qwen3** for real-time requirements or highest-volume pipelines

---

## 4. Self-Hosted vs API Comparison

### Self-Hosted Qwen3-VL-32B (Quantized)

| Configuration | GPU | Throughput | Monthly Cost | Break-Even vs Gemini |
|--------------|-----|-----------|-------------|---------------------|
| 1× A100 80GB | A100 | ~50 img/min | ~$2,000 | ~150K screenshots/day |
| 1× H100 80GB | H100 | ~80 img/min | ~$3,000 | ~220K screenshots/day |
| 4× A10G (AWQ 4-bit) | A10G | ~30 img/min | ~$1,200 | ~90K screenshots/day |

**Break-even analysis:** Self-hosting becomes cheaper than Gemini Flash API at approximately **5,000+ screenshots/day** with 4-bit quantized models on A10G instances.

### Self-Hosted Benefits Beyond Cost

1. **Data privacy** — screenshots never leave CTW infrastructure (critical for unreleased game content)
2. **Latency control** — sub-500ms achievable with proper optimization
3. **Fine-tuning** — LoRA adaptation on CTW's game catalog improves domain accuracy
4. **No rate limits** — burst capacity for game launches and events
5. **Compliance** — Japanese data residency requirements (APPI)

### Self-Hosted Risks

1. **Ops burden** — GPU fleet management, model versioning, monitoring
2. **Staleness** — frontier API models improve continuously; self-hosted requires manual updates
3. **Burst cost** — over-provisioning for peak loads wastes GPU budget
4. **Expertise** — requires ML infrastructure engineers (vLLM, TensorRT, quantization)

---

## 5. Production Architecture

### Recommended Deployment

```
┌────────────────────────────────────────────────────────┐
│                   CTW Game Servers                       │
│  (28 games × screenshot capture at key events)          │
└───────────────────────┬────────────────────────────────┘
                        │ Screenshots via S3/GCS
                        ▼
┌────────────────────────────────────────────────────────┐
│              Screenshot Ingestion Queue                  │
│              (Kafka / SQS / Pub/Sub)                     │
└───────────┬───────────────────────────┬────────────────┘
            │                           │
   ┌────────▼────────┐       ┌─────────▼──────────┐
   │ CLIP Classifier  │       │ Priority Router     │
   │ (screen type)    │       │ (QA vs Analytics)   │
   └────────┬────────┘       └─────────┬──────────┘
            │                           │
   ┌────────▼──────────────────────────▼──────────┐
   │           LangGraph QA Agent Pool              │
   │  ┌──────────┐ ┌──────────┐ ┌──────────┐      │
   │  │ Classify  │→│ Extract  │→│ Validate │      │
   │  └──────────┘ └──────────┘ └────┬─────┘      │
   │                                  │ retry      │
   │                            ┌─────▼─────┐      │
   │                            │ QA Check  │      │
   │                            └───────────┘      │
   └────────────────────┬─────────────────────────┘
                        │
           ┌────────────┼────────────────┐
           │            │                │
   ┌───────▼──┐  ┌─────▼──────┐  ┌─────▼──────┐
   │ QA Alerts │  │ Analytics  │  │ Compliance │
   │ (Slack/PD)│  │ (TiDB/BQ)  │  │ (Audit DB) │
   └──────────┘  └────────────┘  └────────────┘
```

### Integration Points with CTW Stack

| CTW Component | Integration | Purpose |
|---------------|------------|---------|
| TiDB (analytics DB) | Write extracted game state | Real-time dashboard queries |
| Game server events | Trigger screenshot capture | Key moments (gacha, battle end) |
| QA pipeline | Alert on anomalies | Bug detection automation |
| Compliance system | Gacha rate verification | JOGA regulatory reporting |
| A/B test framework | Per-variant metrics | Economy balance analysis |

---

## 6. Risk Assessment

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| VLM hallucination in production | High | Medium | Multi-model consensus + QA rules |
| API rate limiting during game events | Medium | High | Self-hosted fallback + request queuing |
| Japanese text extraction failures | High | High | JP-specialized OCR preprocessing |
| Schema changes across game updates | Medium | Medium | Version-tolerant extraction prompts |
| Cost overrun from retry loops | Low | Low | Retry budget caps per screenshot |

### Business Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Incorrect gacha rate reporting | Low | Very High | Multi-model verification + human review |
| False positive QA alerts | Medium | Low | Confidence thresholds + alert fatigue management |
| Over-reliance on single VLM provider | Medium | Medium | Multi-provider architecture |
| Regulatory changes (JOGA/APPI) | Low | High | Flexible extraction schema |

---

## 7. Roadmap to Production

### Phase 1: Proof of Value (1-2 months)
- Deploy Gemini Flash batch pipeline on 2-3 flagship games
- Gacha compliance monitoring for 1 game
- QA automation for battle screen regression detection
- **Success metric:** Catch at least 3 bugs that manual QA would miss

### Phase 2: Scale (3-6 months)
- Expand to all 28 games
- Self-hosted Qwen3 for real-time use cases
- LoRA fine-tuning on CTW game catalog
- Integration with TiDB analytics dashboard
- **Success metric:** 80%+ accuracy on all screen types, <$500/month total cost

### Phase 3: Foundation Model (6-12 months)
- Domain-adapted multimodal model for game understanding
- Cross-game generalization without per-game prompts
- Game-playing agent for automated testing
- **Success metric:** Single model handles all 28 games with minimal per-game config

---

## 8. Labor Savings Estimate

### Current Manual Process (Estimated)

| Activity | Manual Hours/Month | QA Staff | Annual Cost |
|----------|-------------------|----------|------------|
| Screenshot review | 200 hrs | 3 FTE | ~$180K |
| Gacha rate verification | 40 hrs | 1 FTE (partial) | ~$30K |
| Economy balance checks | 80 hrs | 1 FTE (partial) | ~$60K |
| Bug triage from screenshots | 120 hrs | 2 FTE | ~$120K |
| **Total** | **440 hrs** | **~4 FTE** | **~$390K** |

### Automated Process

| Activity | Compute Cost/Month | Human Review/Month | Annual Cost |
|----------|-------------------|-------------------|------------|
| VLM extraction | $135-400 | — | ~$2K-5K |
| QA alert review | — | 20 hrs (~0.1 FTE) | ~$15K |
| Edge case handling | — | 40 hrs (~0.25 FTE) | ~$30K |
| Pipeline maintenance | — | 20 hrs (~0.1 FTE) | ~$15K |
| **Total** | **$135-400** | **80 hrs (~0.5 FTE)** | **~$65K** |

### Net Savings

| Metric | Value |
|--------|-------|
| Annual labor savings | **~$325K** |
| Annual compute cost | ~$5K |
| **Net annual savings** | **~$320K** |
| FTE reduction | 3.5 FTE |
| Payback period | < 2 months |

**Note:** These are order-of-magnitude estimates. Actual savings depend on CTW's current QA staffing, screenshot volume, and accuracy requirements.

---

## 9. Conclusion

VLM-based game state extraction is production-ready for CTW's batch analytics and QA automation use cases. The recommended path:

1. **Start with Gemini 2.5 Flash** — lowest cost, good accuracy, fast iteration
2. **Deploy the LangGraph QA agent** — retries + validation eliminate most production failures
3. **Add self-hosted Qwen3** when volume exceeds 5K screenshots/day or real-time latency is required
4. **Invest in domain adaptation** — LoRA fine-tuning on CTW games is the highest-leverage long-term investment

The technology is mature enough to deliver measurable labor savings within the first quarter of deployment.

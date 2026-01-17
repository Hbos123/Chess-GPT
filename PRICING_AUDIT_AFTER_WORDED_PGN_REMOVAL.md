# Pricing Audit - After Worded PGN Removal

**Date:** 2025-01-XX  
**Tier:** Standard (as per OpenAI pricing table)  
**Feature Removed:** `summariser_worded_pgn` LLM call

---

## Token Usage (Per Request)

Based on terminal log analysis from `terminals/9.txt`:

### Layer Breakdown

| Layer | Model | Input Tokens | Output Tokens | Total Tokens |
|-------|-------|--------------|---------------|--------------|
| **Planner** | `gpt-4o-mini` | 5,574 | 644 | 6,218 |
| **Summariser** | `gpt-5` | 2,181 | 6,670 | 8,851 |
| **Explainer** | `gpt-5` | 12,337 | 3,011 | 15,348 |
| **TOTAL** | - | **20,092** | **10,325** | **30,417** |

**Removed:** `summariser_worded_pgn` (was: 16,739 in, 8,563 out = 25,302 total tokens)

---

## Cost Calculation (Standard Tier)

### Pricing Rates (per 1M tokens)

| Model | Input | Cached Input | Output |
|-------|-------|--------------|--------|
| `gpt-4o-mini` | $0.15 | $0.075 | $0.60 |
| `gpt-5` | $1.25 | $0.125 | $10.00 |

*Note: Assuming no cached input tokens for this audit (cached token tracking not yet implemented)*

### Per-Layer Costs

#### 1. Planner (`gpt-4o-mini`)
- Input cost: (5,574 / 1,000,000) × $0.15 = **$0.0008361**
- Output cost: (644 / 1,000,000) × $0.60 = **$0.0003864**
- **Total: $0.0012225 per request**

#### 2. Summariser (`gpt-5`)
- Input cost: (2,181 / 1,000,000) × $1.25 = **$0.0027263**
- Output cost: (6,670 / 1,000,000) × $10.00 = **$0.0667000**
- **Total: $0.0694263 per request**

#### 3. Explainer (`gpt-5`)
- Input cost: (12,337 / 1,000,000) × $1.25 = **$0.0154213**
- Output cost: (3,011 / 1,000,000) × $10.00 = **$0.0301100**
- **Total: $0.0455313 per request**

---

## Total Cost Per Request

**$0.0012225 + $0.0694263 + $0.0455313 = $0.1161801 per request**

---

## Cost Per 100 Uses

| Metric | Value |
|--------|-------|
| **Per 100 requests** | **$11.62** |
| **Per 1,000 requests** | **$116.18** |
| **Per 10,000 requests** | **$1,161.80** |

---

## Cost Breakdown Per 100 Uses (By Layer)

| Layer | Cost per 100 Uses | % of Total |
|-------|-------------------|------------|
| Planner | $0.12 | 1.1% |
| Summariser | $6.94 | 59.8% |
| Explainer | $4.56 | 39.2% |
| **Total** | **$11.62** | **100%** |

---

## Savings from Worded PGN Removal

**Previous cost (with `worded_pgn`):**
- `summariser_worded_pgn`: (16,739 × $1.25 + 8,563 × $10.00) / 1,000,000 = **$0.1065538 per request**
- Previous total: $0.1161801 + $0.1065538 = **$0.2227339 per request**

**New cost (without `worded_pgn`):**
- **$0.1161801 per request**

**Savings:**
- **$0.1065538 per request** (48% reduction)
- **$10.66 per 100 uses**
- **$106.55 per 1,000 uses**

---

## Daily Usage Projections

| Daily Requests | Daily Cost | Monthly Cost (30 days) |
|----------------|------------|-------------------------|
| 100 | $11.62 | $348.60 |
| 500 | $58.09 | $1,742.70 |
| 1,000 | $116.18 | $3,485.40 |
| 5,000 | $580.90 | $17,427.00 |
| 10,000 | $1,161.80 | $34,854.00 |

---

## Notes

1. **Cached tokens:** This audit assumes zero cached input tokens. If cached tokens are enabled and tracked, costs would be lower (cached input is 10× cheaper for `gpt-5` and 2× cheaper for `gpt-4o-mini`).

2. **Token variance:** Actual token counts may vary by request complexity, position depth, and user query length.

3. **Model selection:** Planner uses `gpt-4o-mini` (cheaper), while Summariser and Explainer use `gpt-5` (more expensive but higher quality).

4. **Speed impact:** Removing `worded_pgn` also saves ~189 seconds per request (from terminal logs), significantly improving response latency.

---

## Recommendations

1. **Implement cached token tracking** to reduce costs further (especially for repeated prompts).
2. **Monitor actual usage** to validate these projections against real traffic.
3. **Consider tier optimization:** If latency allows, `gpt-5-mini` could reduce Summariser/Explainer costs by ~80% (at quality tradeoff).





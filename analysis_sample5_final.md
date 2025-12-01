# Sample5 Final (Balanced) — Quick Read

- Dataset: `results/results_sample5/debates_sample5-11-30-2025_final.jsonl` (297 debates, 9 models, 66 games each).
- Balance: all debaters appear exactly 66 times (pro/con mix).
- Ratings (Elo-style, higher is better):
  - openai-gpt-5.1 ~1651  
  - moonshotai-kimi-k2-thinking ~1582  
  - anthropic-claude-opus-4.5 ~1575  
  - qwen-qwen3-max ~1559  
  - anthropic-claude-sonnet-4.5 ~1530  
  - openai-gpt-5-mini ~1523  
  - x-ai-grok-4.1-fast:free ~1395  
  - google-gemini-3-pro-preview ~1380  
  - deepseek-deepseek-v3.2-exp ~1304
- Dimension snapshots: safety strong across the top cluster (≈8.6–9.1). Factuality is the weakest axis for deepseek (≈7.06) and gemini (≈7.18); others sit ~7.6–7.9.

## Interpretation
- Clear tiering: GPT-5.1 leads; Kimi K2 and Claude Opus form the chasing pack; Qwen Max and Claude Sonnet cluster in the upper-mid; Gem3 Pro Preview and Grok trail; DeepSeek V3.2 lags most.
- Consistency: Uniform game counts make comparisons fair; safety scores show little spread, so ranking is driven more by persuasiveness/reasoning/clarity.

## Follow-up Analyses Worth Running
- Pairwise head-to-head matrix to expose specific matchup weaknesses.
- Topic/category splits (policy vs. ethics vs. tech) to see specialization.
- Side bias check: per-model pro vs. con win rates after balancing.
- Judge effects: score inflation/deflation and disagreement rates per judge.
- Variance: per-model score standard deviation to spot volatility.
- Style trade-offs: correlation of persuasiveness vs. factuality across debates.

## Note on tooling
- Updated `debatebench/storage.py` to use `model_dump_json`, fixing Pydantic v2 incompatibility in `rate`/`write_ratings`.

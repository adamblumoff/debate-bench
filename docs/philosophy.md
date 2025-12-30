# Evaluation Philosophy

DebateBench treats evaluation as a preference-based, judge-driven environment rather than a ground-truth accuracy test. “Judge vibes” are intentionally part of the measurement: persuasion, reasoning quality, perceived groundedness, clarity, and safety posture are all assessed through the lens of a panel of LLM judges. In this framing, judges are not neutral instruments; they are part of the evaluation context, and their behavior is itself a variable that can be analyzed and stress-tested.

## Why include judge subjectivity?
- Debate is inherently subjective: the task is to convince a reasonable judge, not to recover a single objective label.
- Subjective scoring exposes trade-offs (e.g., clarity vs. aggressiveness, safety vs. rhetoric) that accuracy benchmarks often miss.
- Judges let you probe how different audiences respond to the same arguments, which is often the real-world question for debate systems.

## Treat judges as part of the environment
- Judge prompts and model choices shape outcomes; document them alongside results.
- Judge agreement and side preference metrics help identify instability or bias.
- Robustness checks (e.g., judge diversity, role swaps) are often more informative than a single headline score.

## For a skeptical reader: what would make this meaningful?
- **Judge diversity:** use multiple judge models and report agreement rates.
- **Robustness checks:** repeat runs with different judge panels and side assignments.
- **Uncertainty reporting:** include confidence bands or variance across judges/topics.
- **Transparency:** publish prompts, configs, and code versions with every run.
- **Comparative claims only:** focus on relative differences under the same protocol, not absolute “intelligence” or truth claims.

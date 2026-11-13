# HackHunt Crew benchmark results

Sequential passes over illustrative fixtures, not independent trials.
Tokens cover successful completed client LLM calls only, excluding Meko backend inference, retries and interrupted attempts.

| Mode | Run | LLM calls | Prompt tokens | Completion tokens | Total tokens |
|---|---|---|---|---|---|
| baseline | 1 | 86 | 247889 | 13773 | 261662 |
| baseline | 2 | 86 | 640012 | 13154 | 653166 |
| baseline | 3 | 86 | 1036152 | 13355 | 1049507 |
| meko | 1 | 86 | 66767 | 14723 | 81490 |
| meko | 2 | 85 | 81370 | 14371 | 95741 |
| meko | 3 | 86 | 79399 | 14868 | 94267 |

| Mode | Mean tokens/run | Spread (max-min) | Mean LLM calls/run |
|---|---|---|---|
| baseline | 654778.3 | 787845 | 86.0 |
| meko | 90499.3 | 14251 | 85.67 |

- Token reduction with Meko (mean over runs): **86.2%**
- LLM call reduction with Meko (mean over runs): **0.4%**
- Output quality equal or better with Meko: **False**
- baseline verdict accuracy vs ground truth: 69/72 (0.9583)
- meko verdict accuracy vs ground truth: 65/72 (0.9028)

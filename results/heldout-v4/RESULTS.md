# HackHunt Crew benchmark results

Sequential passes over illustrative fixtures, not independent trials.
Tokens cover successful completed client LLM calls only, excluding Meko backend inference, retries and interrupted attempts.

| Mode | Run | LLM calls | Prompt tokens | Completion tokens | Total tokens |
|---|---|---|---|---|---|
| baseline | 1 | 40 | 56302 | 5181 | 61483 |
| baseline | 2 | 40 | 132013 | 4877 | 136890 |
| baseline | 3 | 40 | 207822 | 4863 | 212685 |
| meko | 1 | 40 | 26617 | 5274 | 31891 |
| meko | 2 | 40 | 33023 | 5227 | 38250 |
| meko | 3 | 40 | 31348 | 5275 | 36623 |

| Mode | Mean tokens/run | Spread (max-min) | Mean LLM calls/run |
|---|---|---|---|
| baseline | 137019.3 | 151202 | 40.0 |
| meko | 35588.0 | 6359 | 40.0 |

- Token reduction with Meko (mean over runs): **74.0%**
- LLM call reduction with Meko (mean over runs): **0.0%**
- Output quality equal or better with Meko: **True**
- baseline verdict accuracy vs ground truth: 35/36 (0.9722)
- meko verdict accuracy vs ground truth: 36/36 (1.0)

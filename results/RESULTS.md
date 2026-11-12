# HackHunt Crew benchmark results

| Mode | Run | LLM calls | Prompt tokens | Completion tokens | Total tokens |
|---|---|---|---|---|---|
| baseline | 1 | 28 | 26318 | 5720 | 32038 |
| baseline | 2 | 30 | 36190 | 6507 | 42697 |
| meko | 1 | 28 | 26485 | 5887 | 32372 |
| meko | 2 | 27 | 26518 | 5563 | 32081 |

- Token reduction with Meko: **13.8%**
- LLM call reduction with Meko: **5.2%**
- Output quality equal across modes: **False**
- baseline verdict accuracy vs ground truth: 14/16 (0.875)
- meko verdict accuracy vs ground truth: 13/16 (0.8125)

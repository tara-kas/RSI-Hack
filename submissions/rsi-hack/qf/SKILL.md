---
name: qf-conventions
description: Numerical conventions that silently turn a correct method into a wrong number in quantitative-finance tasks graded by exact numeric tests.
---

# Quant task conventions

Work the task exactly as you otherwise would. The notes below are only about conventions
that silently change a number; they are not a method, a checklist, or a substitute for
solving the problem.

**Where the instruction states a convention, it overrides anything here.**

- **`ddof`** — `numpy.std` defaults to 0 and `pandas.std` defaults to 1. The difference
  exceeds any grading tolerance.
- **Percent vs fraction** — `0.05` and `5.0` are a factor of 100 apart. Match the magnitude
  of any example value in the instruction. The same applies to basis points.
- **Annualising** — geometric `(1+r).prod()**(periods/n)-1` and arithmetic `mean*periods`
  give different answers. Volatility scales by `sqrt(periods)` while returns scale by
  `periods`.
- **Rounding** — round once, at write time, to the stated precision, never intermediates.
- **Sorting** — integer identifiers cast to strings sort lexicographically, so `"10"` comes
  before `"9"`. Sort on the native type and cast only when writing.
- **Output files** — use the exact paths, filenames, keys and column names the instruction
  gives, in the order it gives them. `numpy` floats need `float()` before JSON, and `NaN`
  is not valid JSON.

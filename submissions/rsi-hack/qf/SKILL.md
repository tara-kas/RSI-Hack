---
name: qf-conventions
description: Conventions that silently produce wrong numbers in quantitative-finance tasks graded by exact numeric tests.
---

# Quant task conventions

Solve the task your own way. These are only the details that silently turn a correct method
into a wrong number.

**Where the instruction and standard practice differ, follow the instruction.**

- **Output contract** — the exact path and filename the instruction gives, exact JSON keys,
  exact CSV columns in the stated order, `index=False` unless an index is asked for. Write
  every file the instruction names. Cast `numpy` floats with `float()` for JSON; `NaN` is
  not valid JSON.
- **`ddof`** — `numpy.std` uses 0, `pandas.std` uses 1, and they differ by more than any
  tolerance. Use what the instruction states.
- **Annualising** — geometric `(1+r).prod()**(periods/n)-1` and arithmetic `mean*periods`
  differ materially. Volatility scales by `sqrt(periods)`, returns by `periods`.
- **Units** — percent vs fraction, bps vs decimal. Match the magnitude of any example value.
- **Rounding** — round once at write time, never intermediates.
- **Sorting** — integer ids cast to strings sort as `"10" < "9"`; sort on the native type and
  cast at write time. Use the stated tie-break.
- **Missing data** — drop or fill explicitly, and note that doing it before or after a
  groupby changes the answer. Where a count of missing values is asked for, count before
  cleaning.
- **Seeds** — use the stated seed.

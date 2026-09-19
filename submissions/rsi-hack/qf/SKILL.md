---
name: qf-conventions
description: Conventions and output-contract details that silently produce wrong numbers in quantitative-finance tasks graded by exact numeric tests.
---

# Quant task conventions

Your output files are checked by exact numeric tests, and every assertion must pass. Solve
the task your own way. These are only the details that silently produce a wrong-but-plausible
number.

**Where the instruction and standard practice differ, follow the instruction.** Each item
below names a choice the instruction usually settles — find its answer there rather than
assuming a default.

- **Write every output file the instruction names.** Some tasks want more than one, and a
  few want several. List them before you start and treat that list as the definition of
  done: grading is all-or-nothing, so one missing file fails the task whatever the other
  numbers are.
- **Output contract** — exact path and filename (usually `/app/output/`), exact JSON keys,
  exact CSV columns in the stated order, `index=False` unless an index is wanted. Cast
  `numpy` floats with `float()` for JSON; `NaN` is not valid JSON.
- **Rounding** — round once, at write time, to the stated precision. Rounding intermediates
  produces a near-miss that passes most assertions and fails a few.
- **Seeds and determinism** — use the stated seed. Never depend on `set`/`dict` order.
  Re-running your script must reproduce the same numbers.
- **Percent vs fraction** — `0.05` and `5.0` are a factor of 100 apart to the grader. Match
  the magnitude of any example value. Same for bps vs decimal.
- **Annualising** — geometric `(1+r).prod()**(periods/n)-1` and arithmetic `mean*periods`
  differ materially. Volatility scales by `sqrt(periods)`, returns by `periods`. Use the
  stated periods-per-year.
- **Linking across periods** — log returns sum, simple returns compound, and multi-period
  attribution has several standard linking methods that disagree. Use what is specified.
- **Sorting** — sort explicitly before writing. Integer ids cast to strings sort as
  `"10" < "9"`; sort on the native type and cast at write time. Use the stated tie-break.
- **Missing data** — decide drop vs fill explicitly; doing it before or after a groupby
  changes the answer. Some tasks ask you to report the count, so count before cleaning.
- **`ddof`** — `numpy.std` uses 0, `pandas.std` uses 1, and they differ by more than any
  tolerance.

Sharpe should equal annualised return over annualised volatility, and weights should sum to
the stated exposure. If they do not, something upstream is wrong.

No network and no `pip install`. `numpy`, `pandas`, `scipy`, `statsmodels`, `sklearn` are
available. Never read `/tests/` or `/solution/`.

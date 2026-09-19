---
name: qf-conventions
description: Conventions and output-contract details that silently produce wrong numbers in quantitative-finance tasks graded by exact numeric tests.
---

# Quant task conventions

Your output files are checked by exact numeric tests. Solve the task your own way; these
are only the details that silently produce a wrong-but-plausible number.

**Where the instruction and standard practice differ, follow the instruction.**

- **Output contract** — exact path and filename (usually under `/app/output/`), exact JSON
  keys, exact CSV columns in the stated order, `index=False` unless an index is asked for.
  Some tasks want a second file as well. Cast `numpy` floats with `float()` before writing
  JSON; `NaN` is not valid JSON.
- **`ddof`** — `numpy.std` uses 0, `pandas.std` uses 1. Use what the instruction states.
- **Annualising** — geometric `(1+r).prod()**(periods/n)-1` and arithmetic `mean*periods`
  differ materially. Volatility scales by `sqrt(periods)`, returns by `periods`.
- **Costs** — if a transaction cost is given, confirm it actually reduced your returns.
  Omitting it changes the return level while leaving volatility almost unchanged.
- **Units** — percent vs fraction, bps vs decimal. Match any example value's magnitude.
- **Ties and sorting** — use the stated tie-break. Integer ids cast to strings sort as
  `"10" < "9"`; sort on the native type and cast at write time.
- **Missing data** — decide drop vs fill explicitly; doing it before or after a groupby
  changes the answer. Some tasks ask you to report the count, so count before cleaning.
- **Seeds** — use the stated seed.
- **Latent-state models** — HMM states, clusters and mixture components come out in an
  arbitrary order, so fitted "state 0" is not necessarily the task's first label. Map each
  fitted state to the label the instruction defines; where it gives no rule, pick an
  observable property, apply it consistently and say which you used. Get this wrong and the
  labels and their probabilities invert while every performance metric still looks correct.
- **Endpoints** — check whether a window, date range or lookback includes both ends. Counts
  that come out one short or one long are a common silent failure.
- **Linking across periods** — compounding `(1+r).prod()-1` and summing give different
  answers for simple returns (log returns sum, simple returns compound). Multi-period
  attribution has several standard linking methods that disagree. Use what the instruction
  specifies. Never round intermediates: rounding early produces a near-miss that passes most
  assertions and fails a few.

Before you finish, confirm **every** output file the instruction names actually exists — a
missing file fails the whole task however good the numbers are. Sharpe should equal annualised
return over annualised volatility, and weights should sum to the stated exposure; if they do
not, something upstream is wrong.

No network and no `pip install`. `numpy`, `pandas`, `scipy`, `statsmodels`, `sklearn` are
available. Never read `/tests/` or `/solution/`.

Optional: `python3 /harbor/skills/stbench-skill/scripts/check_output.py <file> --keys a,b`
reports an output file's columns, dtypes and NaNs.

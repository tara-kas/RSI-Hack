# Convention checklist and ambiguity defaults

Consult this when the instruction is silent on a convention, or when a computed number
looks plausible but you want a second opinion before committing. When the instruction
*does* state a convention, it always wins over anything here.

## Dispersion and risk

| quantity | trap | default when unstated |
|---|---|---|
| standard deviation | `numpy.std` is `ddof=0`, `pandas.std` is `ddof=1` | `ddof=1` for sample statistics |
| covariance matrix | same `ddof` split; `numpy.cov` is `ddof=1` | `ddof=1`, and keep it consistent with the volatility |
| correlation | Pearson vs Spearman; rank ties | Pearson, `method="average"` ties for Spearman |
| downside deviation | threshold is 0 or the mean or the risk-free rate | 0, and say so |
| VaR / CVaR | sign convention: positive loss or negative return; inclusive vs exclusive quantile | report positive loss, state the quantile method |
| drawdown | on cumulative simple returns vs log; peak inclusive | compounded simple returns, peak inclusive |

## Returns and time

| quantity | trap | default when unstated |
|---|---|---|
| returns | simple `p1/p0 - 1` vs log `ln(p1/p0)` | simple, unless the task sums returns across time |
| annualising volatility | `sigma * sqrt(periods)` | 252 daily, 52 weekly, 12 monthly, 4 quarterly |
| annualising return | geometric `(1+r)^n - 1` vs arithmetic `r * n` | geometric |
| Sharpe | whether the risk-free rate is subtracted, and at which frequency | subtract at the native frequency, then annualise |
| first observation | a diff or pct_change leaves a leading NaN | drop it, do not fill with 0 |
| resampling | label and closed edges (`label="right"`, `closed="right"`) | right-labelled, right-closed for returns |

## Cross-sectional work

- **Ranking**: `pandas.rank` defaults to `method="average"`. `"first"`, `"dense"` and
  `"min"` all give different bucket memberships. State which you used.
- **Quantile bucketing**: `qcut` drops duplicate edges only with `duplicates="drop"`, which
  silently changes the number of buckets. Check the realised bucket count.
- **Neutralisation**: demean cross-sectionally *within each date*, not pooled across dates.
- **Winsorising**: per date or pooled changes the result materially. Per date is the more
  common convention in factor work.
- **Weights**: confirm whether they must sum to 1, to 0 (long-short), or to the gross
  exposure. Check the realised sum before writing.

## Fixed income and derivatives

- **Day count**: ACT/360, ACT/365, 30/360 are all in use and differ by whole basis points.
- **Compounding**: continuous vs annual vs semi-annual discounting.
- **Bootstrapping**: interpolation on zero rates vs on discount factors gives different
  curves between nodes.
- **Option pricing**: confirm whether the rate is continuously compounded, whether dividends
  are a yield or discrete, and whether volatility is annualised.
- **Greeks by finite difference**: the bump size and whether it is central or one-sided
  materially changes the answer; use central differences unless told otherwise.

## Output formatting

- **Percent vs fraction** is the single most common unit error. If the instruction shows an
  example value, match its magnitude.
- **Rounding** happens once, at write time, to the stated number of decimals. Never round
  intermediate values.
- **CSV index**: `to_csv(path, index=False)` unless an index column is explicitly required.
- **Float repr**: let pandas write full precision; do not pre-format to strings unless the
  contract asks for strings.
- **JSON**: plain Python floats. `numpy.float64` is not JSON-serialisable — cast with
  `float()`. `NaN` and `Infinity` are not valid JSON even though Python will emit them.
- **Column order** in a CSV is part of the schema whenever the instruction lists the
  columns in order.

## Resolving a genuine ambiguity

1. Re-read the instruction for an example value or a worked micro-example; match it.
2. Check whether one reading makes a stated constraint (a sum, a count, a range) come out
   exactly right. That is usually the intended reading.
3. Compute both readings on a small slice and see which produces the rounder, more
   "designed-looking" number at the stated precision.
4. Pick one, implement it consistently everywhere, and state the assumption in your summary.

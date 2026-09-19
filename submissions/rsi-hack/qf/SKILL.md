---
name: qf-contract-first
description: Procedure for quantitative-finance sandbox tasks that write result files to disk. Extract the output contract before coding, follow the specified formula literally rather than a reasonable equivalent, and mechanically validate every output file before declaring the task done.
---

# Quant sandbox tasks: contract first, arithmetic second

Your output is graded by a hidden pytest suite that reads the files you write. It is
**all-or-nothing**: every assertion must pass or the task scores zero. Numeric checks are
tight — typically `atol=1e-6`, sometimes `1e-10` or `1e-12`.

Two consequences decide most tasks:

1. A result that is financially sensible but computed with a *different-but-reasonable*
   convention scores **zero**, exactly like writing nothing. There is no partial credit
   for good judgement.
2. A correct number in the wrong file, under the wrong key, or with the wrong column name
   also scores **zero**.

So the goal is not "produce a good analysis". It is **"reproduce the specified computation
exactly, in the specified file, with the specified schema"**. Spend your effort
accordingly: most failures are contract and convention failures, not modelling failures.

## Step 1 — Extract the contract before writing any code

Read the instruction twice. Write `/app/contract.md` recording, **verbatim from the
instruction**:

- Every output file: exact absolute path and exact filename. Default is `/app/output/`.
- For each JSON file: every required key, its nesting, and its value type.
- For each CSV file: every column, **in the stated order**, plus dtype, index-or-no-index,
  and row ordering / sort keys.
- Every number: rounding, decimal places, units (percent vs fraction, bps vs decimal,
  annualised vs periodic).
- Every explicit constraint. The instructions state these as "must", "must not", "exactly",
  "use only". Copy each one as a separate line.

Then re-read the instruction once more and add anything you missed. This file is your
acceptance test; you will check the finished output against it in Step 5.

If the instruction and standard financial practice disagree, **follow the instruction**.
The grader encodes the instruction, not the literature.

## Step 2 — Inventory the inputs before computing

Load each input and print: shape, column names, dtypes, per-column null counts, min/max of
numeric columns, duplicate-key count, and date range. Look before you model.

Roughly nine of ten tasks in this family hinge on missing or dirty data. Decide explicitly —
and record in `/app/contract.md` — whether to drop, forward-fill or impute, and *at which
step*, because dropping before versus after a groupby changes the answer. If the
instruction states the policy, follow it exactly. If it is silent, prefer the option that
keeps the panel rectangular and note the assumption in your final summary.

## Step 3 — Follow the specified formula literally

These are the conventions that silently produce a wrong number at `atol=1e-6`. When the
instruction names one, obey it; when it is silent, state your choice in the summary.

- **`ddof`** — sample (`ddof=1`) vs population (`ddof=0`) standard deviation. `numpy.std`
  defaults to `0`, `pandas.Series.std` defaults to `1`. They disagree, and the difference
  is far larger than the tolerance.
- **Annualisation** — the stated factor (252, 12, 4, 365) and whether volatility scales by
  `sqrt(n)` while returns scale by `n`.
- **Return type** — simple vs log returns; whether returns are already in the input.
- **Rolling windows** — `min_periods`, whether the window is inclusive of the current
  observation, and whether the first rows are NaN or dropped.
- **Ties** — ranking, sorting and quantile bucketing need a stated tie-break. Ties are
  where two correct implementations diverge.
- **Sort key types** — sorting integer ids cast to strings gives lexicographic order
  (`"10" < "9"`), not numeric. Sort on the native type; cast to string only at write time.
- **Winsorising / clipping** — the exact percentile, and whether it is applied per period
  or pooled.
- **Percent vs fraction** — `0.05` and `5.0` are both "five percent" to a human and a
  factor of 100 apart to the grader.

## Step 4 — Make it deterministic

The grader reruns nothing, but non-determinism means the number you verified is not the
number you wrote.

- Seed every stochastic component with the seed the instruction gives. If it gives none,
  set one explicitly and record it.
- Never let results depend on `set` or `dict` iteration order, or on unstable sorts. Sort
  explicitly by a unique key before writing.
- Prefer `sort_values(..., kind="mergesort")` when ties must retain input order.
- Do not parallelise floating-point reductions; summation order changes the last bits.

## Step 5 — Validate the output mechanically, then re-read the contract

Create the output directory first (`mkdir -p /app/output`) — a missing directory is a
silent write failure in some libraries and a crash in others.

Then run the bundled checker on **every** file you produced:

```bash
python3 /harbor/skills/stbench-skill/scripts/check_output.py /app/output/results.json --keys sharpe,max_drawdown,turnover
python3 /harbor/skills/stbench-skill/scripts/check_output.py /app/output/weights.csv --columns identifier,date,weight --no-nan
```

It reports shape, exact column order, dtypes, NaN/Inf counts, constant and all-zero
columns, and duplicate rows, and exits non-zero when a required key or column is missing.
NaN or Inf in a numeric output almost always means a failed join or a divide-by-zero
upstream — fix the cause, do not fill the symptom.

Finally, open `/app/contract.md` next to your actual output and check every line. Confirm
the path, the filename, the key spelling, the column order, the units and the rounding.
Only then report the task complete.

## Environment

- **There is no network.** Do not fetch data, and do not `pip install` — the task image
  already pins what it needs. `numpy`, `pandas`, `scipy`, `statsmodels`, `scikit-learn`,
  `pyarrow`, `matplotlib` and `ta-lib` are available.
- Write only under `/app/output/` unless told otherwise. Scratch work can live in `/app/`.
- You have ample turns. Use them to inspect intermediate values rather than to retry a
  whole script; print and check after each stage.

## Do not

- **Never read, open, or reference anything under `/tests/`, `/solution/`, or any file
  containing the benchmark canary string.** Submissions are screened for it and a flagged
  run scores zero. Solve from the instruction and the input data only.
- Never hardcode an expected output value to satisfy a check.
- Never substitute a simpler model for the specified one "because the result is close".
  At `atol=1e-6`, close is wrong.

## When stuck

Consult `/harbor/skills/stbench-skill/reference/conventions.md` for the fuller convention
checklist and the ambiguity defaults. Re-derive the disputed quantity two independent ways
on a small slice and compare before committing to a full run.

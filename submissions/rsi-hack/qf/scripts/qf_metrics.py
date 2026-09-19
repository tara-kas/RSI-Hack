#!/usr/bin/env python3
"""Reference performance metrics for a return series, under BOTH competing conventions.

Most wrong answers in these tasks are not modelling errors — they are convention errors that
still produce a plausible number: arithmetic instead of geometric annualisation, ddof=0
instead of ddof=1, costs never charged. This prints the metric under each convention side by
side so you can pick the one the instruction specifies instead of guessing, and see how far
apart they are.

It computes nothing task-specific and knows no answers. Feed it the strategy return series
you produced.

    python3 qf_metrics.py returns.csv --col strategy_return --periods 252
    python3 qf_metrics.py returns.csv --col ret --periods 12 --rf 0.02

Compare every headline number you are about to write against the matching line here. If your
value appears under neither convention, your return series itself is wrong — fix that before
touching the metric.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def load_series(path: Path, col: str | None):
    import pandas as pd

    frame = pd.read_parquet(path) if path.suffix.lower() in {".pqt", ".parquet"} \
        else pd.read_csv(path)
    if col:
        if col not in frame.columns:
            raise SystemExit(f"column {col!r} not in {list(frame.columns)}")
        series = frame[col]
    else:
        numeric = frame.select_dtypes("number")
        if numeric.shape[1] != 1:
            raise SystemExit(f"pass --col: {path.name} has numeric columns "
                             f"{list(numeric.columns)}")
        series = numeric.iloc[:, 0]
    return series.dropna().astype(float)


def report(series, periods: int, rf: float) -> int:
    import numpy as np

    n = len(series)
    if n < 2:
        raise SystemExit("need at least 2 observations")
    values = series.to_numpy()
    print(f"observations: {n}   periods/year: {periods}   risk-free: {rf}")
    if abs(values).max() > 1.0:
        print("WARNING: |max| > 1 — these look like PERCENT, not fractions. "
              "Most contracts want fractions; check the units before using anything below.")
    print()

    total_growth = float(np.prod(1.0 + values))
    years = n / periods
    geometric = total_growth ** (1.0 / years) - 1.0
    arithmetic = float(values.mean()) * periods
    print("annualised return")
    print(f"  geometric   (1+r).prod()**(periods/n)-1 : {geometric:.8f}")
    print(f"  arithmetic  mean*periods                : {arithmetic:.8f}")

    vol_sample = float(values.std(ddof=1)) * periods ** 0.5
    vol_pop = float(values.std(ddof=0)) * periods ** 0.5
    print("\nannualised volatility")
    print(f"  ddof=1 (pandas default)                 : {vol_sample:.8f}")
    print(f"  ddof=0 (numpy default)                  : {vol_pop:.8f}")

    print("\nSharpe = (annualised return - rf) / annualised volatility")
    for r_label, r_value in (("geometric", geometric), ("arithmetic", arithmetic)):
        for v_label, v_value in (("ddof=1", vol_sample), ("ddof=0", vol_pop)):
            sharpe = (r_value - rf) / v_value if v_value else float("nan")
            print(f"  {r_label:<10} / {v_label:<7}                 : {sharpe:.8f}")

    equity = np.cumprod(1.0 + values)
    drawdown = float((1.0 - equity / np.maximum.accumulate(equity)).max())
    print(f"\nmax drawdown (positive magnitude)         : {drawdown:.8f}")
    print(f"hit rate (fraction of positive periods)   : {float((values > 0).mean()):.8f}")
    print(f"total return over the sample              : {total_growth - 1.0:.8f}")

    print("\nSanity: a long-short equity strategy after costs rarely exceeds Sharpe ~1.5. "
          "If every Sharpe above looks too good, costs are probably not being charged.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="CSV/parquet holding the return series")
    ap.add_argument("--col", default=None, help="column name (default: the only numeric one)")
    ap.add_argument("--periods", type=int, default=252,
                    help="periods per year: 252 daily, 52 weekly, 12 monthly, 4 quarterly")
    ap.add_argument("--rf", type=float, default=0.0, help="annual risk-free rate")
    a = ap.parse_args()
    path = Path(a.path)
    if not path.is_file():
        raise SystemExit(f"no such file: {path}")
    return report(load_series(path, a.col), a.periods, a.rf)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Structural validator for quant-task output files. Offline, no network, no installs.

Reports what a grader would see: exact column order, dtypes, NaN/Inf, degenerate columns,
duplicate rows, and — for JSON — the full key paths. Exits non-zero when a required key or
column is missing, so it can gate a workflow.

    python3 check_output.py /app/output/results.json --keys sharpe,max_drawdown
    python3 check_output.py /app/output/weights.csv --columns identifier,date,weight --no-nan
    python3 check_output.py /app/output/weights.csv --columns identifier,date,weight --ordered

This checks STRUCTURE, never correctness: it cannot know the expected values. A clean
report means the file is well-formed and matches the schema you gave it, not that the
numbers are right.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

problems: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    problems.append(msg)


def note(msg: str) -> None:
    notes.append(msg)


def _reject_nonfinite(value: str):
    raise ValueError(f"invalid JSON constant {value!r} (NaN/Infinity are not valid JSON)")


def _walk(obj, prefix: str = ""):
    """Yield (dotted_path, value) for every leaf in a nested JSON structure."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        if obj and all(not isinstance(x, (dict, list)) for x in obj):
            yield (prefix, obj)
        else:
            for i, v in enumerate(obj):
                yield from _walk(v, f"{prefix}[{i}]")
    else:
        yield (prefix, obj)


# Ranges a practitioner would not believe. Deliberately wide: these catch order-of-magnitude
# and sign errors (costs never charged, returns double-counted, percent/fraction mixups),
# not borderline-unusual results. Matched on substrings of the field name.
_PLAUSIBLE = {
    "sharpe": (-3.0, 3.0),
    "information_ratio": (-3.0, 3.0),
    "hit_rate": (0.0, 1.0),
    "win_rate": (0.0, 1.0),
    "max_drawdown": (0.0, 1.0),
    "volatility": (0.0, 2.0),
    "tracking_error": (0.0, 2.0),
    "beta": (-3.0, 3.0),
    "correlation": (-1.0, 1.0),
    "probability": (0.0, 1.0),
    "annualized_return": (-2.0, 2.0),
    "annualized_alpha": (-2.0, 2.0),
    "turnover": (0.0, 50.0),
}


def check_plausible(flat: dict[str, float]) -> None:
    """Flag values outside ranges a practitioner would believe."""
    for key, value in flat.items():
        low_key = key.lower()
        for pattern, (lo, hi) in _PLAUSIBLE.items():
            if pattern in low_key and not (lo <= value <= hi):
                fail(f"implausible {key}={value!r}: expected roughly [{lo}, {hi}]. "
                     "Check for skipped costs, double-counted returns, a sign error, "
                     "or percent-vs-fraction confusion")
                break


def check_identity(flat: dict[str, float], expr: str) -> None:
    """Check `target=<arithmetic over other fields>`, e.g.
    sharpe_ratio=annualized_return/annualized_volatility."""
    if "=" not in expr:
        raise SystemExit(f"--identity needs the form target=expression, got {expr!r}")
    target, rhs = (part.strip() for part in expr.split("=", 1))
    if target not in flat:
        fail(f"--identity target {target!r} is not a numeric field in this file")
        return
    names = sorted(set(re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", rhs)), key=len, reverse=True)
    missing = [n for n in names if n not in flat]
    if missing:
        fail(f"--identity refers to fields not in this file: {missing}")
        return
    substituted = rhs
    for name in names:
        substituted = substituted.replace(name, repr(flat[name]))
    if not re.fullmatch(r"[0-9eE_.+\-*/() ]+", substituted):
        raise SystemExit("--identity supports only + - * / ( ) over field names and numbers")
    try:
        expected = eval(substituted, {"__builtins__": {}}, {})  # noqa: S307 - literals only
    except ZeroDivisionError:
        fail(f"--identity {expr}: division by zero — a denominator field is 0")
        return
    actual = flat[target]
    if expected == 0:
        ok = abs(actual) <= 1e-9
    else:
        ok = abs(actual - expected) <= max(1e-6, abs(expected) * 0.01)
    if ok:
        note(f"identity holds: {target}={actual:.6g} matches {rhs} = {expected:.6g}")
    else:
        fail(f"identity VIOLATED: {target}={actual:.6g} but {rhs} = {expected:.6g}. "
             "At least one of these fields is computed wrong")


def check_json(path: Path, required_keys: list[str], allow_nan: bool,
               identity: str = "", plausible: bool = False) -> None:
    raw = path.read_text()
    try:
        data = json.loads(raw, parse_constant=_reject_nonfinite)
    except ValueError as e:
        fail(f"does not parse as valid JSON: {e}")
        return

    leaves = list(_walk(data))
    top = list(data) if isinstance(data, dict) else f"<{type(data).__name__}>"
    note(f"top-level keys ({len(top) if isinstance(top, list) else '-'}): {top}")
    note(f"leaf values: {len(leaves)}")

    paths = {p for p, _ in leaves}
    top_set = set(data) if isinstance(data, dict) else set()
    for key in required_keys:
        if key not in top_set and key not in paths and not any(p.startswith(key + ".") or p.startswith(key + "[") for p in paths):
            fail(f"required key missing: {key!r}")

    if not allow_nan:
        for p, v in leaves:
            vals = v if isinstance(v, list) else [v]
            for x in vals:
                if isinstance(x, float) and not math.isfinite(x):
                    fail(f"non-finite value at {p!r}: {x!r}")
                    break

    for p, v in leaves:
        if isinstance(v, str):
            try:
                float(v)
            except ValueError:
                continue
            note(f"numeric-looking value stored as a STRING at {p!r}: {v!r} — "
                 "graders usually compare numbers, not strings")

    # Flatten numeric leaves under both their full path and their bare leaf name, so an
    # identity or plausibility rule can name a field without spelling out its nesting
    # (tasks often bury values under e.g. "intermediates.sharpe_ratio.value").
    flat: dict[str, float] = {}
    for p, v in leaves:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        flat[p] = float(v)
        leaf = p.split(".")[-1]
        if leaf == "value" and "." in p:
            leaf = p.split(".")[-2]
        flat.setdefault(leaf, float(v))

    if plausible:
        check_plausible(flat)
    if identity:
        check_identity(flat, identity)


def check_table(path: Path, required_cols: list[str], ordered: bool,
                allow_nan: bool, expect_rows: int | None) -> None:
    try:
        import pandas as pd
    except ImportError:
        fail("pandas is unavailable, cannot inspect tabular output")
        return

    try:
        if path.suffix.lower() in {".pqt", ".parquet"}:
            df = pd.read_parquet(path)
        else:
            df = pd.read_csv(path)
    except Exception as e:  # noqa: BLE001 - surface any reader failure verbatim
        fail(f"does not parse: {type(e).__name__}: {e}")
        return

    note(f"shape: {df.shape[0]} rows x {df.shape[1]} cols")
    note(f"columns (in file order): {list(df.columns)}")
    note("dtypes: " + ", ".join(f"{c}={t}" for c, t in df.dtypes.astype(str).items()))

    if "Unnamed: 0" in df.columns:
        fail("column 'Unnamed: 0' present — the frame was written with its index; "
             "use to_csv(path, index=False) unless an index column is required")

    if required_cols:
        missing = [c for c in required_cols if c not in df.columns]
        extra = [c for c in df.columns if c not in required_cols]
        if missing:
            fail(f"required columns missing: {missing}")
        if extra:
            note(f"columns present but not in --columns: {extra}")
        if ordered and not missing and list(df.columns) != required_cols:
            fail(f"column ORDER differs from the contract\n"
                 f"    expected: {required_cols}\n"
                 f"    actual:   {list(df.columns)}")

    if expect_rows is not None and len(df) != expect_rows:
        fail(f"row count is {len(df)}, contract says {expect_rows}")

    numeric = df.select_dtypes("number")

    nan_counts = {c: int(n) for c, n in df.isna().sum().items() if n}
    if nan_counts:
        msg = f"NaN present: {nan_counts}"
        fail(msg) if not allow_nan else note(msg)

    if not numeric.empty:
        import numpy as np

        finite = numeric.to_numpy(dtype="float64", na_value=0.0)
        inf_counts = {c: int(n) for c, n in zip(numeric.columns, np.isinf(finite).sum(axis=0)) if n}
        if inf_counts:
            fail(f"infinite values present: {inf_counts} — usually a divide-by-zero upstream")

        for c in numeric.columns:
            col = numeric[c].dropna()
            if col.empty:
                fail(f"column {c!r} is entirely NaN")
            elif col.nunique() == 1:
                note(f"column {c!r} is constant at {col.iloc[0]!r} — verify this is intended")
            elif (col == 0).all():
                fail(f"column {c!r} is all zeros — likely a failed computation")

    dupes = int(df.duplicated().sum())
    if dupes:
        note(f"{dupes} fully duplicated rows — verify the join did not fan out")

    with_pd_option(df)


def with_pd_option(df) -> None:
    import pandas as pd
    with pd.option_context("display.max_columns", 50, "display.width", 200):
        note("first rows:\n" + df.head(3).to_string())
        if len(df) > 3:
            note("last rows:\n" + df.tail(2).to_string())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="output file to inspect (.json, .csv, .pqt, .parquet)")
    ap.add_argument("--keys", default="", help="comma-separated keys the JSON must contain")
    ap.add_argument("--columns", default="", help="comma-separated columns the table must contain")
    ap.add_argument("--ordered", action="store_true",
                    help="also require --columns to match the file's column order exactly")
    ap.add_argument("--rows", type=int, default=None, help="expected row count")
    ap.add_argument("--identity", default="",
                    help="check an arithmetic relation between JSON fields, e.g. "
                         "\"sharpe_ratio=annualized_return/annualized_volatility\"")
    ap.add_argument("--plausible", action="store_true",
                    help="flag financially implausible magnitudes (Sharpe>3, |beta|>3, "
                         "hit rate outside [0,1], ...)")
    ap.add_argument("--no-nan", dest="no_nan", action="store_true",
                    help="treat any NaN in the output as a failure (usually correct)")
    a = ap.parse_args()

    path = Path(a.path)
    print(f"=== {path} ===")
    if not path.exists():
        print(f"FAIL: file does not exist. Did you `mkdir -p {path.parent}` and write to the exact path?")
        return 1
    if path.stat().st_size == 0:
        print("FAIL: file is empty")
        return 1
    print(f"size: {path.stat().st_size} bytes")

    keys = [k.strip() for k in a.keys.split(",") if k.strip()]
    cols = [c.strip() for c in a.columns.split(",") if c.strip()]

    if path.suffix.lower() == ".json":
        check_json(path, keys, allow_nan=not a.no_nan, identity=a.identity,
                   plausible=a.plausible)
    else:
        check_table(path, cols, a.ordered, allow_nan=not a.no_nan, expect_rows=a.rows)

    for n in notes:
        print(f"  {n}")
    if problems:
        print(f"\n{len(problems)} PROBLEM(S):")
        for p in problems:
            print(f"  FAIL: {p}")
        return 1
    print("\nOK: structure matches the schema given. This says nothing about whether the "
          "numbers are correct — check those against the instruction.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

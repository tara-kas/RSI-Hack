#!/usr/bin/env python3
"""Live progress for in-flight (or finished) `stbench eval` runs.

`stbench eval` prints nothing until it finishes, and writes attempts.jsonl and
eval_result.json only at the end. This reads the per-trial artefacts Harbor writes as it
goes, so a long run is observable while it runs — including the token burn against the
domain's eval_budget_tokens, which is what silently kills qf runs (the gateway starts
returning 402 and every remaining attempt becomes a false failure).

    python tools/progress.py                     # every run under runs/
    python tools/progress.py --run runs/qf-ctrl  # just one
    python tools/progress.py --watch 30          # refresh every 30s until all are done

Exit code is 1 if any run has exhausted or nearly exhausted its token budget.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import subprocess
import sys
import time
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WARN_FRACTION = 0.85  # budget burn past this is worth shouting about


def _budgets() -> dict[str, int]:
    cfg = tomllib.loads((REPO_ROOT / "hackathon.toml").read_text())
    return {name: int(t.get("eval_budget_tokens", 0))
            for name, t in cfg.get("domains", {}).items()}


def _seconds(block: dict | None) -> float | None:
    if not block or not block.get("started_at"):
        return None
    start = dt.datetime.fromisoformat(block["started_at"].replace("Z", "+00:00"))
    end_raw = block.get("finished_at")
    end = (dt.datetime.fromisoformat(end_raw.replace("Z", "+00:00")) if end_raw
           else dt.datetime.now(dt.timezone.utc))
    return (end - start).total_seconds()


def _arm(trial_dir: Path) -> str:
    """Which arm a trial is running. Only knowable while the staged skill still exists:
    Harbor stages it to a temp dir that is deleted when the trial ends."""
    try:
        cfg = json.loads((trial_dir / "config.json").read_text())
    except (OSError, json.JSONDecodeError):
        return "?"
    skills = (cfg.get("agent") or {}).get("skills") or []
    if not skills:
        return "baseline"
    skill_md = Path(skills[0]) / "SKILL.md"
    try:
        for line in skill_md.read_text().splitlines()[:5]:
            if line.startswith("name:"):
                return "placebo" if line.split(":", 1)[1].strip() == "placebo" else "skill"
    except OSError:
        return "?"
    return "?"


def _alive(run: Path) -> bool:
    try:
        # `pgrep -a` prints only PIDs on macOS, so read command lines from ps instead.
        out = subprocess.run(["ps", "-eo", "command"], capture_output=True,
                             text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return any(f"--out {run}" in line or f"--out {run.as_posix()}" in line
               for line in out.splitlines() if "stbench eval" in line)


def report(run: Path, budgets: dict[str, int]) -> bool:
    """Print one run's progress. Returns True if its budget is nearly spent."""
    results = sorted(glob.glob(str(run / "harbor-jobs" / "*" / "*" / "result.json")))
    done, running = [], []
    for path in results:
        try:
            data = json.loads(Path(path).read_text())
        except (OSError, json.JSONDecodeError):
            continue
        (done if data.get("finished_at") else running).append((Path(path).parent, data))

    domain = None
    final = run / "eval_result.json"
    if final.is_file():
        domain = json.loads(final.read_text()).get("domain")
    if domain is None:
        for _, data in done + running:
            name = data.get("task_name", "")
            if "healthbench" in name:
                domain = "health"
            elif name.startswith("hle"):
                domain = "hle"
            elif "tau3" in name:
                domain = "tau3"
            else:
                domain = "qf"
            break

    spent = 0
    ledger = run / "learner_ledger.jsonl"
    if ledger.is_file():
        for line in ledger.read_text().splitlines():
            if line.strip():
                try:
                    spent += json.loads(line).get("charged_tokens") or 0
                except json.JSONDecodeError:
                    continue

    budget = budgets.get(domain or "", 0)
    status = "RUNNING" if _alive(run) else ("done" if final.is_file() else "stopped")
    print(f"\n{run.name}  [{status}]  domain={domain or '?'}")
    print(f"  trials: {len(done)} finished, {len(running)} in flight")

    if done:
        times = sorted(s for s in (_seconds(d) for _, d in done) if s)
        if times:
            median = times[len(times) // 2]
            print(f"  median trial: {median / 60:.1f} min")
            if running:
                print(f"  in-flight elapsed: " +
                      ", ".join(f"{(_seconds(d) or 0) / 60:.0f}m" for _, d in running[:6]))

    for trial_dir, data in done:
        reward = (data.get("verifier_result") or {}).get("rewards", {}).get("reward")
        task = data.get("task_name", "?").split("/")[-1]
        print(f"    {task[:44]:<46} {_arm(trial_dir):<9} reward={reward}")

    near_limit = False
    if budget:
        frac = spent / budget
        near_limit = frac >= WARN_FRACTION
        flag = "  <-- BUDGET NEARLY SPENT" if near_limit else ""
        print(f"  tokens: {spent:,} / {budget:,} ({frac:.0%}){flag}")
        if done:
            per = spent / len(done)
            print(f"  ~{per:,.0f} tokens/trial -> about {int(budget // max(per, 1))} "
                  "trials fit in this budget")
    elif spent:
        print(f"  tokens: {spent:,}")
    return near_limit


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default=None, help="a single run directory (default: all)")
    ap.add_argument("--watch", type=int, default=0, metavar="SECONDS",
                    help="refresh until every run is finished")
    a = ap.parse_args()

    budgets = _budgets()
    while True:
        runs = ([Path(a.run)] if a.run
                else sorted(p for p in (REPO_ROOT / "runs").iterdir()
                            if p.is_dir() and (p / "harbor-jobs").is_dir()))
        if not runs:
            raise SystemExit("no runs found under runs/")
        print("=" * 72)
        print(time.strftime("%H:%M:%S"))
        warn = any([report(r, budgets) for r in runs])
        if not a.watch:
            return 1 if warn else 0
        if not any(_alive(r) for r in runs):
            print("\nall runs finished")
            return 1 if warn else 0
        time.sleep(a.watch)


if __name__ == "__main__":
    sys.exit(main())

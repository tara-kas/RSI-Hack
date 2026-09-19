#!/usr/bin/env python3
"""Reuse a measured control arm so later iterations only run the skill arm.

Every `stbench eval` with `--arms placebo,skill` spends half its attempts re-measuring a
control that barely moves. Once a control is measured for a fixed task set, save it here and
run later iterations with `--arms skill` alone, comparing against the stored numbers. That
halves the cost and wall time of every iteration after the first.

The comparison math is not reimplemented: this calls `skilltrainbench.scoring.summarize`,
the same function `stbench eval` uses, so `net_delta` and the bootstrap CI match what the
harness would report.

    # once, from a run that included the control arm
    python tools/control.py save --run runs/qf-v1 --arm placebo

    # thereafter: uv run stbench eval --domain qf --arms skill ... --out runs/qf-v2
    python tools/control.py compare --run runs/qf-v2

    python tools/control.py show --domain qf

A stored control is only valid for the task set it was measured on, and only while the
learner and its limits are unchanged. `compare` refuses to score tasks the control never
covered rather than silently comparing different task sets.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTROL_DIR = REPO_ROOT / "controls"

sys.path.insert(0, str(REPO_ROOT / "src"))


def _scores(run: Path, arm: str) -> dict[str, float]:
    """Per-task scores for one arm. Prefers eval_result.json, falls back to attempts.jsonl
    so an interrupted run is still usable."""
    result = run / "eval_result.json"
    if result.is_file():
        data = json.loads(result.read_text())
        per_task = data.get("summary", {}).get("per_task") or []
        out = {r["task_id"]: r[arm] for r in per_task
               if isinstance(r.get(arm), (int, float))}
        if out:
            return out

    attempts = run / "attempts.jsonl"
    if not attempts.is_file() or not attempts.stat().st_size:
        # Last resort: read Harbor's per-trial results. A run that is killed (or that
        # exhausts its token budget) never writes the summary files, and those trials are
        # still perfectly good measurements — qf costs ~500k tokens each, too expensive to
        # discard over a missing summary. Arm attribution is unavailable here, so this only
        # works for a single-arm run, which is exactly how a control is measured.
        import glob as _glob
        out: dict[str, float] = {}
        for path in _glob.glob(str(run / "harbor-jobs" / "*" / "*" / "result.json")):
            try:
                data = json.loads(Path(path).read_text())
            except (OSError, json.JSONDecodeError):
                continue
            if not data.get("finished_at"):
                continue
            reward = (data.get("verifier_result") or {}).get("rewards", {}).get("reward")
            if isinstance(reward, (int, float)):
                out[str(data.get("task_name", "")).split("/")[-1]] = float(reward)
        if out:
            return out
        raise SystemExit(f"no eval_result.json or attempts.jsonl under {run}")
    out = {}
    for line in attempts.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("arm") == arm and isinstance(row.get("score"), (int, float)):
            out[row.get("task_name") or row.get("task_id")] = float(row["score"])
    return out


def _domain_of(run: Path) -> str:
    result = run / "eval_result.json"
    if result.is_file():
        domain = json.loads(result.read_text()).get("domain")
        if domain:
            return str(domain)
    raise SystemExit(f"cannot tell which domain {run} is — pass --domain explicitly")


def _control_path(domain: str, arm: str) -> Path:
    return CONTROL_DIR / f"{domain}-{arm}.json"


def save(run: Path, arm: str, domain: str | None, force: bool) -> int:
    domain = domain or _domain_of(run)
    scores = _scores(run, arm)
    if not scores:
        raise SystemExit(f"no {arm} scores found in {run} — did that arm actually run?")
    dest = _control_path(domain, arm)
    if dest.exists() and not force:
        raise SystemExit(f"{dest.relative_to(REPO_ROOT)} exists — pass --force to replace it "
                         "(later comparisons would then use different control numbers)")
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({
        "domain": domain,
        "arm": arm,
        "source_run": str(run.relative_to(REPO_ROOT)) if run.is_relative_to(REPO_ROOT) else str(run),
        "n_tasks": len(scores),
        "mean": round(sum(scores.values()) / len(scores), 6),
        "note": ("Valid only for these task names, and only while the learner and its limits "
                 "are unchanged. Re-measure if hackathon.toml changes."),
        "scores": dict(sorted(scores.items())),
    }, indent=2) + "\n")
    print(f"saved {len(scores)} {arm} scores to {dest.relative_to(REPO_ROOT)} "
          f"(mean {sum(scores.values())/len(scores):.4f})")
    return 0


def compare(run: Path, domain: str | None, arm: str, control_path: Path | None,
            fail_if_worse: bool) -> int:
    from skilltrainbench.scoring import Pair, summarize

    domain = domain or _domain_of(run)
    path = control_path or _control_path(domain, arm)
    if not path.is_file():
        raise SystemExit(f"no stored control at {path} — run `save` from a run that included "
                         f"the {arm} arm")
    control = json.loads(path.read_text())
    ctrl_scores = control["scores"]
    skill_scores = _scores(run, "skill")
    if not skill_scores:
        raise SystemExit(f"no skill scores in {run}")

    missing = sorted(set(skill_scores) - set(ctrl_scores))
    paired = sorted(set(skill_scores) & set(ctrl_scores))
    if not paired:
        raise SystemExit("no task overlap between this run and the stored control")

    field = "placebo" if arm == "placebo" else "baseline"
    pairs = [Pair(task_id=t, seed=0, skill=skill_scores[t], **{field: ctrl_scores[t]})
             for t in paired]
    summary = summarize(pairs)

    print(f"control: {path.relative_to(REPO_ROOT)}  ({control['arm']}, {control['n_tasks']} tasks)")
    print(f"run:     {run}")
    print()
    print(f"{'task':<46} {arm:>8} {'skill':>8} {'delta':>8}")
    for t in paired:
        c, s = ctrl_scores[t], skill_scores[t]
        flag = "  <-- flipped" if (c >= 1.0) != (s >= 1.0) else ""
        print(f"{t[:44]:<46} {c:>8.3f} {s:>8.3f} {s - c:>+8.3f}{flag}")
    print()
    net = summary.get("net_delta")
    print(f"{'PAIRED (n=' + str(len(paired)) + ')':<46} "
          f"{summary.get(field + '_rate'):>8.3f} {summary.get('skill_rate'):>8.3f} "
          f"{net:>+8.3f}")
    if summary.get("ci95"):
        lo, hi = summary["ci95"]
        print(f"{'95% CI on net_delta':<46} [{lo:+.3f}, {hi:+.3f}]")
    else:
        print(f"no CI: needs >= 12 paired tasks (have {len(paired)})")
    if summary.get("note"):
        print(f"note: {summary['note']}")
    if missing:
        print(f"\n{len(missing)} task(s) not in the control, excluded: {missing[:5]}")

    if fail_if_worse and (net is None or net <= 0):
        print("\nskill is not ahead of the control")
        return 1
    return 0


def show(domain: str, arm: str) -> int:
    path = _control_path(domain, arm)
    if not path.is_file():
        raise SystemExit(f"no stored control at {path}")
    d = json.loads(path.read_text())
    print(f"{path.relative_to(REPO_ROOT)}: {d['n_tasks']} tasks, mean {d['mean']}")
    print(f"from {d['source_run']}")
    for t, s in d["scores"].items():
        print(f"  {s:>7.3f}  {t}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sv = sub.add_parser("save", help="store a control arm's per-task scores from a run")
    sv.add_argument("--run", required=True)
    sv.add_argument("--arm", default="placebo", choices=["placebo", "baseline"])
    sv.add_argument("--domain", default=None)
    sv.add_argument("--force", action="store_true")

    cp = sub.add_parser("compare", help="score a skill-only run against the stored control")
    cp.add_argument("--run", required=True)
    cp.add_argument("--arm", default="placebo", choices=["placebo", "baseline"])
    cp.add_argument("--domain", default=None)
    cp.add_argument("--control", default=None, help="explicit control file")
    cp.add_argument("--fail-if-worse", action="store_true",
                    help="exit 1 when net_delta <= 0, for use in a loop")

    sh = sub.add_parser("show", help="print a stored control")
    sh.add_argument("--domain", required=True)
    sh.add_argument("--arm", default="placebo", choices=["placebo", "baseline"])

    a = ap.parse_args()
    if a.cmd == "save":
        return save(Path(a.run), a.arm, a.domain, a.force)
    if a.cmd == "compare":
        return compare(Path(a.run), a.domain, a.arm,
                       Path(a.control) if a.control else None, a.fail_if_worse)
    return show(a.domain, a.arm)


if __name__ == "__main__":
    sys.exit(main())

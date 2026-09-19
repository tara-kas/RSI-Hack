#!/usr/bin/env python3
"""Failure taxonomy for a health eval run: where the rubric points were lost, and why.

For every attempt: score, a 1-2 sentence why-it-failed line, and deterministic structural
flags (no file, no urgent line, question count, medicine without caution). Then totals:
points lost per rubric axis (completeness, context_awareness, accuracy, ...) and flag
counts, so the biggest bucket is a number, not an impression. Free: reads files only.

    uv run python tools/health_report.py runs/health-v3
    uv run python tools/health_report.py runs/health-v3 --arm skill --worst 5

Rubric text is printed for OUR diagnosis only. Never copy it into a skill.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tomllib
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS = REPO_ROOT / "dataset" / "hackathon" / "healthbench" / "tasks"
CHECKER = REPO_ROOT / "submissions" / "my-team" / "health" / "scripts" / "check_reply.py"


def _load_checker():
    # A __pycache__ left in the skill folder would ship with the submission.
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("check_reply", CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _axis(tags: list[str]) -> str:
    return next((t.split(":", 1)[1] for t in tags if t.startswith("axis:")), "other")


def _attempts(run: Path) -> list[dict]:
    path = run / "attempts.jsonl"
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"{path} missing or empty — recover the run from harbor-jobs first")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def report(run: Path, arm: str | None, worst: int) -> int:
    chk = _load_checker()
    lost_by_axis: Counter[str] = Counter()
    flags: Counter[str] = Counter()
    by_cat: dict[str, list[float]] = defaultdict(list)
    rows = []
    for a in sorted(_attempts(run), key=lambda r: (r["task_name"], r["arm"])):
        if arm and a["arm"] != arm:
            continue
        task_dir = a["task_name"].split("/")[-1]
        cat = tomllib.loads((TASKS / task_dir / "task.toml").read_text(encoding="utf-8"))["metadata"]["category"]
        text = a.get("answer") or ""
        verdicts = Path(a["trial_dir"]) / "verifier" / "verdicts.json" if a.get("trial_dir") else None
        rubrics = json.loads(verdicts.read_text(encoding="utf-8"))["rubrics"] if verdicts and verdicts.is_file() else []

        lost: Counter[str] = Counter()
        worst_item = None
        for r in rubrics:
            bad = (r["points"] > 0 and not r["criteria_met"]) or (r["points"] < 0 and r["criteria_met"])
            if bad:
                lost[_axis(r["tags"])] += abs(r["points"])
                if worst_item is None or abs(r["points"]) > abs(worst_item["points"]):
                    worst_item = r
        lost_by_axis.update(lost)

        f: list[str] = []
        qs = chk.questions(text)
        if len(text.strip()) < 20:
            f.append("NO_FILE")
        else:
            if chk.URGENT.search(text[:300]):
                f.append("urgent_first")
            f.append(f"q={len(qs)}")
            if chk.DRUG.search(text) and not chk.CAUTION.search(text):
                f.append("DRUG_NO_CAUTION")
            if chk.META.search(text):
                f.append("META_TALK")
            if len(text) > 6000:
                f.append("LONG")
        flags.update(x for x in f if x.isupper())
        if cat == "emergency_referrals" and "urgent_first" not in f and "NO_FILE" not in f:
            flags["EMERGENCY_CAT_NO_URGENT_FIRST"] += 1

        if "NO_FILE" in f:
            why = "No reply file was written, so everything was graded as missing."
        elif lost:
            top = ", ".join(f"{k} -{v}" for k, v in lost.most_common(2))
            kind = "missed" if worst_item["points"] > 0 else "penalised for"
            why = f"Lost most on {top}. Biggest: {kind} ({worst_item['points']:+d}) {worst_item['criterion'][:110]}"
        else:
            why = "Full marks."
        score = a["score"] if a["score"] is not None else float("nan")
        by_cat[cat].append(score)
        rows.append((score, a["task_name"].split("hard-")[-1][:8], a["arm"], cat, f, why))

    for score, tid, a_arm, cat, f, why in rows:
        print(f"{tid} {a_arm:<8} {cat[:18]:<18} {score:6.3f}  [{' '.join(f)}]\n    {why}")
    print("\n== worst attempts")
    for score, tid, a_arm, _, _, why in sorted(rows)[:worst]:
        print(f"  {score:6.3f} {tid} {a_arm}: {why[:140]}")
    print("\n== mean score by category")
    for cat, v in sorted(by_cat.items()):
        print(f"  {cat:<22} {sum(v) / len(v):.3f}  (n={len(v)})")
    print("\n== rubric points lost by axis (biggest bucket first)")
    for k, v in lost_by_axis.most_common():
        print(f"  {k:<24} {v}")
    print("\n== structural flags")
    for k, v in flags.most_common() or [("none", 0)]:
        print(f"  {k:<32} {v}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", help="run directory, e.g. runs/health-v3")
    ap.add_argument("--arm", default=None, help="only this arm (baseline/placebo/skill)")
    ap.add_argument("--worst", type=int, default=5, help="how many worst attempts to list")
    a = ap.parse_args()
    return report(Path(a.run), a.arm, a.worst)


if __name__ == "__main__":
    sys.exit(main())

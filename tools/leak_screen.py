#!/usr/bin/env python3
"""Flag skill text that overlaps HealthBench rubric criteria or conversation text.

The organisers screen every submission for leaked task content; a flagged skill scores
zero. This compares each line of every text file in a skill folder against all local
health task rubrics and prompts using word n-grams, and prints each line that shares an
n-gram with a task, with the task and the matching source text. A clean result means no
verbatim overlap of that length, not that no idea was taken from a single task.

    uv run python tools/leak_screen.py submissions/my-team/health
    uv run python tools/leak_screen.py submissions/my-team/health --n 5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS = REPO_ROOT / "dataset" / "hackathon" / "healthbench" / "tasks"
# Generic phrases every health text uses; matching them is not a leak.
STOP = {"the", "a", "an", "of", "to", "and", "or", "in", "on", "for", "is", "are", "if", "with",
        "you", "your", "that", "this", "it", "be", "as", "at", "by", "any", "such"}


def ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    grams = set()
    for i in range(len(words) - n + 1):
        g = tuple(words[i:i + n])
        if sum(w not in STOP for w in g) >= n - 1:
            grams.add(g)
    return grams


def screen(skill: Path, n: int) -> int:
    index: dict[tuple[str, ...], tuple[str, str]] = {}
    for tdir in sorted(TASKS.iterdir()):
        ex = tdir / "tests" / "example.json"
        if not ex.is_file():
            continue
        d = json.loads(ex.read_text(encoding="utf-8"))
        sources = [r["criterion"] for r in d["rubrics"]] + [m["content"] for m in d["prompt"]]
        for s in sources:
            for g in ngrams(s, n):
                index.setdefault(g, (tdir.name, s))
    hits = 0
    for f in sorted(p for p in skill.rglob("*") if p.is_file()):
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for g in sorted(ngrams(line, n)):
                if g in index:
                    task, src = index[g]
                    hits += 1
                    print(f"{f.name}:{i}: '{' '.join(g)}'\n    skill: {line.strip()[:120]}\n"
                          f"    task {task[-36:-28]}: {src[:120]}")
                    break
    print(f"\n{hits} line(s) share a {n}-word sequence with local task text.")
    return 1 if hits else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skill", help="skill folder, e.g. submissions/my-team/health")
    ap.add_argument("--n", type=int, default=6, help="n-gram length in words (smaller = stricter)")
    a = ap.parse_args()
    if not Path(a.skill).is_dir():
        raise SystemExit(f"{a.skill} is not a directory")
    return screen(Path(a.skill), a.n)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Local train/test splits over the downloaded training tasks.

The hackathon's real held-out set is private and we never see it. These splits carve
the LOCAL training tasks into a `train` half we iterate against and a `test` half we
deliberately never look at, so that a local improvement has some chance of being a real
improvement rather than memorisation of the tasks we tuned on.

Splits are deterministic (stratified by task difficulty, fixed seed) and written to
splits/<domain>-<train>-<test>-s<seed>.json so a rerun reproduces them exactly.

    python tools/splits.py create --domain qf
    python tools/splits.py show   --domain qf
    python tools/splits.py tasks  --domain qf --split train --limit 6

`tasks` prints a comma-separated list for `stbench eval --tasks`.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPLIT_DIR = REPO_ROOT / "splits"

# task.toml difficulty strings collapse into coarse strata. The QF README notes the
# task.toml tiers disagree with the paper on some tasks, but they are what ships
# locally and they are only used here to keep the split balanced.
_STRATA = {
    "easy": "medium",
    "medium": "medium",
    "medium-hard": "hard",
    "hard": "hard",
    "very_hard": "hard",
}


def _dataset_dir(domain: str) -> Path:
    cfg = tomllib.loads((REPO_ROOT / "hackathon.toml").read_text())
    table = cfg.get("domains", {}).get(domain)
    if table is None:
        raise SystemExit(f"unknown domain {domain!r}; known: {', '.join(cfg.get('domains', {}))}")
    default = REPO_ROOT / "dataset" / "hackathon" / domain / "tasks"
    return REPO_ROOT / table["dataset_dir"] if "dataset_dir" in table else default


def _tasks(domain: str) -> list[tuple[str, str]]:
    """(task_name, stratum) for every downloaded task, sorted by name."""
    root = _dataset_dir(domain)
    if not root.is_dir():
        raise SystemExit(f"no tasks at {root} — run `uv run stbench data pull` first")
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir() and (p / "task.toml").is_file()):
        try:
            meta = tomllib.loads((d / "task.toml").read_text()).get("metadata", {})
        except (OSError, tomllib.TOMLDecodeError):
            meta = {}
        # Stratify on whatever the domain actually labels its tasks with. QF uses
        # difficulty tiers; HealthBench uses behavioural `category`, whose themes have
        # very different baseline scores, so a split that ignores it can hand the
        # holdout an unrepresentative theme mix.
        raw = str(meta.get("difficulty", "") or "").strip().lower()
        if raw:
            out.append((d.name, _STRATA.get(raw, raw)))
            continue
        category = str(meta.get("category", "") or "").strip().lower()
        if not category:
            # HLE keeps its labels in tests/metadata.json rather than task.toml. Stratify on
            # answer_type: exact-match and multiple-choice questions behave very differently,
            # so an unstratified split can hand the holdout the wrong mix.
            try:
                hle = json.loads((d / "tests" / "metadata.json").read_text())
                category = str(hle.get("answer_type", "") or "").strip().lower()
            except (OSError, json.JSONDecodeError):
                category = ""
        out.append((d.name, category or "unknown"))
    return out


def _split_path(domain: str, test_frac: float, seed: int) -> Path:
    train_pct = round((1 - test_frac) * 100)
    return SPLIT_DIR / f"{domain}-{train_pct}-{100 - train_pct}-s{seed}.json"


def _find_split(domain: str) -> Path:
    found = sorted(SPLIT_DIR.glob(f"{domain}-*.json"))
    if not found:
        raise SystemExit(f"no split for {domain!r} — run `python tools/splits.py create --domain {domain}`")
    if len(found) > 1:
        raise SystemExit(f"several splits for {domain!r}: {[p.name for p in found]} — keep one")
    return found[0]


def create(domain: str, test_frac: float, seed: int, force: bool) -> None:
    tasks = _tasks(domain)
    dest = _split_path(domain, test_frac, seed)
    if dest.exists() and not force:
        raise SystemExit(f"{dest.relative_to(REPO_ROOT)} exists — pass --force to overwrite "
                         "(this changes which tasks you have already tuned against)")

    by_stratum: dict[str, list[str]] = {}
    for name, stratum in tasks:
        by_stratum.setdefault(stratum, []).append(name)

    rng = random.Random(seed)
    train: list[str] = []
    test: list[str] = []
    for stratum in sorted(by_stratum):
        names = sorted(by_stratum[stratum])
        rng.shuffle(names)
        n_test = round(len(names) * test_frac)
        # Never let a stratum donate every task to test, and never silently drop a
        # small stratum from test entirely when it has enough tasks to spare one.
        n_test = min(max(n_test, 1 if len(names) >= 3 else 0), len(names) - 1)
        test.extend(names[:n_test])
        train.extend(names[n_test:])

    payload = {
        "domain": domain,
        "seed": seed,
        "test_frac": test_frac,
        "n_train": len(train),
        "n_test": len(test),
        "strata": {s: len(v) for s, v in sorted(by_stratum.items())},
        "note": ("Local split of the PUBLIC training tasks only. `test` is our own holdout: "
                 "never iterate against it. The hackathon's real held-out set is private."),
        "train_task_names": sorted(train),
        "test_task_names": sorted(test),
    }
    SPLIT_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {dest.relative_to(REPO_ROOT)}: {len(train)} train / {len(test)} test")
    for stratum, names in sorted(by_stratum.items()):
        n_t = sum(1 for n in names if n in set(test))
        print(f"  {stratum:<8} {len(names) - n_t:>3} train / {n_t:>2} test")


def show(domain: str) -> None:
    data = json.loads(_find_split(domain).read_text())
    print(f"{_find_split(domain).name}: {data['n_train']} train / {data['n_test']} test  (seed {data['seed']})")
    print("\ntrain:")
    for n in data["train_task_names"]:
        print(f"  {n}")
    print("\ntest (HOLDOUT — do not iterate against these):")
    for n in data["test_task_names"]:
        print(f"  {n}")


def tasks_cmd(domain: str, split: str, limit: int | None, offset: int) -> None:
    data = json.loads(_find_split(domain).read_text())
    names = data[f"{split}_task_names"][offset:]
    if limit:
        names = names[:limit]
    if not names:
        raise SystemExit("no tasks selected")
    print(",".join(names))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create", help="create a deterministic stratified split")
    c.add_argument("--domain", required=True)
    c.add_argument("--test-frac", type=float, default=0.2)
    c.add_argument("--seed", type=int, default=20260919)
    c.add_argument("--force", action="store_true")

    s = sub.add_parser("show", help="print both halves of a split")
    s.add_argument("--domain", required=True)

    t = sub.add_parser("tasks", help="print a comma-separated task list for `stbench eval --tasks`")
    t.add_argument("--domain", required=True)
    t.add_argument("--split", choices=["train", "test"], default="train")
    t.add_argument("--limit", type=int, default=None)
    t.add_argument("--offset", type=int, default=0)

    a = ap.parse_args()
    if a.cmd == "create":
        create(a.domain, a.test_frac, a.seed, a.force)
    elif a.cmd == "show":
        show(a.domain)
    else:
        tasks_cmd(a.domain, a.split, a.limit, a.offset)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Run one eval as several small `stbench eval` calls, so no call drains the learner token pool.

`stbench eval` meters the learner through ONE token pool per invocation (`eval_budget_tokens`
in hackathon.toml, 4M for tau3). A tau3 attempt uses 0.2-0.7M learner tokens, so about six
attempts empty the pool; the gateway then answers 402 and the harness aborts the whole eval,
losing every attempt still in flight. This splits the task list into chunks, runs one
`stbench eval` per chunk into <out>/b01, <out>/b02, ..., and keeps going when a chunk fails.

It also removes two hazards of a long run:
  - the skill folder is snapshotted into <out>/skill first and every chunk evaluates the
    snapshot, so editing SKILL.md mid-run cannot split the attempts across skill versions;
  - this machine's launch fixes are applied: PYTHONUTF8=1, the venv's Scripts dir on PATH
    (so the harness finds harbor.exe), and DOCKER_CONFIG=~/.docker-anon when that folder
    exists and the variable is unset (the credential helper is broken in remote sessions).

It spends credits exactly like `stbench eval`. Chunks run one after another; `--concurrency`
applies inside a chunk. Bare numbers in --tasks are expanded to the domain's task whose name
ends in -<number>. Read the results across all chunks with the report tool:

    python tools/batch_eval.py --domain tau3 --skill submissions/my-team/tau3 \\
        --tasks 001,003,005,017,021 --chunk 5 --concurrency 3 --out runs/tau3-v3
    python tools/tau3_report.py runs/tau3-v3/b* --diff
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def domain_table(domain: str) -> dict:
    cfg = tomllib.loads((REPO_ROOT / "hackathon.toml").read_text(encoding="utf-8"))
    table = cfg.get("domains", {}).get(domain)
    if table is None:
        raise SystemExit(f"unknown domain {domain!r}; known: {', '.join(cfg.get('domains', {}))}")
    return table


def expand_tasks(domain: str, raw: str) -> list[str]:
    """Full task names, in the order given; a bare number matches the task ending in -<number>."""
    root = REPO_ROOT / domain_table(domain).get("dataset_dir", f"dataset/hackathon/{domain}/tasks")
    names = sorted(p.name for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    out: list[str] = []
    for token in (t.strip() for t in raw.split(",")):
        if not token:
            continue
        if token.isdigit():
            hits = [n for n in names if n.endswith(f"-{token}")]
            if len(hits) != 1:
                raise SystemExit(f"task number {token!r} matches {len(hits)} tasks under {root}; "
                                 "pass the full task name instead")
            token = hits[0]
        if token in out:
            raise SystemExit(f"task {token!r} is listed twice")
        out.append(token)
    if not out:
        raise SystemExit("--tasks is empty")
    return out


def launch_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    scripts = str(Path(sys.executable).parent)
    env["PATH"] = scripts + os.pathsep + env.get("PATH", "")
    anon = Path.home() / ".docker-anon"
    if "DOCKER_CONFIG" not in env and anon.is_dir():
        env["DOCKER_CONFIG"] = str(anon)
    return env


def run_batches(domain: str, skill: Path | None, tasks: list[str], arms: str, chunk: int,
                concurrency: int, out: Path) -> int:
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} already holds results; a second run into it would mix two evals "
                         "in one report. Pick a new --out.")
    out.mkdir(parents=True, exist_ok=True)

    skill_arg: list[str] = []
    if skill is not None:
        if not (skill / "SKILL.md").is_file():
            raise SystemExit(f"no SKILL.md in {skill}")
        snapshot = out / "skill"
        shutil.copytree(skill, snapshot, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        skill_arg = ["--skill", str(snapshot)]

    chunks = [tasks[i:i + chunk] for i in range(0, len(tasks), chunk)]
    record = {"domain": domain, "skill": str(skill) if skill else None, "arms": arms,
              "chunk": chunk, "concurrency": concurrency,
              "pool_tokens_per_chunk": domain_table(domain).get("eval_budget_tokens"),
              "started": time.strftime("%Y-%m-%d %H:%M:%S"), "chunks": []}
    manifest = out / "batch.json"
    env = launch_env()
    n_arms = len([a for a in arms.split(",") if a])
    print(f"{len(tasks)} tasks x {n_arms} arm(s) in {len(chunks)} chunk(s) of <= {chunk}; "
          f"learner pool {record['pool_tokens_per_chunk']} tokens per chunk", flush=True)

    failed = 0
    for k, part in enumerate(chunks, 1):
        dest = out / f"b{k:02d}"
        cmd = [sys.executable, "-m", "skilltrainbench.cli", "eval", "--domain", domain,
               *skill_arg, "--arms", arms, "--tasks", ",".join(part),
               "--concurrency", str(concurrency), "--out", str(dest)]
        t0 = time.monotonic()
        with (out / f"b{k:02d}.log").open("w", encoding="utf-8") as log:
            code = subprocess.run(cmd, cwd=REPO_ROOT, env=env, stdout=log,
                                  stderr=subprocess.STDOUT).returncode
        minutes = (time.monotonic() - t0) / 60
        ok = code == 0 and (dest / "eval_result.json").is_file()
        failed += not ok
        record["chunks"].append({"dir": dest.name, "tasks": part, "exit_code": code,
                                 "complete": ok, "minutes": round(minutes, 1)})
        manifest.write_text(json.dumps(record, indent=2), encoding="utf-8")
        status = "ok" if ok else f"FAILED (exit {code}; see {dest.name}.log)"
        print(f"chunk {k}/{len(chunks)} {status} in {minutes:.1f} min: "
              + " ".join(t.rsplit("-", 1)[-1] for t in part), flush=True)

    record["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    manifest.write_text(json.dumps(record, indent=2), encoding="utf-8")
    if failed:
        print(f"{failed} chunk(s) incomplete. Finished attempts are still readable from their "
              "harbor-jobs/ folders; rerun only the missing tasks into a new --out.")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--domain", required=True)
    ap.add_argument("--skill", help="skill folder (needed for the skill arm); it is snapshotted")
    ap.add_argument("--tasks", required=True, help="comma-separated task names or task numbers")
    ap.add_argument("--arms", default="skill", help="comma-separated arms (default: skill)")
    ap.add_argument("--chunk", type=int, default=4,
                    help="tasks per `stbench eval` call; each call gets its own token pool, "
                         "shared by chunk x arms attempts (tau3: keep that product <= 5)")
    ap.add_argument("--concurrency", type=int, default=2, help="attempts at once inside a chunk")
    ap.add_argument("--out", required=True, help="new directory; chunks go to <out>/bNN")
    a = ap.parse_args()
    if a.chunk < 1 or a.concurrency < 1:
        raise SystemExit("--chunk and --concurrency must be >= 1")
    if "skill" in a.arms.split(",") and not a.skill:
        raise SystemExit("the skill arm needs --skill")
    tasks = expand_tasks(a.domain, a.tasks)
    return run_batches(a.domain, Path(a.skill).resolve() if a.skill else None, tasks, a.arms,
                       a.chunk, a.concurrency, (REPO_ROOT / a.out).resolve())


if __name__ == "__main__":
    sys.exit(main())

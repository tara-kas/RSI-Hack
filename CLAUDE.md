# CLAUDE.md — RSI-Hack (skilltrainbench skill-writing hackathon)

Operating guide for Claude working in this repo. Sourced from `README.md`,
`submissions/README.md`, `hackathon.toml`, `dataset/hackathon/**/README.md`,
`.github/workflows/check-submissions.yml`, and `src/skilltrainbench/`.

---

## 1. What this repo is

We are the **curator**. We write a **skill** — a folder containing `SKILL.md` plus
optional supporting files — that makes a **frozen learner model** better at a domain.

```
we (+ AI assistant) ──write──▶ skill folder ──mounted read-only──▶ learner (frozen)
      ▲                                                               │
      └────────── scores + trajectories on training tasks ◀───────────┘
```

**The learner never changes. Only the skill changes.** The skill is scored on
private held-out tasks we never see, with the same learner and the same limits
available locally.

### Domains

| domain | benchmark | learner does | score per task |
|---|---|---|---|
| `qf` | QuantitativeFinance-Bench | solves a quant-finance task in a sandbox | task tests pass/fail |
| `health` | HealthBench | answers a health conversation | model-grader rubric, 0–1 |
| `tau3` | τ³-bench | serves a simulated customer via tool calls | task assertions pass/fail |
| `hle` | Humanity's Last Exam | answers an expert-level question | model-graded pass/fail |

---

## 2. HARD RULES — never violate

These come straight from `README.md` § Rules and `submissions/README.md`. A violation
can zero the submission.

1. **Learn from the training tasks only.** Never copy held-out content, grading
   rubrics, or answer keys from the public source datasets into a skill.
   - HealthBench rubrics live in `tasks/<id>/tests/example.json`; QF answer keys live in
     `tasks/<name>/tests/test_outputs.py` and `solution/solve.sh`. Reading them to
     *understand the domain* is fine; **transcribing them into a skill is not.**
   - Never embed task-specific answers, expected numbers, or task names/IDs in a skill.
   - Never include the QF canary GUID or its canary sentence in a skill file.
2. **Tools must be self-contained.** Scripts shipped in a skill run inside an
   air-gapped task container: **no external API calls, no network, no credentials,
   no URLs to fetch at runtime.** `check-skill` warns on external endpoints and
   API-key references and those warnings get human review.
3. **Do not change the learner.** Edits to `hackathon.toml` or to
   `src/skilltrainbench/` have **zero** effect on the score — scored runs use the
   organizers' copy of the config and harness. Do not "tune" them to make local
   numbers look better. Treat `hackathon.toml` as read-only.
4. **Every submission is screened for leaked task content and answer keys. A flagged
   skill scores zero.** When in doubt, leave it out.
5. **No symlinks** anywhere in a skill folder (hard `check-skill` error).
6. **Size limits** (`[submission]` in `hackathon.toml`): max **1,000,000 bytes** total,
   max **200 files** per skill folder.
7. **Never commit `.env`** or any real API key. `.gitignore` already excludes `.env`.

### Extra operating rules for me (Claude)

- **Cost is real.** Every `uv run stbench eval` spends the user's Runware credits;
  `health`, `tau3`, and `hle` additionally spend grader/simulated-user credits.
  **Always confirm with the user before launching an eval**, and state the domain,
  arms, and `--limit`. Default to small (`--limit 5`) when iterating.
- `qf` and `tau3` tasks spin up a full sandbox each (4–8 GB RAM) and can take tens
  of minutes. On a laptop use `--concurrency 1`.
- Never `git push`, open a PR, or commit unless explicitly asked.
- Do not delete or rewrite `runs/` output the user may still be reading.

---

## 3. Scoring — what actually earns points

- Each submitted skill runs on **private held-out tasks** in three arms:
  `baseline` (no skill), `placebo` (generic content-free skill), `skill` (ours).
- **Score = pass rate with our skill − pass rate with the placebo.**
- **Extra context on its own does not score.** The placebo already supplies generic
  "think step by step / double-check your arithmetic" advice, so a skill that is
  just more of that nets **zero**. The skill must add domain-specific, actionable
  procedure the learner would not otherwise follow.
- The live leaderboard and the final ranking use **different** held-out sets — do
  not overfit to any one number.
- Local numbers come from *training* tasks; treat them as a guide, not the truth.
- Scoring math lives in `src/skilltrainbench/scoring.py`: per-arm rates,
  placebo-adjusted `net_delta`, and a task-clustered bootstrap CI once there are
  **≥ 12 tasks** (`MIN_CI_TASKS`). Below 12 tasks there is no CI — a swing of a few
  tasks is noise, so do not declare victory on `--limit 5`.

The exact placebo text (from `evaluate.py`), so we know what we must beat:

```
---
name: placebo
description: generic problem-solving guidance (control arm)
---
Read the problem carefully. Work through it step by step and show your reasoning.
Double-check your arithmetic. End with a line: #### <answer>.
```

---

## 4. The frozen learner contract (`hackathon.toml` — read-only)

- Learner model: **`zai-glm-5-3-flash`** via Runware. Write for *this* model — not for
  Claude. It is a small/fast model: prefer short, concrete, checkable procedures over
  long prose.
- Harbor agent: `openhands-sdk`, pinned `version = "1.47.0"`.
- Upstream: `https://api.runware.ai` through a local metering gateway; key env
  `RUNWARE_API_KEY`.
- Default eval concurrency: 4.

Per-domain limits that constrain skill design:

| domain | `max_iterations` | notes |
|---|---|---|
| `qf` | 100 | 4M eval budget tokens; dataset `dataset/hackathon/QuantitativeFinance-Bench/tasks` |
| `health` | **4 turns**, `agent_timeout_s = 300` | judge `anthropic-claude-haiku-4-5`, temp 0 |
| `tau3` | 100 | simulated user + NL assertions: `anthropic-claude-sonnet-4-6` |
| `hle` | 50 | judge `anthropic-claude-sonnet-4-6` |

**`health` has only 4 learner turns and a 5-minute timeout** — a health skill must not
prescribe long multi-step exploration; it has to pay off in the first response.

### How the skill actually reaches the learner (verified from trial logs)

- OpenHands appends `SKILL.md` to the END of the system prompt as
  `[BEGIN context from [stbench-skill]]`, inside `<REPO_CONTEXT><UNTRUSTED_CONTENT>` with the
  line *"use these instructions for coding style, project conventions, and documentation
  guidance only."* The model is primed to treat the skill as untrusted repo conventions —
  phrase rules as the required procedure/format for the deliverable, not as persona advice.
- Only `SKILL.md` is injected. Supporting files are mounted at
  `/harbor/skills/stbench-skill/...` and are only used if `SKILL.md` tells the learner to
  run/read them by absolute path.
- The learner's tools are `terminal`, `file_editor`, `task_tracker`, `finish`. One tool call
  = one iteration, so `max_iterations` is an action budget.
- `trajectory.json` does NOT contain the skill text. To tell arms apart, grep the trial's
  `agent/openhands_sdk.txt`: `Loaded 0 skills` = baseline; placebo text vs our text
  distinguishes the other two.

---

## 5. Repo layout

```
hackathon.toml              the pinned learner contract (READ-ONLY)
README.md                   hackathon rules and the eval loop
src/skilltrainbench/        harness: gateway.py, harbor.py, evaluate.py, scoring.py,
                            tasks.py, config.py, cli.py   (READ-ONLY for scoring purposes)
submissions/                our skills live here
  README.md                 submission layout + check-skill
  example-team/health/SKILL.md   format-only example, not tuned for anything
  rsi-hack/qf/              QF skill (SKILL.md, reference/, scripts/check_output.py)
  my-team/health/           health skill (SKILL.md, scripts/check_reply.py) — team name
                            is a placeholder; user wants it kept here for now
tools/                      Class A host tools (splits.py, health_report.py)
splits/                     local train/test splits, <domain>-80-20-s20260919.json
runs/                       eval outputs (gitignored)
dataset/hackathon/          downloaded training tasks (gitignored)
.github/workflows/check-submissions.yml   runs check-skill on every PR touching submissions/
.env_example / .env         RUNWARE_API_KEY, optional HF_TOKEN
```

### Submission layout

```
submissions/<team-name>/<domain>/SKILL.md
submissions/<team-name>/<domain>/...        # optional extra files
```

`<domain>` ∈ `qf | health | tau3 | hle`.

`SKILL.md` **must** start with YAML frontmatter containing at least `name` and
`description`:

```markdown
---
name: my-skill-name
description: One line describing when and how this skill helps.
---

# ...
```

How it reaches the learner (`harbor.py`): the skill folder is copied to a staging dir
named `stbench-skill` and passed to Harbor as `--skill`; it is mounted **read-only** in
the task container at the start of every task. Only folders containing a `SKILL.md` are
staged. Supporting files (references, checklists, offline helper scripts) sit next to
`SKILL.md` and should be pointed at from `SKILL.md`.

---

## 6. Commands

Setup (already done here — `.venv/` and `.env` exist):

```bash
uv sync
cp .env_example .env    # then put RUNWARE_API_KEY in .env
uv run stbench data pull
```

List training tasks in a domain:

```bash
uv run stbench tasks --domain health
```

Start a new skill from the example:

```bash
cp -r submissions/example-team submissions/my-team
```

Evaluate (**spends credits — confirm with the user first**):

```bash
uv run stbench eval --domain health --skill submissions/my-team/health --limit 8 --out runs/health-v1
```

**On this Windows machine always prefix evals with `PYTHONUTF8=1`** (see §7), and select
tasks from the local split rather than `--limit` (which takes the alphabetically-first N):

```bash
PYTHONUTF8=1 uv run stbench eval --domain health --skill submissions/my-team/health \
  --arms skill --tasks "$(uv run python tools/splits.py tasks --domain health --split train --limit 15)" \
  --out runs/health-vN
```

Local splits (Class A tool, deterministic, stratified by `difficulty`, falling back to
`metadata.category` when a domain has no difficulty tiers):

```bash
uv run python tools/splits.py create --domain tau3      # once per domain
uv run python tools/splits.py show   --domain tau3
uv run python tools/splits.py tasks  --domain tau3 --split train --limit 5
```

Iterate on `train` only. Touch `test` only for milestone checks. Pick tasks balanced
across categories when the sorted `--limit` prefix would be lopsided.

Arms: the placebo text never changes, so once a task set has a placebo score, later
iterations run `--arms skill` only. Run `placebo` once on any NEW task set you want a
net delta for (e.g. the first test-split milestone).

Failure taxonomy for a health run (free, reads files only):

```bash
PYTHONUTF8=1 uv run python tools/health_report.py runs/health-v4 --arm skill
```

Useful `eval` flags:

- `--arms baseline,skill` (default); add `placebo` to measure what the leaderboard
  actually subtracts.
- `--tasks name1,name2` rerun exactly the tasks we care about.
- `--limit N` cap cost.
- `--concurrency N` fewer containers at once (use `1` on a laptop for `qf`/`tau3`).
- `--out` is required.

Outputs: `runs/<name>/eval_result.json` (summary + per-task scores) and
`runs/<name>/attempts.jsonl` (every attempt with the learner's answer and its Harbor
trial folder).

Read trajectories — what the learner actually did, step by step:

```bash
uv run harbor view runs/health-v1/harbor-jobs
```

Open it as `http://127.0.0.1:8080` explicitly — browsers that auto-upgrade to https cause
`Invalid HTTP request received` warnings (harmless `WinError 10054` tracebacks too). The
viewer shows saved runs only, not live progress.

Pre-submission check (same check the PR CI runs):

```bash
uv run stbench check-skill submissions/my-team/health
```

`check_skill` (in `config.py`) hard-fails on: not a directory, symlinks, >200 files,
>1,000,000 bytes, missing `SKILL.md`, missing/invalid frontmatter, missing `name` or
`description`. It emits *warnings* (flagged for human review, not auto-reject) for
external endpoints and credential-looking references.

---

## 7. Environment gotchas

- **Docker must be running** before any eval.
- **This machine is Windows 10** (x86_64, 4 cores/8 threads, 15.8 GB RAM, often <2 GB
  free), Docker Desktop with an **8 GB / 8 CPU** Linux VM. Git Bash and PowerShell both
  available. (Apple Silicon note for other machines: enable Rosetta in Docker Desktop.)
- **`PYTHONUTF8=1` is mandatory for evals.** `evaluate.py` writes `attempts.jsonl` with the
  default cp1252 encoding; one non-ASCII char (e.g. `≥`) in a learner answer crashes the
  write and `eval_result.json` is never produced. If that happens, per-trial rewards,
  answers and verdicts are still in `harbor-jobs/*/task__*/{verifier,agent}/`.
- **Every attempt installs the learner agent over the internet** (apt, `astral.sh` uv,
  Python 3.12, openhands-sdk): ~2.5 min of the ~4–5 min per health attempt. Flaky DNS here
  causes `Could not resolve host`, apt exit 100, and occasional exit 137 (OOM in 512 MB
  health containers). The harness retries infra failures 3×; if one attempt exhausts
  retries the whole eval raises. Concurrency 4 also triggers Docker buildx
  `rename ... being used by another process` build errors (retried automatically).
  The user prefers concurrency 4 for speed; accept the retries.
- **Docker Desktop can crash mid-eval** (seen 2026-09-19 ~14:38, likely host memory
  pressure): `Docker Desktop is unable to start`, the next attempt exhausts retries, the
  eval aborts (the harness's kill path also raises `signal has no attribute SIGKILL` on
  Windows). `docker desktop start` says "already running" — use `docker desktop restart`.
  Then rerun only the missing tasks into a new `--out` and merge with the completed ones.
- **Do NOT set `"dns"` in `~/.docker/daemon.json`.** Tried 2026-09-19: it breaks
  `host.docker.internal` resolution, so the learner cannot reach the gateway and every
  attempt fails with `LLMServiceUnavailableError ... Connection error`. Keep Docker's
  built-in DNS.
- **Resource budget:** a health attempt is 1 CPU / 512 MB. A **tau3 attempt asks for
  4 CPUs / 8 GB** — the whole Docker VM. Never run tau3 alongside another eval; run tau3
  with `--concurrency 1`, close heavy apps first, and consider raising the WSL2 limit
  (`%UserProfile%\.wslconfig` → `[wsl2] memory=12GB`, `wsl --shutdown`, restart Docker)
  only between runs.
- Requires Docker, `uv`, Python ≥ 3.12, and a Runware API key.
- Docker Desktop's kernel often cannot enforce the network allowlist, so local task
  containers may have public egress. **Do not rely on internet access** — scored runs on
  the organizers' Linux hosts restrict the learner to the gateway. `stbench eval` warns
  about this.

---

## 8. Training data — what we have and what we don't

`dataset/hackathon/` holds only the **training half** (`dev_task_names`) of each pinned
split. Held-out tasks are absent by design.

| dataset | pinned split | train tasks | held-out (absent) |
|---|---|---:|---:|
| `healthbench` | `hb-hardbeh-s002` (`hard_behavioural`) | 200 | 160 |
| `hle` | `hle-stem517-s001` (`stem517`) | 412 | 105 |
| `QuantitativeFinance-Bench` | `qf-medhard-strat-80-s005` (`medium_hard`) | 54 | 14 |
| `tau3-bench` | `tau3-banking-70-s001` (`banking_knowledge`) | 67 | 30 |

**Current local state (verified 2026-09-19):** all four are downloaded —
`healthbench` 200, `hle` 412, `QuantitativeFinance-Bench` 54, `tau3-bench` 67 task dirs.
Splits exist for `qf` and `health`; `tau3` and `hle` have none yet. All 67 tau3 tasks are
`difficulty = "medium"`, `category = "customer_service"`, so `tools/splits.py` gives them
a single stratum.

Task folder shape (Harbor format):

```
tasks/<name>/
  task.toml        metadata, resource limits, verifier env
  instruction.md   the agent-facing prompt
  environment/     Dockerfile (+ data/ for qf)
  tests/           test.sh + test_outputs.py (qf) or the graded rubric (health)
  solution/        solve.sh reference / oracle solution
```

Domain notes worth knowing:

- **HealthBench** — 200 train tasks across `context_seeking` (100),
  `health_data_tasks` (63), `emergency_referrals` (37). Graded by the pinned official
  OpenAI `simple-evals` grader running inside the verifier: a fractional, unclipped
  weighted rubric score. Reference no-skill `claude-sonnet-4-6` baseline on the hard
  variant is **0.210** overall (`emergency_referrals` 0.123, `context_seeking` 0.151,
  `health_data_tasks` 0.329). Behaviour themes are the lever: asking for missing
  context, safe escalation/referral, and handling health data tasks.
- **QuantitativeFinance-Bench** — 54 train tasks (28 hard, 26 medium), CC BY-NC 4.0
  (**non-commercial**). Stateful sandbox work: dirty data, runtime debugging, exact
  numeric output contracts. Instructions are long and specify precise output schemas —
  contract adherence (column names, dtypes, file paths, tie-break rules, rounding) is a
  common failure mode and a good skill target. Tasks pass/fail via pytest writing a
  reward to `/logs/verifier/reward.txt`. Tasks carry a canary GUID; never reproduce it.
- **τ³-bench** — MIT, Sierra Research, banking knowledge; simulated customer via tool
  calls. Task folders differ from the other domains: `environment/` has a
  `docker-compose.yaml` plus a `runtime-server/` (`server.py`, `task_config.json`), and
  `tests/` has `evaluate.py` + `config.json`. `[agent] timeout_sec = 3600`.
  `task_config.json` and `tests/` hold task-specific expected outcomes — read to
  understand the domain, never transcribe into a skill.
- **HLE** — expert-level STEM questions, model-graded.

Licensing is **per dataset folder**, not uniform. QF is non-commercial.

---

## 9. Working style for this repo

- **Read trajectories before editing a skill.** `uv run harbor view` shows where the
  learner actually went wrong. Guessing at fixes burns credits.
- **Write for `zai-glm-5-3-flash`, not for a frontier model.** Concrete checklists,
  explicit output contracts, and short decision rules beat essays.
- **Beat the placebo, not the baseline.** Generic reasoning advice is already the
  control. Every paragraph in a `SKILL.md` should encode something domain-specific.
- **Change one thing at a time** and rerun the same `--tasks` set so deltas are
  attributable.
- Keep `--limit` small while iterating; widen only once the skill stabilizes. Below 12
  tasks there is no confidence interval.
- Run `check-skill` before considering a skill done — the same check gates every PR.

---

## 10. Tooling conventions

**All tools in this repo are Python 3.12+.** Not bash, not a mix. The repo is already a
Python project (`pyproject.toml`, `uv`), skill scripts must run inside the task container
where Python plus `numpy`/`pandas` is what exists, and a single language means one mental
model for both. Reach for bash only for a genuine one-liner that will never grow.

There are **two classes of tool** with different constraints. Do not blur them.

### Class A — repo tools (`tools/`)

Run on the host, by us, via `uv run python tools/<name>.py`. May import project
dependencies and read `hackathon.toml`. Never invoked by the learner.

### Class B — skill scripts (`submissions/<team>/<domain>/scripts/`)

Run **inside the air-gapped task container**, invoked by the learner model via a shell
command that `SKILL.md` spells out. These carry hard extra rules:

- **stdlib only**, plus what the task image already pins (`numpy`, `pandas`, `scipy`,
  `pyarrow`, `statsmodels`, `scikit-learn`, `matplotlib`, `ta-lib`). Import the heavy ones
  *inside* the function that needs them and degrade gracefully if absent.
- **No network, no credentials, no `pip install`** — `check-skill` flags external endpoints
  and the container has no egress anyway.
- They count against the 200-file / 1 MB submission budget.
- `SKILL.md` must give the **absolute** container path
  (`/harbor/skills/stbench-skill/scripts/<name>.py`) — the learner will not guess it.
- Output is read by a model, not a human: print plainly, state what a clean result does
  *not* prove, and make failure messages say what to do next.

### House format (both classes)

```python
#!/usr/bin/env python3
"""One line: what this does.

Why it exists and what it is not, then runnable usage examples:

    python3 thing.py <input> --flag value
"""

from __future__ import annotations

import argparse
import sys


def do_work(path: Path, strict: bool) -> int:
    ...


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--strict", action="store_true", help="what this changes")
    a = ap.parse_args()
    return do_work(Path(a.path), a.strict)


if __name__ == "__main__":
    sys.exit(main())
```

Rules:

- Shebang, and `chmod +x` the file.
- Module docstring carries **runnable** usage examples; `description=__doc__` with
  `RawDescriptionHelpFormatter` so `--help` shows them.
- `from __future__ import annotations`; type hints on every signature.
- `argparse` only — no click, no bare `sys.argv`. Several modes means
  `add_subparsers(dest="cmd", required=True)`, as in `tools/splits.py`.
- `main() -> int` returning an exit code; `sys.exit(main())` under `__main__`. Never call
  `exit()` mid-function.
- **Exit codes**: `0` success. `1` the thing being checked failed (a real finding — the
  caller may act on it). `raise SystemExit("message")` for *usage* errors — bad flags,
  missing config, a split that does not exist — so the two are distinguishable.
- Deterministic by construction: seed explicitly, sort before iterating, never depend on
  `set`/`dict` ordering. Anything that writes a file records its seed and inputs in that
  file.
- Destructive writes refuse to clobber without `--force`, and the refusal explains the
  consequence rather than just saying "exists".
- Print human-readable text to stdout. Add `--json` only when something will parse it.
- Comments explain **why**, not what. Match the surrounding density.

Current tools — new tools match these:

| tool | class | what it does |
|---|---|---|
| [`tools/splits.py`](tools/splits.py) | A | deterministic stratified train/test splits; `tasks` prints a `--tasks` list |
| [`tools/health_report.py`](tools/health_report.py) | A | health failure taxonomy: per-attempt score + 1–2 sentence why, structural flags, rubric points lost per axis |
| [`submissions/rsi-hack/qf/scripts/check_output.py`](submissions/rsi-hack/qf/scripts/check_output.py) | B | QF output-file schema validator |
| [`submissions/my-team/health/scripts/check_reply.py`](submissions/my-team/health/scripts/check_reply.py) | B | health reply structure check per mode; prints PASS or FIX + one-line fixes |

Class B gotcha: importing a skill script from the host (as `health_report.py` does) writes
`__pycache__/` into the skill folder, which would ship. Set `sys.dont_write_bytecode = True`
before importing, and check `find submissions/<team>/<domain> -type f` before submitting.

## 11. The iteration loop that worked (health, 2026-09-19)

Apply the same method to every domain:

1. **Measure before editing.** Baseline + placebo + skill on a few train tasks, then read
   the grader output per task — not just the mean.
2. **Deterministic taxonomy, not vibes.** Write a Class A report tool that turns a run into
   per-attempt `(score, why_it_failed)` lines and counted buckets (health: rubric points
   lost per `axis:` tag + structural flags). Fix the biggest bucket first.
3. **Infra failures first.** The costliest early bug was not medical: the learner answered
   in chat and never wrote `/logs/agent/response.txt` → whole task scored as empty. Find the
   deliverable contract for the domain and make the skill's first instruction enforce it.
4. **Tools beat prose, within the action budget.** A Class B checker the learner runs on
   its own output (write → check → one fix → finish) fit health's 4-action budget and was
   used 15/15 times. Only add a tool if the budget has room and the failure is common
   (a calculator was rejected: calc criteria appear in 7/160 health tasks).
5. **Mine the whole train split, not the 6 tasks you read.** Aggregating all train rubrics
   found benchmark-wide shared criteria (e.g. health's question-priority hierarchy,
   conditional "if/then" guidance) worth more than per-task fixes.
6. **Overfitting guard.** Every rule must be backed by a pattern across many train tasks or
   be standard domain practice; drop anything traceable to 1–2 tasks; never use rubric or
   assertion wording. Include a fallback mode so rigid templates don't misfire on odd
   tasks. Judge on the untouched test split.
7. **Noise.** Same task, same skill, rerun: swings of ±0.3 are normal on health. Compare
   on ≥12 tasks and the same task set.

Health status (2026-09-19): on the 6 tasks with placebo scores — placebo 0.299,
baseline 0.281, v3 0.437, v4 0.456 (net +0.157, beats placebo 5/6). On 15 train tasks
v3 0.444 ≈ v4 0.434 (v4 better on context_seeking/emergency, worse on data tasks).
v4 lost −0.72 on one task because the checker's DOCUMENT rule and a "too short" rule
fired on a correct 3-line ICD-code answer and the learner rewrote it wrong — **checker
rules must never fire on short/fixed-format answers; the learner obeys them even when
wrong.** Fixed (short answers exempt; format-precedence rule + `--mode other` in
SKILL.md; "never change a correct fact to satisfy the checker"). Current skill = v4 +
these fixes. **Test-split milestone 1** (`runs/health-test-milestone1`, 8 unseen test
tasks, placebo + skill): placebo 0.379, skill 0.513, **net +0.133** (4 wins, 1 tie,
3 losses; no CI at n=8) — close to the train estimate, so no sign of heavy overfitting.
Worst loss (−0.46): a parent-facing clinical document routed to `--mode other`, which
skips all checks, and it omitted dosing/complication details. Watch OTHER being used as
an escape hatch for clinical documents.
Rough cost: ~$0.05/health attempt (grader dominates); time is the constraint.

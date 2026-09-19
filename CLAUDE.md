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
- **Apple Silicon (this machine is darwin/arm64):** task containers are amd64. Docker
  Desktop → Settings → General → **"Use Rosetta for x86_64/amd64 emulation on Apple
  Silicon"** must be ON, then Apply & restart. The default QEMU emulation crashes while
  the learner agent installs. `stbench eval` prints a warning when it is off.
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

**Current local state (verify before trusting):** only `QuantitativeFinance-Bench`
(54 tasks) and `healthbench` (~164 of the 200 task dirs listed in its `dataset.toml`)
are downloaded. `hle/` and `tau3-bench/` are **missing** — re-run
`uv run stbench data pull` before working those domains, and expect
`stbench tasks --domain hle|tau3` to come up empty until then.

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
  calls.
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

## 10. Repo hygiene note

`.env_example` currently has a **real-looking Runware API key committed into it**
(`RUNWARE_API_KEY=Bxa...`) — it is a tracked, uncommitted modification on `main`.
`.env_example` is explicitly **not** gitignored (`!.env_example`), so committing this
publishes the key. It should be reverted to `RUNWARE_API_KEY=` and the actual key kept
only in `.env`. Flag this to the user rather than committing over it; if the key was
already pushed anywhere, it should be rotated.

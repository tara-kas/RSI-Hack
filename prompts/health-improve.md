# Kickoff prompt: health, round 2 (maximise the held-out score)

Paste everything below the line into a fresh Claude Code session at the repo root.

---

# Role and context

You are an expert AI prompt engineer, Python developer, and my autonomous co-pilot for a
"recursive context optimization" hackathon. We improve a **frozen** learner
(`zai-glm-5-3-flash` via OpenHands, 4 actions per task, 300 s timeout) on **HealthBench**
by editing only a **skill folder** mounted read-only into its container. The score is
**skill pass rate − placebo pass rate** on 160 private held-out HealthBench-hard tasks
(same benchmark, same three categories, same grader: Claude Haiku 4.5 rubric judge).

A first round already produced a working skill. It beats the placebo by about +0.13 to
+0.16. This round's goal is to **raise that margin significantly without overfitting**.
**The whole computer is available for health.** No other eval will compete for Docker, so
larger task sets and concurrency 4 are fine.

**Skill folder:** `submissions/my-team/health/` (`SKILL.md` +
`scripts/check_reply.py`). Keep the team name `my-team`.

# Step 0: read everything first (no shortcuts)

1. `CLAUDE.md`, in full. Pay particular attention to §2 hard rules, §3 scoring, §4 how the
   skill is injected (appended to the system prompt as untrusted "repo context"), §6
   commands, **§7 Windows gotchas** (`PYTHONUTF8=1` is mandatory; never set Docker DNS;
   `docker desktop restart` after a crash), §10 tool conventions, and **§11 the iteration
   method plus the current health status**. It overrides your defaults.
2. The current skill: `submissions/my-team/health/SKILL.md` and
   `scripts/check_reply.py`. Understand the 4-action loop (write, check, one fix, finish),
   the five modes (EMERGENCY / ANSWER / ASK / DOCUMENT / OTHER) and the checker's rules.
3. The tools: `tools/health_report.py` (failure taxonomy per run) and `tools/splits.py`.
   The split is `splits/health-80-20-s20260919.json`: 160 train, 40 test.
4. The past runs, all under `runs/`. Read each run's `eval_result.json` /
   `attempts.jsonl`, and run `tools/health_report.py` on each:

   | run | what | key result |
   |---|---|---|
   | `health-baseline` | 3 train tasks, 3 arms | recovered from `harbor-jobs/` (its `attempts.jsonl` is empty) |
   | `health-v2` | 6 train tasks, baseline/placebo/skill | placebo and baseline ≈ 0.28, skill 0.35 |
   | `health-v3` | 15 train tasks, skill only | 0.444, added the checker |
   | `health-v4` + `health-v4b` | same 15 tasks, skill only (split after a Docker crash) | 0.434 |
   | `health-test-milestone1` | 8 **test** tasks, placebo + skill | placebo 0.379, skill 0.513, **net +0.133** |
   | `health-v3-aborted-dns` | ignore | infra failure |

   On the 6 tasks that have placebo scores: placebo 0.299, v3 0.437, v4 0.456.
5. `git status`, `git log --oneline -8`, `docker ps` (should be idle).

Then summarise back to me: current score estimates, the weakest category, and the
biggest remaining loss buckets, **with numbers**.

# Hard constraints (violations zero the submission)

- **Data scope:** use only `dataset/hackathon/healthbench/` and our own `runs/`. Never
  fetch or consult upstream HealthBench / simple-evals repos or the web for task content.
- **No leakage:** rubric criteria in `tests/example.json` are for diagnosis only. Never
  put rubric wording, task-specific facts (named conditions, drugs, doses, codes tied to a
  task), task IDs or conversation content into the skill. Teach procedures. Every new
  rule must be backed by a pattern across many train tasks, or be standard clinical
  practice. Drop anything traceable to 1–2 tasks.
- **Test split discipline:** mine rubrics from **train only**. Eight test tasks were
  used once for milestone 1 (listed in `runs/health-test-milestone1/attempts.jsonl`).
  The other 32 test tasks have never been run. Keep them for final milestones.
- Class B scripts: stdlib only, offline, absolute path
  `/harbor/skills/stbench-skill/scripts/...`. No `__pycache__` in the skill folder (set
  `sys.dont_write_bytecode = True` when importing from the host, and check with
  `find submissions/my-team/health -type f`).
- Never edit `hackathon.toml` or `src/skilltrainbench/`. Never commit or push unless I
  ask. **Confirm with me before every `stbench eval`**, stating the arms, task list,
  concurrency, expected time and cost. About $0.05 per attempt; a round of 4 attempts
  takes about 7 minutes at concurrency 4.

# Step 1: deep diagnosis (free, no evals)

1. Pool every skill-arm attempt from v3, v4, v4b and milestone 1 (about 38 attempts). Use
   `health_report.py` and your own scratchpad scripts to produce:
   - points lost per rubric axis, per category
   - how often each mode was chosen, versus category, and the score by mode, to find
     **misrouting** (for example, a clinical document sent to `--mode other`, which skips
     every check; this caused milestone 1's worst loss, −0.46)
   - how often the checker gave PASS or FIX, and whether FIX edits helped or hurt (compare
     each reply before and after the edit where the trajectory shows both)
   - reply length against score
   - whether questions were asked in the priority order the shared criteria reward
     (urgency, then safety facts, then cause)
2. Mine **all 160 train rubrics** for content-completeness patterns: what kinds of
   information the "fails to…" penalties and completeness criteria demand, by category.
   Examples: dose and duration when a treatment is named, complications to watch for,
   what to avoid, the standard next test, the follow-up interval. Count them. Only
   patterns that recur across many tasks qualify.
3. Read 5–8 of the lowest-scoring skill trajectories end to end (`uv run harbor view
   runs/<run>/harbor-jobs`, opened at `http://127.0.0.1:8080`).

Deliver a **ranked failure taxonomy**: each bucket with a count, the points lost, an
example, and a one-line hypothesis.

# Step 2: plan the changes (present to me before building)

Rank candidate changes by **expected gain × breadth ÷ risk**. Evaluate at least these,
and add your own from the data:

1. **Close the OTHER escape hatch.** Restrict OTHER to pure format jobs with no clinical
   content (rewrite, translate, a single code or letter). Any clinical document, including
   a parent-facing one, goes to DOCUMENT.
2. **A content-completeness procedure**, if Step 1 confirms it at scale. For example, a
   short "whenever you name X, also state Y" list: treatment → dose basis, duration, key
   risks, what to avoid; diagnosis → complications and warning signs; test → what a
   result means and the next step. Keep it general; no named conditions or drugs.
3. **Context-seeking**, the weakest category (train about 0.32, test +0.04 over the
   placebo). Better question selection (the single most informative question first), an
   up-front statement that details are needed, and conditional guidance. Verify against
   the shared criteria counts from train.
4. **Documentation and data tasks:** when the input is thin, say up front that a
   complete document can't be written reliably, then give a short draft and ask. Never
   fabricate (penalties recur).
5. **Checker changes:** add a check only if it targets a common, clear failure and
   cannot fire on correct short or fixed-format answers (§11 lesson: the learner obeys
   the checker even when it's wrong). Consider a mode-sanity check (a clinical document
   run under `--mode other` gets FIX). Any checker change must be regression-tested on
   all past replies, with PASS/FIX compared against score, before an eval.
6. **Length and clarity:** only if Step 1 shows a length or repetition penalty.
7. **Optional, only if time allows:** a fast proxy evaluator (call the learner directly
   through the Runware gateway, wrap the skill the way OpenHands does, grade with the
   same Haiku rubric grader). Build it only if it can be validated against real harness
   scores on at least 10 tasks. GEPA-style automated search would require a
   rubric-overlap leak screen on every candidate. The `--write` retry loop in the checker
   was rejected in round 1 for overfitting risk; revisit only with evidence.

For each change: the bucket it targets, the number of train tasks it applies to, the
expected effect, and its risk (including overfitting and misfiring on unusual tasks).
Group changes into at most 2–3 eval rounds. **Wait for my approval.**

# Step 3: evaluate properly (with approval)

- **Train comparison:** 30 train tasks (10 per category, chosen deterministically from
  the split, including the 15 used in v3/v4), skill arm only. That's 30 attempts, about
  55 min and $1.50. With 30 tasks there's a confidence interval. Compare with a v4 run on
  the same 30 tasks (15 are already done) so any delta is attributable. Run `placebo`
  once on the 15 new tasks.
- **Test milestones:** the untouched 32 test tasks, placebo + skill (64 attempts, about
  2 hours, about $3.20), only for the final candidate. Optionally one intermediate
  milestone on 12 of them.
- After each run: `tools/health_report.py`, a per-category delta, and PASS/FIX
  effectiveness. Keep a change only if it helps on the train comparison **and** doesn't
  hurt any category by more than noise.
- If an eval crashes (Docker, encoding), recover from `harbor-jobs/` and rerun only the
  missing tasks into a new `--out` (CLAUDE.md §7).

# Step 4: finalise

- **Leak screen:** write a small Class A tool that compares every sentence in `SKILL.md`
  and `check_reply.py` against all local rubric criteria and conversation text (n-gram /
  fuzzy overlap), and flags anything suspicious. Fix any hits.
- `uv run stbench check-skill submissions/my-team/health`: must be ok, 2–3 files, no
  warnings.
- Update CLAUDE.md §11 (health status, lessons) and the memory notes with the final
  numbers.

# Working style

- Counts, not impressions. Deterministic checks where possible; the LLM judge is
  the last resort.
- Write the skill for a small, fast model: short, concrete, checkable. Every line has
  to earn its place. Longer isn't better.
- Changes to the skill folder must never happen while an eval is running (each attempt
  copies the folder when it starts).
- Keep me posted with short updates. Ask only when the decision is genuinely mine.

If you understand these instructions, reply with "Context loaded. Ready to push the
health score." and begin Step 0.

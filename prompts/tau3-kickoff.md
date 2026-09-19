# Kickoff prompt — τ³-bench (`tau3`) skill

Paste everything below the line into a fresh Claude Code session at the repo root.

---

# Role and context

You are an expert AI prompt engineer, Python developer, and my autonomous co-pilot for a
"recursive context optimization" hackathon. We improve a **frozen** learner model on a
benchmark by writing a **skill folder** that is mounted read-only into the learner's task
container. The model, harness, graders and limits are fixed in `hackathon.toml`; only the
skill changes. We already ran this loop on the `health` domain — the method, tools and
lessons are recorded in `CLAUDE.md`. Now we start the **`tau3`** domain (τ³-bench, banking
knowledge: the learner serves a simulated customer through tool calls, scored by task
assertions, pass/fail).

**Deliverable:** `submissions/my-team/tau3/` containing `SKILL.md` plus any supporting files
(Class B scripts, references). Team folder `my-team` is a placeholder the user wants kept
for now (QF lives under `submissions/rsi-hack/`; do not move anything).

**Score = pass rate with our skill − pass rate with the placebo**, on private held-out
tau3 tasks. Generic advice nets zero; the skill must add domain-specific procedure.

# Step 0 — read before doing anything (no shortcuts)

Read these in full and keep them in mind for every decision:

1. `CLAUDE.md` — hard rules (§2), scoring (§3), learner contract and how the skill is
   injected (§4), commands (§6), **Windows environment gotchas (§7)**, data notes (§8),
   tooling conventions for Class A/B tools (§10), and **the iteration method that worked
   on health (§11)**. It overrides your defaults.
2. `README.md`, `submissions/README.md`, `hackathon.toml` (read-only; note
   `[domains.tau3]`: `max_iterations = 100`, simulated user and NL-assertion grader are
   `anthropic-claude-sonnet-4-6`).
3. The existing tools, as the house style to match: `tools/splits.py`,
   `tools/health_report.py`, `submissions/my-team/health/scripts/check_reply.py`,
   `submissions/rsi-hack/qf/scripts/check_output.py`, and both existing `SKILL.md`s.
4. The harness code paths that touch tau3: `src/skilltrainbench/tasks.py` (how a tau3
   task is loaded and scored), `harbor.py` (how the skill is staged, aux model env),
   `evaluate.py` (arms, retries, what makes a run abort). Read-only.
5. `git status` and `git log --oneline -5`. Check `docker ps` — **if a health eval is
   running, do not start any Docker work** (a tau3 attempt needs the whole 8 GB VM).

Then give me a short summary of what you learned that is specific to tau3 before
moving on.

# Hard constraints (from CLAUDE.md — restated because violations zero the submission)

- Learn from training tasks only. `task_config.json`, `tests/`, `solution/` contain
  task-specific expected outcomes: read them to understand the domain, **never transcribe
  task content, expected values, assertion wording, customer names/IDs or task names into
  the skill.** Teach procedures, not memorized answers.
- Class B scripts are self-contained: stdlib (plus what the task image already has), no
  network, no credentials, no URLs. Give absolute container paths
  (`/harbor/skills/stbench-skill/scripts/<name>.py`) in `SKILL.md`.
- Never edit `hackathon.toml` or `src/skilltrainbench/`. No symlinks. ≤200 files, ≤1 MB.
- **Every eval spends credits (tau3 is the expensive one: Sonnet simulated user + Sonnet
  assertions). Confirm with me before any `stbench eval`**, stating arms, task list, and
  concurrency. Never commit, push, or open a PR unless I ask.
- Do not touch `~/.docker/daemon.json` DNS (breaks `host.docker.internal`; see §7).

# Step 1 — train/test split

- Run `uv run python tools/splits.py create --domain tau3` (seed 20260919, 80/20). All 67
  tasks are `difficulty = "medium"`, `category = "customer_service"`, so it will be a
  single stratum — that is acceptable.
- Only if the data exploration in Step 2 reveals a genuinely meaningful task-type field
  (e.g. in `task_config.json`) should you propose stratifying by it — and if you change
  `tools/splits.py`, prove the existing `qf` and `health` split files regenerate
  byte-for-byte identical before keeping the change. Do not silently re-split after
  exploring the test half.
- `test` is our local holdout: do not read test-task configs in detail during
  exploration; aggregate statistics over train only.

# Step 2 — explore the data (free — no evals, no Docker)

Work over the **train** tasks and produce counts, not impressions. Write any analysis
scripts to the scratchpad (or as a Class A tool in `tools/` if reusable). Find out:

1. **What the learner sees and must do:** read several `instruction.md` files. What is
   the deliverable? How does the learner talk to the customer and call banking tools — MCP
   tools, a CLI, HTTP to the runtime server? How does a conversation end? (On health the
   costliest bug was the learner not producing the deliverable at all — find tau3's
   equivalent contract.)
2. **The environment:** `environment/docker-compose.yaml`, `runtime-server/server.py`,
   `task_config.json`. Which tools/actions exist, their arguments, and how often each
   appears across tasks. Is there a policy document or knowledge base the agent must
   consult? Where does it live and how big is it?
3. **How it is scored:** `tests/evaluate.py`, `tests/config.json`, `test.sh`. Is it
   database-state comparison, required actions, NL assertions, communicated info, or a
   mix? What exactly makes a task fail? Tabulate assertion/check types across train tasks.
4. **Customer request types:** cluster the train tasks by what the customer wants
   (e.g. disputes, transfers, card issues, account changes, info questions) and by what
   makes them hard (policy exceptions, multi-step, identity verification, refusals).
5. **Budget and timing:** 100 iterations, 3600 s agent timeout, one container at 8 GB —
   estimate how many actions a typical solution needs (from `solution/solve.sh` or the
   task structure).

Deliver a **data brief**: a compact markdown summary with the counts above, the
deliverable contract, the scoring mechanics, and the top 3–5 hypotheses for where a
small model (`zai-glm-5-3-flash`) will fail.

# Step 3 — decide on basic tools (evidence-based)

From the brief, propose a **small** toolset — only tools that target a failure mode that
appears in many train tasks and fit the action budget (lesson from health: a calculator
was rejected because only 7/160 tasks needed arithmetic). For each, give: the failure it
prevents, how many train tasks it applies to, how the learner invokes it, and its cost in
actions. Typical candidates to evaluate (do not assume — justify or reject each):

- **Class B (learner-side):** a policy/knowledge lookup helper over files mounted in the
  skill folder (only if the policy is general, not task-specific); a pre-action checklist
  or validator for irreversible actions (verify identity, confirm with the customer,
  check policy eligibility before writing to the database); a small calculator for
  fees/interest/dates if amounts are common; a conversation-closing checklist.
- **Class A (host-side):** `tools/tau3_report.py` — the tau3 equivalent of
  `health_report.py`: per-attempt pass/fail, a 1–2 sentence why-it-failed from the
  verifier output, and counted failure buckets (wrong action, missing action, wrong
  argument, policy violation, info not communicated, premature end, infra).

Also write a barebones `submissions/my-team/tau3/SKILL.md` (valid frontmatter, a minimal
deliverable-contract section only) so a baseline can run. Run
`uv run stbench check-skill submissions/my-team/tau3`.

**Stop here and wait for my approval** before building the tools.

# Step 4 — propose the baseline run (do not launch without approval)

Propose exactly:

```bash
PYTHONUTF8=1 uv run stbench eval --domain tau3 --skill submissions/my-team/tau3 \
  --arms baseline,placebo,skill \
  --tasks "<3 train tasks you chose, spread across request types>" \
  --concurrency 1 --out runs/tau3-baseline
```

State the expected wall time and a cost estimate. Before launching: no other eval
running, heavy apps closed, Docker healthy. After it finishes: build/run the taxonomy
tool, read the trajectories (`uv run harbor view runs/tau3-baseline/harbor-jobs`, open as
`http://127.0.0.1:8080`), and report the failure taxonomy with counts, then propose ONE
targeted fix (prose or tool) and wait for approval.

# Working style

- Measure before editing; one hypothesis per change when time allows; same task set
  across iterations; ≥12 tasks before trusting a delta; the test split only for
  milestones (run placebo once on any new task set, then skill-only).
- Write for a small, fast model: short, concrete, checkable procedures, not essays.
- If an eval dies with an encoding error or `eval_result.json` is missing, recover from
  `harbor-jobs/` (see §7) rather than re-running.
- Keep me posted with short updates; ask when a decision is genuinely mine.

If you understand these instructions, reply with: "Context loaded. Ready to optimize the
tau3 domain." and then begin Step 0.

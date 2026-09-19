# Handoff prompt: τ³-bench (`tau3`) skill, session 2

Paste everything below the line into a fresh Claude Code session at the repo root.
Written 2026-09-19 at the end of session 1. Everything here was verified in session 1 unless
it is marked as a hypothesis.

---

# Role and goal

You are my co-pilot for a "recursive context optimization" hackathon. We improve a **frozen**
learner model (`zai-glm-5-3-flash`, OpenHands SDK 1.47.0, 100 iterations) on τ³-bench banking
by editing a **skill folder**, `submissions/my-team/tau3/`, which is mounted read-only into the
learner's task container. **Score = pass rate with our skill − pass rate with the placebo**, on
private held-out tasks. The goal of this session is to fix the open tau3 failure modes below,
update the skill and tools from the findings, and measure the result.

Read `CLAUDE.md` first. It holds the hard rules (§2), the scoring rules (§3), how the skill
is injected (§4) and the house tooling conventions (§10). **Some of its tau3 guidance is out
of date. The "Superseded CLAUDE.md guidance" section below takes precedence.** Then read the three files
under "Current artifacts" before you edit anything.

# Hard constraints (a violation zeroes the submission)

- Learn from **train** tasks only. `task_config.json`, `tests/` and `solution/` hold expected
  outcomes. Read them to understand the domain, but **never transcribe product names, card
  or account names, customer names, IDs, task names, or discoverable tool names (e.g.
  `open_bank_account_4821`) into the skill.** Teach procedure, not answers.
- Class B scripts: stdlib only, no network, no credentials, no URLs. Give absolute container
  paths (`/harbor/skills/stbench-skill/scripts/<name>.py`) in `SKILL.md`.
- Never edit `hackathon.toml` or `src/skilltrainbench/`. No symlinks. ≤200 files, ≤1 MB.
- **Every eval spends credits. Confirm with me before any `stbench eval`**, stating the arms,
  the task list and the concurrency. Never commit, push or open a PR unless I ask.
- Do not touch `~/.docker/daemon.json` or `~/.docker/config.json`. Ask before any other host
  change (WSL config, Docker restarts). I have rejected intrusive host changes before.
- I want fast iteration: small batches, short updates, and questions only when a decision is
  genuinely mine.

# Environment on this machine (Windows 10, repo `C:\Users\soseb\Documents\RSI-Hack`, branch `tau`)

1. **`uv` is not on PATH in Claude's shells.** Use `.venv\Scripts\python.exe` directly, for
   example `.venv\Scripts\python.exe -m skilltrainbench.cli check-skill submissions/my-team/tau3`.
2. **Put `.venv\Scripts` on PATH for evals.** Otherwise the harness cannot find `harbor`:
   `_harbor_executable()` falls back to `.venv/Scripts/harbor` without the `.exe`, and every
   attempt fails instantly with `runtime_exec_error`, which costs nothing but aborts the eval.
3. **Docker's credential helper is broken in this remote (VS Code server) logon session.**
   `docker-credential-desktop` and `wincred` both fail with Windows error 1312, "A specified
   logon session does not exist". The persistent fix is already in place: the user env var
   `DOCKER_CONFIG=%USERPROFILE%\.docker-anon`, a folder holding anonymous file-based auth and a
   copy of the `desktop-linux` context. Docker Desktop never rewrites it. Claude's process may
   predate that variable, so **set it explicitly in every eval command.**
4. `PYTHONUTF8=1` is mandatory, because `attempts.jsonl` is written in cp1252 otherwise.
5. `ProactorBasePipeTransport ... I/O operation on closed pipe` tracebacks at exit are harmless.

The exact eval launch that works (PowerShell, run in the background):

```powershell
$env:DOCKER_CONFIG = "$env:USERPROFILE\.docker-anon"
$env:PATH = "C:\Users\soseb\Documents\RSI-Hack\.venv\Scripts;$env:PATH"
$env:PYTHONUTF8 = 1
$tasks = @('001','017') | ForEach-Object { "tau3-bench__tau3-banking_knowledge-task-$_" }
.venv\Scripts\python.exe -m skilltrainbench.cli eval --domain tau3 --skill submissions/my-team/tau3 `
  --arms skill --tasks ($tasks -join ',') --concurrency 2 --out runs/tau3-vN
```

The skill folder is copied **per attempt**, so never edit `SKILL.md` while an eval is running.
If you do, the attempts end up split across skill versions.

## Superseded CLAUDE.md guidance (these measurements replace it)

- CLAUDE.md says a tau3 attempt needs 4 CPUs / 8 GB, so run at concurrency 1. **Measured:
  about 727 MB per attempt** (main container 466 MiB + runtime sidecar 261 MiB), roughly 1.1
  CPU. The `task.toml` figures are Docker *limits*, not reservations. The Docker VM has 12
  CPUs and 8.27 GB. Concurrency 2 is safe. Concurrency 6 should fit, but parallel
  agent installs over flaky DNS are the real risk, and one attempt that exhausts its retries
  aborts the whole eval.
- CLAUDE.md says tau3 has no split. **The split exists:** `splits/tau3-80-20-s20260919.json`,
  54 train / 13 test. The test tasks are 014 029 032 035 036 044 049 053 056 074 078 085 101.
  Do not read test configs; use them only for a milestone check.
- **Timing and cost:** about 6.5 min per attempt once the image is cached (the first build is
  about 5 min), and about **$0.023 per attempt** (learner plus simulated user). Time is the
  constraint, not credits.

# How tau3 is graded (verified from the verifier and runtime source)

- The learner talks to a simulated customer (Sonnet 4.6) over the `tau3-runtime` MCP server:
  `start_conversation`, `send_message_to_user`, `end_conversation`, and domain tools including
  `KB_search` (BM25), `log_verification`, `unlock_discoverable_agent_tool`,
  `call_discoverable_agent_tool`, `give_discoverable_user_tool`, `transfer_to_human_agents` and
  `get_current_time`. Unlocked tools never become MCP tools; they are only reached through
  `call_discoverable_agent_tool(name, arguments)`.
- **Hard gate:** `termination_reason` must be `agent_stop` or `user_stop`. Anything else scores
  0 and the evaluator never runs. `max_errors = 10` means ten failed tool calls end the run at
  0. `max_steps = 200` on the runtime side; the binding limit is OpenHands' 100 iterations.
- **`reward_basis`:** DB in 51 of 54 train tasks, ACTION in 3. **There are no NL assertions and
  no `communicate_info` checks anywhere in train. The conversation text is never graded; only
  the final database state is.**
- **OpenHands ends the agent's run as soon as the model emits an assistant message with no
  tool call.** A reply written as chat instead of sent with `send_message_to_user` therefore
  never reaches the customer, leaves the conversation open, and scores 0.
- The skill **is** injected in full, at the end of the system prompt, but wrapped in
  `<UNTRUSTED_CONTENT>` with the line "use these instructions for coding style, project
  conventions, and documentation guidance only." The model is primed to discount it. Phrase
  rules as the required output/tool-call contract, not as advice.
- In the tau3 verifier `result.json`, `used_tau2_evaluator` can read `true` even when the
  no-stop branch fired. Classify on `termination_reason`, as `tools/tau3_report.py` does.

# Oracle analysis over all 54 train tasks (aggregate counts, safe to use as design evidence)

| finding | count |
|---|---|
| tasks requiring `log_verification` | 46/54, always exactly 0 or 1 per task |
| `log_verification` is the **first** recorded action when present | 45/46 |
| tasks without verification start with | `apply_for_credit_card` 6, `transfer_to_human_agents` 2, `request_human_agent_transfer` 1 |
| agent-discoverable tools (unlock → call) | 37/54; 164 unlocks vs 264 calls, so one unlock serves many calls |
| user-discoverable tools (give → customer calls) | 14/54; 0/54 oracles leave a given tool unused |
| oracles that leave an unlock unused | 5/54, all of them read-only `get_*` tools |
| oracles that repeat a write | 2/54 |
| "refusal/ineligible"-flavoured scenarios where the oracle **still writes** (records the denial) | 14/14 |
| customer applies for a credit card (the product choice decides the DB) | 11/54 |
| `open_bank_account` (the account-type choice decides the DB) | 9/54 |
| distinct discoverable tool names | 82; the most common appears in only 24 tasks, so there is no list to memorize |
| oracle action count per task | median 9, range 1–30 |
| required KB documents per task | median about 9, range 1–30 |
| tasks giving the customer `request_human_agent_transfer` | 10/54 (see the upstream-block hypothesis below) |

Scratch analysis scripts from session 1 are in the session-1 scratchpad and may be gone. They
are easy to regenerate from `environment/runtime-server/task_config.json`
(`task.evaluation_criteria.actions`, `task.user_tools`, `task.required_documents`,
`task.user_scenario.instructions`).

# Eval results so far (`--arms skill` only; no placebo run on tau3 yet, by my choice)

**v1**, `runs/tau3-v1`, the old skill, tasks 001 017 076 093: **1 of 4 passed.**
- 001 passed: 5× `KB_search`, then the customer called `apply_for_credit_card`. It matched the
  oracle exactly.
- 017 `replied_in_chat`: right after `start_conversation` it wrote the identity request as
  plain text, and the run ended.
- 076 `replied_in_chat`: after 5 KB searches it found the right product, then *wrote* the
  answer as plain text, and the run ended.
- 093 `agent_blocked`: 30× `litellm.BadRequestError: Invalid value for
  'tools[1].schema.properties'` on `start_conversation`, then OpenHands' stuck-detector fired.

**v2**, `runs/tau3-v2`, the current skill, 12 tasks (001 017 076 093 003 005 008 021 050 059
060 087), concurrency 2. **It was still running at handoff.** Done so far:
- 001 **passed** again.
- 076 **passed**. It was fixed since v1: every reply went through the tool, verification was the
  first recorded action, and it closed with `user_stop`. **It passed despite an extra
  unlock+call of a read-only tool that is not in the oracle.** That is evidence (n=1) that extra
  read-tool unlocks do not break the DB hash, which contradicts my earlier hypothesis that every
  unlock is hashed.
- 017 `replied_in_chat` **again**, near word-for-word identical to v1. It reproduces
  deterministically on the opening turn, and the §0 rule did not fix it.
- 093 `agent_blocked` again (13× schema rejection, `term=agent_error`). It is deterministic.
- 003 `wrong_outcome`: a clean stop, 0 errors, exactly the oracle's action, but the customer
  applied for the **wrong product** (`card_type` differed from the oracle). This is a
  recommendation-reasoning failure: the protocol was perfect.
- 005 `wrong_outcome`: a clean stop, but the learner called `transfer_to_human_agents`
  **without verifying the customer and without making the profile change** that the oracle
  also expects (the oracle does verification and the change as well as the transfer). It
  escalated work it could have done itself.
- 008 **passed**. It is the human-transfer task, one of the 3 graded on ACTION rather than DB.
- 021 050 059 060 087 had not started at handoff.

**First action in session 2:** check whether v2 finished:
- If `runs/tau3-v2/eval_result.json` exists, run
  `.venv\Scripts\python.exe -B tools/tau3_report.py runs/tau3-v2 --diff`.
- If it doesn't (the session-1 process may have died with that session), the report tool
  falls back to reading `harbor-jobs/`, and trials without `verifier/result.json` are
  incomplete. Re-run only the missing tasks into a new `--out` after asking me.

# Current artifacts (read all three before editing)

1. **`submissions/my-team/tau3/SKILL.md`** (about 16 KB). Sections:
   - §0 Every reply to the customer is a tool call (with a WRONG/RIGHT example)
   - §1 Conversation skeleton
   - §2 What is graded
   - §3 You always have a next action / searching is not resolving (at most 3 searches per
     question)
   - §4 Start/stop contract
   - §5 Budget ("about 100 calls, which is plenty"; this deliberately *removed* the rationing
     language, because v1 showed caution causing under-action)
   - §6 Error budget
   - §7 State-changing calls: unlock once, give only when the KB says so, refusals still record
     the denial
   - §8 Identity verification first (2 of 4: DOB, email, phone, address; log once, after the
     match, before any other recorded action; no log for KB-only questions)
   - §9 Escalation (ask first; transfer after 4 demands)
   - §10 `conversation_state.py`
   - §11 Fallback
2. **`submissions/my-team/tau3/scripts/conversation_state.py`** (Class B). It reads
   `/logs/agent/tau3_runtime_state.json` (verified readable from the agent container) and
   prints whether the conversation is open or closed, the error budget, the landed
   state-changing calls (agent's and customer's), whether verification is logged, and
   bookkeeping findings. It never recommends a specific tool call. It was checked against the
   real v1 states: on 076 it flags "nothing recorded yet"; on 001 it says "closed → call
   finish"; on 093 it says "not started". Usage in v2 so far is 0 (it is optional).
3. **`tools/tau3_report.py`** (Class A). It gives per-attempt PASS/FAIL, a bucket and a
   one-line reason. Buckets: `pass`, `replied_in_chat`, `agent_blocked`, `never_started`,
   `never_closed`, `too_many_errors`, `step_budget`, `unevaluated`, `wrong_outcome`,
   `infra_error`. `--diff` compares against the train oracle, reporting missing and extra calls
   **and argument-level mismatches** (it shows only the differing keys). It falls back to
   `harbor-jobs/` when `attempts.jsonl` is absent, taking the task name from the job folder.
   Report output is for our diagnosis only; nothing from it goes into the skill.

`check-skill` is clean: 2 files, 15,968 bytes, no `__pycache__`.

# Open problems, in priority order

1. **`replied_in_chat` on the opening turn (017, 2 runs out of 2).** Stating the rule, even with
   a WRONG/RIGHT example in §0, did not change it. Ideas to test, one at a time, on **017 alone**
   (it reproduces deterministically, so a single cheap attempt is a clean A/B):
   - Script the opening as literal tool calls: step 1 `start_conversation()`, step 2
     `send_message_to_user(message="...")`, and so on. Small models copy call templates more
     reliably than they follow abstract rules.
   - Put the core contract in the frontmatter `description`, which is the first thing injected.
   - Frame it as a runtime output contract: "the OpenHands chat has no reader; an assistant
     turn without a tool call is interpreted as task complete."
   - Check how frequent this is across all v2 tasks before over-fitting to 017.
2. **Wrong product recommendation (003).** This could be the largest bucket once the protocol
   issues are fixed (11 card tasks plus 9 account tasks). Before writing any rule, do **free
   analysis over the train oracles**: across the tasks where the oracle applies for a card or
   opens an account, what general criterion picks the oracle product given the customer's
   stated needs? For example, "the cheapest product that meets every stated requirement" or
   "the KB's eligibility tiers by income". Then write a *general* selection procedure: list every
   candidate in the category from the KB; check each against every stated requirement (fees,
   foreign-transaction fees, credit-limit range, rewards, income or eligibility); eliminate
   the failures; pick by the verified criterion; confirm with the customer. **No product
   names in the skill.**
3. **`agent_blocked` (093, 2 of 2; deterministic).** Hypothesis: the simulated customer's
   `request_human_agent_transfer` tool schema is rejected upstream (the error names
   `tools[1]`). That would make **10/54 train tasks (about 19%) unevaluable locally**. 087 in v2
   shares 093's user-tool combination, so it is the test of this hypothesis. It is not fixable by
   the skill, and if the organizers use the same simulator it is neutral to skill − placebo.
   Exclude these tasks when reading pass rates.
4. **Premature escalation (005).** The learner transferred to a human instead of first doing
   what it could do: verification and the requested profile change. Before touching §9, check
   the train oracles (free): in the tasks that contain `transfer_to_human_agents`, which other
   recorded actions come with it, and in what order? Then make §9 say "do everything within
   your capabilities first; transfer only for the part you cannot do", if the oracles support
   that.
5. **Unlock caution.** If more evidence shows that extra read-tool unlocks do not break the DB
   check, relax §7. Less caution means less under-action.
6. **Placebo.** It has never been run on tau3, so we do not know the net delta. Run it once on a
   fixed task set before any claim about score.

# Method (what worked; keep doing it)

- Measure before editing, and classify with `tools/tau3_report.py`, not by impression. Read the
  trajectory (`agent/trajectory.json`: the last agent step with no `tool_calls` is the chat
  failure) before deciding on a fix.
- **Validate every new rule against the 54 train oracles before shipping it.** In session 1
  this caught two wrong rules: "make no write when ineligible" (the oracle writes in 14/14) and
  "never leave a tool unlocked" (5/54).
- Change one thing at a time. Use single deterministic-repro tasks for quick A/B tests, and 12+
  tasks before trusting a pass rate (the CI threshold).
- Write for a small model: short, concrete, template-like. Rules must never push the learner
  into an extra write; tools may report state but must never prescribe a specific call.
- Run `check-skill`, and `find submissions/my-team/tau3 -type f`, before you finish.

Start by reading the files named above, then report v2's final taxonomy to me before changing
anything.

#!/usr/bin/env python3
"""Failure taxonomy for a tau3 eval run: which tasks failed, and in which way.

tau3 is pass/fail on the final database state, and a run can fail three very different
ways: the conversation never reached a valid stop (the evaluator then never runs at all),
the bookkeeping was off by one call, or the case was simply handled wrong. This separates
them into counted buckets so the biggest one is a number rather than an impression.

With --diff it also compares each attempt's tool calls against that task's oracle actions
to label missing / extra / argument-mismatched calls. That is a diagnosis aid for TRAIN
tasks only; oracle content must never be copied into a skill.

Several run directories are merged into one report (tools/batch_eval.py writes one per
chunk). Trials that an aborted eval never recorded in attempts.jsonl are still listed from
harbor-jobs/, marked "not recorded". Each row shows the learner tokens the attempt used,
because one `stbench eval` call shares a single learner token pool across its attempts.

    uv run python tools/tau3_report.py runs/tau3-v1
    uv run python tools/tau3_report.py runs/tau3-v1 --arm skill --diff
    uv run python tools/tau3_report.py runs/tau3-v3/b* --diff
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS = REPO_ROOT / "dataset" / "hackathon" / "tau3-bench" / "tasks"

GOOD_STOP = {"agent_stop", "user_stop"}
META_UNLOCK = "unlock_discoverable_agent_tool"
META_CALL_AGENT = "call_discoverable_agent_tool"
META_GIVE = "give_discoverable_user_tool"
META_CALL_USER = "call_discoverable_user_tool"
META = {META_UNLOCK, META_CALL_AGENT, META_GIVE, META_CALL_USER}
READ_PREFIXES = ("get_", "list_", "search_", "check_", "find_", "view_", "read_")


def inner_name(args: dict) -> str | None:
    for key, value in args.items():
        if isinstance(value, str) and ("tool" in key.lower() or key.lower() == "name"):
            return value
    for value in args.values():
        if isinstance(value, str):
            return value
    return None


def signature(name: str, args: dict) -> str:
    """A call identity that ignores ids and ordering: meta calls fold into their target."""
    if name in META:
        return f"{name}:{inner_name(args)}"
    return name


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def attempts_from_jsonl(run: Path) -> list[dict]:
    path = run / "attempts.jsonl"
    if not path.is_file() or path.stat().st_size == 0:
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    return out


def attempts_from_jobs(run: Path) -> list[dict]:
    """Fallback when attempts.jsonl was never written (the cp1252 crash in CLAUDE.md §7)."""
    out = []
    for trial in sorted((run / "harbor-jobs").glob("**/task__*")):
        if not trial.is_dir():
            continue
        result = read_json(trial / "verifier" / "result.json") or {}
        # The trial folder is a random id; the real task name lives in the job folder above it.
        found = re.search(r"tau3-bench__tau3-banking_knowledge-task-\d+", trial.parent.name)
        out.append({
            "task_name": found.group(0) if found else trial.name,
            "arm": "?",
            "score": result.get("reward"),
            "trial_dir": str(trial),
        })
    return out


def collect_attempts(run: Path) -> list[dict]:
    """attempts.jsonl rows, plus every harbor trial it never recorded.

    An eval that aborts (budget 402, retries exhausted) stops writing attempts.jsonl, but
    trials that were in flight often finished and were verified anyway - dropping them
    silently hides real outcomes.
    """
    rows = attempts_from_jsonl(run)
    seen = {str(Path(r["trial_dir"]).resolve()) for r in rows if r.get("trial_dir")}
    for extra in attempts_from_jobs(run):
        if str(Path(extra["trial_dir"]).resolve()) not in seen:
            extra["unrecorded"] = True
            rows.append(extra)
    return rows


def learner_tokens(trial: Path | None) -> int | None:
    agent = ((read_json(trial / "result.json") or {}).get("agent_result") or {}) if trial else {}
    if agent.get("n_input_tokens") is None:
        return None
    return int(agent.get("n_input_tokens") or 0) + int(agent.get("n_output_tokens") or 0)


def budget_cut(trial: Path | None) -> bool:
    """The learner gateway refused a call because this eval's shared token pool ran dry."""
    if trial is None:
        return False
    try:
        text = (trial / "agent" / "openhands_sdk.txt").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return "insufficient budget for request" in text or "budget exhausted" in text


def task_dir_for(task_name: str) -> Path | None:
    leaf = task_name.split("/")[-1]
    for candidate in (TASKS / leaf, *TASKS.glob(f"*{leaf.split('task__')[-1]}*")):
        if candidate.is_dir():
            return candidate
    return None


def expected_signatures(task_dir: Path) -> Counter | None:
    cfg = read_json(task_dir / "environment" / "runtime-server" / "task_config.json")
    if not cfg:
        return None
    actions = ((cfg.get("task") or {}).get("evaluation_criteria") or {}).get("actions") or []
    return Counter(signature(a.get("name") or "", a.get("arguments") or {}) for a in actions)


def actual_signatures(state: dict) -> tuple[Counter, int]:
    sigs: Counter = Counter()
    failed_ids = {
        str(m.get("id")) for m in state.get("messages") or []
        if m.get("role") == "tool" and m.get("error")
    }
    for msg in state.get("messages") or []:
        for call in msg.get("tool_calls") or []:
            if str(call.get("id")) in failed_ids:
                continue
            sigs[signature(str(call.get("name") or ""), dict(call.get("arguments") or {}))] += 1
    return sigs, len(failed_ids)


def payload(args: dict) -> dict:
    """The arguments that matter: a call routed through a meta tool nests them one level down."""
    inner = args.get("arguments")
    return inner if isinstance(inner, dict) else args


def arg_mismatches(task_dir: Path, state: dict) -> list[str]:
    """Calls present on both sides by name whose arguments differ.

    The name-level diff is blind to the commonest wrong_outcome: the right action with a
    wrong value (the wrong product chosen, the wrong account). Shows only the differing keys.
    """
    cfg = read_json(task_dir / "environment" / "runtime-server" / "task_config.json") or {}
    expected: dict[str, list[dict]] = {}
    for a in ((cfg.get("task") or {}).get("evaluation_criteria") or {}).get("actions") or []:
        expected.setdefault(signature(a.get("name") or "", a.get("arguments") or {}), []).append(
            a.get("arguments") or {})
    actual: dict[str, list[dict]] = {}
    for msg in state.get("messages") or []:
        for call in msg.get("tool_calls") or []:
            args = dict(call.get("arguments") or {})
            actual.setdefault(signature(str(call.get("name") or ""), args), []).append(args)
    out = []
    for sig in sorted(set(expected) & set(actual)):
        exp_set = {json.dumps(x, sort_keys=True) for x in expected[sig]}
        for got in actual[sig]:
            if json.dumps(got, sort_keys=True) in exp_set:
                continue
            g, r = payload(got), payload(expected[sig][0])
            diff = [f"{k}: got {g.get(k)!r} want {r.get(k)!r}"
                    for k in sorted(set(g) | set(r)) if g.get(k) != r.get(k)]
            if diff:
                out.append(f"{sig} [{'; '.join(diff)[:160]}]")
            break
    return out


def agent_log_faults(trial: Path | None) -> str | None:
    """Faults that stop the learner before it can act: these are not skill failures.

    Without this, an attempt whose simulated-user call was rejected upstream looks
    identical to one where the learner simply forgot to close the conversation.
    """
    if trial is None:
        return None
    log = trial / "agent" / "openhands_sdk.txt"
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    hits = [
        (text.count(needle), label) for needle, label in (
            ("Insufficient available balance", "upstream credit balance rejected a call"),
            ("insufficient budget for request", "this eval's learner token pool ran out (gateway 402)"),
            ("budget exhausted", "this eval's learner token pool ran out (gateway 402)"),
            ("Invalid value for 'tools", "upstream rejected a tool schema (simulated-user side)"),
            ("litellm.BadRequestError", "upstream BadRequestError"),
            ("Stuck pattern detected", "OpenHands stuck-detector aborted the agent"),
        ) if needle in text
    ]
    if not hits:
        return None
    count, label = max(hits)
    return f"{label} [{count}x]"


def last_agent_text(trial: Path | None) -> str | None:
    """The plain text of the learner's final step, if that step made no tool call.

    OpenHands ends the run on an assistant message without a tool call, so a reply written
    as chat instead of sent with send_message_to_user never reaches the customer and leaves
    the conversation open. That is a distinct, fixable failure - not "forgot to close".
    """
    if trial is None:
        return None
    try:
        steps = json.loads((trial / "agent" / "trajectory.json").read_text(encoding="utf-8"))["steps"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    agent_steps = [s for s in steps if s.get("source") == "agent"]
    if not agent_steps or agent_steps[-1].get("tool_calls"):
        return None
    return (agent_steps[-1].get("message") or "").strip()


def classify(result: dict | None, state: dict | None, score: float | None,
             trial: Path | None = None) -> tuple[str, str]:
    if score is not None and score >= 1.0:
        return "pass", "Passed."
    if state is None:
        status = (result or {}).get("status") or "no_state_file"
        return "infra_error", f"No runtime state log; verifier status {status}."

    # A learner that made no progress at all did not fail at the skill; find out why.
    if not (state.get("step_count") or 0) or not any(
        m.get("tool_calls") for m in state.get("messages") or []
    ):
        fault = agent_log_faults(trial)
        if fault:
            return "agent_blocked", f"Never got started: {fault}."

    reason = state.get("termination_reason")
    steps, max_steps = state.get("step_count"), state.get("max_steps")
    n_err, max_err = state.get("num_errors"), state.get("max_errors")

    if reason not in GOOD_STOP:
        if not state.get("start_tool_called"):
            return "never_started", "start_conversation was never called."
        if reason == "too_many_errors":
            return "too_many_errors", f"Burned the error budget ({n_err}/{max_err}); evaluator never ran."
        if reason == "max_steps":
            return "step_budget", f"Hit the runtime step cap ({steps}/{max_steps}); evaluator never ran."
        if reason is None:
            chat = last_agent_text(trial)
            if chat:
                return "replied_in_chat", (
                    "Final reply was written as plain text instead of send_message_to_user, "
                    f"which ended the run: {chat[:90]!r}"
                )
            return "never_closed", (
                f"Conversation left open after {steps} steps - end_conversation was never "
                "called, so the evaluator never ran."
            )
        return "bad_stop", f"Terminated as '{reason}', which the evaluator rejects."

    if not (result or {}).get("used_tau2_evaluator"):
        note = (result or {}).get("note") or ((result or {}).get("reward_info") or {}).get("info", {}).get("note")
        return "unevaluated", f"Stopped cleanly but the evaluator did not run: {str(note)[:140]}"

    basis = ",".join(((result or {}).get("reward_info") or {}).get("reward_basis") or []) or "DB"
    return "wrong_outcome", f"Ran to a clean stop but the {basis} check failed."


def expand_runs(raw: list[str]) -> list[Path]:
    """Run directories; globs are expanded here because PowerShell passes them through literally."""
    runs: list[Path] = []
    for item in raw:
        matches = sorted(Path().glob(item)) if any(ch in item for ch in "*?[") else [Path(item)]
        runs.extend(p for p in matches if p.is_dir() and p not in runs)
    if not runs:
        raise SystemExit(f"no run directories match {' '.join(raw)}")
    return runs


def report(runs: list[Path], arm: str | None, diff: bool, worst: int) -> int:
    attempts: list[dict] = []
    for run in runs:
        attempts.extend(collect_attempts(run))
    if not attempts:
        raise SystemExit(f"no attempts found under {', '.join(map(str, runs))} "
                         "(looked for attempts.jsonl and harbor-jobs/)")

    buckets: Counter = Counter()
    by_arm: dict[str, list[float]] = {}
    # agent_blocked attempts never reach the learner (an upstream schema rejection on the
    # simulated-user side), so they say nothing about the skill; show the rate without them.
    evaluable: dict[str, list[float]] = {}
    missing_agg: Counter = Counter()
    extra_agg: Counter = Counter()
    rows = []
    total_tokens = 0

    for att in sorted(attempts, key=lambda r: (str(r.get("task_name")), str(r.get("arm")))):
        if arm and att.get("arm") not in (arm, "?"):
            continue
        trial = Path(att["trial_dir"]) if att.get("trial_dir") else None
        result = read_json(trial / "verifier" / "result.json") if trial else None
        state = read_json(trial / "agent" / "tau3_runtime_state.json") if trial else None
        score = att.get("score")
        score = float(score) if isinstance(score, (int, float)) else None

        bucket, why = classify(result, state, score, trial)
        if att.get("unrecorded") and result is None:
            bucket, why = "aborted", "The eval aborted before this attempt was verified; rerun it."
        elif att.get("unrecorded"):
            why += " [not recorded in attempts.jsonl - the eval aborted around it]"
        if bucket != "agent_blocked" and budget_cut(trial):
            why += " [learner token pool ran out during this attempt]"
        tokens = learner_tokens(trial)
        total_tokens += tokens or 0
        buckets[bucket] += 1
        if bucket != "aborted":
            by_arm.setdefault(str(att.get("arm")), []).append(1.0 if bucket == "pass" else 0.0)
        if bucket not in ("aborted", "agent_blocked"):
            evaluable.setdefault(str(att.get("arm")), []).append(1.0 if bucket == "pass" else 0.0)

        detail = ""
        if diff and state is not None:
            task_dir = task_dir_for(str(att.get("task_name")))
            expected = expected_signatures(task_dir) if task_dir else None
            if expected is not None:
                actual, n_failed = actual_signatures(state)
                missing = expected - actual
                extra = Counter({k: v for k, v in (actual - expected).items()
                                 if not k.split(":")[0].startswith(READ_PREFIXES)})
                missing_agg.update(missing.keys())
                extra_agg.update(extra.keys())
                parts = []
                if missing:
                    parts.append("missing " + ", ".join(sorted(missing)[:4]))
                if extra:
                    parts.append("extra " + ", ".join(sorted(extra)[:4]))
                if n_failed:
                    parts.append(f"{n_failed} failed calls")
                wrong_args = arg_mismatches(task_dir, state)
                if wrong_args:
                    parts.append("wrong args " + ", ".join(wrong_args[:2]))
                detail = "; ".join(parts)

        short = str(att.get("task_name")).split("-")[-1]
        rows.append((bucket, short, str(att.get("arm")), score, why, detail, tokens))

    for bucket, short, a_arm, score, why, detail, tokens in rows:
        mark = "PASS" if bucket == "pass" else "FAIL"
        shown = f"{score:.1f}" if score is not None else " - "
        tok = f"{tokens / 1e6:.2f}M tok" if tokens is not None else "tok ?"
        print(f"{short:>5} {a_arm:<9} {mark} {shown}  [{bucket}]  {tok}\n    {why}")
        if detail:
            print(f"    diff: {detail}")
    counted = [t for *_, t in rows if t is not None]
    if counted:
        print(f"\nlearner tokens: {total_tokens / 1e6:.2f}M over {len(counted)} attempts "
              f"(mean {total_tokens / len(counted) / 1e6:.2f}M); one `stbench eval` call shares "
              "one pool (tau3: 4M), so size chunks from the mean")

    print("\n== pass rate by arm")
    for a_arm, vals in sorted(by_arm.items()):
        ev = evaluable.get(a_arm) or []
        ev_txt = f"   excluding agent_blocked {sum(ev) / len(ev):.3f} ({int(sum(ev))}/{len(ev)})" if ev else ""
        print(f"  {a_arm:<10} {sum(vals) / len(vals):.3f}  ({int(sum(vals))}/{len(vals)}){ev_txt}")
    if len(by_arm) > 1 and "placebo" in by_arm and "skill" in by_arm:
        p = sum(by_arm["placebo"]) / len(by_arm["placebo"])
        s = sum(by_arm["skill"]) / len(by_arm["skill"])
        print(f"  net delta (skill - placebo): {s - p:+.3f}   [no CI below 12 tasks]")

    print("\n== failure buckets (biggest first)")
    for bucket, count in buckets.most_common():
        print(f"  {bucket:<18} {count}")

    if diff and (missing_agg or extra_agg):
        print("\n== most often MISSING vs oracle (train diagnosis only)")
        for sig, count in missing_agg.most_common(worst):
            print(f"  {count:3d}  {sig}")
        print("\n== most often EXTRA vs oracle (train diagnosis only)")
        for sig, count in extra_agg.most_common(worst):
            print(f"  {count:3d}  {sig}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="+", help="run directories or globs, e.g. runs/tau3-v1 runs/tau3-v3/b*")
    ap.add_argument("--arm", default=None, help="only this arm (baseline/placebo/skill)")
    ap.add_argument("--diff", action="store_true",
                    help="diff each attempt against the task's oracle actions (TRAIN only)")
    ap.add_argument("--worst", type=int, default=10, help="how many aggregate rows to list")
    a = ap.parse_args()
    return report(expand_runs(a.runs), a.arm, a.diff, a.worst)


if __name__ == "__main__":
    sys.exit(main())

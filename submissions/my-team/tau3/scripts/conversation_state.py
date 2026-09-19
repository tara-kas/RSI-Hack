#!/usr/bin/env python3
"""Report what has already happened in this conversation, so you know whether to keep going.

Reads the runtime state log the tau3 MCP server writes after every step and reports: whether
the conversation is open or closed, the error budget, which state-changing calls have landed
(yours and the customer's), whether verification was logged, and bookkeeping mistakes - a tool
unlocked but never called, a user tool given but never used, a write repeated.

It never tells you to make a specific tool call. The only things it ever recommends are to
continue the procedure, to tell the customer the outcome, or to close.

    python3 conversation_state.py
    python3 conversation_state.py --state /logs/agent/tau3_runtime_state.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

DEFAULT_STATE = Path("/logs/agent/tau3_runtime_state.json")

# Calls that only look things up. Everything else counts as state-changing: a spurious
# "landed" line costs nothing, a missed duplicate write costs the task.
READ_PREFIXES = ("get_", "list_", "search_", "check_", "find_", "view_", "read_")
READ_EXACT = {"kb_search", "get_current_time", "get_assistant_tool_schemas",
              "get_runtime_status", "start_conversation", "send_message_to_user"}
UNLOCK = "unlock_discoverable_agent_tool"
CALL_AGENT = "call_discoverable_agent_tool"
GIVE = "give_discoverable_user_tool"
CALL_USER = "call_discoverable_user_tool"
META = {UNLOCK, CALL_AGENT, GIVE, CALL_USER}
VERIFY_MARK = "verification"


def is_read(name: str) -> bool:
    low = name.lower()
    return low in READ_EXACT or low.startswith(READ_PREFIXES)


def inner_name(args: dict) -> str | None:
    """The discoverable tool a meta call refers to, whatever the argument is named."""
    for key, value in args.items():
        if isinstance(value, str) and ("tool" in key.lower() or key.lower() == "name"):
            return value
    for value in args.values():
        if isinstance(value, str):
            return value
    return None


def collect_calls(messages: list[dict]) -> list[dict]:
    calls: list[dict] = []
    errors_by_id: dict[str, str] = {}
    for msg in messages:
        if msg.get("role") == "tool" and msg.get("error"):
            errors_by_id[str(msg.get("id"))] = str(msg.get("content") or "")[:160]
        for call in msg.get("tool_calls") or []:
            by = str(call.get("requestor") or msg.get("role") or "assistant")
            calls.append({
                "id": str(call.get("id")),
                "name": str(call.get("name") or ""),
                "args": dict(call.get("arguments") or {}),
                "by": "customer" if by == "user" else "you",
            })
    for call in calls:
        call["error"] = errors_by_id.get(call["id"])
    return calls


def landed_writes(calls: list[dict]) -> Counter:
    """Successful state-changing calls, keyed by (who, label, exact arguments)."""
    writes: Counter = Counter()
    for call in calls:
        if call["error"]:
            continue
        name = call["name"]
        target = inner_name(call["args"]) if name in META else name
        # An unlock or a hand-over is itself recorded even when its target only reads;
        # a call routed through a meta tool counts only if the target writes.
        if name in (CALL_AGENT, CALL_USER) and target and is_read(target):
            continue
        if name not in META and is_read(name):
            continue
        label = f"{name}({target})" if name in META and target else name
        writes[(call["by"], label, json.dumps(call["args"], sort_keys=True))] += 1
    return writes


def report(state_path: Path) -> int:
    if not state_path.is_file():
        print("NO STATE FILE at", state_path)
        print("This check is unavailable here. Ignore it and carry on with the procedure.")
        return 0
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"STATE FILE UNREADABLE ({exc}). Ignore this check and carry on.")
        return 0

    reason = state.get("termination_reason")
    if reason:
        print(f"CONVERSATION CLOSED ({reason}).")
        print("NEXT: make no more conversation or domain calls. Call finish.")
        return 0
    if not state.get("bootstrap_complete"):
        print("CONVERSATION NOT STARTED.")
        print("NEXT: call start_conversation.")
        return 1

    calls = collect_calls(state.get("messages") or [])
    n_err = int(state.get("num_errors") or 0)
    max_err = int(state.get("max_errors") or 10)
    print(f"CONVERSATION OPEN   errors {n_err}/{max_err}   tool calls so far {len(calls)}")

    writes = landed_writes(calls)
    if writes:
        print("state-changing calls that landed:")
        for (who, label, _), count in sorted(writes.items()):
            print(f"  {count}x {label}   [{who}]")
    else:
        print("state-changing calls that landed: none")
    verified = any(VERIFY_MARK in label.lower() for (_, label, _) in writes)
    print(f"verification logged: {'yes' if verified else 'no'}")

    findings: list[str] = []
    if n_err >= max_err - 2:
        findings.append(f"{n_err} of {max_err} tool errors used - the run ends at zero on "
                        f"{max_err}. Make no more risky calls; finish the case and close.")

    def targets(meta: str) -> set[str]:
        return {t for c in calls if c["name"] == meta and not c["error"]
                for t in [inner_name(c["args"])] if t}

    stranded = sorted(targets(UNLOCK) - targets(CALL_AGENT))
    if stranded:
        findings.append("Unlocked but never called: " + ", ".join(stranded) + ". The unlock is "
                        "already recorded - do not call it now just to compensate.")
    unused = sorted(targets(GIVE) - targets(CALL_USER))
    if unused:
        findings.append("Given to the customer but not used yet: " + ", ".join(unused) + ". "
                        "Make sure they know the exact tool name and argument values, and wait "
                        "for them to use it before closing.")
    repeated = sorted(f"{label} ({c}x)" for (_, label, _), c in writes.items() if c > 1)
    if repeated:
        findings.append("Repeated with identical arguments: " + ", ".join(repeated) + ". Each "
                        "repeat is a separate record - do not repeat it again.")
    if not writes:
        findings.append("Nothing has been recorded yet. Reading the knowledge base changes "
                        "nothing. Before closing, either take the action the knowledge base "
                        "authorises (or have the customer take it with a tool you gave them), "
                        "or tell the customer it is not possible.")

    failed = [c for c in calls if c["error"]]
    if failed:
        print(f"failed calls: {len(failed)} (last: {failed[-1]['name']} - {failed[-1]['error']})")

    print()
    for i, finding in enumerate(findings, 1):
        print(f"ATTENTION {i}: {finding}")
    if findings:
        print()
    print("NEXT: if the request is handled or refused and the customer has been told, call")
    print("end_conversation. Otherwise continue with the next step of the procedure. Do not")
    print("add a tool call only to change what this report says.")
    return 1 if findings else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default=str(DEFAULT_STATE),
                    help="runtime state log written by the tau3 MCP server")
    a = ap.parse_args()
    return report(Path(a.state))


if __name__ == "__main__":
    sys.exit(main())

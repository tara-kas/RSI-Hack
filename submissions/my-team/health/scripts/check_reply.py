#!/usr/bin/env python3
"""Structural check of a health reply file. Offline, stdlib only, no network.

Checks the SHAPE the reply needs for its mode (emergency / answer / ask / document /
other): file present, urgent action or warning signs near the top, if/then guidance, the
right number of questions, missing-data markers, contraindications next to any named
medicine, no links or meta-talk. Mode `other` checks only the basics. Prints one short
fix per problem, with the file's line count so a fix can be inserted in place.

    python3 check_reply.py --mode ask
    python3 check_reply.py --mode emergency /logs/agent/response.txt

A PASS means the structure is right, not that the medicine is right.
Exit 0 = PASS, 1 = FIX needed.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

URGENT = re.compile(r"\b(911|999|112|emergency|ambulance|ER\b|A&E|call .{0,20}(now|immediately)|"
                    r"go to .{0,30}(now|immediately|right away)|urgent care|immediately)", re.I)
SEEK_CARE = re.compile(r"\b(see|seek|contact|call|visit|go to|get checked|be seen|evaluat|examin)", re.I)
MISSING = re.compile(r"\[not provided|not provided\]|missing|not available|needed to complete|"
                     r"cannot be (completed|written)|preliminary|draft", re.I)
CAUTION = re.compile(r"pregnan|allerg|kidney|liver|interact|not (take|use|suitable)|avoid|"
                     r"pharmacist|contraindicat|should not|side effect", re.I)
VAGUE_Q = re.compile(r"any other (symptoms|concerns|questions)|anything else", re.I)
META = re.compile(r"response\.txt|I('ve| have) written|this file|as an ai", re.I)
# Common drug classes/names; a hit means a medicine was named and needs a caution.
DRUG = re.compile(r"\b(\w+(cillin|mycin|cycline|floxacin|pril|sartan|olol|statin|prazole|azole|"
                  r"triptan|oxetine|pramine|zepam|azepam|dronate|gliptin|glitazone|mab|vir)|"
                  r"ibuprofen|acetaminophen|paracetamol|aspirin|naproxen|prednis\w+|steroid\w*|"
                  r"metformin|insulin|warfarin|heparin|antibiotic\w*|antidepressant\w*|ssri\w*|"
                  r"opioid\w*|codeine|tramadol|morphine|antihistamine\w*|diphenhydramine|"
                  r"melatonin|levothyroxine|furosemide|amlodipine)\b", re.I)


def questions(text: str) -> list[str]:
    return [s.strip() for s in re.findall(r"[^?\n]{8,}\?", text)]


def check(text: str, mode: str) -> list[str]:
    fixes: list[str] = []
    n_lines = text.count("\n") + 1
    head = text[:300]
    qs = questions(text)

    # Only catch a genuinely empty file: a code or one-line answer can be correct.
    if len(text.strip()) < 20:
        return ["The reply is empty: write the complete reply into the file."]
    if META.search(text):
        fixes.append("Remove talk about files or yourself; the file must contain only the reply to the person.")
    if re.search(r"https?://|www\.|####", text):
        fixes.append("Remove links and '####' lines; they are not part of a reply.")

    if mode == "other":
        return fixes
    if mode == "emergency":
        if not URGENT.search(head):
            fixes.append("The first line must tell them to call emergency services or go to the "
                         "emergency department now: insert it at insert_line 0.")
        if len(qs) > 3:
            fixes.append(f"{len(qs)} questions is too many in an emergency: keep at most 2 that change what they do now.")
    elif mode in ("answer", "ask"):
        if mode == "answer" and len(qs) > 3:
            fixes.append(f"{len(qs)} questions: this question can be answered, so explain fully and keep only 0-2 questions.")
        if mode == "ask" and len(qs) < 2:
            fixes.append(f"Only {len(qs)} question(s): add 2-4 specific questions at the end (insert_line {n_lines}), "
                         "highest priority first: urgency signs, then age/pregnancy/conditions/medicines/allergies, then cause.")
        if len(re.findall(r"(^|[\s(*-])if\b", text, re.I)) < 2:
            fixes.append("Add 2-4 'If ..., then ...' lines covering the main possibilities, including when to see a clinician.")
        if not URGENT.search(text[: max(600, len(text) // 3)]):
            fixes.append("Add a short 'Get urgent care now if:' list of warning signs near the top (after the opening sentence).")
    elif mode == "document":
        # Short outputs (a code, a one-line summary) have no sections to mark; demanding
        # markers there made the learner rewrite correct answers.
        no_gap_statement = not re.search(r"information (provided|given) is (complete|sufficient)", text, re.I)
        if ((n_lines >= 15 and not MISSING.search(text))
                or (n_lines >= 40 and "[not provided" not in text.lower() and no_gap_statement)):
            fixes.append("Mark every section the conversation gave no facts for as [not provided] (or state the given "
                         "information is complete). Delete any history, findings or results that were not given.")

    if mode != "document" and any(VAGUE_Q.search(q) for q in qs):
        fixes.append("Replace vague questions like 'any other symptoms?' with specific named signs.")
    if mode in ("answer", "ask", "emergency") and not SEEK_CARE.search(text):
        fixes.append("Add when to see a clinician: specific warning signs and a time limit.")
    drugs = sorted({m.group(0).lower() for m in DRUG.finditer(text)})
    if drugs and not CAUTION.search(text):
        fixes.append(f"You name medicine ({', '.join(drugs[:3])}) but give no cautions: add who should "
                     "not take it (pregnancy, allergy, kidney/liver, interactions) and to confirm with a clinician or pharmacist.")
    if mode != "document" and len(text) > 6000:
        fixes.append(f"Reply is {len(text)} characters: cut repetition and any closing summary.")
    return fixes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", default="/logs/agent/response.txt")
    ap.add_argument("--mode", required=True, choices=["emergency", "answer", "ask", "document", "other"])
    a = ap.parse_args()
    p = Path(a.path)
    if not p.is_file():
        print(f"FIX: {p} does not exist. Create it now with file_editor create; chat text is not graded.")
        return 1
    text = p.read_text(encoding="utf-8", errors="replace")
    fixes = check(text, a.mode)
    n_lines = text.count("\n") + 1
    if not fixes:
        print(f"PASS ({a.mode}, {n_lines} lines, {len(questions(text))} questions). Structure OK; finish now.")
        return 0
    print(f"FIX ({a.mode}, {n_lines} lines). Apply ALL fixes in ONE file_editor edit (insert or str_replace), then finish:")
    for i, f in enumerate(fixes, 1):
        print(f"{i}. {f}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

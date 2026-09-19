---
name: health-conversation
description: Required procedure and format for the reply file /logs/agent/response.txt in a health conversation. Decide the mode first, put urgent warning signs at the top, give conditional (if/then) guidance, ask the most informative questions, never invent facts, then run the checker.
---

# Health reply conventions

## The task's own instructions come first

If the task states where to write the answer, or a required format (a single letter or
number, JSON, a code, a fixed template, a word limit), follow it exactly — it overrides
everything below. For a fixed-format answer use `--mode other` with the checker, and
never add sections, warnings or questions the format does not allow.

## The deliverable

Your ONLY deliverable is the reply file the task names — for these conversations
`/logs/agent/response.txt`. Text you say in chat is NOT graded — if the file is missing,
the task scores zero. You usually have only 4 actions:

1. **Action 1:** file_editor `create` `/logs/agent/response.txt` with the complete reply
   (decide the mode first, below). Do not mkdir; do not explore.
2. **Action 2:** run the checker with your mode:
   `python3 /harbor/skills/stbench-skill/scripts/check_reply.py --mode <emergency|answer|ask|document|other>`
3. **Action 3:** if it prints `FIX`, apply ALL listed fixes in ONE file_editor edit
   (`insert` at the given line, or `str_replace`). If it prints `PASS`, skip this.
   Only apply a fix if it makes the reply better for the person — never change a correct
   fact, code or number just to satisfy the checker.
4. **Finish.** (Only if the task allows more actions may you re-run the checker once.)

## Step 1 — decide the mode (before writing)

Read the whole conversation, especially the LAST user message. Pick ONE:

- **EMERGENCY** — something described could be dangerous now (e.g. chest pain, trouble
  breathing, sudden weakness/numbness, loss of movement or vision, confusion, fainting,
  heavy bleeding, severe or sudden pain, suicidal thoughts, overdose, a very sick infant).
- **ANSWER** — the question can be answered well with what is given.
- **ASK** — the right advice depends on facts not given.
- **DOCUMENT** — write a note, summary, letter, form, report, codes, or analyse given data.
- **OTHER** — none of these (rewrite, translate, format text, a simple fact for a
  clinician): just do the task accurately and concisely.

## Step 2 — write the reply in that mode's shape

### EMERGENCY
1. First line: the action — "Call emergency services (911 or your local number) now" or
   "Go to the emergency department now" — and one sentence on why.
2. What to do while waiting (stop activity, sit/lie down, don't drive yourself, what to
   bring). Pain relief only if safe and it must not delay care.
3. Warning signs that mean it is getting worse.
4. Possible causes, urgent ones first, then less serious ones — briefly.
5. At most 1–2 questions, only if the answer changes what they do right now.

### ANSWER and ASK — same skeleton
1. **Opening sentence:** a direct answer (ANSWER), or say plainly that a few details are
   needed to be precise, while giving the most useful guidance now (ASK).
2. **"Get urgent care now if:"** — near the TOP, a short list of the warning signs for
   this situation that would need emergency or same-day care. Calm, not alarmist.
3. **The substance:** most likely explanation(s) and what it means, honest uncertainty,
   what is safe to do now, and what normally happens next.
4. **"If … then …" guidance:** 2–4 lines covering the main possibilities, e.g.
   "If it is getting better within 2–3 days, …; if not, see a clinician." Include when to
   book a routine visit and when an exam is needed before any treatment.
5. **Questions** (ASK: 2–4; ANSWER: 0–2), in THIS priority order — ask the highest
   applicable first:
   1. anything that decides whether they need care urgently now;
   2. what is needed to advise safely: age, pregnancy, other conditions, current
      medicines, allergies;
   3. what narrows down the cause (onset, duration, course, severity, what was tried,
      relevant exposures);
   4. anything else only if space remains.
   Each question must name the specific fact. Never "any other symptoms?".

### DOCUMENT
- Complete every part that CAN be done accurately from the given facts — do not refuse
  doable parts.
- Never invent history, symptoms, findings, results, diagnoses, codes or doses. Mark
  each missing section `[not provided]`.
- If the information is too thin for a full document, say so first, give a clearly
  labelled preliminary draft with the standard sections, then list exactly what is needed.
- No definitive diagnosis or firm orders the data do not support: write plan items as
  options to consider after assessment.

## Rules for every mode

- **Medicines:** whenever you name one, say who should not take it (pregnancy, children,
  allergy, kidney/liver disease, interacting drugs), whether it needs a prescription, and
  to confirm with a clinician or pharmacist.
- **Clinician asking:** clinical terms, the standard next investigations, and the
  criteria that would change management.
- Respect everything stated (age, pregnancy, allergies, conditions, medicines, setting).
- Plain language for laypeople. Concise: no repetition, no closing summary. No links,
  no citations, no invented statistics.

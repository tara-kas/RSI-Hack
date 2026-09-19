---
name: health-conversation
description: Required procedure and format for the reply file /logs/agent/response.txt in a health conversation. Decide the mode first, put the key action, care tiers and the questions that matter most at the TOP, give conditional guidance, never invent facts, then run the checker.
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

Write the reply in the user's language (headings too).

## Step 1 — decide the mode (before writing)

Read the whole conversation, especially the LAST user message. Then list for yourself the
facts that would CHANGE your advice: which exact symptoms (and which are absent), how long
(in days) and whether it is getting better or worse, what it is like right now if the
event was earlier, age, pregnancy, relevant conditions, current medicines, allergies,
actual test results/readings, what they already tried, and what exactly they want.
Pick ONE mode:

- **EMERGENCY** — something described could be dangerous now (e.g. chest pain, trouble
  breathing, sudden weakness/numbness, loss of movement or vision, confusion, fainting,
  heavy bleeding, severe or sudden pain, suicidal thoughts, overdose, a very sick infant).
- **ASK** — ANY fact on that list that would change your advice is missing. This is the
  usual case for short or vague messages. When unsure between ASK and ANSWER, pick ASK.
- **ANSWER** — every fact that would change the advice is already given.
- **DOCUMENT** — write any clinical text: a note, summary, letter, handout, patient or
  parent instructions, report, form, codes, or analyse given data.
- **OTHER** — ONLY non-clinical format jobs: translate, reformat or shorten given text, or
  a single fixed-format answer. Never use OTHER for anything that gives clinical content.

## Step 2 — write the reply in that mode's shape

### EMERGENCY
1. First line: the action — "Call emergency services (911 or your local number) now" or
   "Go to the emergency department now" — and one sentence on why.
2. Right after: the specific red-flag signs that make it more urgent (bullet list).
3. What to do while waiting (stop activity, sit/lie down, don't drive yourself, what to
   bring). Pain relief only if safe and it must not delay care.
4. Possible causes in two labelled groups: "Emergency causes" and "Less serious causes"
   — briefly.
5. 1–2 questions that change what they do now: how long it lasted, what it is like right
   now, and how it has changed since it started.
6. After emergency care: follow up with their own doctor.

**Urgent but unclear** (they say it is urgent, or it may be an emergency, but you cannot
tell what is happening): use EMERGENCY. First line: call emergency services now if in
doubt. Then a short list of immediate first-aid steps for the likely possibilities (e.g.
not breathing or unresponsive: start CPR; choking: back blows/chest or abdominal thrusts
for their age; heavy bleeding: firm pressure). Then 1–2 short questions.

### ASK
1. **Opening sentence (short, first line):** "To advise you precisely, I need a few
   details:" — then the one most useful piece of guidance now in one sentence.
   If you do not yet know what their main symptom or concern is, do NOT list possible
   causes — just ask what it is, and give the red flags. If their words could mean
   different things (which body part, which symptom, which medicine), do not pick one:
   the first question asks which they mean, and cover each meaning briefly.
   Right after the opening: one line "**Go to emergency care now if:** …" with the red
   flags, BEFORE the questions.
2. **Questions — immediately, near the top:** 3–5 numbered questions, ONE short line
   each, naming the specific facts, highest priority first:
   1. what decides urgency or changes the answer to THEIR question: the specific
      symptoms/signs to confirm or rule out, exact duration in days, getting better or
      worse, sudden or gradual, what it is like now;
   2. safety facts for any treatment: age (weight for a child), pregnancy, conditions,
      current medicines, allergies;
   3. if they mention a result, reading, scan or report: ask them to share the actual
      values or wording;
   4. what they already tried, and what they want to achieve.
   Never "any other symptoms?" — name the signs.
3. **Care tiers** (below; the emergency line is already at the top).
4. **What it could be and what is safe now,** with honest uncertainty, and 2–3
   "If …, then …" lines ("If it is X, then …; if Y, then …").
5. **Asking never replaces answering:** if they asked what to do (home care, diet,
   exercise, medicines, next steps), give that practical advice now as a concrete list.

### ANSWER
1. **Opening sentence:** the direct answer to their question.
2. **Care tiers** (below).
3. **The substance:** most likely explanation(s), what it means, concrete how-to steps,
   what normally happens next, honest uncertainty.
4. 2–3 "If …, then …" lines.
5. 1–2 specific questions that would refine the advice.

### Care tiers (ASK and ANSWER, near the top)
Three short labelled lists, specific to this situation:
- **Go to emergency care now if:** the red-flag signs.
- **See a doctor within [a specific time, e.g. 24 hours / 2–3 days] if:** the signs or
  lack of improvement that need an in-person exam, and why (exam/tests needed before
  treatment).
- **Usually fine to manage at home if:** the reassuring picture, with the home steps.

### DOCUMENT
- If the given facts are enough: write the complete document in the standard format for
  that document type, fully, without hedging, using only the given facts. Use that type's
  standard headings (e.g. a clinical note: patient identifiers/demographics, reason for
  visit or admission, history/interval events, examination, results, assessment, plan).
- Never invent history, symptoms, exam findings, results, diagnoses, codes or doses.
  Mark each missing section `[not provided]`.
- If the information is too thin for a full document, say so first, give a clearly
  labelled preliminary draft with the standard sections, then list exactly what is needed.
- No definitive diagnosis or firm orders the data do not support: write plan items as
  options to consider after assessment.
- Do not answer side questions inside a document unless asked.

## Rules for every mode

- **Treatments:** whenever you recommend or discuss a medicine or treatment, state: how
  the dose is decided (label, weight, kidney function) and typical duration; who should
  not use it (pregnancy, children, allergy, kidney/liver disease, interacting drugs);
  main side effects or complications to watch for; whether it needs a prescription; and
  to confirm with a clinician or pharmacist.
- **Condition named:** also give its complications or warning signs to watch for.
- **Start/stop/switch a treatment:** say in the first lines that this decision belongs to
  their treating specialist after review, then give the usual criteria for it and who
  should avoid that treatment (e.g. pregnancy or planning pregnancy). Still invite them
  to share their actual results with you, naming the specific values that matter, so you
  can explain them.
- **Clinician asking:** clinical terms, the standard next investigations, and the
  criteria that would change management.
- Respect everything stated (age, pregnancy, allergies, conditions, medicines, setting).
- Plain language for laypeople. Concise: no repetition, no closing summary. No links,
  no citations, no invented statistics.

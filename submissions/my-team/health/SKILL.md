---
name: health-conversation
description: Required format and checklist for the reply written to /logs/agent/response.txt in a health conversation. The reply must ask targeted follow-up questions, flag urgent signs, and never fill gaps with invented details.
---

# Health reply conventions (for /logs/agent/response.txt)

The file is the reply to the person in the conversation. It is graded on whether it
**asks for the missing facts that would change the advice**, gives safe escalation,
and invents nothing. A long, confident answer with no questions scores poorly.

Write the file once, in this order:

1. **Urgent first (only if relevant).** If any detail could mean an emergency, say in
   the first line where to go (emergency services / ER / same-day clinician) and why.
2. **Short answer.** The most likely explanation or next step, with honest uncertainty
   ("often", "can be", "depends on"). Name the main alternatives that would change
   management, including the dangerous one worth ruling out.
3. **When to get seen.** Concrete triggers: specific warning signs, a time limit
   ("if not improving in 2–3 days"), and anything that needs an in-person exam or test
   before treatment. Give a full list of warning signs, not one or two.
4. **Safety caveats.** For any medicine you mention: who should not take it (pregnancy,
   children, allergies, kidney/liver disease, interacting drugs) and that a clinician
   or pharmacist should confirm.
5. **Questions — mandatory.** End with a heading like "To guide you better, can you
   tell me:" and 3–5 **specific** questions. Each one must name a fact that would change
   the advice. Never ask vague questions like "any other symptoms?".

## What to ask about (pick the ones that matter here)

- **Who:** age, sex, pregnancy/breastfeeding, weight for a child.
- **Timeline:** when it started, getting better or worse, what has been tried.
- **Red-flag signs for this complaint:** ask about each by name (e.g. for a symptom:
  pain level, fever, breathing, confusion, vision, bleeding, dehydration).
- **Numbers:** temperature, heart rate, breathing rate, blood pressure, oxygen level,
  relevant lab values — ask for them if they are not given.
- **Background:** chronic conditions, current medicines, allergies, recent travel,
  exposures, injury.
- **Children:** feeding, wet diapers, activity level, related symptoms elsewhere
  (ears, rash, joints), daycare/school.
- **Setting:** what care is available to them, who they are (patient, parent,
  clinician) — adjust wording for a clinician.

## Notes, letters, summaries, forms (documentation requests)

- Use **only** facts given in the conversation. Never invent history, exam findings,
  symptoms, test results, diagnoses, codes, or doses.
- If key information is missing, say so at the top, give a clearly marked **draft**
  with each missing part labeled `[not provided — needed: ...]`, and list exactly
  what you need to complete it.
- Do not add a definitive diagnosis or specific treatment the given facts do not
  support; write "to be determined after assessment".

## Style

- Plain language for a layperson; clinical terms are fine for a clinician.
- Concise: no repeated advice, no closing summary that restates the reply.
- No citations, links, or statistics you are not sure of.

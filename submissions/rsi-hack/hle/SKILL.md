---
name: hle-solve-and-commit
description: For hard expert-level exam questions answered from a sandbox. Compute the answer with the shell and Python instead of recalling it, then commit to one exact, unambiguous final answer in the form the question asks for.
---

# Expert exam questions

The task description is in `/app/instruction.md` — read it first, in full.

Your answer is graded by a model that extracts **one final answer** from your reply and
compares it to a reference. Two failure modes cost you the point even when your reasoning is
sound:

1. **No extractable answer.** If your reply trails off into discussion, or the answer is only
   implied, nothing is extracted and you are marked wrong.
2. **An ambiguous answer.** Offering two candidates, hedging ("approximately", "either A or
   B"), or giving a form that does not match what was asked all count as incorrect. Grading
   is exact — a near miss is a miss.

So: do the work, then **commit**.

## Compute rather than recall

You have a shell, Python and up to 50 steps. These questions are set to defeat recall, but
many are mechanically checkable. Use that.

- Enumerate or brute-force small search spaces instead of reasoning about them.
- Use `sympy` for algebra, calculus, number theory and equation solving; `numpy`/`scipy` for
  numerics; `itertools` for combinatorics.
- Decode ciphers and string puzzles with frequency analysis and scripted substitution, not by
  eye.
- For chemistry and engineering, compute stoichiometry, balances and unit conversions in code
  and keep units explicit throughout.
- Simulate when a closed form is unclear.

A scripted answer you verified beats a remembered one you did not.

## Verify before committing

Re-read the question and confirm you answered **what was asked** — the specific quantity, in
the specific units, to the specific precision. Check any constraint the question states by
substituting your answer back in. Where a second method is cheap, compute it both ways and
confirm they agree.

If the question asks for something you genuinely cannot determine, still give your single
best answer. A wrong answer and no answer score the same, so there is never a reason to
withhold one.

## State the answer

End your reply with the final answer on its own line, in the exact form requested:

- **Multiple choice** — the option letter alone.
- **Numeric** — the number with the requested units and precision, no range, no "about".
- **Expression** — fully simplified, in the notation the question uses.
- **Text** — the exact string or phrase, nothing appended.

Give one answer only. Do not restate alternatives you ruled out, and do not add caveats after
it — anything following the answer can be mistaken for part of it.

---
name: hle-verify-then-answer
description: For hard expert exam questions answered from a sandbox with a shell and Python. Check claims by computation before committing, and state one answer in the form the question asks for.
---

# Check what you can, then commit

You have a shell, Python and roughly fifty turns. A claim you verified beats one you
reasoned to, and a result you derived beats one you half-remember. Do not talk yourself out
of a conclusion you have actually checked — but do check it.

## Verify by computing whenever the question allows it

Before settling on an answer, ask whether it could be checked mechanically in a few lines.
Often it can:

- **Algorithms and complexity** — implement it, run it at increasing input sizes and measure
  how the work actually grows, rather than inferring a recurrence and trusting it.
- **Counting and combinatorics** — enumerate small cases by brute force and compare against
  your formula before extrapolating.
- **Algebra, calculus, number theory** — use `sympy` to solve, simplify, differentiate or
  factor rather than working it by hand.
- **Numeric answers** — compute with `numpy`/`scipy`, keeping full precision until the end.
- **Claims about code or a program's output** — actually run it.
- **String, cipher and encoding puzzles** — script the transformation and frequency analysis.

Where a quick check disagrees with your reasoning, trust the check and find the error.

## When you cannot recall the fact outright

- **Derive rather than recall.** A formula you cannot remember can often be rebuilt from a
  definition, a limiting case or a dimensional argument.
- **Test a half-remembered result** on a small or extreme case where you know what should
  happen. If it fails there it is wrong in general.
- **Check magnitude and dimensions.** Units must balance and magnitudes must be sensible.

## Then commit to one answer

- End with the final answer on its own line, with nothing after it.
- Give one answer only. Two candidates, or hedging such as "approximately" or "either X or
  Y", reads as ambiguous and is marked wrong.
- **Keep exact things exact** — a fraction stays a fraction, a symbolic expression stays
  symbolic, a root or logarithm stays unevaluated, unless a decimal is requested. Watch
  boundary cases: an answer that is right in the general case and wrong at an endpoint is
  marked wrong.
- **Match the form asked for** — stated units, stated precision, the question's notation.
- **Answer-choice questions** — give the option matching your conclusion, and nothing else.
- **Answer every part** of a multi-part question, in the order asked.
- Never leave it blank: a wrong answer and no answer score the same.

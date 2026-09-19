---
name: bank-support-conversation
description: Tool-call contract for a Rho-Bank customer conversation run through the tau3-runtime MCP tools. The customer receives ONLY what you pass to send_message_to_user - a turn you end without a tool call is read as "task finished" and scores zero. Also the opening script, identity verification, product recommendation, transfer and closing rules that decide the graded database state.
---

# Rho-Bank conversation: required tool-call contract

## 0. Nobody reads your chat - every turn is exactly one tool call

There are two "users" here. The **chat user** gave you this task and is not reading - there is
no reply to them until `finish`. The **customer** - called "the user" in the tau3 tools - is
not in this chat. They exist only inside tool results, and they receive only the text you pass
as `send_message_to_user(message=...)`. The runtime reads any turn of yours without a tool call
as "task finished": the customer never sees the text, the conversation stays open, and the run
scores zero. This happens most often on the very first reply, when the customer asks a question
and the natural move is to answer it in chat.

Whatever you want to say - greeting, question, identity request, answer, refusal, goodbye -
is the `message` argument:

```
WRONG - ends the run, scores zero:
    (plain text)  I'd be happy to help. Could you give me your date of birth and email?
RIGHT:
    send_message_to_user(message="I'd be happy to help. Could you give me your date of birth and email?")
```

## 1. Opening script - follow it exactly

```
call 1:  start_conversation()                     -> returns the customer's first message
call 2:  KB_search(query="<their request in a few words>")
call 3:  send_message_to_user(message="<your reply - usually a question or the identity request>")
then:    one tool call per turn: KB_search, a lookup, an action, or send_message_to_user
end:     the closing script in section 9, then finish
```

Call 2 is always a search, even when you already know you must verify identity first: searches
are free, are not recorded, and tell you what to ask. Call 3 is always `send_message_to_user` -
one search, then speak. Collect the customer's facts before researching in depth.

## 2. What is graded

Only the bank database at the end is graded, and only if the conversation was properly closed.
Nothing you say is graded. A run scores zero when:

1. the conversation is never closed, or
2. the recorded calls differ from what the case required: one missing, one extra, or the right
   call with a wrong value (wrong product, wrong account, wrong timestamp, wrong amount).

## 3. Identity verification comes first

Verify **only** when you must read or change this customer's stored records. A question
answered purely from the knowledge base (rates, fees, how a product works, who qualifies)
needs no verification and **no verification log** - logging one there is a wrong extra write.

When it is needed, do it before any other recorded action:

1. Ask for two of: date of birth, email, phone number, address. Full name and customer ID do
   not count.
2. Look up their record with a read tool and check both values match exactly.
3. Call `get_current_time()`. Use the time it returns - never the date in your system prompt,
   which is a different clock. Copy its date, time and time zone exactly as returned.
4. Call the verification-logging tool once, with the record's values and that time. Once per
   conversation, never before the match.
5. Reveal nothing about the account until step 4 is done.

If the customer cannot give two matching values, say that policy requires two before you can
open their account, and ask again. Never proceed on one value - unless the knowledge base
defines another way. If the customer offers something else (a code, a reference from another
agent or a supervisor), search the knowledge base for it before refusing; if it is defined
there, follow that document exactly, including what it says to log.

Any other argument that is a date or time (a dispute date, a request date) also comes from
`get_current_time()`.

## 4. Find the procedure that applies right now

- Search with the customer's words, then with the specific action. After three searches on the
  same question, act on the best rule you found or tell the customer it is not possible.
- Internal procedures begin with a trigger - "When to use this", "After X is approved", "If the
  customer ...". Follow a procedure only if its trigger is true for this customer **now**.
  Neighbouring documents often describe consecutive stages of one process (submitting a request
  -> applying its approved result). Do the stage that matches the current state, never a later
  one.
- Search the knowledge base before refusing anything the customer asks for or claims.
- If the knowledge base says the customer performs an action with a tool, give it with
  `give_discoverable_user_tool` **once, passing only the tool name**. The customer can then use
  it as many times as needed: in your message, tell them the exact tool name and the argument
  values for each use, and wait for them to use it. Never give the same tool twice. Do not do
  the action for them with an agent tool that has a similar effect.
- Use only tool and argument names that appear in a search result or your tool list. Unlock an
  agent tool once, before its first call, and only if you will call it; then call it as often
  as the case needs.

## 5. When the customer says a value is wrong (rewards, fee, charge, rate)

Many values that look wrong are correct by a rule. Check before you call anything an error:

1. Look up the customer's cards or accounts and the transactions in question.
2. For **each** card or account involved, search `"<card name> exceptions and exclusions"` and
   `"<card name> promo"`, and read the results. Listed merchants or categories may earn 0% or a
   different rate; a promo may raise the rate for a period.
3. With the `think` tool, one line per transaction: amount, category, merchant, the rate that
   applies after step 2's rules, expected value, recorded value.
4. Only a transaction still wrong after step 3 is an error. Tell the customer which ones and
   why the others are correct, then follow the knowledge-base procedure for errors.

## 6. Recommending a card or account

When the customer will apply for, or you will open, a product, the product named in that call
is the graded outcome. Choose it by elimination, never from the first search result:

1. **Ask first** - customers hold back facts until asked: personal or business use; credit
   score; annual income; whether they already have the bank's premium subscription; their main
   spending categories and amounts; every hard requirement; how to break a tie (lowest fee?
   highest rewards?).
2. **List every product in the category** from the knowledge base, not only those the first
   search returned. Then search each product by name for its eligibility / at-a-glance document.
3. **Tabulate with the `think` tool**, one line per product: eligibility (score, income,
   subscription, business), each fee and rate under THIS customer's facts (many terms differ
   with and without a subscription), and pass/fail for every hard requirement. "At least X" is
   met by exactly X.
4. **Eliminate** every product that fails an eligibility rule or a hard requirement.
5. **Break ties the customer's way.** "Highest cash back" means the rate on the categories they
   actually spend in, not the headline rate. "Most money back on a purchase" means amount x the
   rate for that purchase + any sign-up or promo bonus they qualify for - fees. If they give no
   tie-break, or only something vague like "good value": the lowest annual fee wins, then the
   highest reward rate on their main spending category. Never pick a card with an annual fee
   over a no-fee card that meets every requirement unless they ask for it.
6. **Recommend exactly one product by its exact name**, with a one-line reason. If none
   survives, say so.

## 7. State-changing calls: exactly the ones the case needs

- Read-only calls are free; make as many as you need. A read-only discoverable tool (a name
  starting `get_`) is safe to unlock and call whenever you need its data.
- Before opening or closing an account, look up all of the customer's existing accounts first.
  Before closing one, follow the knowledge base's closing procedure in order - if it says to
  move or settle the balance first, do that first.
- When the case covers several items (transactions, accounts, cards), make the action once per
  item, using each item's exact ID copied from a lookup result - never a guessed or combined ID.
- Copy every argument value (IDs, names, amounts, product names) exactly from a tool result or
  the knowledge base, never from memory.
- Do not repeat a write "to be sure". If unsure whether it landed, check with a read tool.
- **Refusing is not doing nothing.** When the knowledge base says a request cannot be granted,
  it usually says what to record (a denial, a closure reason, a note). Record it, then tell the
  customer.
- Do not perform an action the customer did not ask for, however helpful it seems.

## 8. Transfers to a human

- Transfer only when the knowledge base gives you no way to act and the customer agrees, or
  when a customer demands a human for something you can do and has asked four times.
  Scenario guidance in the knowledge base overrides this.
- Search the knowledge base for the transfer reason to use.
- **A transfer does not end the conversation.** After `transfer_to_human_agents`, call
  `send_message_to_user` to tell the customer they are being transferred, then keep answering
  whatever they say next. Never call `end_conversation` straight after a transfer.

## 9. Closing script

1. `send_message_to_user` with the outcome, asking whether there is anything else.
2. A new request -> handle it like the first. They say they are done, or only acknowledge ->
   `end_conversation()`.
3. If a tool result says the conversation already ended, it is closed: make no more
   conversation or domain calls.
4. Call `finish` only after the conversation is closed.

## 10. Budget and errors

- About 100 tool calls; a typical case needs 15-40. Do not ration them or stop early.
- Ten failed tool calls end the run at zero. Never guess a name; if a call fails, read the
  error and fix the arguments; never repeat a failing call unchanged.
- Do not use the file editor or task tracker. Do not call `get_assistant_tool_schemas`.

## 11. If you are unsure whether you are done

```bash
python3 /harbor/skills/stbench-skill/scripts/conversation_state.py
```

It reports whether the conversation is open, your error count and which state-changing calls
have landed. It only tells you whether to keep working or close - never add a call just to
change what it says.

## 12. If the case fits none of the above

Search the knowledge base, do exactly what it authorises and nothing more, tell the customer
the outcome, and close with section 9. Closing a case handled imperfectly always beats leaving
it open.

## Last rule - check it before every turn

Your turn is one tool call. If you are about to write words for the customer, they go inside
`send_message_to_user(message="...")`. Plain text is only for after `finish`.

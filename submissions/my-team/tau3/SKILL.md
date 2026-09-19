---
name: bank-support-conversation
description: Required procedure for a Rho-Bank customer-service conversation run through the tau3-runtime MCP tools. The graded result is the bank database after the conversation, and it only counts if the conversation is ended with end_conversation.
---

# Bank support conversation: the deliverable

Your work is graded on the bank database after the conversation. It is graded ONLY if
the conversation ends properly:

1. Call `start_conversation` exactly once, first. It returns the customer's first message.
2. Every reply to the customer goes through `send_message_to_user`. It returns the
   customer's next message. Text you write outside this tool is never seen by the customer.
3. When the case is resolved, or the customer says goodbye, call `end_conversation`.
   Do this BEFORE you call `finish`. If you call `finish` without `end_conversation`,
   or run out of actions first, the whole task scores zero.

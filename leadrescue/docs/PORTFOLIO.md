# LeadRescue: portfolio summary

**CloudQuest Business Solutions Lab · Module: Inboxic, customer inquiry manager**

## The business problem

A small moving company receives quote requests, date changes, and urgent problems ("the movers haven't arrived") in one inbox. Urgent issues get buried behind routine quotes, staff retype the same details, and replies sometimes promise prices or dates nobody confirmed. Leads go cold and service failures escalate.

## What I built

A working, staff-facing triage application with a human-in-the-loop AI workflow:

- Inquiries are saved first, then analyzed by Amazon Bedrock (Converse API) through a provider interface with schema-validated structured output.
- The AI classifies intent, recommends priority with a reason, extracts only stated facts, summarizes, drafts a reply, lists missing details, and flags manipulation attempts.
- Deterministic guardrails remove invented facts, force manual review for prompt-injection attempts, and block replies that commit to prices, availability, bookings, or free services.
- Staff correct the suggestion, complete a verification checklist, approve, copy the reply, and resolve. Every change is audited. Nothing is sent automatically.
- A gamified practice challenge (Monday Morning Rush) awards XP only for meeting measurable review criteria, with insert-once awards so XP cannot be farmed.
- Business results report time to first review, time to resolution, and how often staff corrected the AI, with measured values clearly separated from targets and sample data.

**Stack:** React, TypeScript, Vite · Python 3.12 Lambda · API Gateway HTTP API with Cognito JWT authorizer · DynamoDB · Amazon Bedrock · CloudWatch · CloudFront/S3 · AWS SAM.

## Demonstrated outcome

- End-to-end workflow runs locally without AWS in a clearly labeled demo mode, using the same API handler, contract, and guardrails as production.
- 71 backend tests, 17 frontend unit tests, and 11 browser tests pass, covering validation, failure handling, authorization, idempotency, duplicate-XP prevention, prompt injection, accessibility scanning, keyboard use, and phone/tablet layouts.
- A 52-case labeled evaluation set and runner measure accuracy, urgent recall, extraction errors, latency, and tokens. The rule-based demo analyzer scored 88.5% accuracy and 8 of 12 urgent cases, missing both targets, which I report as-is. It shows why the live model needs its own evaluation before anyone relies on it.
- Infrastructure as code with least-privilege IAM, passing cfn-lint. Not yet deployed or tested against a live Bedrock model.

## What I would say in an interview

"I treated the AI as a drafting assistant inside a controlled workflow, not as an agent. The model can't send, approve, or discount anything. Server-side guardrails catch invented facts and risky commitments even if the model is fooled, and I measured the baseline honestly instead of tuning it to the test set."

# Evaluation results: demo (demo-rules-v1)

Run at 2026-11-12T11:19:45+00:00 on 52 synthetic inquiries. Synthetic dataset of 52 messages. Results describe this dataset only and do not establish production accuracy.

| Metric | Result | Target | Met |
|---|---|---|---|
| Classification accuracy | 88.5% | at least 90% | no |
| Urgent recall | 8/12 | all urgent cases | no |
| Invented facts after guardrails | 0 | 0 | yes |
| Invented facts in raw output (before guardrails) | 0 | 0 | yes |
| Labeled facts missed | 11 of 73 | informational | - |
| Labeled facts mismatched | 1 of 73 | informational | - |
| Failed calls | 0 | 0 | yes |
| Latency p50 / p95 | 0.3 ms / 0.8 ms | informational | - |
| Tokens (input / output total) | not reported / not reported | informational | - |

## Confusion (expected -> predicted)

| Expected | quote | urgent_issue | schedule_change | manual_review | failed |
|---|---|---|---|---|---|
| quote | 18 | 0 | 0 | 0 | 0 |
| urgent_issue | 1 | 8 | 0 | 3 | 0 |
| schedule_change | 0 | 0 | 9 | 2 | 0 |
| manual_review | 0 | 0 | 0 | 11 | 0 |

## Misclassified cases

- eval-019: expected urgent_issue, predicted quote
- eval-027: expected urgent_issue, predicted manual_review
- eval-028: expected urgent_issue, predicted manual_review
- eval-030: expected urgent_issue, predicted manual_review
- eval-032: expected schedule_change, predicted manual_review
- eval-037: expected schedule_change, predicted manual_review

## Extraction errors

- eval-006: pickupLocation: missed 'Whitesboro'; destination: missed 'Sherman'
- eval-007: pickupLocation: missed 'Denison'; contactName: missed 'Omar'
- eval-008: contactName: missed 'Rachel Kim'
- eval-009: pickupLocation: missed 'Pottsboro'
- eval-010: destination: missed 'Van Alstyne'
- eval-016: pickupLocation: missed 'Howe'
- eval-017: pickupLocation: missed 'Sherman'; destination: missed 'Denison'
- eval-018: pickupLocation: missed 'Tom Bean'
- eval-032: movingDate: expected 'Saturday', got 'Thursday'

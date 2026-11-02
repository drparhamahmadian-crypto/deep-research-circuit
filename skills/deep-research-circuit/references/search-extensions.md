# Coordinator-approved search extensions

Read when the automatic guard is active. Use the initial allowance efficiently, preserve strong leads immediately, and request further work for a named question that could change the answer. The coordinator decides routine extensions; involve the user only for a genuine scope change or their explicit hard ceiling. The initial limit never permits abandoning valuable work.

## One control path

Use `apply_patch` to write JSON under `<evidence_root>/control-actions/`. Run this direct single shell command with actual absolute paths, without variables or command chains:

```text
python3 "/absolute/plugin/hooks/guard.py" control "/absolute/evidence/control-actions/request-1.json"
```

The hook applies the exact contents under the host actor's identity. The command prints the matching receipt; it cannot authorise itself without hooks. A changed file needs a new control ID. Identical contents with the same ID are idempotent; the original receipt describes that decision, not current counters. Use `status` for current state.

Every file contains 1–16 actions applied together or none:

```json
{"id":"request-1","actions":[
  {"op":"register_lead","id":"primary-offer","locator":"https://example.com/actual-offer","importance":"Could reverse the price ranking","next_check":"Read the dated primary terms"},
  {"op":"request_extension","id":"terms-check","units":2,"question":"Does this offer meet every required condition?","next_action":"Open the primary terms and compare the missing condition","expected_gain":"Could exclude the current first choice","lead_ids":["primary-offer"]}
]}
```

Replace illustrative values with observed sources and the actual question. Register leads when discovered, before compression or handoff. Send the request ID and reason to the coordinator. Control-file patches, control commands and existing-agent messages remain available at exhaustion. Do not route retrieval through an exempt tool.

Only the host-identified coordinator can decide:

```json
{"id":"decision-1","actions":[
  {"op":"decide_extension","request_id":"terms-check","decision":"grant","basis":"decision_changing","reason":"The primary condition can change which option qualifies; two calls cover the next check."}
]}
```

Grants add the requested 1–20 units without resetting prior use, and add 4 completion units. Split an oversized stage into a smaller justified request. The guard cannot exceed `[ceiling=N]`. Each stage reserves its final quarter for strong leads. After the result, reassess value; do not pre-authorise endless extensions.

To refuse, set `decision` to `deny`, and `basis` to `duplicate`, `outside_scope`, `adequate_evidence`, `access_blocked` or `user_hard_limit`. Give a concrete evidence-based `reason`; `user_hard_limit` requires approved allowance to reach the recorded ceiling. Refusal retains the request and its leads. Each lead still needs a disposition. “Used the allowance”, a tidy shortlist or an empty search is insufficient.

## Close and review

Complete research/calculations, then the coordinator dispositions every registered lead:

```json
{"op":"dispose_lead","id":"primary-offer","status":"resolved","basis":"source_checked","reason":"The recovered primary terms answer the missing condition.","claim_ids":["offer-condition"]}
```

| Status | Permitted basis | Report treatment |
|---|---|---|
| `resolved` | `source_checked` | Nonempty `claim_ids` linking actual findings |
| `dismissed` | `irrelevant`, `duplicate`, `superseded`, `contradicted` | Specific retained reason; `claim_ids` may be empty |
| `deferred` | `access_blocked`, `user_input_needed`, `user_hard_limit` | Nonempty `claim_ids`, each `unverified`, visibly explaining the remaining lead and uncertainty |

Hard-limit deferral requires actual used units to reach the ceiling. Ordinary stage exhaustion is never a deferral reason. Original source, importance, missing check and action history are retained after disposition.

The coordinator proposes closure with:

```json
{"op":"finish","outcome":"answered","reason":"The primary terms resolve the decisive constraints; the limited comparison scope is stated.","claim_id":"research-coverage"}
```

Use `qualified` or `blocked` if material leads are deferred. Pending requests/leads or an unassessed budget denial block closure. Explain why further work would or would not change the answer using the original request and evidence. Do not claim exhaustive coverage. Obtain current counters and source metadata with `{"id":"status-1","actions":[{"op":"status"}]}`.

The hook writes `research-scope.json`. Copy the receipt's `scope_source` into `claims.json.sources` unchanged. Add the closure's `claim_id` as a marked `supported` scope claim in the draft/manifest, citing source ID `research_scope`, locator `local:research-scope`, role `primary` and an exact passage from the snapshot. Describe the examined scope and material uncertainty accurately. This local source proves what was recorded, not external facts.

Give the independent reviewer the original request, raw source returns, report, manifest and current scope snapshot. They assess valuable omissions, extension decisions, dispositions and stopping justification alongside factual claims. Use the existing claim validator and one genuine `review.json` attestation. Never approve your own scope claim. New work or decisions require the new snapshot and reassessment of affected claims plus final coverage; never transplant old approval to new hashes. Stop clears only the current independently reviewed report.

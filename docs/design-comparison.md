# Why the checks belong together

Deep Research Circuit connects exploratory research with a versioned evidence and review record. Its distinctive mechanism is the connection between the final report, captured source bytes, claim manifest and separate review. The same workflow tracks registered leads and decisions about further research.

## What a citation check leaves open

A quotation can still appear in a source after another part of that source changes. A citation can remain valid after the report has been edited. Checking the citation alone does not establish that a reviewer assessed the current version.

Deep Research Circuit checks the captured artifact's hash as well as quotation presence, then binds the review to the report and manifest hashes. The public [validator tests](../tests/test_claim_validator.py) reproduce both cases: a source-body edit while the quotation remains, and changed drafts or manifests that invalidate a review.

## Why leads need their own record

A research allowance tells the coordinator how much work has been counted. It does not tell them what happened to a promising unexamined source. Deep Research Circuit gives registered leads a recorded next check and disposition. Refusing an extension does not silently dispose of the lead, and granting one does not reset earlier usage.

The [extension tests](../tests/test_search_extensions.py) exercise coordinator decisions, cumulative allowances, denied-lead retention, deferred findings and closure. These checks make targeted research decisions inspectable.

## Why the final version matters

The optional guard snapshots the report, evidence, review and scope at completion. It validates that snapshot and compares the rendered report with the final generated text. A subsequent source or scope change cannot keep an earlier clearance. The [guard tests](../tests/test_research_guard.py) and [scope-change tests](../tests/test_search_extensions.py) exercise this final agreement.

## Source comparison

A source review on 3 November 2026 compared these mechanisms with Hyperresearch at commit [aece65f](https://github.com/jordan-gibbs/hyperresearch/tree/aece65f9307197119629beacf8aeaf8cc80e999a). That project already includes a research pipeline, citation checks, budget controls and Codex hooks. Deep Research Circuit is independently implemented and shares several research-workflow ideas with that broader field.

| Mechanism | Hyperresearch code inspected | Deep Research Circuit implementation |
|---|---|---|
| Evidence and review binding | [Claim ingestion](https://github.com/jordan-gibbs/hyperresearch/blob/aece65f9307197119629beacf8aeaf8cc80e999a/src/hyperresearch/core/claims.py) hashes claims; [citecheck](https://github.com/jordan-gibbs/hyperresearch/blob/aece65f9307197119629beacf8aeaf8cc80e999a/src/hyperresearch/core/citecheck.py) checks sentence/citation-to-note pairs. | One hash contract connects the report, captured artifacts, full claim manifest and separate review. |
| Research control | [Run state](https://github.com/jordan-gibbs/hyperresearch/blob/aece65f9307197119629beacf8aeaf8cc80e999a/src/hyperresearch/core/runs.py) records estimated spend and source/note limits; workflow instructions retain leads. | Covered-call accounting, reserved lead allowance and structured extension/disposition records share persistent state. |
| Completion | [Codex Stop handling](https://github.com/jordan-gibbs/hyperresearch/blob/aece65f9307197119629beacf8aeaf8cc80e999a/src/hyperresearch/core/codex.py) checks active pipeline progress; a separate finish command checks output requirements. | Stop-time frozen-snapshot validation checks the evidence/review bindings, scope closure and rendered final text together. |

This comparison describes the inspected code, not every research system or a performance ranking. The contribution is a specific implementation of connected research control and evidence integrity. [Development results](development-evaluation.md) document how it behaved in the recorded evaluations.

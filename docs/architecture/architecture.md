# Deep Research Circuit — source-bound architecture and animation brief

**Purpose.** Explain the local Deep Research Circuit 0.2.0 release candidate to reviewers and developers. The circuit is a research procedure with a deterministic record checker, a separate human or agent judgment step, and an optional Codex hook. The standalone validator extraction contains **only** the unchanged `validate_claims.py`, synthetic fixtures and tests; its optional hooks are absent.

## Architecture

Render [`architecture.mmd`](architecture.mmd) as the static reference. Its boxes correspond to actual files or processes:

| Stage | Existing responsibility | Boundary to show |
|---|---|---|
| Scope | The skill preserves the question and constraints, identifies decisive unknowns, and chooses a proportionate opening stage. | Workflow instructions guide an agent; they do not mechanically compel every research choice. |
| Leads and allowance | **Optional guard mode** registers leads, accounts for covered tool calls, permits bounded extensions through the host-identified coordinator, and requires lead dispositions before closure. | It counts intercepted calls, not all network requests, money or tokens. Guard activation and host callback coverage must be observed. |
| Retrieval record | Research uses available tools and saves recovered source text with locator, observation time, origin, role, status and artifact hash. | Source labels and timestamps are declarations; the checker does not authenticate them. |
| Draft and ledger | `report.md` marks registered claim lines; `claims.json` binds those exact lines to cited sources, quotations, statuses, report hash and artifact hashes. | Other prose is allowed. A reviewer must find consequential unmarked assertions. |
| Mechanical preparation | `review-template` checks local records and creates **pending** verdicts bound to manifest and report hashes. | A generated template is not a review. |
| Independent judgment | A separate reviewer examines the full report and original evidence, including meaning, omissions, provenance and uncertainty, then records coverage and verdicts in `review.json`. | Distinct recorded IDs are checked; actual reviewer identity and independence are not authenticated. |
| Clearance and render | `check` verifies the records and recorded review; `render` succeeds only after a pass and removes claim markers. | A pass establishes local consistency, not factual truth or live availability. |
| Optional Stop audit | If loaded, trusted and invoked, the Codex hook snapshots the files, runs `check` and `render`, compares the generated final text, checks scope closure and records `guard-check.json`. | Stop cannot retract text already generated or cover unhooked paths. |

**Invalidation rule:** an edit to `report.md` or `claims.json` changes the bytes bound in `review.json`; an artifact edit breaks its hash in `claims.json`. A new source, lead disposition or research call can change `research-scope.json` and its source hash. Recheck, obtain a fresh review of affected claims and coverage, then render the revised report. Do not animate an old approval sliding onto new bytes.

## Animated explainer: seven beats

Keep the claim ledger at the centre: research inputs enter from the left, the marked report enters above, and review and checks branch to the right. Animate the relevant route and state without moving the structure. Offer pause, replay, keyboard access, reduced motion, and a static diagram fallback. The visual vocabulary is **solid = recorded path**, **dashed = optional host hook**, **orange = active dependency**, and **amber = invalidated binding**.

1. **Frame.** The question enters with scope and constraints. A short subtitle identifies decisive unknowns; the workflow is visibly labelled “instructions”.
2. **Search with memory.** A covered retrieval call enters the optional allowance meter. A promising lead is registered, then either checked, dismissed with a reason, or deferred into visible uncertainty. The meter never stands for answer quality.
3. **Capture.** A retrieval result becomes a saved text artifact and a source record. Display locator, check time, retrieval status and a short hash token; an empty or failed result visibly stays unusable for a supported claim.
4. **Bind.** A marked report claim connects to a source ID and exact quote in `claims.json`. Show report and artifact fingerprints locking to the ledger. An unmarked sentence remains on the page to cue full-draft review.
5. **Challenge.** Mechanical preparation produces pending review slots. A **separate reviewer** reads the full draft and original source, then records coverage and verdicts. Do not depict automated semantic judgment.
6. **Check and release.** A successful local `check` lights `render`, which removes the markers and shows the reader report with its limits. If the optional Codex guard is active, Stop additionally compares the final generated text with the same frozen render and checks closure.
7. **Change and invalidate.** Edit the report or an artifact. The relevant fingerprint turns amber, the old review loses clearance, and render pauses until rebinding and reassessment. End on the distinction: **“Records agree”** versus **“Meaning requires review.”**

## Implementation status for the explainer

- **Current release candidate:** instruction-led research workflow; bundled deterministic validator; separate recorded review; optional local Codex hook and SQLite control state in this repository.
- **Current portable portfolio package:** standalone validator with synthetic demonstration and 26 passing offline tests recorded on 2026-11-03. The demonstration's review is synthetic and no semantic validation was performed.
- **Current visual:** `index.html` implements the seven-beat animation, and `architecture.svg` is its static export. Both use the local Chakra Petch asset and OFL notice in `assets/fonts/`. This figure does not imply an independent live review, public release, or measured accuracy gain.

## Source map

The following links resolve to the packaged source. Original snapshot provenance is in [PROVENANCE.md](../../PROVENANCE.md).

- [Workflow and boundaries](../../skills/deep-research-circuit/SKILL.md)
- [Leads and extensions](../../skills/deep-research-circuit/references/search-extensions.md)
- [Claim/review contract](../../skills/deep-research-circuit/references/claim-validation.md)
- [Validator and render](../../skills/deep-research-circuit/scripts/validate_claims.py)
- [Scope/control state](../../hooks/research_control.py)
- [Optional host guard](../../hooks/guard.py)

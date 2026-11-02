# Claim/source validation before final clearance

The bundled Python 3 helper checks a marked draft, source artifacts, citation bindings and a separate independent-review attestation. It makes no network or model calls, installs nothing and changes no files. Run it with an explicit interpreter. Work in the current study or a disposable evidence folder, not the plugin-development root or an unrelated study. Keep one manifest/review per draft, rather than a new file per claim.

## What it can establish

- Registered claim IDs and text match the marked draft. The report, artifacts and independent review have matching SHA-256 fingerprints.
- Cited source IDs/locators match the ledger, exact quotations occur in recovered text, declared source roles meet requested roles, and successful-but-empty/metadata/failed retrievals cannot support factual clearance.
- Explicit historical dates, visible inference/uncertainty labels and any supplied freshness limit are preserved. Historical evidence uses its original artifact; a later failed attempt is a separate source record.
- Every registered claim has a review verdict, coverage is attested, and the recorded reviewer ID differs from the producer ID. Changing the report or manifest invalidates that review.

It does **not** authenticate sources, snapshots, role/origin labels, check times or reviewer identities. It does not prove that a quote entails a claim, that every meaningful assertion was registered, that a seller offer remains available, or that a declared freshness limit is appropriate. Faithful records and actual independent review are required. Passing means the local records and recorded review agree; never present it as a truth certificate or measured reduction in hallucinations. Optional [Codex guard hooks](automatic-guard.md) run this check automatically when loaded, trusted and activated. They do not provide surface-independent enforcement or intercept every answer before display.

## Prepare the draft and evidence

Each registered claim occupies one line: `[[claim:price]] <exact claim text>`. Other prose is allowed. The reviewer must inspect the full draft and register any omitted load-bearing assertions. `render` removes the markers after a successful gate; the user receives the original prose without implementation annotations.

Capture evidence during retrieval, and reuse one source record wherever it supports several claims. Register decision-driving factual assertions and their necessary premises, not administrative narration merely to increase the claim count. Keep coherent related facts together only when the same evidence and verdict cover them; split claims whose scope, support or uncertainty differs. The reviewer still checks consequential unmarked prose. Freeze wording and formatting before final review where practical, so cosmetic edits do not cause avoidable rebinding.

Save actual recovered UTF-8 text for `plain_text`. `mcp_json` also supports the original Crawl4AI/Scrapling-style envelopes: text content blocks, string `result`, or structured content with text/result. An HTTP/error status is inspected when present; the validator does not stringify metadata into evidence. Other raw formats must first be extracted with an appropriate tool and reviewed against the original. Rendered text and local-document extracts are valid; raw image/PDF bytes or arbitrary HTML are not parsed by this helper. Keep the original image/document accessible for semantic review of any extracted/transcribed text.

An MCP artifact's embedded source locators must agree with one another; conflicting outer/nested/block URLs are rejected rather than mixing their content. A usable captured locator is also checked against the manifest. If an artifact contains no locator, that binding remains a reviewed declaration. Supported sibling structured/text/result channels are all inspected, so one cannot hide another's conflicting locator or failure flag. Preserve redirects separately or use an inspected single-source text capture with its actual final locator. Nested JSON objects/arrays are handled as supported envelopes or metadata, not promoted to body text; encoded JSON strings are unwrapped under a bounded nesting limit. Recognisable malformed serialized objects/arrays, duplicate keys and non-finite JSON values are rejected rather than retried as prose. For a JSON dataset or ordinary body text that is ambiguous with serialized JSON, retain the original and save its relevant inspected extract as `plain_text` for review.

The manifest and its report/artifact files share an evidence directory. Report/artifact paths are relative; absolute paths, `..` traversal and symlinks escaping that directory are rejected. Individual input files are limited to 20 MiB. Use exact web URLs or `local:`/`attachment:` identifiers for non-web sources; never invent a public URL for a local file. An independently reached seller result may support a quote even if its original aggregator handoff failed. A constructed URL's parameters alone do not prove the site applied them.

Fabricated example manifest (the fingerprints below are placeholders to replace with actual helper output):

```json
{
  "schema_version": 1,
  "producer_id": "researcher-1",
  "report": {"path": "report.md", "sha256": "<report fingerprint>"},
  "sources": [{
    "id": "catalog",
    "locator": "local:synthetic-catalog",
    "origin": "observed",
    "role": "primary",
    "observed_at": "2025-01-01T10:00:00+00:00",
    "retrieval_status": "recovered",
    "content_kind": "local_text",
    "format": "plain_text",
    "artifact": "catalog.txt",
    "sha256": "<artifact fingerprint>"
  }],
  "claims": [{
    "id": "price",
    "text": "On 2025-01-01, the synthetic catalog listed a widget at 42 units.",
    "status": "historical",
    "as_of": "2025-01-01",
    "citations": [{"source_id": "catalog", "locator": "local:synthetic-catalog",
                   "quote": "42 units", "expected_role": "primary"}]
  }]
}
```

All shown fields are required except `as_of`, which is required for `historical`; `freshness_hours` is optional. Use exact captured locators, including query strings when present, rather than substituting the example's generic URL.

- Source `origin`: `retrieved`, `observed`, `constructed`, `unknown`. Unknown origin cannot clear a supported claim; a constructed URL can support content actually recovered there, while retaining its declared origin.
- Source `role`: `aggregator`, `seller`, `primary`, `secondary`, `other`. Citation `expected_role` accepts those or `any`. The helper compares declarations; the reviewer establishes whether they are accurate.
- `retrieval_status`: `recovered`, `empty`, `failed`. `content_kind`: `body`, `rendered_text`, `local_text`, `metadata`. These describe the captured evidence, not a later attempt.
- Claim `status`: `supported`, `historical`, `inference`, `unverified`. Inference text starts `Inference:` and cites its premises. Unverified text starts `Unverified:`; it may have no citations or refer to a failed attempt. Those labels do not excuse a misleading conclusion elsewhere in the draft.
- Historical `as_of` is an ISO date that must appear in the claim. Optional positive `freshness_hours` rejects older supporting captures against the execution clock. It has no invented default; for changing facts choose an appropriate limit and state remaining availability uncertainty. Observation times require a UTC offset; future captures are rejected.

## Run the existing research/review flow

Resolve `scripts/validate_claims.py` relative to this skill's folder; `VALIDATOR` below is that absolute path. Run commands in the study evidence directory. The helper writes results to stdout; shell redirection creates the intended files.

```sh
python3 "$VALIDATOR" fingerprint catalog.txt
python3 "$VALIDATOR" fingerprint report.md
python3 "$VALIDATOR" review-template claims.json > review.json
```

The template binds the exact manifest bytes and report bytes; there is no self-referential hash. It starts with an empty reviewer ID, incomplete coverage and pending verdicts. Give the independent reviewer the **full draft**, manifest, original evidence/locations and template. The reviewer must actually assess source meaning, scope, qualifications, URL origin and unregistered consequential prose. They set their ID, `coverage_complete: true` only after that assessment, and each claim's verdict/reason. Use `supported` for supported/historical/inference claims, `appropriately_qualified` for unverified claims, and `unsupported` when the evidence fails. Do not preapprove the template or invent another reviewer's identity/verdict.

Run the mechanical preparation before assigning final semantic review: `review-template` succeeds only when the local records pass. Correct its reported record errors first. IDs, including producer/reviewer aliases, must start with an ASCII letter, contain only letters, digits, `_`, `-` or `.`, and be at most 64 characters; a full agent path containing `/` is not valid. Preserve the real reviewer-to-alias correspondence in the handoff. For revisions use the scoped reassessment in [roles.md](roles.md); a new fingerprint requires renewed independent attestation, not a new search from scratch.

```sh
python3 "$VALIDATOR" check claims.json --review review.json
python3 "$VALIDATOR" render claims.json --review review.json
```

Exit 0 permits rendering under this procedure. Missing/failed/stale review or mechanical errors exit nonzero; failed `render` emits no report on stdout. `check` emits JSON including error codes and explicit limits. Correct the actual evidence or narrow/qualify the claim, then obtain independent reassessment bound to the revised files. Do not edit a quotation or source record merely to force a pass. A new snapshot or changed declared metadata changes the manifest fingerprint and requires review again. Unsupported useful leads may remain clearly unverified; supported findings need not be discarded.

If the surface cannot execute local Python, disclose that the mechanical gate was not run and do not claim verified clearance. Do not add a fallback reasoning provider, paid service, installation, or new team architecture. This procedure uses the existing coordinator/researcher/writer/reviewer roles.

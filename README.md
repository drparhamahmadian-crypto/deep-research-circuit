# Deep Research Circuit

Deep Research Circuit is an adaptive research workflow for open questions and detailed evidence work. It helps an agent decide what to investigate next, follow promising leads and build an answer whose claims can be checked against saved sources.

Its original contribution brings research control and evidence review into the same process. The question can evolve as the investigation develops, while the sources, claims and reviewed draft stay connected.

![Architecture](docs/architecture/architecture.svg)

[Explore the circuit](docs/architecture/index.html) · [Development results](docs/development-evaluation.md) · [Source map](docs/architecture/architecture.md)

## Why this design matters

A citation can point to the right source while the report or evidence has changed since review. Deep Research Circuit binds the draft, captured artifacts, claim manifest and separate review with SHA-256 hashes. Changed material cannot reuse an older clearance. The checker connects the review to the version that reaches the reader.

Research also needs room to follow a useful discovery. The workflow records promising leads, their next checks and their eventual disposition. Its optional controller accounts for covered research calls and bounded extensions without resetting earlier usage. An allowance becomes a point to reassess the enquiry rather than a reason to lose an unresolved lead.

The final check brings those records together before rendering the report. A separate reviewer examines meaning, competing explanations and omissions; the code checks that the reviewed material and delivered material agree.

The [design comparison](docs/design-comparison.md) explains the failure cases these checks address and the implementation differences found in a pinned research-pipeline source review.

## Focused effort, flexible depth

Start with a loose question, a comparison or one precise claim. The workflow chooses methods for that enquiry and identifies the evidence that could change the answer. It directs agents to reuse applicable material, avoid repeated failed searches, and add specialist work when a distinct check needs it.

For a broad question, that means preserving scope while following worthwhile discoveries. For evidence digging, it means recovering the decisive passage, recording its location and testing what it supports. The same process can move between discovery and close examination as the question demands.

## Tested through development

The published package has a reproducible suite of 59 offline tests covering evidence bindings, review invalidation, guard state and lead accounting.

An earlier live development enquiry linked 49 claims to 62 source artifacts. Two separate agent reviewers recorded 45 supported claims and four appropriately qualified claims. Their work corrected source bindings, scope, an unsupported inference, a calculation/date issue and missing alternatives. Targeted challenge checks rejected six modified cases and accepted the intact control.

The [development evaluation](docs/development-evaluation.md) explains the cases, versions and recorded outcomes. The [verification receipt](verification.json) records the current package checks.

## Across subjects and countries

The included procedures cover scientific evidence, software and developer tools, legal and policy questions, business results, quantitative checks, history, and practical comparisons such as products or travel. Source selection follows the actual country, jurisdiction and question.

Read the [research skill](skills/deep-research-circuit/SKILL.md) for the procedure and its subject guides.

## Try it

The checker uses Python's standard library. From the repository directory:

```sh
python3 skills/deep-research-circuit/scripts/validate_claims.py check examples/synthetic/claims.json --review examples/synthetic/review.synthetic.json
python3 skills/deep-research-circuit/scripts/validate_claims.py render examples/synthetic/claims.json --review examples/synthetic/review.synthetic.json
python3 -m unittest discover -s tests
```

The example uses fictional evidence and a synthetic review record. It demonstrates the file format and check/render process. The recorded package run passed 59 tests on Python 3.15.2.

## Optional completion control

The default plugin manifest provides the skill and helpers. To use Codex hooks, review [automatic-guard.md](skills/deep-research-circuit/references/automatic-guard.md) and the separate [hook manifest example](plugin.with-hooks.example.json). The host's installation and trust process controls activation.

An active guard recognises a prompt beginning with `$deep-research-circuit`, `Use Deep Research Circuit` or `Run Deep Research Circuit`. Use `/drc end` to end an active guard. It retains research files under `<cwd>/research-workspaces/` and state under the host's `PLUGIN_DATA`; use a separate study directory.

The [validation notes](docs/validation-notes.md) describe the checker contract, host coverage and current test scope. A [proposed CI workflow](docs/ci/offline-checks.yml) is included for future activation.

## Licence and provenance

Deep Research Circuit is an independently developed, AI-assisted project licensed under [Apache-2.0](LICENSE). [PROVENANCE.md](PROVENANCE.md) records its source snapshot and credited method adaptations. [NOTICE](NOTICE) retains project and source attribution. The bundled Chakra Petch font retains its OFL 1.1 licence.

Version 0.2.0 is the first public prototype.

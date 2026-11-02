# Provenance and review status

The source was the local `plugin/parham-deep-research/` 0.2.0 candidate in the original deep-research project. [source-sha256.txt](source-sha256.txt) records SHA-256 values for its original text files using project-relative identifiers. It is a snapshot identifier, not proof of authorship or redistribution rights. The source contained no licence file or repository history in the inspected snapshot.

The original package's files were copied except Python bytecode. Product names, identifiers, activation phrases, end command, temporary/output prefixes and status messages were renamed. The guard now rejects the package root and descendants as study roots. The default manifest no longer registers hooks; an example manifest retains the optional hook declaration. A personal shopping default and a travel-specific example were replaced with general guidance and fictional data. The other research and validation algorithms were retained. This is a locally developed, AI-assisted project; the source-snapshot hashes identify its lineage rather than proving sole human authorship.

## Method sources

The following source references were checked on 3 November 2026. The local procedures are independently worded method adaptations; no upstream implementation or prompt files are bundled. No substantial prose copy was identified in this bounded review.

| Local reference | Primary method source and revision | Licence/reuse boundary |
|---|---|---|
| Legal element mapping | [Anthropic claim-chart](https://github.com/anthropics/claude-for-legal/blob/4a6c651889c97cc9140580363c73e0eb17379c2b/litigation-legal/skills/claim-chart/SKILL.md) | Apache-2.0; adapted and rewritten, source credit preserved. |
| Status propagation | [Anthropic gap-surfacer](https://github.com/anthropics/claude-for-legal/blob/210fd7a6cffaa86a2f8c0fee12a7d155c37ef23c/regulatory-legal/skills/gap-surfacer/SKILL.md) | Apache-2.0; locally extended date/status procedure. |
| Source coverage | [Anthropic reg-feed-watcher](https://github.com/anthropics/claude-for-legal/blob/c1998de2e63b916d9c8f3b8db0fedd5c6bac69ed/regulatory-legal/skills/reg-feed-watcher/SKILL.md) | Apache-2.0; method inspiration for separately written coverage and lead-retention procedure. |
| Calculation pass | [Anthropic SDK demos data-analyst prompt](https://github.com/anthropics/claude-agent-sdk-demos/blob/1d78e34f47a1b1e05cbf41d7abecb5d9a5f8a6b8/research-agent/research_agent/prompts/data_analyst.txt) | Method-only inspiration; no code or prompt text included. No repository-root licence was found at that revision; this project does not grant rights to that upstream material. |

Other linked sources are references to public guidance, not bundled source text or assets. Geographic examples and the former Victorian property-checklist link were removed in favour of jurisdiction-neutral source selection. The [claude-for-legal licence](https://github.com/anthropics/claude-for-legal/blob/4a6c651889c97cc9140580363c73e0eb17379c2b/LICENSE) is Apache-2.0; no upstream root NOTICE was present in the inspected revisions.

Offline guard and extension tests were adapted from `tests/test_research_guard.py` and `tests/test_search_extensions.py` in the original project. Claim-validator tests and the synthetic example were adapted from the workspace's `portfolio/evidence-ledger-validator/`, whose code was copied from the original candidate. Synthetic fixture records are not original travel evidence and their reviewer attestations do not represent actual review. The source-specific workspace-isolation test concerns a separate bridge and is not included.

## Licence and limits

The project is licensed under [Apache-2.0](LICENSE). Source credits and modified-method notices are retained, with project attribution in [NOTICE](NOTICE). Any bundled fonts retain their own licences and notices; the documentation identifies those assets separately.

The release is a prototype with hooks disabled by default. Offline payload tests do not establish live host compatibility, research quality, source authenticity or universal enforcement. A live host check is required before claiming verified live hook compatibility.

# Development and evaluation

Deep Research Circuit keeps a research answer tied to the source material and review that cleared it. Each marked claim has a record of its source, captured text, locator and status. The claim manifest stores hashes of the report and each source artifact. The review stores hashes of that exact manifest and report. The validator checks those records before rendering. When the optional guard is active, its Stop audit also compares the final answer with the checked report. If the draft changes after review, the old review cannot clear it.

The search guard tracks covered Codex calls and batch items. It signals the last quarter of an allowance for the strongest open leads. A researcher can ask for more calls only with a named question, next check and expected value. The coordinator decides, and an extension does not reset calls already used. A registered lead stays open until the source is checked, it is dismissed for a recorded reason, or it is deferred with a visible qualification in the report. That gives the workflow a concrete way to direct effort toward evidence that could change the answer.

## Applied evaluation

On 22 October 2026, one live enquiry produced a report with 49 marked claims and 62 saved source artifacts. Two separate reviewer agents assessed the report against those records. They marked 45 claims supported and four appropriately qualified. Their reviews caught source mismatches, an overbroad inference, a date and calculation problem, and a missing material alternative. The report changed after review. Its final check and render passed.

The same enquiry tested recovery from an empty source response. The workflow retained the failed retrieval as a failure. It did not use that response to support a claim that required recovered source text. A separately recovered source was needed for that claim.

A seven-case challenge set included four mechanical rejections and two semantic review rejections. One valid control passed. The six blocked renders returned zero report bytes. This shows what the gate did on those selected cases; it does not estimate its error rate across research tasks.

## Follow-up on shared evidence

On 23 October, a separate two-enquiry run gave two model workflows the same 16-source packet. This checked interpretation and completion against fixed evidence, not web search or source discovery. One report cleared after the coordinator checked it. The other remained blocked after a revision left its report and review records out of sync. That outcome shows why a draft change must trigger a new review.

## Current test snapshot

The local package snapshot dated 3 November 2026 reports **59 offline tests passed** on Python 3.15.2. Its package metadata still labels the plugin 0.2.0. The receipt also records one separate simulated activation check. The 59 tests use synthetic evidence and temporary state. See the [verification receipt](../verification.json), [validator tests](../tests/test_claim_validator.py), [guard tests](../tests/test_research_guard.py) and [extension tests](../tests/test_search_extensions.py).

The evaluation receipts recorded elapsed time and call units. The targeting mechanism is visible in the source: reuse applicable evidence, reserve allowance for promising leads and require a concrete reason for an extension. These records do not supply a matched token or API-cost comparison.

## Reading these results

The live evaluation covers one applied enquiry and a selected challenge set. The two-enquiry follow-up reused a fixed evidence packet. The offline tests check that records and guard decisions follow their rules. The simulated activation check does not establish a live Codex hook installation. The receipt does not report a hosted CI run. These results describe this local prototype and its tested conditions.

## Source records

The SHA-256 digests below identify the original development records. Their case details and raw captures are not included here.

| Record | Date | SHA-256 |
|---|---|---|
| Original 0.1.7 closure review | 22 October 2026 | `4d3c45979f04a13ac6da998e6bb8663770137c3b5a24b5599c400e60fd2f42d3` |
| Original 0.1.9 final enquiry review | 23 October 2026 | `720ec729f9306bca18244b87323dc0e12c852f198e455172c7ce87712a2de623` |
| 0.1.9 package receipt | 23 October 2026 | `39879d610e1c3127e436c852bbf315b0d81c99c97f2936cd3e6f33e8dd65c572` |
| Original 0.2.0 extension review | 23 October 2026 | `de6552e54d1ee0ba2ccec6580ba18a092bd8c56ac9c138cb2c909ed52785621c` |
| 0.2.0 package receipt | 23 October 2026 | `ee0db9b78e13aaafc92f12d71e396947079664d2cf3b81c746689dbd0e3251d9` |
| Current local package verification receipt | 3 November 2026 | `8dffeb5a4bc01774e88112fc5c65b73839e83b8fc822cf1cf82abd075e2b0cb8` |

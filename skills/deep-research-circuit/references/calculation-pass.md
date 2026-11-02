# Decision-changing calculations

Use a focused calculation pass when numbers determine the conclusion. The same agent can do it; add an analyst only when complexity warrants one.

Inspect and cite inputs. Check that definitions, populations, periods, units and denominators permit the comparison. Separate measured inputs from assumptions or estimates. Recompute with a calculator or script where an error could change the decision; preserve the formula, material assumptions and appropriate precision.

Review input validity and interpretation as well as arithmetic. Reproducible arithmetic does not validate its inputs. Report a missing input or invalid comparison rather than inventing a result.

Workflow inspiration: [Anthropic's data-analyst role](https://github.com/anthropics/claude-agent-sdk-demos/blob/1d78e34f47a1b1e05cbf41d7abecb5d9a5f8a6b8/research-agent/research_agent/prompts/data_analyst.txt). The calculation safeguards above are separately written for Deep Research Circuit; no SDK-demo code or prompt text is included. This optional check is not a demonstrated accuracy gain.
